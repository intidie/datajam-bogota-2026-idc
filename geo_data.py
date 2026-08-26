"""
geo_data.py
-----------
Centroides de las 20 localidades (respaldo) y polígonos oficiales de la
Secretaría Distrital de Planeación / IDECA, obtenidos en vivo vía el
servicio ArcGIS REST público de la Unidad de Catastro Distrital.

Si el servicio no responde (por ejemplo, sin salida a internet), el mapa
cae automáticamente al modo de puntos de calor por centroide, sin romper
la aplicación.
"""

import json
import urllib.request

import pandas as pd
import streamlit as st

import pipeline

GEOJSON_LOCALIDADES_URL = (
    "https://serviciosgis.catastrobogota.gov.co/arcgis/rest/services/"
    "ordenamientoterritorial/localidad/MapServer/0/query"
    "?where=1%3D1&outFields=LOCNOMBRE,LOCCODIGO&outSR=4326&f=geojson"
)

GEO_LOCALIDADES = pd.DataFrame([
    {"cod_localidad": "01", "localidad_limpia": "USAQUEN",            "latitud": 4.7110, "longitud": -74.0301},
    {"cod_localidad": "02", "localidad_limpia": "CHAPINERO",          "latitud": 4.6486, "longitud": -74.0625},
    {"cod_localidad": "03", "localidad_limpia": "SANTA FE",           "latitud": 4.6097, "longitud": -74.0817},
    {"cod_localidad": "04", "localidad_limpia": "SAN CRISTOBAL",      "latitud": 4.5573, "longitud": -74.0817},
    {"cod_localidad": "05", "localidad_limpia": "USME",               "latitud": 4.4826, "longitud": -74.1264},
    {"cod_localidad": "06", "localidad_limpia": "TUNJUELITO",         "latitud": 4.5721, "longitud": -74.1319},
    {"cod_localidad": "07", "localidad_limpia": "BOSA",               "latitud": 4.6183, "longitud": -74.1772},
    {"cod_localidad": "08", "localidad_limpia": "KENNEDY",            "latitud": 4.6280, "longitud": -74.1531},
    {"cod_localidad": "09", "localidad_limpia": "FONTIBON",           "latitud": 4.6784, "longitud": -74.1459},
    {"cod_localidad": "10", "localidad_limpia": "ENGATIVA",           "latitud": 4.7133, "longitud": -74.1131},
    {"cod_localidad": "11", "localidad_limpia": "SUBA",               "latitud": 4.7460, "longitud": -74.0930},
    {"cod_localidad": "12", "localidad_limpia": "BARRIOS UNIDOS",     "latitud": 4.6673, "longitud": -74.0836},
    {"cod_localidad": "13", "localidad_limpia": "TEUSAQUILLO",        "latitud": 4.6377, "longitud": -74.0930},
    {"cod_localidad": "14", "localidad_limpia": "LOS MARTIRES",       "latitud": 4.6041, "longitud": -74.0925},
    {"cod_localidad": "15", "localidad_limpia": "ANTONIO NARINO",     "latitud": 4.5901, "longitud": -74.0999},
    {"cod_localidad": "16", "localidad_limpia": "PUENTE ARANDA",      "latitud": 4.6156, "longitud": -74.1157},
    {"cod_localidad": "17", "localidad_limpia": "LA CANDELARIA",      "latitud": 4.5966, "longitud": -74.0741},
    {"cod_localidad": "18", "localidad_limpia": "RAFAEL URIBE URIBE", "latitud": 4.5581, "longitud": -74.1064},
    {"cod_localidad": "19", "localidad_limpia": "CIUDAD BOLIVAR",     "latitud": 4.5000, "longitud": -74.1600},
    {"cod_localidad": "20", "localidad_limpia": "SUMAPAZ",            "latitud": 4.0500, "longitud": -74.3833},
])


@st.cache_resource(show_spinner=False)
def cargar_geojson_oficial():
    """Descarga los poligonos oficiales de localidades (IDECA / SDP) una
    sola vez, compartido entre todas las sesiones. Devuelve None si falla,
    para que el mapa use el modo de respaldo por centroides."""
    try:
        req = urllib.request.Request(
            GEOJSON_LOCALIDADES_URL, headers={"User-Agent": "Mozilla/5.0 (IDC-Bogota-App)"}
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("features"):
            return None
        for feature in data["features"]:
            nombre_original = feature["properties"].get("LOCNOMBRE", "")
            feature["properties"]["localidad_limpia"] = pipeline.estandarizar_localidad(nombre_original)
        return data
    except Exception:
        return None


@st.cache_resource(show_spinner=False)
def cargar_geojson_subido(file_bytes: bytes):
    """Permite usar un GeoJSON alterno subido manualmente por el usuario."""
    data = json.loads(file_bytes.decode("utf-8"))
    if data.get("features"):
        for feature in data["features"]:
            props = feature.get("properties", {})
            candidato = None
            for llave in ("LOCNOMBRE", "LocNombre", "Nombre_de_la_localidad", "nombre", "NOMBRE", "localidad", "LOCALIDAD"):
                if llave in props:
                    candidato = props[llave]
                    break
            feature["properties"]["localidad_limpia"] = pipeline.estandarizar_localidad(candidato)
    return data
