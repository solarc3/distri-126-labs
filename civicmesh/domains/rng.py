import math
import random
import zlib


def rng_compuesto(seed: int, *partes: str) -> random.Random:
    clave = ":".join(partes).encode("utf-8")
    seed_compuesta = (seed + zlib.crc32(clave)) % (2**32)
    return random.Random(seed_compuesta)


def poisson(rng: random.Random, lam: float) -> int:
    if lam < 0:
        raise ValueError("lam no puede ser negativo")
    if lam == 0:
        return 0

    limite = math.exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= limite:
            return k - 1
