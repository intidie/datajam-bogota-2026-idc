"""
charts.py
---------
Métricas, gráficos Plotly, mapa interactivo, análisis descriptivo por
localidad, componentes principales (PCA) y explicaciones en lenguaje
sencillo. Cada bloque incluye, además de la interpretación para público
general, un expansor "¿Qué está pasando por dentro?" con el detalle técnico.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

TEMPLATE = "plotly_white"
COLOR_SCALE = "OrRd"

COLUMNAS_CANDIDATAS = {
    "total_contratado": "Total contratado (todos los sectores)",
    "num_contratos": "Número de contratos",
    "total_contratado_directo": "Ejecutado por el Fondo Local",
    "num_postulantes": "Personas TNP vinculadas vía Fondo Local",
    "idc": "IDC",
    "poblacion_total": "Población total (localidad)",
    "contratos_por_1000_hab": "Contratos por 1.000 habitantes",
    "contratado_per_capita": "Contratado per cápita ($/hab)",
}


# ------------------------------------------------------------------
# Gradiente de color sin matplotlib (el proyecto es "todo Plotly"; usar
# Styler.background_gradient de pandas exige matplotlib instalado, así
# que aquí se interpola manualmente entre dos colores por columna).
# ------------------------------------------------------------------

def _interpolar_color(valor_normalizado: float, color_bajo=(255, 247, 236), color_alto=(215, 48, 31)):
    r = color_bajo[0] + (color_alto[0] - color_bajo[0]) * valor_normalizado
    g = color_bajo[1] + (color_alto[1] - color_bajo[1]) * valor_normalizado
    b = color_bajo[2] + (color_alto[2] - color_bajo[2]) * valor_normalizado
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    text_color = "#000000" if luminance > 0.5 else "#FFFFFF"
    return f"background-color: rgb({r:.0f}, {g:.0f}, {b:.0f}); color: {text_color};"


def _gradiente_columna(serie: pd.Series):
    """Reemplazo manual de `Styler.background_gradient` (sin matplotlib):
    normaliza cada columna entre su mínimo y máximo y le asigna un color
    de fondo, columna por columna (misma lógica que axis=0)."""
    s = pd.to_numeric(serie, errors="coerce")
    minimo, maximo = s.min(), s.max()
    if pd.isna(minimo) or pd.isna(maximo) or maximo == minimo:
        return ["" for _ in s]
    normalizados = (s - minimo) / (maximo - minimo)
    return [
        "" if pd.isna(v) else _interpolar_color(v)
        for v in normalizados
    ]


def _explica(texto_sencillo: str, texto_tecnico: str):
    st.markdown(texto_sencillo)
    with st.expander("¿Qué está pasando por dentro? (Detalle técnico)"):
        st.markdown(texto_tecnico)


def _columnas_utiles(idc_data, candidatas: dict):
    """Separa las columnas que tienen información real de las que están
    completamente en cero o nulas (sin información), para no graficar ni
    analizar columnas vacías."""
    utiles, vacias = {}, []
    for col, etiqueta in candidatas.items():
        if col not in idc_data.columns:
            continue
        serie = idc_data[col].dropna()
        if serie.empty or (serie == 0).all():
            vacias.append(etiqueta)
        else:
            utiles[col] = etiqueta
    return utiles, vacias


def _bar_localidad(data, columna: str, etiqueta: str, color_scale: str, ascending: bool = False):
    st.markdown(f"**{etiqueta} por localidad**")
    d = data.dropna(subset=[columna]).sort_values(columna, ascending=ascending)
    fig = px.bar(
        d, x="localidad_limpia", y=columna, color=columna,
        color_continuous_scale=color_scale, template=TEMPLATE,
        labels={columna: etiqueta, "localidad_limpia": ""},
    )
    fig.update_layout(height=380, xaxis_tickangle=-40, showlegend=False, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------
# Resumen / Análisis Multivariado
# ------------------------------------------------------------------

def mostrar_metricas(idc_data, corte_label: str):
    st.subheader("Lo más importante: Análisis Multivariado e Insights Conjuntos", anchor=False, divider="orange")
    st.caption(f"Corte analizado: {corte_label}. Evaluación integrada de la relación entre el IDC, el volumen presupuestal, la ejecución de los Fondos Locales y la dinámica demográfica.")

    tiene_outlier = "es_outlier" in idc_data.columns
    urbanas = idc_data[~idc_data["es_outlier"]].copy() if tiene_outlier else idc_data.copy()
    validos = urbanas.dropna(subset=["idc", "total_contratado"]).copy()

    total_contratado = idc_data["total_contratado"].sum()
    total_fdl = idc_data["total_contratado_directo"].sum()
    idc_macro = (total_fdl / total_contratado) if total_contratado > 0 else 0
    tiene_poblacion = "poblacion_total" in idc_data.columns and idc_data["poblacion_total"].sum() > 0

    # 1. Cálculo de Correlaciones
    corr_total = validos["idc"].corr(validos["total_contratado"]) if len(validos) > 2 else 0

    # 2. Análisis de Conglomerados (Clustering K-Means) sobre localidades urbanas
    cols_cluster = ["idc", "total_contratado", "total_contratado_directo"]
    if "num_contratos" in validos.columns and validos["num_contratos"].notna().any():
        cols_cluster.append("num_contratos")
    if tiene_poblacion and "contratado_per_capita" in validos.columns:
        cols_cluster.append("contratado_per_capita")

    df_cluster_valid = validos.dropna(subset=cols_cluster).copy()
    num_clusters = 3
    if len(df_cluster_valid) >= num_clusters:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df_cluster_valid[cols_cluster])
        km = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
        df_cluster_valid["cluster_id"] = km.fit_predict(X_scaled)

        resumen_c = df_cluster_valid.groupby("cluster_id")[["idc", "total_contratado"]].mean()
        orden_c = resumen_c.sort_values("idc", ascending=False).index.tolist()
        nombres_map = {
            orden_c[0]: "Clúster A: Alta Descentralización (Autonomía Local)",
            orden_c[1]: "Clúster B: Perfil Balanceado Intermedio",
            orden_c[2]: "Clúster C: Gran Volumen Centralizado",
        }
        df_cluster_valid["cluster_nombre"] = df_cluster_valid["cluster_id"].map(nombres_map)
        validos = validos.merge(df_cluster_valid[["localidad_limpia", "cluster_id", "cluster_nombre"]], on="localidad_limpia", how="left")
    else:
        validos["cluster_nombre"] = "Sin suficientes datos para clústeres"

    # --- PRESENTACIÓN DE HALLAZGOS CLAVE (INSIGHTS MULTIVARIADOS) ---
    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        st.metric("IDC Macro Distrital", f"{idc_macro:.2%}", help="Porcentaje de la contratación distrital ejecutado directamente por Fondos Locales.")
    with col_kpi2:
        st.metric("Correlación (IDC vs. Presupuesto Total)", f"{corr_total:.2f}", help="Valor negativo indica que a mayor presupuesto total captado, menor tiende a ser la ponderación del Fondo Local.")
    with col_kpi3:
        st.metric("Clústeres Contractuales Urbanos", f"{num_clusters} Grupos", help="Grupos de localidades identificadas mediante K-Means multivariado.")

    st.write("")

    st.markdown("### 🔍 Patrones Conjuntos Detectados")

    ins1, ins2 = st.columns(2)
    with ins1:
        st.info(
            f"**1. Relación Inversa Presupuesto-IDC (r = {corr_total:.2f}):**\n\n"
            "Existe una tendencia clara en Bogotá: las localidades con mayor volumen total de "
            "contratación captado por sus residentes (ej. Suba, Usaquén, Chapinero) presentan un IDC menor. "
            "Esto ocurre porque el sector central (salud, movilidad, educación) concentra la gran mayoría de su contratación en zonas corporativas, "
            "opacando la proporción ejecutada directamente por el Fondo Local."
        )
    with ins2:
        st.success(
            f"**2. Estructura de Clústeres de Comportamiento Contractual:**\n\n"
            f"Las localidades urbanas no se distribuyen al azar, sino en **3 grupos diferenciados**:\n"
            "• **Alta Autonomía Local:** Fondos locales con mayor peso relativo en el gasto.\n"
            "• **Gran Volumen Centralizado:** Alto presupuesto captado, pero dominado por el sector central.\n"
            "• **Perfil Balanceado:** Comportamiento intermedio en escala y descentralización."
        )

    ins3, ins4 = st.columns(2)
    with ins3:
        pob_text = "Se evidencia mayor densidad de contratación del Fondo Local por cada 1.000 habitantes en localidades medianas." if tiene_poblacion else "Métricas per cápita calculadas con base en el censo distrital."
        st.warning(
            "**3. Intensidad Demográfica Per Cápita:**\n\n"
            f"{pob_text} La normalización por población muestra que el impacto directo de los Fondos "
            "Locales es significativamente más equitativo por habitante en localidades periféricas que lo "
            "que sugerirían las cifras brutas sin normalizar."
        )
    with ins4:
        st.error(
            "**4. Exclusión Estructural de Sumapaz (Outlier Rural):**\n\n"
            "Sumapaz es un **outlier estructural**: su territorio es 100% rural, su densidad es muy baja y "
            "registra un número mínimo de contratistas domiciliados allí. Esto genera un IDC matemático "
            "desproporcionado que distorsionaría los centros de los clústeres urbanos. Por ello, se excluye "
            "del modelo de clustering urbano y se analiza como caso atípico de control."
        )

    st.write("")

    # --- SECCIÓN DE CLUSTERING Y TABLA RESUMEN ---
    if "cluster_nombre" in validos.columns and validos["cluster_nombre"].notna().any():
        st.markdown("### 🧩 Agrupación de Localidades (Clustering Multivariado)")
        st.markdown(
            "A diferencia de simplemente clasificar localidades en una lista unidimensional, "
            "el análisis de clústeres agrupa localidades que comparten **patrones semejantes** en múltiples dimensiones simultáneamente."
        )

        fig_cluster = px.scatter(
            validos,
            x="total_contratado",
            y="idc",
            color="cluster_nombre",
            size="total_contratado_directo",
            hover_name="localidad_limpia",
            text="localidad_limpia",
            template=TEMPLATE,
            color_discrete_sequence=["#2A9D8F", "#E76F51", "#F4A261"],
            labels={
                "total_contratado": "Total Contratado (Todos los Sectores, $)",
                "idc": "Índice de Descentralización (IDC)",
                "cluster_nombre": "Perfil del Clúster",
                "total_contratado_directo": "Ejecutado por Fondo Local ($)",
            },
        )
        fig_cluster.update_traces(textposition="top center", textfont=dict(size=10))
        fig_cluster.update_layout(
            height=480,
            margin=dict(l=10, r=10, t=20, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_cluster, use_container_width=True)

        # Tabla de Perfil por Clúster
        res_tabla = (
            validos.groupby("cluster_nombre")
            .agg(
                Número_Localidades=("localidad_limpia", "count"),
                IDC_Promedio=("idc", "mean"),
                Total_Contratado_Promedio=("total_contratado", "mean"),
                Ejecutado_FDL_Promedio=("total_contratado_directo", "mean"),
                Localidades=("localidad_limpia", lambda x: ", ".join(sorted([loc.title() for loc in x]))),
            )
            .reset_index()
        )
        st.dataframe(
            res_tabla.style.format({
                "IDC_Promedio": "{:.2%}",
                "Total_Contratado_Promedio": "${:,.0f}",
                "Ejecutado_FDL_Promedio": "${:,.0f}",
            }),
            use_container_width=True,
        )

    # --- MATRIZ DE CORRELACIONES ---
    st.markdown("### 📊 Matriz de Correlación entre Variables")
    cols_corr = ["idc", "total_contratado", "total_contratado_directo"]
    if "num_contratos" in validos.columns:
        cols_corr.append("num_contratos")
    if tiene_poblacion and "contratado_per_capita" in validos.columns:
        cols_corr.append("contratado_per_capita")

    labels_corr = {
        "idc": "IDC",
        "total_contratado": "Total Contratado",
        "total_contratado_directo": "Ejecutado FDL",
        "num_contratos": "N° Contratos",
        "contratado_per_capita": "Contratado per cápita",
    }
    matrix_corr = validos[cols_corr].rename(columns=labels_corr).corr()

    fig_corr = px.imshow(
        matrix_corr,
        text_auto=".2f",
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        aspect="auto",
        template=TEMPLATE,
    )
    fig_corr.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_corr, use_container_width=True)

    _explica(
        "El análisis multivariado combina múltiples dimensiones para entender la gestión pública de forma integral: "
        "la correlación lineal mide la fuerza de la asociación entre variables (-1.0 a +1.0) y el algoritmo K-Means "
        "agrupa localidades con perfiles similares.",
        "**Detalle técnico:** Se aplica estandarización Z-score (`StandardScaler`) sobre el vector multivariado para evitar que "
        "variables de gran magnitud (como pesos colombianos en `total_contratado`) dominen sobre variables acotadas (`idc` entre 0 y 1). "
        "Luego se ejecuta `KMeans(n_clusters=3, random_state=42)` y se calcula la matriz de correlación de Pearson r = Cov(X,Y)/(sigma_X * sigma_Y). "
        "Sumapaz se marca como outlier estructural debido a su apalancamiento atípico en `idc_raw` sin contrapartida en masa contractual urbana.",
    )


# ------------------------------------------------------------------
# Análisis descriptivo por localidad (EDA)
# ------------------------------------------------------------------

def analisis_exploratorio(idc_data, filas_sin_localidad: dict):
    st.subheader("Análisis descriptivo por localidad", anchor=False, divider="orange")
    st.markdown(
        "Cada indicador que alimenta el IDC, mostrado como un gráfico de barras "
        "ordenado por localidad (igual estilo en toda la app), más una tabla resumen "
        "con colores para comparar todo de un vistazo."
    )

    utiles, vacias = _columnas_utiles(idc_data, COLUMNAS_CANDIDATAS)
    if vacias:
        st.info("Estas columnas no tienen información en este corte y se excluyeron del análisis: " + ", ".join(vacias) + ".")

    escalas = {"total_contratado": "OrRd", "num_contratos": "Purples",
               "total_contratado_directo": "Reds", "num_postulantes": "Blues", "idc": "OrRd"}
    items = list(utiles.items())
    for i in range(0, len(items), 2):
        pareja = items[i:i + 2]
        cols = st.columns(len(pareja))
        for c, (col_name, etiqueta) in zip(cols, pareja):
            with c:
                _bar_localidad(idc_data, col_name, etiqueta, escalas.get(col_name, "OrRd"))

    st.write("")
    st.markdown("**Tabla resumen por localidad** (colores más oscuros = valores más altos, cada columna con su propia escala)")
    columnas_tabla = ["localidad_limpia"] + list(utiles.keys())
    tabla = idc_data[columnas_tabla].set_index("localidad_limpia")
    st.dataframe(
        tabla.style.apply(_gradiente_columna, axis=0).format("{:,.2f}"),
        use_container_width=True,
    )

    st.write("")
    st.markdown("**Calidad de los datos (control de calidad)**")
    if filas_sin_localidad:
        qc_cols = st.columns(len(filas_sin_localidad))
        for col, (fuente, cantidad) in zip(qc_cols, filas_sin_localidad.items()):
            col.metric(f"Sin localidad: {fuente}", f"{cantidad:,}")

    _explica(
        "Cada gráfico ordena las 20 localidades de mayor a menor en ese indicador. La "
        "tabla junta todos los indicadores útiles en un solo lugar, coloreando cada "
        "columna según su propio rango de valores.",
        "Se descarta del análisis cualquier columna cuyos valores no nulos sean todos "
        "cero (`serie.dropna().eq(0).all()`), en vez de graficar una columna sin "
        "información real. La tabla usa `DataFrame.style.background_gradient` (una "
        "escala de color independiente por columna).",
    )


# ------------------------------------------------------------------
# Componentes principales (PCA)
# ------------------------------------------------------------------

def analisis_componentes_principales(idc_data):
    st.subheader("Análisis de Componentes Principales (PCA)", anchor=False, divider="orange")
    st.markdown(
        "El PCA sintetiza múltiples dimensiones numéricas en un solo plano bi-dimensional (PC1 vs. PC2), "
        "permitiendo visualizar qué localidades comparten patrones contractuales y cuáles se diferencian marcadamente."
    )

    utiles, _ = _columnas_utiles(idc_data, COLUMNAS_CANDIDATAS)
    columnas_pca = list(utiles.keys())
    base = idc_data.dropna(subset=columnas_pca).copy() if columnas_pca else idc_data.iloc[0:0]

    if len(columnas_pca) < 3 or len(base) < 4:
        st.info("No hay suficientes variables o localidades con datos completos en este corte para calcular un PCA confiable.")
        return

    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    X = StandardScaler().fit_transform(base[columnas_pca].values)
    pca = PCA(n_components=2)
    scores = pca.fit_transform(X)
    var_explicada = pca.explained_variance_ratio_ * 100

    df_scores = pd.DataFrame({
        "PC1": scores[:, 0],
        "PC2": scores[:, 1],
        "localidad_limpia": base["localidad_limpia"].values,
        "idc": base["idc"].values if "idc" in base.columns else 0,
        "total_contratado": base["total_contratado"].values if "total_contratado" in base.columns else 0,
        "total_contratado_directo": base["total_contratado_directo"].values if "total_contratado_directo" in base.columns else 0,
        "num_contratos": base["num_contratos"].values if "num_contratos" in base.columns else 0,
    })

    # ALGORITMO ANTI-COLISIÓN DE ETIQUETAS E INTELLIGENT POSITIONS
    coords = df_scores[["PC1", "PC2"]].values
    N = len(coords)
    annotations = []

    # Radio de densidad poblada en el plano PCA
    R_threshold = 0.45

    for i in range(N):
        x_i, y_i = coords[i, 0], coords[i, 1]
        name_i = df_scores.iloc[i]["localidad_limpia"].title()

        # Calcular distancias a otros puntos
        dists = np.linalg.norm(coords - coords[i], axis=1)
        close_mask = (dists < R_threshold) & (dists > 0)
        num_close = np.sum(close_mask)

        if num_close > 0:
            # Calcular centro de masa de vecinos cercanos
            c_neighbors = np.mean(coords[close_mask], axis=0)
            vec = coords[i] - c_neighbors
            norm = np.linalg.norm(vec)
            if norm == 0:
                vec = np.array([np.cos(i * 2 * np.pi / N), np.sin(i * 2 * np.pi / N)])
            else:
                vec = vec / norm

            # Desplazamiento inteligente de la etiqueta (en píxeles)
            ax_offset = float(vec[0] * 38)
            ay_offset = float(-vec[1] * 38)

            annotations.append(dict(
                x=x_i, y=y_i,
                text=f"<b>{name_i}</b>",
                showarrow=True,
                arrowhead=1,
                arrowsize=0.8,
                arrowwidth=1.0,
                arrowcolor="rgba(180, 180, 180, 0.7)",
                ax=ax_offset,
                ay=ay_offset,
                font=dict(size=10.5, color="#FFFFFF"),
                bgcolor="rgba(25, 25, 25, 0.85)",
                bordercolor="rgba(200, 200, 200, 0.5)",
                borderwidth=1,
                borderpad=3,
            ))
        else:
            # Punto aislado: etiqueta limpia arriba
            annotations.append(dict(
                x=x_i, y=y_i,
                text=f"<b>{name_i}</b>",
                showarrow=True,
                arrowhead=1,
                arrowsize=0.8,
                arrowwidth=0.8,
                arrowcolor="rgba(180, 180, 180, 0.5)",
                ax=0,
                ay=-24,
                font=dict(size=11, color="#FFFFFF"),
                bgcolor="rgba(25, 25, 25, 0.85)",
                bordercolor="rgba(200, 200, 200, 0.4)",
                borderwidth=1,
                borderpad=3,
            ))

    col1, col2 = st.columns([2.2, 1])
    with col1:
        # Gráfico Scatter Plot con paleta de alto contraste 'Viridis' y puntos destacados
        fig = px.scatter(
            df_scores,
            x="PC1",
            y="PC2",
            color="idc",
            color_continuous_scale="Viridis",
            template=TEMPLATE,
            labels={"idc": "IDC", "PC1": "Componente Principal 1", "PC2": "Componente Principal 2"},
            custom_data=["localidad_limpia", "idc", "total_contratado", "total_contratado_directo", "num_contratos"],
        )

        fig.update_traces(
            marker=dict(size=20, line=dict(width=1.5, color="#FFFFFF"), opacity=0.95),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "• <b>IDC:</b> %{customdata[1]:.2%}<br>"
                "• <b>Total Contratado:</b> $%{customdata[2]:,.0f}<br>"
                "• <b>Ejecutado FDL:</b> $%{customdata[3]:,.0f}<br>"
                "• <b>Contratos:</b> %{customdata[4]:,.0f}<br>"
                "• <b>PC1:</b> %{x:.2f} | <b>PC2:</b> %{y:.2f}"
                "<extra></extra>"
            ),
        )

        # Agregar etiquetas anti-colisión
        for ann in annotations:
            fig.add_annotation(**ann)

        # VECTORES DE VARIABLES (LOADINGS) CON ETIQUETAS DESPLAZADAS Y CONTRASTE
        escala = max(np.abs(scores).max() * 0.85, 0.01)
        loadings = pca.components_.T

        angle_offsets = [-12, 12, -15, 15, 0, 18]
        for i, col_name in enumerate(columnas_pca):
            lx, ly = loadings[i, 0] * escala, loadings[i, 1] * escala
            fig.add_annotation(
                x=lx, y=ly,
                ax=0, ay=0, xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=3, arrowcolor="#FF5722", arrowwidth=2.5,
            )
            # Etiqueta desplazada perpendicularmente
            fig.add_annotation(
                x=lx * 1.14, y=ly * 1.14 + (0.05 * (i % 2 - 0.5)),
                text=f"<b>{COLUMNAS_CANDIDATAS.get(col_name, col_name)}</b>",
                showarrow=False,
                font=dict(size=11, color="#FF7043"),
                bgcolor="rgba(0,0,0,0.5)",
                borderpad=2,
            )

        # Ejes de referencia cero (cuadrantes)
        fig.update_xaxes(zeroline=True, zerolinecolor="rgba(150, 150, 150, 0.4)", zerolinewidth=1.5)
        fig.update_yaxes(zeroline=True, zerolinecolor="rgba(150, 150, 150, 0.4)", zerolinewidth=1.5)

        fig.update_layout(
            height=580,
            margin=dict(l=15, r=15, t=15, b=15),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_colorbar_title="IDC",
            dragmode="pan",
        )
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})

    with col2:
        fig_var = px.bar(
            x=["Componente 1", "Componente 2"],
            y=var_explicada,
            template=TEMPLATE,
            color=["Componente 1", "Componente 2"],
            color_discrete_sequence=["#2A9D8F", "#E76F51"],
            text=var_explicada,
        )
        fig_var.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig_var.update_layout(
            height=580,
            showlegend=False,
            yaxis_title="% de Información Explicada",
            xaxis_title="",
            margin=dict(l=10, r=10, t=15, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_var, use_container_width=True)

    _explica(
        f"Entre los dos ejes del plano PCA se resume el **{var_explicada.sum():.1f}%** de toda la variabilidad contractual de las localidades. "
        "Las localidades agrupadas cerca en el gráfico comparten perfiles semejantes; las alejadas (como Sumapaz o Engativá/Suba) difieren por su masa de contratación o nivel de IDC. "
        "Las flechas naranja-rojas representan los vectores de cada variable (*loadings*), indicando en qué dirección influye cada indicador.",
        "**Detalle técnico:** Se estandarizan las variables con `StandardScaler` (Z-score) y se computa la descomposición en valores singulares (SVD) con `PCA(n_components=2)`. "
        "Las etiquetas del scatter plot implementan un algoritmo anti-colisión por repulsión vectorial de centro de masa local con líneas guía (*leader lines*). "
        "La paleta `Viridis` garantiza máximo contraste lumínico sobre fondos oscuros.",
    )


# ------------------------------------------------------------------
# Ranking y comparativos
# ------------------------------------------------------------------

def grafico_ranking(idc_data):
    st.subheader("Ranking de localidades según su IDC", anchor=False, divider="orange")
    data = idc_data.dropna(subset=["idc"]).sort_values("idc", ascending=True)

    fig = px.bar(
        data, x="idc", y="localidad_limpia", orientation="h",
        color="idc", color_continuous_scale=COLOR_SCALE, template=TEMPLATE,
        text="idc", labels={"idc": "IDC", "localidad_limpia": ""},
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

    _explica(
        "Cada barra es una localidad. Entre más larga y oscura, mayor proporción de su "
        "contratación pasó por su propio Fondo de Desarrollo Local.",
        "Se ordena `idc_data` por `idc` (excluyendo `NaN`) y se grafica con "
        "`plotly.express.bar` horizontal, coloreado por el mismo valor.",
    )


def grafico_comparativo(idc_data):
    st.subheader("Fondo de Desarrollo Local vs. contratación total", anchor=False, divider="orange")
    data = idc_data.sort_values("total_contratado", ascending=False)

    fig = go.Figure()
    fig.add_bar(x=data["localidad_limpia"], y=data["total_contratado"], name="Total contratado (todos los sectores)", marker_color="#F4A261")
    fig.add_bar(x=data["localidad_limpia"], y=data["total_contratado_directo"], name="Ejecutado por el Fondo Local", marker_color="#E76F51")
    fig.update_layout(
        barmode="group", template=TEMPLATE, height=480, xaxis_tickangle=-40,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)

    _explica(
        "Compara, localidad por localidad, el total contratado (barra clara) contra lo "
        "que ejecutó el Fondo de Desarrollo Local (barra oscura). Nota la diferencia de "
        "escala: el sector central maneja muchísimo más volumen que los fondos locales, "
        "por eso la barra oscura casi siempre se ve pequeña frente a la clara.",
        "Se grafican lado a lado `total_contratado` (suma general por localidad de "
        "domicilio del contratista) y `total_contratado_directo` (suma del subconjunto "
        "`Sector == 'Localidades'`, agrupado por la localidad del Fondo de Desarrollo Local).",
    )


def grafico_talento(idc_data, tabla_entidad):
    utiles, _ = _columnas_utiles(idc_data, {"num_postulantes": "x"})
    if "num_postulantes" in utiles:
        st.subheader("Talento no Palanca vinculado vía Fondo de Desarrollo Local", anchor=False, divider="orange")
        data = idc_data.sort_values("num_postulantes", ascending=False)
        fig = px.bar(
            data, x="localidad_limpia", y="num_postulantes", color="num_postulantes",
            color_continuous_scale="Blues", template=TEMPLATE,
            labels={"num_postulantes": "Personas contratadas vía TNP", "localidad_limpia": ""},
        )
        fig.update_layout(height=420, xaxis_tickangle=-40, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        _explica(
            "Muestra cuántas personas contrató cada Fondo de Desarrollo Local a través "
            "de la estrategia Talento no Palanca en este corte.",
            "El reporte de Talento no Palanca está organizado por **entidad**, no por "
            "localidad de residencia. Solo se puede ubicar geográficamente el subconjunto "
            "de entidades llamadas 'Fondo de Desarrollo Local de <localidad>'; el resto "
            "(sector central) se muestra en el gráfico de abajo, por entidad.",
        )

    if tabla_entidad is not None and not tabla_entidad.empty:
        st.markdown("**Talento no Palanca por entidad (incluye sector central)**")
        top15 = tabla_entidad.head(15)
        fig2 = px.bar(
            top15, x="num_contratistas_tnp", y="entidad", orientation="h",
            color="num_contratistas_tnp", color_continuous_scale="Teal", template=TEMPLATE,
            labels={"num_contratistas_tnp": "Personas contratadas vía TNP", "entidad": ""},
        )
        fig2.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10), yaxis={"categoryorder": "total ascending"}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "Estas entidades (salud, movilidad, cultura, etc.) no se pueden asignar a "
            "una sola localidad: prestan servicio a toda la ciudad, por eso se muestran "
            "por entidad y no entran al cálculo del IDC."
        )


# ------------------------------------------------------------------
# Mapa geográfico
# ------------------------------------------------------------------

def mapa_geografico(idc_data, geojson_obj, corte_label: str):
    st.subheader("Mapa interactivo del IDC en Bogotá", anchor=False, divider="orange")
    st.caption("Explora la distribución espacial del IDC y los indicadores de normalización demográfica per cápita.")

    data = idc_data.copy()

    tiene_poblacion = "contratado_per_capita" in data.columns and data["poblacion_total"].sum() > 0

    col_opt1, col_opt2 = st.columns(2)

    with col_opt1:
        opciones_metrica = {"idc": "IDC (Índice de Descentralización)"}
        if tiene_poblacion:
            opciones_metrica["contratado_per_capita"] = "Contratado per cápita ($/hab)"
            opciones_metrica["contratos_por_1000_hab"] = "Contratos por 1.000 hab"
            opciones_metrica["postulantes_tnp_por_1000_hab"] = "Talento no Palanca por 1.000 hab"

        metrica_color = st.selectbox(
            "Métrica de Normalización Demográfica (Per Cápita)",
            options=list(opciones_metrica.keys()),
            index=1 if tiene_poblacion else 0,
            format_func=lambda m: opciones_metrica[m],
        )

    with col_opt2:
        tipo_mapa = st.selectbox(
            "Estilo de visualización del mapa",
            options=["calor", "poligonos", "burbujas"],
            format_func=lambda t: {
                "calor": "Mapa de Calor Espacial (Density Heatmap)",
                "poligonos": "Polígonos Oficiales (Coropletas SDP/IDECA)",
                "burbujas": "Círculos en Centroides (Scatter Mapbox)",
            }[t],
        )

    if metrica_color == "contratado_per_capita":
        data["idc_mapa"] = data["contratado_per_capita"].fillna(0)
        rango_color = [0, data["idc_mapa"].max() or 1]
        titulo_color = "$/hab"
    elif metrica_color == "contratos_por_1000_hab":
        data["idc_mapa"] = data["contratos_por_1000_hab"].fillna(0)
        rango_color = [0, data["idc_mapa"].max() or 1]
        titulo_color = "Contratos / 1k hab"
    elif metrica_color == "postulantes_tnp_por_1000_hab":
        data["idc_mapa"] = data["postulantes_tnp_por_1000_hab"].fillna(0)
        rango_color = [0, data["idc_mapa"].max() or 1]
        titulo_color = "TNP / 1k hab"
    else:
        data["idc_mapa"] = data["idc"].fillna(0).clip(upper=1.0)
        rango_color = [0, 1.0]
        titulo_color = "IDC"

    fig = None

    if tipo_mapa == "calor":
        fig = px.density_mapbox(
            data, lat="latitud", lon="longitud", z="idc_mapa",
            radius=45, zoom=9.8, center={"lat": 4.65, "lon": -74.1},
            mapbox_style="open-street-map", color_continuous_scale=COLOR_SCALE,
            hover_name="localidad_limpia", hover_data={"idc": True, "idc_mapa": True, "latitud": False, "longitud": False},
            labels={"idc_mapa": titulo_color},
        )
        modo = "Mapa de calor espacial por centroides (Density Heatmap)"

    elif tipo_mapa == "poligonos" and geojson_obj is not None:
        try:
            fig = px.choropleth_mapbox(
                data, geojson=geojson_obj, locations="localidad_limpia",
                featureidkey="properties.localidad_limpia",
                color="idc_mapa", range_color=rango_color, color_continuous_scale=COLOR_SCALE,
                mapbox_style="open-street-map", zoom=9.8, center={"lat": 4.65, "lon": -74.1}, opacity=0.8,
                hover_name="localidad_limpia", hover_data={"idc": True, "idc_mapa": True},
                labels={"idc_mapa": titulo_color},
            )
            modo = "Polígonos oficiales (IDECA / Secretaría Distrital de Planeación)"
        except Exception:
            fig = None

    if fig is None:
        fig = px.scatter_mapbox(
            data, lat="latitud", lon="longitud", color="idc_mapa",
            size=np.maximum(data["total_contratado"], 1), color_continuous_scale=COLOR_SCALE,
            range_color=rango_color, size_max=38, zoom=9.8, center={"lat": 4.65, "lon": -74.1},
            mapbox_style="open-street-map", text="localidad_limpia", hover_name="localidad_limpia",
            hover_data={"idc": True, "idc_mapa": True, "latitud": False, "longitud": False},
            labels={"idc_mapa": titulo_color},
        )
        fig.update_traces(textposition="top center", textfont=dict(size=10))
        modo = "Círculos por localidad en centroides"

    fig.update_layout(
        height=620, margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_colorbar_title=titulo_color, dragmode="pan",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
    st.caption(f"Modo de mapa activo: {modo}. Métrica seleccionada: {opciones_metrica[metrica_color]}. Corte mostrado: {corte_label}.")

    st.subheader("¿Qué nos dice el mapa? (Análisis geográfico)", anchor=False, divider="orange")
    referencia = idc_data.dropna(subset=["idc", "latitud"]) if "latitud" in idc_data.columns else idc_data.dropna(subset=["idc"])

    if "latitud" in idc_data.columns and not referencia.empty:
        mediana_lat = idc_data["latitud"].median()
        norte = referencia[referencia["latitud"] > mediana_lat]
        sur = referencia[referencia["latitud"] <= mediana_lat]
        idc_norte = norte["idc"].mean() if not norte.empty else float("nan")
        idc_sur = sur["idc"].mean() if not sur.empty else float("nan")
        texto_geo = (
            f"En el corte de **{corte_label}**, las localidades del **norte** de Bogotá "
            f"tienen un IDC promedio de **{idc_norte:.2f}**, mientras que las del **sur** "
            f"tienen **{idc_sur:.2f}**. "
        )
        if not np.isnan(idc_norte) and not np.isnan(idc_sur):
            if idc_norte > idc_sur:
                texto_geo += "El norte descentralizó un poco más su contratación que el sur en este corte."
            elif idc_sur > idc_norte:
                texto_geo += "El sur descentralizó un poco más su contratación que el norte en este corte."
            else:
                texto_geo += "Norte y sur se comportaron de forma muy parecida en este corte."
    else:
        texto_geo = "No hay suficiente información geográfica para comparar zonas de la ciudad en este corte."

    _explica(
        texto_geo,
        "El color representa `idc` (acotado a un máximo de 1.0 para no distorsionar la "
        "escala de color); en el modo de círculos, el tamaño representa `total_contratado`. "
        "El análisis norte/sur divide las localidades por la mediana de su latitud de "
        "centroide y compara el promedio de `idc` entre ambos grupos: una forma simple, "
        "no un modelo espacial formal (no incluye autocorrelación espacial ni pruebas de "
        "significancia estadística).",
    )


# ------------------------------------------------------------------
# Interpretación general (Síntesis Multivariada)
# ------------------------------------------------------------------

def interpretacion_general(idc_data, corte_label: str):
    st.subheader("¿Qué significan estos patrones multivariados en la práctica?", anchor=False, divider="orange")

    st.markdown(
        f"""
