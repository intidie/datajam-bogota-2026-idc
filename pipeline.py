"""
pipeline.py
-----------
Limpieza, normalizacion de localidades y calculo del Indice de
Descentralizacion de Contratacion (IDC), adaptado a las nuevas fuentes:

Fuente 1 (Contratistas del Distrito): columnas Sector, Entidad, Localidad,
    Contratistas, Valor total reportado.
Fuente 2 (Talento no Palanca): columna LocalidadResidencia.
Fuente 3 (proxy de presupuesto local): subconjunto de la Fuente 1 con
    Sector == "Localidades", agrupado por la localidad que corresponde a
    cada Fondo de Desarrollo Local (extraida del nombre de la Entidad).

Formula usada para el IDC (ver nota de transparencia en la app):
    IDC = dinero ejecutado por el Fondo de Desarrollo Local de la localidad
          / dinero total contratado por contratistas de esa localidad
          (todos los sectores, no solo el fondo local)
"""

import io
import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

# ------------------------------------------------------------------
# Carga robusta de archivos (CSV/XLSX), usada tanto para archivos subidos
# como para los descargados de datosabiertos.bogota.gov.co
# ------------------------------------------------------------------

@st.cache_data(show_spinner=False, ttl=3600)
def cargar_dataset(file_bytes: bytes, filename: str, skiprows: int = 0) -> pd.DataFrame:
    suffix = filename.lower().split(".")[-1]

    if suffix in ("xlsx", "xls"):
        return pd.read_excel(io.BytesIO(file_bytes), skiprows=skiprows)

    separators_to_try = [",", ";", "\t", "|"]
    encodings_to_try = ["utf-8-sig", "latin-1"]

    for sep in separators_to_try:
        for enc in encodings_to_try:
            try:
                df = pd.read_csv(
                    io.BytesIO(file_bytes), sep=sep, encoding=enc,
                    low_memory=False, skiprows=skiprows,
                )
                if df.shape[1] > 1:
                    return df
            except Exception:
                continue

    raise ValueError(
        f"No se pudo leer el archivo '{filename}'. Ajusta el separador, el "
        f"encoding o el numero de filas a saltar."
    )


# ------------------------------------------------------------------
# Normalizacion de nombres de localidad (20 localidades oficiales de Bogota)
# ------------------------------------------------------------------

def limpiar_texto_localidad(texto):
    if pd.isna(texto):
        return np.nan
    texto = str(texto).upper().strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


LOCALIDADES_OFICIALES = [
    "USAQUEN", "CHAPINERO", "SANTA FE", "SAN CRISTOBAL", "USME",
    "TUNJUELITO", "BOSA", "KENNEDY", "FONTIBON", "ENGATIVA",
    "SUBA", "BARRIOS UNIDOS", "TEUSAQUILLO", "LOS MARTIRES",
    "ANTONIO NARIÑO", "PUENTE ARANDA", "LA CANDELARIA",
    "RAFAEL URIBE URIBE", "CIUDAD BOLIVAR", "SUMAPAZ",
]
LOCALIDADES_OFICIALES = [limpiar_texto_localidad(l) for l in LOCALIDADES_OFICIALES]

