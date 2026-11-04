"""Sentencias SQL que aíslan una tabla del local con Row Level Security."""

import re

PATRON_DE_TABLA = re.compile(r"[a-z_][a-z0-9_]*")
NOMBRE_DE_POLITICA = "aislamiento_local"
CONDICION = "local_id = current_setting('app.local_id')::uuid"


class NombreDeTablaInvalido(ValueError):
    pass


def asegurar_nombre_de_tabla_valido(tabla: str) -> None:
    if not PATRON_DE_TABLA.fullmatch(tabla):
        raise NombreDeTablaInvalido(f"'{tabla}' no es un nombre de tabla válido")


def sentencias_de_aislamiento(tabla: str) -> list[str]:
    asegurar_nombre_de_tabla_valido(tabla)
    return [
        f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {tabla} FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY {NOMBRE_DE_POLITICA} ON {tabla} USING ({CONDICION}) "
        f"WITH CHECK ({CONDICION})",
    ]


def sentencias_para_quitar_aislamiento(tabla: str) -> list[str]:
    asegurar_nombre_de_tabla_valido(tabla)
    return [
        f"DROP POLICY {NOMBRE_DE_POLITICA} ON {tabla}",
        f"ALTER TABLE {tabla} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {tabla} DISABLE ROW LEVEL SECURITY",
    ]
