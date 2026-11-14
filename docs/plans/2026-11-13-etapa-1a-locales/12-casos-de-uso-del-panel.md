# Tarea 12: Casos de uso del panel del admin

**Archivos:**
- Crear: `src/minutas/locales/aplicacion/procesador_de_imagenes.py`
- Crear: `src/minutas/locales/aplicacion/modificar_local.py`
- Crear: `src/minutas/locales/aplicacion/actualizar_datos_del_local.py`
- Crear: `src/minutas/locales/aplicacion/reemplazar_horario.py`
- Crear: `src/minutas/locales/aplicacion/cambiar_hora_de_corte.py`
- Crear: `src/minutas/locales/aplicacion/cerrar_manualmente.py`
- Crear: `src/minutas/locales/aplicacion/reabrir.py`
- Crear: `src/minutas/locales/aplicacion/subir_imagen_del_local.py`
- Crear: `src/minutas/locales/aplicacion/obtener_local_del_panel.py`
- Test: `tests/unitarios/locales/test_casos_de_uso_del_panel.py`

---

## Decisiones de diseño

**¿Por qué existen si el panel llega en la 1b?**
- El diseño entrega en la 1a todo el dominio y sus casos de uso, probados. La 1b solo los conecta a rutas HTTP con login. Mientras tanto, la prueba de punta a punta (tarea 20) los usa para cargar horarios e imágenes.

**¿Por qué `modificar_local`?**
- Los casos de uso del panel repiten "obtener, cambiar, guardar y confirmar" sobre el local de la sesión. Queda en una función y cada caso de uso dice solo qué cambia.

**¿Cómo elige `CerrarManualmente` el cierre?**
- Con una tabla de despacho (`CIERRES_POR_TIPO`) de `TipoDeCierre` a la acción del agregado, sin condicionales.

**¿En qué orden trabaja `SubirImagenDelLocal`?**
- Procesa la imagen fuera de la transacción (es CPU, no toca la base). Dentro: obtiene el local, verifica con `local.asegurar_modificable()` que se pueda modificar antes de escribir el archivo, guarda, cambia la referencia y confirma. Las imágenes reemplazadas no se borran y un archivo huérfano por una transacción fallida es aceptable, como decidió el diseño: el nombre nunca se reutiliza.

**Puerto nuevo:** `ProcesadorDeImagenes` (valida, achica y pasa a WebP). Su adaptador está en la tarea 15.

---

## Paso 1: Escribir el test que falla

`tests/unitarios/locales/test_casos_de_uso_del_panel.py`:

