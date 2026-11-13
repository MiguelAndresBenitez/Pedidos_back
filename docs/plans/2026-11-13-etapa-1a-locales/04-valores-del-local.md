# Tarea 4: Errores y valores del local

**Archivos:**
- Crear: `src/minutas/locales/dominio/errores.py`
- Crear: `src/minutas/locales/dominio/slug.py`
- Crear: `src/minutas/locales/dominio/whatsapp.py`
- Crear: `src/minutas/locales/dominio/color.py`
- Crear: `src/minutas/locales/dominio/zona_horaria.py`
- Crear: `src/minutas/locales/dominio/modalidad.py`
- Test: `tests/unitarios/locales/test_valores_del_local.py`

---

## Decisiones de diseño

**¿Por qué todos los errores de Locales en esta tarea?**
- Son declaraciones sin lógica y los usan casi todas las tareas siguientes. Los códigos son los de la tabla de errores del diseño.

**¿Cómo se valida el WhatsApp?**
- Con `phonenumbers`, la tabla de numeración de Google, con Argentina como región por defecto. Acepta el número como lo escribe una persona (`0351 15 512-3456`, `+54 9 351…`), exige que sea un celular y lo guarda en el formato de `wa.me` (`5493515123456`). Un número sin el 15 ni el 9 (`351 5123456`) es un fijo y se rechaza con un mensaje que muestra cómo escribirlo.
- El constructor exige el formato final (lo que se lee de la base); `desde_texto` es la puerta para lo que escribe una persona.

**`Slug`, `Color`, `ZonaHoraria` y `Modalidad`** se mantienen como en el diseño: slug de 3 a 40 caracteres sin palabras reservadas, color `#rrggbb`, zona IANA válida en `zoneinfo` (rechaza también rutas como `../etc/passwd`).

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_valores_del_local.py`:

```python
import pytest

from minutas.locales.dominio.color import Color
from minutas.locales.dominio.errores import (
    DatoDelLocalInvalido,
    SlugInvalido,
    SlugReservado,
    WhatsappInvalido,
    ZonaHorariaInvalida,
)
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria


@pytest.mark.parametrize("valor", ["abc", "la-esquina", "pizzeria-24", "a" * 40])
def test_crear_slug_valido_conserva_el_valor(valor: str) -> None:
    assert str(Slug(valor)) == valor


@pytest.mark.parametrize(
    "valor",
    ["ab", "a" * 41, "La-Esquina", "-esquina", "esquina-", "la--esquina", "la esquina", "ñu"],
)
def test_crear_slug_invalido_falla(valor: str) -> None:
    with pytest.raises(SlugInvalido, match="no es un slug válido"):
        Slug(valor)


@pytest.mark.parametrize("valor", ["api", "panel", "admin", "tiendas"])
def test_crear_slug_reservado_falla(valor: str) -> None:
    with pytest.raises(SlugReservado, match="palabra reservada"):
        Slug(valor)


@pytest.mark.parametrize(
    "texto",
    [
        "0351 15 512-3456",
        "351 15 5123456",
        "+54 9 351 512 3456",
        "5493515123456",
        "+5493515123456",
    ],
)
def test_whatsapp_desde_texto_normaliza_las_formas_de_escribir_un_celular(texto: str) -> None:
    assert Whatsapp.desde_texto(texto) == Whatsapp("5493515123456")


def test_whatsapp_desde_texto_de_otro_pais_lo_acepta_con_su_codigo() -> None:
    assert Whatsapp.desde_texto("+56 9 6123 4567").numero == "56961234567"


@pytest.mark.parametrize("texto", ["351 5123456", "0351 4123456", "123", "sin numero", ""])
def test_whatsapp_desde_texto_que_no_es_un_celular_falla(texto: str) -> None:
    with pytest.raises(WhatsappInvalido, match="no es un celular válido"):
        Whatsapp.desde_texto(texto)


def test_crear_whatsapp_sin_normalizar_falla() -> None:
    with pytest.raises(WhatsappInvalido):
        Whatsapp("03515123456")


def test_color_desde_texto_pasa_a_minusculas() -> None:
    assert Color.desde_texto("#FF8800") == Color("#ff8800")


