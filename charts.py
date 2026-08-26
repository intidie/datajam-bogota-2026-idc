"""
charts.py
---------
Metricas, graficos Plotly, mapa interactivo, analisis descriptivo por
localidad, componentes principales (PCA) y explicaciones en lenguaje
sencillo. Cada bloque incluye, ademas de la interpretacion para publico
general, un expansor "Que esta pasando por dentro" con el detalle tecnico.
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
    "num_contratos": "Numero de contratos",
    "total_contratado_directo": "Ejecutado por el Fondo Local",
    "num_postulantes": "Personas TNP vinculadas via Fondo Local",
    "idc": "IDC",
    "poblacion_total": "Poblacion total (localidad)",
    "contratos_por_1000_hab": "Contratos por 1.000 habitantes",
    "contratado_per_capita": "Contratado per capita ($/hab)",
}


# ------------------------------------------------------------------
# Gradiente de color sin matplotlib (el proyecto es "todo Plotly"; usar
# Styler.background_gradient de pandas exige matplotlib instalado, asi
# que aqui se interpola manualmente entre dos colores por columna).
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
    normaliza cada columna entre su minimo y maximo y le asigna un color
    de fondo, columna por columna (misma logica que axis=0)."""
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
    with st.expander("Que esta pasando por dentro (detalle tecnico)"):
        st.markdown(texto_tecnico)


def _columnas_utiles(idc_data, candidatas: dict):
    """Separa las columnas que tienen informacion real de las que estan
    completamente en cero o nulas (sin informacion), para no graficar ni
    analizar columnas vacias."""
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
# Resumen / metricas
# ------------------------------------------------------------------

def mostrar_metricas(idc_data, corte_label: str):
    st.subheader("Lo mas importante, en 4 numeros", anchor=False, divider="orange")
    st.caption(f"Corte analizado: {corte_label} (fotografia del estado acumulado a esa fecha, no una suma de varios meses)")

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
        st.metric("IDC macro de Bogota", f"{idc_macro:.2%}")
    with col2:
        st.metric("Localidad urbana mas descentralizada", top["localidad_limpia"].title() if top is not None else "-")
    with col3:
        st.metric("Total contratado (este corte)", f"${total_contratado:,.0f}")
    with col4:
        st.metric("Ejecutado por Fondos de Desarrollo Local", f"${total_fdl:,.0f}")
    if col5 is not None:
        anio_pob = idc_data["anio_poblacion"].dropna().iloc[0] if "anio_poblacion" in idc_data.columns and idc_data["anio_poblacion"].notna().any() else "?"
        with col5:
            st.metric(f"Poblacion Bogota ({anio_pob})", f"{idc_data['poblacion_total'].sum():,.0f}")

    if tiene_outlier and idc_data.loc[idc_data["es_outlier"], "idc_raw"].notna().any():
        st.info(
            "Sumapaz es una localidad casi enteramente rural: apenas registra contratistas "
            "domiciliados alli, lo que produce un IDC bruto matematicamente desproporcionado. "
            "Por eso se muestra por separado y no entra en el 'Top' de localidades urbanas."
        )

    st.write("")
    _explica(
        "El **IDC (Indice de Descentralizacion de Contratacion)** compara, para cada "
        "localidad, cuanta plata ejecuto directamente su **Fondo de Desarrollo Local** "
        "frente al total de dinero que se contrato con personas domiciliadas en esa "
        "localidad, en todos los sectores de la ciudad.\n\n"
        "- IDC **alto** (cercano a 1): buena parte de la contratacion de esa localidad "
        "paso por su propio fondo local.\n"
        "- IDC **bajo** (cercano a 0): la mayor parte vino de entidades sectoriales "
        "(salud, ambiente, cultura, etc.), no del fondo local.",
        "**Formula:** `IDC = total_contratado_directo / total_contratado` (acotado a un "
        "maximo de 1.0 para que un caso extremo no distorsione los graficos; el valor sin "
        "acotar queda disponible en `idc_raw`). El **IDC macro** de arriba es distinto: es "
        "`total_contratado_directo` sumado en toda la ciudad, dividido por `total_contratado` "
        "sumado en toda la ciudad — un unico numero para Bogota, menos sensible a casos "
        "extremos de una sola localidad que el promedio simple de los IDC individuales.\n\n"
        "**Limitacion metodologica reconocida**: `total_contratado` se agrupa por la "
        "*localidad de domicilio del contratista* (el unico dato geografico disponible en "
        "la fuente), no por el lugar donde efectivamente se ejecuta el contrato. Esto puede "
        "sub-representar localidades perifericas y sobre-representar localidades con mas "
        "infraestructura corporativa. El IDC de esta app es un proxy, no una medida exacta."
        + (
            "\n\n**Poblacion (Fuente 4, SDP)**: se integraron las proyecciones/retroproyecciones "
            "de poblacion 2005-2035 por localidad para calcular indicadores *per capita* "
            "(`contratos_por_1000_hab`, `contratado_per_capita`) y para que las 20 localidades "
            "siempre aparezcan en mapas y tablas con su poblacion, aunque un corte mensual no "
            "tenga contratistas registrados alli."
            if tiene_poblacion else ""
        ),
    )


