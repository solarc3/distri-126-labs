import random
import unittest

from civicmesh.domains.percepcion import (
    AgregadorRumores,
    MemoriaEMA,
    PercepcionError,
    clip,
    ruido_gaussiano,
    sigmoide,
)


class MemoriaEMATests(unittest.TestCase):
    def test_condicion_inicial_es_cero(self) -> None:
        memoria = MemoriaEMA(alpha=0.8)
        self.assertEqual(memoria.valor, 0.0)

    def test_actualizar_aplica_la_formula_de_la_seccion_4_3(self) -> None:
        memoria = MemoriaEMA(alpha=0.8)
        primero = memoria.actualizar(10.0)
        self.assertAlmostEqual(primero, 0.8 * 0.0 + 0.2 * 10.0)

        segundo = memoria.actualizar(0.0)
        self.assertAlmostEqual(segundo, 0.8 * primero + 0.2 * 0.0)

    def test_alpha_fuera_de_rango_falla(self) -> None:
        with self.assertRaises(PercepcionError):
            MemoriaEMA(alpha=0.0)
        with self.assertRaises(PercepcionError):
            MemoriaEMA(alpha=1.0)


class AgregadorRumoresTests(unittest.TestCase):
    def test_resumen_vacio_es_cero(self) -> None:
        agregador = AgregadorRumores()
        self.assertEqual(agregador.resumen(), 0.0)

    def test_resumen_promedio(self) -> None:
        agregador = AgregadorRumores("promedio")
        for valor in (0.2, 0.4, 0.6):
            agregador.agregar(valor)
        self.assertAlmostEqual(agregador.resumen(), 0.4)

    def test_resumen_maximo(self) -> None:
        agregador = AgregadorRumores("maximo")
        for valor in (0.2, 0.9, 0.6):
            agregador.agregar(valor)
        self.assertEqual(agregador.resumen(), 0.9)

    def test_vaciar_limpia_el_buffer(self) -> None:
        agregador = AgregadorRumores()
        agregador.agregar(1.0)
        agregador.vaciar()
        self.assertEqual(len(agregador), 0)
        self.assertEqual(agregador.resumen(), 0.0)

    def test_resumen_desconocido_falla(self) -> None:
        with self.assertRaises(PercepcionError):
            AgregadorRumores("mediana")


class SigmoideClipTests(unittest.TestCase):
    def test_sigmoide_en_cero_es_un_medio(self) -> None:
        self.assertAlmostEqual(sigmoide(0.0), 0.5)

    def test_sigmoide_es_creciente_y_acotada(self) -> None:
        self.assertLess(sigmoide(-10.0), sigmoide(0.0))
        self.assertLess(sigmoide(0.0), sigmoide(10.0))
        self.assertGreaterEqual(sigmoide(-1000.0), 0.0)
        self.assertLessEqual(sigmoide(1000.0), 1.0)

    def test_clip_acota_al_rango(self) -> None:
        self.assertEqual(clip(-5.0, 0.0, 1.0), 0.0)
        self.assertEqual(clip(5.0, 0.0, 1.0), 1.0)
        self.assertEqual(clip(0.5, 0.0, 1.0), 0.5)

    def test_clip_rango_invertido_falla(self) -> None:
        with self.assertRaises(PercepcionError):
            clip(0.5, 1.0, 0.0)


class RuidoGaussianoTests(unittest.TestCase):
    def test_sigma_cero_no_agrega_ruido(self) -> None:
        self.assertEqual(ruido_gaussiano(random.Random(1), 0.0), 0.0)

    def test_sigma_negativo_falla(self) -> None:
        with self.assertRaises(PercepcionError):
            ruido_gaussiano(random.Random(1), -1.0)

    def test_misma_semilla_misma_secuencia(self) -> None:
        rng_a = random.Random(42)
        rng_b = random.Random(42)
        secuencia_a = [ruido_gaussiano(rng_a, 1.0) for _ in range(5)]
        secuencia_b = [ruido_gaussiano(rng_b, 1.0) for _ in range(5)]
        self.assertEqual(secuencia_a, secuencia_b)


if __name__ == "__main__":
    unittest.main()
