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
# Resumen / métricas
# ------------------------------------------------------------------

def mostrar_metricas(idc_data, corte_label: str):
    st.subheader("Lo más importante, en 4 números", anchor=False, divider="orange")
    st.caption(f"Corte analizado: {corte_label} (fotografía del estado acumulado a esa fecha, no una suma de varios meses)")

    tiene_outlier = "es_outlier" in idc_data.columns
    urbanas = idc_data[~idc_data["es_outlier"]] if tiene_outlier else idc_data
    validos_urbanos = urbanas.dropna(subset=["idc"])

    total_contratado = idc_data["total_contratado"].sum()
    total_fdl = idc_data["total_contratado_directo"].sum()
    idc_macro = (total_fdl / total_contratado) if total_contratado > 0 else 0
    top = validos_urbanos.sort_values("idc", ascending=False).iloc[0] if not validos_urbanos.empty else None

    tiene_poblacion = "poblacion_total" in idc_data.columns and idc_data["poblacion_total"].sum() > 0

    if tiene_poblacion:
        col1, col2, col3, col4, col5 = st.columns(5)
    else:
        col1, col2, col3, col4 = st.columns(4)
        col5 = None
    with col1:
        st.metric("IDC macro de Bogotá", f"{idc_macro:.2%}")
    with col2:
        st.metric("Localidad urbana más descentralizada", top["localidad_limpia"].title() if top is not None else "-")
    with col3:
        st.metric("Total contratado (este corte)", f"${total_contratado:,.0f}")
    with col4:
        st.metric("Ejecutado por Fondos de Desarrollo Local", f"${total_fdl:,.0f}")
    if col5 is not None:
        anio_pob = idc_data["anio_poblacion"].dropna().iloc[0] if "anio_poblacion" in idc_data.columns and idc_data["anio_poblacion"].notna().any() else "?"
        with col5:
            st.metric(f"Población Bogotá ({anio_pob})", f"{idc_data['poblacion_total'].sum():,.0f}")

    if tiene_outlier and idc_data.loc[idc_data["es_outlier"], "idc_raw"].notna().any():
        st.info(
            "Sumapaz es una localidad casi enteramente rural: apenas registra contratistas "
            "domiciliados allí, lo que produce un IDC bruto matemáticamente desproporcionado. "
            "Por eso se muestra por separado y no entra en el 'top' de localidades urbanas."
        )

    st.write("")
    _explica(
        "El **IDC (Índice de Descentralización de Contratación)** compara, para cada "
        "localidad, cuánta plata ejecutó directamente su **Fondo de Desarrollo Local** "
        "frente al total de dinero que se contrató con personas domiciliadas en esa "
        "localidad, en todos los sectores de la ciudad.\n\n"
        "- IDC **alto** (cercano a 1): buena parte de la contratación de esa localidad "
        "pasó por su propio fondo local.\n"
        "- IDC **bajo** (cercano a 0): la mayor parte vino de entidades sectoriales "
        "(salud, ambiente, cultura, etc.), no del fondo local.",
        "**Fórmula:** `IDC = total_contratado_directo / total_contratado` (acotado a un "
        "máximo de 1.0 para que un caso extremo no distorsione los gráficos; el valor sin "
        "acotar queda disponible en `idc_raw`). El **IDC macro** de arriba es distinto: es "
        "`total_contratado_directo` sumado en toda la ciudad, dividido por `total_contratado` "
        "sumado en toda la ciudad — un único número para Bogotá, menos sensible a casos "
        "extremos de una sola localidad que el promedio simple de los IDC individuales.\n\n"
        "**Limitación metodológica reconocida**: `total_contratado` se agrupa por la "
        "*localidad de domicilio del contratista* (el único dato geográfico disponible en "
        "la fuente), no por el lugar donde efectivamente se ejecuta el contrato. Esto puede "
        "subrepresentar localidades periféricas y sobrerrepresentar localidades con más "
        "infraestructura corporativa. El IDC de esta app es un proxy, no una medida exacta."
        + (
            "\n\n**Población (Fuente 4, SDP)**: se integraron las proyecciones/retroproyecciones "
            "de población 2005-2035 por localidad para calcular indicadores *per cápita* "
            "(`contratos_por_1000_hab`, `contratado_per_capita`) y para que las 20 localidades "
            "siempre aparezcan en mapas y tablas con su población, aunque un corte mensual no "
            "tenga contratistas registrados allí."
            if tiene_poblacion else ""
        ),
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
    st.subheader("Análisis de componentes principales (PCA)", anchor=False, divider="orange")
    st.markdown(
        "Cada localidad tiene varios números distintos (cuánto contrató, cuántos "
        "contratos, cuánto ejecutó su fondo local...). El PCA junta toda esa "
        "información en un solo mapa de 2 dimensiones, para ver qué localidades se "
        "parecen entre sí y cuáles se salen del grupo."
    )

    utiles, _ = _columnas_utiles(idc_data, COLUMNAS_CANDIDATAS)
    columnas_pca = list(utiles.keys())
    base = idc_data.dropna(subset=columnas_pca) if columnas_pca else idc_data.iloc[0:0]

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
        "PC1": scores[:, 0], "PC2": scores[:, 1],
        "localidad_limpia": base["localidad_limpia"].values,
        "idc": base["idc"].values if "idc" in base.columns else 0,
    })

    col1, col2 = st.columns([2, 1])
    with col1:
        fig = px.scatter(
            df_scores, x="PC1", y="PC2", text="localidad_limpia",
            color="idc", color_continuous_scale=COLOR_SCALE, template=TEMPLATE, labels={"idc": "IDC"},
        )
        fig.update_traces(textposition="top center", marker=dict(size=14, line=dict(width=1, color="white")))

        escala = max(np.abs(scores).max() * 0.9, 0.01)
        loadings = pca.components_.T
        for i, col_name in enumerate(columnas_pca):
            fig.add_annotation(
                x=loadings[i, 0] * escala, y=loadings[i, 1] * escala,
                ax=0, ay=0, xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=3, arrowcolor="#E76F51", arrowwidth=1.5,
            )
            fig.add_annotation(
                x=loadings[i, 0] * escala * 1.15, y=loadings[i, 1] * escala * 1.15,
                text=COLUMNAS_CANDIDATAS.get(col_name, col_name), showarrow=False,
                font=dict(size=11, color="#E76F51"),
            )
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig_var = px.bar(
            x=["Componente 1", "Componente 2"], y=var_explicada, template=TEMPLATE,
            color=["Componente 1", "Componente 2"], color_discrete_sequence=["#E76F51", "#F4A261"], text=var_explicada,
        )
        fig_var.update_traces(texttemplate="%{text:.0f}%", textposition="outside")
        fig_var.update_layout(height=520, showlegend=False, yaxis_title="% de información explicada", xaxis_title="", margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_var, use_container_width=True)

    _explica(
        f"Entre los dos ejes de este mapa se resume el **{var_explicada.sum():.0f}%** de "
        "toda la información de las localidades. Las que quedan **cerca** en el gráfico "
        "se parecen en su forma de contratar; las que quedan **lejos** son distintas. "
        "Las flechas muestran hacia dónde 'jala' cada variable.",
        "Se estandarizan (media 0, desviación 1) las columnas útiles con `StandardScaler` "
        "y se ajusta un `PCA(n_components=2)` de scikit-learn sobre las localidades con "
        "datos completos. `PC1`/`PC2` son los puntajes de cada localidad; las flechas son "
        "los `pca.components_` (loadings) de cada variable original, escalados para verse "
        "junto a los puntos (biplot). El panel derecho muestra `explained_variance_ratio_`.",
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
# Interpretación general
# ------------------------------------------------------------------

def interpretacion_general(idc_data, corte_label: str):
    st.subheader("¿Qué significa todo esto en fácil?", anchor=False, divider="orange")
    urbanas = idc_data[~idc_data["es_outlier"]] if "es_outlier" in idc_data.columns else idc_data
    validos = urbanas.dropna(subset=["idc"])
    if not validos.empty:
        top = validos.sort_values("idc", ascending=False).iloc[0]
        bottom = validos.sort_values("idc", ascending=True).iloc[0]
        frase_top = f"En el corte de **{corte_label}**, la localidad urbana que más contrató vía su fondo local fue **{top['localidad_limpia'].title()}**."
        frase_bottom = f"La que menos lo hizo fue **{bottom['localidad_limpia'].title()}**."
    else:
        frase_top = f"En el corte de **{corte_label}** no hay suficiente información para identificar la localidad más descentralizada."
        frase_bottom = ""

    st.markdown(
        f"""
Piensa en cada localidad de Bogotá como si tuviera su propia "alcancía" para
gastar en su barrio: eso es el **Fondo de Desarrollo Local**.

Además de esa alcancía propia, muchas entidades de la ciudad (salud, cultura,
ambiente, movilidad...) también contratan gente que vive en esa localidad.

El **IDC** compara: *de todo lo que se contrató con gente domiciliada en una
localidad, cuánto vino de la alcancía propia y cuánto vino de entidades
grandes de la ciudad.*

- IDC **alto** (cerca de 1): la localidad maneja bastante de su contratación
  con su propia alcancía.
- IDC **bajo** (cerca de 0): casi toda la contratación vino de entidades
  grandes de la ciudad.

{frase_top} {frase_bottom}

Recuerda: esto se mide por dónde vive el contratista, no necesariamente por
dónde se presta el servicio, así que tómalo como una señal para investigar
más, no como una conclusión definitiva.
        """
    )
