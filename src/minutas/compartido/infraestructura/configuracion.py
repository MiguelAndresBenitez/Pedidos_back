"""Configuración leída de variables de entorno MINUTAS_*, una clase por proceso."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

NivelDeRegistro = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
Entorno = Literal["desarrollo", "pruebas", "produccion"]


class Configuracion(BaseSettings):
    """Configuración de la API. Solo conoce la credencial del rol minutas_app."""

    model_config = SettingsConfigDict(env_prefix="MINUTAS_", frozen=True, extra="ignore")

    url_base_de_datos: str
    nivel_de_registro: NivelDeRegistro = "INFO"
    entorno: Entorno = "desarrollo"


class ConfiguracionDeMigraciones(BaseSettings):
    """Configuración de Alembic. Solo conoce la credencial del rol minutas_owner."""

    model_config = SettingsConfigDict(env_prefix="MINUTAS_", frozen=True, extra="ignore")

    url_base_de_datos_migraciones: str
