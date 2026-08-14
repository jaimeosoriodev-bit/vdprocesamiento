import psycopg2
import psycopg2.extras # Fix export
from psycopg2 import sql
import logging
import requests
import json
import time
import concurrent.futures
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reduction in requests noise
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Optimized HTTP Session with Connection Pooling for Metal GPU throughput
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=1)
http_session.mount('http://', adapter)
http_session.mount('https://', adapter)

# Database Configuration
DB_CONFIG = config.DB_CONFIG

SCHEMA_NAME = config.SCHEMA_NAME
TABLE_NAME_MAIN = config.TABLE_NAME_MAIN
OLLAMA_API_URL = config.OLLAMA_API_URL or 'http://127.0.0.1:11434/api/generate'
OLLAMA_MODEL = config.OLLAMA_MODEL

# Force IPv4 127.0.0.1 to eliminate macOS IPv6 DNS stalls
if "localhost" in OLLAMA_API_URL:
    OLLAMA_API_URL = OLLAMA_API_URL.replace("localhost", "127.0.0.1")

# Classification Config
BATCH_SIZE = 50
MAX_WORKERS = 4
PK_COL = config.PK_COL
OLLAMA_TIMEOUT = 45
OLLAMA_TEMPERATURE = config.OLLAMA_TEMPERATURE or 0.0
OLLAMA_HOST = (config.OLLAMA_HOST or 'http://127.0.0.1:11434').replace("localhost", "127.0.0.1")

def get_classification_config(conn):
    try:
        with conn.cursor() as cur:
            cur.execute(f'SELECT clase, categorias, filter_keywords, prompt_template FROM "{SCHEMA_NAME}"."config_clasificacion"')
            rows = cur.fetchall()
            
            config_dict = {}
            for row in rows:
                clase, categorias, filter_keywords, prompt_template = row
                config_dict[clase] = {
                    'categorias': categorias,
                    'filter_keywords': filter_keywords,
                    'prompt_template': prompt_template
                }
            return config_dict
    except Exception as e:
        logger.error(f"Error fetching classification config: {e}")
        return {}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def call_ollama(prompt, model=OLLAMA_MODEL, retries=1):
    for attempt in range(retries + 1):
        try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "24h",
                "options": {
                    "temperature": OLLAMA_TEMPERATURE,
                    "num_predict": 20,
                    "num_ctx": 512
                }
            }
            response = http_session.post(OLLAMA_API_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5)
                continue
            logger.error(f"Error calling Ollama: {e}")
            return None

def classify_record(asunto, clase, categories, prompt_template):
    if not asunto:
        return None
    asunto_clean = str(asunto)[:600].strip()
    
    # Construct prompt
    categories_list = "\n- ".join(categories)
    
    prompt = prompt_template.format(
        clase_upper=clase.upper(),
        clase=clase,
        categories_list="- " + categories_list,
        asunto=asunto_clean
    )
    
    response = call_ollama(prompt)
    if not response:
        return None
        
    # Clean response
    cleaned_response = response.strip().replace("Respuesta:", "").strip()
    
    # Validation
    if "NO_APLICA" in cleaned_response.upper():
        return "NO_APLICA"
    
    # Try to fuzzy match or check if valid category
    for cat in categories:
        if cat.lower() in cleaned_response.lower():
            return cat
            
    # Fallback if AI responds with category synonym
    if clase == "ruido":
        return "Ruido sin especificar"
    if clase == "salud":
        return "Otros"
        
    return "NO_APLICA"

def check_ollama_model():
    try:
        res = http_session.get(f"{OLLAMA_API_URL.replace('/api/generate', '/api/tags')}", timeout=5)
        if res.status_code == 200:
            models_data = res.json().get('models', [])
            models = [m['name'] for m in models_data]
            logger.info(f"Modelos instalados en Ollama: {models}")
            
            # Consultar modelos activos en GPU/VRAM
            try:
                ps_res = http_session.get(f"{OLLAMA_API_URL.replace('/api/generate', '/api/ps')}", timeout=5)
                if ps_res.status_code == 200:
                    running_models = [m['name'] for m in ps_res.json().get('models', [])]
                    logger.info(f"Modelos cargados en GPU (Metal): {running_models}")
            except Exception:
                pass

            if OLLAMA_MODEL not in models:
                logger.warning(f"Model {OLLAMA_MODEL} not found in Ollama. Available: {models}")
                logger.warning(f"Please run: ollama pull {OLLAMA_MODEL}")
                return False
            
            # Precalentamiento rápido del modelo en GPU
            logger.info(f"Precalentando modelo {OLLAMA_MODEL} en GPU (Metal)...")
            warmup_payload = {
                "model": OLLAMA_MODEL,
                "prompt": "ping",
                "stream": False,
                "keep_alive": "24h",
                "options": {
                    "num_predict": 1,
                    "num_ctx": 512
                }
            }
            try:
                http_session.post(OLLAMA_API_URL, json=warmup_payload, timeout=15)
                logger.info("OK: Modelo precalentado y residente en GPU.")
            except Exception as e:
                logger.warning(f"Aviso durante precalentamiento: {e}")

            return True
    except Exception as e:
        logger.warning(f"Could not check models: {e}")
    return True

