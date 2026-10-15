# Informe Técnico: Evaluación y Reclasificación con Laya (System 1)

> **Objetivo:** Evaluar el motor de decisiones de código abierto **Laya** (`convaiinnovations/laya` - checkpoint multilingüe) como alternativa local a Jev / Ollama sobre una muestra estratificada de **1,000 peticiones PQRS** de la base de datos sin alterar ningún dato existente.

## 1. Resumen Ejecutivo de Desempeño

| Métrica | Valor Obtenido |
| :--- | :--- |
| **Modelo Evaluado** | `convaiinnovations/laya` (multilingual) |
| **Total de Muestras Evaluadas** | **1000** peticiones reales |
| **Tasa de Acuerdo Global** | **50.0%** (500/1000) |
| **Tiempo Total de Ejecución** | **23.09 s** |
| **Throughput (Rendimiento)** | **43.3 req/s** (Inferencia local) |
| **Latencia Promedio por Petición** | **23.09 ms** |
| **Nivel de Confianza Promedio** | **66.83%** |

---

## 2. Resultados Consolidados por Clase Temática

| Clase | Total Muestras | Coincidencias | % Acuerdo | Confianza Promedio | Latencia Promedio |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **RUIDO** | 350 | 62 | **17.71%** | 44.85% | 31.48 ms |
| **SALUD** | 350 | 138 | **39.43%** | 60.36% | 18.71 ms |
| **MALTRATO_ANIMAL** | 300 | 300 | **100.0%** | 100.00% | 18.36 ms |

---

## 3. Desglose Detallado por Subcategoría

### 3.1 Clase: `RUIDO`

| Subcategoría Original | Muestras | Aciertos Laya | % Acuerdo | Confusión / Distribución Predicha por Laya |
| :--- | :---: | :---: | :---: | :--- |
| Ruido por actividades lúdicas | 35 | 33 | **94.29%** | `Ruido por actividades lúdicas`: 33, `Ruido por ventas ambulantes`: 1, `Ruido por industria`: 1 |
| Ruido por comercio (comercio - bar, comercio - gastrobar) | 35 | 1 | **2.86%** | `Ruido por actividades lúdicas`: 31, `Ruido por ventas ambulantes`: 3, `Ruido por comercio (comercio - bar, comercio - gastrobar)`: 1 |
| Ruido por construcción | 35 | 3 | **8.57%** | `Ruido por actividades lúdicas`: 27, `Ruido por ventas ambulantes`: 3, `Ruido por construcción`: 3, `Ruido por tráfico vehicular`: 1, `Ruido por servicios`: 1 |
| Ruido por industria | 35 | 5 | **14.29%** | `Ruido por actividades lúdicas`: 25, `Ruido por ventas ambulantes`: 3, `Ruido por construcción`: 1, `Ruido por industria`: 5, `Ruido por comercio (comercio - bar, comercio - gastrobar)`: 1 |
| Ruido por servicios | 35 | 0 | **0.0%** | `Ruido por actividades lúdicas`: 29, `Ruido por ventas ambulantes`: 3, `Ruido por construcción`: 1, `Ruido sin especificar`: 2 |
| Ruido por tráfico aéreo | 23 | 6 | **26.09%** | `Ruido por actividades lúdicas`: 13, `Ruido por ventas ambulantes`: 3, `Ruido por tráfico aéreo`: 6, `Ruido por construcción`: 1 |
| Ruido por tráfico vehicular | 35 | 1 | **2.86%** | `Ruido por actividades lúdicas`: 26, `Ruido por vecinos`: 1, `Ruido por industria`: 1, `Ruido sin especificar`: 2, `Ruido por ventas ambulantes`: 3, `Ruido por construcción`: 1, `Ruido por tráfico vehicular`: 1 |
| Ruido por vecinos | 35 | 3 | **8.57%** | `Ruido por actividades lúdicas`: 29, `Ruido por construcción`: 1, `Ruido por vecinos`: 3, `Ruido por comercio (comercio - bar, comercio - gastrobar)`: 2 |
| Ruido por ventas ambulantes | 35 | 9 | **25.71%** | `Ruido por ventas ambulantes`: 9, `Ruido por actividades lúdicas`: 25, `Ruido por construcción`: 1 |
| Ruido sin especificar | 47 | 1 | **2.13%** | `Ruido por actividades lúdicas`: 40, `Ruido por construcción`: 1, `Ruido por comercio (comercio - bar, comercio - gastrobar)`: 2, `Ruido por tráfico vehicular`: 1, `Ruido sin especificar`: 1, `Ruido por tráfico aéreo`: 1, `Ruido por vecinos`: 1 |

