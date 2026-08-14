import os
import psycopg2
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()

# Database Configuration
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}
SCHEMA_NAME = os.getenv("SCHEMA_NAME")

# Initialize default variables to None or empty (values are populated from DB or .env)
CSV_FILE = None
TABLE_NAME_MAIN = None
TABLE_NAME_CLASES = None
AZURE_ACCOUNT_URL = None
CONTAINER_NAME = None
BLOB_NAME = None
OLLAMA_API_URL = None
OLLAMA_MODEL = None
BATCH_SIZE = None
MAX_WORKERS = None
CHUNK_SIZE = None
PK_COL = None
OLLAMA_TIMEOUT = None
OLLAMA_TEMPERATURE = None
OLLAMA_HOST = None
MINIO_ENDPOINT = None
MINIO_BUCKET = None
MINIO_PATH = None

# Secrets directly from .env
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")

def load_config_from_db():
    global CSV_FILE, TABLE_NAME_MAIN, TABLE_NAME_CLASES, AZURE_ACCOUNT_URL
    global CONTAINER_NAME, BLOB_NAME, OLLAMA_API_URL, OLLAMA_MODEL, BATCH_SIZE, MAX_WORKERS
    global PK_COL, OLLAMA_TIMEOUT, OLLAMA_TEMPERATURE, OLLAMA_HOST
    global MINIO_ENDPOINT, MINIO_BUCKET, MINIO_PATH
    global CHUNK_SIZE
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        with conn.cursor() as cur:
            cur.execute(f'SELECT config_key, config_value FROM "{SCHEMA_NAME}"."app_config"')
            rows = cur.fetchall()
            
            for key, val in rows:
                if key == "CSV_FILE": CSV_FILE = val
                elif key == "TABLE_NAME_MAIN": TABLE_NAME_MAIN = val
                elif key == "TABLE_NAME_CLASES": TABLE_NAME_CLASES = val
                elif key == "AZURE_ACCOUNT_URL": AZURE_ACCOUNT_URL = val
                elif key == "CONTAINER_NAME": CONTAINER_NAME = val
                elif key == "BLOB_NAME": BLOB_NAME = val
                elif key == "OLLAMA_API_URL": OLLAMA_API_URL = val
                elif key == "OLLAMA_MODEL": OLLAMA_MODEL = val
                elif key == "BATCH_SIZE": BATCH_SIZE = val
                elif key == "MAX_WORKERS": MAX_WORKERS = val
                elif key == "CHUNK_SIZE": CHUNK_SIZE = val
                elif key == "PK_COL": PK_COL = val
                elif key == "OLLAMA_TIMEOUT": OLLAMA_TIMEOUT = val
                elif key == "OLLAMA_TEMPERATURE": OLLAMA_TEMPERATURE = val
                elif key == "OLLAMA_HOST": OLLAMA_HOST = val
                elif key == "MINIO_ENDPOINT": MINIO_ENDPOINT = val
                elif key == "MINIO_BUCKET": MINIO_BUCKET = val
                elif key == "MINIO_PATH": MINIO_PATH = val
                
        conn.close()
    except Exception as e:
        logger.error(f"Failed to load config from database: {e}")

# Load configuration automatically upon import
load_config_from_db()