def finalize_empty_asuntos(conn, fq_table_clase, fq_table_main, pk_col):
    logger.info(f"Optimizando registros vacíos para {fq_table_clase}...")
    
    # We construct the query carefully.
    # UPDATE tcc_registradas_{clase} AS t1
    # SET procesado = TRUE
    # FROM tcc_registradas AS t2
    # WHERE t1.pk = t2.pk AND (t2.asunto IS NULL OR TRIM(t2.asunto) = '') AND t1.procesado = FALSE
    
    query = sql.SQL("""
        UPDATE {table_clase} AS t1
        SET procesado = TRUE, clasificacion = NULL, metodo_clasificacion = 'VACIO'
        FROM {table_main} AS t2
        WHERE t1.{pk} = t2.{pk}
          AND t1.procesado = FALSE
          AND (t2.asunto IS NULL OR TRIM(t2.asunto) = '')
    """).format(
        table_clase=sql.SQL(fq_table_clase),
        table_main=sql.SQL(fq_table_main),
        pk=sql.Identifier(pk_col)
    )
    
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            processed_count = cur.rowcount
            conn.commit()
            
        if processed_count > 0:
            logger.info(f"OK: Se marcaron {processed_count} registros vacíos como procesados.")
        else:
            logger.info("OK: No se encontraron registros vacíos pendientes.")
            
    except Exception as e:
        logger.error(f"Error optimizando registros vacíos: {e}")
        conn.rollback()


def filter_irrelevant_records(conn, fq_table_clase, fq_table_main, pk_col, keywords):
    """
    Optimización: Marcar como procesados los registros que NO contienen ninguna palabra clave.
    Solo se envían al LLM los que tienen potencial de ser de la categoría.
    """
    if not keywords:
        return

    logger.info(f"Aplicando filtro de palabras clave negativas para {fq_table_clase}...")
    
    # Construct array for ILIKE ANY
    # We add wildcards to keywords
    kws_pattern = [f"%{k}%" for k in keywords]
    
    # Query: Update where asunto does NOT match ANY of the patterns
    # Using Postgres `NOT (col ILIKE ANY(%s))`
    
    query = sql.SQL("""
        UPDATE {table_clase} AS t1
        SET procesado = TRUE, clasificacion = NULL, metodo_clasificacion = 'KEYWORDS'
        FROM {table_main} AS t2
        WHERE t1.{pk} = t2.{pk}
          AND t1.procesado = FALSE
          AND NOT (t2.asunto ILIKE ANY(%s))
    """).format(
        table_clase=sql.SQL(fq_table_clase),
        table_main=sql.SQL(fq_table_main),
        pk=sql.Identifier(pk_col)
    )
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, (kws_pattern,))
            processed_count = cur.rowcount
            conn.commit()
            
        if processed_count > 0:
            logger.info(f"OK: Se descartaron {processed_count} registros irrelevantes (sin palabras clave).")
        else:
            logger.info("OK: No se encontraron registros irrelevantes pendientes.")
            
    except Exception as e:
        logger.error(f"Error filtrando registros irrelevantes: {e}")
        conn.rollback()

