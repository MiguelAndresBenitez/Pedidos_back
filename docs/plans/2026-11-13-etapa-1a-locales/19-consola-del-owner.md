# Tarea 19: Consola del owner

**Archivos:**
- Crear: `src/minutas/cli/__init__.py`
- Crear: `src/minutas/cli/comandos.py`
- Crear: `src/minutas/cli/__main__.py`
- Test: `tests/unitarios/cli/test_comandos.py`

---

## Decisiones de diseño

**¿Qué comandos tiene la 1a?**
- `alta-local`, `cambiar-slug`, `cambiar-zona-horaria`, `suspender-local` y `reactivar-local`. `alta-admin` y `revocar-sesiones` llegan con la 1b.

**¿Cómo se prueba sin base?**
- `correr(argv, servicios)` arma los casos de uso con el mismo `crear_casos_de_uso` que la API: los tests le pasan servicios en memoria y la prueba de punta a punta, los reales. `principal` arma los servicios del entorno y los cierra al terminar.

**¿Cómo se despachan los comandos sin condicionales?**
- Cada subcomando registra su función con `set_defaults(ejecutar=...)`. Todas reciben los argumentos, los casos de uso y `ahora`, leído una sola vez.

**¿Qué queda registrado?**
- Un evento JSON por comando (`comando_ejecutado` o `comando_rechazado`) con el comando y el slug. No se registran todos los argumentos: el WhatsApp es un dato personal. Sale con 0, con 1 ante un error de dominio (mensaje por `stderr`) o con 2 ante un uso incorrecto, incluida una modalidad desconocida (`leer_modalidades` es el `type` de argparse).

**Uso:** `docker compose exec api python -m minutas.cli alta-local --slug la-esquina --nombre "La Esquina" --whatsapp "0351 15 512-3456"`.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/cli/test_comandos.py`:

```python
import pytest

from minutas.cli.__main__ import correr
from minutas.locales.dominio.estado_del_local import Activo, Suspendido
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.zona_horaria import ZonaHoraria
from soporte.servicios_en_memoria import ServiciosEnMemoria


async def dar_de_alta(memoria: ServiciosEnMemoria) -> None:
    alta = ["alta-local", "--slug", "la-esquina", "--nombre", "La Esquina"]
    assert await correr([*alta, "--whatsapp", "0351 15 512-3456"], memoria.servicios) == 0


async def test_alta_local_lo_crea_con_ambas_modalidades_y_el_whatsapp_normalizado(
    memoria: ServiciosEnMemoria, capsys: pytest.CaptureFixture[str]
) -> None:
    await dar_de_alta(memoria)

    (local,) = memoria.locales.locales.values()
    assert local.slug == Slug("la-esquina")
    assert local.datos.whatsapp.numero == "5493515123456"
    assert local.datos.modalidades == {Modalidad.DELIVERY, Modalidad.RETIRO}
    assert "Local 'la-esquina' dado de alta" in capsys.readouterr().out