@pytest.mark.parametrize("texto", ["ff8800", "#ff88", "#gg8800", "rojo"])
def test_color_desde_texto_invalido_falla(texto: str) -> None:
    with pytest.raises(DatoDelLocalInvalido, match="no es un color válido"):
        Color.desde_texto(texto)


def test_crear_zona_horaria_valida_expone_su_zoneinfo() -> None:
    assert ZonaHoraria("America/Santiago").info.key == "America/Santiago"


@pytest.mark.parametrize("nombre", ["Marte/Olympus", "", "../etc/passwd"])
def test_crear_zona_horaria_desconocida_falla(nombre: str) -> None:
    with pytest.raises(ZonaHorariaInvalida, match="no es una zona horaria válida"):
        ZonaHoraria(nombre)
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_valores_del_local.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.dominio.color'`

## Paso 3: Implementación

`src/minutas/locales/dominio/errores.py`:

```python
"""Errores de dominio del contexto Locales."""

from minutas.compartido.dominio.errores import (
    AccesoDenegado,
    Conflicto,
    NoEncontrado,
    ReglaDeNegocioIncumplida,
)


class SlugInvalido(ReglaDeNegocioIncumplida):
    codigo = "slug_invalido"


class SlugReservado(ReglaDeNegocioIncumplida):
    codigo = "slug_reservado"


class DatoDelLocalInvalido(ReglaDeNegocioIncumplida):
    codigo = "dato_del_local_invalido"


class WhatsappInvalido(ReglaDeNegocioIncumplida):
    codigo = "whatsapp_invalido"


class ZonaHorariaInvalida(ReglaDeNegocioIncumplida):
    codigo = "zona_horaria_invalida"


class FranjaAmbigua(ReglaDeNegocioIncumplida):
    codigo = "franja_ambigua"


class HorariosSuperpuestos(ReglaDeNegocioIncumplida):
    codigo = "horarios_superpuestos"


class FranjaCortaLaHoraDeCorte(ReglaDeNegocioIncumplida):
    codigo = "franja_corta_la_hora_de_corte"


class ImagenInvalida(ReglaDeNegocioIncumplida):
    codigo = "imagen_invalida"


class ImagenDemasiadoGrande(ReglaDeNegocioIncumplida):
    codigo = "imagen_demasiado_grande"


class SlugEnUso(Conflicto):
    codigo = "slug_en_uso"


class LocalModificadoEnParalelo(Conflicto):
    codigo = "local_modificado_en_paralelo"


class LocalNoEncontrado(NoEncontrado):
    codigo = "local_no_encontrado"


class LocalSuspendido(AccesoDenegado):
    codigo = "local_suspendido"


class ImagenNoEncontrada(NoEncontrado):
    codigo = "imagen_no_encontrada"
```

`src/minutas/locales/dominio/slug.py`:

```python
"""Slug: el tramo del link público de la tienda, por ejemplo `la-esquina`."""

import re
from dataclasses import dataclass

from minutas.locales.dominio.errores import SlugInvalido, SlugReservado

PATRON_DE_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
LARGO_MINIMO_DE_SLUG = 3
LARGO_MAXIMO_DE_SLUG = 40
SLUGS_RESERVADOS = frozenset(
    {
        "admin",
        "api",
        "auth",
        "imagenes",
        "minutas",
        "owner",
        "panel",
        "salud",
        "static",
        "tiendas",
        "www",
    }
)


@dataclass(frozen=True, slots=True)
class Slug:
    valor: str

    def __post_init__(self) -> None:
        largo_valido = LARGO_MINIMO_DE_SLUG <= len(self.valor) <= LARGO_MAXIMO_DE_SLUG
        if not largo_valido or not PATRON_DE_SLUG.fullmatch(self.valor):
            raise SlugInvalido(
                f"'{self.valor}' no es un slug válido: de 3 a 40 caracteres entre a-z, 0-9 y "
                "guiones, sin guion al principio, al final ni dos seguidos"
            )
        if self.valor in SLUGS_RESERVADOS:
            raise SlugReservado(f"'{self.valor}' es una palabra reservada")

    def __str__(self) -> str:
        return self.valor
```

