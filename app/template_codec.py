"""Sérialisation binaire des gabarits et transformation révocable (cancelable).

Format v1 (avant chiffrement) :
  magic 'IRT1' | rows u16 | cols u16 | bits u8 | packbits(code) | packbits(mask)

Transformation révocable (biométrie annulable) : permutation pseudo-aléatoire P
des positions de bits + XOR avec une chaîne K, toutes deux dérivées par HMAC d'un
secret et de (sujet, version). Propriété : HD(T(a), T(b)) = HD(a, b) — la
comparaison se fait dans le domaine transformé, l'IrisCode brut n'est jamais
stocké, et un gabarit compromis est révoqué en incrémentant la version.
Limite (à dire !) : si le secret de transformation fuit AVEC la base, la
transformation est inversible ; elle complète le chiffrement, sans le remplacer.
"""
from __future__ import annotations

import hashlib
import hmac
import struct

import numpy as np

from .iris_engine import IrisTemplate

MAGIC = b"IRT1"


def serialize(t: IrisTemplate) -> bytes:
    r, c, b = t.code.shape
    return (MAGIC + struct.pack(">HHB", r, c, b)
            + np.packbits(t.code.ravel()).tobytes() + np.packbits(t.mask.ravel()).tobytes())


def deserialize(blob: bytes) -> IrisTemplate:
    if blob[:4] != MAGIC:
        raise ValueError("format de gabarit inconnu")
    r, c, b = struct.unpack(">HHB", blob[4:9])
    n = r * c * b
    nb = (n + 7) // 8
    body = np.frombuffer(blob[9:], dtype=np.uint8)
    if body.size != 2 * nb:
        raise ValueError("gabarit tronqué")
    code = np.unpackbits(body[:nb])[:n].astype(bool).reshape(r, c, b)
    mask = np.unpackbits(body[nb:])[:n].astype(bool).reshape(r, c, b)
    return IrisTemplate(code=code, mask=mask)


def _prng(secret: bytes, subject_id: str, version: int) -> np.random.Generator:
    seed = hmac.new(secret, f"cancelable|{subject_id}|{version}".encode(), hashlib.sha256).digest()
    return np.random.default_rng(int.from_bytes(seed, "big"))


def cancelable_transform(t: IrisTemplate, secret: bytes, subject_id: str, version: int) -> IrisTemplate:
    rng = _prng(secret, subject_id, version)
    n = t.code.size
    perm = rng.permutation(n)
    key = rng.integers(0, 2, n).astype(bool)
    code = (t.code.ravel()[perm] ^ key).reshape(t.code.shape)
    mask = t.mask.ravel()[perm].reshape(t.mask.shape)
    return IrisTemplate(code=code, mask=mask)
