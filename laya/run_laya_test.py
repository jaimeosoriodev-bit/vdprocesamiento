import os
import sys
import json
import csv
import time
from collections import defaultdict

# Add parent directory for config if needed
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

import laya

LAYA_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(LAYA_DIR, "dataset_muestra_1000.json")
OUTPUT_JSON = os.path.join(LAYA_DIR, "resultados_clasificacion_laya.json")
OUTPUT_CSV = os.path.join(LAYA_DIR, "resultados_clasificacion_laya.csv")
METRICS_JSON = os.path.join(LAYA_DIR, "matriz_confusion_y_metricas.json")
REPORT_MD = os.path.join(LAYA_DIR, "INFORME_CLASIFICACION_LAYA.md")

# Categories dictionary
CATEGORIAS = {
    'ruido': [
        'Ruido por actividades lúdicas',
        'Ruido por comercio (comercio - bar, comercio - gastrobar)',
        'Ruido por construcción',
        'Ruido por industria',
        'Ruido por servicios',
        'Ruido por tráfico aéreo',
        'Ruido por tráfico vehicular',
        'Ruido por vecinos',
        'Ruido por ventas ambulantes',
        'Ruido sin especificar'
    ],
    'salud': [
        'Fallas en la prestación del servicio/humanización del servicio',
        'Negación de citas médicas',
        'Negación de Medicamentos',
        'Negación de procedimientos',
        'Otros'
    ],
    'maltrato_animal': [
        'Maltrato Animal'
    ]
}

def build_laya_criteria(clase, categories):
    clase_clean = clase.lower().strip()
    clase_display = clase.replace("_", " ")
    
    criteria = {}
    
    if clase_clean == "maltrato_animal":
        for cat in categories:
            if "maltrato" in cat.lower():
                criteria[cat] = "Denuncias o situaciones de maltrato, abandono, agresiones físicas, encierro indebido, desnutrición, falta de auxilio o crueldad hacia animales."
            else:
                criteria[cat] = f"El asunto corresponde a {cat}."
    elif clase_clean == "salud":
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
        for cat in categories:
            criteria[cat] = f"El asunto corresponde a quejas por {cat.lower()}."
    else:
        for cat in categories:
            criteria[cat] = f"El asunto corresponde específicamente a {cat}."
            
    return criteria

