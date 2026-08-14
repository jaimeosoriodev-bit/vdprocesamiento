import psycopg2
from psycopg2 import sql
import logging
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_columns():
    conn = None
    try:
        conn = psycopg2.connect(**config.DB_CONFIG)
        schema_name = config.SCHEMA_NAME
        table_main = config.TABLE_NAME_MAIN
        
        clases = ['salud', 'ruido']
        
        for clase in clases:
            table_clase = f"{table_main}_{clase}"
            logger.info(f"Agregando columna metodo_clasificacion a {table_clase}...")
            
            # Agregamos la columna. En postgres, ADD COLUMN sin default pone NULL a todos los registros existentes.
            query = sql.SQL("""
                ALTER TABLE {schema}.{table_clase} 
                ADD COLUMN IF NOT EXISTS metodo_clasificacion VARCHAR(50);
            """).format(
                schema=sql.Identifier(schema_name),
                table_clase=sql.Identifier(table_clase)
            )
            
            with conn.cursor() as cur:
                cur.execute(query)
                logger.info(f"OK: Columna agregada en {table_clase}.")
                
        conn.commit()
        logger.info("Cambios guardados con éxito.")
        
    except Exception as e:
        logger.error(f"Error alterando tablas: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    add_columns()