```python
from dataclasses import replace
from datetime import UTC, date, datetime, time

import pytest

from minutas.locales.aplicacion.actualizar_datos_del_local import ActualizarDatosDelLocal
from minutas.locales.aplicacion.cambiar_hora_de_corte import CambiarHoraDeCorte
from minutas.locales.aplicacion.cerrar_manualmente import CerrarManualmente, TipoDeCierre
from minutas.locales.aplicacion.dar_de_alta_local import DarDeAltaLocal
from minutas.locales.aplicacion.obtener_local_del_panel import ObtenerLocalDelPanel
from minutas.locales.aplicacion.reabrir import Reabrir
from minutas.locales.aplicacion.reemplazar_horario import ReemplazarHorario
from minutas.locales.aplicacion.subir_imagen_del_local import SubirImagenDelLocal
from minutas.locales.dominio.cierre_manual import CierreHastaNuevoAviso, CierrePorJornada, SinCierre
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import FranjaCortaLaHoraDeCorte, LocalSuspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import TipoDeImagen
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from soporte.imagenes_en_memoria import AlmacenDeImagenesEnMemoria, ProcesadorDeImagenesFalso
from soporte.locales_en_memoria import BaseDeLocalesEnMemoria

# Viernes 6/11/2026 a las 21:00 en Buenos Aires.
AHORA = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)


@pytest.fixture
def base() -> BaseDeLocalesEnMemoria:
    return BaseDeLocalesEnMemoria()


@pytest.fixture
async def local(base: BaseDeLocalesEnMemoria) -> Local:
    return await DarDeAltaLocal(base.crear_unidad_del_local).ejecutar(
        Slug("la-esquina"), "La Esquina", Whatsapp("5493515123456"), frozenset({Modalidad.RETIRO})
    )


async def test_actualizar_datos_guarda_e_incrementa_la_version(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    datos = replace(local.datos, nombre="La Esquina de Ana")

    await ActualizarDatosDelLocal(base.crear_unidad_del_local).ejecutar(local.id, datos)

    assert base.locales[local.id].datos == datos
    assert base.locales[local.id].version == 1


async def test_reemplazar_horario_invalido_no_guarda_nada(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    horario = Horario((FranjaHoraria(DiaDeLaSemana.LUNES, time(20), time(9)),))

    with pytest.raises(FranjaCortaLaHoraDeCorte):
        await ReemplazarHorario(base.crear_unidad_del_local).ejecutar(local.id, horario, AHORA)

    assert base.locales[local.id].horario == Horario.vacio()


async def test_cambiar_hora_de_corte_queda_pendiente(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    await CambiarHoraDeCorte(base.crear_unidad_del_local).ejecutar(local.id, time(5), AHORA)

    assert base.locales[local.id].jornada.cortes() == (time(6), time(5))


@pytest.mark.parametrize(
    ("tipo", "cierre"),
    [
        (TipoDeCierre.POR_HOY, CierrePorJornada(date(2026, 11, 6))),
        (TipoDeCierre.HASTA_NUEVO_AVISO, CierreHastaNuevoAviso()),
    ],
)
async def test_cerrar_manualmente_y_reabrir(
    base: BaseDeLocalesEnMemoria,
    local: Local,
    tipo: TipoDeCierre,
    cierre: CierrePorJornada | CierreHastaNuevoAviso,
) -> None:
    await CerrarManualmente(base.crear_unidad_del_local).ejecutar(local.id, tipo, AHORA)
    assert base.locales[local.id].cierre_manual == cierre

    await Reabrir(base.crear_unidad_del_local).ejecutar(local.id)
    assert base.locales[local.id].cierre_manual == SinCierre()


async def test_subir_imagen_la_procesa_con_las_medidas_del_tipo_y_la_guarda(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    almacen = AlmacenDeImagenesEnMemoria()
    subir = SubirImagenDelLocal(base.crear_unidad_del_local, ProcesadorDeImagenesFalso(), almacen)

    nombre = await subir.ejecutar(local.id, TipoDeImagen.LOGO, b"foto")

    assert almacen.imagenes == {nombre: b"webp 512x512:foto"}
    assert base.locales[local.id].imagenes == {TipoDeImagen.LOGO: nombre}


async def test_subir_imagen_a_un_local_suspendido_falla_sin_guardar_el_archivo(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    base.locales[local.id].suspender()
    almacen = AlmacenDeImagenesEnMemoria()
    subir = SubirImagenDelLocal(base.crear_unidad_del_local, ProcesadorDeImagenesFalso(), almacen)

    with pytest.raises(LocalSuspendido):
        await subir.ejecutar(local.id, TipoDeImagen.PORTADA, b"foto")

    assert almacen.imagenes == {}


async def test_obtener_local_del_panel_devuelve_el_local(
    base: BaseDeLocalesEnMemoria, local: Local
) -> None:
    leido = await ObtenerLocalDelPanel(base.crear_unidad_del_local).ejecutar(local.id)

    assert leido.slug == local.slug
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/unitarios/locales/test_casos_de_uso_del_panel.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.aplicacion.actualizar_datos_del_local'`

## Paso 3: Implementación

`src/minutas/locales/aplicacion/procesador_de_imagenes.py`:

```python
"""Puerto del procesador de imágenes: valida, achica y re-codifica lo que sube el local."""

from typing import Protocol

from minutas.locales.dominio.imagen import Medidas


class ProcesadorDeImagenes(Protocol):
    async def procesar(self, contenido: bytes, medidas_maximas: Medidas) -> bytes:
        """Devuelve un WebP sin metadatos dentro de las medidas.

        Lanza `ImagenInvalida` o `ImagenDemasiadoGrande`.
        """
        ...
```

`src/minutas/locales/aplicacion/modificar_local.py`:

```python
"""Paso que repiten los casos de uso del panel: obtener, cambiar, guardar y confirmar."""

from collections.abc import Callable

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


async def modificar_local(
    crear_unidad: FabricaDeUnidadesDelLocal, local_id: LocalId, cambio: Callable[[Local], object]
) -> Local:
    """Aplica el cambio al local en una transacción y devuelve el local guardado."""
    async with crear_unidad(local_id) as unidad:
        local = await unidad.locales.obtener()
        cambio(local)
        await unidad.locales.guardar(local)
        await unidad.confirmar()
    return local
```

`src/minutas/locales/aplicacion/actualizar_datos_del_local.py`:

```python
"""Caso de uso del admin: reemplazar los datos editables de su local."""

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.datos_del_local import DatosDelLocal
from minutas.locales.dominio.local import Local


class ActualizarDatosDelLocal:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId, datos: DatosDelLocal) -> Local:
        return await modificar_local(
            self._crear_unidad, local_id, lambda local: local.actualizar_datos(datos)
        )
```

`src/minutas/locales/aplicacion/reemplazar_horario.py`:

```python
"""Caso de uso del admin: reemplazar la semana completa de franjas."""

from datetime import datetime

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.local import Local


class ReemplazarHorario:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId, horario: Horario, ahora: datetime) -> Local:
        return await modificar_local(
            self._crear_unidad, local_id, lambda local: local.reemplazar_horario(horario, ahora)
        )
```

