"""Configuración leída de variables de entorno MINUTAS_*, una clase por proceso."""

from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

NivelDeRegistro = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
Entorno = Literal["desarrollo", "pruebas", "produccion"]


class Configuracion(BaseSettings):
    """Configuración de la API y la consola. Solo conoce la credencial del rol minutas_app."""

    model_config = SettingsConfigDict(env_prefix="MINUTAS_", frozen=True, extra="ignore")

    url_base_de_datos: SecretStr
    nivel_de_registro: NivelDeRegistro = "INFO"
    entorno: Entorno = "desarrollo"
    directorio_de_imagenes: Path = Path("/var/lib/minutas/imagenes")


class ConfiguracionDeMigraciones(BaseSettings):
    """Configuración de Alembic. Solo conoce la credencial del rol minutas_owner."""

    model_config = SettingsConfigDict(env_prefix="MINUTAS_", frozen=True, extra="ignore")

    url_base_de_datos_migraciones: SecretStr
