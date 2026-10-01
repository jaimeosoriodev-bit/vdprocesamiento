import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import psycopg2
from psycopg2 import sql
import config

def get_db_connection():
    try:
        conn = psycopg2.connect(**config.DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        sys.exit(1)

def format_table(headers, rows):
    # Genera una representación en texto plano / markdown de una tabla
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

def obtener_metricas():
    schema = config.SCHEMA_NAME
    table_main = config.TABLE_NAME_MAIN
    
    print("Conectando a la base de datos...")
    conn = get_db_connection()
    
    try:
        with conn.cursor() as cur:
            # 1. Cantidad de PQRS por cada mes
            print("Consultando PQRS por mes...")
            query_mes = sql.SQL("""
                SELECT 
                    SUBSTRING(fecha_ingreso, 1, 7) AS mes, 
                    COUNT(*) AS total_pqrs
                FROM {schema}.{table}
                GROUP BY mes
                ORDER BY mes;
            """).format(
                schema=sql.Identifier(schema),
                table=sql.Identifier(table_main)
            )
            cur.execute(query_mes)
            rows_mes = cur.fetchall()
            
            # 2. Cantidad de PQRS con asunto
            print("Consultando PQRS con asunto...")
            query_asunto = sql.SQL("""
                SELECT 
                    COUNT(*) FILTER (WHERE asunto IS NOT NULL AND TRIM(asunto) != '') AS con_asunto,
                    COUNT(*) FILTER (WHERE asunto IS NULL OR TRIM(asunto) = '') AS sin_asunto,
                    COUNT(*) AS total
                FROM {schema}.{table};
            """).format(
                schema=sql.Identifier(schema),
                table=sql.Identifier(table_main)
            )
            cur.execute(query_asunto)
            con_asunto, sin_asunto, total_pqrs = cur.fetchone()
            
            # 3. Cantidad de registros clasificados por salud
            print("Consultando clasificaciones de salud...")
            table_salud = f"{table_main}_salud"
            query_salud_total = sql.SQL("""
                SELECT 
                    COUNT(*) FILTER (WHERE clasificacion IS NOT NULL) AS clasificados,
                    COUNT(*) FILTER (WHERE clasificacion IS NULL) AS no_clasificados,
                    COUNT(*) AS total
                FROM {schema}.{table_salud};
            """).format(
                schema=sql.Identifier(schema),
                table_salud=sql.Identifier(table_salud)
            )
            cur.execute(query_salud_total)
            clasificados_salud, no_clasificados_salud, total_salud = cur.fetchone()
            
            # Desglose salud
            query_salud_breakdown = sql.SQL("""
                SELECT clasificacion, COUNT(*) AS total
                FROM {schema}.{table_salud}
                WHERE clasificacion IS NOT NULL
                GROUP BY clasificacion
                ORDER BY total DESC;
            """).format(
                schema=sql.Identifier(schema),
                table_salud=sql.Identifier(table_salud)
            )
            cur.execute(query_salud_breakdown)
            rows_salud_breakdown = cur.fetchall()
            
            # 4. Cantidad de registros clasificados por ruido
            print("Consultando clasificaciones de ruido...")
            table_ruido = f"{table_main}_ruido"
            query_ruido_total = sql.SQL("""
                SELECT 
                    COUNT(*) FILTER (WHERE clasificacion IS NOT NULL) AS clasificados,
                    COUNT(*) FILTER (WHERE clasificacion IS NULL) AS no_clasificados,
                    COUNT(*) AS total
                FROM {schema}.{table_ruido};
            """).format(
                schema=sql.Identifier(schema),
                table_ruido=sql.Identifier(table_ruido)
            )
            cur.execute(query_ruido_total)
            clasificados_ruido, no_clasificados_ruido, total_ruido = cur.fetchone()
            
            # Desglose ruido
            query_ruido_breakdown = sql.SQL("""
                SELECT clasificacion, COUNT(*) AS total
                FROM {schema}.{table_ruido}
                WHERE clasificacion IS NOT NULL
                GROUP BY clasificacion
                ORDER BY total DESC;
            """).format(
                schema=sql.Identifier(schema),
                table_ruido=sql.Identifier(table_ruido)
            )
            cur.execute(query_ruido_breakdown)
            rows_ruido_breakdown = cur.fetchall()

            # 5. Cantidad de registros clasificados por maltrato animal
            print("Consultando clasificaciones de maltrato animal...")
            table_animal = f"{table_main}_maltrato_animal"
            query_animal_total = sql.SQL("""
                SELECT 
                    COUNT(*) FILTER (WHERE clasificacion IS NOT NULL) AS clasificados,
                    COUNT(*) FILTER (WHERE clasificacion IS NULL) AS no_clasificados,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE procesado = TRUE) AS procesados,
                    COUNT(*) FILTER (WHERE procesado = FALSE) AS pendientes
                FROM {schema}.{table_animal};
            """).format(
                schema=sql.Identifier(schema),
                table_animal=sql.Identifier(table_animal)
            )
            cur.execute(query_animal_total)
            clasificados_animal, no_clasificados_animal, total_animal, procesados_animal, pendientes_animal = cur.fetchone()
            
            # Desglose maltrato animal
            query_animal_breakdown = sql.SQL("""
                SELECT clasificacion, COUNT(*) AS total
                FROM {schema}.{table_animal}
                WHERE clasificacion IS NOT NULL
                GROUP BY clasificacion
                ORDER BY total DESC;
            """).format(
                schema=sql.Identifier(schema),
                table_animal=sql.Identifier(table_animal)
            )
            cur.execute(query_animal_breakdown)
            rows_animal_breakdown = cur.fetchall()
            
        conn.close()
        
        # Generar reporte Markdown
        report_content = []
        report_content.append("# Reporte de Métricas de PQRS en Base de Datos\n")
        
        # 1. Total PQRS y asunto
        report_content.append("## 1. Resumen General y Asuntos")
        asunto_table_rows = [
            ["Con Asunto (Contenido válido)", f"{con_asunto:,}", f"{(con_asunto/total_pqrs)*100:.2f}%"],
            ["Sin Asunto (Vacíos o Nulos)", f"{sin_asunto:,}", f"{(sin_asunto/total_pqrs)*100:.2f}%"],
            ["Total de PQRS", f"{total_pqrs:,}", "100.00%"]
        ]
        report_content.append(format_table(["Métrica", "Cantidad", "Porcentaje"], asunto_table_rows))
        report_content.append("")
        
        # 2. PQRS por Mes
        report_content.append("## 2. Cantidad de PQRS por Mes")
        mes_rows = [[r[0] if r[0] else "Sin fecha", f"{r[1]:,}"] for r in rows_mes]
        report_content.append(format_table(["Año-Mes", "Cantidad de PQRS"], mes_rows))
        report_content.append("")
        
        # 3. Clasificación por Salud
        report_content.append("## 3. Clasificación por Salud")
        report_content.append(f"**Total registros analizados:** {total_salud:,}")
        salud_total_rows = [
            ["Clasificados Salud (Positivos)", f"{clasificados_salud:,}", f"{(clasificados_salud/total_salud)*100:.2f}%"],
            ["No clasificados (NO APLICA / Otros)", f"{no_clasificados_salud:,}", f"{(no_clasificados_salud/total_salud)*100:.2f}%"]
        ]
        report_content.append(format_table(["Estado", "Cantidad", "Porcentaje"], salud_total_rows))
        report_content.append("\n### Desglose de Categorías de Salud:")
        if rows_salud_breakdown:
            salud_breakdown_rows = [[r[0], f"{r[1]:,}", f"{(r[1]/clasificados_salud)*100:.2f}%"] for r in rows_salud_breakdown]
            report_content.append(format_table(["Subcategoría Salud", "Cantidad", "% del total salud clasificado"], salud_breakdown_rows))
        else:
            report_content.append("*No hay registros clasificados en categorías de salud.*")
        report_content.append("")
        
        # 4. Clasificación por Ruido
        report_content.append("## 4. Clasificación por Ruido")
        report_content.append(f"**Total registros analizados:** {total_ruido:,}")
        ruido_total_rows = [
            ["Clasificados Ruido (Positivos)", f"{clasificados_ruido:,}", f"{(clasificados_ruido/total_ruido)*100:.2f}%"],
            ["No clasificados (NO APLICA / Otros)", f"{no_clasificados_ruido:,}", f"{(no_clasificados_ruido/total_ruido)*100:.2f}%"]
        ]
        report_content.append(format_table(["Estado", "Cantidad", "Porcentaje"], ruido_total_rows))
        report_content.append("\n### Desglose de Categorías de Ruido:")
        if rows_ruido_breakdown:
            ruido_breakdown_rows = [[r[0], f"{r[1]:,}", f"{(r[1]/clasificados_ruido)*100:.2f}%"] for r in rows_ruido_breakdown]
            report_content.append(format_table(["Subcategoría Ruido", "Cantidad", "% del total ruido clasificado"], ruido_breakdown_rows))
        else:
            report_content.append("*No hay registros clasificados en categorías de ruido.*")
        report_content.append("")

        # 5. Clasificación por Maltrato Animal
        report_content.append("## 5. Clasificación por Maltrato Animal")
        report_content.append(f"**Total registros:** {total_animal:,} | **Procesados:** {procesados_animal:,} | **Pendientes:** {pendientes_animal:,}")
        animal_total_rows = [
            ["Clasificados Maltrato Animal (Positivos)", f"{clasificados_animal:,}", f"{(clasificados_animal/total_animal)*100:.2f}%" if total_animal > 0 else "0.00%"],
            ["No clasificados (NO APLICA / No Animal)", f"{no_clasificados_animal:,}", f"{(no_clasificados_animal/total_animal)*100:.2f}%" if total_animal > 0 else "0.00%"]
        ]
        report_content.append(format_table(["Estado", "Cantidad", "Porcentaje"], animal_total_rows))
        report_content.append("\n### Desglose de Categorías de Maltrato Animal:")
        if rows_animal_breakdown:
            animal_breakdown_rows = [[r[0], f"{r[1]:,}", f"{(r[1]/clasificados_animal)*100:.2f}%" if clasificados_animal > 0 else "0.00%"] for r in rows_animal_breakdown]
            report_content.append(format_table(["Categoría", "Cantidad", "% del total clasificado"], animal_breakdown_rows))
        else:
            report_content.append("*No hay registros clasificados aún en categorías de maltrato animal.*")
        report_content.append("")
        
        report_text = "\n".join(report_content)
        
        # Imprimir en consola
        print("\n" + "=" * 50)
        print(" REPORTE GENERADO CON ÉXITO")
        print("=" * 50 + "\n")
        print(report_text)
        
        # Guardar en archivo
        report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reporte_metricas_pqrs.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"\n[OK] Reporte guardado en: {report_path}")
        
    except Exception as e:
        print(f"Error procesando métricas: {e}")
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    obtener_metricas()
