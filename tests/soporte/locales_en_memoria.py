"""Dobles en memoria del contexto Locales: transacciones, RLS y bloqueo optimista como la base."""

from copy import deepcopy
from types import TracebackType
from typing import Self

from minutas.compartido.dominio.local_id import LocalId
from minutas.locales.dominio.errores import LocalModificadoEnParalelo, LocalNoEncontrado, SlugEnUso
from minutas.locales.dominio.local import Local
from minutas.locales.dominio.slug import Slug


class BaseDeLocalesEnMemoria:
    """Estado confirmado. Cada unidad de trabajo trabaja sobre una copia que aplica al confirmar."""

    def __init__(self) -> None:
        self.locales: dict[LocalId, Local] = {}

    def crear_unidad_del_local(self, local_id: LocalId) -> "UnidadDelLocalEnMemoria":
        return UnidadDelLocalEnMemoria(self, local_id)

    def crear_unidad_del_directorio(self) -> "UnidadDelDirectorioEnMemoria":
        return UnidadDelDirectorioEnMemoria(self)


class _Transaccion:
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        traza: TracebackType | None,
    ) -> None:
        return None


class RepositorioDeLocalesEnMemoria:
    """Ve solo el local fijado, como el repositorio real con RLS."""

    def __init__(self, base: BaseDeLocalesEnMemoria, local_id: LocalId) -> None:
        self._base = base
        self._local_id = local_id
        self.pendiente: Local | None = None
        self.version_leida: int | None = None

    async def obtener(self) -> Local:
        guardado = self._base.locales.get(self._local_id)
        if guardado is None:
            raise LocalNoEncontrado("El local no existe")
        self.version_leida = guardado.version
        return deepcopy(guardado)

    async def agregar(self, local: Local) -> None:
        assert local.id == self._local_id, "RLS: solo se inserta el local fijado"
        self._asegurar_slug_libre(local)
        self.pendiente = deepcopy(local)

    async def guardar(self, local: Local) -> None:
        guardado = self._base.locales.get(local.id)
        if guardado is None:
            raise LocalNoEncontrado("El local no existe")
        if guardado.version != local.version:
            raise LocalModificadoEnParalelo("El local cambió mientras lo editabas")
        self._asegurar_slug_libre(local)
        local.registrar_guardado()
        self.pendiente = deepcopy(local)

    def _asegurar_slug_libre(self, local: Local) -> None:
        if any(
            otro.slug == local.slug and otro.id != local.id for otro in self._base.locales.values()
        ):
            raise SlugEnUso(f"El slug '{local.slug}' ya está en uso")


class UnidadDelLocalEnMemoria(_Transaccion):
    def __init__(self, base: BaseDeLocalesEnMemoria, local_id: LocalId) -> None:
        self._base = base
        self.local_id = local_id
        self.locales = RepositorioDeLocalesEnMemoria(base, local_id)

    async def confirmar(self) -> None:
        """Aplica el cambio, salvo que otra unidad haya guardado el local antes (como el UPDATE)."""
        pendiente = self.locales.pendiente
        if pendiente is None:
            return
        confirmado = self._base.locales.get(pendiente.id)
        if confirmado is not None and confirmado.version != pendiente.version - 1:
            raise LocalModificadoEnParalelo("El local cambió mientras lo editabas")
        self._base.locales[pendiente.id] = pendiente


class DirectorioEnMemoria:
    def __init__(self, base: BaseDeLocalesEnMemoria) -> None:
        self._base = base

    async def obtener_local_id_por_slug(self, slug: Slug) -> LocalId:
        encontrado = next(
            (local.id for local in self._base.locales.values() if local.slug == slug), None
        )
        if encontrado is None:
            raise LocalNoEncontrado(f"No hay un local con el slug '{slug}'")
        return encontrado


class UnidadDelDirectorioEnMemoria(_Transaccion):
    def __init__(self, base: BaseDeLocalesEnMemoria) -> None:
        self.directorio = DirectorioEnMemoria(base)

    async def confirmar(self) -> None:
        return None
