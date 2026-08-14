import os
import csv
import psycopg2
from psycopg2 import sql
import sys

# Agregar el directorio padre al PATH para poder importar config.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def export_march_2026():
    output_filename = "pqrs_marzo_2026.csv"
    # Guardar en la misma carpeta tools
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)
    
    print("Conectando a la base de datos...")
    try:
        conn = psycopg2.connect(**config.DB_CONFIG)
    except Exception as e:
        print(f"Error de conexión a la base de datos: {e}")
        sys.exit(1)
        
    schema = config.SCHEMA_NAME
    table = config.TABLE_NAME_MAIN
    
    # Consulta para obtener registros de marzo de 2026
    # Usamos tanto fecha_ingreso como fecha_registro para cubrir la contingencia de marzo
    query = sql.SQL("""
        SELECT * 
        FROM {schema}.{table}
        WHERE fecha_ingreso LIKE '2026-03%' OR fecha_registro LIKE '2026-03%'
        ORDER BY fecha_ingreso ASC;
    """).format(
        schema=sql.Identifier(schema),
        table=sql.Identifier(table)
    )
    
    print("Consultando registros correspondientes a marzo de 2026...")
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            
            # Obtener nombres de las columnas
            columns = [desc[0] for desc in cur.description]
            
            rows = cur.fetchall()
            total_records = len(rows)
            print(f"Se encontraron {total_records} registros.")
            
            if total_records == 0:
                print("No se encontraron registros para exportar.")
                return
            
            print(f"Escribiendo registros en el archivo CSV...")
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                # Usar el delimitador estándar del proyecto '»'
                writer = csv.writer(f, delimiter='»')
                writer.writerow(columns)
                writer.writerows(rows)
                
            print(f"[OK] Exportación completada con éxito.")
            print(f"Archivo generado: {output_path}")
            
    except Exception as e:
        print(f"Error ejecutando la consulta o escribiendo el archivo: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    export_march_2026()
