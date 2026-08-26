import tempfile
import unittest
from pathlib import Path
from typing import cast

from civicmesh.frontend import (
    canales_medidos,
    construir_resumen,
    topics_medidos,
)
from civicmesh.metrics import EscribirMetricas, leer_metricas


def _demo_metricas() -> list:
    with tempfile.TemporaryDirectory() as directorio:
        base = Path(directorio)
        a = EscribirMetricas("run-1", "127.0.0.1:7001", base)
        b = EscribirMetricas("run-1", "127.0.0.1:7002", base)
        for ts, objetivo_a, objetivo_b in ((1.0, 10.0, 30.0), (2.0, 20.0, 20.0)):
            a.topic("aire", "santiago", "objetivo", objetivo_a, ts=ts)
            b.topic("aire", "santiago", "objetivo", objetivo_b, ts=ts)
        for ts, subjetivo in ((1.5, 22.0), (2.5, 25.0)):
            a.topic("aire", "santiago", "subjetivo", subjetivo, ts=ts)
        a.estado(2, 0, 0, 2, ts=1.0)
        a.estado(1, 0, 1, 2, ts=3.0)
        return list(leer_metricas(base))


class TopicsMedidosTests(unittest.TestCase):
    def test_topics_y_canales_presentes(self) -> None:
        metricas = _demo_metricas()
        self.assertEqual(topics_medidos(metricas), {"santiago"})
        self.assertEqual(
            canales_medidos(metricas, "santiago"), {"objetivo", "subjetivo"}
        )


class ConstruirResumenTests(unittest.TestCase):
    def test_estructura_del_resumen(self) -> None:
        metricas = _demo_metricas()
        resumen = construir_resumen(metricas, eps=2.0, bucket=1.0)

        self.assertEqual(resumen["total_registros"], 8)
        topicos = cast(dict, resumen["topicos"])
        self.assertIn("santiago", topicos)
        santiago = cast(dict, topicos["santiago"])
        objetivo = cast(dict, santiago["objetivo"])

        self.assertEqual(
            objetivo["ultimo_por_peer"],
            {"127.0.0.1:7001": 20.0, "127.0.0.1:7002": 20.0},
        )
        converg = cast(dict, objetivo["convergencia"])
        self.assertTrue(converg["convergido"])

    def test_vista_toma_el_ultimo_estado_por_peer(self) -> None:
        metricas = _demo_metricas()
        resumen = construir_resumen(metricas)
        vista = cast(dict, resumen["vista"])
        self.assertEqual(vista["127.0.0.1:7001"]["muertos"], 1)


if __name__ == "__main__":
    unittest.main()
