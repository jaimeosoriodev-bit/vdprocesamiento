import os
import sys
import psycopg2
from psycopg2 import sql

# Agregar el directorio padre al PATH para poder importar config.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def format_table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
            
    header_line = " | ".join(f"{h:<{widths[i]}}" for i, h in enumerate(headers))
    separator_line = "-+-".join("-" * w for w in widths)
    
    table_lines = [header_line, separator_line]
    for row in rows:
        row_line = " | ".join(f"{str(val):<{widths[i]}}" for i, val in enumerate(row))
        table_lines.append(row_line)
        
    return "\n".join(table_lines)

def generate_report():
    print("Conectando a la base de datos...")
    try:
        conn = psycopg2.connect(**config.DB_CONFIG)
    except Exception as e:
        print(f"Error de conexión: {e}")
        sys.exit(1)
        
    schema = config.SCHEMA_NAME
    table_main = config.TABLE_NAME_MAIN
    table_salud = f"{table_main}_salud"
    
    # 1. Metricas por Fecha de Ingreso
    print("Calculando métricas por fecha de ingreso...")
    query_ingreso = sql.SQL("""
        SELECT 
            SUBSTRING(t2.fecha_ingreso, 1, 7) AS mes,
            COUNT(*) AS total_pqrs,
            COUNT(*) FILTER (WHERE t1.clasificacion IS NOT NULL) AS clasificados_salud
        FROM {schema}.{table_salud} t1
        JOIN {schema}.{table_main} t2 ON t1.numero_peticion = t2.numero_peticion
        GROUP BY mes
        ORDER BY mes DESC;
    """).format(
        schema=sql.Identifier(schema),
        table_salud=sql.Identifier(table_salud),
        table_main=sql.Identifier(table_main)
    )
    
    # 2. Metricas por Fecha de Registro
    print("Calculando métricas por fecha de registro...")
    query_registro = sql.SQL("""
        SELECT 
            SUBSTRING(t2.fecha_registro, 1, 7) AS mes,
            COUNT(*) AS total_pqrs,
            COUNT(*) FILTER (WHERE t1.clasificacion IS NOT NULL) AS clasificados_salud,
            COUNT(*) FILTER (WHERE t2.asunto IS NULL OR TRIM(t2.asunto) = '') AS sin_asunto
        FROM {schema}.{table_salud} t1
        JOIN {schema}.{table_main} t2 ON t1.numero_peticion = t2.numero_peticion
        GROUP BY mes
        ORDER BY mes DESC;
    """).format(
        schema=sql.Identifier(schema),
        table_salud=sql.Identifier(table_salud),
        table_main=sql.Identifier(table_main)
    )
    
    report_lines = []
    report_lines.append("# Reporte de Porcentajes de Clasificación en Salud por Mes\n")
    
    try:
        with conn.cursor() as cur:
            # Procesar fecha de ingreso
            cur.execute(query_ingreso)
            rows_ingreso = cur.fetchall()
            
            ingreso_table_rows = []
            for r in rows_ingreso:
                mes = r[0] if r[0] else "Sin fecha"
                total = r[1]
                salud = r[2]
                pct = (salud / total) * 100 if total > 0 else 0.0
                ingreso_table_rows.append([mes, f"{total:,}", f"{salud:,}", f"{pct:.4f}%"])
                
            report_lines.append("## 1. Métricas por Fecha de Ingreso")
            report_lines.append(format_table(["Año-Mes (Ingreso)", "Total PQRS", "Clasificados Salud", "Porcentaje Salud"], ingreso_table_rows))
            report_lines.append("\n" + "="*80 + "\n")
            
            # Procesar fecha de registro
            cur.execute(query_registro)
            rows_registro = cur.fetchall()
            
            registro_table_rows = []
            for r in rows_registro:
                mes = r[0] if r[0] else "Sin fecha"
                total = r[1]
                salud = r[2]
                sin_asunto = r[3]
                pct = (salud / total) * 100 if total > 0 else 0.0
                pct_sin_asunto = (sin_asunto / total) * 100 if total > 0 else 0.0
                registro_table_rows.append([mes, f"{total:,}", f"{salud:,}", f"{pct:.4f}%", f"{sin_asunto:,} ({pct_sin_asunto:.2f}%)"])
                
            report_lines.append("## 2. Métricas por Fecha de Registro")
            report_lines.append(format_table(["Año-Mes (Registro)", "Total PQRS", "Clasificados Salud", "Porcentaje Salud", "Sin Asunto (%)"], registro_table_rows))
            
        report_text = "\n".join(report_lines)
        
        # Guardar archivo
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reporte_porcentajes_salud.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
            
        print(f"\n[OK] Reporte generado exitosamente en: {output_path}")
        
    except Exception as e:
        print(f"Error procesando el reporte: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    generate_report()
