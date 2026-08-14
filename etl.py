
import csv
import psycopg2
from psycopg2 import sql, extras
import logging
import sys
import os
from download_azure import download_blob_file
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Reduce noise from Azure and external libraries
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)


# Database Configuration
DB_CONFIG = config.DB_CONFIG

# Constants
CSV_FILE = config.CSV_FILE
SCHEMA_NAME = config.SCHEMA_NAME
TABLE_NAME = config.TABLE_NAME_MAIN
TABLE_NAME_CLASES = config.TABLE_NAME_CLASES
CHUNK_SIZE = config.CHUNK_SIZE  # Number of rows to process at a time

# Download is handled by download_azure.py imported at the top

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)

def sanitize_column_name(col_name):
    # Remove special characters, spaces to underscores, lowercase
    # Also handle some specific odd chars from the original header if needed
    s = col_name.strip().lower().replace(" ", "_")
    s = s.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    s = s.replace("ñ", "n").replace(".", "").replace("/", "_").replace("-", "_")
    # remove BOM if present
    s = s.replace('\ufeff', '')
    return s

def create_table(conn, columns):
    sanitized_columns = [sanitize_column_name(col) for col in columns]
    
    # Check for duplicates in sanitized column names
    if len(sanitized_columns) != len(set(sanitized_columns)):
        logger.warning("Duplicate column names detected after sanitization. Handling duplicates...")
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

    # First column is assumed to be the Primary Key based on the CSV structure (Número petición)
    pk_col = sanitized_columns[0] 
    
    cols_def_list = [f"{pk_col} TEXT PRIMARY KEY"]
    for col in sanitized_columns[1:]:
        cols_def_list.append(f"{col} TEXT")
    
    cols_def = ", ".join(cols_def_list)
    
    fq_table_name = sql.SQL("{}.{}").format(sql.Identifier(SCHEMA_NAME), sql.Identifier(TABLE_NAME))
    
    create_query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({});").format(
        fq_table_name,
        sql.SQL(cols_def)
    )
    
    with conn.cursor() as cur:
        logger.info(f"Creating table {SCHEMA_NAME}.{TABLE_NAME} if not exists...")
        cur.execute(create_query)
        conn.commit()
    
    return sanitized_columns