async def test_alta_local_con_slug_invalido_sale_con_1(
    memoria: ServiciosEnMemoria, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["alta-local", "--slug", "API", "--nombre", "X", "--whatsapp", "5493515123456"]

    assert await correr(argv, memoria.servicios) == 1
    assert "Error: 'API' no es un slug válido" in capsys.readouterr().err
    assert memoria.locales.locales == {}


async def test_alta_local_con_modalidad_desconocida_es_un_error_de_uso(
    memoria: ServiciosEnMemoria, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["alta-local", "--slug", "x-y", "--nombre", "X", "--whatsapp", "5493515123456"]

    with pytest.raises(SystemExit) as salida:
        await correr([*argv, "--modalidades", "delivery,mesa"], memoria.servicios)

    assert salida.value.code == 2
    assert "modalidades válidas: delivery, retiro" in capsys.readouterr().err


async def test_cambiar_slug_suspender_y_reactivar(memoria: ServiciosEnMemoria) -> None:
    await dar_de_alta(memoria)
    servicios = memoria.servicios

    assert (
        await correr(["cambiar-slug", "--slug", "la-esquina", "--nuevo", "esquina"], servicios) == 0
    )
    assert await correr(["suspender-local", "--slug", "esquina"], servicios) == 0
    (local,) = memoria.locales.locales.values()
    assert (local.slug, local.estado) == (Slug("esquina"), Suspendido())

    assert await correr(["reactivar-local", "--slug", "esquina"], servicios) == 0
    (local,) = memoria.locales.locales.values()
    assert local.estado == Activo()


async def test_cambiar_zona_horaria_informa_desde_que_jornada_rige(
    memoria: ServiciosEnMemoria, capsys: pytest.CaptureFixture[str]
) -> None:
    await dar_de_alta(memoria)
    argv = ["cambiar-zona-horaria", "--slug", "la-esquina", "--zona", "America/Santiago"]

    assert await correr(argv, memoria.servicios) == 0

    (local,) = memoria.locales.locales.values()
    assert local.jornada.reglas_destino.zona == ZonaHoraria("America/Santiago")
    # El reloj de prueba está en la jornada del viernes 6/11: rige desde el sábado.
    assert "desde la jornada del 2026-11-07" in capsys.readouterr().out


async def test_cambiar_zona_horaria_invalida_sale_con_1(memoria: ServiciosEnMemoria) -> None:
    await dar_de_alta(memoria)
    argv = ["cambiar-zona-horaria", "--slug", "la-esquina", "--zona", "Marte/Olympus"]

    assert await correr(argv, memoria.servicios) == 1


async def test_comando_sobre_un_slug_inexistente_sale_con_1(memoria: ServiciosEnMemoria) -> None:
    assert await correr(["suspender-local", "--slug", "no-existe"], memoria.servicios) == 1


async def test_comando_desconocido_termina_con_error_de_uso(memoria: ServiciosEnMemoria) -> None:
    with pytest.raises(SystemExit) as salida:
        await correr(["alta-admin"], memoria.servicios)

    assert salida.value.code == 2
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/cli/test_comandos.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.cli'`

## Paso 3: Implementación

`src/minutas/cli/__init__.py`:

```python
"""Consola del owner: `python -m minutas.cli <comando>`."""
```

`src/minutas/cli/comandos.py`:

```python
"""Comandos del owner. Cada uno ejecuta un caso de uso y devuelve el texto para la consola."""

import argparse
from collections.abc import Awaitable, Callable
from datetime import datetime

from minutas.composicion import CasosDeUso
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria

type Comando = Callable[[argparse.Namespace, CasosDeUso, datetime], Awaitable[str]]


def leer_modalidades(texto: str) -> frozenset[Modalidad]:
    """Tipo de argparse: `delivery,retiro`. Un valor desconocido es un error de uso (código 2)."""
    try:
        return frozenset(Modalidad(valor.strip()) for valor in texto.split(","))
    except ValueError as error:
        opciones = ", ".join(Modalidad)
        raise argparse.ArgumentTypeError(f"modalidades válidas: {opciones}") from error


async def alta_local(argumentos: argparse.Namespace, casos: CasosDeUso, _ahora: datetime) -> str:
    local = await casos.dar_de_alta_local.ejecutar(
        Slug(argumentos.slug),
        argumentos.nombre,
        Whatsapp.desde_texto(argumentos.whatsapp),
        argumentos.modalidades,
    )
    return f"Local '{local.slug}' dado de alta con id {local.id}"


async def cambiar_slug(argumentos: argparse.Namespace, casos: CasosDeUso, _ahora: datetime) -> str:
    await casos.cambiar_slug.ejecutar(Slug(argumentos.slug), Slug(argumentos.nuevo))
    return f"El local '{argumentos.slug}' ahora es '{argumentos.nuevo}'"


async def cambiar_zona_horaria(
    argumentos: argparse.Namespace, casos: CasosDeUso, ahora: datetime
) -> str:
    desde = await casos.cambiar_zona_horaria.ejecutar(
        Slug(argumentos.slug), ZonaHoraria(argumentos.zona), ahora
    )
    return f"El local '{argumentos.slug}' pasa a {argumentos.zona} desde la jornada del {desde}"


async def suspender_local(
    argumentos: argparse.Namespace, casos: CasosDeUso, _ahora: datetime
) -> str:
    await casos.suspender_local.ejecutar(Slug(argumentos.slug))
    return f"Local '{argumentos.slug}' suspendido"


async def reactivar_local(
    argumentos: argparse.Namespace, casos: CasosDeUso, _ahora: datetime
) -> str:
    await casos.reactivar_local.ejecutar(Slug(argumentos.slug))
    return f"Local '{argumentos.slug}' reactivado"
```

`src/minutas/cli/__main__.py`:

```python
"""Punto de entrada de la consola del owner."""

import argparse
import asyncio
import sys
from collections.abc import Sequence

import structlog

from minutas.cli import comandos
from minutas.compartido.dominio.errores import ErrorDeDominio
from minutas.compartido.infraestructura.configuracion import Configuracion
from minutas.compartido.infraestructura.registro import configurar_registro
from minutas.composicion import Servicios, crear_casos_de_uso, crear_servicios


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minutas", description="Operaciones del owner")
    subcomandos = parser.add_subparsers(dest="comando", required=True)

    alta_local = subcomandos.add_parser("alta-local", help="Da de alta un local")
    alta_local.add_argument("--slug", required=True)
    alta_local.add_argument("--nombre", required=True)
    alta_local.add_argument("--whatsapp", required=True)
    alta_local.add_argument(
        "--modalidades", type=comandos.leer_modalidades, default="delivery,retiro"
    )
    alta_local.set_defaults(ejecutar=comandos.alta_local)

    cambiar_slug = subcomandos.add_parser("cambiar-slug", help="Cambia el link de un local")
    cambiar_slug.add_argument("--slug", required=True)
    cambiar_slug.add_argument("--nuevo", required=True)
    cambiar_slug.set_defaults(ejecutar=comandos.cambiar_slug)

    zona = subcomandos.add_parser(
        "cambiar-zona-horaria", help="Cambia la zona horaria desde la próxima jornada"
    )
    zona.add_argument("--slug", required=True)
    zona.add_argument("--zona", required=True, help="Nombre IANA, por ejemplo America/Santiago")
    zona.set_defaults(ejecutar=comandos.cambiar_zona_horaria)

    suspender = subcomandos.add_parser("suspender-local", help="Suspende un local")
    suspender.add_argument("--slug", required=True)
    suspender.set_defaults(ejecutar=comandos.suspender_local)

    reactivar = subcomandos.add_parser("reactivar-local", help="Reactiva un local suspendido")
    reactivar.add_argument("--slug", required=True)
    reactivar.set_defaults(ejecutar=comandos.reactivar_local)
    return parser


async def correr(argv: Sequence[str], servicios: Servicios) -> int:
    """Ejecuta un comando y devuelve el código de salida: 0 si funcionó, 1 si no."""
    argumentos = crear_parser().parse_args(argv)
    # Solo el comando y el slug: los argumentos pueden traer datos personales (el WhatsApp).
    registro = structlog.get_logger().bind(comando=argumentos.comando, slug=argumentos.slug)
    casos = crear_casos_de_uso(servicios)
    try:
        mensaje = await argumentos.ejecutar(argumentos, casos, servicios.reloj.ahora())
    except ErrorDeDominio as error:
        registro.warning("comando_rechazado", codigo=error.codigo, mensaje=error.mensaje)
        print(f"Error: {error.mensaje}", file=sys.stderr)
        return 1
    registro.info("comando_ejecutado", resultado=mensaje)
    print(mensaje)
    return 0


async def principal(argv: Sequence[str]) -> int:
    configuracion = Configuracion()
    configurar_registro(configuracion.nivel_de_registro)
    servicios = crear_servicios(configuracion)
    try:
        return await correr(argv, servicios)
    finally:
        await servicios.cerrar()


if __name__ == "__main__":
    sys.exit(asyncio.run(principal(sys.argv[1:])))
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/cli/test_comandos.py -v && uv run mypy`
Expected: PASS (8 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/cli/__init__.py src/minutas/cli/comandos.py src/minutas/cli/__main__.py tests/unitarios/cli/test_comandos.py
git commit -m "feat(proyecto): consola del owner para locales" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
