import pytest

from minutas.compartido.infraestructura.rls import (
    NombreDeTablaInvalido,
    sentencias_de_aislamiento,
    sentencias_para_quitar_aislamiento,
)

CONDICION = "local_id = current_setting('app.local_id')::uuid"


def test_sentencias_de_aislamiento_activan_fuerzan_y_crean_la_politica() -> None:
    assert sentencias_de_aislamiento("productos") == [
        "ALTER TABLE productos ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE productos FORCE ROW LEVEL SECURITY",
        f"CREATE POLICY aislamiento_local ON productos USING ({CONDICION}) "
        f"WITH CHECK ({CONDICION})",
    ]


def test_sentencias_para_quitar_aislamiento_revierten_en_orden_inverso() -> None:
    assert sentencias_para_quitar_aislamiento("productos") == [
        "DROP POLICY aislamiento_local ON productos",
        "ALTER TABLE productos NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE productos DISABLE ROW LEVEL SECURITY",
    ]


@pytest.mark.parametrize("tabla", ["", "Productos", "productos; DROP TABLE x", "1productos"])
def test_sentencias_de_aislamiento_con_nombre_invalido_falla(tabla: str) -> None:
    with pytest.raises(NombreDeTablaInvalido, match="no es un nombre de tabla válido"):
        sentencias_de_aislamiento(tabla)
