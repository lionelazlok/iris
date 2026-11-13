"""Journal d'audit infalsifiable par chaînage HMAC-SHA256.
Toute modification, suppression ou insertion d'une ligne casse la chaîne et est
détectée par verify_chain(). Le journal ne contient jamais de donnée biométrique."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog

GENESIS = "0" * 64


def _digest(key: bytes, prev: str, e: dict) -> str:
    payload = json.dumps(e, sort_keys=True, ensure_ascii=False).encode()
    return hmac.new(key, prev.encode() + payload, hashlib.sha256).hexdigest()


def _content(row: AuditLog) -> dict:
    return {"id": row.id, "ts": row.ts, "actor": row.actor, "role": row.role, "action": row.action,
            "subject_ref": row.subject_ref, "outcome": row.outcome, "details": row.details}


def log_event(db: Session, key: bytes, *, actor: str, role: str, action: str, outcome: str,
              subject_ref: str | None = None, details: dict | None = None) -> AuditLog:
    last = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none()
    prev = last.hash if last else GENESIS
    row = AuditLog(id=(last.id + 1) if last else 1, ts=datetime.now(timezone.utc).isoformat(), actor=actor,
                   role=role, action=action, subject_ref=subject_ref, outcome=outcome,
                   details=json.dumps(details or {}, ensure_ascii=False), prev_hash=prev, hash="")
    row.hash = _digest(key, prev, _content(row))
    db.add(row)
    db.flush()
    return row


def verify_chain(db: Session, key: bytes) -> dict:
    prev, n = GENESIS, 0
    expected_id = 1
    for row in db.execute(select(AuditLog).order_by(AuditLog.id)).scalars():
        if row.id != expected_id:
            return {"valid": False, "checked": n, "broken_at": row.id, "reason": "entrée manquante (trou dans la séquence)"}
        if row.prev_hash != prev or not hmac.compare_digest(row.hash, _digest(key, prev, _content(row))):
            return {"valid": False, "checked": n, "broken_at": row.id, "reason": "entrée modifiée ou chaîne rompue"}
        prev, n, expected_id = row.hash, n + 1, expected_id + 1
    return {"valid": True, "checked": n, "broken_at": None, "reason": None}