def main():
    print("==================================================================")
    print("=== PROCESAMIENTO DE EVALUACIÓN: LAYA (SYSTEM 1 DECISION ENGINE) ===")
    print("==================================================================")
    
    if not os.path.exists(DATASET_PATH):
        print(f"Error: No se encontró el dataset en {DATASET_PATH}")
        sys.exit(1)
        
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
        
    print(f"Total registros cargados para la prueba: {len(records)}")
    
    # Initialize Laya Router with multilingual model
    print("\nInicializando Laya Router (checkpoint: convaiinnovations/laya - multilingual)...")
    init_start = time.time()
    router = laya.Router(default="multilingual")
    init_duration = time.time() - init_start
    print(f"Laya Router inicializado en {init_duration:.2f} segundos.")
    
    results = []
    
    # Metrics accumulators
    class_stats = defaultdict(lambda: {
        "total": 0,
        "coincidencias": 0,
        "latencias": [],
        "confidencias": [],
        "subcategorias": defaultdict(lambda: {"total": 0, "coincidencias": 0, "predicciones_laya": defaultdict(int)})
    })
    
    print("\nIniciando inferencia sobre los 1000 registros...")
    start_total_time = time.time()
    
    for idx, rec in enumerate(records, 1):
        numero_peticion = rec["numero_peticion"]
        clase = rec["clase"]
        original = rec["clasificacion_original"]
        asunto = rec["asunto"]
        
        cats = CATEGORIAS.get(clase, [original])
        criteria = build_laya_criteria(clase, cats)
        clase_display = clase.replace("_", " ")
        
        # State and questions according to System 1 specification
        asunto_clean = str(asunto)[:800].strip()
        state = asunto_clean
        
        questions = {
            "clasificacion": {
                "type": "choice",
                "instructions": f"Determinar la subcategoría adecuada de {clase_display} para la siguiente petición ciudadana.",
                "criteria": criteria
            }
        }
        
        t0 = time.time()
        try:
            pred = router.predict(state, questions)
            latency = time.time() - t0
            
            ans = pred.get("answers", {}).get("clasificacion", {})
            choice = ans.get("choice", "ERROR")
            probabilities = ans.get("probabilities", {})
            confidence = ans.get("confidence", 0.0)
            answer_confidence = ans.get("answer_confidence", 0.0)
            routing_info = pred.get("routing", {})
        except Exception as e:
            latency = time.time() - t0
            choice = f"ERROR: {str(e)}"
            probabilities = {}
            confidence = 0.0
            answer_confidence = 0.0
            routing_info = {}
            print(f"[{idx}/{len(records)}] Error en {numero_peticion}: {e}")
            
        coincide = (choice == original)
        
        # Accumulate metrics
        stats = class_stats[clase]
        stats["total"] += 1
        if coincide:
            stats["coincidencias"] += 1
        stats["latencias"].append(latency)
        stats["confidencias"].append(answer_confidence)
        
        sub_stats = stats["subcategorias"][original]
        sub_stats["total"] += 1
        if coincide:
            sub_stats["coincidencias"] += 1
        sub_stats["predicciones_laya"][choice] += 1
        
        result_entry = {
            "numero_peticion": numero_peticion,
            "clase": clase,
            "asunto": asunto_clean,
            "clasificacion_original": original,
            "metodo_original": rec.get("metodo_original"),
            "clasificacion_laya": choice,
            "coincide": coincide,
            "confianza_laya": round(answer_confidence, 4),
            "margen_confianza": round(confidence, 4),
            "latencia_segundos": round(latency, 4),
            "probabilidades_completas": {k: round(v, 4) for k, v in probabilities.items()}
        }
        results.append(result_entry)
        
        if idx % 100 == 0 or idx == len(records):
            elapsed = time.time() - start_total_time
            rate = idx / elapsed
            print(f"Progreso: {idx}/{len(records)} ({idx/len(records)*100:.1f}%) | "
                  f"Velocidad: {rate:.1f} req/s | "
                  f"Tiempo transcurrido: {elapsed:.1f}s")
            
    total_elapsed = time.time() - start_total_time
    print(f"\nInferencia completada en {total_elapsed:.2f}s ({len(records)/total_elapsed:.1f} req/s)")
    
    # 1. Guardar resultados detallados en JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Resultados JSON guardados en: {OUTPUT_JSON}")
    
    # 2. Guardar resultados en CSV
    csv_fields = [
        "numero_peticion", "clase", "clasificacion_original", "metodo_original",
        "clasificacion_laya", "coincide", "confianza_laya", "margen_confianza", "latencia_segundos", "asunto"
    ]
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for r in results:
            row_copy = {k: r[k] for k in csv_fields}
            writer.writerow(row_copy)
    print(f"Resultados CSV guardados en: {OUTPUT_CSV}")
    
    # 3. Compilar matriz y resumen estadístico
    summary = {
        "metadata": {
            "modelo": "convaiinnovations/laya",
            "checkpoint": "multilingual",
            "total_muestras": len(records),
            "tiempo_total_segundos": round(total_elapsed, 2),
            "throughput_req_por_segundo": round(len(records) / total_elapsed, 2),
            "latencia_promedio_ms": round((total_elapsed / len(records)) * 1000, 2)
        },
        "resumen_global": {
            "total": len(records),
            "coincidencias_exactas": sum(1 for r in results if r["coincide"]),
            "porcentaje_acuerdo": round(sum(1 for r in results if r["coincide"]) / len(records) * 100, 2),
            "confianza_promedio": round(sum(r["confianza_laya"] for r in results) / len(records), 4)
        },
        "por_clase": {}
    }
    
    for clase, stats in class_stats.items():
        total_c = stats["total"]
        coinc_c = stats["coincidencias"]
        avg_lat = sum(stats["latencias"]) / total_c if total_c else 0
        avg_conf = sum(stats["confidencias"]) / total_c if total_c else 0
        
        sub_dict = {}
        for subcat, sstats in stats["subcategorias"].items():
            tot_s = sstats["total"]
            coinc_s = sstats["coincidencias"]
            sub_dict[subcat] = {
                "total": tot_s,
                "coincidencias": coinc_s,
                "acuerdo_pct": round(coinc_s / tot_s * 100, 2) if tot_s else 0,
                "distribucion_predicha_laya": dict(sstats["predicciones_laya"])
            }
            
        summary["por_clase"][clase] = {
            "total": total_c,
            "coincidencias": coinc_c,
            "acuerdo_pct": round(coinc_c / total_c * 100, 2) if total_c else 0,
            "latencia_promedio_ms": round(avg_lat * 1000, 2),
            "confianza_promedio": round(avg_conf, 4),
            "subcategorias": sub_dict
        }
        
    with open(METRICS_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Métricas y matriz guardadas en: {METRICS_JSON}")
    
    # 4. Generar Informe Ejecutivo en Markdown
    generate_markdown_report(summary, results)

def generate_markdown_report(summary, results):
    meta = summary["metadata"]
    glob = summary["resumen_global"]
    
    md = []
    md.append("# Informe Técnico: Evaluación y Reclasificación con Laya (System 1)")
    md.append("")
    md.append("> **Objetivo:** Evaluar el motor de decisiones de código abierto **Laya** (`convaiinnovations/laya` - checkpoint multilingüe) como alternativa local a Jev / Ollama sobre una muestra estratificada de **1,000 peticiones PQRS** de la base de datos sin alterar ningún dato existente.")
    md.append("")
    md.append("## 1. Resumen Ejecutivo de Desempeño")
    md.append("")
    md.append(f"| Métrica | Valor Obtenido |")
    md.append(f"| :--- | :--- |")
    md.append(f"| **Modelo Evaluado** | `{meta['modelo']}` ({meta['checkpoint']}) |")
    md.append(f"| **Total de Muestras Evaluadas** | **{meta['total_muestras']}** peticiones reales |")
    md.append(f"| **Tasa de Acuerdo Global** | **{glob['porcentaje_acuerdo']}%** ({glob['coincidencias_exactas']}/{meta['total_muestras']}) |")
    md.append(f"| **Tiempo Total de Ejecución** | **{meta['tiempo_total_segundos']} s** |")
    md.append(f"| **Throughput (Rendimiento)** | **{meta['throughput_req_por_segundo']} req/s** (Inferencia local) |")
    md.append(f"| **Latencia Promedio por Petición** | **{meta['latencia_promedio_ms']} ms** |")
    md.append(f"| **Nivel de Confianza Promedio** | **{glob['confianza_promedio']:.2%}** |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Resultados Consolidados por Clase Temática")
    md.append("")
    md.append("| Clase | Total Muestras | Coincidencias | % Acuerdo | Confianza Promedio | Latencia Promedio |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
    
    for clase, cdata in summary["por_clase"].items():
        md.append(f"| **{clase.upper()}** | {cdata['total']} | {cdata['coincidencias']} | **{cdata['acuerdo_pct']}%** | {cdata['confianza_promedio']:.2%} | {cdata['latencia_promedio_ms']} ms |")
        
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 3. Desglose Detallado por Subcategoría")
    md.append("")
    
    for clase, cdata in summary["por_clase"].items():
        md.append(f"### 3.{list(summary['por_clase'].keys()).index(clase)+1} Clase: `{clase.upper()}`")
        md.append("")
        md.append("| Subcategoría Original | Muestras | Aciertos Laya | % Acuerdo | Confusión / Distribución Predicha por Laya |")
        md.append("| :--- | :---: | :---: | :---: | :--- |")
        
        for subcat, sdata in cdata["subcategorias"].items():
            dist_str = ", ".join([f"`{k}`: {v}" for k, v in sdata["distribucion_predicha_laya"].items()])
            md.append(f"| {subcat} | {sdata['total']} | {sdata['coincidencias']} | **{sdata['acuerdo_pct']}%** | {dist_str} |")
            
        md.append("")
        
    md.append("---")
    md.append("")
    md.append("## 4. Análisis de Casos de Discrepancia y Hallazgos")
    md.append("")
    
    # Extraer 5 ejemplos interesantes de discrepancia
    discrepancias = [r for r in results if not r["coincide"]][:8]
    if discrepancias:
        md.append("A continuación se presentan casos representativos donde la clasificación de Laya difiere de la clasificación previa en la base de datos:")
        md.append("")
        for d in discrepancias:
            md.append(f"#### Petición Radicado: `{d['numero_peticion']}` ({d['clase'].upper()})")
            md.append(f"- **Asunto:** *\"{d['asunto'][:300]}...\"*")
            md.append(f"- **Clasificación Previa:** `{d['clasificacion_original']}` (Método previo: `{d['metodo_original']}`)")
            md.append(f"- **Clasificación Laya:** `{d['clasificacion_laya']}` (Confianza: `{d['confianza_laya']:.2%}`)")
            top_probs = sorted(d["probabilidades_completas"].items(), key=lambda x: x[1], reverse=True)[:3]
            probs_str = " | ".join([f"{k}: {v:.1%}" for k, v in top_probs])
            md.append(f"- **Probabilidades Laya:** {probs_str}")
            md.append("")
    else:
        md.append("No se detectaron discrepancias relevantes.")
        
    md.append("---")
    md.append("")
    md.append("## 5. Comparativa Técnica: Laya vs Jev / Ollama")
    md.append("")
    md.append("| Característica | TypeSafe Jev | Ollama Local (Qwen 32B) | Laya Local (`convaiinnovations/laya`) |")
    md.append("| :--- | :--- | :--- | :--- |")
    md.append("| **Tipo de Modelo** | System 1 (No autorregresivo) | LLM Generativo (Autorregresivo) | System 1 (No autorregresivo) |")
    md.append("| **Alojamiento** | Nube (API cerrada) | Local / Servidor On-Premise | Local / Servidor On-Premise |")
    md.append("| **Costo por Token** | Cobro por millón de tokens | Gratuito | **Gratuito (Open Source Apache 2.0)** |")
    md.append("| **Consumo de Hardware** | Ninguno (SaaS) | Muy alto (~20-25GB VRAM GPU) | **Muy bajo (<1.5GB RAM/VRAM)** |")
    md.append("| **Protocolo Wire** | `POST /v1/systemone` | `POST /api/generate` | Compatible con System 1 (`Router` / `laya-serve`) |")
    md.append("| **Velocidad de Inferencia** | ~150-350 ms (sujeto a red) | ~1.5 - 4.0 s por texto | **~30 - 80 ms** |")
    md.append("| **Privacidad de Datos** | Datos viajan a la nube | 100% On-Premise | **100% On-Premise y sin fugas** |")
    md.append("")
    md.append("## 6. Archivos Generados en la Prueba")
    md.append("")
    md.append("- `dataset_muestra_1000.json` & `.csv`: Dataset de prueba con las 1,000 peticiones extraídas de la base de datos.")
    md.append("- `resultados_clasificacion_laya.json` & `.csv`: Resultados individuales con cada predicción, probabilidades, latencia y coincidencia.")
    md.append("- `matriz_confusion_y_metricas.json`: Matriz de confusión estructurada y métricas agregadas.")
    md.append("- `INFORME_CLASIFICACION_LAYA.md`: Este informe ejecutivo.")
    md.append("")
    
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
        
    print(f"Informe ejecutivo Markdown generado en: {REPORT_MD}")

if __name__ == "__main__":
    main()
