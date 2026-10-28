"""Base: punto de partida de las migraciones."""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Las tablas llegan con cada contexto desde la etapa 1; acá solo se protege alembic_version."""
    op.execute("REVOKE ALL ON alembic_version FROM minutas_app")


def downgrade() -> None:
    """No se devuelve el permiso a minutas_app."""