MAPA_VARIANTES_LOCALIDAD = {
    "USAQUEN": "USAQUEN", "USAQUÉN": "USAQUEN", "01 USAQUEN": "USAQUEN",
    "CHAPINERO": "CHAPINERO", "02 CHAPINERO": "CHAPINERO",
    "SANTA FE": "SANTA FE", "SANTAFE": "SANTA FE", "SANTA FÉ": "SANTA FE",
    "SAN CRISTOBAL": "SAN CRISTOBAL", "SAN CRISTÓBAL": "SAN CRISTOBAL",
    "USME": "USME",
    "TUNJUELITO": "TUNJUELITO", "TUNJUELO": "TUNJUELITO",
    "BOSA": "BOSA",
    "KENNEDY": "KENNEDY",
    "FONTIBON": "FONTIBON", "FONTIBÓN": "FONTIBON",
    "ENGATIVA": "ENGATIVA", "ENGATIVÁ": "ENGATIVA",
    "SUBA": "SUBA",
    "BARRIOS UNIDOS": "BARRIOS UNIDOS",
    "TEUSAQUILLO": "TEUSAQUILLO",
    "LOS MARTIRES": "LOS MARTIRES", "MARTIRES": "LOS MARTIRES", "LOS MÁRTIRES": "LOS MARTIRES",
    "MÁRTIRES": "LOS MARTIRES",
    "ANTONIO NARINO": "ANTONIO NARINO", "ANTONIO NARIÑO": "ANTONIO NARINO",
    "PUENTE ARANDA": "PUENTE ARANDA",
    "LA CANDELARIA": "LA CANDELARIA", "CANDELARIA": "LA CANDELARIA",
    "RAFAEL URIBE URIBE": "RAFAEL URIBE URIBE", "RAFAEL URIBE": "RAFAEL URIBE URIBE",
    "CIUDAD BOLIVAR": "CIUDAD BOLIVAR", "CIUDAD BOLÍVAR": "CIUDAD BOLIVAR",
    "SUMAPAZ": "SUMAPAZ",
    "SIN LOCALIZACION": "SIN INFORMACION", "SIN INFORMACION": "SIN INFORMACION",
    "SIN INFORMACIÓN": "SIN INFORMACION",
    "NO APLICA": "SIN INFORMACION", "N A": "SIN INFORMACION",
}


def estandarizar_localidad(texto):
    limpio = limpiar_texto_localidad(texto)
    if limpio is None or limpio == "" or pd.isna(limpio):
        return "SIN INFORMACION"
    return MAPA_VARIANTES_LOCALIDAD.get(limpio, limpio)


LOCALIDADES_PARA_EXTRACCION = LOCALIDADES_OFICIALES + ["CANDELARIA"]


def extraer_localidad_de_entidad(entidad_texto):
    """Busca dentro del nombre de una Entidad (p. ej. 'Fondo de Desarrollo
    Local de Kennedy') cual de las 20 localidades oficiales menciona.
    Incluye 'Candelaria' (sin el articulo 'La') porque asi aparece en los
    nombres reales de las entidades de los Fondos de Desarrollo Local."""
    norm = limpiar_texto_localidad(entidad_texto)
    if not norm:
        return None
    for loc in sorted(LOCALIDADES_PARA_EXTRACCION, key=len, reverse=True):
        if loc in norm:
            return MAPA_VARIANTES_LOCALIDAD.get(loc, loc)
    return None


# ------------------------------------------------------------------
# Limpieza financiera y deteccion flexible de columnas
# ------------------------------------------------------------------

def limpiar_monto(valor):
    if pd.isna(valor):
        return np.nan
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip()
    texto = re.sub(r"[^\d,.\-]", "", texto)
    if texto == "":
        return np.nan
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        partes = texto.split(",")
        if len(partes[-1]) == 3:
            texto = texto.replace(",", "")
        else:
            texto = texto.replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return np.nan


def _limpiar_numero_tnp(valor):
    """Convierte '1,353' -> 1353 y '-' (sin dato) -> 0, como vienen los
    conteos en los reportes de Talento no Palanca."""
    if pd.isna(valor):
        return 0
    texto = str(valor).strip().replace(",", "").replace(".", "")
    if texto in ("", "-"):
        return 0
    try:
        return int(float(texto))
    except ValueError:
        return 0


