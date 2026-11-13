import pytest

from minutas.cli.__main__ import correr
from minutas.locales.dominio.estado_del_local import Activo, Suspendido
from minutas.locales.dominio.modalidad import Modalidad
from minutas.locales.dominio.slug import Slug
from minutas.locales.dominio.zona_horaria import ZonaHoraria
from soporte.servicios_en_memoria import ServiciosEnMemoria


async def dar_de_alta(memoria: ServiciosEnMemoria) -> None:
    alta = ["alta-local", "--slug", "la-esquina", "--nombre", "La Esquina"]
    assert await correr([*alta, "--whatsapp", "0351 15 512-3456"], memoria.servicios) == 0


async def test_alta_local_lo_crea_con_ambas_modalidades_y_el_whatsapp_normalizado(
    memoria: ServiciosEnMemoria, capsys: pytest.CaptureFixture[str]
) -> None:
    await dar_de_alta(memoria)

    (local,) = memoria.locales.locales.values()
    assert local.slug == Slug("la-esquina")
    assert local.datos.whatsapp.numero == "5493515123456"
    assert local.datos.modalidades == {Modalidad.DELIVERY, Modalidad.RETIRO}
    assert "Local 'la-esquina' dado de alta" in capsys.readouterr().out


async def test_alta_local_con_slug_invalido_sale_con_1(
    memoria: ServiciosEnMemoria, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["alta-local", "--slug", "API", "--nombre", "X", "--whatsapp", "5493515123456"]

    assert await correr(argv, memoria.servicios) == 1
    assert "Error: 'API' no es un slug válido" in capsys.readouterr().err
    assert memoria.locales.locales == {}


async def test_alta_local_con_modalidad_desconocida_es_un_error_de_uso(
    memoria: ServiciosEnMemoria, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["alta-local", "--slug", "x-y", "--nombre", "X", "--whatsapp", "5493515123456"]

    with pytest.raises(SystemExit) as salida:
        await correr([*argv, "--modalidades", "delivery,mesa"], memoria.servicios)

    assert salida.value.code == 2
    assert "modalidades válidas: delivery, retiro" in capsys.readouterr().err


async def test_cambiar_slug_suspender_y_reactivar(memoria: ServiciosEnMemoria) -> None:
    await dar_de_alta(memoria)
    servicios = memoria.servicios

    assert (
        await correr(["cambiar-slug", "--slug", "la-esquina", "--nuevo", "esquina"], servicios) == 0
    )
    assert await correr(["suspender-local", "--slug", "esquina"], servicios) == 0
    (local,) = memoria.locales.locales.values()
    assert (local.slug, local.estado) == (Slug("esquina"), Suspendido())

    assert await correr(["reactivar-local", "--slug", "esquina"], servicios) == 0
    (local,) = memoria.locales.locales.values()
    assert local.estado == Activo()


async def test_cambiar_zona_horaria_informa_desde_que_jornada_rige(
    memoria: ServiciosEnMemoria, capsys: pytest.CaptureFixture[str]
) -> None:
    await dar_de_alta(memoria)
    argv = ["cambiar-zona-horaria", "--slug", "la-esquina", "--zona", "America/Santiago"]

    assert await correr(argv, memoria.servicios) == 0

    (local,) = memoria.locales.locales.values()
    assert local.jornada.reglas_destino.zona == ZonaHoraria("America/Santiago")
    # El reloj de prueba está en la jornada del viernes 6/11: rige desde el sábado.
    assert "desde la jornada del 2026-11-07" in capsys.readouterr().out


async def test_cambiar_zona_horaria_invalida_sale_con_1(memoria: ServiciosEnMemoria) -> None:
    await dar_de_alta(memoria)
    argv = ["cambiar-zona-horaria", "--slug", "la-esquina", "--zona", "Marte/Olympus"]

    assert await correr(argv, memoria.servicios) == 1


async def test_comando_sobre_un_slug_inexistente_sale_con_1(memoria: ServiciosEnMemoria) -> None:
    assert await correr(["suspender-local", "--slug", "no-existe"], memoria.servicios) == 1


async def test_comando_desconocido_termina_con_error_de_uso(memoria: ServiciosEnMemoria) -> None:
    with pytest.raises(SystemExit) as salida:
        await correr(["alta-admin"], memoria.servicios)

    assert salida.value.code == 2
