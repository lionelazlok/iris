"""Service cryptographique : chiffrement d'enveloppe AES-256-GCM.

  - Chaque gabarit est chiffré par une DEK (Data Encryption Key) aléatoire de 256 bits.
  - La DEK est « enveloppée » (chiffrée) par une KEK versionnée (Key Encryption Key).
  - Les KEK sont dans un keystore lui-même chiffré par la clé maîtresse (IRIS_MASTER_KEY),
    qui, en production, réside dans un HSM/KMS.
  - AAD (données authentifiées associées) = sujet | id gabarit | version KEK :
    un chiffré copié vers un autre sujet ou une autre ligne est rejeté (tag GCM invalide).
  - Nonce de 96 bits aléatoire par opération (os.urandom) — jamais réutilisé avec la même clé.
  - Rotation : nouvelle KEK active ; chaque gabarit est déchiffré en mémoire puis
    rechiffré (DEK neuve, AAD liée à la nouvelle KEK) — sans ré-enrôlement des personnes.
"""
from __future__ import annotations

import base64
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_LEN = 12


class IntegrityError(Exception):
    """Échec d'authentification GCM : donnée altérée, mauvaise clé ou mauvais contexte."""


@dataclass
class EncryptedBlob:
    ciphertext: bytes
    nonce: bytes
    wrapped_dek: bytes
    dek_nonce: bytes
    kek_id: str


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _ub64(s: str) -> bytes:
    return base64.b64decode(s)


class KeyStore:
    """Keystore fichier (démonstration). Contenu chiffré AES-GCM par la clé maîtresse."""

    def __init__(self, path: Path, master_key: bytes):
        if len(master_key) != 32:
            raise ValueError("la clé maîtresse doit faire 32 octets (AES-256)")
        self.path = Path(path)
        self._master = AESGCM(master_key)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            data = {"active": None, "keys": {}, "cancel_secret": _b64(os.urandom(32))}
            self._data = data
            self._new_kek_locked()
            return self._data
        raw = json.loads(self.path.read_text())
        try:
            plain = self._master.decrypt(_ub64(raw["nonce"]), _ub64(raw["ct"]), b"iris-keystore-v1")
        except InvalidTag as e:
            raise IntegrityError("keystore illisible : clé maîtresse incorrecte ou fichier altéré") from e
        return json.loads(plain)

    def _save(self) -> None:
        nonce = os.urandom(NONCE_LEN)
        ct = self._master.encrypt(nonce, json.dumps(self._data).encode(), b"iris-keystore-v1")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"nonce": _b64(nonce), "ct": _b64(ct)}))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)

    def _new_kek_locked(self) -> str:
        n = len(self._data["keys"]) + 1
        kid = f"kek-v{n}"
        self._data["keys"][kid] = {"key": _b64(AESGCM.generate_key(256)),
                                   "created": datetime.now(timezone.utc).isoformat(), "status": "active"}
        if self._data["active"]:
            self._data["keys"][self._data["active"]]["status"] = "retired"
        self._data["active"] = kid
        self._save()
        return kid

    def rotate(self) -> str:
        with self._lock:
            return self._new_kek_locked()

    @property
    def active_id(self) -> str:
        return self._data["active"]

    def kek(self, kid: str) -> bytes:
        try:
            return _ub64(self._data["keys"][kid]["key"])
        except KeyError as e:
            raise IntegrityError(f"KEK inconnue : {kid}") from e

    def list_keys(self) -> list[dict]:
        return [{"kek_id": k, "created": v["created"], "status": v["status"]} for k, v in self._data["keys"].items()]

    @property
    def cancel_secret(self) -> bytes:
        return _ub64(self._data["cancel_secret"])

    @property
    def audit_key(self) -> bytes:
        # Clé HMAC du journal d'audit dérivée et distincte des clés de chiffrement
        import hashlib, hmac
        return hmac.new(self.cancel_secret, b"audit-chain-key", hashlib.sha256).digest()


def aad_for(subject_id: str, template_id: str, kek_id: str) -> bytes:
    return f"iris-template-v1|{subject_id}|{template_id}|{kek_id}".encode()


class CryptoService:
    def __init__(self, keystore: KeyStore):
        self.ks = keystore

    def encrypt(self, plaintext: bytes, subject_id: str, template_id: str) -> EncryptedBlob:
        kid = self.ks.active_id
        aad = aad_for(subject_id, template_id, kid)
        dek = AESGCM.generate_key(256)
        nonce = os.urandom(NONCE_LEN)
        ct = AESGCM(dek).encrypt(nonce, plaintext, aad)
        dek_nonce = os.urandom(NONCE_LEN)
        wrapped = AESGCM(self.ks.kek(kid)).encrypt(dek_nonce, dek, aad)
        return EncryptedBlob(ct, nonce, wrapped, dek_nonce, kid)

    def decrypt(self, blob: EncryptedBlob, subject_id: str, template_id: str) -> bytes:
        aad = aad_for(subject_id, template_id, blob.kek_id)
        try:
            dek = AESGCM(self.ks.kek(blob.kek_id)).decrypt(blob.dek_nonce, blob.wrapped_dek, aad)
            return AESGCM(dek).decrypt(blob.nonce, blob.ciphertext, aad)
        except InvalidTag as e:
            raise IntegrityError("gabarit altéré ou contexte invalide (tag GCM)") from e

    def rewrap(self, blob: EncryptedBlob, subject_id: str, template_id: str) -> EncryptedBlob:
        """Rotation : déchiffre en mémoire avec l'ancienne KEK, rechiffre sous la KEK active."""
        old_aad = aad_for(subject_id, template_id, blob.kek_id)
        try:
            dek = AESGCM(self.ks.kek(blob.kek_id)).decrypt(blob.dek_nonce, blob.wrapped_dek, old_aad)
            pt = AESGCM(dek).decrypt(blob.nonce, blob.ciphertext, old_aad)
        except InvalidTag as e:
            raise IntegrityError("gabarit altéré détecté pendant la rotation") from e
        # L'AAD contient l'id de KEK : on rechiffre le gabarit (DEK neuve) pour lier le nouveau contexte.
        return self.encrypt(pt, subject_id, template_id)


def load_master_key(b64: str | None, dev_path: Path) -> bytes:
    """Production : IRIS_MASTER_KEY obligatoire. Démo : clé générée dans un fichier 0600."""
    if b64:
        return base64.b64decode(b64)
    dev_path = Path(dev_path)
    if dev_path.exists():
        return base64.b64decode(dev_path.read_text().strip())
    key = AESGCM.generate_key(256)
    dev_path.parent.mkdir(parents=True, exist_ok=True)
    dev_path.write_text(_b64(key))
    os.chmod(dev_path, 0o600)
    return key
