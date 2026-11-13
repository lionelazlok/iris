"""Évaluation expérimentale : performance biométrique + coût de la sécurité.
Usage : python -m tools.benchmark [--subjects 50]  -> docs/results.json, docs/*.png"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys
import time
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.crypto_service import CryptoService, KeyStore  # noqa: E402
from app.iris_engine import IrisEngine, match  # noqa: E402
from app.template_codec import cancelable_transform, deserialize, serialize  # noqa: E402
from tools.synth_iris import capture  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs"


def rates(gen, imp, thr):
    gen, imp = np.asarray(gen), np.asarray(imp)
    return float((imp <= thr).mean()), float((gen > thr).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=50)
    ap.add_argument("--sessions", type=int, default=4)
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    eng = IrisEngine()
    res: dict = {"dataset": {"type": "synthétique", "subjects": a.subjects, "sessions": a.sessions}}

    # 1. Extraction
    tpl, times, fails = {}, [], 0
    for s in range(a.subjects):
        for k in range(a.sessions):
            img = capture(s, k)
            t0 = time.perf_counter()
            try:
                tpl[(s, k)] = eng.extract(img)
            except Exception:
                fails += 1
            times.append((time.perf_counter() - t0) * 1000)
    res["extraction"] = {"images": a.subjects * a.sessions, "failure_to_enroll": fails,
                         "mean_ms": round(st.mean(times), 1), "p95_ms": round(float(np.percentile(times, 95)), 1)}

    # 2. Distributions genuine / impostor
    gen = [match(tpl[(s, i)], tpl[(s, j)])[0] for s in range(a.subjects)
           for i, j in combinations(range(a.sessions), 2) if (s, i) in tpl and (s, j) in tpl]
    imp = [match(tpl[(x, 0)], tpl[(y, 1)])[0] for x in range(a.subjects) for y in range(a.subjects)
           if x != y and (x, 0) in tpl and (y, 1) in tpl]
    ths = np.linspace(0, 0.6, 601)
    far = np.array([rates(gen, imp, t)[0] for t in ths]); frr = np.array([rates(gen, imp, t)[1] for t in ths])
    i = int(np.argmin(np.abs(far - frr)))
    dprime = abs(np.mean(imp) - np.mean(gen)) / np.sqrt((np.var(imp) + np.var(gen)) / 2)
    res["matching"] = {
        "genuine_pairs": len(gen), "impostor_pairs": len(imp),
        "genuine_hd_mean": round(float(np.mean(gen)), 4), "genuine_hd_max": round(float(np.max(gen)), 4),
        "impostor_hd_mean": round(float(np.mean(imp)), 4), "impostor_hd_min": round(float(np.min(imp)), 4),
        "decidability_dprime": round(float(dprime), 2), "eer": round(float((far[i] + frr[i]) / 2), 4),
        "eer_threshold": round(float(ths[i]), 3),
        "at_threshold": {str(t): dict(zip(("FAR", "FRR"), rates(gen, imp, t))) for t in (0.30, 0.32, 0.34, 0.36, 0.40)},
    }
    plt.figure(figsize=(7, 4))
    plt.hist(gen, bins=40, alpha=.75, label="Authentiques (même œil)", color="#2a9d8f", density=True)
    plt.hist(imp, bins=40, alpha=.75, label="Imposteurs (yeux différents)", color="#e76f51", density=True)
    plt.axvline(0.34, ls="--", c="k", label="Seuil 0,34")
    plt.xlabel("Distance de Hamming fractionnaire"); plt.ylabel("Densité"); plt.legend()
    plt.title("Distributions des scores"); plt.tight_layout(); plt.savefig(OUT / "fig_distributions.png", dpi=160); plt.close()

    # 3. Robustesse à la rotation
    rot = {}
    for deg in (0, 4, 8, 12, 16, 20):
        hds = [match(tpl[(s, 0)], eng.extract(capture(s, 9, rotation_deg=deg)))[0] for s in range(min(15, a.subjects))]
        rot[deg] = round(float(np.mean(hds)), 4)
    res["rotation_mean_hd"] = rot
    plt.figure(figsize=(6, 3.5)); plt.plot(list(rot), list(rot.values()), "o-", c="#264653")
    plt.axhline(0.34, ls="--", c="k"); plt.xlabel("Rotation de l'œil (°)"); plt.ylabel("HD moyenne")
    plt.title("Robustesse à la rotation (compensation ±8 colonnes ≈ ±12°)"); plt.tight_layout()
    plt.savefig(OUT / "fig_rotation.png", dpi=160); plt.close()

    # 4. Coût de la sécurité
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ks = KeyStore(Path(d) / "ks.json", os.urandom(32)); c = CryptoService(ks)
        t = tpl[(0, 0)]
        raw = serialize(t)
        N = 2000
        t0 = time.perf_counter()
        for _ in range(N):
            blob = c.encrypt(raw, "s", "t")
        enc = (time.perf_counter() - t0) / N * 1e6
        t0 = time.perf_counter()
        for _ in range(N):
            c.decrypt(blob, "s", "t")
        dec = (time.perf_counter() - t0) / N * 1e6
        t0 = time.perf_counter()
        for _ in range(200):
            cancelable_transform(t, ks.cancel_secret, "s", 1)
        canc = (time.perf_counter() - t0) / 200 * 1000
        t0 = time.perf_counter()
        for _ in range(200):
            match(t, tpl[(0, 1)])
        mt = (time.perf_counter() - t0) / 200 * 1000
        stored = len(blob.ciphertext) + len(blob.nonce) + len(blob.wrapped_dek) + len(blob.dek_nonce)
        res["security_cost"] = {
            "iriscode_bits": int(t.code.size), "serialized_bytes": len(raw), "stored_bytes_encrypted": stored,
            "storage_overhead_bytes": stored - len(raw),
            "encrypt_us": round(enc, 1), "decrypt_us": round(dec, 1),
            "cancelable_transform_ms": round(canc, 2), "match_17_shifts_ms": round(mt, 2),
            "extraction_ms": res["extraction"]["mean_ms"],
            "crypto_share_of_verification_pct": round(dec / 1000 / (res["extraction"]["mean_ms"] + mt + dec / 1000) * 100, 3),
        }
        # Effet de la transformation révocable sur les scores (doit être nul)
        diffs = []
        for s in range(10):
            x, y = tpl[(s, 0)], tpl[(s, 1)]
            hd_plain = match(x, y)[0]
            sec = os.urandom(32)
            from app.iris_engine import IrisTemplate, MAX_SHIFT, hamming_distance, shifted
            tx = cancelable_transform(x, sec, "s", 1)
            hd_t = min(hamming_distance(tx.code, tx.mask,
                                        *(lambda p: (p.code, p.mask))(cancelable_transform(
                                            IrisTemplate(shifted(y.code, k), shifted(y.mask, k)), sec, "s", 1)))
                       for k in range(-MAX_SHIFT, MAX_SHIFT + 1))
            diffs.append(abs(hd_plain - hd_t))
        res["cancelable_score_deviation_max"] = float(max(diffs))
        assert deserialize(raw).code.shape == t.code.shape

    (OUT / "results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
