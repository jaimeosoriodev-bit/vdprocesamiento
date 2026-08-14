import psycopg2
from psycopg2 import sql
import logging
import config

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def reprocess_march_2026():
    conn = None
    try:
        # Conectar a la base de datos
        logger.info("Conectando a la base de datos...")
        conn = psycopg2.connect(**config.DB_CONFIG)
        
        schema_name = config.SCHEMA_NAME
        table_main = config.TABLE_NAME_MAIN
        pk_col = config.PK_COL
        
        # Clases a reprocesar según la contingencia
        clases = ['salud', 'ruido']
        
        for clase in clases:
            table_clase = f"{table_main}_{clase}"
            
            logger.info(f"Alterando registros en la tabla {table_clase} para marzo de 2026...")
            
            # Query para resetear procesado y clasificacion de los registros de marzo 2026
            query = sql.SQL("""
                UPDATE {schema}.{table_clase} AS t1
                SET procesado = FALSE, clasificacion = NULL
                FROM {schema}.{table_main} AS t2
                WHERE t1.{pk} = t2.{pk}
                  AND (t2.fecha_ingreso LIKE '2026-03%' OR t2.fecha_registro LIKE '2026-03%')
            """).format(
                schema=sql.Identifier(schema_name),
                table_clase=sql.Identifier(table_clase),
                table_main=sql.Identifier(table_main),
                pk=sql.Identifier(pk_col)
            )
            
            with conn.cursor() as cur:
                cur.execute(query)
                processed_count = cur.rowcount
                logger.info(f"OK: Se resetearon {processed_count} registros en {table_clase} correspondientes a marzo de 2026.")
                
        # Confirmar cambios
        conn.commit()
        logger.info("Cambios guardados en la base de datos con éxito. Ya puedes ejecutar classify.py.")
        
    except Exception as e:
        logger.error(f"Ocurrió un error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Conexión cerrada.")

if __name__ == "__main__":
    reprocess_march_2026()
