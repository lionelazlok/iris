"""Interface web Streamlit — démonstration interactive, déployable sur Streamlit Community Cloud.

Lancement local :  streamlit run streamlit_app.py
L'interface appelle directement la couche métier (app/service.py) : mêmes contrôles de
sécurité que l'API FastAPI (chiffrement, RBAC, audit), sans serveur séparé."""
from __future__ import annotations

import io
import json
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from sqlalchemy import select

from app.audit import verify_chain
from app.config import Settings
from app.crypto_service import KeyStore, load_master_key
from app.database import make_engine, make_session_factory
from app.models import AuditLog
from app.security import Principal
from app.service import IrisService, ServiceError
from tools.synth_iris import capture

st.set_page_config(page_title="Iris Secure DB", page_icon="👁️", layout="wide")

# Secrets : Streamlit Cloud (st.secrets) > variables d'environnement > clé de démonstration locale
try:
    for k in ("IRIS_MASTER_KEY",):
        if k in st.secrets and not os.getenv(k):
            os.environ[k] = st.secrets[k]
except Exception:
    pass


@st.cache_resource
def backend():
    s = Settings()
    s.database_url = os.getenv("IRIS_DB_URL", "sqlite:///./data/streamlit.db")
    s.keystore_path = Path(os.getenv("IRIS_KEYSTORE", "./data/streamlit_keystore.json"))
    master = load_master_key(s.master_key_b64, s.keystore_path.with_name("streamlit_master.key"))
    ks = KeyStore(s.keystore_path, master)
    eng = make_engine(s.database_url)
    return s, ks, make_session_factory(eng), IrisService(s, ks)


settings, ks, Session, svc = backend()
DB_FILE = settings.database_url.removeprefix("sqlite:///")

# ------------------------------------------------------------------ Barre latérale
st.sidebar.title("👁️ Iris Secure DB")
role = st.sidebar.radio("Se connecter en tant que", ["operator", "auditor", "admin"],
                        captions=["enrôler, vérifier", "lire et contrôler l'audit", "clés, révocation, effacement"])
who = Principal(f"{role}-streamlit", role)
st.sidebar.divider()
st.sidebar.caption("Source de l'image")
src = st.sidebar.radio("Image", ["Iris synthétique", "Téléverser un fichier"], label_visibility="collapsed")


def image_input(key: str, default_subject: int, default_session: int):
    if src == "Iris synthétique":
        c1, c2 = st.columns(2)
        subj = c1.number_input("Personne n°", 0, 999, default_subject, key=f"{key}_s")
        sess = c2.number_input("Photo n°", 0, 50, default_session, key=f"{key}_k",
                               help="Même personne, photo différente = autre angle, éclairage, dilatation…")
        arr = capture(int(subj), int(sess))
        buf = io.BytesIO(); Image.fromarray(arr).save(buf, format="PNG")
        return buf.getvalue(), arr
    f = st.file_uploader("Image de l'œil (PNG/JPG, niveaux de gris de préférence)", type=["png", "jpg", "jpeg", "bmp"], key=key)
    if not f:
        return None, None
    data = f.getvalue()
    return data, np.asarray(Image.open(io.BytesIO(data)).convert("L"))


def run(fn, *a):
    db = Session()
    try:
        if not who.can(fn.__perm__):
            st.error(f"⛔ Rôle « {role} » non autorisé ({fn.__perm__}).")
            return None
        return fn(db, who, *a)
    except ServiceError as e:
        (st.error if e.status >= 409 else st.warning)(f"HTTP {e.status} — {e.msg}")
    finally:
        db.close()


for name, perm in (("enroll", "enroll"), ("verify", "verify"), ("revoke", "revoke"), ("reenroll", "revoke"),
                   ("delete", "delete"), ("rotate_keys", "rotate_keys")):
    getattr(svc, name).__func__.__perm__ = perm


def subjects():
    with sqlite3.connect(DB_FILE) as con:
        return pd.read_sql("select external_ref as pseudonyme, status as statut, cancel_version as version, "
                           "failed_attempts as echecs, created_at as cree_le from subjects order by created_at", con)


# ------------------------------------------------------------------ Onglets
st.title("Sécurisation d'une base de données biométrique à iris")
tabs = st.tabs(["① Enrôlement", "② Vérification", "③ Base de données", "④ Administration", "⑤ Audit", "⑥ Attaques", "À propos"])

