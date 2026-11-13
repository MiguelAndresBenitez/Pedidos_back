"""Errores de dominio del contexto Locales."""

from minutas.compartido.dominio.errores import (
    AccesoDenegado,
    Conflicto,
    NoEncontrado,
    ReglaDeNegocioIncumplida,
)


class SlugInvalido(ReglaDeNegocioIncumplida):
    codigo = "slug_invalido"


class SlugReservado(ReglaDeNegocioIncumplida):
    codigo = "slug_reservado"


class DatoDelLocalInvalido(ReglaDeNegocioIncumplida):
    codigo = "dato_del_local_invalido"


class WhatsappInvalido(ReglaDeNegocioIncumplida):
    codigo = "whatsapp_invalido"


class ZonaHorariaInvalida(ReglaDeNegocioIncumplida):
    codigo = "zona_horaria_invalida"


class FranjaAmbigua(ReglaDeNegocioIncumplida):
    codigo = "franja_ambigua"


class HorariosSuperpuestos(ReglaDeNegocioIncumplida):
    codigo = "horarios_superpuestos"


class FranjaCortaLaHoraDeCorte(ReglaDeNegocioIncumplida):
    codigo = "franja_corta_la_hora_de_corte"


class ImagenInvalida(ReglaDeNegocioIncumplida):
    codigo = "imagen_invalida"


class ImagenDemasiadoGrande(ReglaDeNegocioIncumplida):
    codigo = "imagen_demasiado_grande"


class SlugEnUso(Conflicto):
    codigo = "slug_en_uso"


class LocalModificadoEnParalelo(Conflicto):
    codigo = "local_modificado_en_paralelo"


class LocalNoEncontrado(NoEncontrado):
    codigo = "local_no_encontrado"


class LocalSuspendido(AccesoDenegado):
    codigo = "local_suspendido"


class ImagenNoEncontrada(NoEncontrado):
    codigo = "imagen_no_encontrada"
