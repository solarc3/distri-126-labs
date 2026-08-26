"""Valida que un perfil Compose levante una malla CivicMesh funcional."""

import argparse
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Sequence

ESTADO_GOSSIP = re.compile(r"vista=(\d+) vivos=(\d+)")


class ComposeCheckError(RuntimeError):
    """Indica que el stack no alcanzó el estado esperado."""


def _compose(
    profile: str,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "--profile", profile, *args],
        check=check,
        text=True,
        capture_output=True,
    )


def _parse_ps(output: str) -> dict[str, str]:
    """Acepta tanto el JSON por línea de Compose v2 como el arreglo de v5."""
    output = output.strip()
    if not output:
        return {}

    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        parsed = [json.loads(line) for line in output.splitlines() if line.strip()]
    if isinstance(parsed, dict):
        parsed = [parsed]

    return {
        str(container["Service"]): str(container["State"]).lower()
        for container in parsed
    }


def _frontend_disponible() -> bool:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8080/api/resumen", timeout=1.0
        ) as response:
            payload = json.load(response)
            return response.status == 200 and "total_registros" in payload
    except (OSError, ValueError, urllib.error.URLError):
        return False


def _descubrimiento_completo(profile: str, malla: set[str]) -> bool:
    peers_esperados = len(malla) - 1
    for servicio in malla:
        logs = _compose(profile, "logs", "--no-color", servicio).stdout
        if not any(
            int(vista) >= peers_esperados and int(vivos) >= 1
            for vista, vivos in ESTADO_GOSSIP.findall(logs)
        ):
            return False
    return True


def verificar(profile: str, timeout: float) -> None:
    publisher = f"publisher-{profile}"
    servicios = {"peer-1", "peer-2", "peer-3", publisher, "frontend"}
    malla = servicios - {"frontend"}
    limite = time.monotonic() + timeout
    ultimo_estado: dict[str, str] = {}

    while time.monotonic() < limite:
        ultimo_estado = _parse_ps(
            _compose(profile, "ps", "--all", "--format", "json").stdout
        )
        terminados = {
            servicio: estado
            for servicio, estado in ultimo_estado.items()
            if servicio in servicios and estado not in {"created", "running"}
        }
        if terminados:
            raise ComposeCheckError(f"servicios terminados: {terminados}")

        todos_arriba = all(
            ultimo_estado.get(servicio) == "running" for servicio in servicios
        )
        if (
            todos_arriba
            and _frontend_disponible()
            and _descubrimiento_completo(profile, malla)
        ):
            print(
                f"perfil {profile}: {len(servicios)} servicios arriba, "
                f"frontend disponible y {len(malla)} peers descubiertos"
            )
            return
        time.sleep(1.0)

    raise ComposeCheckError(
        f"el perfil {profile} no convergió en {timeout:.0f}s; "
        f"último estado: {ultimo_estado}"
    )


def main(args: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="levanta y valida un perfil Docker Compose de CivicMesh"
    )
    parser.add_argument("profile", choices=("delitos", "aire"))
    parser.add_argument("--timeout", type=float, default=30.0)
    parsed = parser.parse_args(args)

    if parsed.timeout <= 0:
        parser.error("--timeout debe ser positivo")

    try:
        result = _compose(parsed.profile, "up", "--build", "--detach")
        print(result.stdout, end="")
        verificar(parsed.profile, parsed.timeout)
    except ComposeCheckError as error:
        print(f"ERROR: {error}")
        ps = _compose(parsed.profile, "ps", "--all", check=False)
        logs = _compose(parsed.profile, "logs", "--no-color", check=False)
        print(ps.stdout, end="")
        print(logs.stdout, end="")
        return 1
    except subprocess.CalledProcessError as error:
        print(f"ERROR: {error}")
        print(error.stdout, end="")
        print(error.stderr, end="")
        ps = _compose(parsed.profile, "ps", "--all", check=False)
        logs = _compose(parsed.profile, "logs", "--no-color", check=False)
        print(ps.stdout, end="")
        print(logs.stdout, end="")
        return 1
    finally:
        _compose(
            parsed.profile,
            "down",
            "--volumes",
            "--remove-orphans",
            check=False,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
