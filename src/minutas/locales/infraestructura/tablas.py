"""Tablas del contexto Locales. `locales` tiene RLS por operación; `franjas_horarias`, completo."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Table,
    Text,
    Time,
    Uuid,
    func,
)

from minutas.compartido.infraestructura.metadata import METADATA

LOCALES = Table(
    "locales",
    METADATA,
    Column("id", Uuid, primary_key=True),
    Column("slug", Text, nullable=False, unique=True),
    Column("nombre", Text, nullable=False),
    Column("descripcion", Text),
    Column("direccion", Text),
    Column("whatsapp", Text, nullable=False),
    Column("color", Text, nullable=False),
    Column("ofrece_delivery", Boolean, nullable=False),
    Column("ofrece_retiro", Boolean, nullable=False),
    Column("zona_horaria", Text, nullable=False),
    Column("hora_de_corte", Time, nullable=False),
    Column("zona_horaria_pendiente", Text),
    Column("hora_de_corte_pendiente", Time),
    Column("reglas_desde_jornada", Date),
    Column("cierre_manual", Text),
    Column("cierre_manual_jornada", Date),
    Column("logo", Text),
    Column("portada", Text),
    Column("estado", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("creado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("actualizado_en", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("ofrece_delivery OR ofrece_retiro", name="modalidades"),
    CheckConstraint("estado IN ('activo', 'suspendido')", name="estado"),
    CheckConstraint(
        "num_nulls(zona_horaria_pendiente, hora_de_corte_pendiente, reglas_desde_jornada) "
        "IN (0, 3)",
        name="reglas_pendientes",
    ),
    CheckConstraint("cierre_manual IN ('por_jornada', 'hasta_nuevo_aviso')", name="cierre_manual"),
    CheckConstraint(
        "(cierre_manual IS NOT DISTINCT FROM 'por_jornada') = (cierre_manual_jornada IS NOT NULL)",
        name="cierre_manual_jornada",
    ),
)

FRANJAS_HORARIAS = Table(
    "franjas_horarias",
    METADATA,
    Column("id", Uuid, primary_key=True),
    Column("local_id", Uuid, ForeignKey("locales.id"), nullable=False, index=True),
    Column("dia", SmallInteger, nullable=False),
    Column("apertura", Time, nullable=False),
    Column("cierre", Time, nullable=False),
    CheckConstraint("dia BETWEEN 0 AND 6", name="dia"),
)