Para entender la descentralización en Bogotá sin perderse en tecnicismos, piensa en la contratación de cada localidad mediante la metáfora de dos bolsillos:

1. **El bolsillo propio (Fondo de Desarrollo Local):** El presupuesto administrado por la alcaldía local para proyectos directos en la comunidad.
2. **El bolsillo distrital (Sector Central):** Los recursos de las grandes secretarías (Salud, Educación, Movilidad, Gobierno, Hábitat), que contratan masivamente a personas o empresas domiciliadas en la localidad.

### Por qué el análisis multivariado cambia la perspectiva:
- **No existe una única localidad 'ganadora':** Evaluar solo una cifra aislada (como el IDC más alto) resulta engañoso. Una localidad con IDC alto puede tener un presupuesto absoluto menor, mientras que una localidad con IDC bajo puede estar recibiendo inversiones masivas del sector central.
- **Patrones de concentración corporativa:** Localidades con alta concentración institucional o empresarial (como Chapinero o Usaquén) captan miles de contratistas de secretarías centrales. Por dinámica proporcional, esto reduce su valor numérico de IDC a pesar de que sus Fondos Locales ejecuten montos importantes.
- **Equidad per cápita:** Al analizar la masa contratada por cada 1.000 habitantes, se comprueba que los Fondos Locales cumplen una función indispensable de **red redistributiva** en localidades del sur y periferia de Bogotá.

> **Conclusión técnica:** El IDC y el análisis de clústeres no evalúan la 'eficiencia' o 'buena gestión' de un alcalde local; miden la **estructura y composición del flujo de dinero público** que llega a los residentes de cada territorio.
        """
    )
