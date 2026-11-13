# Tarea 14: Repositorio, directorio y unidades de trabajo sobre SQLAlchemy

**Archivos:**
- Crear: `src/minutas/compartido/infraestructura/errores_de_base.py`
- Crear: `src/minutas/locales/infraestructura/repositorio_de_locales_sqlalchemy.py`
- Crear: `src/minutas/locales/infraestructura/directorio_de_locales_sqlalchemy.py`
- Crear: `src/minutas/locales/infraestructura/unidades_de_trabajo_sqlalchemy.py`
- Test: `tests/integracion/test_repositorio_de_locales.py`

---

## Decisiones de diseño

**¿Cómo se guarda el agregado?**
- Una fila en `locales` y una por franja. `guardar` hace `UPDATE ... WHERE id = :id AND version = :leida` y, si actualizó exactamente una fila, llama a `local.registrar_guardado()`. Si no, lanza `LocalModificadoEnParalelo` (409). Se eligió bloqueo optimista para no retener bloqueos mientras el admin edita.
- Las franjas se reemplazan (borrar e insertar, con ids nuevos) solo si el horario cambió respecto del que se leyó: suspender o cerrar no las reescribe. Ningún otro dato apunta a una franja por id.

**¿Cómo se traduce cada variante?**
- Con tablas de despacho por tipo, en los dos sentidos (`CODIGOS_DE_ESTADO`/`ESTADOS`, `CODIGOS_DE_CIERRE`/`CIERRES`): el vocabulario de las columnas vive en la infraestructura, no en el dominio. La jornada se guarda con `reglas_vigentes` y `cambio_pendiente`, y se reconstruye con un condicional en el mapper, como permite la convención.

**¿Cómo se detecta un slug repetido?**
- `viola_restriccion` compara el `constraint_name` que informa asyncpg (`uq_locales_slug`), sin depender del idioma de los mensajes. La unicidad vale entre todos los locales aunque haya RLS: las restricciones no pasan por las políticas.

**¿Por qué el repositorio filtra por `id` si hay RLS?**
- Porque la lectura de `locales` es abierta: sin el filtro vería todos. En `franjas_horarias` el filtro y el RLS coinciden.

---

## Paso 1: Escribir el test que falla

`tests/integracion/test_repositorio_de_locales.py`:

