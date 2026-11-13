"""Configuration (variables d'environnement). En production : secrets dans un
KMS/HSM (AWS KMS, HashiCorp Vault…), jamais dans le code ni dans la base."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("IRIS_DB_URL", "sqlite:///./data/iris_secure.db"))
    keystore_path: Path = field(default_factory=lambda: Path(os.getenv("IRIS_KEYSTORE", "./data/keystore.json")))
    # Clé maîtresse (KEK racine) protégeant le keystore, base64 32 octets.
    master_key_b64: str | None = field(default_factory=lambda: os.getenv("IRIS_MASTER_KEY"))
    # Clés d'API -> rôle. Format : "cle1:admin,cle2:operator,cle3:auditor"
    api_keys: str = field(default_factory=lambda: os.getenv(
        "IRIS_API_KEYS", "admin-demo-key:admin,operator-demo-key:operator,auditor-demo-key:auditor"))
    match_threshold: float = float(os.getenv("IRIS_MATCH_THRESHOLD", "0.34"))
    max_failed_attempts: int = int(os.getenv("IRIS_MAX_FAILED", "5"))
    lockout_minutes: int = int(os.getenv("IRIS_LOCKOUT_MIN", "15"))
    max_upload_bytes: int = 5 * 1024 * 1024