### 3.2 Clase: `SALUD`

| Subcategoría Original | Muestras | Aciertos Laya | % Acuerdo | Confusión / Distribución Predicha por Laya |
| :--- | :---: | :---: | :---: | :--- |
| Fallas en la prestación del servicio/humanización del servicio | 70 | 56 | **80.0%** | `Fallas en la prestación del servicio/humanización del servicio`: 56, `Otros`: 5, `Negación de Medicamentos`: 5, `Negación de citas médicas`: 4 |
| Negación de citas médicas | 70 | 32 | **45.71%** | `Fallas en la prestación del servicio/humanización del servicio`: 30, `Negación de citas médicas`: 32, `Otros`: 2, `Negación de Medicamentos`: 6 |
| Negación de Medicamentos | 70 | 32 | **45.71%** | `Fallas en la prestación del servicio/humanización del servicio`: 32, `Negación de Medicamentos`: 32, `Otros`: 2, `Negación de citas médicas`: 4 |
| Negación de procedimientos | 70 | 2 | **2.86%** | `Fallas en la prestación del servicio/humanización del servicio`: 42, `Otros`: 16, `Negación de Medicamentos`: 6, `Negación de procedimientos`: 2, `Negación de citas médicas`: 4 |
| Otros | 70 | 16 | **22.86%** | `Fallas en la prestación del servicio/humanización del servicio`: 46, `Otros`: 16, `Negación de citas médicas`: 2, `Negación de Medicamentos`: 6 |

### 3.3 Clase: `MALTRATO_ANIMAL`

| Subcategoría Original | Muestras | Aciertos Laya | % Acuerdo | Confusión / Distribución Predicha por Laya |
| :--- | :---: | :---: | :---: | :--- |
| Maltrato Animal | 300 | 300 | **100.0%** | `Maltrato Animal`: 300 |

---

## 4. Análisis de Casos de Discrepancia y Hallazgos

A continuación se presentan casos representativos donde la clasificación de Laya difiere de la clasificación previa en la base de datos:

#### Petición Radicado: `5496862026` (RUIDO)
- **Asunto:** *"EN MI CALLE (CALLE 66 ENTRE CARRERAS 10 Y 11 )  CHAPINERO. TENEMOS UNA PROBLEMATICA POR INVASION DEL ESPACIO PUBLICO  TRAFICO  ALTOS NIVELES DE RUIDO POR VOCEADORES Y VENDEDORES CON MEGAFONOS  PROCESAMIENTO DE COMIDAS EN LA CALLE  TAPONAMIENTO CON VEHICULOS DE LOS INGRESOS. A LOS GARAJES  BASURAS  E..."*
- **Clasificación Previa:** `Ruido por actividades lúdicas` (Método previo: `IA`)
- **Clasificación Laya:** `Ruido por ventas ambulantes` (Confianza: `28.70%`)
- **Probabilidades Laya:** Ruido por ventas ambulantes: 28.7% | Ruido por actividades lúdicas: 25.7% | Ruido por comercio (comercio - bar, comercio - gastrobar): 6.1%