```python
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.cierre_manual import CierrePorJornada
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import (
    LocalModificadoEnParalelo,
    LocalNoEncontrado,
    SlugEnUso,
)
from minutas.locales.dominio.estado_del_local import Suspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.local import Local, crear_local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria
from minutas.locales.infraestructura.unidades_de_trabajo_sqlalchemy import (
    UnidadDelDirectorioSQLAlchemy,
    UnidadDelLocalSQLAlchemy,
)

pytestmark = pytest.mark.integracion

LEER_IDS_DE_FRANJAS = text("SELECT id FROM franjas_horarias ORDER BY id")

type Fabrica = async_sessionmaker[AsyncSession]

# Viernes 6/11/2026 a las 21:00 en Buenos Aires.
AHORA = datetime(2026, 11, 7, 0, 0, tzinfo=UTC)
LOGO = NombreDeImagen("01a18e9b-3c49-75a8-a745-cbce398ad79a.webp")


def nuevo_local(slug: str = "la-esquina") -> Local:
    return crear_local(
        Slug(slug),
        "La Esquina",
        Whatsapp("5493515123456"),
        frozenset({Modalidad.DELIVERY, Modalidad.RETIRO}),
    )


async def agregar(fabrica: Fabrica, local: Local) -> None:
    async with UnidadDelLocalSQLAlchemy(fabrica, local.id) as unidad:
        await unidad.locales.agregar(local)
        await unidad.confirmar()


async def obtener(fabrica: Fabrica, local_id: LocalId) -> Local:
    async with UnidadDelLocalSQLAlchemy(fabrica, local_id) as unidad:
        return await unidad.locales.obtener()


async def guardar(fabrica: Fabrica, local: Local) -> None:
    async with UnidadDelLocalSQLAlchemy(fabrica, local.id) as unidad:
        await unidad.locales.guardar(local)
        await unidad.confirmar()


async def test_agregar_y_obtener_conserva_todo_el_agregado(fabrica_de_sesiones: Fabrica) -> None:
    local = nuevo_local()
    local.reemplazar_horario(
        Horario(
            (
                FranjaHoraria(DiaDeLaSemana.LUNES, time(12), time(15)),
                FranjaHoraria(DiaDeLaSemana.DOMINGO, time(20), time(1, 30)),
            )
        ),
        AHORA,
    )
    local.cerrar_por_hoy(AHORA)
    local.cambiar_imagen(TipoDeImagen.LOGO, LOGO)
    local.cambiar_zona_horaria(ZonaHoraria("America/Santiago"), AHORA)
    local.suspender()
    await agregar(fabrica_de_sesiones, local)

    leido = await obtener(fabrica_de_sesiones, local.id)

    assert leido.slug == local.slug
    assert leido.datos == local.datos
    assert leido.horario == local.horario
    assert leido.cierre_manual == local.cierre_manual
    assert leido.jornada == local.jornada
    assert leido.imagenes == {TipoDeImagen.LOGO: LOGO}
    assert leido.estado == Suspendido()
    assert leido.version == 0


async def test_guardar_reemplaza_las_franjas_e_incrementa_la_version(
    fabrica_de_sesiones: Fabrica,
) -> None:
    local = nuevo_local()
    await agregar(fabrica_de_sesiones, local)
    leido = await obtener(fabrica_de_sesiones, local.id)
    horario = Horario((FranjaHoraria(DiaDeLaSemana.MARTES, time(20), time(0, 30)),))
    leido.reemplazar_horario(horario, AHORA)

    await guardar(fabrica_de_sesiones, leido)

    guardado = await obtener(fabrica_de_sesiones, local.id)
    assert guardado.horario == horario
    assert guardado.version == 1


async def test_suspension_durante_una_edicion_del_admin_no_se_pierde(
    fabrica_de_sesiones: Fabrica,
) -> None:
    local = nuevo_local()
    await agregar(fabrica_de_sesiones, local)

    async with UnidadDelLocalSQLAlchemy(fabrica_de_sesiones, local.id) as edicion_del_admin:
        leido_por_el_admin = await edicion_del_admin.locales.obtener()

        a_suspender = await obtener(fabrica_de_sesiones, local.id)
        a_suspender.suspender()
        await guardar(fabrica_de_sesiones, a_suspender)

        leido_por_el_admin.reabrir()
        with pytest.raises(LocalModificadoEnParalelo, match="volvé a cargarlo"):
            await edicion_del_admin.locales.guardar(leido_por_el_admin)

    assert (await obtener(fabrica_de_sesiones, local.id)).estado == Suspendido()


async def test_agregar_local_con_slug_en_uso_falla(fabrica_de_sesiones: Fabrica) -> None:
    await agregar(fabrica_de_sesiones, nuevo_local())

    with pytest.raises(SlugEnUso, match="la-esquina"):
        await agregar(fabrica_de_sesiones, nuevo_local())


async def test_guardar_con_el_slug_de_otro_local_falla(fabrica_de_sesiones: Fabrica) -> None:
    await agregar(fabrica_de_sesiones, nuevo_local())
    otro = nuevo_local("el-rincon")
    await agregar(fabrica_de_sesiones, otro)
    otro.cambiar_slug(Slug("la-esquina"))

    with pytest.raises(SlugEnUso):
        await guardar(fabrica_de_sesiones, otro)


async def test_obtener_local_inexistente_falla(fabrica_de_sesiones: Fabrica) -> None:
    with pytest.raises(LocalNoEncontrado):
        await obtener(fabrica_de_sesiones, LocalId.generar())


async def test_directorio_resuelve_el_slug_sin_local_fijado(fabrica_de_sesiones: Fabrica) -> None:
    local = nuevo_local()
    await agregar(fabrica_de_sesiones, local)

    async with UnidadDelDirectorioSQLAlchemy(fabrica_de_sesiones) as unidad:
        encontrado = await unidad.directorio.obtener_local_id_por_slug(Slug("la-esquina"))
        with pytest.raises(LocalNoEncontrado, match="no-existe"):
            await unidad.directorio.obtener_local_id_por_slug(Slug("no-existe"))

    assert encontrado == local.id


async def test_cierre_por_jornada_se_guarda_con_su_jornada(fabrica_de_sesiones: Fabrica) -> None:
    local = nuevo_local()
    local.cerrar_por_hoy(AHORA)
    await agregar(fabrica_de_sesiones, local)

    leido = await obtener(fabrica_de_sesiones, local.id)

    assert leido.cierre_manual == CierrePorJornada(date(2026, 11, 6))


async def test_guardar_sin_cambiar_el_horario_no_reescribe_las_franjas(
    fabrica_de_sesiones: Fabrica,
) -> None:
    local = nuevo_local()
    local.reemplazar_horario(
        Horario((FranjaHoraria(DiaDeLaSemana.LUNES, time(12), time(15)),)), AHORA
    )
    await agregar(fabrica_de_sesiones, local)

    async with UnidadDelLocalSQLAlchemy(fabrica_de_sesiones, local.id) as unidad:
        antes = (await unidad.sesion.scalars(LEER_IDS_DE_FRANJAS)).all()
        leido = await unidad.locales.obtener()
        leido.suspender()
        await unidad.locales.guardar(leido)
        despues = (await unidad.sesion.scalars(LEER_IDS_DE_FRANJAS)).all()

    assert antes == despues
    assert len(antes) == 1
```

