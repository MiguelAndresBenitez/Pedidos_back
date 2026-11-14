# Tarea 3: Errores de dominio

**Archivos:**
- Crear: `src/minutas/compartido/dominio/errores.py`
- Test: `tests/unitarios/compartido/test_errores.py`

---

## Decisiones de diseño

**¿Por qué una jerarquía con cuatro categorías en lugar de un código HTTP en cada error?**
- El dominio no conoce HTTP (ver `docs/plans/00-conventions.md`, Decisiones transversales).
- Cada error concreto hereda de una categoría (`TiendaCerrada(ReglaDeNegocioIncumplida)`) y la tarea 8 traduce la categoría a un estado HTTP con una tabla de despacho, sin `if`.
- Categorías tomadas de la spec: 404 no encontrado, 409 conflicto, 422 regla incumplida, 429 límite.

**¿Por qué `codigo` como atributo de clase?**
- Es el `code` de `problem+json` que el front usa para reaccionar (`tienda_cerrada`, `seleccion_invalida`).
- Cada error concreto lo redefine; el mensaje sigue siendo libre para personas.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/compartido/test_errores.py`:

```python
import pytest

from minutas.compartido.dominio.errores import (
    Conflicto,
    ErrorDeDominio,
    LimiteExcedido,
    NoEncontrado,
    ReglaDeNegocioIncumplida,
)


class ProductoInexistente(NoEncontrado):
    codigo = "producto_inexistente"


def test_crear_error_de_dominio_guarda_mensaje_y_codigo() -> None:
    error = ErrorDeDominio("Algo salió mal")

    assert error.mensaje == "Algo salió mal"
    assert error.codigo == "error_de_dominio"
    assert str(error) == "Algo salió mal"


@pytest.mark.parametrize(
    ("clase", "codigo"),
    [
        (NoEncontrado, "no_encontrado"),
        (Conflicto, "conflicto"),
        (ReglaDeNegocioIncumplida, "regla_de_negocio_incumplida"),
        (LimiteExcedido, "limite_excedido"),
    ],
)
def test_crear_categoria_de_error_tiene_codigo_propio(
    clase: type[ErrorDeDominio], codigo: str
) -> None:
    error = clase("mensaje")

    assert isinstance(error, ErrorDeDominio)
    assert error.codigo == codigo


def test_crear_error_concreto_hereda_categoria_y_redefine_codigo() -> None:
    error = ProductoInexistente("El producto no existe")

    assert isinstance(error, NoEncontrado)
    assert error.codigo == "producto_inexistente"
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/compartido/test_errores.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.compartido.dominio.errores'`

## Paso 3: Implementación mínima

`src/minutas/compartido/dominio/errores.py`:

```python
"""Errores de dominio, agrupados por categoría.

Cada error concreto hereda de una categoría y redefine `codigo`. El borde HTTP
traduce la categoría a un estado; el dominio no conoce HTTP.
"""

from typing import ClassVar


class ErrorDeDominio(Exception):
    """Base de todos los errores que el dominio lanza a propósito."""

    codigo: ClassVar[str] = "error_de_dominio"

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class NoEncontrado(ErrorDeDominio):
    """Lo pedido no existe o no pertenece al local."""

    codigo = "no_encontrado"


class Conflicto(ErrorDeDominio):
    """La operación choca con el estado actual de los datos."""

    codigo = "conflicto"


class ReglaDeNegocioIncumplida(ErrorDeDominio):
    """Los datos son válidos en forma, pero el negocio no lo permite."""

    codigo = "regla_de_negocio_incumplida"


class LimiteExcedido(ErrorDeDominio):
    """Se superó un límite de uso."""

    codigo = "limite_excedido"
```

## Paso 4: Correr el test y ver que pasa

Run: `uv run pytest tests/unitarios/compartido/test_errores.py -v`
Expected: PASS (6 passed)

## Paso 5: Commit

```bash
git add src/minutas/compartido/dominio/errores.py tests/unitarios/compartido/test_errores.py
git commit -m "feat(compartido): jerarquía de errores de dominio por categoría" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
