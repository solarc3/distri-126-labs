import json
import tempfile
import unittest
from pathlib import Path

from civicmesh.metrics import (
    EscribirMetricas,
    MetricaError,
    brecha_percepcion,
    convergencia,
    leer_metricas,
    saludar_peer_id,
    serie_topic,
    ultimo_valor,
)


class EscribirMetricasTests(unittest.TestCase):
    def test_vuelca_registros_y_los_relee(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio)
            escritor = EscribirMetricas("run-1", "127.0.0.1:7001", base)

            escritor.topic("delitos", "santiago", "objetivo", 4.0, ts=100.0)
            escritor.topic("delitos", "santiago", "subjetivo", 3.0, ts=101.0)
            escritor.estado(2, 1, 0, 3, ts=102.0)
            escritor.red(10, 7, 2, ts=103.0)

            metricas = list(leer_metricas(base))
            self.assertEqual(len(metricas), 4)
            self.assertEqual(metricas[0]["kind"], "topic")
            self.assertEqual(metricas[0]["topic"], "santiago")
            self.assertEqual(metricas[1]["channel"], "subjetivo")
            self.assertEqual(metricas[2]["vivos"], 2)
            self.assertEqual(metricas[3]["reenviados"], 7)

    def test_sanea_el_peer_id_para_el_nombre_de_archivo(self) -> None:
        self.assertEqual(saludar_peer_id("127.0.0.1:7001"), "127_0_0_1_7001")
        self.assertNotIn(":", saludar_peer_id("127.0.0.1:7001"))

    def test_niega_valores_nulos(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            archivo = Path(directorio) / "malo.jsonl"
            archivo.write_text(
                json.dumps(
                    {
                        "kind": "topic",
                        "run_id": "run-1",
                        "ts": 1.0,
                        "peer": "127.0.0.1:7001",
                        "domain": "delitos",
                        "topic": "santiago",
                        "channel": "objetivo",
                        "value": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(MetricaError):
                list(leer_metricas(archivo))

    def test_niega_campos_faltantes(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            archivo = Path(directorio) / "malo.jsonl"
            archivo.write_text(
                json.dumps(
                    {
                        "kind": "topic",
                        "run_id": "run-1",
                        "ts": 1.0,
                        "peer": "127.0.0.1:7001",
                        "domain": "delitos",
                        "topic": "santiago",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(MetricaError):
                list(leer_metricas(archivo))


class SerieTopicTests(unittest.TestCase):
    def test_filtra_por_topic_canal_y_ordena_por_ts(self) -> None:
        con_escritor: list = []
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio)
            escritor = EscribirMetricas("run-1", "127.0.0.1:7001", base)
            escritor.topic("delitos", "santiago", "objetivo", 5.0, ts=2.0)
            escritor.topic("delitos", "santiago", "objetivo", 3.0, ts=1.0)
            escritor.topic("delitos", "providencia", "objetivo", 9.0, ts=1.0)
            escritor.topic("delitos", "santiago", "subjetivo", 8.0, ts=1.0)
            con_escritor = list(leer_metricas(base))

        serie = serie_topic(con_escritor, "santiago", "objetivo")
        self.assertEqual([valor for _ts, _peer, valor in serie], [3.0, 5.0])
        self.assertEqual(
            [peer for _ts, peer, _valor in serie],
            ["127.0.0.1:7001", "127.0.0.1:7001"],
        )

    def test_filtra_por_peer(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio)
            a = EscribirMetricas("run-1", "127.0.0.1:7001", base)
            b = EscribirMetricas("run-1", "127.0.0.1:7002", base)
            a.topic("aire", "santiago", "objetivo", 10.0, ts=1.0)
            b.topic("aire", "santiago", "objetivo", 20.0, ts=1.0)
            metricas = list(leer_metricas(base))

        self.assertEqual(
            serie_topic(metricas, "santiago", "objetivo", peer="127.0.0.1:7002"),
            [(1.0, "127.0.0.1:7002", 20.0)],
        )


class BrechaPercepcionTests(unittest.TestCase):
    def test_usa_el_ultimo_objetivo_conocido(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio)
            escritor = EscribirMetricas("run-1", "127.0.0.1:7001", base)
            escritor.topic("delitos", "santiago", "objetivo", 10.0, ts=1.0)
            escritor.topic("delitos", "santiago", "subjetivo", 13.0, ts=2.0)
            escritor.topic("delitos", "santiago", "objetivo", 12.0, ts=3.0)
            escritor.topic("delitos", "santiago", "subjetivo", 15.0, ts=4.0)
            metricas = list(leer_metricas(base))

        brechas = brecha_percepcion(metricas, "santiago")
        self.assertEqual([round(gap, 6) for _t, _p, gap in brechas], [3.0, 3.0])
        self.assertEqual([t for t, _p, _v in brechas], [2.0, 4.0])

    def test_ignora_subjetivo_sin_objetivo_previo(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio)
            escritor = EscribirMetricas("run-1", "127.0.0.1:7001", base)
            escritor.topic("delitos", "santiago", "subjetivo", 100.0, ts=1.0)
            metricas = list(leer_metricas(base))

        self.assertEqual(brecha_percepcion(metricas, "santiago"), [])

    def test_deduplica_el_mismo_instante_y_peer(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio)
            escritor = EscribirMetricas("run-1", "127.0.0.1:7001", base)
            escritor.topic("delitos", "santiago", "objetivo", 10.0, ts=1.0)
            escritor.topic("delitos", "santiago", "subjetivo", 13.0, ts=2.0)
            escritor.topic("delitos", "santiago", "subjetivo", 16.0, ts=2.0)
            metricas = list(leer_metricas(base))

        self.assertEqual(
            brecha_percepcion(metricas, "santiago"),
            [(2.0, "127.0.0.1:7001", 6.0)],
        )


class ConvergenciaTests(unittest.TestCase):
    def test_detecta_convergencia_con_eps(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio)
            a = EscribirMetricas("run-1", "127.0.0.1:7001", base)
            b = EscribirMetricas("run-1", "127.0.0.1:7002", base)
            divergentes = [(0.5, 10.0, 20.0), (1.5, 11.0, 11.5)]
            for ts, valor_a, valor_b in divergentes:
                a.topic("aire", "santiago", "objetivo", valor_a, ts=ts)
                b.topic("aire", "santiago", "objetivo", valor_b, ts=ts)
            metricas = list(leer_metricas(base))

        resumen = convergencia(metricas, "santiago", "objetivo", eps=2.0, bucket=1.0)
        self.assertTrue(resumen.convergido)
        self.assertIsNotNone(resumen.ts_convergencia)
        self.assertEqual(resumen.serie[1][1], 0.5)
        self.assertEqual(resumen.serie[-1][1], 0.5)

    def test_rechaza_eps_negativo(self) -> None:
        with self.assertRaises(ValueError):
            convergencia([], "santiago", "objetivo", eps=-1, bucket=1.0)


class UltimoValorTests(unittest.TestCase):
    def test_devuelve_el_ultimo_valor_por_peer(self) -> None:
        with tempfile.TemporaryDirectory() as directorio:
            base = Path(directorio)
            a = EscribirMetricas("run-1", "127.0.0.1:7001", base)
            a.topic("aire", "santiago", "objetivo", 1.0, ts=1.0)
            a.topic("aire", "santiago", "objetivo", 2.0, ts=2.0)
            metricas = list(leer_metricas(base))

        self.assertEqual(
            ultimo_valor(metricas, "santiago", "objetivo"), {"127.0.0.1:7001": 2.0}
        )
        self.assertEqual(ultimo_valor(metricas, "santiago", "subjetivo"), {})


if __name__ == "__main__":
    unittest.main()
