"""Logique métier : enrôlement, vérification 1:1, révocation, rotation, effacement.
Le gabarit en clair n'existe qu'en mémoire, le temps du calcul."""
from __future__ import annotations

import io
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import log_event
from .config import Settings
from .crypto_service import CryptoService, EncryptedBlob, IntegrityError, KeyStore
from .iris_engine import MAX_SHIFT, IrisEngine, IrisTemplate, SegmentationError, hamming_distance, shifted
from .models import Subject, Template
from .security import Principal
from .template_codec import cancelable_transform, deserialize, serialize


class ServiceError(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status, self.msg = status, msg


@dataclass
class VerifyResult:
    match: bool
    hamming_distance: float | None
    threshold: float
    decision_ms: float
    reason: str | None = None


def load_image(data: bytes, max_bytes: int) -> np.ndarray:
    if len(data) > max_bytes:
        raise ServiceError(413, "image trop volumineuse")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data)).convert("L")
    except (UnidentifiedImageError, OSError) as e:
        raise ServiceError(400, "fichier image invalide") from e
    if img.width * img.height > 4_000_000:
        raise ServiceError(413, "résolution trop élevée")
    return np.asarray(img)


def _utc(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class IrisService:
    def __init__(self, settings: Settings, keystore: KeyStore, engine: IrisEngine | None = None):
        self.s = settings
        self.ks = keystore
        self.crypto = CryptoService(keystore)
        self.engine = engine or IrisEngine()

    def _audit(self, db, who: Principal, action, outcome, ref=None, **details):
        log_event(db, self.ks.audit_key, actor=who.name, role=who.role, action=action,
                  outcome=outcome, subject_ref=ref, details=details)

    def _extract(self, img) -> IrisTemplate:
        try:
            return self.engine.extract(img)
        except SegmentationError as e:
            raise ServiceError(422, f"image iris inexploitable : {e}") from e

    def _protect(self, subj: Subject, tpl: IrisTemplate) -> IrisTemplate:
        return cancelable_transform(tpl, self.ks.cancel_secret, subj.id, subj.cancel_version)

    # ---------- Enrôlement ----------
    def enroll(self, db: Session, who: Principal, external_ref: str, image: bytes) -> dict:
        if db.execute(select(Subject).where(Subject.external_ref == external_ref)).scalar_one_or_none():
            self._audit(db, who, "enroll", "rejected", external_ref, reason="déjà enrôlé")
            db.commit()
            raise ServiceError(409, "sujet déjà enrôlé")
        tpl = self._extract(load_image(image, self.s.max_upload_bytes))
        subj = Subject(external_ref=external_ref)
        db.add(subj)
        db.flush()
        rec = Template(subject_id=subj.id, quality=tpl.usable_ratio, ciphertext=b"", nonce=b"",
                       wrapped_dek=b"", dek_nonce=b"", kek_id="")
        db.add(rec)
        db.flush()
        blob = self.crypto.encrypt(serialize(self._protect(subj, tpl)), subj.id, rec.id)
        rec.ciphertext, rec.nonce, rec.wrapped_dek, rec.dek_nonce, rec.kek_id = (
            blob.ciphertext, blob.nonce, blob.wrapped_dek, blob.dek_nonce, blob.kek_id)
        self._audit(db, who, "enroll", "success", external_ref, template_id=rec.id, kek=blob.kek_id,
                    quality=round(tpl.usable_ratio, 3))
        db.commit()
        return {"subject_id": subj.id, "external_ref": external_ref, "template_id": rec.id,
                "kek_id": blob.kek_id, "quality": round(tpl.usable_ratio, 3), "algorithm": rec.algorithm,
                "cancelable_version": subj.cancel_version}

    def _get_subject(self, db, ref) -> Subject:
        subj = db.execute(select(Subject).where(Subject.external_ref == ref)).scalar_one_or_none()
        if not subj:
            raise ServiceError(404, "sujet inconnu")
        return subj

    # ---------- Vérification 1:1 ----------
    def verify(self, db: Session, who: Principal, external_ref: str, image: bytes) -> VerifyResult:
        t0 = time.perf_counter()
        subj = self._get_subject(db, external_ref)
        now = datetime.now(timezone.utc)
        if subj.status == "revoked":
            self._audit(db, who, "verify", "rejected", external_ref, reason="gabarit révoqué")
            db.commit()
            raise ServiceError(403, "gabarit révoqué : ré-enrôlement requis")
        if _utc(subj.locked_until) and _utc(subj.locked_until) > now:
            self._audit(db, who, "verify", "rejected", external_ref, reason="compte verrouillé")
            db.commit()
            raise ServiceError(423, "trop d'échecs : sujet temporairement verrouillé")
        probe = self._extract(load_image(image, self.s.max_upload_bytes))
        rec = subj.templates[-1]
        try:
            ref_tpl = deserialize(self.crypto.decrypt(EncryptedBlob(rec.ciphertext, rec.nonce, rec.wrapped_dek,
                                                                    rec.dek_nonce, rec.kek_id), subj.id, rec.id))
        except IntegrityError as e:
            self._audit(db, who, "verify", "integrity_alert", external_ref, template_id=rec.id, error=str(e))
            db.commit()
            raise ServiceError(409, "ALERTE INTÉGRITÉ : gabarit stocké altéré, vérification refusée") from e
        # Comparaison dans le domaine transformé (révocable), pour chaque décalage angulaire de la sonde
        hd = 1.0
        for sft in range(-MAX_SHIFT, MAX_SHIFT + 1):
            p = self._protect(subj, IrisTemplate(shifted(probe.code, sft), shifted(probe.mask, sft)))
            hd = min(hd, hamming_distance(ref_tpl.code, ref_tpl.mask, p.code, p.mask))
        ok = hd <= self.s.match_threshold
        if ok:
            subj.failed_attempts, subj.locked_until = 0, None
        else:
            subj.failed_attempts += 1
            if subj.failed_attempts >= self.s.max_failed_attempts:
                subj.locked_until = now + timedelta(minutes=self.s.lockout_minutes)
                subj.failed_attempts = 0
        ms = (time.perf_counter() - t0) * 1000
        self._audit(db, who, "verify", "match" if ok else "no_match", external_ref,
                    hd=round(hd, 4), threshold=self.s.match_threshold)
        db.commit()
        return VerifyResult(ok, round(hd, 4), self.s.match_threshold, round(ms, 1))

    # ---------- Révocation / effacement / rotation ----------
    def revoke(self, db, who, external_ref) -> dict:
        subj = self._get_subject(db, external_ref)
        subj.status = "revoked"
        subj.cancel_version += 1
        for t in list(subj.templates):
            db.delete(t)
        self._audit(db, who, "revoke", "success", external_ref, new_cancel_version=subj.cancel_version)
        db.commit()
        return {"external_ref": external_ref, "status": "revoked", "next_cancelable_version": subj.cancel_version}

    def reenroll(self, db, who, external_ref, image) -> dict:
        subj = self._get_subject(db, external_ref)
        if subj.status != "revoked":
            raise ServiceError(409, "ré-enrôlement réservé aux gabarits révoqués")
        tpl = self._extract(load_image(image, self.s.max_upload_bytes))
        rec = Template(subject_id=subj.id, quality=tpl.usable_ratio, ciphertext=b"", nonce=b"",
                       wrapped_dek=b"", dek_nonce=b"", kek_id="")
        db.add(rec)
        db.flush()
        blob = self.crypto.encrypt(serialize(self._protect(subj, tpl)), subj.id, rec.id)
        rec.ciphertext, rec.nonce, rec.wrapped_dek, rec.dek_nonce, rec.kek_id = (
            blob.ciphertext, blob.nonce, blob.wrapped_dek, blob.dek_nonce, blob.kek_id)
        subj.status, subj.failed_attempts, subj.locked_until = "active", 0, None
        self._audit(db, who, "reenroll", "success", external_ref, cancel_version=subj.cancel_version)
        db.commit()
        return {"external_ref": external_ref, "status": "active", "cancelable_version": subj.cancel_version}

    def delete(self, db, who, external_ref) -> dict:
        subj = self._get_subject(db, external_ref)
        db.delete(subj)
        self._audit(db, who, "delete", "success", external_ref, note="effacement RGPD art. 17")
        db.commit()
        return {"external_ref": external_ref, "deleted": True}

    def rotate_keys(self, db, who) -> dict:
        old = self.ks.active_id
        new = self.ks.rotate()
        n, errors = 0, []
        for rec in db.execute(select(Template)).scalars():
            try:
                b = self.crypto.rewrap(EncryptedBlob(rec.ciphertext, rec.nonce, rec.wrapped_dek, rec.dek_nonce,
                                                     rec.kek_id), rec.subject_id, rec.id)
            except IntegrityError:
                errors.append(rec.id)
                continue
            rec.ciphertext, rec.nonce, rec.wrapped_dek, rec.dek_nonce, rec.kek_id = (
                b.ciphertext, b.nonce, b.wrapped_dek, b.dek_nonce, b.kek_id)
            n += 1
        self._audit(db, who, "rotate_keys", "success" if not errors else "partial",
                    old_kek=old, new_kek=new, rewrapped=n, integrity_errors=errors)
        db.commit()
        return {"old_kek": old, "new_kek": new, "templates_rewrapped": n, "integrity_errors": errors}

    def subject_info(self, db, external_ref) -> dict:
        subj = self._get_subject(db, external_ref)
        return {"subject_id": subj.id, "external_ref": subj.external_ref, "status": subj.status,
                "cancelable_version": subj.cancel_version, "created_at": subj.created_at.isoformat(),
                "templates": [{"template_id": t.id, "algorithm": t.algorithm, "kek_id": t.kek_id,
                               "ciphertext_bytes": len(t.ciphertext), "quality": round(t.quality, 3)}
                              for t in subj.templates]}