## Paso 2: Correr el test y ver que falla

Run: `uv run pytest tests/integracion/test_repositorio_de_locales.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'minutas.locales.infraestructura.unidades_de_trabajo_sqlalchemy'`

## Paso 3: Implementación

`src/minutas/compartido/infraestructura/errores_de_base.py`:

```python
"""Traducción de errores de PostgreSQL a errores de dominio."""

from sqlalchemy.exc import IntegrityError


def viola_restriccion(error: IntegrityError, restriccion: str) -> bool:
    """Si el error lo causó la restricción con ese nombre.

    asyncpg informa el nombre en `constraint_name`; no depende del idioma de los mensajes.
    """
    causa = getattr(error.orig, "__cause__", None)
    return getattr(causa, "constraint_name", None) == restriccion
```

`src/minutas/locales/infraestructura/repositorio_de_locales_sqlalchemy.py`:

```python
"""Repositorio del local fijado, sobre SQLAlchemy Core, con traducción explícita fila ↔ dominio."""

from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, cast

from sqlalchemy import CursorResult, Executable, RowMapping, delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from minutas.compartido.dominio.identificador import Identificador
from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura.errores_de_base import viola_restriccion
from minutas.locales.dominio.cierre_manual import (
    CierreHastaNuevoAviso,
    CierreManual,
    CierrePorJornada,
    SinCierre,
)
from minutas.locales.dominio.color import Color
from minutas.locales.dominio.datos_del_local import DatosDelLocal
from minutas.locales.dominio.dia_de_la_semana import DiaDeLaSemana
from minutas.locales.dominio.errores import LocalModificadoEnParalelo, LocalNoEncontrado, SlugEnUso
from minutas.locales.dominio.estado_del_local import Activo, EstadoDelLocal, Suspendido
from minutas.locales.dominio.franja_horaria import FranjaHoraria
from minutas.locales.dominio.horario import Horario
from minutas.locales.dominio.imagen import NombreDeImagen, TipoDeImagen
from minutas.locales.dominio.jornada import Jornada, JornadaConCambioPendiente, JornadaFija
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.reglas_de_jornada import ReglasDeJornada
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.whatsapp import Whatsapp
from minutas.locales.dominio.zona_horaria import ZonaHoraria
from minutas.locales.infraestructura.tablas import FRANJAS_HORARIAS, LOCALES

RESTRICCION_DE_SLUG = "uq_locales_slug"
MENSAJE_DE_CONFLICTO = "El local cambió mientras lo editabas; volvé a cargarlo e intentá de nuevo"

# El vocabulario de las columnas vive acá, no en el dominio: tablas de despacho en los dos sentidos.
CODIGOS_DE_ESTADO: dict[type[EstadoDelLocal], str] = {Activo: "activo", Suspendido: "suspendido"}
ESTADOS: dict[str, Callable[[], EstadoDelLocal]] = {"activo": Activo, "suspendido": Suspendido}
CODIGOS_DE_CIERRE: dict[type[CierreManual], str | None] = {
    SinCierre: None,
    CierrePorJornada: "por_jornada",
    CierreHastaNuevoAviso: "hasta_nuevo_aviso",
}
CIERRES: dict[str | None, Callable[[date | None], CierreManual]] = {
    None: lambda _jornada: SinCierre(),
    "por_jornada": lambda jornada: CierrePorJornada(cast(date, jornada)),
    "hasta_nuevo_aviso": lambda _jornada: CierreHastaNuevoAviso(),
}


class RepositorioDeLocalesSQLAlchemy:
    """Trabaja solo sobre el local fijado: RLS impide escribir otro."""

    def __init__(self, sesion: AsyncSession, local_id: LocalId) -> None:
        self._sesion = sesion
        self._local_id = local_id
        self._horario_leido: Horario | None = None

    async def obtener(self) -> Local:
        fila = (
            (
                await self._sesion.execute(
                    select(LOCALES).where(LOCALES.c.id == self._local_id.valor)
                )
            )
            .mappings()
            .one_or_none()
        )
        if fila is None:
            raise LocalNoEncontrado("El local no existe")
        franjas = (
            await self._sesion.execute(
                select(FRANJAS_HORARIAS)
                .where(FRANJAS_HORARIAS.c.local_id == self._local_id.valor)
                .order_by(FRANJAS_HORARIAS.c.dia, FRANJAS_HORARIAS.c.apertura)
            )
        ).mappings()
        local = _desde_filas(fila, franjas.all())
        self._horario_leido = local.horario
        return local

    async def agregar(self, local: Local) -> None:
        await self._escribir(insert(LOCALES).values(_a_fila(local)), local.slug)
        await self._insertar_franjas(local)

    async def guardar(self, local: Local) -> None:
        """Bloqueo optimista: solo escribe si nadie guardó el local desde que se leyó."""
        sentencia = (
            update(LOCALES)
            .where(LOCALES.c.id == local.id.valor, LOCALES.c.version == local.version)
            .values({**_a_fila(local), "version": local.version + 1, "actualizado_en": func.now()})
        )
        resultado = await self._escribir(sentencia, local.slug)
        if resultado.rowcount != 1:
            raise LocalModificadoEnParalelo(MENSAJE_DE_CONFLICTO)
        local.registrar_guardado()
        if local.horario != self._horario_leido:
            await self._reemplazar_franjas(local)

    async def _reemplazar_franjas(self, local: Local) -> None:
        """Solo cuando el horario cambió: suspender o cerrar no reescribe las franjas."""
        await self._sesion.execute(
            delete(FRANJAS_HORARIAS).where(FRANJAS_HORARIAS.c.local_id == local.id.valor)
        )
        await self._insertar_franjas(local)
        self._horario_leido = local.horario

    async def _insertar_franjas(self, local: Local) -> None:
        filas = [
            {
                "id": Identificador.generar().valor,
                "local_id": local.id.valor,
                "dia": franja.dia.value,
                "apertura": franja.apertura,
                "cierre": franja.cierre,
            }
            for franja in local.horario.franjas
        ]
        if filas:
            await self._sesion.execute(insert(FRANJAS_HORARIAS), filas)

    async def _escribir(self, sentencia: Executable, slug: Slug) -> CursorResult[Any]:
        try:
            return cast(CursorResult[Any], await self._sesion.execute(sentencia))
        except IntegrityError as error:
            if viola_restriccion(error, RESTRICCION_DE_SLUG):
                raise SlugEnUso(f"El slug '{slug}' ya está en uso") from error
            raise


def _a_fila(local: Local) -> dict[str, Any]:
    datos, jornada, imagenes = local.datos, local.jornada, local.imagenes
    pendiente = _reglas_pendientes(jornada)
    vigentes = jornada.reglas_vigentes
    return {
        "id": local.id.valor,
        "slug": local.slug.valor,
        "nombre": datos.nombre,
        "descripcion": datos.descripcion,
        "direccion": datos.direccion,
        "whatsapp": datos.whatsapp.numero,
        "color": datos.color.hexadecimal,
        "ofrece_delivery": Modalidad.DELIVERY in datos.modalidades,
        "ofrece_retiro": Modalidad.RETIRO in datos.modalidades,
        "zona_horaria": vigentes.zona.nombre,
        "hora_de_corte": vigentes.corte,
        **pendiente,
        "cierre_manual": CODIGOS_DE_CIERRE[type(local.cierre_manual)],
        "cierre_manual_jornada": _jornada_del_cierre(local.cierre_manual),
        "logo": _nombre(imagenes.get(TipoDeImagen.LOGO)),
        "portada": _nombre(imagenes.get(TipoDeImagen.PORTADA)),
        "estado": CODIGOS_DE_ESTADO[type(local.estado)],
        "version": local.version,
    }


def _reglas_pendientes(jornada: Jornada) -> dict[str, Any]:
    pendientes, desde = jornada.cambio_pendiente or (None, None)
    return {
        "zona_horaria_pendiente": pendientes.zona.nombre if pendientes else None,
        "hora_de_corte_pendiente": pendientes.corte if pendientes else None,
        "reglas_desde_jornada": desde,
    }


def _jornada_del_cierre(cierre: CierreManual) -> date | None:
    return cierre.jornada if isinstance(cierre, CierrePorJornada) else None


def _nombre(nombre: NombreDeImagen | None) -> str | None:
    return None if nombre is None else nombre.valor


def _jornada_desde_fila(fila: RowMapping) -> Jornada:
    vigentes = ReglasDeJornada(ZonaHoraria(fila["zona_horaria"]), fila["hora_de_corte"])
    if fila["reglas_desde_jornada"] is None:
        return JornadaFija(vigentes)
    pendientes = ReglasDeJornada(
        ZonaHoraria(fila["zona_horaria_pendiente"]), fila["hora_de_corte_pendiente"]
    )
    return JornadaConCambioPendiente(vigentes, pendientes, fila["reglas_desde_jornada"])


def _desde_filas(fila: RowMapping, franjas: Sequence[RowMapping]) -> Local:
    modalidades = {
        Modalidad.DELIVERY: fila["ofrece_delivery"],
        Modalidad.RETIRO: fila["ofrece_retiro"],
    }
    datos = DatosDelLocal(
        nombre=fila["nombre"],
        descripcion=fila["descripcion"],
        direccion=fila["direccion"],
        whatsapp=Whatsapp(fila["whatsapp"]),
        color=Color(fila["color"]),
        modalidades=frozenset(modalidad for modalidad, ofrece in modalidades.items() if ofrece),
    )
    horario = Horario(
        tuple(
            FranjaHoraria(DiaDeLaSemana(franja["dia"]), franja["apertura"], franja["cierre"])
            for franja in franjas
        )
    )
    imagenes = {tipo: NombreDeImagen(fila[tipo.value]) for tipo in TipoDeImagen if fila[tipo.value]}
    return Local(
        id=LocalId(fila["id"]),
        slug=Slug(fila["slug"]),
        datos=datos,
        jornada=_jornada_desde_fila(fila),
        horario=horario,
        cierre_manual=CIERRES[fila["cierre_manual"]](fila["cierre_manual_jornada"]),
        imagenes=imagenes,
        estado=ESTADOS[fila["estado"]](),
        version=fila["version"],
    )
```

