import importlib.util
import json
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from civicmesh.metrics import EscribirMetricas

RUTA_FRONTEND = Path(__file__).parents[1] / "scripts" / "frontend.py"


def _cargar_frontend() -> object:
    spec = importlib.util.spec_from_file_location(
        "civicmesh_frontend_script", RUTA_FRONTEND
    )
    if spec is None or spec.loader is None:
        raise AssertionError("no se pudo cargar scripts/frontend.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class FrontendServerTests(unittest.TestCase):
    def _servidor(self, directorio: Path) -> object:
        modulo = _cargar_frontend()
        handler = modulo._crear_handler(directorio, 2.0, 0.1)
        servidor = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        return servidor, hilo

    def test_api_resumen_describe_las_metricas(self) -> None:
        with TemporaryDirectory() as directorio:
            base = Path(directorio)
            escritor = EscribirMetricas("run-t", "127.0.0.1:7001", base)
            escritor.topic("aire", "santiago", "objetivo", 12.0, ts=1.0)
            escritor.topic("aire", "santiago", "subjetivo", 20.0, ts=1.5)
            escritor.estado(1, 0, 0, 1, ts=1.0)

            servidor, hilo = self._servidor(base)
            try:
                puerto = servidor.server_address[1]
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{puerto}/api/resumen",
                    timeout=5,
                ) as respuesta:
                    self.assertEqual(respuesta.status, 200)
                    datos = json.loads(respuesta.read().decode("utf-8"))

                self.assertEqual(datos["total_registros"], 3)
                santiago = datos["topicos"]["santiago"]
                self.assertEqual(
                    santiago["objetivo"]["ultimo_por_peer"], {"127.0.0.1:7001": 12.0}
                )
                self.assertTrue(santiago["objetivo"]["convergencia"]["convergido"])
                self.assertEqual(datos["vista"]["127.0.0.1:7001"]["vivos"], 1)
            finally:
                servidor.shutdown()
                servidor.server_close()
                hilo.join(timeout=2.0)

    def test_pagina_html_se_serve(self) -> None:
        with TemporaryDirectory() as directorio:
            base = Path(directorio)
            EscribirMetricas("run-t", "127.0.0.1:7001", base).red(1, 0, 0, ts=1.0)

            servidor, hilo = self._servidor(base)
            try:
                puerto = servidor.server_address[1]
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{puerto}/",
                    timeout=5,
                ) as respuesta:
                    self.assertEqual(respuesta.status, 200)
                    html = respuesta.read().decode("utf-8")
                self.assertIn("CivicMesh", html)
                self.assertIn("api/resumen", html)
            finally:
                servidor.shutdown()
                servidor.server_close()
                hilo.join(timeout=2.0)


if __name__ == "__main__":
    unittest.main()
