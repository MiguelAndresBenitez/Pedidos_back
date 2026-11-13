"""Reloj real, en UTC."""

from datetime import UTC, datetime


class RelojDelSistema:
    def ahora(self) -> datetime:
        return datetime.now(UTC)
