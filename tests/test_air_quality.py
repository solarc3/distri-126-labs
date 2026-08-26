import unittest
from pathlib import Path

from civicmesh.domains.air_quality_cache import (
    SerieAireError,
    cargar_serie,
    cargar_series_directorio,
)
from civicmesh.domains.coords import (
    CoordenadasError,
    coordenadas_de,
    distancia_haversine_km,
)
from civicmesh.domains.extrapolacion import (
    ExtrapolacionError,
    ProveedorAire,
    idw,
    promedio_vecinos,
    vecino_mas_cercano,
)
from civicmesh.domains.replay import ReplayAgotadoError, ReplayAire

FIXTURES = Path(__file__).parent / "fixtures" / "air_quality"


class CoordsTests(unittest.TestCase):
    def test_coordenadas_normalizan_el_topico(self) -> None:
        self.assertEqual(coordenadas_de("Santiago"), coordenadas_de("santiago"))

    def test_coordenadas_de_comuna_desconocida_falla(self) -> None:
        with self.assertRaises(CoordenadasError):
            coordenadas_de("comuna-inexistente")

    def test_distancia_haversine_es_cero_para_el_mismo_punto(self) -> None:
        punto = coordenadas_de("santiago")
        self.assertAlmostEqual(distancia_haversine_km(punto, punto), 0.0)

    def test_distancia_haversine_es_simetrica_y_positiva(self) -> None:
        a, b = coordenadas_de("santiago"), coordenadas_de("las_condes")
        self.assertGreater(distancia_haversine_km(a, b), 0.0)
        self.assertAlmostEqual(
            distancia_haversine_km(a, b),
            distancia_haversine_km(b, a),
        )


