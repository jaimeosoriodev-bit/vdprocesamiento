import csv
import psycopg2
from psycopg2 import sql
import logging
import sys
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use constants from config
DB_CONFIG = config.DB_CONFIG
CSV_FILE = config.CSV_FILE
SCHEMA_NAME = config.SCHEMA_NAME
TABLE_NAME = config.TABLE_NAME_MAIN
TABLE_NAME_CLASES = config.TABLE_NAME_CLASES

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)

def sanitize_column_name(col_name):
    # Sanitize column names for PostgreSQL
    s = col_name.strip().lower().replace(" ", "_")
    s = s.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    s = s.replace("ñ", "n").replace(".", "").replace("/", "_").replace("-", "_")
    s = s.replace('\ufeff', '') # Remove BOM
    return s

def init_db_structure():
    conn = get_db_connection()
    
    try:
        # 1. Create Schema
        with conn.cursor() as cur:
            logger.info(f"Creating schema {SCHEMA_NAME} if not exists...")
            cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(SCHEMA_NAME)))
            conn.commit()

        # 2. Read headers from CSV to define table structure
        logger.info(f"Reading headers from {CSV_FILE}...")
        with open(CSV_FILE, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f, delimiter='»')
            headers = next(reader)
        
        sanitized_columns = [sanitize_column_name(col) for col in headers]
        
        # Handle duplicates
        if len(sanitized_columns) != len(set(sanitized_columns)):
            seen = set()
            new_cols = []
            for col in sanitized_columns:
                if col in seen:
                    i = 1
                    while f"{col}_{i}" in seen:
                        i += 1
                    col = f"{col}_{i}"
                seen.add(col)
                new_cols.append(col)
            sanitized_columns = new_cols

        # 3. Create Table in Schema
        pk_col = sanitized_columns[0]
        cols_def_list = [f"{pk_col} TEXT PRIMARY KEY"]
        for col in sanitized_columns[1:]:
            cols_def_list.append(f"{col} TEXT")
        
        cols_def = ", ".join(cols_def_list)
        
        # Fully qualified table name: "PQRS"."tcc_registradas"
        fq_table_name = sql.SQL("{}.{}").format(sql.Identifier(SCHEMA_NAME), sql.Identifier(TABLE_NAME))
        
        create_query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
            fq_table_name,
            sql.SQL(cols_def)
        )
        
        with conn.cursor() as cur:
            logger.info(f"Creating table {SCHEMA_NAME}.{TABLE_NAME}...")
            cur.execute(create_query)
            conn.commit()
            
        logger.info(f"Table {SCHEMA_NAME}.{TABLE_NAME} created/verified.")

        # 4. Create tcc_registradas_{clase} Tables (Optimized: PK + clasificacion only)
        
        # Only include PK and clasificacion
        cols_def_list_clase = [f"{pk_col} TEXT PRIMARY KEY"]
        # Add Foreign Key constraint logic could be added here, but simple PK is enough for optimization structure base.
        # Ideally: REFERENCES PQRS.tcc_registradas(numero_peticion)        
        # Add the additional columns
        cols_def_list_clase.append("clasificacion TEXT")
        cols_def_list_clase.append("procesado BOOLEAN DEFAULT FALSE")
        cols_def_list_clase.append("metodo_clasificacion CHARACTER VARYING")
        
        cols_def_clase = ", ".join(cols_def_list_clase)
        
        for clase in TABLE_NAME_CLASES:
            # Construct table name: tcc_registradas_ruido, tcc_registradas_salud, tcc_registradas_maltrato_animal, etc.
            current_table_name = f"{TABLE_NAME}_{clase}"
            fq_table_name_clase = sql.SQL("{}.{}").format(sql.Identifier(SCHEMA_NAME), sql.Identifier(current_table_name))
            idx_name = f"idx_{current_table_name}_pendientes"
            
            create_query_clase = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
                fq_table_name_clase,
                sql.SQL(cols_def_clase)
            )
            create_idx_clase = sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (procesado) WHERE procesado = FALSE").format(
                sql.Identifier(idx_name),
                fq_table_name_clase
            )
            
            with conn.cursor() as cur:
                logger.info(f"Checking table {SCHEMA_NAME}.{current_table_name}...")
                cur.execute(create_query_clase)
                cur.execute(create_idx_clase)
                conn.commit()
            
        logger.info(f"Structure initialized successfully in schema {SCHEMA_NAME}.")
        
    except Exception as e:
        logger.error(f"Failed to initialize database structure: {e}")
        conn.close()
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db_structure()