with tabs[0]:
    st.subheader("Enregistrer une personne")
    st.caption("L'image est transformée en IrisCode, brouillée (révocable) puis chiffrée en AES-256-GCM. "
               "Ni l'image ni le code lisible ne sont conservés.")
    c1, c2 = st.columns([1, 1])
    with c1:
        ref = st.text_input("Pseudonyme de la personne", "ALICE", key="enr_ref")
        data, arr = image_input("enr", 1, 0)
        go = st.button("Enrôler", type="primary", disabled=data is None)
    with c2:
        if arr is not None:
            st.image(arr, caption="Image fournie", width=320)
    if go:
        r = run(svc.enroll, ref, data)
        if r:
            st.success(f"✅ {ref} enrôlé — gabarit chiffré avec {r['kek_id']} (qualité {r['quality']:.0%})")
            st.json(r)

with tabs[1]:
    st.subheader("Vérifier une identité (1:1)")
    st.caption("Même personne, autre photo ⇒ distance faible ; personne différente ⇒ distance ≈ 0,5. Seuil : "
               f"{settings.match_threshold}.")
    c1, c2 = st.columns([1, 1])
    with c1:
        ref = st.text_input("Pseudonyme revendiqué", "ALICE", key="ver_ref")
        data, arr = image_input("ver", 1, 2)
        go = st.button("Vérifier", type="primary", disabled=data is None)
    with c2:
        if arr is not None:
            st.image(arr, caption="Image présentée", width=320)
    if go:
        r = run(svc.verify, ref, data)
        if r:
            m1, m2, m3 = st.columns(3)
            m1.metric("Décision", "ACCEPTÉ ✅" if r.match else "REFUSÉ ❌")
            m2.metric("Distance de Hamming", f"{r.hamming_distance:.3f}", help="0 = identiques, 0,5 = sans rapport")
            m3.metric("Temps", f"{r.decision_ms:.0f} ms")
            st.progress(min(r.hamming_distance / 0.6, 1.0), text=f"Score {r.hamming_distance:.3f}  |  seuil {r.threshold}")

with tabs[2]:
    st.subheader("Ce que contient réellement la base")
    st.caption("Vue « attaquant » : le contenu brut des tables SQL.")
    st.dataframe(subjects(), width="stretch")
    with sqlite3.connect(DB_FILE) as con:
        rows = con.execute("select s.external_ref, t.kek_id, t.algorithm, length(t.ciphertext), hex(substr(t.ciphertext,1,24)), "
                           "hex(t.nonce) from templates t join subjects s on s.id=t.subject_id").fetchall()
    st.dataframe(pd.DataFrame(rows, columns=["pseudonyme", "clé (KEK)", "algorithme", "taille (octets)",
                                             "début du chiffré (hex)", "nonce"]), width="stretch")
    st.info("Aucune colonne image, aucun IrisCode en clair : uniquement des octets chiffrés et des métadonnées.")

with tabs[3]:
    st.subheader("Administration (rôle admin)")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Rotation de la clé de chiffrement (KEK)**")
        st.dataframe(pd.DataFrame(ks.list_keys()), width="stretch", hide_index=True)
        if st.button("Lancer la rotation"):
            r = run(svc.rotate_keys)
            if r:
                st.success(f"{r['old_kek']} → {r['new_kek']} · {r['templates_rewrapped']} gabarit(s) rechiffré(s)")
    with c2:
        refs = subjects()["pseudonyme"].tolist()
        target = st.selectbox("Personne", refs, index=0, key=f"adm_{'-'.join(refs)}") if refs else None
        b1, b2 = st.columns(2)
        if b1.button("Révoquer le gabarit", disabled=not target):
            r = run(svc.revoke, target)
            r and st.success(f"Révoqué. Prochaine version : {r['next_cancelable_version']}")
        if b2.button("Effacer (RGPD)", disabled=not target):
            r = run(svc.delete, target)
            r and st.success(f"{target} supprimé définitivement.")
        st.markdown("**Ré-enrôlement après révocation**")
        data, _ = image_input("reenr", 1, 3)
        if st.button("Ré-enrôler", disabled=not (target and data)):
            r = run(svc.reenroll, target, data)
            r and st.success(f"Actif, version {r['cancelable_version']}")

