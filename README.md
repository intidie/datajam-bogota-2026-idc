# 🏙️ Panel Distrital del Índice de Desviación Contractual (IDC)
> **Proyecto desarrollado para el DataJam Edición 3 – 2026**  
> **Organizado por:** Alcaldía Mayor de Bogotá D.C.  
> **Nombre del Equipo:** Proyecto Lazarus  
> **Integrantes:** Inti Olaya, Alan Cheyne, Jhojan Montaña  

---

## 📌 1. Descripción del Problema Abordado

En el marco de la gestión pública del Distrito Capital, la eficiencia y transparencia en la asignación del gasto público representan retos fundamentales para garantizar el desarrollo equitativo de la ciudad. El fenómeno urbano abordado en este proyecto es la **discrepancia espacial y temporal entre la planificación presupuestal y la ejecución de la contratación directa** en las 20 localidades de Bogotá D.C.

La contratación a nivel local en Bogotá (que se encarga de las vías de los barrios, los parques zonales, dotación de colegios y seguridad local) ha sufrido históricamente de altas tasas de desviación. Esto representa un problema crítico por cuatro razones fundamentales:

* **Violación del Principio de Planeación:** Una alta desviación demuestra que los "estudios previos" (la fase donde la alcaldía local planea qué va a hacer y cuánto cuesta) quedaron mal hechos. Si un contrato para arreglar una calle requiere tres prórrogas y una adición de dinero a los pocos meses de iniciar, significa que no se calcularon bien los materiales, las redes de acueducto subterráneas o los tiempos.
* **Foco y Riesgo de Corrupción:** Las adiciones contractuales son una de las zonas más grises de la contratación pública. Al modificar un contrato existente, se le entrega dinero directamente al mismo contratista sin tener que abrir una nueva licitación pública o concurso, lo que a veces se utiliza para desviar recursos públicos.
* **Ineficiencia y "Elefantes Blancos":** La desviación en tiempo se traduce en obras abandonadas o retrasadas durante años. Para la ciudadanía, esto significa calles rotas, polisombras que generan inseguridad en el barrio y parques inhabilitados.
* **Desgaste Administrativo y Presupuestal:** Los Fondos de Desarrollo Local tienen presupuestos limitados. Cuando el dinero debe usarse para cubrir los sobrecostos (adiciones) de obras mal planeadas del año anterior, la localidad se queda sin recursos para financiar nuevos proyectos sociales o de infraestructura.

Para diagnosticar y visualizar este fenómeno a nivel distrital, desarrollamos el **Índice de Desviación Contractual (IDC)**. Este indicador analítico cuantifica las variaciones críticas entre el `total_presupuesto_planeado` y el `total_contratado_directo`. A través de un enfoque cuantitativo y geoespacial, el modelo identifica patrones de riesgo contractual, concentración atípica de recursos y niveles de ejecución por localidad, permitiendo a tomadores de decisión y a la ciudadanía monitorear el desempeño del gasto distrital.

---

## 📊 2. Fuentes de Datos Utilizadas

Para el desarrollo de este ejercicio analítico, se utilizaron datos provenientes del **[Portal de Datos Abiertos de Bogotá](https://datosabiertos.bogota.gov.co/)**. Aunque inicialmente se exploraron rangos históricos más amplios, el análisis final se delimitó al periodo del **año 2022** utilizando los siguientes conjuntos de datos:

1. **Contratos Distritales (Contratistas):**  
   * Se utilizaron los cortes mensuales correspondientes a **septiembre, octubre y noviembre de 2022** (`contratistas-2022-09.csv`, `contratistas-2022-10.csv`, `contratistas-2022-11.csv`).

2. **Banco de Proveedores - Talento no Palanca:**  
   * De las bases exploradas entre septiembre y diciembre, se seleccionó como insumo final únicamente el archivo de **diciembre de 2022** (`tnp-diciembre.csv`).

3. **Proyección de Población por Localidad:**  
   * Se integró el archivo de proyecciones y retroproyecciones de población distrital 2005-2035 (`202503_localidad_proyeccion_retroproyeccion_poblacion_2005_2035.ods`) para permitir la normalización e interpretación territorial de los datos.

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
