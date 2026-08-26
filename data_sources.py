"""
data_sources.py
----------------
Descarga de las fuentes oficiales de Datos Abiertos de Bogotá.

Nota metodológica importante (corregida tras revisión): los archivos
mensuales de Contratistas del Distrito son "cortes" (fotografías del
estado acumulado a esa fecha), no movimientos nuevos de cada mes. Sumar
varios cortes cuenta varias veces los mismos contratos que siguen
vigentes en más de un corte, inflando artificialmente los totales. Por
eso esta versión NO suma meses: se analiza siempre UN SOLO corte a la
vez (por defecto, el de diciembre, el más completo del año).

Fuente 1: Caracterización de los Contratistas del Distrito (SIDEAP/DASCD),
          4 cortes mensuales (septiembre a diciembre de 2022).
Fuente 2: Banco de Proveedores - Talento no Palanca, 4 cortes mensuales.
          Es un reporte por ENTIDAD (no trae localidad de residencia por
          persona); ver pipeline.procesar_talento().
Fuente 3 (proxy de presupuesto/ejecución local): subconjunto de la
          Fuente 1 donde Sector == "Localidades" (Fondos de Desarrollo
          Local), del mismo corte seleccionado.
"""

import urllib.request
from urllib.error import URLError

import streamlit as st

import pipeline

MESES_NOMBRE = {9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"}

CONTRATISTAS_URLS = {
    9: "https://datosabiertos.bogota.gov.co/dataset/d3ca4e99-c8fd-4330-8968-2a7f7c5dfecb/resource/22110184-50d4-475f-a73c-368aa8cdcd06/download/contratistas-2022-09.csv",
    10: "https://datosabiertos.bogota.gov.co/dataset/d3ca4e99-c8fd-4330-8968-2a7f7c5dfecb/resource/b3b83e1c-d0ff-4d40-a589-b44abe36e0f9/download/contratistas-2022-10.csv",
    11: "https://datosabiertos.bogota.gov.co/dataset/d3ca4e99-c8fd-4330-8968-2a7f7c5dfecb/resource/88011c84-28af-4334-9e74-ce015c98541a/download/contratistas-2022-11.csv",
    12: "https://datosabiertos.bogota.gov.co/dataset/d3ca4e99-c8fd-4330-8968-2a7f7c5dfecb/resource/3eda897c-9047-4aed-adec-8701309c6dae/download/contratistas-2022-12.csv",
}

TNP_URLS = {
    9: "https://datosabiertos.bogota.gov.co/dataset/6b242132-ceb6-4e8a-a6e8-69d7ebf020d7/resource/83851ebf-50b0-4249-a84f-d15521cc1284/download/tnp-septiembre.csv",
    10: "https://datosabiertos.bogota.gov.co/dataset/6b242132-ceb6-4e8a-a6e8-69d7ebf020d7/resource/0486e5af-b5ea-4287-97c8-d0b6f37f0d43/download/tnp-octubre.csv",
    11: "https://datosabiertos.bogota.gov.co/dataset/6b242132-ceb6-4e8a-a6e8-69d7ebf020d7/resource/2b59fe36-7eb3-428d-861c-098d31ebfca5/download/tnp-noviembre.csv",
    12: "https://datosabiertos.bogota.gov.co/dataset/6b242132-ceb6-4e8a-a6e8-69d7ebf020d7/resource/ac98c249-d5b1-4412-9d63-26aba166cc84/download/tnp-diciembre.csv",
}


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def _descargar_bytes(url: str, timeout: int = 40) -> bytes:
    """Descarga un archivo por HTTP con un User-Agent explicito (algunos
    portales de datos abiertos bloquean peticiones sin uno)."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (IDC-Bogota-App)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def cargar_corte_contratistas(mes: int):
    """Descarga (o recupera de cache) UN SOLO corte mensual de
    Contratistas del Distrito. Devuelve (dataframe, error_o_None)."""
    try:
        contenido = _descargar_bytes(CONTRATISTAS_URLS[mes])
        df = pipeline.cargar_dataset(contenido, f"contratistas-2022-{mes:02d}.csv")
        df["mes_origen"] = mes
        return df, None
    except (URLError, TimeoutError, Exception) as e:  # noqa: BLE001
        return None, f"No se pudo descargar Contratistas de {MESES_NOMBRE[mes]}: {e}"


@st.cache_data(show_spinner=False, ttl=6 * 3600)
def cargar_corte_tnp(mes: int):
    """Descarga (o recupera de cache) UN SOLO corte mensual de Talento no
    Palanca. Devuelve (dataframe, error_o_None)."""
    try:
        contenido = _descargar_bytes(TNP_URLS[mes])
        df = pipeline.cargar_tnp_archivo(contenido, f"tnp-2022-{mes:02d}.csv")
        df["mes_origen"] = mes
        return df, None
    except (URLError, TimeoutError, Exception) as e:  # noqa: BLE001
        return None, f"No se pudo descargar Talento no Palanca de {MESES_NOMBRE[mes]}: {e}"
