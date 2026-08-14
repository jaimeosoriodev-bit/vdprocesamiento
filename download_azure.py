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
        
        with open(CSV_FILE, "wb") as my_blob:
            stream = blob_client.download_blob()
            with tqdm(total=blob_size, unit='B', unit_scale=True, desc=CSV_FILE) as pbar:
                for chunk in stream.chunks():
                    my_blob.write(chunk)
                    pbar.update(len(chunk))
        
        logger.info("Descarga completada exitosamente. Actualizando estado en BD...")
        set_last_blob_size(blob_size)
        return True

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
