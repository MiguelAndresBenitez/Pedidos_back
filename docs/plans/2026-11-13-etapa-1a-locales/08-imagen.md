# Tarea 8: Tipos, medidas y nombre de imagen

**Archivos:**
- Crear: `src/minutas/locales/dominio/imagen.py`
- Test: `tests/unitarios/locales/test_imagen.py`

---

## Decisiones de diseño

**¿Qué es del dominio y qué de la infraestructura?**
- Del dominio: los tipos (logo y portada), sus medidas máximas (512×512 y 1600 de ancho), el tope de 2 MB y la forma del nombre (`<uuid7>.webp`). El procesamiento con Pillow es infraestructura (tarea 15).

**¿Por qué validar el nombre?**
- Es lo que se guarda en `locales` y lo que llega en la URL de `GET /imagenes/{nombre}` (tarea 18). Con el patrón exacto, un nombre como `../etc/passwd` no se puede construir.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_imagen.py`:

```python
import pytest

from minutas.locales.dominio.errores import ImagenInvalida
from minutas.locales.dominio.imagen import Medidas, NombreDeImagen, TipoDeImagen


def test_medidas_maximas_dependen_del_tipo() -> None:
    assert TipoDeImagen.LOGO.medidas_maximas == Medidas(512, 512)
    assert TipoDeImagen.PORTADA.medidas_maximas.ancho == 1600


def test_crear_nombre_de_imagen_valido_conserva_el_valor() -> None:
    assert str(NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp")).endswith(".webp")


@pytest.mark.parametrize(
    "valor", ["logo.png", "../etc/passwd", "01a18e9b-3c49-45a8-a745-cbce398ad79a.webp"]
)
def test_crear_nombre_de_imagen_invalido_falla(valor: str) -> None:
    with pytest.raises(ImagenInvalida, match="no es un nombre de imagen válido"):
        NombreDeImagen(valor)
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_imagen.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.dominio.imagen'`

## Paso 3: Implementación

`src/minutas/locales/dominio/imagen.py`:

```python
"""Imágenes del local: tipos, límites y el nombre con que se guardan."""

import re
from dataclasses import dataclass
from enum import StrEnum

from minutas.locales.dominio.errores import ImagenInvalida

TAMANIO_MAXIMO_DE_IMAGEN = 2 * 1024 * 1024
PATRON_DE_NOMBRE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}\.webp"
)


@dataclass(frozen=True, slots=True)
class Medidas:
    """Medidas máximas en píxeles; la imagen se achica manteniendo la proporción."""

    ancho: int
    alto: int


class TipoDeImagen(StrEnum):
    LOGO = "logo"
    PORTADA = "portada"

    @property
    def medidas_maximas(self) -> Medidas:
        return MEDIDAS_POR_TIPO[self]


# La portada se limita por ancho; el alto queda libre dentro de una proporción razonable.
MEDIDAS_POR_TIPO = {
    TipoDeImagen.LOGO: Medidas(512, 512),
    TipoDeImagen.PORTADA: Medidas(1600, 4800),
}


@dataclass(frozen=True, slots=True)
class NombreDeImagen:
    """`<uuid7>.webp`: lo genera el almacén y nunca se repite."""

    valor: str

    def __post_init__(self) -> None:
        if not PATRON_DE_NOMBRE.fullmatch(self.valor):
            raise ImagenInvalida(f"'{self.valor}' no es un nombre de imagen válido")

    def __str__(self) -> str:
        return self.valor
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_imagen.py -v && uv run mypy`
Expected: PASS (5 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/dominio/imagen.py tests/unitarios/locales/test_imagen.py
git commit -m "feat(locales): tipos, medidas y nombre de imagen" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
