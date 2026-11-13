"""Générateur d'images d'iris synthétiques (substitut aux bases publiques
CASIA/UBIRIS dont l'accès exige une licence). Chaque « sujet » a une texture
irienne propre (graine) ; chaque « capture » varie : position, dilatation
pupillaire, rotation, éclairage, flou, bruit, paupière, reflet spéculaire."""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy import ndimage

W, H = 320, 280


def _texture(seed: int):
    rng = np.random.default_rng(seed)
    comps = [(rng.uniform(0.3, 1.0), rng.uniform(0.5, 8), rng.integers(2, 70),
              rng.uniform(0, 2 * np.pi), rng.uniform(0, 2 * np.pi)) for _ in range(60)]
    crypts = [(rng.uniform(0.15, 0.9), rng.uniform(0, 2 * np.pi), rng.uniform(0.04, 0.1),
               rng.uniform(0.05, 0.25)) for _ in range(18)]
    base = rng.uniform(85, 125)

    def f(rn, th):
        v = np.zeros_like(rn)
        for a, fr, fa, ph1, ph2 in comps:
            v += a * np.sin(2 * np.pi * fr * rn + ph1) * np.cos(fa * th + ph2)
        v = v / np.sqrt(len(comps)) * 22
        for cr, ct, sr, st in crypts:
            dth = np.angle(np.exp(1j * (th - ct)))
            v -= 35 * np.exp(-((rn - cr) ** 2) / (2 * sr ** 2) - dth ** 2 / (2 * st ** 2))
        return np.maximum(base + v, 58)  # l'iris reste nettement plus clair que la pupille
    return f


def capture(subject: int, session: int, rotation_deg: float | None = None) -> np.ndarray:
    tex = _texture(subject)
    srng = np.random.default_rng(subject)
    rng = np.random.default_rng(subject * 100_003 + session + 1)
    rp0, ri0 = srng.uniform(28, 38), srng.uniform(92, 104)
    cx, cy = W / 2 + rng.uniform(-6, 6), H / 2 + rng.uniform(-6, 6)
    rp = rp0 * rng.uniform(0.9, 1.12)
    ri = ri0 + rng.uniform(-1.5, 1.5)
    rot = np.deg2rad(rotation_deg if rotation_deg is not None else rng.uniform(-8, 8))
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    r = np.hypot(xx - cx, yy - cy)
    th = np.arctan2(yy - cy, xx - cx)
    img = np.full((H, W), 195.0) - 0.08 * np.maximum(r - ri, 0)
    ring = (r >= rp) & (r < ri)
    rn = (r[ring] - rp) / (ri - rp)
    img[ring] = tex(rn, th[ring] - rot)
    img[r < rp] = 22
    # Paupière supérieure (occlusion partielle)
    lid = cy - ri * rng.uniform(0.7, 0.95) + 0.002 * (xx - cx) ** 2
    img[yy < lid] = 165
    # Reflet spéculaire dans la pupille
    sx, sy = cx + rng.uniform(-8, 8), cy + rng.uniform(-8, 8)
    img[np.hypot(xx - sx, yy - sy) < 4] = 250
    img = ndimage.gaussian_filter(img, rng.uniform(0.5, 1.0))
    img = img * rng.uniform(0.88, 1.12) + rng.uniform(-8, 8)
    img += rng.normal(0, rng.uniform(3, 6), img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def save(path, arr):
    Image.fromarray(arr).save(path)


if __name__ == "__main__":
    import argparse, pathlib
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/synthetic")
    p.add_argument("--subjects", type=int, default=20)
    p.add_argument("--sessions", type=int, default=4)
    a = p.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for s in range(a.subjects):
        for k in range(a.sessions):
            save(out / f"S{s:03d}_{k}.png", capture(s, k))
    print(f"{a.subjects * a.sessions} images écrites dans {out}")
