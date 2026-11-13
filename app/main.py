"""API REST sécurisée — documentation interactive Swagger sur /docs.

Lancement : uvicorn app.main:app --reload
En-tête requis : X-API-Key (voir IRIS_API_KEYS)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy import select

from .audit import log_event, verify_chain
from .config import Settings
from .crypto_service import KeyStore, load_master_key
from .database import make_engine, make_session_factory
from .models import AuditLog
from .security import ApiKeyRegistry, Principal
from .service import IrisService, ServiceError

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        master = load_master_key(settings.master_key_b64, settings.keystore_path.with_name("master.key"))
        ks = KeyStore(settings.keystore_path, master)
        eng = make_engine(settings.database_url)
        app.state.Session = make_session_factory(eng)
        app.state.service = IrisService(settings, ks)
        app.state.keys = ApiKeyRegistry(settings.api_keys)
        app.state.ks = ks
        yield
        eng.dispose()

    app = FastAPI(
        title="Iris Secure DB — API",
        version="1.0.0",
        description=("Prototype de base de données biométrique iris sécurisée : gabarits IrisCode "
                     "transformés (révocables) puis chiffrés AES-256-GCM (enveloppe DEK/KEK), RBAC, "
                     "journal d'audit chaîné HMAC. **Authentification : bouton Authorize, clé d'API.**"),
        lifespan=lifespan,
    )

    def db_dep(request: Request):
        db = request.app.state.Session()
        try:
            yield db
        finally:
            db.close()

    def principal(request: Request, key: str | None = Depends(api_key_header)) -> Principal:
        p = request.app.state.keys.authenticate(key)
        if not p:
            db = request.app.state.Session()
            try:
                log_event(db, request.app.state.ks.audit_key, actor="anonymous", role="none",
                          action=f"{request.method} {request.url.path}", outcome="unauthenticated",
                          details={"client": request.client.host if request.client else None})
                db.commit()
            finally:
                db.close()
            raise HTTPException(401, "clé d'API absente ou invalide")
        return p

    def require(perm: str):
        def dep(request: Request, p: Principal = Depends(principal), db=Depends(db_dep)) -> Principal:
            if not p.can(perm):
                log_event(db, request.app.state.ks.audit_key, actor=p.name, role=p.role,
                          action=f"{request.method} {request.url.path}", outcome="forbidden",
                          details={"missing_permission": perm})
                db.commit()
                raise HTTPException(403, f"rôle '{p.role}' non autorisé ({perm})")
            return p
        return dep

    @app.exception_handler(ServiceError)
    async def _svc_err(_, exc: ServiceError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.msg})

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/health", tags=["système"])
    def health():
        return {"status": "ok"}

    @app.post("/enroll", tags=["biométrie"], summary="Enrôler un sujet (image iris -> gabarit chiffré)")
    async def enroll(request: Request, external_ref: str = Form(..., min_length=1, max_length=128),
                     image: UploadFile = File(...), p: Principal = Depends(require("enroll")), db=Depends(db_dep)):
        return request.app.state.service.enroll(db, p, external_ref, await image.read())

    @app.post("/verify", tags=["biométrie"], summary="Vérification 1:1 (image sonde vs gabarit stocké)")
    async def verify(request: Request, external_ref: str = Form(...), image: UploadFile = File(...),
                     p: Principal = Depends(require("verify")), db=Depends(db_dep)):
        return request.app.state.service.verify(db, p, external_ref, await image.read()).__dict__

    @app.get("/subjects/{external_ref}", tags=["biométrie"], summary="Métadonnées (jamais le gabarit)")
    def subject(request: Request, external_ref: str, p: Principal = Depends(require("read_subject")),
                db=Depends(db_dep)):
        return request.app.state.service.subject_info(db, external_ref)

    @app.post("/subjects/{external_ref}/revoke", tags=["administration"], summary="Révoquer un gabarit compromis")
    def revoke(request: Request, external_ref: str, p: Principal = Depends(require("revoke")), db=Depends(db_dep)):
        return request.app.state.service.revoke(db, p, external_ref)

    @app.post("/subjects/{external_ref}/reenroll", tags=["administration"],
              summary="Ré-enrôler après révocation (nouvelle transformation)")
    async def reenroll(request: Request, external_ref: str, image: UploadFile = File(...),
                       p: Principal = Depends(require("revoke")), db=Depends(db_dep)):
        return request.app.state.service.reenroll(db, p, external_ref, await image.read())

    @app.delete("/subjects/{external_ref}", tags=["administration"], summary="Effacement définitif (RGPD art. 17)")
    def delete(request: Request, external_ref: str, p: Principal = Depends(require("delete")), db=Depends(db_dep)):
        return request.app.state.service.delete(db, p, external_ref)

    @app.post("/admin/rotate-keys", tags=["administration"], summary="Rotation de la KEK")
    def rotate(request: Request, p: Principal = Depends(require("rotate_keys")), db=Depends(db_dep)):
        return request.app.state.service.rotate_keys(db, p)

    @app.get("/admin/keys", tags=["administration"], summary="Liste des KEK (sans les valeurs)")
    def keys(request: Request, p: Principal = Depends(require("rotate_keys"))):
        return request.app.state.ks.list_keys()

    @app.get("/audit", tags=["audit"], summary="Journal d'audit (dernières entrées)")
    def audit(request: Request, limit: int = 50, p: Principal = Depends(require("read_audit")), db=Depends(db_dep)):
        rows = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))).scalars()
        return [{"id": r.id, "ts": r.ts, "actor": r.actor, "role": r.role, "action": r.action,
                 "subject_ref": r.subject_ref, "outcome": r.outcome, "details": r.details,
                 "hash": r.hash[:16] + "…"} for r in rows]

    @app.get("/audit/verify", tags=["audit"], summary="Contrôle d'intégrité de la chaîne d'audit")
    def audit_verify(request: Request, p: Principal = Depends(require("read_audit")), db=Depends(db_dep)):
        return verify_chain(db, request.app.state.ks.audit_key)

    return app


app = create_app()