`src/minutas/locales/aplicacion/cambiar_hora_de_corte.py`:

```python
"""Caso de uso del admin: cambiar la hora de corte. Rige desde la próxima jornada."""

from datetime import datetime, time

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


class CambiarHoraDeCorte:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId, corte: time, ahora: datetime) -> Local:
        return await modificar_local(
            self._crear_unidad, local_id, lambda local: local.cambiar_hora_de_corte(corte, ahora)
        )
```

`src/minutas/locales/aplicacion/cerrar_manualmente.py`:

```python
"""Caso de uso del admin: cerrar el local por hoy o hasta nuevo aviso."""

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


class TipoDeCierre(StrEnum):
    POR_HOY = "por_hoy"
    HASTA_NUEVO_AVISO = "hasta_nuevo_aviso"


def _cerrar_por_hoy(local: Local, ahora: datetime) -> None:
    local.cerrar_por_hoy(ahora)


def _cerrar_hasta_nuevo_aviso(local: Local, _ahora: datetime) -> None:
    local.cerrar_hasta_nuevo_aviso()


CIERRES_POR_TIPO: dict[TipoDeCierre, Callable[[Local, datetime], None]] = {
    TipoDeCierre.POR_HOY: _cerrar_por_hoy,
    TipoDeCierre.HASTA_NUEVO_AVISO: _cerrar_hasta_nuevo_aviso,
}


class CerrarManualmente:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId, tipo: TipoDeCierre, ahora: datetime) -> Local:
        return await modificar_local(
            self._crear_unidad, local_id, lambda local: CIERRES_POR_TIPO[tipo](local, ahora)
        )
```

`src/minutas/locales/aplicacion/reabrir.py`:

```python
"""Caso de uso del admin: quitar el cierre manual, vigente o no."""

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.modificar_local import modificar_local
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


class Reabrir:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId) -> Local:
        return await modificar_local(self._crear_unidad, local_id, Local.reabrir)
```

`src/minutas/locales/aplicacion/subir_imagen_del_local.py`:

```python
"""Caso de uso del admin: subir el logo o la portada. Sin entrada HTTP hasta la etapa 1b."""

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.almacen_de_imagenes import AlmacenDeImagenes
from minutas.locales.aplicacion.procesador_de_imagenes import ProcesadorDeImagenes
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen


class SubirImagenDelLocal:
    def __init__(
        self,
        crear_unidad: FabricaDeUnidadesDelLocal,
        procesador: ProcesadorDeImagenes,
        almacen: AlmacenDeImagenes,
    ) -> None:
        self._crear_unidad = crear_unidad
        self._procesador = procesador
        self._almacen = almacen

    async def ejecutar(
        self, local_id: LocalId, tipo: TipoDeImagen, contenido: bytes
    ) -> NombreDeImagen:
        """Procesa fuera de la transacción. Si la transacción falla, el archivo queda huérfano:
        es aceptable, porque el nombre nunca se reutiliza."""
        procesada = await self._procesador.procesar(contenido, tipo.medidas_maximas)
        async with self._crear_unidad(local_id) as unidad:
            local = await unidad.locales.obtener()
            local.asegurar_modificable()
            nombre = await self._almacen.guardar(procesada)
            local.cambiar_imagen(tipo, nombre)
            await unidad.locales.guardar(local)
            await unidad.confirmar()
        return nombre
```

`src/minutas/locales/aplicacion/obtener_local_del_panel.py`:

```python
"""Consulta del admin: su local completo. Sin entrada HTTP hasta la etapa 1b."""

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.aplicacion.unidades_de_trabajo import FabricaDeUnidadesDelLocal
from minutas.locales.dominio.local import Local


class ObtenerLocalDelPanel:
    def __init__(self, crear_unidad: FabricaDeUnidadesDelLocal) -> None:
        self._crear_unidad = crear_unidad

    async def ejecutar(self, local_id: LocalId) -> Local:
        async with self._crear_unidad(local_id) as unidad:
            return await unidad.locales.obtener()
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/unitarios/locales/test_casos_de_uso_del_panel.py -v && uv run mypy`
Expected: PASS (8 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/locales/aplicacion/procesador_de_imagenes.py src/minutas/locales/aplicacion/modificar_local.py src/minutas/locales/aplicacion/actualizar_datos_del_local.py src/minutas/locales/aplicacion/reemplazar_horario.py src/minutas/locales/aplicacion/cambiar_hora_de_corte.py src/minutas/locales/aplicacion/cerrar_manualmente.py src/minutas/locales/aplicacion/reabrir.py src/minutas/locales/aplicacion/subir_imagen_del_local.py src/minutas/locales/aplicacion/obtener_local_del_panel.py tests/unitarios/locales/test_casos_de_uso_del_panel.py
git commit -m "feat(locales): casos de uso del panel del admin" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