`src/minutas/locales/dominio/whatsapp.py`:

```python
"""Número de WhatsApp del local, en el formato que usa el link `wa.me`."""

from dataclasses import dataclass
from typing import Self

import phonenumbers

from minutas.locales.dominio.errores import WhatsappInvalido

REGION_POR_DEFECTO = "AR"
TIPOS_DE_CELULAR = frozenset(
    {phonenumbers.PhoneNumberType.MOBILE, phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE}
)
MENSAJE = (
    "'{texto}' no es un celular válido. Escribilo con la característica y el 15, "
    "por ejemplo 0351 15 512-3456, o con el código de país, +54 9 351 512 3456"
)


@dataclass(frozen=True, slots=True)
class Whatsapp:
    """Solo dígitos, con código de país: `5493515123456`."""

    numero: str

    def __post_init__(self) -> None:
        if desde_texto_o_none(f"+{self.numero}") != self.numero:
            raise WhatsappInvalido(MENSAJE.format(texto=self.numero))

    @classmethod
    def desde_texto(cls, texto: str) -> Self:
        """Acepta el número como lo escribe una persona; Argentina es la región por defecto."""
        numero = desde_texto_o_none(texto)
        if numero is None:
            raise WhatsappInvalido(MENSAJE.format(texto=texto))
        return cls(numero)


def desde_texto_o_none(texto: str) -> str | None:
    """Interpreta el número con la tabla de numeración de `phonenumbers`; exige un celular."""
    try:
        interpretado = phonenumbers.parse(texto, REGION_POR_DEFECTO)
    except phonenumbers.NumberParseException:
        return None
    valido = phonenumbers.is_valid_number(interpretado) and (
        phonenumbers.number_type(interpretado) in TIPOS_DE_CELULAR
    )
    formato = phonenumbers.format_number(interpretado, phonenumbers.PhoneNumberFormat.E164)
    return formato.removeprefix("+") if valido else None
```

`src/minutas/locales/dominio/color.py`:

```python
"""Color de marca del local, en hexadecimal."""

import re
from dataclasses import dataclass
from typing import Self

from minutas.locales.dominio.errores import DatoDelLocalInvalido

PATRON_DE_COLOR = re.compile(r"#[0-9a-f]{6}")


@dataclass(frozen=True, slots=True)
class Color:
    hexadecimal: str

    def __post_init__(self) -> None:
        if not PATRON_DE_COLOR.fullmatch(self.hexadecimal):
            raise DatoDelLocalInvalido(
                f"'{self.hexadecimal}' no es un color válido: se espera #rrggbb"
            )

    @classmethod
    def desde_texto(cls, texto: str) -> Self:
        return cls(texto.lower())


COLOR_POR_DEFECTO = Color("#000000")
```

`src/minutas/locales/dominio/zona_horaria.py`:

```python
"""Zona horaria IANA del local: define su hora local para horarios y jornada."""

from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from minutas.locales.dominio.errores import ZonaHorariaInvalida


@dataclass(frozen=True, slots=True)
class ZonaHoraria:
    nombre: str

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.nombre)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ZonaHorariaInvalida(f"'{self.nombre}' no es una zona horaria válida") from error

    @property
    def info(self) -> ZoneInfo:
        return ZoneInfo(self.nombre)


ZONA_HORARIA_POR_DEFECTO = ZonaHoraria("America/Argentina/Buenos_Aires")
```

`src/minutas/locales/dominio/modalidad.py`:

```python
"""Modalidades de entrega que ofrece un local."""

from enum import StrEnum


class Modalidad(StrEnum):
    DELIVERY = "delivery"
    RETIRO = "retiro"
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_valores_del_local.py -v && uv run mypy`
Expected: PASS (37 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/dominio/errores.py src/minutas/locales/dominio/slug.py src/minutas/locales/dominio/whatsapp.py src/minutas/locales/dominio/color.py src/minutas/locales/dominio/zona_horaria.py src/minutas/locales/dominio/modalidad.py tests/unitarios/locales/test_valores_del_local.py
git commit -m "feat(locales): errores, slug, whatsapp, color y zona horaria" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
