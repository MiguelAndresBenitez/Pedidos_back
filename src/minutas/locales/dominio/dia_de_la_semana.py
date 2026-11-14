"""Días de la semana con la numeración de Python (`date.weekday()`): lunes = 0, domingo = 6."""

from enum import IntEnum


class DiaDeLaSemana(IntEnum):
    LUNES = 0
    MARTES = 1
    MIERCOLES = 2
    JUEVES = 3
    VIERNES = 4
    SABADO = 5
    DOMINGO = 6
