"""Authentification par clé d'API et contrôle d'accès par rôles (RBAC).
Les clés ne sont conservées qu'en empreinte SHA-256 ; comparaison à temps constant.

  operator : enrôler, vérifier
  auditor  : lire le journal d'audit, vérifier son intégrité
  admin    : tout + rotation des clés, révocation, suppression (droit à l'effacement)
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

PERMISSIONS = {
    "operator": {"enroll", "verify", "read_subject"},
    "auditor": {"read_audit", "read_subject"},
    "admin": {"enroll", "verify", "read_subject", "read_audit", "rotate_keys", "revoke", "delete"},
}


@dataclass
class Principal:
    name: str
    role: str

    def can(self, perm: str) -> bool:
        return perm in PERMISSIONS.get(self.role, set())


class ApiKeyRegistry:
    def __init__(self, spec: str):
        self._keys: list[tuple[bytes, Principal]] = []
        for i, item in enumerate(filter(None, (x.strip() for x in spec.split(",")))):
            key, role = item.rsplit(":", 1)
            if role not in PERMISSIONS:
                raise ValueError(f"rôle inconnu : {role}")
            self._keys.append((hashlib.sha256(key.encode()).digest(), Principal(f"{role}-{i + 1}", role)))

    def authenticate(self, presented: str | None) -> Principal | None:
        if not presented:
            return None
        h = hashlib.sha256(presented.encode()).digest()
        found = None
        for stored, p in self._keys:  # pas de sortie anticipée : temps constant vis-à-vis de la position
            if hmac.compare_digest(stored, h):
                found = p
        return found
