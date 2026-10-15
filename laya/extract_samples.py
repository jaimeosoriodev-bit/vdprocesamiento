import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import csv
import psycopg2
import config

def extract_samples():
    conn = psycopg2.connect(**config.DB_CONFIG)
    cur = conn.cursor()
    
    samples = []
    
    # Stratified target counts:
    # 1. RUIDO (10 subcategories): total target 350
    # 2. SALUD (5 subcategories): total target 350
    # 3. MALTRATO ANIMAL (1 subcategory): total target 300
    # Grand total: 1000
    
    plan = {
        'ruido': {
            'Ruido por actividades lúdicas': 35,
            'Ruido por comercio (comercio - bar, comercio - gastrobar)': 35,
            'Ruido por construcción': 35,
            'Ruido por industria': 35,
            'Ruido por servicios': 35,
            'Ruido por tráfico aéreo': 23, # All available (total in db is 23)
            'Ruido por tráfico vehicular': 35,
            'Ruido por vecinos': 35,
            'Ruido por ventas ambulantes': 35,
            'Ruido sin especificar': 47    # adjusted to reach exactly 350 for ruido
        },
        'salud': {
            'Fallas en la prestación del servicio/humanización del servicio': 70,
            'Negación de citas médicas': 70,
            'Negación de Medicamentos': 70,
            'Negación de procedimientos': 70,
            'Otros': 70
        },
        'maltrato_animal': {
            'Maltrato Animal': 300
        }
    }
    
    print("--- INICIANDO EXTRACCIÓN DE 1000 EJEMPLOS (READ-ONLY) ---")
    
    for clase, subcats in plan.items():
        table_clase = f'"{config.SCHEMA_NAME}"."tcc_registradas_{clase}"'
        table_main = f'"{config.SCHEMA_NAME}"."{config.TABLE_NAME_MAIN or "tcc_registradas"}"'
        
        for subcat, target_count in subcats.items():
            query = f"""
                SELECT t1.numero_peticion, t1.clasificacion, t1.metodo_clasificacion, t2.asunto
                FROM {table_clase} t1
                JOIN {table_main} t2 ON t1.numero_peticion = t2.numero_peticion
                WHERE t1.clasificacion = %s
                  AND t2.asunto IS NOT NULL
                  AND TRIM(t2.asunto) <> ''
                ORDER BY RANDOM()
                LIMIT %s
            """
            cur.execute(query, (subcat, target_count))
            rows = cur.fetchall()
            print(f"[{clase}] Subcategoría '{subcat}': Solicitados {target_count}, Obtenidos {len(rows)}")
            
            for row in rows:
                samples.append({
                    "numero_peticion": row[0],
                    "clase": clase,
                    "clasificacion_original": row[1],
                    "metodo_original": row[2],
                    "asunto": row[3]
                })
                
    conn.close()
    
    print(f"\nTotal ejemplos recopilados: {len(samples)}")
    
    # Save to JSON
    out_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(out_dir, "dataset_muestra_1000.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"Guardado JSON en: {json_path}")
    
    # Save to CSV
    csv_path = os.path.join(out_dir, "dataset_muestra_1000.csv")
    fieldnames = ["numero_peticion", "clase", "clasificacion_original", "metodo_original", "asunto"]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)
    print(f"Guardado CSV en: {csv_path}")

if __name__ == "__main__":
    extract_samples()
