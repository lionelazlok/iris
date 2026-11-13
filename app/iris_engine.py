"""Moteur de reconnaissance iris — pipeline de type Daugman / Masek.

Étapes (Masek, 2003 ; Daugman, 2004) :
  1. Segmentation : pupille (seuillage + opérateur intégro-différentiel),
     limbe iris/sclère (opérateur intégro-différentiel de Daugman sur arcs latéraux).
  2. Normalisation « rubber sheet » de Daugman : anneau irien -> rectangle 20 x 240.
  3. Encodage : filtre log-Gabor 1D sur chaque ligne angulaire, quantification de
     phase sur 2 bits -> IrisCode (20 x 240 x 2 = 9 600 bits) + masque de bruit.
  4. Comparaison : distance de Hamming fractionnaire masquée, minimisée sur des
     décalages circulaires (compensation de la rotation de l'œil).

Implémentation pédagogique simplifiée, réécrite d'après les publications ; elle
n'est pas destinée à la production. Un adaptateur vers Open-IRIS (Worldcoin) peut
remplacer `IrisEngine.extract` sans modifier le reste de l'architecture.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

RADIAL_RES = 20
ANGULAR_RES = 240
MAX_SHIFT = 8  # ±8 colonnes ≈ ±12° de rotation


class SegmentationError(ValueError):
    """Image inexploitable (pupille ou iris introuvable)."""


@dataclass
class IrisTemplate:
    code: np.ndarray  # bool (RADIAL_RES, ANGULAR_RES, 2)
    mask: np.ndarray  # bool (RADIAL_RES, ANGULAR_RES, 2) — True = bit non fiable

    @property
    def usable_ratio(self) -> float:
        return float(1.0 - self.mask.mean())


@dataclass
class Segmentation:
    pupil: tuple[float, float, float]  # (x, y, r)
    iris: tuple[float, float, float]


def _circle_mean(img: np.ndarray, x: float, y: float, r: float, angles: np.ndarray) -> float:
    xs = x + r * np.cos(angles)
    ys = y + r * np.sin(angles)
    return float(ndimage.map_coordinates(img, [ys, xs], order=1, mode="nearest").mean())


def integro_differential(img, x, y, radii, angles, sigma=1.5):
    """Opérateur intégro-différentiel de Daugman :
    max_r | G_sigma(r) * d/dr ∮ I(x,y)/(2πr) ds |  → renvoie (r*, score)."""
    means = np.array([_circle_mean(img, x, y, r, angles) for r in radii])
    deriv = np.gradient(means)
    deriv = ndimage.gaussian_filter1d(deriv, sigma)
    i = int(np.argmax(np.abs(deriv)))
    return float(radii[i]), float(abs(deriv[i]))


class IrisEngine:
    def __init__(self, wavelength: float = 18.0, sigma_on_f: float = 0.5):
        self.wavelength = wavelength
        self.sigma_on_f = sigma_on_f

    # ---------- 1. Segmentation ----------
    def segment(self, img: np.ndarray) -> Segmentation:
        img = img.astype(np.float64)
        h, w = img.shape
        smooth = ndimage.gaussian_filter(img, 2)
        thr = np.percentile(smooth, 1) + 18
        dark = ndimage.binary_fill_holes(smooth < thr)
        dark = ndimage.binary_opening(dark, iterations=4)
        labels, n = ndimage.label(dark)
        if n == 0:
            raise SegmentationError("pupille introuvable")
        sizes = ndimage.sum(dark, labels, range(1, n + 1))
        blob = labels == (int(np.argmax(sizes)) + 1)
        if blob.sum() < 200:
            raise SegmentationError("pupille trop petite")
        py, px = ndimage.center_of_mass(blob)
        r0 = np.sqrt(blob.sum() / np.pi)
        full = np.linspace(0, 2 * np.pi, 64, endpoint=False)
        rp, _ = integro_differential(smooth, px, py, np.arange(max(5, r0 * 0.7), r0 * 1.3, 0.5), full)

        # Limbe : arcs latéraux uniquement (évite paupières), petite recherche de centre
        lateral = np.concatenate([np.linspace(-np.pi / 5, np.pi / 5, 24),
                                  np.linspace(np.pi - np.pi / 5, np.pi + np.pi / 5, 24)])
        rmax = min(px, w - px, py + 40, h - py + 40, w / 2) - 2
        radii = np.arange(rp * 1.6, rmax, 1.0)
        if len(radii) < 5:
            raise SegmentationError("iris hors champ")
        best = (0.0, px, py, radii[0])
        for dx in (-3, 0, 3):
            for dy in (-3, 0, 3):
                r, s = integro_differential(smooth, px + dx, py + dy, radii, lateral)
                if s > best[0]:
                    best = (s, px + dx, py + dy, r)
        _, ix, iy, ri = best
        return Segmentation(pupil=(px, py, rp), iris=(ix, iy, ri))

    # ---------- 2. Normalisation (rubber sheet) ----------
    def normalize(self, img: np.ndarray, seg: Segmentation):
        img = img.astype(np.float64)
        px, py, rp = seg.pupil
        ix, iy, ri = seg.iris
        theta = np.linspace(0, 2 * np.pi, ANGULAR_RES, endpoint=False)
        # On évite les bords exacts (transition floue)
        rho = np.linspace(0.05, 0.95, RADIAL_RES)[:, None]
        xp, yp = px + rp * np.cos(theta), py + rp * np.sin(theta)
        xi, yi = ix + ri * np.cos(theta), iy + ri * np.sin(theta)
        xs = (1 - rho) * xp + rho * xi
        ys = (1 - rho) * yp + rho * yi
        polar = ndimage.map_coordinates(img, [ys, xs], order=1, mode="constant", cval=-1)
        outside = polar < 0
        # Bruit : reflets spéculaires et paupières (valeurs aberrantes)
        valid = polar[~outside]
        med, mad = np.median(valid), np.median(np.abs(valid - np.median(valid))) + 1e-6
        noise = outside | (np.abs(polar - med) > 4.5 * 1.4826 * mad)
        return polar, noise

    # ---------- 3. Encodage log-Gabor ----------
    def encode(self, polar: np.ndarray, noise: np.ndarray) -> IrisTemplate:
        rows, cols = polar.shape
        p = polar.copy()
        p[noise] = np.mean(polar[~noise]) if (~noise).any() else 0
        freqs = np.fft.fftfreq(cols)
        f0 = 1.0 / self.wavelength
        lg = np.zeros(cols)
        pos = freqs > 0
        lg[pos] = np.exp(-(np.log(freqs[pos] / f0) ** 2) / (2 * np.log(self.sigma_on_f) ** 2))
        resp = np.fft.ifft(np.fft.fft(p, axis=1) * lg[None, :] * 2, axis=1)
        code = np.stack([resp.real > 0, resp.imag > 0], axis=-1)
        weak = np.abs(resp) < 1e-4 * (np.abs(resp).max() + 1e-12)
        mask = np.repeat((noise | weak)[..., None], 2, axis=-1)
        return IrisTemplate(code=code, mask=mask)

    def extract(self, img: np.ndarray) -> IrisTemplate:
        seg = self.segment(img)
        polar, noise = self.normalize(img, seg)
        tpl = self.encode(polar, noise)
        if tpl.usable_ratio < 0.5:
            raise SegmentationError("qualité insuffisante (trop de bits masqués)")
        return tpl


# ---------- 4. Comparaison ----------
def hamming_distance(a_code, a_mask, b_code, b_mask) -> float:
    valid = ~(a_mask | b_mask)
    n = int(valid.sum())
    if n == 0:
        return 1.0
    return float(((a_code ^ b_code) & valid).sum() / n)


def shifted(code: np.ndarray, s: int) -> np.ndarray:
    return np.roll(code, s, axis=1)


def match(a: IrisTemplate, b: IrisTemplate, max_shift: int = MAX_SHIFT) -> tuple[float, int]:
    """Distance de Hamming minimale sur les décalages angulaires. Renvoie (HD, décalage)."""
    best = (1.0, 0)
    for s in range(-max_shift, max_shift + 1):
        hd = hamming_distance(a.code, a.mask, shifted(b.code, s), shifted(b.mask, s))
        if hd < best[0]:
            best = (hd, s)
    return best
