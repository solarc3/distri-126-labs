import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from civicmesh.domains.coords import CoordenadasError, coordenadas_de

BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "air_quality"
ANCLAS_POR_DEFECTO = [
    "santiago",
    "las_condes",
    "maipu",
    "la_florida",
    "penalolen",
    "pudahuel",
]


def descargar_comuna(
    comuna: str,
    start_date: str,
    end_date: str,
    variables: str,
    timeout: float,
) -> dict[str, Any]:
    lat, lon = coordenadas_de(comuna)
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": variables,
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "America/Santiago",
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=timeout) as respuesta:
        cuerpo = respuesta.read()
    data = json.loads(cuerpo)

    if "hourly" not in data or "time" not in data.get("hourly", {}):
        raise ValueError(
            f"respuesta de Open-Meteo sin 'hourly.time' para {comuna}: {data}"
        )

    return {
        "comuna": comuna,
        "fuente": "open-meteo",
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "generated_at": datetime.now(UTC).isoformat(),
        "hourly": data["hourly"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comunas", nargs="+", default=ANCLAS_POR_DEFECTO)
    parser.add_argument("--start-date", default="2025-06-01")
    parser.add_argument("--end-date", default="2025-06-03")
    parser.add_argument("--variables", default="pm2_5,pm10")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="pausa entre requests sucesivos, en segundos (cortesia con la API)",
    )
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    fallidas: list[str] = []
    for indice, comuna in enumerate(args.comunas):
        if indice:
            time.sleep(args.sleep)
        try:
            payload = descargar_comuna(
                comuna, args.start_date, args.end_date, args.variables, args.timeout
            )
        except CoordenadasError as error:
            print(
                f"[fetch] {comuna}: sin coordenadas registradas: {error}",
                file=sys.stderr,
            )
            fallidas.append(comuna)
            continue
        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            print(f"[fetch] {comuna}: fallo la descarga: {error}", file=sys.stderr)
            fallidas.append(comuna)
            continue

        destino = args.out_dir / f"{comuna}.json"
        destino.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        cantidad = len(payload["hourly"]["time"])
        print(f"[fetch] {comuna}: {cantidad} muestras -> {destino}")

    if fallidas:
        print(f"[fetch] fallaron {len(fallidas)} comunas: {fallidas}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
