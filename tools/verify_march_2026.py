import psycopg2
from psycopg2 import sql
import logging
import config

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def verify_march_2026():
    conn = None
    try:
        # Conectar a la base de datos
        logger.info("Conectando a la base de datos...")
        conn = psycopg2.connect(**config.DB_CONFIG)
        
        schema_name = config.SCHEMA_NAME
        table_main = config.TABLE_NAME_MAIN
        pk_col = config.PK_COL
        
        clases = ['salud', 'ruido']
        
        logger.info("\n=== REPORTE DE CLASIFICACIONES MARZO 2026 ===\n")
        
        for clase in clases:
            table_clase = f"{table_main}_{clase}"
            
            # Query para agrupar por procesado y si tiene clasificación
            query = sql.SQL("""
                SELECT 
                    t1.procesado, 
                    t1.clasificacion IS NOT NULL AS tiene_clasificacion,
                    COUNT(*)
                FROM {schema}.{table_clase} AS t1
                JOIN {schema}.{table_main} AS t2 ON t1.{pk} = t2.{pk}
                WHERE t2.fecha_ingreso LIKE '2026-03%%' OR t2.fecha_registro LIKE '2026-03%%'
                GROUP BY t1.procesado, tiene_clasificacion
                ORDER BY t1.procesado, tiene_clasificacion
            """).format(
                schema=sql.Identifier(schema_name),
                table_clase=sql.Identifier(table_clase),
                table_main=sql.Identifier(table_main),
                pk=sql.Identifier(pk_col)
            )
            
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()
                
                total_marzo = 0
                procesados = 0
                pendientes = 0
                con_clasificacion = 0
                
                for row in rows:
                    is_procesado = row[0]
                    has_class = row[1]
                    count = row[2]
                    
                    total_marzo += count
                    
                    if is_procesado:
                        procesados += count
                        if has_class:
                            con_clasificacion += count
                    else:
                        pendientes += count
                        
                logger.info(f"--- Módulo: {clase.upper()} ---")
                logger.info(f"Total registros en Marzo 2026: {total_marzo}")
                logger.info(f"  - Procesados por el sistema: {procesados}")
                logger.info(f"    * Con clasificación positiva (asignada por IA): {con_clasificacion}")
                logger.info(f"    * Sin clasificación (NO APLICA o irrelevante): {procesados - con_clasificacion}")
                logger.info(f"  - Pendientes de procesar: {pendientes}\n")
                
    except Exception as e:
        logger.error(f"Ocurrió un error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    verify_march_2026()