# ------------------------------------------------------------------
# Analisis descriptivo por localidad (EDA)
# ------------------------------------------------------------------

def analisis_exploratorio(idc_data, filas_sin_localidad: dict):
    st.subheader("Analisis descriptivo por localidad", anchor=False, divider="orange")
    st.markdown(
        "Cada indicador que alimenta el IDC, mostrado como un grafico de barras "
        "ordenado por localidad (igual estilo en toda la app), mas una tabla resumen "
        "con colores para comparar todo de un vistazo."
    )

    utiles, vacias = _columnas_utiles(idc_data, COLUMNAS_CANDIDATAS)
    if vacias:
        st.info("Estas columnas no tienen informacion en este corte y se excluyeron del analisis: " + ", ".join(vacias) + ".")

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
    st.markdown("**Tabla resumen por localidad** (colores mas oscuros = valores mas altos, cada columna con su propia escala)")
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
        "Cada grafico ordena las 20 localidades de mayor a menor en ese indicador. La "
        "tabla junta todos los indicadores utiles en un solo lugar, coloreando cada "
        "columna segun su propio rango de valores.",
        "Se descarta del analisis cualquier columna cuyos valores no nulos sean todos "
        "cero (`serie.dropna().eq(0).all()`), en vez de graficar una columna sin "
        "informacion real. La tabla usa `DataFrame.style.background_gradient` (una "
        "escala de color independiente por columna).",
    )


# ------------------------------------------------------------------
# Componentes principales (PCA)
# ------------------------------------------------------------------

def analisis_componentes_principales(idc_data):
    st.subheader("Analisis de componentes principales (PCA)", anchor=False, divider="orange")
    st.markdown(
        "Cada localidad tiene varios numeros distintos (cuanto contrato, cuantos "
        "contratos, cuanto ejecuto su fondo local...). El PCA junta toda esa "
        "informacion en un solo mapa de 2 dimensiones, para ver que localidades se "
        "parecen entre si y cuales se salen del grupo."
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
        fig_var.update_layout(height=520, showlegend=False, yaxis_title="% de informacion explicada", xaxis_title="", margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_var, use_container_width=True)

    _explica(
        f"Entre los dos ejes de este mapa se resume el **{var_explicada.sum():.0f}%** de "
        "toda la informacion de las localidades. Las que quedan **cerca** en el grafico "
        "se parecen en su forma de contratar; las que quedan **lejos** son distintas. "
        "Las flechas muestran hacia donde 'jala' cada variable.",
        "Se estandarizan (media 0, desviacion 1) las columnas utiles con `StandardScaler` "
        "y se ajusta un `PCA(n_components=2)` de scikit-learn sobre las localidades con "
        "datos completos. `PC1`/`PC2` son los puntajes de cada localidad; las flechas son "
        "los `pca.components_` (loadings) de cada variable original, escalados para verse "
        "junto a los puntos (biplot). El panel derecho muestra `explained_variance_ratio_`.",
    )


# ------------------------------------------------------------------
# Ranking y comparativos
# ------------------------------------------------------------------

def grafico_ranking(idc_data):
    st.subheader("Ranking de localidades segun su IDC", anchor=False, divider="orange")
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
        "Cada barra es una localidad. Entre mas larga y oscura, mayor proporcion de su "
        "contratacion paso por su propio Fondo de Desarrollo Local.",
        "Se ordena `idc_data` por `idc` (excluyendo `NaN`) y se grafica con "
        "`plotly.express.bar` horizontal, coloreado por el mismo valor.",
    )


def grafico_comparativo(idc_data):
    st.subheader("Fondo de Desarrollo Local vs. contratacion total", anchor=False, divider="orange")
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
        "que ejecuto el Fondo de Desarrollo Local (barra oscura). Nota la diferencia de "
        "escala: el sector central maneja muchisimo mas volumen que los fondos locales, "
        "por eso la barra oscura casi siempre se ve pequeña frente a la clara.",
        "Se grafican lado a lado `total_contratado` (suma general por localidad de "
        "domicilio del contratista) y `total_contratado_directo` (suma del subconjunto "
        "`Sector == 'Localidades'`, agrupado por la localidad del Fondo de Desarrollo Local).",
    )


