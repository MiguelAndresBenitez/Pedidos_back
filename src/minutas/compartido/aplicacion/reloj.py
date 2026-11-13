"""Puerto de reloj: la hora actual llega de afuera para poder fijarla en los tests."""

from datetime import datetime
from typing import Protocol


class Reloj(Protocol):
    def ahora(self) -> datetime:
        """Instante actual, con zona horaria."""
        ...