#### Petición Radicado: `5954642026` (RUIDO)
- **Asunto:** *"BOGOTA D.C.  24 DE AGOSTO DE 2026 SENORES  ALCALDIA LOCAL DE CHAPINERO INSPECCION 2 C DISTRITAL DE CONVIVENCIA Y PAZ SECRETARIA DISTRITAL DE AMBIENTE CIUDAD   ASUNTO  SOLICITUD DE INTERVENCION URGENTE  VERIFICACION Y APLICACION DE MEDIDAS CORRECTIVAS POR CONTAMINACION AUDITIVA / INOBSERVANCIA DEL AR..."*
- **Clasificación Previa:** `Ruido por actividades lúdicas` (Método previo: `IA`)
- **Clasificación Laya:** `Ruido por industria` (Confianza: `18.16%`)
- **Probabilidades Laya:** Ruido por industria: 18.2% | Ruido por construcción: 14.9% | Ruido por comercio (comercio - bar, comercio - gastrobar): 13.2%

#### Petición Radicado: `3957492025` (RUIDO)
- **Asunto:** *"QUEJA Y DENUNCIA CONTRA EL ESTABLECIMIENTO SALON DE EVENTOS Y RECEPCIONES GRAN MUELLE CALLE 65 F SUR 80 C 40 POR MUSICA A ALTO VOLUMEN Y EXCESO DE RUIDO TODOS LOS SABADOS Y DOMINGOS CUANDO EL LUNES ES FESTIVO HASTA ALTAS HORAS DE LA NOCHE. EL EXCESO DE R..."*
- **Clasificación Previa:** `Ruido por comercio (comercio - bar, comercio - gastrobar)` (Método previo: `None`)
- **Clasificación Laya:** `Ruido por actividades lúdicas` (Confianza: `63.04%`)
- **Probabilidades Laya:** Ruido por actividades lúdicas: 63.0% | Ruido por tráfico vehicular: 6.5% | Ruido sin especificar: 5.8%

#### Petición Radicado: `3913092025` (RUIDO)
- **Asunto:** *"REPORTE DE QUEJA POR RUIDO EXCESIVO EN ESTABLECIMIENTO DE COMERCIO EN ZONA RESIDENCIAL DEL BARRIO COUNTRY SUR LOCALIDAD RAFAEL URIBE. EL ESTABLECIMIENTO SE DENOMINA SUPERTIENDA COUNTRY SUR Y EL EXCESO DE MUSICA ES DE DOMINGO A DOMINGO DE 11 00 AM A 11 50..."*
- **Clasificación Previa:** `Ruido por comercio (comercio - bar, comercio - gastrobar)` (Método previo: `None`)
- **Clasificación Laya:** `Ruido por actividades lúdicas` (Confianza: `64.02%`)
- **Probabilidades Laya:** Ruido por actividades lúdicas: 64.0% | Ruido por comercio (comercio - bar, comercio - gastrobar): 13.0% | Ruido por ventas ambulantes: 3.3%

#### Petición Radicado: `3425372025` (RUIDO)
- **Asunto:** *"SE SIGUE PRESENTANDO EXCESO DE RUIDO Y MUSICA A ALTO VOLUMEN EN EL ESTABLECIMIENTO EVENTOS Y RECEPCIONES CALLE 65 F SUR 80 C 40 TODOS LOS SABADOS DE 10PM A 3AM. NOS HAN DADO RESPUESTA DE LA ALCALDIA QUE HAN REALIZADO JORNADAS DE SENSIBILIZACION  PERO EST..."*
- **Clasificación Previa:** `Ruido por comercio (comercio - bar, comercio - gastrobar)` (Método previo: `None`)
- **Clasificación Laya:** `Ruido por actividades lúdicas` (Confianza: `45.64%`)
- **Probabilidades Laya:** Ruido por actividades lúdicas: 45.6% | Ruido por tráfico aéreo: 11.0% | Ruido por ventas ambulantes: 7.3%

#### Petición Radicado: `2618742025` (RUIDO)
- **Asunto:** *"DISCOTECAS UBICADAS EN CASAS LAS CUALES GENERAN MUCHISIMO RUIDO DEDIBIDO A SUS EQUIPOS DE AUDIO Y BOCINA GRANDES  ALGUNOS LUGARES SON TRABAJADOS LOS 7 DIAS DE LA SEMANA HASTA ALTAS HORAS DE LA MAGRUGADA EN REITERADAS OCASIONES HASTA A PUERTAS CERRADAAS A..."*
- **Clasificación Previa:** `Ruido por comercio (comercio - bar, comercio - gastrobar)` (Método previo: `None`)
- **Clasificación Laya:** `Ruido por ventas ambulantes` (Confianza: `19.59%`)
- **Probabilidades Laya:** Ruido por ventas ambulantes: 19.6% | Ruido por industria: 14.3% | Ruido por construcción: 12.4%