@st.cache_data(show_spinner=False, ttl=3600)
def cargar_tnp_archivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Carga un archivo de 'Banco de Proveedores - Talento no Palanca'.

    Este reporte NO es una tabla plana: trae 3 filas de notas/encabezado
    antes de la tabla real, va codificado en CP850 (no UTF-8/Latin-1) y
    termina con una fila de 'Total general' que hay que descartar. La
    tabla esta organizada por ENTIDAD, no por localidad.
    """
    df = None
    for enc in ("cp850", "latin-1", "utf-8-sig"):
        try:
            candidato = pd.read_csv(io.BytesIO(file_bytes), sep=";", skiprows=3, encoding=enc)
            if candidato.shape[1] > 3:
                df = candidato
                break
        except Exception:
            continue
    if df is None:
        raise ValueError(f"No se pudo leer el archivo de Talento no Palanca '{filename}'.")

    df = df.rename(columns={df.columns[0]: "Entidad"})
    df = df[df["Entidad"].notna()]
    df = df[~df["Entidad"].astype(str).str.strip().str.lower().str.startswith("total")]
    return df.reset_index(drop=True)


def encontrar_columna(df: pd.DataFrame, candidatos: list):
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidatos:
        for lower, original in cols_lower.items():
            if cand.lower() in lower:
                return original
    return None


# ------------------------------------------------------------------
# Fuente 1 -- Contratistas del Distrito: total contratado por localidad
# ------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def procesar_contratistas(df_contratistas: pd.DataFrame):
    col_localidad = encontrar_columna(df_contratistas, ["localidad"])
    col_valor = encontrar_columna(df_contratistas, ["valor total reportado", "valor_total_reportado", "valor"])
    col_contratistas = encontrar_columna(df_contratistas, ["contratistas"])

    df = df_contratistas.copy()
    df["localidad_limpia"] = df[col_localidad].apply(estandarizar_localidad) if col_localidad else "SIN INFORMACION"
    filas_sin_localidad = int((df["localidad_limpia"] == "SIN INFORMACION").sum())

    df["valor_num"] = df[col_valor].apply(limpiar_monto) if col_valor else np.nan
    df["contratistas_num"] = pd.to_numeric(df[col_contratistas], errors="coerce").fillna(0) if col_contratistas else 0

    agg = (
        df[df["localidad_limpia"] != "SIN INFORMACION"]
        .groupby("localidad_limpia")
        .agg(total_contratado=("valor_num", "sum"), num_contratos=("contratistas_num", "sum"))
        .reset_index()
    )

    cols_detectadas = {"localidad": col_localidad, "valor": col_valor, "contratistas": col_contratistas}
    return agg, filas_sin_localidad, cols_detectadas


# ------------------------------------------------------------------
# Fuente 3 -- proxy de presupuesto/ejecucion local (Fondos de Desarrollo Local)
# ------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def procesar_fondos_desarrollo_local(df_contratistas: pd.DataFrame):
    col_sector = encontrar_columna(df_contratistas, ["sector"])
    col_entidad = encontrar_columna(df_contratistas, ["entidad"])
    col_valor = encontrar_columna(df_contratistas, ["valor total reportado", "valor_total_reportado", "valor"])

    if col_sector is None or col_entidad is None or col_valor is None:
        return pd.DataFrame(columns=["localidad_limpia", "total_presupuesto_planeado", "total_contratado_directo"]), 0

    subset = df_contratistas[df_contratistas[col_sector].astype(str).str.strip().str.upper() == "LOCALIDADES"].copy()
    subset["localidad_fdl"] = subset[col_entidad].apply(extraer_localidad_de_entidad)
    filas_sin_asignar = int(subset["localidad_fdl"].isna().sum())
    subset = subset.dropna(subset=["localidad_fdl"])
    subset["valor_num"] = subset[col_valor].apply(limpiar_monto)

    agg = (
        subset.groupby("localidad_fdl")
        .agg(total_presupuesto_planeado=("valor_num", "sum"))
        .reset_index()
        .rename(columns={"localidad_fdl": "localidad_limpia"})
    )
    # El mismo monto se usa como "contratado de forma directa/descentralizada"
    # (ver nota de transparencia sobre la definicion del IDC en esta version).
    agg["total_contratado_directo"] = agg["total_presupuesto_planeado"]

    return agg, filas_sin_asignar


# ------------------------------------------------------------------
# Fuente 2 -- Talento no Palanca: postulantes por localidad
# ------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def procesar_talento(df_talento: pd.DataFrame):
    """Fuente 2 (Talento no Palanca).

    Nota metodologica importante: este reporte esta agregado por ENTIDAD,
    no trae una columna de localidad de residencia por persona. Solo se
    puede ubicar geograficamente el subconjunto de entidades que son
    'Fondo de Desarrollo Local de <localidad>'; el resto (entidades del
    sector central: salud, cultura, movilidad, etc.) se reporta aparte, a
    nivel de entidad, sin forzarlo dentro de una localidad que no le
    corresponde.
    """
    col_entidad = "Entidad" if "Entidad" in df_talento.columns else encontrar_columna(df_talento, ["entidad"])
    col_contratistas = encontrar_columna(
        df_talento, ["no contratistas registrados", "contratistas registrados", "contratistas"]
    )

    df = df_talento.copy()
    df["contratistas_tnp"] = df[col_contratistas].apply(_limpiar_numero_tnp) if col_contratistas else 0
    df["localidad_fdl"] = df[col_entidad].apply(extraer_localidad_de_entidad) if col_entidad else None

    tabla_entidad = (
        df[[col_entidad, "contratistas_tnp"]]
        .rename(columns={col_entidad: "entidad", "contratistas_tnp": "num_contratistas_tnp"})
        .sort_values("num_contratistas_tnp", ascending=False)
        .reset_index(drop=True)
    )

    subset_fdl = df.dropna(subset=["localidad_fdl"])
    agg = (
        subset_fdl.groupby("localidad_fdl")
        .agg(num_postulantes=("contratistas_tnp", "sum"))
        .reset_index()
        .rename(columns={"localidad_fdl": "localidad_limpia"})
    )

    # No es un "dato faltante" en el sentido de error: son entidades del
    # sector central que legitimamente no pertenecen a ninguna localidad.
    filas_sin_localidad = int(df[col_entidad].notna().sum() - len(subset_fdl)) if col_entidad else 0

    cols_detectadas = {"entidad": col_entidad, "contratistas": col_contratistas}
    return agg, filas_sin_localidad, cols_detectadas, tabla_entidad


# ------------------------------------------------------------------
# Consolidacion final y calculo del IDC
# ------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def construir_idc(agg_contratistas, agg_fdl, agg_talento, geo_localidades, agg_poblacion=None, anio_poblacion=None):
    idc_data = geo_localidades.merge(agg_contratistas, on="localidad_limpia", how="left")
    idc_data = idc_data.merge(agg_fdl, on="localidad_limpia", how="left")
    idc_data = idc_data.merge(agg_talento, on="localidad_limpia", how="left")

    # Fuente 4 (poblacion por localidad): left-join, asi las 20
    # localidades quedan siempre con su poblacion, incluso si en el corte
    # de contratistas/TNP de ese mes no tuvieron ningun registro (esas
    # filas quedan en 0 en vez de desaparecer del mapa/graficos).
    if agg_poblacion is not None and not agg_poblacion.empty:
        idc_data = idc_data.merge(agg_poblacion, on="localidad_limpia", how="left")
    idc_data["anio_poblacion"] = anio_poblacion

    cols_num = [
        "total_contratado", "num_contratos", "total_contratado_directo",
        "total_presupuesto_planeado", "num_postulantes",
        "poblacion_hombres", "poblacion_mujeres", "poblacion_total",
    ]
    for c in cols_num:
        if c in idc_data.columns:
            idc_data[c] = idc_data[c].fillna(0)

    # Indicadores "per capita" (por cada 1.000 habitantes), solo si hay
    # poblacion cargada: permiten comparar localidades de tamaños muy
    # distintos (p. ej. Kennedy vs. La Candelaria) de forma mas justa que
    # los valores absolutos.
    if "poblacion_total" in idc_data.columns:
        con_poblacion = idc_data["poblacion_total"] > 0
        idc_data["contratos_por_1000_hab"] = np.where(
            con_poblacion, idc_data["num_contratos"] / idc_data["poblacion_total"] * 1000, np.nan
        )
        idc_data["contratado_per_capita"] = np.where(
            con_poblacion, idc_data["total_contratado"] / idc_data["poblacion_total"], np.nan
        )
        idc_data["postulantes_tnp_por_1000_hab"] = np.where(
            con_poblacion, idc_data["num_postulantes"] / idc_data["poblacion_total"] * 1000, np.nan
        )

    # Guardamos el valor original sin acotar para transparencia de datos
    idc_data["idc_raw"] = np.where(
        idc_data["total_contratado"] > 0,
        idc_data["total_contratado_directo"] / idc_data["total_contratado"],
        np.nan,
    )
    
    # Acotamos el IDC al 1.0 (100%) para que los gráficos/mapas no colapsen
    idc_data["idc"] = idc_data["idc_raw"].clip(upper=1.0).round(4)
    idc_data["idc_raw"] = idc_data["idc_raw"].round(4)
    
    # Marcamos a Sumapaz como individuo suplementario/outlier
    idc_data["es_outlier"] = idc_data["localidad_limpia"] == "SUMAPAZ"

    idc_data["vigencia"] = 2022
    idc_data["fecha_actualizacion"] = pd.Timestamp.now(tz="America/Bogota").strftime("%Y-%m-%d %H:%M:%S")

    return idc_data
