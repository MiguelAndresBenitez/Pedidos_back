# Tarea 4: Identificadores UUIDv7

**Archivos:**
- Crear: `src/minutas/compartido/dominio/identificador.py`
- Crear: `src/minutas/compartido/dominio/local_id.py`
- Test: `tests/unitarios/compartido/test_identificador.py`

---

## Decisiones de diseño

**¿Por qué un value object `Identificador` en lugar de usar `UUID` suelto?**
- Garantiza que todo id del dominio sea UUIDv7 (spec D02): la validación vive en un solo lugar.
- Cada entidad tiene su subclase (`LocalId`, y luego `PedidoId`, `ProductoId`). Dos ids de tipos distintos nunca son iguales, aunque tengan el mismo valor, porque la igualdad de dataclass compara la clase.

**¿Por qué `uuid_utils.compat.uuid7`?**
- Python 3.13 no trae `uuid7`; `uuid-utils` lo genera en Rust y la variante `compat` devuelve un `uuid.UUID` estándar.
- Cuando el proyecto pase a Python 3.14 se reemplaza por `uuid.uuid7` sin tocar a quienes usan `Identificador.generar()`.

**¿Por qué `LocalId` en `compartido`?**
- Todos los contextos lo necesitan para aislar datos, y ninguno debe importar el dominio de `locales`.

**¿Por qué `IdentificadorInvalido` es una `ReglaDeNegocioIncumplida`?**
- Un id mal formado que llega en una URL o un cuerpo es un dato que no cumple las reglas: corresponde un 422.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/compartido/test_identificador.py`:

```python
import time
from dataclasses import dataclass
from uuid import uuid4

import pytest

from minutas.compartido.dominio.identificador import Identificador, IdentificadorInvalido
from minutas.compartido.dominio.local_id import LocalId


@dataclass(frozen=True, slots=True)
class PedidoId(Identificador):
    pass


def test_generar_crea_uuid_version_7() -> None:
    assert Identificador.generar().valor.version == 7


def test_generar_devuelve_instancia_de_la_subclase() -> None:
    assert isinstance(LocalId.generar(), LocalId)


def test_generar_respeta_el_orden_temporal() -> None:
    primero = Identificador.generar()
    time.sleep(0.002)
    segundo = Identificador.generar()

    assert primero.valor < segundo.valor


def test_crear_con_uuid_version_4_falla() -> None:
    with pytest.raises(IdentificadorInvalido, match="versión 4"):
        Identificador(uuid4())


def test_desde_texto_reconstruye_el_mismo_identificador() -> None:
    original = LocalId.generar()

    assert LocalId.desde_texto(str(original)) == original


def test_desde_texto_con_texto_invalido_falla() -> None:
    with pytest.raises(IdentificadorInvalido, match="no es un UUID válido"):
        LocalId.desde_texto("cualquier-cosa")


def test_comparar_identificadores_de_tipos_distintos_no_son_iguales() -> None:
    valor = Identificador.generar().valor
    otro: object = PedidoId(valor)

    assert LocalId(valor) != otro
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/compartido/test_identificador.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.compartido.dominio.identificador'`

## Paso 3: Implementación mínima

`src/minutas/compartido/dominio/identificador.py`:

```python
"""Identificador UUIDv7, base de los ids de todas las entidades."""

from dataclasses import dataclass
from typing import Self
from uuid import UUID

from uuid_utils.compat import uuid7

from minutas.compartido.dominio.errores import ReglaDeNegocioIncumplida

VERSION_ESPERADA = 7


class IdentificadorInvalido(ReglaDeNegocioIncumplida):
    codigo = "identificador_invalido"


@dataclass(frozen=True, slots=True)
class Identificador:
    """Value object que envuelve un UUIDv7."""

    valor: UUID

    def __post_init__(self) -> None:
        if self.valor.version != VERSION_ESPERADA:
            raise IdentificadorInvalido(
                f"Se esperaba un UUIDv7 y llegó la versión {self.valor.version}"
            )

    @classmethod
    def generar(cls) -> Self:
        return cls(uuid7())

    @classmethod
    def desde_texto(cls, texto: str) -> Self:
        try:
            valor = UUID(texto)
        except ValueError as error:
            raise IdentificadorInvalido(f"'{texto}' no es un UUID válido") from error
        return cls(valor)

    def __str__(self) -> str:
        return str(self.valor)
```

`src/minutas/compartido/dominio/local_id.py`:

```python
"""Identificador del local, el tenant dueño de cada dato de negocio."""

from dataclasses import dataclass

from minutas.compartido.dominio.identificador import Identificador


@dataclass(frozen=True, slots=True)
class LocalId(Identificador):
    """Identifica al local dueño de un dato."""
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/unitarios/compartido/test_identificador.py -v`
Expected: PASS (7 passed)

## Paso 5: Commit

```bash
git add src/minutas/compartido/dominio/identificador.py src/minutas/compartido/dominio/local_id.py tests/unitarios/compartido/test_identificador.py
git commit -m "feat(compartido): identificadores UUIDv7 como value objects" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
