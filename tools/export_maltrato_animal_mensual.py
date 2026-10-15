import os
import sys
import csv
import psycopg2
from psycopg2 import sql

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def export_maltrato_animal_mensual():
    output_filename = "pqrs_maltrato_animal_por_mes.csv"
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(root_dir, output_filename)
    
    print("Conectando a la base de datos PostgreSQL...")
    conn = psycopg2.connect(**config.DB_CONFIG)
    
    schema = config.SCHEMA_NAME
    table_main = config.TABLE_NAME_MAIN
    table_maltrato = f"{table_main}_maltrato_animal"
    
    query = sql.SQL("""
        SELECT 
            SUBSTRING(t2.fecha_ingreso, 1, 7) AS anio_mes,
            COUNT(*) AS total_pqrs,
            COUNT(*) FILTER (WHERE t1.clasificacion IS NOT NULL) AS maltrato_animal
        FROM {schema}.{table_maltrato} t1
        JOIN {schema}.{table_main} t2 ON t1.numero_peticion = t2.numero_peticion
        WHERE t2.fecha_ingreso IS NOT NULL AND TRIM(t2.fecha_ingreso) != ''
        GROUP BY anio_mes
        ORDER BY anio_mes ASC;
    """).format(
        schema=sql.Identifier(schema),
        table_maltrato=sql.Identifier(table_maltrato),
        table_main=sql.Identifier(table_main)
    )
    
    try:
        with conn.cursor() as cur:
            print("Consultando métricas mensuales de maltrato animal...")
            cur.execute(query)
            rows = cur.fetchall()
            
            headers = [
                "anio_mes",
                "anio",
                "mes",
                "cantidad_maltrato_animal",
                "total_pqrs",
                "porcentaje_maltrato_animal"
            ]
            
            csv_rows = []
            total_maltrato_sum = 0
            total_pqrs_sum = 0
            
            for row in rows:
                anio_mes = row[0]
                total_pqrs = row[1]
                cant_maltrato = row[2]
                
                if not anio_mes or len(anio_mes) < 7:
                    continue
                    
                anio = anio_mes[:4]
                mes = anio_mes[5:7]
                pct = (cant_maltrato / total_pqrs * 100) if total_pqrs > 0 else 0.0
                
                total_maltrato_sum += cant_maltrato
                total_pqrs_sum += total_pqrs
                
                csv_rows.append([
                    anio_mes,
                    anio,
                    mes,
                    cant_maltrato,
                    total_pqrs,
                    f"{pct:.4f}%"
                ])
                
            print(f"Escribiendo {len(csv_rows)} meses en {output_path}...")
            with open(output_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=",")
                writer.writerow(headers)
                writer.writerows(csv_rows)
                
            print(f"\n[OK] Archivo CSV exportado exitosamente en: {output_path}")
            print(f"Total histórico PQRS: {total_pqrs_sum:,}")
            print(f"Total clasificadas como Maltrato Animal: {total_maltrato_sum:,}")
            overall_pct = (total_maltrato_sum / total_pqrs_sum * 100) if total_pqrs_sum > 0 else 0
            print(f"Porcentaje global: {overall_pct:.2f}%")
            return output_path
            
    finally:
        conn.close()

if __name__ == "__main__":
    export_maltrato_animal_mensual()
