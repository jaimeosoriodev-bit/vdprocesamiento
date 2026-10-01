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

# Optimized HTTP Session with Connection Pooling for Local & Cloud APIs
http_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=150, pool_maxsize=150, max_retries=1)
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
BATCH_SIZE = config.BATCH_SIZE or 50
MAX_WORKERS = config.MAX_WORKERS or 4
PK_COL = config.PK_COL or 'numero_peticion'
OLLAMA_TIMEOUT = max(30, int(config.OLLAMA_TIMEOUT or 60))
OLLAMA_TEMPERATURE = config.OLLAMA_TEMPERATURE if config.OLLAMA_TEMPERATURE is not None else 0.0
OLLAMA_HOST = (config.OLLAMA_HOST or 'http://127.0.0.1:11434').replace("localhost", "127.0.0.1")

# Engine Configuration: OLLAMA o JEV
CLASSIFIER_ENGINE = (config.CLASSIFIER_ENGINE or "OLLAMA").strip().upper()
TYPESAFE_API_KEY = config.TYPESAFE_API_KEY
JEV_MODEL = config.JEV_MODEL or "jev-latest"
TYPESAFE_API_URL = config.TYPESAFE_API_URL or "https://api.typesafe.ai/v1/systemone"
JEV_MAX_WORKERS = getattr(config, "JEV_MAX_WORKERS", 20)
JEV_BATCH_SIZE = getattr(config, "JEV_BATCH_SIZE", 200)

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
                "think": False,
                "keep_alive": "24h",
                "options": {
                    "temperature": OLLAMA_TEMPERATURE,
                    "num_predict": 40,
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

def build_jev_criteria(clase, categories):
    clase_clean = clase.lower().strip()
    clase_display = clase.replace("_", " ")
    
    criteria = {
        "NO_APLICA": f"El asunto NO está relacionado con {clase_display} o corresponde a otros temas no pertinentes."
    }
    
    if clase_clean == "maltrato_animal":
        criteria["NO_APLICA"] = "El asunto NO corresponde a maltrato animal (trata sobre otros trámites, salud humana, ruido, tenencia responsable rutinaria, vacunación o esterilización preventiva sin denuncia de maltrato)."
        for cat in categories:
            if "maltrato" in cat.lower():
                criteria[cat] = "Denuncias o situaciones de maltrato, abandono, agresiones físicas, encierro indebido, desnutrición, falta de auxilio o crueldad hacia animales."
            else:
                criteria[cat] = f"El asunto corresponde a {cat}."
    elif clase_clean == "salud":
        criteria["NO_APLICA"] = "El asunto NO tiene ninguna relación con el sector salud ni atención médica."
        for cat in categories:
            if "prestación" in cat.lower() or "humanización" in cat.lower():
                criteria[cat] = "Quejas por mala atención, tratos inhumanos, demoras graves o fallas en la prestación del servicio de salud."
            elif "citas" in cat.lower():
                criteria[cat] = "Negación, falta de agenda o trabas para asignación de citas médicas generales o con especialista."
            elif "medicamento" in cat.lower():
                criteria[cat] = "No entrega, desabastecimiento, demoras o negación de medicamentos formulados."
            elif "procedimiento" in cat.lower():
                criteria[cat] = "Negación, dilación o falta de autorización de cirugías, exámenes o procedimientos médicos."
            elif "otros" in cat.lower():
                criteria[cat] = "Otras peticiones o quejas vinculadas al sistema de salud que no corresponden a las categorías anteriores."
            else:
                criteria[cat] = f"El asunto corresponde a {cat}."
    elif clase_clean == "ruido":
        criteria["NO_APLICA"] = "El asunto NO tiene relación con quejas o denuncias por ruido o contaminación acústica."
        for cat in categories:
            criteria[cat] = f"El asunto corresponde a quejas por {cat.lower()}."
    else:
        for cat in categories:
            criteria[cat] = f"El asunto corresponde específicamente a {cat}."
            
    return criteria

def call_jev(asunto, clase, categories, retries=1):
    if not TYPESAFE_API_KEY:
        logger.error("TYPESAFE_API_KEY / JEV_TOKEN no configurado en .env.")
        return None
        
    asunto_clean = str(asunto)[:800].strip()
    clase_display = clase.replace("_", " ")
    criteria = build_jev_criteria(clase, categories)
    
    payload = {
        "state": {"asunto": asunto_clean},
        "model": JEV_MODEL,
        "questions": {
            "clasificacion": {
                "type": "choice",
                "instructions": f"Determinar si el asunto de la petición ciudadana PQRS corresponde a {clase_display} y seleccionar la subcategoría adecuada, o 'NO_APLICA'.",
                "criteria": criteria
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {TYPESAFE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    for attempt in range(retries + 1):
        try:
            response = http_session.post(
                TYPESAFE_API_URL, 
                json=payload, 
                headers=headers, 
                timeout=30
            )
            if response.status_code == 401:
                logger.error("Error de autenticación con TypeSafe Jev (401). Verifica tu JEV_TOKEN / TYPESAFE_API_KEY en .env.")
                return None
            if response.status_code == 429:
                wait_time = max(2, int(response.headers.get("Retry-After", 2 * (attempt + 1))))
                logger.warning(f"Rate limit 429 en TypeSafe Jev. Esperando {wait_time}s antes de reintentar (intento {attempt+1}/{retries+1})...")
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            result = response.json()
            answer = result.get("answers", {}).get("clasificacion", {})
            choice = answer.get("choice")
            return choice
        except Exception as e:
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            logger.error(f"Error calling TypeSafe Jev: {e}")
            return None

def check_jev_connection():
    if not TYPESAFE_API_KEY:
        logger.error("Falta JEV_TOKEN / TYPESAFE_API_KEY en .env.")
        return False
    try:
        headers = {
            "Authorization": f"Bearer {TYPESAFE_API_KEY}",
            "Content-Type": "application/json"
        }
        test_payload = {
            "state": "ping",
            "model": JEV_MODEL,
            "questions": {
                "ping": {
                    "type": "noul",
                    "instructions": "Is this a connection test?"
                }
            }
        }
        res = http_session.post(TYPESAFE_API_URL, json=test_payload, headers=headers, timeout=10)
        if res.status_code == 200:
            logger.info(f"OK: Conexión con TypeSafe Jev exitosa (Modelo: {JEV_MODEL}).")
            return True
        elif res.status_code == 401:
            logger.error("Error 401 Unauthorized: El JEV_TOKEN / TYPESAFE_API_KEY en .env no es válido.")
            return False
        else:
            logger.warning(f"Respuesta inesperada de TypeSafe Jev ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        logger.error(f"No se pudo conectar a la API de TypeSafe: {e}")
        return False

def classify_record(asunto, clase, categories, prompt_template):
    if not asunto:
        return None
        
    if CLASSIFIER_ENGINE == "JEV":
        choice = call_jev(asunto, clase, categories)
        if not choice:
            return None
        if choice == "NO_APLICA":
            return "NO_APLICA"
        for cat in categories:
            if cat.lower() == choice.lower() or cat.lower() in choice.lower():
                return cat
        return "NO_APLICA"
    else:
        asunto_clean = str(asunto)[:600].strip()
        
        # Construct prompt
        categories_list = "\n- ".join(categories)
        clase_display = clase.replace("_", " ")
        
        prompt = prompt_template.format(
            clase_upper=clase_display.upper(),
            clase=clase_display,
            categories_list="- " + categories_list,
            asunto=asunto_clean
        )
        
        response = call_ollama(prompt)
        if not response:
            return None
            
        # Clean response
        cleaned_response = response.strip().replace("Respuesta:", "").strip()
        
        # Validation
        cleaned_upper = cleaned_response.upper()
        if "NO_APLICA" in cleaned_upper or "NO APLICA" in cleaned_upper:
            return "NO_APLICA"
        
        # Try to fuzzy match or check if valid category
        for cat in categories:
            if cat.lower() in cleaned_response.lower():
                return cat
                
        # Default to NO_APLICA if not matching any valid category
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
                "think": False,
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

    if CLASSIFIER_ENGINE == "JEV":
        effective_batch_size = JEV_BATCH_SIZE
        effective_workers = JEV_MAX_WORKERS
    else:
        effective_batch_size = BATCH_SIZE
        effective_workers = MAX_WORKERS

    logger.info(f"--- [START] Procesando clasificación con IA para: {clase} ({total_pending} pendientes) | Motor: {CLASSIFIER_ENGINE} (Hilos: {effective_workers}, Lote: {effective_batch_size}) ---")
    
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
                cur.execute(fetch_query, (effective_batch_size,))
                rows = cur.fetchall()
            
            if not rows:
                logger.info(f"--- [FIN] No hay más registros pendientes para {clase}. ---")
                break
                
            batch_start = time.time()
            batch_updates = 0
            
            metodo_val = 'JEV' if CLASSIFIER_ENGINE == 'JEV' else 'IA'
            update_query = sql.SQL("""
                UPDATE {table}
                SET clasificacion = %s, procesado = %s, metodo_clasificacion = %s
                WHERE {pk} = %s
            """).format(
                table=sql.SQL(fq_table_clase),
                pk=sql.Identifier(pk_col)
            )
            
            # Parallel Execution with Real-Time Streaming Commits
            with concurrent.futures.ThreadPoolExecutor(max_workers=effective_workers) as executor:
                future_to_row = {
                    executor.submit(classify_record, row[1], clase, categories, prompt_template): row 
                    for row in rows
                }
                
                for future in concurrent.futures.as_completed(future_to_row):
                    row = future_to_row[future]
                    peticion_id = row[0]
                    
                    try:
                        classification = future.result()
                    except Exception as exc:
                        logger.error(f"[{clase.upper()}] Error en {peticion_id}: {exc}")
                        classification = None

                    if classification is None:
                        logger.warning(f"[{clase.upper()}] Inferencia fallida/timeout para {peticion_id}. Se deja pendiente para reintento.")
                        continue

                    if classification == "NO_APLICA":
                        cat_val = None
                    else:
                        cat_val = classification

                    # Immediate commit per record (eliminates waiting for slow threads)
                    try:
                        with conn.cursor() as cur:
                            cur.execute(update_query, (cat_val, True, metodo_val, peticion_id))
                            conn.commit()
                        batch_updates += 1
                        total_processed += 1
                    except Exception as e:
                        logger.error(f"[{clase.upper()}] Error guardando {peticion_id}: {e}")
                        conn.rollback()

            if batch_updates == 0 and len(rows) > 0:
                logger.error(f"[{clase.upper()}] Ningún registro del lote pudo ser procesado por la IA. Abortando clase para evitar bucle.")
                break

            batch_duration = time.time() - batch_start
            rate = batch_updates / batch_duration if batch_duration > 0 else 0
            remaining = max(0, total_pending - total_processed)
            logger.info(f"[{clase.upper()}] Lote completado: {batch_updates} registros en {batch_duration:.1f}s ({rate:.1f} reg/s) | Acumulado: {total_processed} | Restantes aprox: {remaining}")
            import sys
            sys.stdout.flush()
    finally:
        conn.close()

def process_classification(target_class=None):
    conn = get_db_connection()
    if not conn:
        return

    db_config = get_classification_config(conn)
    if not db_config:
        logger.error("No se encontró configuración de clasificación en la base de datos.")
        conn.close()
        return

    if target_class:
        if target_class in db_config:
            logger.info(f"Filtro de ejecución activado para la clase: {target_class}")
            db_config = {target_class: db_config[target_class]}
        else:
            logger.error(f"Clase '{target_class}' no encontrada en config_clasificacion. Disponibles: {list(db_config.keys())}")
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

        # Optimization 1: Pre-process empty subjects (keeps only records with actual text for the LLM)
        finalize_empty_asuntos(conn, fq_table_clase, fq_table_main, pk_col)
        
        # Optimization 2 (Keywords Filter): OMITIDO para evaluar el 100% de los registros con Inteligencia Artificial.
        logger.info(f"Filtro de palabras clave omitido para {clase}: se procesará el 100% de los textos con IA.")
            
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
    import sys
    logger.info("Iniciando proceso de clasificación...")
    logger.info(f"Motor de inferencia configurado: {CLASSIFIER_ENGINE}")
    
    if CLASSIFIER_ENGINE == "JEV":
        logger.info(f"Usando TypeSafe System One (Modelo: {JEV_MODEL})")
        if not TYPESAFE_API_KEY:
            logger.error("Error: CLASSIFIER_ENGINE está configurado como 'JEV', pero JEV_TOKEN / TYPESAFE_API_KEY no está definido en .env.")
            sys.exit(1)
        if not check_jev_connection():
            logger.error("No se pudo autenticar con TypeSafe Jev. Verifica tu token.")
            sys.exit(1)
    else:
        logger.info(f"Usando Ollama Local (Modelo: {OLLAMA_MODEL})")
        if not check_ollama_model():
            logger.error("Modelo de Ollama no encontrado. Abortando para evitar errores. Asegurate de tener el modelo instalado.")
            sys.exit(1)

        try:
            requests.get(OLLAMA_HOST, timeout=5)
            logger.info("Ollama detectado correctamente.")
        except Exception:
            logger.warning("No se pudo conectar a Ollama en localhost:11434. Asegúrate que esté corriendo.")
            # Proceed anyway, calls will fail and log errors.
    
    target_arg = sys.argv[1] if len(sys.argv) > 1 else None
    process_classification(target_class=target_arg)
    logger.info("Proceso finalizado.")