def process_etl():
    # 1. Download file is now handled by Orchestrator
    
    if not os.path.exists(CSV_FILE):
        logger.info(f"No se encontró el archivo {CSV_FILE} localmente. Saltando ETL local ya que no hay datos nuevos.")
        return

    conn = get_db_connection()
    
    try:
        # Open CSV file
        # Using encoding='utf-8-sig' to handle BOM if present, otherwise 'utf-8' or 'latin-1' might be needed.
        # Given the previous 'head' output showed readable characters, likely utf-8.
        # The delimiter is '»'
        f = open(CSV_FILE, 'r', encoding='utf-8', errors='replace')
        # We need to handle the potential complexity of the separator.
        # Python's csv module handles single char delimiters fine.
        reader = csv.reader(f, delimiter='»')
        
        headers = next(reader)
        sanitized_columns = create_table(conn, headers)
        
    except Exception as e:
        logger.error(f"Failed to read CSV headers or create table: {e}")
        if 'f' in locals(): f.close()
        conn.close()
        sys.exit(1)

    # Counters
    total_processed = 0
    total_inserted = 0
    total_existing = 0
    total_errors = 0

    # SQL for insertion
    pk_col = sanitized_columns[0]
    
    # Prepare list of target tables: Main table + Class tables
    target_tables = [TABLE_NAME] + [f"{TABLE_NAME}_{clase}" for clase in TABLE_NAME_CLASES]
    
    # Pre-calculate INSERT queries for each table
    # Pre-calculate INSERT queries for each table
    insert_queries = {}
    
    # Main Table Query (Full Columns)
    fq_main_tbl = sql.SQL("{}.{}").format(sql.Identifier(SCHEMA_NAME), sql.Identifier(TABLE_NAME))
    base_q_main = sql.SQL("INSERT INTO {table} ({fields}) VALUES %s").format(
        table=fq_main_tbl,
        fields=sql.SQL(', ').join(map(sql.Identifier, sanitized_columns))
    )
    single_q_main = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({placeholders}) ON CONFLICT ({pk}) DO NOTHING").format(
        table=fq_main_tbl,
        fields=sql.SQL(', ').join(map(sql.Identifier, sanitized_columns)),
        placeholders=sql.SQL(', ').join(sql.Placeholder() * len(sanitized_columns)),
        pk=sql.Identifier(pk_col)
    )
    insert_queries[TABLE_NAME] = {"base": base_q_main, "single": single_q_main, "is_main": True}
    
    # Class Table Query (PK + clasificacion)
    # Target columns: [pk_col, "clasificacion"]
    class_cols = [pk_col, "clasificacion"]
    
    for tbl_clase in [f"{TABLE_NAME}_{clase}" for clase in TABLE_NAME_CLASES]:
        fq_tbl = sql.SQL("{}.{}").format(sql.Identifier(SCHEMA_NAME), sql.Identifier(tbl_clase))
        
        base_q = sql.SQL("INSERT INTO {table} ({fields}) VALUES %s").format(
            table=fq_tbl,
            fields=sql.SQL(', ').join(map(sql.Identifier, class_cols))
        )
        
        single_q = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({placeholders}) ON CONFLICT ({pk}) DO NOTHING").format(
            table=fq_tbl,
            fields=sql.SQL(', ').join(map(sql.Identifier, class_cols)),
            placeholders=sql.SQL(', ').join(sql.Placeholder() * len(class_cols)),
            pk=sql.Identifier(pk_col)
        )
        insert_queries[tbl_clase] = {"base": base_q, "single": single_q, "is_main": False}

    batch = []
    
    def flush_batch(current_batch):
        nonlocal total_inserted, total_existing, total_errors
        
        if not current_batch:
            return

        cols_count = len(sanitized_columns)
        # Validate row length (simple check)
        valid_rows = []
        for row in current_batch:
            if len(row) == cols_count:
                valid_rows.append(row)
            else:
                if len(row) < cols_count:
                    valid_rows.append(row + [None]*(cols_count-len(row)))
                else:
                    valid_rows.append(row[:cols_count])
        
        # Perform insert for each table
        # We track stats ONLY for the main table (first in target_tables)
        
        # Prepare subset data for class tables: (PK, None)
        # PK is usually first column, sanitized_columns[0]
        # We verify sanitized_columns[0] == pk_col, which is true by logic.
        # But we need index of pk_col in sanitized_columns to be safe? 
        # Yes, definition says sanitized_columns[0] is PK.
        valid_rows_class = [(row[0], None) for row in valid_rows]

        # Perform insert for each table
        for tbl in target_tables:
            is_main_table = (tbl == TABLE_NAME)
            queries = insert_queries[tbl]
            
            # Select appropriate data
            current_rows = valid_rows if is_main_table else valid_rows_class
            
            try:
                with conn.cursor() as cur:
                    full_query = queries["base"].as_string(conn) + " ON CONFLICT (" + pk_col + ") DO NOTHING"
                    
                    extras.execute_values(cur, full_query, current_rows)
                    
                    if is_main_table:
                        inserted_in_batch = cur.rowcount
                        existing_in_batch = len(valid_rows) - inserted_in_batch
                        total_inserted += inserted_in_batch
                        total_existing += existing_in_batch
                    
                    conn.commit()
                    
            except Exception as e:
                conn.rollback()
                if is_main_table:
                    logger.warning(f"Batch failed for {tbl}: {e}. Switching to row-by-row processing...")
                
                with conn.cursor() as cur:
                    for row in current_rows:
                        try:
                            cur.execute(queries["single"], row)
                            if is_main_table:
                                if cur.rowcount > 0:
                                    total_inserted += 1
                                else:
                                    total_existing += 1
                            conn.commit()
                        except Exception as row_error:
                            conn.rollback()
                            if is_main_table:
                                logger.error(f"Error inserting row in {tbl}: {row_error}")
                                total_errors += 1


    try:
        # Loop through CSV
        for row in reader:
            batch.append(row)
            total_processed += 1
            
            if len(batch) >= CHUNK_SIZE:
                flush_batch(batch)
                batch = []
                if total_processed % 50000 == 0:
                    logger.info(f"Processed {total_processed} rows...")

        # Flush remaining
        if batch:
            flush_batch(batch)

    except KeyboardInterrupt:
        logger.warning("\nETL interrupted by user. Finalizing current batch and displaying stats...")
        # Optionally flush the partial batch if needed, or just stop. 
        # Usually user wants to stop immediately. Let's just print stats.
        pass
    except Exception as e:
        logger.error(f"Error during processing: {e}")


    f.close()
    conn.close()

    try:
        if os.path.exists(CSV_FILE):
            os.remove(CSV_FILE)
            logger.info(f"Archivo temporal {CSV_FILE} eliminado para liberar espacio.")
    except Exception as e:
        logger.warning(f"No se pudo eliminar el archivo {CSV_FILE}: {e}")

    print("\n" + "="*40)
    print("ETL Summary")
    print("="*40)
    print(f"Total processed: {total_processed}")
    print(f"Inserted: {total_inserted}")
    print(f"Not inserted (Already Existed): {total_existing}")
    print(f"Not inserted (Errors): {total_errors}")
    print("="*40)

if __name__ == "__main__":
    process_etl()
