import asyncpg
import pytest

from soporte.base_de_prueba import BaseDePrueba

pytestmark = pytest.mark.integracion


async def test_consultar_rol_app_no_tiene_bypassrls_ni_superusuario(
    base_de_prueba: BaseDePrueba,
) -> None:
    conexion = await asyncpg.connect(base_de_prueba.dsn_admin())
    try:
        fila = await conexion.fetchrow(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = 'minutas_app'"
        )
    finally:
        await conexion.close()

    assert fila["rolsuper"] is False
    assert fila["rolbypassrls"] is False


async def test_crear_tabla_como_app_falla(base_de_prueba: BaseDePrueba) -> None:
    conexion = await asyncpg.connect(base_de_prueba.dsn_app())
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="schema public"):
            await conexion.execute("CREATE TABLE intrusa (id int)")
    finally:
        await conexion.close()


async def test_crear_tabla_como_owner_da_permisos_de_datos_a_app(
    base_de_prueba: BaseDePrueba,
) -> None:
    owner = await asyncpg.connect(base_de_prueba.dsn_owner())
    try:
        await owner.execute("CREATE TABLE prueba_privilegios (id int)")
        app = await asyncpg.connect(base_de_prueba.dsn_app())
        try:
            await app.execute("INSERT INTO prueba_privilegios VALUES (1)")
            cantidad = await app.fetchval("SELECT count(*) FROM prueba_privilegios")
        finally:
            await app.close()
    finally:
        await owner.execute("DROP TABLE prueba_privilegios")
        await owner.close()

    assert cantidad == 1