def process_single_class(clase, config_data):
    conn = get_db_connection()
    if not conn:
        logger.error(f"No se pudo conectar a la base de datos para la clase: {clase}")
        return

    categories = config_data.get('categorias', [])
    prompt_template = config_data.get('prompt_template', '')
    
    table_clase = f"{TABLE_NAME_MAIN}_{clase}"
    fq_table_clase = f'"{SCHEMA_NAME}"."{table_clase}"'
    fq_table_main = f'"{SCHEMA_NAME}"."{TABLE_NAME_MAIN}"'
    pk_col = PK_COL
    
    # Get total pending
    try:
        with conn.cursor() as cur:
            cur.execute(f'SELECT count(*) FROM {fq_table_clase} WHERE procesado = FALSE')
            total_pending = cur.fetchone()[0]
    except Exception:
        total_pending = 0

    logger.info(f"--- [START] Procesando clasificación con IA para: {clase} ({total_pending} pendientes) ---")
    
    total_processed = 0
    start_time_all = time.time()
    
    try:
        while True:
            # 1. Fetch unprocesssed records
            fetch_query = sql.SQL("""
                SELECT t1.{pk}, t2.asunto
                FROM {table_clase} t1
                JOIN {table_main} t2 ON t1.{pk} = t2.{pk}
                WHERE t1.procesado = FALSE
                LIMIT %s
            """).format(
                pk=sql.Identifier(pk_col),
                table_clase=sql.SQL(fq_table_clase),
                table_main=sql.SQL(fq_table_main)
            )
            
            with conn.cursor() as cur:
                cur.execute(fetch_query, (BATCH_SIZE,))
                rows = cur.fetchall()
            
            if not rows:
                logger.info(f"--- [FIN] No hay más registros pendientes para {clase}. ---")
                break
                
            batch_start = time.time()
            batch_updates = 0
            
            update_query = sql.SQL("""
                UPDATE {table}
                SET clasificacion = %s, procesado = %s, metodo_clasificacion = 'IA'
                WHERE {pk} = %s
            """).format(
                table=sql.SQL(fq_table_clase),
                pk=sql.Identifier(pk_col)
            )
            
            # Parallel Execution with Real-Time Streaming Commits
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_row = {
                    executor.submit(classify_record, row[1], clase, categories, prompt_template): row 
                    for row in rows
                }
                
                for future in concurrent.futures.as_completed(future_to_row):
                    row = future_to_row[future]
                    peticion_id = row[0]
                    
                    try:
                        classification = future.result()
                        if classification == "NO_APLICA":
                            cat_val = None
                        elif classification:
                            cat_val = classification
                        else:
                            cat_val = None
                    except Exception as exc:
                        logger.error(f"[{clase.upper()}] Error en {peticion_id}: {exc}")
                        cat_val = None

                    # Immediate commit per record (eliminates waiting for slow threads)
                    try:
                        with conn.cursor() as cur:
                            cur.execute(update_query, (cat_val, True, peticion_id))
                            conn.commit()
                        batch_updates += 1
                        total_processed += 1
                    except Exception as e:
                        logger.error(f"[{clase.upper()}] Error guardando {peticion_id}: {e}")
                        conn.rollback()

            batch_duration = time.time() - batch_start
            rate = batch_updates / batch_duration if batch_duration > 0 else 0
            remaining = max(0, total_pending - total_processed)
            logger.info(f"[{clase.upper()}] Lote completado: {batch_updates} registros en {batch_duration:.1f}s ({rate:.1f} reg/s) | Acumulado: {total_processed} | Restantes aprox: {remaining}")
            import sys
            sys.stdout.flush()
    finally:
        conn.close()

def process_classification():
    conn = get_db_connection()
    if not conn:
        return

    db_config = get_classification_config(conn)
    if not db_config:
        logger.error("No se encontró configuración de clasificación en la base de datos.")
        conn.close()
        return

    # Phase 1: Global Optimization (SQL Updates)
    logger.info("=== FASE 1: OPTIMIZACIÓN GLOBAL (Filtros SQL) ===")
    for clase, config_data in db_config.items():
        logger.info(f"--- Optimizando clase: {clase} ---")
        
        table_clase = f"{TABLE_NAME_MAIN}_{clase}"
        fq_table_clase = f'"{SCHEMA_NAME}"."{table_clase}"'
        fq_table_main = f'"{SCHEMA_NAME}"."{TABLE_NAME_MAIN}"'
        pk_col = PK_COL

        # Optimization 1: Pre-process empty subjects
        finalize_empty_asuntos(conn, fq_table_clase, fq_table_main, pk_col)
        
        # Optimization 2: Filter irrelevant subjects using keywords
        keywords = config_data.get('filter_keywords', [])
        if keywords:
            filter_irrelevant_records(conn, fq_table_clase, fq_table_main, pk_col, keywords)
            
    conn.close()

    # Phase 2: LLM Classification in PARALLEL across all classes
    logger.info(f"=== FASE 2: CLASIFICACIÓN PARALELA CON INTELIGENCIA ARTIFICIAL ({len(db_config)} clases simultáneas) ===")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(db_config)) as class_executor:
        futures = {
            class_executor.submit(process_single_class, clase, config_data): clase
            for clase, config_data in db_config.items()
        }
        for future in concurrent.futures.as_completed(futures):
            clase_name = futures[future]
            try:
                future.result()
                logger.info(f"=== Finalizada clasificación completa para: {clase_name} ===")
            except Exception as e:
                logger.error(f"Error procesando clase {clase_name}: {e}")

if __name__ == "__main__":
    logger.info("Iniciando proceso de clasificación con Ollama...")
    if not check_ollama_model():
        logger.error("Modelo no encontrado. Abortando para evitar errores. Asegurate de tener el modelo instalado.")
        import sys
        sys.exit(1)

    try:
        requests.get(OLLAMA_HOST, timeout=5)
        logger.info("Ollama detectado correctamente.")
    except Exception:
        logger.warning("No se pudo conectar a Ollama en localhost:11434. Asegúrate que esté corriendo.")
        # Proceed anyway, calls will fail and log errors.
    
    process_classification()
    logger.info("Proceso finalizado.")
