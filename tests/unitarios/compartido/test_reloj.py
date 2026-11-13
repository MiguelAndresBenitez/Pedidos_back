from datetime import UTC, datetime, timedelta

from minutas.compartido.aplicacion.reloj import Reloj
from minutas.compartido.infraestructura.reloj_del_sistema import RelojDelSistema
from soporte.reloj_fijo import RelojFijo


def test_ahora_del_reloj_del_sistema_es_utc_y_actual() -> None:
    reloj: Reloj = RelojDelSistema()

    ahora = reloj.ahora()

    assert ahora.tzinfo is UTC
    assert abs(datetime.now(UTC) - ahora) < timedelta(seconds=5)


def test_reloj_fijo_avanza_solo_cuando_se_le_pide() -> None:
    instante = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
    reloj: Reloj = RelojFijo(instante)

    assert reloj.ahora() == instante
    assert isinstance(reloj, RelojFijo)
    reloj.avanzar(timedelta(hours=1))
    assert reloj.ahora() == instante + timedelta(hours=1)
