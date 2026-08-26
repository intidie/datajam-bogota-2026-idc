# 🏙️ Panel Distrital del Índice de Desviación Contractual (IDC)
> **Proyecto desarrollado para el DataJam Edición 3 – 2026**  
> **Organizado por:** Alcaldía Mayor de Bogotá D.C.  
> **Nombre del Equipo:** Proyecto Lazarus  
> **Integrantes:** Inti Olaya, Alan Cheyne, Jhojan Montaña  

---

## 📌 1. Descripción del Problema Abordado

En el marco de la gestión pública del Distrito Capital, la eficiencia y transparencia en la asignación del gasto público representan retos fundamentales para garantizar el desarrollo equitativo de la ciudad. El fenómeno urbano abordado en este proyecto es la **discrepancia espacial y temporal entre la planificación presupuestal y la ejecución de la contratación directa** en las 20 localidades de Bogotá D.C.

Para diagnosticar y visualizar este fenómeno a nivel distrital, desarrollamos el **Índice de Desviación Contractual (IDC)**. Este indicador analítico cuantifica las variaciones críticas entre el `total_presupuesto_planeado` y el `total_contratado_directo`. A través de un enfoque cuantitativo y geoespacial, el modelo identifica patrones de riesgo contractual, concentración atípica de recursos y niveles de ejecución por localidad, permitiendo a tomadores de decisión y a la ciudadanía monitorear el desempeño del gasto distrital.

---

## 📊 2. Fuentes de Datos Utilizadas

El análisis se alimenta de conjuntos de datos públicos oficiales provenientes del **[Portal de Datos Abiertos de Bogotá](https://datosabiertos.bogota.gov.co/)** (integrados a través de SECOP y fuentes distritales) y alojados en **Supabase**:

1. **Conjunto de Datos de Contratación Pública Distrital (SECOP)**  
   * **Descripción:** Contiene el registro detallado de los contratos firmados por entidades distritales, modalidades de contratación y montos ejecutados.  
   * **Aporte al Análisis:** Proporciona los datos del `total_contratado_directo` y la vigencia fiscal (`year`) para el cálculo del IDC.

2. **Conjunto de Datos de Presupuesto Anual por Localidad**  
   * **Descripción:** Información presupuestal desagregada por plan de desarrollo local y asignación previa de recursos.  
   * **Aporte al Análisis:** Proporciona los valores de `total_presupuesto_planeado`, sirviendo como línea base de comparación frente a la ejecución real.

3. **Conjunto de Datos Geoespaciales y Demográficos de Bogotá (Cartografía Oficial)**  
   * **Descripción:** Capa cartográfica con delimitaciones de localidades, coordenadas de referencia (`latitud`, `longitud`) y proyecciones poblacionales.  
   * **Aporte al Análisis:** Permite la normalización del IDC en función de la población local y la generación de capas de mapas de calor interactivos en PyDeck.

---

## 🔬 3. Metodología General

El desarrollo del producto analítico siguió un pipeline estructurado de ciencia de datos:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   1. Extracción  │ ──► │  2. Limpieza e   │ ──► │  3. Modelado e   │ ──► │ 4. Visualización │
│  (Supabase/APIs) │     │  Integración     │     │   Cálculo IDC    │     │   (Streamlit UI) │
└──────────────────┘     └──────────────────┘     └──────────────────┘     └──────────────────┘
```

1. **Extracción y Persistencia (`database/connection.py`, `supabase_utils.py`):**  
   Conexión optimizada a Supabase con mecanismos de almacenamiento en caché (`st.cache_data` con TTL) para optimizar consultas de alto tráfico.

2. **Limpieza e Integración (`pipeline.py`, `data_sources.py`):**  
   Normalización de nombres de localidades, imputación de valores faltantes, conversión de tipos numéricos y filtrado de coordenadas geográficas válidas.

3. **Modelado y Análisis (`geo_data.py`, `poblacion_data.py`, `scikit-learn`):**  
   Cálculo numérico del IDC, ponderación poblacional por localidad y segmentación de riesgo presupuestal.

4. **Visualización Interactiva (`app.py`, `components/`, `charts.py`):**  
   Despliegue de un tablero de control en Streamlit equipado con filtros por vigencia y localidad, gráficos de Plotly y mapas de calor espaciales interactivos en PyDeck.

---

## 🛠️ 4. Instrucciones de Ejecución

Sigue este paso a paso para reproducir la solución en tu entorno local.

### Prerrequisitos
- Python **3.10+** (Recomendado: Python 3.11)
- Git

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/intidie/datajam-bogota-2026-idc.git
cd datajam-bogota-2026-idc
```

### Paso 2: Crear y Activar el Entorno Virtual
* **En Linux/macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
* **En Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```

### Paso 3: Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 4: Configurar Variables de Entorno (Credenciales de Supabase)
Crea un archivo `.env` en la raíz del proyecto basándote en la plantilla `.env.example`:
```env
SUPABASE_URL=https://tu-proyecto-id.supabase.co
SUPABASE_KEY=tu-clave-anon-de-supabase
```

### Paso 5: Ejecutar la Aplicación / Scripts Analíticos
* **Para ejecutar el tablero de control interactivo (Streamlit):**
  ```bash
  streamlit run app.py
  ```
  La interfaz se abrirá automáticamente en tu navegador web en `http://localhost:8501`.

* **Para ejecutar el pipeline de datos independiente:**
  ```bash
  python pipeline.py
  ```

---

## 📁 5. Estructura del Repositorio

```text
datajam-bogota-2026-idc/
├── .streamlit/           # Configuración visual del tema del tablero Streamlit
├── components/           # Componentes modulares de interfaz de usuario
│   ├── __init__.py
│   ├── map.py            # Renderizado del mapa de calor espacial PyDeck
│   └── sidebar.py        # Barra lateral y controles de filtrado dinámico
├── data/                 # Conjuntos de datos locales y muestras de respaldo
│   ├── processed/        # Datos transformados e integrados para el modelo
│   └── raw/              # Datos originales descargados del Portal de Datos Abiertos
├── database/             # Capa de persistencia y abstracción de la base de datos
│   ├── __init__.py
│   └── connection.py     # Conector singleton a Supabase con caché
├── docs/                 # Documentación técnica, metodológica y anexos
├── notebooks/            # Notebooks de exploración inicial (Jupyter / R)
├── outputs/              # Gráficos exportados, reportes y métricas generadas
├── scripts/              # Scripts auxiliares de automatización
├── app.py                # Punto de entrada y orquestador principal del tablero
├── charts.py             # Generación de componentes de gráficos interactivos (Plotly)
├── data_sources.py       # Conectores para fuentes de Datos Abiertos de Bogotá
├── geo_data.py           # Procesamiento de datos geográficos y centroides
├── pipeline.py           # Pipeline ETL para procesamiento del IDC
├── poblacion_data.py     # Carga y procesamiento de datos demográficos
├── supabase_utils.py     # Utilidades de consulta y ejecución en Supabase
├── requirements.txt      # Archivo de dependencias del proyecto
└── README.md             # Documentación principal del repositorio
```

---

> 💡 **Nota:** Proyecto elaborado en el marco del **DataJam Edición 3 – 2026** de Bogotá D.C.