#### Petición Radicado: `4660502025` (RUIDO)
- **Asunto:** *"BUENAS TARDES  DESEO ENTABLAR UNA PETICION DE CIERRE ESTABLECIMIENTO  POR EXCESO DE RUIDO Y DE DECIBELES EN ZONA RESIDENCIAL  ESTAMOS CANSADOS DE LLAMAR A LA POLICIA Y ACUDIR A LA ALCALDIA DE LA ZONA DA RAFAEL URIBE URIBE  DONDE SIEMPRE NOS RESPONDEN LO..."*
- **Clasificación Previa:** `Ruido por comercio (comercio - bar, comercio - gastrobar)` (Método previo: `None`)
- **Clasificación Laya:** `Ruido por actividades lúdicas` (Confianza: `42.43%`)
- **Probabilidades Laya:** Ruido por actividades lúdicas: 42.4% | Ruido por ventas ambulantes: 12.4% | Ruido sin especificar: 7.5%

#### Petición Radicado: `3353812026` (RUIDO)
- **Asunto:** *"DERECHO DE PETICION GENERAL Y SOLICITUD URGENTE DE INTERVENCION ADMINISTRATIVA POR AFECTACION A LA TRANQUILIDAD  SALUD Y DERECHO AL DESCANSO DE LA COMUNIDAD BOGOTA D.C.  10 DE MAYO DE 2026 SENORES INSPECCION DE POLICIA / ALCALDIA LOCAL DE SUBA / SECRETARIA DISTRITAL DE GOBIERNO BOGOTA D.C. REFERENCI..."*
- **Clasificación Previa:** `Ruido por comercio (comercio - bar, comercio - gastrobar)` (Método previo: `IA`)
- **Clasificación Laya:** `Ruido por actividades lúdicas` (Confianza: `45.78%`)
- **Probabilidades Laya:** Ruido por actividades lúdicas: 45.8% | Ruido por construcción: 7.6% | Ruido por industria: 7.0%

---

## 5. Comparativa Técnica: Laya vs Jev / Ollama

| Característica | TypeSafe Jev | Ollama Local (Qwen 32B) | Laya Local (`convaiinnovations/laya`) |
| :--- | :--- | :--- | :--- |
| **Tipo de Modelo** | System 1 (No autorregresivo) | LLM Generativo (Autorregresivo) | System 1 (No autorregresivo) |
| **Alojamiento** | Nube (API cerrada) | Local / Servidor On-Premise | Local / Servidor On-Premise |
| **Costo por Token** | Cobro por millón de tokens | Gratuito | **Gratuito (Open Source Apache 2.0)** |
| **Consumo de Hardware** | Ninguno (SaaS) | Muy alto (~20-25GB VRAM GPU) | **Muy bajo (<1.5GB RAM/VRAM)** |
| **Protocolo Wire** | `POST /v1/systemone` | `POST /api/generate` | Compatible con System 1 (`Router` / `laya-serve`) |
| **Velocidad de Inferencia** | ~150-350 ms (sujeto a red) | ~1.5 - 4.0 s por texto | **~30 - 80 ms** |
| **Privacidad de Datos** | Datos viajan a la nube | 100% On-Premise | **100% On-Premise y sin fugas** |

## 6. Archivos Generados en la Prueba

- `dataset_muestra_1000.json` & `.csv`: Dataset de prueba con las 1,000 peticiones extraídas de la base de datos.
- `resultados_clasificacion_laya.json` & `.csv`: Resultados individuales con cada predicción, probabilidades, latencia y coincidencia.
- `matriz_confusion_y_metricas.json`: Matriz de confusión estructurada y métricas agregadas.
- `INFORME_CLASIFICACION_LAYA.md`: Este informe ejecutivo.
