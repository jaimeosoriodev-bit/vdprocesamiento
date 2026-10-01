import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import psycopg2
from psycopg2 import sql
import logging
import time
import json
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_maltrato_animal():
    conn = None
    try:
        logger.info("Conectando a la base de datos PostgreSQL...")
        conn = psycopg2.connect(**config.DB_CONFIG)
        schema = config.SCHEMA_NAME
        table_main = config.TABLE_NAME_MAIN
        table_clase = f"{table_main}_maltrato_animal"
        pk_col = config.PK_COL or "numero_peticion"
        
        with conn.cursor() as cur:
            # 1. Crear la tabla analítica tcc_registradas_maltrato_animal
            logger.info(f"1. Creando tabla {schema}.{table_clase} si no existe...")
            create_tbl_query = sql.SQL("""
                CREATE TABLE IF NOT EXISTS {schema}.{table} (
                    {pk} TEXT PRIMARY KEY,
                    clasificacion TEXT,
                    procesado BOOLEAN DEFAULT FALSE,
                    metodo_clasificacion CHARACTER VARYING
                );
            """).format(
                schema=sql.Identifier(schema),
                table=sql.Identifier(table_clase),
                pk=sql.Identifier(pk_col)
            )
            cur.execute(create_tbl_query)
            conn.commit()
            logger.info(f"Tabla {schema}.{table_clase} verificada/creada exitosamente.")

            # 2. Poblar con los registros de la tabla principal
            cur.execute(sql.SQL("SELECT count(*) FROM {schema}.{table}").format(
                schema=sql.Identifier(schema),
                table=sql.Identifier(table_clase)
            ))
            existing_count = cur.fetchone()[0]
            logger.info(f"Registros actuales en {table_clase}: {existing_count:,}")

            if existing_count == 0:
                logger.info(f"2. Poblando {table_clase} desde {table_main} (esto puede tomar unos segundos)...")
                t0 = time.time()
                populate_query = sql.SQL("""
                    INSERT INTO {schema}.{table_clase} ({pk}, clasificacion, procesado)
                    SELECT {pk}, NULL, FALSE
                    FROM {schema}.{table_main}
                    ON CONFLICT ({pk}) DO NOTHING;
                """).format(
                    schema=sql.Identifier(schema),
                    table_clase=sql.Identifier(table_clase),
                    table_main=sql.Identifier(table_main),
                    pk=sql.Identifier(pk_col)
                )
                cur.execute(populate_query)
                inserted = cur.rowcount
                conn.commit()
                logger.info(f"Se insertaron {inserted:,} registros en {table_clase} en {time.time()-t0:.2f}s.")
            else:
                logger.info(f"La tabla {table_clase} ya contiene registros. Sincronizando faltantes si existen...")
                sync_query = sql.SQL("""
                    INSERT INTO {schema}.{table_clase} ({pk}, clasificacion, procesado)
                    SELECT t1.{pk}, NULL, FALSE
                    FROM {schema}.{table_main} t1
                    LEFT JOIN {schema}.{table_clase} t2 ON t1.{pk} = t2.{pk}
                    WHERE t2.{pk} IS NULL
                    ON CONFLICT ({pk}) DO NOTHING;
                """).format(
                    schema=sql.Identifier(schema),
                    table_clase=sql.Identifier(table_clase),
                    table_main=sql.Identifier(table_main),
                    pk=sql.Identifier(pk_col)
                )
                cur.execute(sync_query)
                inserted = cur.rowcount
                conn.commit()
                logger.info(f"Registros sincronizados: {inserted:,}.")

            # 3. Crear índice parcial para acelerar búsquedas de pendientes
            logger.info("3. Creando índice parcial sobre procesado = FALSE...")
            idx_name = f"idx_{table_clase}_pendientes"
            create_idx_query = sql.SQL("""
                CREATE INDEX IF NOT EXISTS {idx}
                ON {schema}.{table} (procesado)
                WHERE procesado = FALSE;
            """).format(
                idx=sql.Identifier(idx_name),
                schema=sql.Identifier(schema),
                table=sql.Identifier(table_clase)
            )
            cur.execute(create_idx_query)
            conn.commit()
            logger.info(f"Índice {idx_name} creado/verificado.")

            # 4. Registrar en config_clasificacion
            logger.info("4. Registrando clase 'maltrato_animal' en config_clasificacion...")
            prompt_template = """Eres un asistente experto en clasificación de PQRS (Peticiones, Quejas, Reclamos y Sugerencias).
Tu tarea es analizar el siguiente 'Asunto' y determinar si corresponde a denuncias o situaciones de '{clase_upper}'.

El '{clase_upper}' incluye: abandono, agresiones físicas, falta de alimento o agua, encierro indebido, desnutrición, negligencia en salud o bienestar de animales domésticos o silvestres, tenencia en condiciones deplorables o crueldad animal.

Si el asunto NO está relacionado con '{clase_upper}' (o trata de otros trámites, salud humana, ruido, tenencia responsable rutinaria, solicitudes de esterilización preventiva, vacunación sin denuncia de maltrato), responde únicamente con la palabra "NO_APLICA".

Si el asunto SI corresponde a '{clase_upper}', responde con:
{categories_list}

Responde ÚNICAMENTE con el nombre exacto de la categoría o "NO_APLICA". No des explicaciones ni agregues texto adicional.

Asunto: "{asunto}"
Respuesta:"""

            categorias = ["Maltrato Animal"]
            filter_keywords = [
                "animal", "animales", "perro", "perros", "canino", "caninos", 
                "gato", "gatos", "felino", "felinos", "mascota", "mascotas", 
                "maltrato", "crueldad", "abandono", "encerrado", "encerrados", 
                "golpe", "golpes", "desnutrido", "desnutricion", "herido", 
                "zoonosis", "fauna", "cachorro", "cachorros"
            ]

            insert_config_query = sql.SQL("""
                INSERT INTO {schema}.config_clasificacion (clase, categorias, filter_keywords, prompt_template)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (clase) DO UPDATE SET
                    categorias = EXCLUDED.categorias,
                    filter_keywords = EXCLUDED.filter_keywords,
                    prompt_template = EXCLUDED.prompt_template;
            """).format(schema=sql.Identifier(schema))

            cur.execute(insert_config_query, (
                "maltrato_animal",
                json.dumps(categorias),
                json.dumps(filter_keywords),
                prompt_template
            ))
            conn.commit()
            logger.info("Configuración de clasificación para 'maltrato_animal' guardada exitosamente.")

            # 5. Actualizar app_config con TABLE_NAME_CLASES
            logger.info("5. Actualizando TABLE_NAME_CLASES en app_config...")
            cur.execute(sql.SQL("""
                SELECT config_value FROM {schema}.app_config WHERE config_key = 'TABLE_NAME_CLASES'
            """).format(schema=sql.Identifier(schema)))
            row = cur.fetchone()
            current_clases = row[0] if row else []
            if isinstance(current_clases, str):
                current_clases = json.loads(current_clases)
            
            if "maltrato_animal" not in current_clases:
                current_clases.append("maltrato_animal")
                cur.execute(sql.SQL("""
                    UPDATE {schema}.app_config
                    SET config_value = %s
                    WHERE config_key = 'TABLE_NAME_CLASES'
                """).format(schema=sql.Identifier(schema)), (json.dumps(current_clases),))
                conn.commit()
                logger.info(f"TABLE_NAME_CLASES actualizado a: {current_clases}")
            else:
                logger.info(f"TABLE_NAME_CLASES ya contenía 'maltrato_animal': {current_clases}")

        logger.info("¡Inicialización de 'Maltrato Animal' completada exitosamente!")
    except Exception as e:
        logger.error(f"Error durante la inicialización: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    setup_maltrato_animal()
