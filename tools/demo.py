"""Scénario de démonstration en 10 étapes.
  python -m tools.demo                      # en mémoire (TestClient), base temporaire
  python -m tools.demo --url http://127.0.0.1:8000   # contre un serveur uvicorn lancé
Génère aussi data/demo/*.png pour les tests manuels dans Swagger (/docs)."""
from __future__ import annotations

import argparse
import io
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.synth_iris import capture  # noqa: E402

ADMIN, OP, AUD = ({"X-API-Key": k} for k in ("admin-demo-key", "operator-demo-key", "auditor-demo-key"))


def png(s, k):
    b = io.BytesIO(); Image.fromarray(capture(s, k)).save(b, format="PNG"); return b.getvalue()


def step(n, title):
    print(f"\n\033[1m[{n:02d}] {title}\033[0m")


def show(r):
    try:
        body = r.json()
    except Exception:
        body = r.text
    print(f"     HTTP {r.status_code} -> {json.dumps(body, ensure_ascii=False)[:300]}")
    return r


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--url"); a = ap.parse_args()
    demo_dir = ROOT / "data" / "demo"; demo_dir.mkdir(parents=True, exist_ok=True)
    for name, (s, k) in {"alice_enrolement": (1, 0), "alice_verification": (1, 2),
                         "bob_enrolement": (2, 0), "imposteur": (7, 1)}.items():
        (demo_dir / f"{name}.png").write_bytes(png(s, k))

    tmp = tempfile.TemporaryDirectory()
    db_path = None
    if a.url:
        import httpx
        c = httpx.Client(base_url=a.url, timeout=30)
    else:
        from fastapi.testclient import TestClient
        from app.config import Settings
        from app.main import create_app
        st = Settings(); st.database_url = f"sqlite:///{tmp.name}/demo.db"; st.keystore_path = Path(tmp.name) / "ks.json"
        db_path = f"{tmp.name}/demo.db"
        c = TestClient(create_app(st)); c.__enter__()

    f = lambda s, k: {"image": ("eye.png", png(s, k), "image/png")}
    step(1, "Enrôlement d'Alice (opérateur) — l'image est transformée en IrisCode, puis chiffrée")
    show(c.post("/enroll", data={"external_ref": "ALICE"}, files=f(1, 0), headers=OP))
    show(c.post("/enroll", data={"external_ref": "BOB"}, files=f(2, 0), headers=OP))
    step(2, "Consultation des métadonnées : seul le chiffré existe (taille, algorithme, KEK)")
    show(c.get("/subjects/ALICE", headers=OP))
    if db_path:
        con = sqlite3.connect(db_path)
        ct = con.execute("select ciphertext from templates limit 1").fetchone()[0]
        print(f"     Contenu brut en base (32 premiers octets) : {ct[:32].hex()} … (illisible)")
    step(3, "Vérification authentique : Alice, autre capture (rotation/éclairage différents)")
    show(c.post("/verify", data={"external_ref": "ALICE"}, files=f(1, 2), headers=OP))
    step(4, "Tentative d'imposteur : un autre œil se présente comme Alice")
    show(c.post("/verify", data={"external_ref": "ALICE"}, files=f(7, 1), headers=OP))
    step(5, "Accès sans clé d'API, puis opérateur tentant de lire l'audit (RBAC)")
    show(c.get("/audit")); show(c.get("/audit", headers=OP))
    step(6, "Rotation de la clé de chiffrement (KEK) par l'administrateur")
    show(c.post("/admin/rotate-keys", headers=ADMIN))
    show(c.post("/verify", data={"external_ref": "ALICE"}, files=f(1, 1), headers=OP))
    if db_path:
        step(7, "ATTAQUE : un attaquant ayant accès à la base remplace le gabarit d'Alice par celui de Bob")
        con = sqlite3.connect(db_path)
        b = con.execute("select t.ciphertext,t.nonce,t.wrapped_dek,t.dek_nonce,t.kek_id from templates t join subjects s "
                        "on s.id=t.subject_id where s.external_ref='BOB'").fetchone()
        saved = con.execute("select t.ciphertext,t.nonce,t.wrapped_dek,t.dek_nonce,t.kek_id,t.id from templates t join subjects s "
                            "on s.id=t.subject_id where s.external_ref='ALICE'").fetchone()
        con.execute("update templates set ciphertext=?,nonce=?,wrapped_dek=?,dek_nonce=?,kek_id=? where id=?", (*b, saved[5]))
        con.commit()
        show(c.post("/verify", data={"external_ref": "ALICE"}, files=f(2, 1), headers=OP))
        con.execute("update templates set ciphertext=?,nonce=?,wrapped_dek=?,dek_nonce=?,kek_id=? where id=?", saved)
        con.commit(); print("     (gabarit d'origine restauré depuis la sauvegarde)")
    else:
        step(7, "(attaque par substitution : uniquement en mode local, voir tests/test_api.py)")
    step(8, "Révocation (gabarit supposé compromis) puis ré-enrôlement avec nouvelle transformation")
    show(c.post("/subjects/ALICE/revoke", headers=ADMIN))
    show(c.post("/verify", data={"external_ref": "ALICE"}, files=f(1, 2), headers=OP))
    show(c.post("/subjects/ALICE/reenroll", files=f(1, 3), headers=ADMIN))
    show(c.post("/verify", data={"external_ref": "ALICE"}, files=f(1, 2), headers=OP))
    step(9, "Effacement définitif de Bob (droit à l'effacement)")
    show(c.delete("/subjects/BOB", headers=ADMIN))
    step(10, "Audit : journal et contrôle d'intégrité de la chaîne HMAC")
    for e in reversed(c.get("/audit?limit=30", headers=AUD).json()):
        print(f"     #{e['id']:>2} {e['actor']:<11} {e['action']:<22} {e['outcome']:<16} {e['subject_ref'] or ''}")
    show(c.get("/audit/verify", headers=AUD))
    if db_path:
        con.execute("update audit_logs set outcome='match' where outcome='no_match'"); con.commit()
        print("     -> un attaquant falsifie le journal (échec transformé en succès)…")
        show(c.get("/audit/verify", headers=AUD))
    print(f"\nImages de démonstration pour Swagger : {demo_dir}")


if __name__ == "__main__":
    main()
