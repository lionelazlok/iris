"""Figures pour la présentation et le rapport -> docs/fig_*.png"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.crypto_service import CryptoService, KeyStore  # noqa: E402
from app.iris_engine import IrisEngine  # noqa: E402
from app.template_codec import cancelable_transform, serialize  # noqa: E402
from tools.synth_iris import capture  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs"
OUT.mkdir(exist_ok=True)


def pipeline():
    e = IrisEngine()
    img = capture(3, 0)
    seg = e.segment(img)
    polar, noise = e.normalize(img, seg)
    t = e.extract(img)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ks = KeyStore(Path(d) / "k.json", os.urandom(32))
        tc = cancelable_transform(t, ks.cancel_secret, "s", 1)
        ct = CryptoService(ks).encrypt(serialize(tc), "s", "t").ciphertext
    fig, ax = plt.subplots(1, 5, figsize=(17, 3.6), gridspec_kw={"width_ratios": [1.1, 1.1, 1.6, 1.6, 1.6]})
    ax[0].imshow(img, cmap="gray"); ax[0].set_title("1. Capture (image)")
    ax[1].imshow(img, cmap="gray")
    for (x, y, r), c in ((seg.pupil, "#e76f51"), (seg.iris, "#2a9d8f")):
        ax[1].add_patch(Circle((x, y), r, fill=False, ec=c, lw=2))
    ax[1].set_title("2. Segmentation\n(opérateur intégro-différentiel)")
    ax[2].imshow(polar, cmap="gray", aspect="auto"); ax[2].set_title("3. Normalisation « rubber sheet »\n20 × 240")
    ax[3].imshow(np.concatenate([t.code[..., 0], t.code[..., 1]], 0), cmap="binary", aspect="auto", interpolation="nearest")
    ax[3].set_title("4. IrisCode (log-Gabor, 9 600 bits)")
    arr = np.frombuffer(ct[:2400], dtype=np.uint8)
    bits = np.unpackbits(arr)[:9600].reshape(40, 240)
    ax[4].imshow(bits, cmap="binary", aspect="auto", interpolation="nearest")
    ax[4].set_title("5. Stocké : transformé + AES-256-GCM\n(indistinguable d'un aléa)")
    for a in ax:
        a.set_xticks([]); a.set_yticks([])
    plt.tight_layout(); plt.savefig(OUT / "fig_pipeline.png", dpi=170); plt.close()


def box(ax, x, y, w, h, text, fc, fs=9.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec="#264653", lw=1.3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, wrap=True)


def arrow(ax, a, b, label="", color="#264653"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=14, lw=1.4, color=color))
    if label:
        ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.12, label, ha="center", fontsize=8, color=color)


def architecture():
    fig, ax = plt.subplots(figsize=(13, 6.6)); ax.set_xlim(0, 13); ax.set_ylim(0, 6.6); ax.axis("off")
    box(ax, 0.2, 4.6, 2.2, 1.2, "Client / capteur\n(opérateur)", "#e9f5f2")
    box(ax, 0.2, 2.6, 2.2, 1.2, "Administrateur\nAuditeur", "#e9f5f2")
    ax.add_patch(FancyBboxPatch((3.0, 0.4), 6.4, 5.8, boxstyle="round,pad=0.02", fc="#f8f9fa", ec="#adb5bd", ls="--"))
    ax.text(6.2, 6.0, "Serveur applicatif (FastAPI)", ha="center", fontsize=10.5, weight="bold")
    box(ax, 3.3, 4.6, 2.6, 1.0, "API REST + Swagger\nTLS · validation entrées", "#fff3e0")
    box(ax, 6.5, 4.6, 2.6, 1.0, "Authentification clé d'API\nRBAC (3 rôles)", "#fff3e0")
    box(ax, 3.3, 3.0, 2.6, 1.1, "Moteur iris\nsegmentation · rubber sheet\nlog-Gabor · Hamming", "#e3f2fd")
    box(ax, 6.5, 3.0, 2.6, 1.1, "Transformation révocable\npermutation + XOR\n(HMAC sujet|version)", "#e3f2fd")
    box(ax, 6.5, 1.2, 2.6, 1.2, "Service crypto\nAES-256-GCM\nDEK par gabarit + AAD", "#fce4ec")
    box(ax, 3.3, 1.2, 2.6, 1.2, "Audit append-only\nchaînage HMAC-SHA256\nverrouillage anti-brute-force", "#fce4ec")
    box(ax, 10.1, 4.2, 2.7, 1.6, "Coffre de clés (KMS/HSM)\nclé maîtresse\nKEK versionnées (rotation)\nsecret de transformation", "#ede7f6")
    box(ax, 10.1, 0.5, 2.7, 2.6, "Base de données\nsubjects (pseudonymes)\ntemplates : chiffré,\nnonce, DEK enveloppée,\nkek_id\naudit_logs (chaînés)\n— aucune image —", "#e8f5e9")
    arrow(ax, (2.4, 5.2), (3.3, 5.1), "HTTPS")
    arrow(ax, (2.4, 3.2), (3.3, 4.75))
    arrow(ax, (5.9, 5.1), (6.5, 5.1))
    arrow(ax, (4.6, 4.6), (4.6, 4.1))
    arrow(ax, (5.9, 3.55), (6.5, 3.55))
    arrow(ax, (7.8, 3.0), (7.8, 2.4))
    ax.text(7.9, 2.62, "gabarit protégé", fontsize=8, color="#264653")
    arrow(ax, (9.1, 1.9), (10.1, 1.9), color="#c62828")
    ax.text(9.6, 2.05, "chiffré", ha="center", fontsize=8, color="#c62828")
    arrow(ax, (10.6, 4.2), (9.1, 2.3), color="#6a1b9a")
    ax.text(10.15, 3.5, "KEK", fontsize=8, color="#6a1b9a")
    ax.plot([4.6, 4.6, 9.8], [1.2, 0.75, 0.75], color="#264653", lw=1.4)
    arrow(ax, (9.8, 0.75), (10.1, 0.9))
    ax.set_title("Architecture sécurisée proposée — défense en profondeur", fontsize=13, weight="bold")
    plt.tight_layout(); plt.savefig(OUT / "fig_architecture.png", dpi=170); plt.close()


def envelope():
    plt.rcParams["font.size"] = 13
    fig, ax = plt.subplots(figsize=(11, 3.6)); ax.set_xlim(0, 11); ax.set_ylim(0, 3.4); ax.axis("off")
    box(ax, 0.1, 1.2, 1.9, 1.0, "Gabarit\n(transformé)", "#e3f2fd")
    box(ax, 2.7, 1.2, 2.2, 1.0, "AES-256-GCM\nDEK aléatoire\nnonce 96 bits", "#fce4ec")
    box(ax, 5.6, 1.9, 2.3, 0.95, "Chiffré + tag 128 bits", "#e8f5e9")
    box(ax, 5.6, 0.3, 2.3, 0.95, "DEK enveloppée\npar KEK v_n", "#e8f5e9")
    box(ax, 2.5, 2.5, 2.6, 0.8, "AAD = sujet | id | kek_id", "#fff3e0", 12)
    box(ax, 8.6, 0.9, 2.3, 1.6, "Ligne en base\n(+ kek_id)\nRotation : KEK v_n+1", "#ede7f6")
    arrow(ax, (2.0, 1.7), (2.7, 1.7)); arrow(ax, (4.9, 1.9), (5.6, 2.3)); arrow(ax, (4.9, 1.5), (5.6, 0.8))
    arrow(ax, (3.8, 2.5), (3.8, 2.2)); arrow(ax, (7.9, 2.3), (8.6, 1.9)); arrow(ax, (7.9, 0.8), (8.6, 1.3))
    for t in ax.texts:
        t.set_fontsize(max(t.get_fontsize(), 12.5))
    ax.set_title("Chiffrement d'enveloppe (envelope encryption)", fontsize=15, weight="bold")
    plt.tight_layout(); plt.savefig(OUT / "fig_envelope.png", dpi=170); plt.close()


if __name__ == "__main__":
    pipeline(); architecture(); envelope(); print("figures OK")