class CargarSerieTests(unittest.TestCase):
    def test_cargar_serie_rellena_huecos_hacia_adelante(self) -> None:
        serie = cargar_serie(FIXTURES / "santiago.json")

        self.assertEqual(serie.comuna, "santiago")
        self.assertEqual(len(serie), 4)
        self.assertEqual(
            [serie.valor(i, "pm2_5") for i in range(4)],
            [80.0, 80.0, 40.0, 20.0],
        )
        self.assertEqual(
            [serie.valor(i, "pm10") for i in range(4)],
            [90.0, 70.0, 70.0, 70.0],
        )

    def test_cargar_serie_rechaza_archivo_sin_comuna(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directorio:
            path = Path(directorio) / "malo.json"
            path.write_text(json.dumps({"fuente": "x", "hourly": {"time": []}}))
            with self.assertRaises(SerieAireError):
                cargar_serie(path)

    def test_cargar_serie_rechaza_variable_toda_nula(self) -> None:
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as directorio:
            path = Path(directorio) / "malo.json"
            path.write_text(
                json.dumps(
                    {
                        "comuna": "santiago",
                        "fuente": "open-meteo",
                        "latitude": -33.4,
                        "longitude": -70.6,
                        "hourly": {
                            "time": ["2025-06-01T00:00"],
                            "pm2_5": [None],
                        },
                    }
                )
            )
            with self.assertRaises(SerieAireError):
                cargar_serie(path)

    def test_cargar_series_directorio_indexa_por_comuna(self) -> None:
        series = cargar_series_directorio(FIXTURES)
        self.assertEqual(set(series), {"santiago", "las_condes"})


class ExtrapolacionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.series = cargar_series_directorio(FIXTURES)

    def test_vecino_mas_cercano_usa_la_estacion_mas_proxima(self) -> None:
        # providencia es vecina de santiago y de las_condes en el grafo, pero
        # geograficamente esta mucho mas cerca de santiago
        valor = vecino_mas_cercano("providencia", 0, self.series)
        self.assertEqual(valor, self.series["santiago"].valor(0, "pm2_5"))

    def test_promedio_vecinos_promedia_comunas_adyacentes_con_serie(self) -> None:
        # nuñoa solo es adyacente a santiago entre las comunas con serie propia
        valor = promedio_vecinos("nunoa", 0, self.series)
        self.assertEqual(valor, self.series["santiago"].valor(0, "pm2_5"))

    def test_promedio_vecinos_sin_vecinos_disponibles_falla(self) -> None:
        with self.assertRaises(ExtrapolacionError):
            promedio_vecinos("maipu", 0, self.series)

    def test_idw_es_un_promedio_ponderado_entre_ambas_series(self) -> None:
        valor = idw("providencia", 0, self.series, potencia=2.0)
        pm25_santiago = self.series["santiago"].valor(0, "pm2_5")
        pm25_las_condes = self.series["las_condes"].valor(0, "pm2_5")
        self.assertTrue(
            min(pm25_santiago, pm25_las_condes)
            < valor
            < max(pm25_santiago, pm25_las_condes)
        )

    def test_idw_en_la_misma_coordenada_devuelve_el_valor_exacto(self) -> None:
        valor = idw("santiago", 0, self.series)
        self.assertEqual(valor, self.series["santiago"].valor(0, "pm2_5"))


class ProveedorAireTests(unittest.TestCase):
    def setUp(self) -> None:
        self.series = cargar_series_directorio(FIXTURES)

    def test_comuna_con_serie_propia_no_se_extrapola(self) -> None:
        proveedor = ProveedorAire(self.series, "idw")
        muestra = proveedor.muestra("santiago", 0)
        self.assertEqual(muestra["fuente"], "propia:open-meteo")
        self.assertEqual(muestra["pm2_5"], 80.0)

    def test_comuna_sin_serie_propia_se_extrapola_y_se_marca(self) -> None:
        proveedor = ProveedorAire(self.series, "promedio_vecinos")
        muestra = proveedor.muestra("nunoa", 0)
        self.assertEqual(muestra["fuente"], "heredado:promedio_vecinos")
        self.assertIsNotNone(muestra["pm2_5"])

    def test_longitud_es_el_minimo_entre_las_series(self) -> None:
        proveedor = ProveedorAire(self.series, "idw")
        self.assertEqual(proveedor.longitud(), 4)

    def test_metodo_desconocido_falla_al_construir(self) -> None:
        with self.assertRaises(ExtrapolacionError):
            ProveedorAire(self.series, "metodo-inventado")

    def test_comuna_inexistente_falla_con_extrapolacion_error_no_coordenadas_error(
        self,
    ) -> None:
        # comuna fuera del grafo (typo, etc): coordenadas_de() lanza CoordenadasError,
        # que _extrapolar_o_none debe atrapar igual que ExtrapolacionError, para que
        # el llamador solo tenga que manejar un tipo de error.
        proveedor = ProveedorAire(self.series, "idw")
        with self.assertRaises(ExtrapolacionError):
            proveedor.muestra("comuna-inventada", 0)


class ReplayAireTests(unittest.TestCase):
    def test_replay_avanza_indice_y_repite_si_loop(self) -> None:
        series = cargar_series_directorio(FIXTURES)
        proveedor = ProveedorAire(series, "idw")
        replay = ReplayAire("santiago", proveedor, loop=True)

        valores = [replay.step()["pm2_5"] for _ in range(4)]
        self.assertEqual(valores, [80.0, 80.0, 40.0, 20.0])

        # con loop=True, el quinto paso vuelve al principio de la serie
        self.assertEqual(replay.step()["pm2_5"], 80.0)

    def test_replay_sin_loop_se_agota(self) -> None:
        series = cargar_series_directorio(FIXTURES)
        proveedor = ProveedorAire(series, "idw")
        replay = ReplayAire("santiago", proveedor, loop=False)

        for _ in range(4):
            replay.step()

        with self.assertRaises(ReplayAgotadoError):
            replay.step()


if __name__ == "__main__":
    unittest.main()