`src/minutas/locales/infraestructura/directorio_de_locales_sqlalchemy.py`:

```python
"""Directorio de locales: resuelve el slug sin local fijado (la lectura de `locales` es abierta)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.errores import LocalNoEncontrado
from minutas.locales.dominio.slug import Slug
from minutas.locales.infraestructura.tablas import LOCALES


class DirectorioDeLocalesSQLAlchemy:
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_local_id_por_slug(self, slug: Slug) -> LocalId:
        valor = await self._sesion.scalar(select(LOCALES.c.id).where(LOCALES.c.slug == slug.valor))
        if valor is None:
            raise LocalNoEncontrado(f"No hay un local con el slug '{slug}'")
        return LocalId(valor)
```

`src/minutas/locales/infraestructura/unidades_de_trabajo_sqlalchemy.py`:

```python
"""Adaptadores de las unidades de trabajo de Locales."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from minutas.compartido.dominio.local_id import LocalId
from minutas.compartido.infraestructura.unidad_de_trabajo_sqlalchemy import (
    UnidadDeTrabajoDePlataformaSQLAlchemy,
    UnidadDeTrabajoSQLAlchemy,
)
from minutas.locales.infraestructura.directorio_de_locales_sqlalchemy import (
    DirectorioDeLocalesSQLAlchemy,
)
from minutas.locales.infraestructura.repositorio_de_locales_sqlalchemy import (
    RepositorioDeLocalesSQLAlchemy,
)


class UnidadDelLocalSQLAlchemy(UnidadDeTrabajoSQLAlchemy):
    """Fija `app.local_id` al entrar: las políticas de RLS solo dejan escribir ese local."""

    def __init__(
        self, fabrica_de_sesiones: async_sessionmaker[AsyncSession], local_id: LocalId
    ) -> None:
        super().__init__(fabrica_de_sesiones, local_id)
        self.locales = RepositorioDeLocalesSQLAlchemy(self.sesion, local_id)


class UnidadDelDirectorioSQLAlchemy(UnidadDeTrabajoDePlataformaSQLAlchemy):
    """Sin local fijado: solo puede leer `locales` para resolver un slug."""

    def __init__(self, fabrica_de_sesiones: async_sessionmaker[AsyncSession]) -> None:
        super().__init__(fabrica_de_sesiones)
        self.directorio = DirectorioDeLocalesSQLAlchemy(self.sesion)
```

## Paso 4: Correr los tests y ver que pasan

Run: `uv run pytest tests/integracion/test_repositorio_de_locales.py -v && uv run mypy`
Expected: PASS (9 passed) y `Success: no issues found`

## Paso 5: Commit

```bash
git add src/minutas/compartido/infraestructura/errores_de_base.py src/minutas/locales/infraestructura/repositorio_de_locales_sqlalchemy.py src/minutas/locales/infraestructura/directorio_de_locales_sqlalchemy.py src/minutas/locales/infraestructura/unidades_de_trabajo_sqlalchemy.py tests/integracion/test_repositorio_de_locales.py
git commit -m "feat(locales): repositorio con bloqueo optimista y directorio de slugs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
