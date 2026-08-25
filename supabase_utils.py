"""
supabase_utils.py
------------------
Conexión y carga (upsert) a Supabase. Las credenciales NUNCA se
hardcodean: se leen de `st.secrets` (Streamlit Cloud) o de variables de
entorno / `.env` (entorno local), en ese orden.
"""

import os

import numpy as np
import streamlit as st
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()  # no-op si no existe .env (p. ej. en Streamlit Cloud)

TABLE_NAME = "idc_data"


def _get_credencial(nombre: str):
    try:
        if nombre in st.secrets:
            return st.secrets[nombre]
    except Exception:
        pass  # no hay secrets.toml configurado, seguimos con variables de entorno
    return os.getenv(nombre)


@st.cache_resource(show_spinner=False)
def get_supabase_client() -> Client | None:
    """Crea (una sola vez, compartido entre sesiones) el cliente de Supabase."""
    url = _get_credencial("SUPABASE_URL")
    key = _get_credencial("SUPABASE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def _limpiar_tipos(registro: dict) -> dict:
    """Convierte tipos numpy a tipos nativos de Python para que sean serializables a JSON."""
    limpio = {}
    for k, v in registro.items():
        if isinstance(v, np.integer):
            limpio[k] = int(v)
        elif isinstance(v, np.floating):
            limpio[k] = float(v) if not np.isnan(v) else None
        else:
            limpio[k] = v
    return limpio


def subir_idc_a_supabase(idc_data, table_name: str = TABLE_NAME):
    """Hace upsert del DataFrame consolidado a la tabla `idc_data`, usando
    `cod_localidad` como llave de conflicto (igual que en el notebook)."""
    client = get_supabase_client()
    if client is None:
        raise EnvironmentError(
            "No se encontraron SUPABASE_URL / SUPABASE_KEY. "
            "Configúralas en `.streamlit/secrets.toml` (nube) o en un archivo `.env` (local)."
        )

    registros = idc_data.replace({np.nan: None}).to_dict(orient="records")
    registros = [_limpiar_tipos(r) for r in registros]

    response = client.table(table_name).upsert(registros, on_conflict="cod_localidad").execute()
    return len(response.data) if response.data else 0