with tabs[4]:
    st.subheader("Journal d'audit chaîné (HMAC-SHA256)")
    if not who.can("read_audit"):
        st.error(f"⛔ Le rôle « {role} » ne peut pas lire l'audit. Choisissez auditor ou admin.")
    else:
        db = Session()
        res = verify_chain(db, ks.audit_key)
        (st.success if res["valid"] else st.error)(
            f"Chaîne {'INTÈGRE' if res['valid'] else 'ROMPUE à l’entrée #' + str(res['broken_at'])} — "
            f"{res['checked']} entrée(s) vérifiée(s)" + ("" if res["valid"] else f" — {res['reason']}"))
        rows = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)).scalars().all()
        st.dataframe(pd.DataFrame([{"#": r.id, "horodatage": r.ts[:19], "acteur": r.actor, "action": r.action,
                                    "sujet": r.subject_ref, "résultat": r.outcome, "détails": r.details,
                                    "empreinte": r.hash[:16] + "…"} for r in rows]), width="stretch", hide_index=True)
        db.close()

with tabs[5]:
    st.subheader("Simuler un attaquant ayant accès au fichier de la base")
    st.caption("Ces boutons modifient directement le fichier SQLite, comme le ferait un pirate ou un administrateur malveillant.")
    refs = subjects()["pseudonyme"].tolist()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**1. Altérer un gabarit**")
        v = st.selectbox("Victime", refs, index=0, key=f"a1_{'-'.join(refs)}") if refs else None
        if st.button("Inverser un octet du chiffré", disabled=not v):
            with sqlite3.connect(DB_FILE) as con:
                tid, ct = con.execute("select t.id, t.ciphertext from templates t join subjects s on s.id=t.subject_id "
                                      "where s.external_ref=?", (v,)).fetchone()
                ct = bytearray(ct); ct[40] ^= 0xFF
                con.execute("update templates set ciphertext=? where id=?", (bytes(ct), tid))
            st.warning(f"Gabarit de {v} altéré. Lancez une vérification : une alerte d'intégrité doit apparaître.")
    with c2:
        st.markdown("**2. Substituer un gabarit**")
        v2 = st.selectbox("Victime", refs, index=0, key=f"a2_{'-'.join(refs)}") if refs else None
        others = [r for r in refs if r != v2]
        att = st.selectbox("Attaquant", others, index=0 if others else None,
                           key=f"a3_{v2}_{'-'.join(others)}") if others else None
        if refs and not others:
            st.caption("Enrôlez au moins deux personnes pour cette attaque.")
        if st.button("Copier le gabarit de l'attaquant chez la victime", disabled=not (v2 and att)):
            with sqlite3.connect(DB_FILE) as con:
                q = ("select t.ciphertext,t.nonce,t.wrapped_dek,t.dek_nonce,t.kek_id from templates t join subjects s "
                     "on s.id=t.subject_id where s.external_ref=?")
                m = con.execute(q, (att,)).fetchone()
                con.execute("update templates set ciphertext=?,nonce=?,wrapped_dek=?,dek_nonce=?,kek_id=? where subject_id="
                            "(select id from subjects where external_ref=?)", (*m, v2))
            st.warning(f"Vérifiez « {v2} » avec l'œil de {att} : l'accès doit être refusé (AAD).")
    with c3:
        st.markdown("**3. Falsifier le journal**")
        if st.button("Transformer les échecs en succès"):
            with sqlite3.connect(DB_FILE) as con:
                n = con.execute("update audit_logs set outcome='match' where outcome in ('no_match','integrity_alert')").rowcount
            st.warning(f"{n} entrée(s) falsifiée(s). Ouvrez l'onglet Audit : la chaîne doit être ROMPUE.")
    st.divider()
    if st.button("🔄 Réinitialiser complètement la démonstration"):
        st.cache_resource.clear()
        for f in (DB_FILE, settings.keystore_path, settings.keystore_path.with_name("streamlit_master.key")):
            Path(f).unlink(missing_ok=True)
        st.rerun()

with tabs[6]:
    st.markdown(Path("docs/STREAMLIT_ABOUT.md").read_text() if Path("docs/STREAMLIT_ABOUT.md").exists() else "")
    res = Path("docs/results.json")
    if res.exists():
        st.json(json.loads(res.read_text()), expanded=False)
