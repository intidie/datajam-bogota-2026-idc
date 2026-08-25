"""
app.py
------
Indice de Descentralizacion de Contratacion (IDC) - Bogota D.C. (2022)

Dos secciones conectadas por el menu lateral:
  1) Datos: descarga automatica de UN corte mensual (no una suma de
     varios) desde datosabiertos.bogota.gov.co, con opcion de subir
     archivos propios; procesamiento y carga a Supabase.
  2) Analisis: exploracion de datos por localidad, componentes
     principales, mapa interactivo y comparativos.

Pensada para Streamlit Cloud con muchos usuarios simultaneos:
- @st.cache_data para las descargas y el procesamiento pesado.
- @st.cache_resource para el cliente de Supabase y el GeoJSON oficial.
- Sin matplotlib/seaborn: todo Plotly, renderizado del lado del cliente.
"""

import pandas as pd
import streamlit as st

import charts
import data_sources
import geo_data
import pipeline
import poblacion_data
import supabase_utils

st.set_page_config(page_title="IDC Bogota", page_icon=None, layout="wide")

# ------------------------------------------------------------------
# Estilo: diseno mas suave, tarjetas redondeadas, tipografia mas clara
# ------------------------------------------------------------------

st.markdown(
    """
    <style>
    .stApp { background-color: #FAFAF7; }
    h1, h2, h3 { color: #2B2118; }
    [data-testid="stMetric"] {
        background: #FFFFFF;
        border: 1px solid #EFE6DA;
        border-radius: 14px;
        padding: 14px 16px 10px 16px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    [data-testid="stMetricLabel"] { color: #8A7B68; font-size: 0.85rem; }
    [data-testid="stExpander"] { border-radius: 12px; border: 1px solid #EFE6DA; }
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 10px; border: 1px solid #E76F51; color: #E76F51; background: #FFFFFF;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover { background: #E76F51; color: #FFFFFF; }
    section[data-testid="stSidebar"] { background-color: #FBF3EA; }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: 8px 14px; background-color: #F3EBDF; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("IDC Bogota")
seccion = st.sidebar.radio("Navegacion", ["1. Datos", "2. Analisis"], label_visibility="collapsed")
st.sidebar.divider()


def mostrar_descripcion_proyecto():
    st.markdown(
        "**Que es esto?** Esta pagina calcula el **IDC (Indice de Descentralizacion "
        "de Contratacion)** para las 20 localidades de Bogota: un numero que indica "
        "que tanto de la contratacion de cada localidad paso por su propio **Fondo "
        "de Desarrollo Local** (su 'alcancia' propia), en vez de venir de las grandes "
        "entidades del sector central de la ciudad (salud, cultura, movilidad, etc.). "
        "Sirve para explorar, con datos abiertos oficiales, que tan autonoma es cada "
        "localidad en su propia contratacion, con mapas y graficos que cualquiera "
        "puede leer sin ser experto en datos."
    )


def mostrar_limitaciones():
    with st.expander("Limitaciones metodologicas (leer antes de sacar conclusiones)"):
        st.markdown(
            "**1. Un solo corte, no una suma de meses.** Los archivos mensuales de "
            "Contratistas del Distrito son 'fotografias' del estado acumulado a esa "
            "fecha, no movimientos nuevos de cada mes. Sumar varios cortes contaria "
            "varias veces los mismos contratos que siguen vigentes en mas de un "
            "corte, inflando el total. Por eso esta app analiza **un unico corte a "
            "la vez** (por defecto, diciembre, el mas completo del año), en vez de "
            "sumar septiembre a diciembre.\n\n"
            "**2. Talento no Palanca es un reporte por entidad, no por localidad.** "
            "No trae una columna de localidad de residencia por persona. Solo se "
            "puede ubicar geograficamente el subconjunto de entidades que son "
            "'Fondo de Desarrollo Local de <localidad>'; el resto (sector central) "
            "se muestra por separado, por entidad, sin forzarlo dentro de una "
            "localidad que no le corresponde.\n\n"
            "**3. Domicilio del contratista, no lugar de ejecucion.** El IDC usa la "
            "localidad donde vive el contratista (el unico dato geografico "
            "disponible), no donde efectivamente se presta el servicio. Esto puede "
            "sub-representar localidades perifericas y sobre-representar las que "
            "tienen mas infraestructura corporativa. Es un proxy razonable, no una "
            "medida exacta de ejecucion territorial.\n\n"
            "**4. Escalas distintas.** El sector central maneja muchisimo mas "
            "volumen que los Fondos de Desarrollo Local; mezclarlos en un solo "
            "grafico de valores absolutos puede ser enganoso, por eso el IDC "
            "tambien se muestra como porcentaje/proporcion en vez de solo en pesos.\n\n"
            "**5. Poblacion de un solo año, contratacion de un solo corte.** Los "
            "indicadores per capita dividen los datos del corte mensual elegido "
            "(2022) entre la poblacion proyectada del año que selecciones (por "
            "defecto 2022): no son series de tiempo, son una foto de un año contra "
            "otra. Ademas, la poblacion esta a nivel de localidad completa, no por "
            "barrio, asi que dentro de una misma localidad puede haber zonas muy "
            "distintas entre si."
        )


# ==================================================================
# SECCION 1 -- Datos: descarga, procesamiento, exportacion / Supabase
# ==================================================================

if seccion.startswith("1"):
    st.title("1. Obtencion y procesamiento de datos")
    mostrar_descripcion_proyecto()
    st.write("")

    st.markdown(
        "**Como se estandarizan los datos?** Cada archivo mensual de Datos Abiertos "
        "de Bogota trae, en la practica, varias dificultades tipicas de este tipo de "
        "reportes: separadores distintos (`,` `;` `\\t`), codificaciones de texto "
        "distintas (algunos archivos usan tildes en UTF-8, otros en una codificacion "
        "antigua tipo CP850), nombres de localidad escritos de formas distintas "
        "('Bogota' vs 'Bogotá', con o sin tildes, con mayusculas mezcladas), montos "
        "de dinero escritos como texto con simbolos de moneda y separadores de miles "
        "('$ 1.234.567' o '$1,234,567.00'), filas de encabezado y notas antes de la "
        "tabla real, y filas de 'Total general' que no son datos. Puedes subir "
        "cualquier archivo del portal de Datos Abiertos de Bogota (o el tuyo propio) "
        "y esta app se encarga de limpiarlo y estandarizarlo con las mismas reglas."
    )

    with st.expander("Usar mis propios archivos en vez de los oficiales (opcional)"):
        st.caption(
            "Si subes un archivo aqui, reemplaza por completo la descarga automatica "
            "para esa fuente en el corte que elijas abajo."
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            f_contratistas = st.file_uploader("Contratistas del Distrito (opcional)", type=["csv", "xlsx"])
        with c2:
            f_tnp = st.file_uploader("Talento no Palanca (opcional)", type=["csv", "xlsx"])
        with c3:
            f_poblacion = st.file_uploader(
                "Poblacion por localidad 2005-2035, SDP (opcional, .ods)", type=["ods"],
                help="Se usa para calcular indicadores per capita y para que todas las localidades "
                     "aparezcan en mapas/tablas aunque un corte no tenga contratistas registrados.",
            )

    anio_poblacion_deseado = st.number_input(
        "Año de poblacion a usar (para los indicadores per capita)",
        min_value=2005, max_value=2035, value=poblacion_data.ANIO_POR_DEFECTO, step=1,
        help="Si el .ods no trae exactamente este año, se usa el mas cercano disponible.",
    )

    corte = st.selectbox(
        "Corte a descargar y procesar",
        options=[9, 10, 11, 12], index=3, format_func=lambda m: data_sources.MESES_NOMBRE[m],
        help="Cada corte es un acumulado a esa fecha. No se suman varios cortes (ver Limitaciones metodologicas).",
    )

    if st.button("Descargar y calcular el IDC", type="primary"):
        with st.spinner(f"Descargando y procesando el corte de {data_sources.MESES_NOMBRE[corte]}..."):
            errores_totales = []

            if f_contratistas is not None:
                df_contratistas = pipeline.cargar_dataset(f_contratistas.getvalue(), f_contratistas.name)
                df_contratistas["mes_origen"] = corte
            else:
                df_contratistas, err_c = data_sources.cargar_corte_contratistas(corte)
                if err_c:
                    errores_totales.append(err_c)

            if f_tnp is not None:
                df_tnp = pipeline.cargar_tnp_archivo(f_tnp.getvalue(), f_tnp.name)
                df_tnp["mes_origen"] = corte
            else:
                df_tnp, err_t = data_sources.cargar_corte_tnp(corte)
                if err_t:
                    errores_totales.append(err_t)

            if f_poblacion is not None:
                try:
                    df_poblacion_raw = poblacion_data.cargar_poblacion_ods(f_poblacion.getvalue())
                    st.session_state["df_poblacion_raw"] = df_poblacion_raw
                except Exception as e:
                    errores_totales.append(f"No se pudo leer el archivo de poblacion: {e}")

            st.session_state["anio_poblacion_deseado"] = anio_poblacion_deseado

            if df_contratistas is not None and df_tnp is not None:
                st.session_state["df_contratistas_raw"] = df_contratistas
                st.session_state["df_tnp_raw"] = df_tnp
                st.session_state["corte_actual"] = corte
            st.session_state["errores_descarga"] = errores_totales

        if df_contratistas is not None and df_tnp is not None:
            st.success(f"Listo: {len(df_contratistas):,} filas de Contratistas y {len(df_tnp):,} filas de Talento no Palanca (corte {data_sources.MESES_NOMBRE[corte]}).")
        else:
            st.error("No se pudo completar la descarga de alguna fuente. Revisa los avisos abajo.")

    if st.session_state.get("errores_descarga"):
        with st.expander("Avisos durante la descarga"):
            for a in st.session_state["errores_descarga"]:
                st.warning(a)

    mostrar_limitaciones()

    if "df_contratistas_raw" in st.session_state:
        df_contratistas = st.session_state["df_contratistas_raw"]
        df_tnp = st.session_state["df_tnp_raw"]
        corte_label = data_sources.MESES_NOMBRE[st.session_state.get("corte_actual", 12)]

        agg_contratistas, sin_loc_c, cols_c = pipeline.procesar_contratistas(df_contratistas)
        agg_fdl, sin_asignar_fdl = pipeline.procesar_fondos_desarrollo_local(df_contratistas)
        agg_talento, sin_loc_t, cols_t, tabla_entidad = pipeline.procesar_talento(df_tnp)

        agg_poblacion, anio_poblacion_usado = None, None
        if "df_poblacion_raw" in st.session_state:
            agg_poblacion, anio_poblacion_usado = poblacion_data.procesar_poblacion(
                st.session_state["df_poblacion_raw"],
                st.session_state.get("anio_poblacion_deseado", poblacion_data.ANIO_POR_DEFECTO),
            )

        idc_data = pipeline.construir_idc(
            agg_contratistas, agg_fdl, agg_talento, geo_data.GEO_LOCALIDADES,
            agg_poblacion=agg_poblacion, anio_poblacion=anio_poblacion_usado,
        )
        st.session_state["idc_data_completo"] = idc_data
        st.session_state["tabla_entidad_tnp"] = tabla_entidad

        st.divider()
        st.subheader("Tabla consolidada (idc_data)", anchor=False, divider="orange")
        st.caption(f"Corte: {corte_label} de 2022")
        st.dataframe(idc_data, use_container_width=True)

        with st.expander("Que esta pasando por dentro (detalle tecnico)"):
            st.markdown(
                "- **Contratistas del Distrito**: se agrupa por `Localidad`, sumando "
                "`Valor total reportado` (-> `total_contratado`) y `Contratistas` "
                "(-> `num_contratos`), usando solo el corte seleccionado.\n"
                "- **Fondos de Desarrollo Local (proxy de presupuesto)**: se filtra "
                "`Sector == 'Localidades'`, se extrae la localidad del nombre de la "
                "`Entidad` y se suma `Valor total reportado` "
                "(-> `total_presupuesto_planeado` / `total_contratado_directo`).\n"
                "- **Talento no Palanca**: reporte por entidad; se extrae la localidad "
                "solo de las entidades 'Fondo de Desarrollo Local de <localidad>' "
                "(-> `num_postulantes`); el resto queda en una tabla por entidad aparte.\n"
                "- **IDC** = `total_contratado_directo / total_contratado`, acotado a 1.0.\n"
                "- **Poblacion (Fuente 4, SDP)**: se suman las filas 'Cabecera Municipal' y "
                "'Centro Poblado y Rural Disperso' del año elegido, por localidad "
                "(-> `poblacion_total`, `poblacion_hombres`, `poblacion_mujeres`), y se derivan "
                "`contratos_por_1000_hab`, `contratado_per_capita` y "
                "`postulantes_tnp_por_1000_hab`.\n\n"
                f"Columnas detectadas en Contratistas: `{cols_c}`. "
                f"Columnas detectadas en Talento no Palanca: `{cols_t}`."
            )

        st.subheader("Control de calidad", anchor=False, divider="orange")
        if agg_poblacion is not None and not agg_poblacion.empty:
            qc1, qc2, qc3, qc4 = st.columns(4)
            qc4.metric("Localidades con poblacion cargada", f"{agg_poblacion['localidad_limpia'].nunique():,} / 20")
        else:
            qc1, qc2, qc3 = st.columns(3)
        qc1.metric("Contratistas sin localidad", f"{sin_loc_c:,}")
        qc2.metric("Filas de Fondos Locales sin asignar", f"{sin_asignar_fdl:,}")
        qc3.metric("TNP no geolocalizable (sector central)", f"{sin_loc_t:,}")
        st.caption("Estas filas se descartaron del calculo por localidad en vez de forzarlas dentro de una que no les corresponde.")
        if agg_poblacion is None:
            st.caption("Sube el archivo .ods de poblacion (arriba, seccion de archivos propios) para habilitar indicadores per capita.")

        st.divider()
        st.subheader("Exportar o publicar en Supabase", anchor=False, divider="orange")
        colA, colB = st.columns(2)
        with colA:
            st.markdown("**Descargar**")
            st.download_button(
                "Descargar CSV estandarizado", data=idc_data.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"idc_localidades_2022_{corte_label.lower()}.csv", mime="text/csv", use_container_width=True,
            )
            st.download_button(
                "Descargar Parquet", data=idc_data.to_parquet(index=False),
                file_name=f"idc_localidades_2022_{corte_label.lower()}.parquet", mime="application/octet-stream", use_container_width=True,
            )
        with colB:
            st.markdown("**Subir a Supabase**")
            st.caption("Credenciales leidas desde st.secrets (nube) o .env (local). Nunca se hardcodean.")
            if st.button("Subir a Supabase (upsert por cod_localidad)", use_container_width=True):
                try:
                    with st.spinner("Subiendo a Supabase..."):
                        filas = supabase_utils.subir_idc_a_supabase(idc_data)
                    st.success(f"{filas} filas confirmadas en la tabla idc_data de Supabase.")
                except Exception as e:
                    st.error(f"No se pudo subir a Supabase: {e}")
    else:
        st.info("Elige un corte y presiona el boton de arriba para descargar y calcular el IDC.")

# ==================================================================
# SECCION 2 -- Analisis: exploracion, PCA, mapa y comparativos
# ==================================================================

else:
    st.title("2. Analisis, mapa y estadisticas")
    mostrar_descripcion_proyecto()
    st.write("")

    tiene_datos = "idc_data_completo" in st.session_state

    if not tiene_datos:
        st.warning("Primero descarga los datos en la seccion '1. Datos', o carga un archivo ya estandarizado abajo.")
        f = st.file_uploader("Cargar idc_localidades_2022.csv o .parquet ya calculado", type=["csv", "parquet"])
        if f is not None:
            st.session_state["idc_data_completo"] = pd.read_parquet(f) if f.name.endswith(".parquet") else pd.read_csv(f)
            st.session_state["corte_actual"] = None
            tiene_datos = True

    if tiene_datos:
        idc_data = st.session_state["idc_data_completo"]
        tabla_entidad = st.session_state.get("tabla_entidad_tnp")
        corte = st.session_state.get("corte_actual")
        corte_label = data_sources.MESES_NOMBRE[corte] if corte else "archivo cargado"

        filas_sin_localidad = {}
        if "df_contratistas_raw" in st.session_state:
            _, sin_loc_c, _ = pipeline.procesar_contratistas(st.session_state["df_contratistas_raw"])
            _, sin_asignar_fdl = pipeline.procesar_fondos_desarrollo_local(st.session_state["df_contratistas_raw"])
            _, sin_loc_t, _, _ = pipeline.procesar_talento(st.session_state["df_tnp_raw"])
            filas_sin_localidad = {"Contratistas": sin_loc_c, "Fondos Locales": sin_asignar_fdl, "TNP sector central": sin_loc_t}

        st.sidebar.subheader("Mapa (opcional)")
        geojson_subido = st.sidebar.file_uploader("GeoJSON alterno de localidades", type=["geojson", "json"])
        geojson_obj = geo_data.cargar_geojson_subido(geojson_subido.getvalue()) if geojson_subido is not None else geo_data.cargar_geojson_oficial()

        tab_resumen, tab_eda, tab_pca, tab_mapa, tab_comparativas = st.tabs(
            ["Resumen", "Analisis descriptivo", "Componentes principales", "Mapa y geografia", "Comparativas"]
        )

        with tab_resumen:
            charts.mostrar_metricas(idc_data, corte_label)
            st.divider()
            charts.interpretacion_general(idc_data, corte_label)

        with tab_eda:
            charts.analisis_exploratorio(idc_data, filas_sin_localidad)

        with tab_pca:
            charts.analisis_componentes_principales(idc_data)

        with tab_mapa:
            charts.mapa_geografico(idc_data, geojson_obj, corte_label)

        with tab_comparativas:
            charts.grafico_ranking(idc_data)
            st.divider()
            charts.grafico_comparativo(idc_data)
            st.divider()
            charts.grafico_talento(idc_data, tabla_entidad)
