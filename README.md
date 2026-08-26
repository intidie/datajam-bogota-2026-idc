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

El ejercicio analítico conecta directamente el problema de la **desviación y autonomía en la contratación pública local** con los datos abiertos oficiales a través de una metodología estructurada en cuatro fases:

```
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│  1. Ingesta y Limpieza  │ ──► │  2. Disociación FDL vs  │ ──► │   3. Cálculo IDC &      │ ──► │ 4. Análisis Exploratorio│
│  (Cortes independientes)│     │     Sector Central      │     │ Normalización Demográfica│     │    (PCA & Geoespacial) │
└─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘     └─────────────────────────┘
```

### 3.1. Ingesta y Tratamiento de Desafíos en Datos Abiertos (`data_sources.py`, `pipeline.py`)
- **Evitar Duplicidad por Cortes Acumulados:** Cada reporte mensual de Contratistas es un estado acumulado a esa fecha. El pipeline procesa **cortes mensuales independientes** (septiembre, octubre, noviembre y diciembre 2022) sin sumar meses entre sí, evitando inflar valores al duplicar contratos plurianuales o vigentes.
- **Normalización Textual Rígida:** Se convierten cadenas con diversas codificaciones (`CP850`, `Latin-1`, `UTF-8`) a texto plano sin tildes, caracteres especiales ni prefijos numéricos (`"01 USAQUÉN"` → `"USAQUEN"`), mapeándolos contra un catálogo estandarizado de las **20 localidades oficiales de Bogotá D.C.**
- **Saneamiento Numérico Financiero:** Limpieza automatizada de valores de dinero con formato mixto (convertidor de strings con símbolos de moneda `$`, puntos de millar y comas decimales a `float64`).

### 3.2. Disociación Territorial: Fondos Locales vs. Sector Central (`pipeline.py`)
- **Contratación Total (`total_contratado`):** Se agrupa la contratación del Distrito según la **localidad de domicilio del contratista** (única variable geográfica disponible en la fuente).
- **Contratación Directa Local (`total_contratado_directo`):** Se filtra el `Sector == 'Localidades'` y se aplica extracción de entidades (`extraer_localidad_de_entidad`) para identificar los recursos ejecutados específicamente por el **Fondo de Desarrollo Local (FDL)** de cada localidad.
- **Transparencia en Sesgos:** Las entidades del sector central (Salud, Educación, Movilidad, etc.) prestan servicio a nivel distrital y no poseen residencia de contratista única; por ello se procesan en una tabla independiente sin forzarlas arbitrariamente dentro de una localidad ajena.

### 3.3. Formulación del IDC y Normalización Poblacional (`pipeline.py`, `poblacion_data.py`)
- **Fórmula del Índice de Desviación Contractual (IDC):**

$$\text{IDC} = \min\left(1.0, \frac{\text{Total Contratado Directo (Fondo Local)}}{\text{Total Contratado (Todos los sectores)}}\right)$$

Un IDC cercano a 1.0 refleja una alta proporción de gasto canalizado a través del propio Fondo Local. Para evitar que casos extremos distorsionen los gráficos, el valor se acota a 1.0, preservando la versión sin acotar en `idc_raw`.
- **Tratamiento de Outliers (Sumapaz):** Debido a su carácter eminentemente rural y baja densidad de contratistas domiciliados, Sumapaz genera un IDC matemático atípico, por lo cual se categoriza como *outlier suplementario* para no sesgar las comparativas urbanas.
- **Normalización Demográfica (Per Cápita):** Con base en el censo y proyecciones de población distrital 2005–2035 (SDP), se derivan métricas por cada 1.000 habitantes (`contratos_por_1000_hab`, `contratado_per_capita`, `postulantes_tnp_por_1000_hab`), garantizando comparaciones equitativas entre localidades de gran tamaño (Kennedy, Suba) y pequeñas (La Candelaria).

### 3.4. Análisis Multivariado y Visualización (`charts.py`, `app.py`)
- **Reducción de Dimensionalidad (PCA):** Estandarización (`StandardScaler`) y Análisis de Componentes Principales (`PCA(n_components=2)`) con `scikit-learn` para identificar clústeres de localidades con patrones similares de contratación y vectores de carga (*loadings*).
- **Análisis Geoespacial Interactivo:** Integración de mapas de coropletas (polígonos cartográficos oficiales SDP/IDECA) y mapas de burbujas en centroides para evaluar diferencias territoriales (p. ej. disparidades en el eje Norte vs. Sur).

---

## 🛠️ 4. Instrucciones de Ejecución

### Prerrequisitos
- Python **3.10+** (Recomendado: Python 3.11)
- Git

### ⚡ Ejecución Rápida (3 Pasos)

```bash
# 1. Clonar el repositorio e ingresar a la carpeta
git clone https://github.com/intidie/datajam-bogota-2026-idc.git && cd datajam-bogota-2026-idc

# 2. Instalar dependencias requeridas
pip install -r requirements.txt

# 3. Lanzar la aplicación interactiva
streamlit run app.py
```

La interfaz se abrirá automáticamente en tu navegador web en `http://localhost:8501`.

*(Opcional: Si deseas guardar o sincronizar con Supabase, configura las credenciales `SUPABASE_URL` y `SUPABASE_KEY` en tu archivo `.env` o en `st.secrets`).*

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
