import sys
import logging
import os
from tqdm import tqdm
from azure.storage.blob import BlobClient
from azure.identity import InteractiveBrowserCredential
import psycopg2
import json
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reduce noise from Azure and external libraries
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

# Constants
AZURE_ACCOUNT_URL = config.AZURE_ACCOUNT_URL
CONTAINER_NAME = config.CONTAINER_NAME
BLOB_NAME = config.BLOB_NAME
CSV_FILE = config.CSV_FILE
DB_CONFIG = config.DB_CONFIG
SCHEMA_NAME = config.SCHEMA_NAME

def get_last_blob_size():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute(f'SELECT config_value FROM "{SCHEMA_NAME}"."app_config" WHERE config_key = %s', ('LAST_BLOB_SIZE',))
            row = cur.fetchone()
            if row:
                return row[0]
    except Exception as e:
        logger.warning(f"No se pudo leer LAST_BLOB_SIZE de la DB: {e}")
    return None

def set_last_blob_size(size):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            insert_query = f"""
            INSERT INTO "{SCHEMA_NAME}"."app_config" (config_key, config_value)
            VALUES (%s, %s)
            ON CONFLICT (config_key) DO UPDATE 
            SET config_value = EXCLUDED.config_value;
            """
            cur.execute(insert_query, ('LAST_BLOB_SIZE', json.dumps(size)))
        conn.commit()
    except Exception as e:
        logger.error(f"Error actualizando LAST_BLOB_SIZE: {e}")


def download_blob_file(force=False):
    logger.info("Tentando descargar archivo desde Azure Blob Storage...")
    
    credential = None
    try:
        logger.info("Autenticando...")
        credential = InteractiveBrowserCredential()
    except Exception as e:
        logger.error(f"Error creando credencial: {e}")
        sys.exit(1)

    try:
        blob_client = BlobClient(
            account_url=AZURE_ACCOUNT_URL,
            container_name=CONTAINER_NAME,
            blob_name=BLOB_NAME,
            credential=credential
        )

        properties = blob_client.get_blob_properties()
        blob_size = properties.size
        last_size = get_last_blob_size()

        if not force and last_size == blob_size:
            logger.info("El archivo remoto tiene el mismo tamaño que el último procesado. Saltando descarga.")
            return False
        else:
            if force and last_size == blob_size:
                logger.info("Fuerzo de descarga activado (el archivo remoto tiene el mismo tamaño). Descargando de todos modos...")
            else:
                logger.info(f"El tamaño remoto difiere o es nuevo (Último: {last_size}, Remoto: {blob_size}). Descargando...")

        logger.info(f"Descargando {BLOB_NAME} a {CSV_FILE} (Tamaño: {blob_size / (1024*1024):.2f} MB)...")
        
        import time
        CHUNK_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB chunks
        part_file = f"{CSV_FILE}.part"
        
        if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) < blob_size:
            if os.path.exists(part_file):
                os.remove(part_file)
            os.rename(CSV_FILE, part_file)
        
        initial_offset = 0
        if os.path.exists(part_file):
            initial_offset = os.path.getsize(part_file)
            if initial_offset > blob_size:
                logger.warning("El archivo temporal parcial excede el tamaño remoto. Reiniciando descarga...")
                initial_offset = 0
            elif initial_offset > 0:
                logger.info(f"Reanudando descarga desde byte {initial_offset} ({initial_offset / (1024*1024):.2f} MB ya descargados)...")

        file_mode = "ab" if initial_offset > 0 else "wb"
        
        with open(part_file, file_mode) as my_blob:
            with tqdm(total=blob_size, initial=initial_offset, unit='B', unit_scale=True, desc=CSV_FILE) as pbar:
                offset = initial_offset
                while offset < blob_size:
                    current_chunk = min(CHUNK_SIZE_BYTES, blob_size - offset)
                    for attempt in range(1, 6):
                        try:
                            stream = blob_client.download_blob(offset=offset, length=current_chunk, timeout=120)
                            data = stream.readall()
                            my_blob.write(data)
                            my_blob.flush()
                            pbar.update(len(data))
                            offset += len(data)
                            break
                        except Exception as chunk_err:
                            logger.warning(f"Error descargando fragmento {offset}/{blob_size} (intento {attempt}/5): {chunk_err}")
                            if attempt == 5:
                                raise chunk_err
                            time.sleep(attempt * 2)
        
        if os.path.exists(part_file) and os.path.getsize(part_file) == blob_size:
            if os.path.exists(CSV_FILE):
                os.remove(CSV_FILE)
            os.rename(part_file, CSV_FILE)
            logger.info("Descarga completada exitosamente. Actualizando estado en BD...")
            set_last_blob_size(blob_size)
            return True
        else:
            raise Exception("El tamaño del archivo descargado no coincide con el tamaño esperado.")

    except Exception as e:
        logger.error(f"Error durante la descarga: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import sys
    force_download = False
    
    # Soporta tanto "-force" como "--force", opcionalmente seguido de "true/1/yes"
    for i, arg in enumerate(sys.argv):
        if arg.lower() in ["-force", "--force"]:
            if i + 1 < len(sys.argv) and sys.argv[i + 1].lower() in ["true", "1", "yes"]:
                force_download = True
            else:
                force_download = True
            break
            
    download_blob_file(force=force_download)
