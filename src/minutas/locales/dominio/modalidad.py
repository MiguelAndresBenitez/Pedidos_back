"""Modalidades de entrega que ofrece un local."""

from enum import StrEnum


class Modalidad(StrEnum):
    DELIVERY = "delivery"
    RETIRO = "retiro"
