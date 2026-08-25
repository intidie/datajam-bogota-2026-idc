"""
poblacion_data.py
------------------
Carga y procesamiento de la Fuente 4: proyecciones/retroproyecciones de
poblacion por localidad 2005-2035 (Secretaria Distrital de Planeacion,
archivo .ods "202503_localidad_proyeccion_retroproyeccion_poblacion_
2005_2035.ods").

Se usa para:
  - Dar contexto demografico a cada localidad (poblacion total, hombres,
    mujeres) en el año del corte analizado.
  - Calcular indicadores "per capita" (p. ej. contratistas o dinero
    contratado por cada 1.000 habitantes), que permiten comparar
    localidades de tamaños muy distintos de forma mas justa que los
    valores absolutos.
  - Rellenar vacios de la tabla estandarizada: localidades que no
    aparecen en los cortes de Contratistas/TNP de un mes (por ejemplo,
    porque no tuvieron contratistas domiciliados alli ese corte) igual
    quedan con su poblacion, en vez de desaparecer de mapas y graficos.

El archivo NO es una tabla plana lista para usar:
  - Las primeras 4 filas son titulo/notas (la fila de encabezados reales
    esta en la posicion 5, es decir header=4 con pandas).
  - Cada localidad aparece dos veces por año: una fila "Cabecera
    Municipal" (urbano) y otra "Centro Poblado y Rural Disperso" (rural);
    hay que sumarlas para obtener la poblacion total de la localidad.
  - Trae un año por fila desde 2005 hasta 2035 (retroproyeccion +
    proyeccion), asi que hay que filtrar el año que corresponde al corte
    analizado (2022 por defecto, el vigencia de esta app).
"""

import io

import pandas as pd
import streamlit as st

import pipeline

ANIO_POR_DEFECTO = 2022


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def cargar_poblacion_ods(file_bytes: bytes) -> pd.DataFrame:
    """Lee el .ods crudo de poblacion por localidad. El encabezado real
    esta en la fila 5 del archivo (header=4, base 0), no en la primera."""
    raw = pd.read_excel(io.BytesIO(file_bytes), engine="odf", sheet_name=0, header=4)
    # Filas totalmente vacias (separadores dentro del archivo original)
    raw = raw.dropna(subset=["Nombre Localidad", "AÑO"])
    raw["AÑO"] = pd.to_numeric(raw["AÑO"], errors="coerce")
    return raw


@st.cache_data(show_spinner=False)
def procesar_poblacion(df_poblacion_raw: pd.DataFrame, anio: int = ANIO_POR_DEFECTO):
    """Agrega por localidad (sumando 'Cabecera Municipal' + 'Centro
    Poblado y Rural Disperso') para el año pedido. Si ese año exacto no
    esta en el archivo, usa el año disponible mas cercano.

    Devuelve (dataframe_agregado, anio_realmente_usado).
    """
    anios_disponibles = sorted(df_poblacion_raw["AÑO"].dropna().unique().tolist())
    if not anios_disponibles:
        return pd.DataFrame(columns=["localidad_limpia", "poblacion_hombres", "poblacion_mujeres", "poblacion_total"]), None

    anio_usado = anio if anio in anios_disponibles else min(anios_disponibles, key=lambda a: abs(a - anio))

    df = df_poblacion_raw[df_poblacion_raw["AÑO"] == anio_usado].copy()
    df["localidad_limpia"] = df["Nombre Localidad"].apply(pipeline.estandarizar_localidad)

    agg = (
        df.groupby("localidad_limpia")
        .agg(
            poblacion_hombres=("Total Hombres", "sum"),
            poblacion_mujeres=("Total Mujeres", "sum"),
            poblacion_total=("Total", "sum"),
        )
        .reset_index()
    )
    return agg, int(anio_usado)
