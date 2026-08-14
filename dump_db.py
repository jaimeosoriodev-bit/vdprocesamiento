import os
import subprocess
from datetime import datetime
import config

# DB Connection
DB_HOST = config.DB_CONFIG["host"]
DB_PORT = config.DB_CONFIG["port"]
DB_USER = config.DB_CONFIG["user"]
DB_PASS = config.DB_CONFIG["password"]
DB_NAME = config.DB_CONFIG["dbname"]
SCHEMA = f'"{config.SCHEMA_NAME}"'

def dump_schema():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dump_file = f"pqrs_dump_{timestamp}.sql"
    env = os.environ.copy()
    env["PGPASSWORD"] = DB_PASS
    
    cmd = [
        "/usr/local/bin/docker", "exec", "-i",
        "-e", f"PGPASSWORD={DB_PASS}",
        "postgres",
        "pg_dump",
        "-U", DB_USER,
        "-d", DB_NAME,
        "-n", SCHEMA
    ]
    
    print(f"Dumping schema {SCHEMA} to {dump_file} via Docker...")
    try:
        with open(dump_file, "w") as f:
            subprocess.run(cmd, stdout=f, check=True)
        print(f"Dump successful. File created: {os.path.abspath(dump_file)}")
        return os.path.abspath(dump_file)
    except Exception as e:
        print(f"Error during dump: {e}")
        return None

if __name__ == "__main__":
    dump_schema()
