"""Datos de conexión al PostgreSQL de pruebas, con sus tres roles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BaseDePrueba:
    host: str
    puerto: int
    nombre: str
    usuario_admin: str
    clave_admin: str

    def dsn(self, usuario: str, clave: str) -> str:
        return f"postgresql://{usuario}:{clave}@{self.host}:{self.puerto}/{self.nombre}"

    def dsn_admin(self) -> str:
        return self.dsn(self.usuario_admin, self.clave_admin)

    def dsn_owner(self) -> str:
        return self.dsn("minutas_owner", "owner-pruebas")

    def dsn_app(self) -> str:
        return self.dsn("minutas_app", "app-pruebas")

    def url_owner(self) -> str:
        return self.dsn_owner().replace("postgresql://", "postgresql+asyncpg://", 1)

    def url_app(self) -> str:
        return self.dsn_app().replace("postgresql://", "postgresql+asyncpg://", 1)
