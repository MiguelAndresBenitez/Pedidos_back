"""Locales y franjas horarias, con RLS: `locales` por operación y `franjas_horarias` completo."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AHORA = sa.text("now()")
LOCAL_FIJADO = "id = current_setting('app.local_id')::uuid"

# Lectura abierta para resolver el slug; escritura solo con ese local fijado. Sin DELETE.
AISLAMIENTO_DE_LOCALES = [
    "ALTER TABLE locales ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE locales FORCE ROW LEVEL SECURITY",
    "CREATE POLICY lectura_publica ON locales FOR SELECT USING (true)",
    f"CREATE POLICY alta_propia ON locales FOR INSERT WITH CHECK ({LOCAL_FIJADO})",
    f"CREATE POLICY escritura_propia ON locales FOR UPDATE "
    f"USING ({LOCAL_FIJADO}) WITH CHECK ({LOCAL_FIJADO})",
]

# La política estándar de la etapa 0, copiada: la migración no depende del código de la app.
DEL_LOCAL = "local_id = current_setting('app.local_id')::uuid"
AISLAMIENTO_DE_FRANJAS = [
    "ALTER TABLE franjas_horarias ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE franjas_horarias FORCE ROW LEVEL SECURITY",
    f"CREATE POLICY aislamiento_local ON franjas_horarias USING ({DEL_LOCAL}) "
    f"WITH CHECK ({DEL_LOCAL})",
]


def upgrade() -> None:
    op.create_table(
        "locales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("nombre", sa.Text(), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("direccion", sa.Text(), nullable=True),
        sa.Column("whatsapp", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("ofrece_delivery", sa.Boolean(), nullable=False),
        sa.Column("ofrece_retiro", sa.Boolean(), nullable=False),
        sa.Column("zona_horaria", sa.Text(), nullable=False),
        sa.Column("hora_de_corte", sa.Time(), nullable=False),
        sa.Column("zona_horaria_pendiente", sa.Text(), nullable=True),
        sa.Column("hora_de_corte_pendiente", sa.Time(), nullable=True),
        sa.Column("reglas_desde_jornada", sa.Date(), nullable=True),
        sa.Column("cierre_manual", sa.Text(), nullable=True),
        sa.Column("cierre_manual_jornada", sa.Date(), nullable=True),
        sa.Column("logo", sa.Text(), nullable=True),
        sa.Column("portada", sa.Text(), nullable=True),
        sa.Column("estado", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False),
        sa.Column(
            "actualizado_en", sa.DateTime(timezone=True), server_default=AHORA, nullable=False
        ),
        sa.CheckConstraint("ofrece_delivery OR ofrece_retiro", name=op.f("ck_locales_modalidades")),
        sa.CheckConstraint("estado IN ('activo', 'suspendido')", name=op.f("ck_locales_estado")),
        sa.CheckConstraint(
            "num_nulls(zona_horaria_pendiente, hora_de_corte_pendiente, reglas_desde_jornada) "
            "IN (0, 3)",
            name=op.f("ck_locales_reglas_pendientes"),
        ),
        sa.CheckConstraint(
            "cierre_manual IN ('por_jornada', 'hasta_nuevo_aviso')",
            name=op.f("ck_locales_cierre_manual"),
        ),
        sa.CheckConstraint(
            "(cierre_manual IS NOT DISTINCT FROM 'por_jornada') = "
            "(cierre_manual_jornada IS NOT NULL)",
            name=op.f("ck_locales_cierre_manual_jornada"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locales")),
        sa.UniqueConstraint("slug", name=op.f("uq_locales_slug")),
    )
    op.create_table(
        "franjas_horarias",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("local_id", sa.Uuid(), nullable=False),
        sa.Column("dia", sa.SmallInteger(), nullable=False),
        sa.Column("apertura", sa.Time(), nullable=False),
        sa.Column("cierre", sa.Time(), nullable=False),
        sa.CheckConstraint("dia BETWEEN 0 AND 6", name=op.f("ck_franjas_horarias_dia")),
        sa.ForeignKeyConstraint(
            ["local_id"], ["locales.id"], name=op.f("fk_franjas_horarias_local_id_locales")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_franjas_horarias")),
    )
    op.create_index(
        op.f("ix_franjas_horarias_local_id"), "franjas_horarias", ["local_id"], unique=False
    )
    for sentencia in [*AISLAMIENTO_DE_LOCALES, *AISLAMIENTO_DE_FRANJAS]:
        op.execute(sentencia)


def downgrade() -> None:
    op.drop_table("franjas_horarias")
    op.drop_table("locales")
