import psycopg2
from psycopg2 import sql
import logging
import config

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def prepare_reprocess_2023():
    conn = None
    try:
        # Conectar a la base de datos
        logger.info("Conectando a la base de datos...")
        conn = psycopg2.connect(**config.DB_CONFIG)
        
        schema_name = config.SCHEMA_NAME
        table_main = config.TABLE_NAME_MAIN
        pk_col = config.PK_COL
        
        # Clases a limpiar
        clases = ['salud', 'ruido']
        
        # Meses a borrar
        months_conditions = " OR ".join([
            f"t2.fecha_ingreso LIKE '2023-{m:02d}%' OR t2.fecha_registro LIKE '2023-{m:02d}%'"
            for m in range(3, 11)
        ])
        
        months_conditions_main = " OR ".join([
            f"fecha_ingreso LIKE '2023-{m:02d}%' OR fecha_registro LIKE '2023-{m:02d}%'"
            for m in range(3, 11)
        ])
        
        for clase in clases:
            table_clase = f"{table_main}_{clase}"
            logger.info(f"Eliminando registros de {table_clase} para los meses 03 al 10 del 2023...")
            
            query = sql.SQL("""
                DELETE FROM {schema}.{table_clase} AS t1
                USING {schema}.{table_main} AS t2
                WHERE t1.{pk} = t2.{pk}
                  AND ({months})
            """).format(
                schema=sql.Identifier(schema_name),
                table_clase=sql.Identifier(table_clase),
                table_main=sql.Identifier(table_main),
                pk=sql.Identifier(pk_col),
                months=sql.SQL(months_conditions)
            )
            
            with conn.cursor() as cur:
                cur.execute(query)
                deleted_count = cur.rowcount
                logger.info(f"OK: Se eliminaron {deleted_count} registros de {table_clase}.")
                
        # Ahora eliminar de la tabla principal
        logger.info(f"Eliminando registros de la tabla principal {table_main} para los meses 03 al 10 del 2023...")
        query_main = sql.SQL("""
            DELETE FROM {schema}.{table_main}
            WHERE {months}
        """).format(
            schema=sql.Identifier(schema_name),
            table_main=sql.Identifier(table_main),
            months=sql.SQL(months_conditions_main)
        )
        
        with conn.cursor() as cur:
            cur.execute(query_main)
            deleted_count_main = cur.rowcount
            logger.info(f"OK: Se eliminaron {deleted_count_main} registros de {table_main}.")
            
        # Confirmar cambios
        conn.commit()
        logger.info("Base de datos limpia y lista para re-importación.")
        
    except Exception as e:
        logger.error(f"Ocurrió un error al limpiar la base de datos: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logger.info("Conexión cerrada.")

if __name__ == "__main__":
    prepare_reprocess_2023()
