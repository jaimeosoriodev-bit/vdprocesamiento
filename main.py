import logging
import os
import sys

# Import local modules
import download_azure
import etl
import classify
import dump_db
import upload_minio

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("========================================")
    logger.info("=== INICIANDO ORQUESTADOR GLOBAL ETL ===")
    logger.info("========================================")
    
    # 1. Descarga desde Azure
    logger.info("\n>>> FASE 1: DESCARGA DESDE AZURE BLOB STORAGE")
    try:
        force_download = any(arg.lower() in ["--force", "-force", "-f"] for arg in sys.argv[1:])
        if force_download:
            logger.info("Flag de forzado detectado: se forzará la descarga del blob.")
        
        downloaded = download_azure.download_blob_file(force=force_download)
        if downloaded is False:
            logger.info("\n>>> NO HAY DATOS NUEVOS: El archivo en Azure no ha cambiado.")
            logger.info(">>> Abortando orquestación temprana para ahorrar recursos.")
            logger.info("\n=======================================================")
            logger.info("=== PIPELINE FINALIZADO TEMPRANAMENTE SIN CAMBIOS ===")
            logger.info("=======================================================")
            return
    except Exception as e:
        logger.error(f"Falla crítica en Fase 1: {e}")
        sys.exit(1)
        
    # 2. Carga en PostgreSQL local
    logger.info("\n>>> FASE 2: EXTRACCIÓN, TRANSFORMACIÓN Y CARGA (ETL) LOCAL")
    try:
        etl.process_etl()
    except Exception as e:
        logger.error(f"Falla crítica en Fase 2: {e}")
        sys.exit(1)
        
    # 3. Procesamiento con Ollama
    logger.info("\n>>> FASE 3: CLASIFICACIÓN CON INTELIGENCIA ARTIFICIAL (OLLAMA)")
    try:
        if not classify.check_ollama_model():
            logger.error("Modelo de Ollama no disponible. Abortando pipeline para prevenir falsos positivos.")
            sys.exit(1)
        classify.process_classification()
    except Exception as e:
        logger.error(f"Falla crítica en Fase 3: {e}")
        sys.exit(1)
        
    # 4. Dump de la base de datos
    logger.info("\n>>> FASE 4: RESPALDO DE BASE DE DATOS (DUMP)")
    try:
        dump_file = dump_db.dump_schema()
    except Exception as e:
        logger.error(f"Falla crítica en Fase 4: {e}")
        sys.exit(1)
        
    # 5. Upload a MinIO
    if dump_file and os.path.exists(dump_file):
        logger.info("\n>>> FASE 5: SUBIDA DEL RESPALDO A MINIO")
        try:
            upload_minio.upload_to_minio(dump_file)
            
            # Limpieza del dump local
            os.remove(dump_file)
            logger.info(f"Archivo temporal eliminado con éxito: {dump_file}")
            
        except Exception as e:
            logger.error(f"Falla crítica en Fase 5: {e}")
            sys.exit(1)
    else:
        logger.error("Error: No se pudo localizar el archivo dump de la base de datos para la subida.")
        sys.exit(1)

    logger.info("\n========================================")
    logger.info("=== PIPELINE COMPLETADO EXITOSAMENTE ===")
    logger.info("========================================")

if __name__ == "__main__":
    main()