def grafico_talento(idc_data, tabla_entidad):
    utiles, _ = _columnas_utiles(idc_data, {"num_postulantes": "x"})
    if "num_postulantes" in utiles:
        st.subheader("Talento no Palanca vinculado via Fondo de Desarrollo Local", anchor=False, divider="orange")
        data = idc_data.sort_values("num_postulantes", ascending=False)
        fig = px.bar(
            data, x="localidad_limpia", y="num_postulantes", color="num_postulantes",
            color_continuous_scale="Blues", template=TEMPLATE,
            labels={"num_postulantes": "Personas contratadas via TNP", "localidad_limpia": ""},
        )
        fig.update_layout(height=420, xaxis_tickangle=-40, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
        _explica(
            "Muestra cuantas personas contrato cada Fondo de Desarrollo Local a traves "
            "de la estrategia Talento no Palanca en este corte.",
            "El reporte de Talento no Palanca esta organizado por **entidad**, no por "
            "localidad de residencia. Solo se puede ubicar geograficamente el subconjunto "
            "de entidades llamadas 'Fondo de Desarrollo Local de <localidad>'; el resto "
            "(sector central) se muestra en el grafico de abajo, por entidad.",
        )

    if tabla_entidad is not None and not tabla_entidad.empty:
        st.markdown("**Talento no Palanca por entidad (incluye sector central)**")
        top15 = tabla_entidad.head(15)
        fig2 = px.bar(
            top15, x="num_contratistas_tnp", y="entidad", orientation="h",
            color="num_contratistas_tnp", color_continuous_scale="Teal", template=TEMPLATE,
            labels={"num_contratistas_tnp": "Personas contratadas via TNP", "entidad": ""},
        )
        fig2.update_layout(height=480, margin=dict(l=10, r=10, t=10, b=10), yaxis={"categoryorder": "total ascending"}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)
        st.caption(
            "Estas entidades (salud, movilidad, cultura, etc.) no se pueden asignar a "
            "una sola localidad: prestan servicio a toda la ciudad, por eso se muestran "
            "por entidad y no entran al calculo del IDC."
        )


# ------------------------------------------------------------------
# Mapa geografico
# ------------------------------------------------------------------

def mapa_geografico(idc_data, geojson_obj, corte_label: str):
    st.subheader("Mapa interactivo del IDC en Bogota", anchor=False, divider="orange")
    st.caption("Puedes hacer zoom con la rueda del mouse (o pellizcar en el celular) y arrastrar para moverte por el mapa.")

    data = idc_data.copy()

    tiene_poblacion = "contratado_per_capita" in data.columns and data["poblacion_total"].sum() > 0
    metrica_color = "idc"
    if tiene_poblacion:
        metrica_color = st.radio(
            "Colorear el mapa por",
            options=["idc", "contratado_per_capita"],
            format_func=lambda m: "IDC" if m == "idc" else "Contratado per capita ($/habitante)",
            horizontal=True,
        )

    if metrica_color == "contratado_per_capita":
        data["idc_mapa"] = data["contratado_per_capita"].fillna(0)
        rango_color = [0, data["idc_mapa"].max() or 1]
        titulo_color = "$/hab"
    else:
        data["idc_mapa"] = data["idc"].fillna(0).clip(upper=1.0)
        rango_color = [0, 1.0]
        titulo_color = "IDC"
    fig = None

    if geojson_obj is not None:
        try:
            fig = px.choropleth_mapbox(
                data, geojson=geojson_obj, locations="localidad_limpia",
                featureidkey="properties.localidad_limpia",
                color="idc_mapa", range_color=rango_color, color_continuous_scale=COLOR_SCALE,
                mapbox_style="open-street-map", zoom=9.3, center={"lat": 4.65, "lon": -74.1}, opacity=0.8,
                hover_name="localidad_limpia", hover_data={"idc": True, "idc_mapa": False},
                labels={"idc_mapa": titulo_color},
            )
            modo = "poligonos oficiales (IDECA / Secretaria Distrital de Planeacion)"
        except Exception:
            fig = None

    if fig is None:
        # Mapa de burbujas por localidad: siempre funciona (solo necesita
        # latitud/longitud de los centroides) y es mucho mas legible que un
        # mapa de calor difuso con solo 20 puntos.
        fig = px.scatter_mapbox(
            data, lat="latitud", lon="longitud", color="idc_mapa",
            size=np.maximum(data["total_contratado"], 1), color_continuous_scale=COLOR_SCALE,
            range_color=rango_color, size_max=38, zoom=9.3, center={"lat": 4.65, "lon": -74.1},
            mapbox_style="open-street-map", text="localidad_limpia", hover_name="localidad_limpia",
            hover_data={"idc": True, "idc_mapa": False, "latitud": False, "longitud": False},
            labels={"idc_mapa": titulo_color},
        )
        fig.update_traces(textposition="top center", textfont=dict(size=10))
        modo = "circulos por localidad (no se pudo cargar el mapa de poligonos oficial)"

    fig.update_layout(height=620, margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar_title=titulo_color, dragmode="pan", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
    st.caption(f"Modo de mapa activo: {modo}. Corte mostrado: {corte_label}.")

    st.subheader("Que nos dice el mapa (analisis geografico)", anchor=False, divider="orange")
    referencia = idc_data.dropna(subset=["idc", "latitud"]) if "latitud" in idc_data.columns else idc_data.dropna(subset=["idc"])

    if "latitud" in idc_data.columns and not referencia.empty:
        mediana_lat = idc_data["latitud"].median()
        norte = referencia[referencia["latitud"] > mediana_lat]
        sur = referencia[referencia["latitud"] <= mediana_lat]
        idc_norte = norte["idc"].mean() if not norte.empty else float("nan")
        idc_sur = sur["idc"].mean() if not sur.empty else float("nan")
        texto_geo = (
            f"En el corte de **{corte_label}**, las localidades del **norte** de Bogota "
            f"tienen un IDC promedio de **{idc_norte:.2f}**, mientras que las del **sur** "
            f"tienen **{idc_sur:.2f}**. "
        )
        if not np.isnan(idc_norte) and not np.isnan(idc_sur):
            if idc_norte > idc_sur:
                texto_geo += "El norte descentralizo un poco mas su contratacion que el sur en este corte."
            elif idc_sur > idc_norte:
                texto_geo += "El sur descentralizo un poco mas su contratacion que el norte en este corte."
            else:
                texto_geo += "Norte y sur se comportaron de forma muy parecida en este corte."
    else:
        texto_geo = "No hay suficiente informacion geografica para comparar zonas de la ciudad en este corte."

    _explica(
        texto_geo,
        "El color representa `idc` (acotado a un maximo de 1.0 para no distorsionar la "
        "escala de color); en el modo de circulos, el tamano representa `total_contratado`. "
        "El analisis norte/sur divide las localidades por la mediana de su latitud de "
        "centroide y compara el promedio de `idc` entre ambos grupos: una forma simple, "
        "no un modelo espacial formal (no incluye autocorrelacion espacial ni pruebas de "
        "significancia estadistica).",
    )


# ------------------------------------------------------------------
# Interpretacion general
# ------------------------------------------------------------------

def interpretacion_general(idc_data, corte_label: str):
    st.subheader("Que significa todo esto, en facil", anchor=False, divider="orange")
    urbanas = idc_data[~idc_data["es_outlier"]] if "es_outlier" in idc_data.columns else idc_data
    validos = urbanas.dropna(subset=["idc"])
    if not validos.empty:
        top = validos.sort_values("idc", ascending=False).iloc[0]
        bottom = validos.sort_values("idc", ascending=True).iloc[0]
        frase_top = f"En el corte de **{corte_label}**, la localidad urbana que mas contrato via su fondo local fue **{top['localidad_limpia'].title()}**."
        frase_bottom = f"La que menos lo hizo fue **{bottom['localidad_limpia'].title()}**."
    else:
        frase_top = f"En el corte de **{corte_label}** no hay suficiente informacion para identificar la localidad mas descentralizada."
        frase_bottom = ""

    st.markdown(
        f"""
Piensa en cada localidad de Bogota como si tuviera su propia "alcancia" para
gastar en su barrio: eso es el **Fondo de Desarrollo Local**.

Ademas de esa alcancia propia, muchas entidades de la ciudad (salud, cultura,
ambiente, movilidad...) tambien contratan gente que vive en esa localidad.

El **IDC** compara: *de todo lo que se contrato con gente domiciliada en una
localidad, cuanto vino de la alcancia propia y cuanto vino de entidades
grandes de la ciudad.*

- IDC **alto** (cerca de 1): la localidad maneja bastante de su contratacion
  con su propia alcancia.
- IDC **bajo** (cerca de 0): casi toda la contratacion vino de entidades
  grandes de la ciudad.

{frase_top} {frase_bottom}

Recuerda: esto se mide por donde vive el contratista, no necesariamente por
donde se presta el servicio, asi que tomalo como una senal para investigar
mas, no como una conclusion definitiva.
        """
    )
