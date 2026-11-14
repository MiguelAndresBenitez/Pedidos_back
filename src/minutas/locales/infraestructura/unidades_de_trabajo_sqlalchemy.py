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
