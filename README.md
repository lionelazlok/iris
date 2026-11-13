# 👁️ Iris Secure DB — Securing Iris Biometric Databases

> Project: analysis of the threats facing iris biometric databases, design of a protection architecture, and a **working prototype** (REST API + web interface) that has been measured and attacked.

The system enrolls and verifies people by their iris **without ever storing either the eye image or its readable code**. What is stored is scrambled by a revocable transform, then encrypted with AES-256-GCM. Every access is checked against a role and recorded in a tamper-evident audit log.

| | |
|---|---|
| **Language** | Python 3.10+ |
| **API** | FastAPI + Swagger (`/docs`) |
| **Web interface** | Streamlit (free deployment possible) |
| **Database** | SQLite (demo) / PostgreSQL (production) via SQLAlchemy |
| **Cryptography** | AES-256-GCM, envelope encryption, HMAC-SHA256 (`cryptography`) |
| **Tests** | 30 `pytest` tests, including 10 attack scenarios |
| **Authors** | Lionel F. S. AZELOKONON, Clément KOUTON |

---

## Table of contents

1. [Results at a glance](#1-results-at-a-glance)
2. [Background and goals](#2-background-and-goals)
3. [Features](#3-features)
4. [Architecture](#4-architecture)
5. [Security mechanisms in detail](#5-security-mechanisms-in-detail)
6. [Iris recognition engine](#6-iris-recognition-engine)
7. [Repository layout](#7-repository-layout)
8. [Installation](#8-installation)
9. [Configuration](#9-configuration-environment-variables)
10. [Usage](#10-usage)
11. [API reference](#11-api-reference)
12. [Data model](#12-data-model)
13. [Automated tests](#13-automated-tests)
14. [Experimental evaluation](#14-experimental-evaluation)
15. [Running online](#15-running-online)
16. [Regenerating figures and results](#16-regenerating-figures-and-results)
17. [Production checklist](#17-production-checklist)
18. [Known limitations](#18-known-limitations)
19. [Troubleshooting](#19-troubleshooting)
20. [References](#20-references)

---

## 1. Results at a glance

The measurements cover 200 synthetic images (50 people × 4 captures). They can be regenerated with `python -m tools.benchmark`.

| Metric | Result | Interpretation |
|---|---|---|
| Impostors accepted (FAR, threshold 0.34) | **0 / 2,450** | No false acceptance |
| Genuine users rejected (FRR) | **1 / 300 (0.33%)** | One heavily rotated capture |
| Decidability index d′ | **14.48** | Classes very well separated |
| Failures to enroll | 0 / 200 | Every image could be processed |
| Tolerated eye rotation | ≈ 12° | Compensated by ±8 shifts |
| Feature extraction time (mean) | ≈ 23 ms | — |
| Full verification through the API | ≈ 30 ms | Instant for the user |
| Encryption / decryption | 6.6 µs / 4.4 µs | ≈ 0.02% of verification time |
| Storage overhead | +88 bytes per template (+3.7%) | Negligible |
| Effect of protection on scores | **0** | Accuracy strictly unchanged |
| Attack scenarios | **10 / 10 blocked or detected** | See [§13](#13-automated-tests) |

> ⚠️ **Synthetic images**: real-world databases (CASIA-Iris, UBIRIS, ND-IRIS) require a license, cannot be redistributed, and contain sensitive personal data. Error rates on real photos would be higher. These results validate the pipeline and the security layer, not field performance.

---

## 2. Background and goals

A stolen password can be changed; **a stolen iris cannot**. A centralized biometric database is therefore a high-value target, and a breach is permanent: in the OPM breach (United States, 2015), 5.6 million fingerprints were stolen; in the Biostar 2 incident (2019), more than one million fingerprints were left unencrypted. The GDPR classifies such data as sensitive (Art. 9). **ISO/IEC 24745** requires three properties:

| Requirement | Meaning | How the prototype meets it |
|---|---|---|
| Irreversibility | The iris cannot be recovered from what is stored | Transform, then encryption |
| Unlinkability | A person cannot be linked across two databases | Transform specific to each subject and version |
| Revocability | A compromised reference can be cancelled and reissued | Version incremented, re-enrollment |
| *(+) Performance* | Recognition must not degrade | Hamming distance preserved exactly |

**Goals**: (1) theoretical framework (biometrics, threats, protections); (2) secure architecture; (3) a prototype with a testable API; (4) measurements of accuracy, cost and resistance to attacks.

---

## 3. Features

- **Enrollment** of a person from an eye image (PNG, JPG, BMP).
- **1:1 verification** ("is this person really EMP-001?") with score, decision and processing time.
- **Revocation** of a compromised template, then **re-enrollment** with a new transform that cannot be linked to the old one.
- **Permanent erasure** (right to erasure, GDPR Art. 17).
- **Key rotation** without re-enrolling anyone.
- **Role-based access control**: `operator`, `auditor`, `admin`.
- **Hash-chained audit log** with integrity verification.
- **Lockout** after 5 consecutive failures (15 minutes).
- **Streamlit interface** with an **attack simulation** tab.
- **Synthetic iris generator**, **benchmark**, **10-step demo**.

---

## 4. Architecture

![Architecture](docs/fig_architecture.png)

### Enrollment flow

```
Image ──► validation (size, format, resolution)
      ──► segmentation ─► normalization 20×240 ─► IrisCode 9,600 bits + mask
      ──► revocable transform T(subject, version)             [never stored in clear]
      ──► serialization ─► AES-256-GCM (random DEK, AAD = subject|template|KEK)
      ──► DEK wrapped by the active KEK
      ──► INSERT templates (ciphertext, nonces, wrapped DEK, kek_id)
      ──► chained audit entry                                  [the image is never written]
```

### Verification flow

```
Probe image ─► probe IrisCode
Database ─► decryption (GCM tag and AAD check integrity and context)
            └─ failure ⇒ INTEGRITY ALERT (409) + audit
For each shift s ∈ [-8, +8]: HD( stored , T(shift(probe, s)) )
Decision: min HD ≤ 0.34 ⇒ accepted; otherwise failure counter (lockout at 5)
```

---

## 5. Security mechanisms in detail

### 5.1 Revocable transform (cancelable biometrics) — `app/template_codec.py`
- Seed = `HMAC-SHA256(secret, "cancelable|<subject>|<version>")`.
- The seed determines a **permutation P** of the 9,600 bit positions and a **9,600-bit string K**.
- Stored template: `T(c) = P(c) ⊕ K`; the mask is permuted the same way.
- Property: `HD(T(a), T(b)) = HD(a, b)`, so matching happens **in the transformed domain** with no loss of accuracy.
- Revocation: `version + 1` ⇒ new transform; two versions of the same eye give HD ≈ 0.5, so they cannot be linked.
- **Limitation**: the transform is invertible if its secret leaks together with the database. It complements encryption, it does not replace it.

### 5.2 Authenticated encryption, AES-256-GCM with envelope — `app/crypto_service.py`
| Item | Value |
|---|---|
| Algorithm | AES-256-GCM (AEAD, NIST SP 800-38D) |
| Data key (DEK) | 256 random bits, **one per template** |
| Nonce | 96 random bits (`os.urandom`), one per operation |
| Tag | 128 bits: changing even a single bit is detected |
| AAD | `iris-template-v1|<subject>|<template id>|<kek_id>` binds the ciphertext to **its own** row |
| Envelope | DEK encrypted by the active KEK (same AAD) |
| Keystore | JSON file fully encrypted with AES-GCM under the **master key** |
| Master key | `IRIS_MASTER_KEY`; in production: KMS or HSM |

**Rotation** (`POST /admin/rotate-keys`): a new KEK `kek-vN` becomes active and the old one is retired. Each template is decrypted in memory, then re-encrypted with a fresh DEK under the new KEK, with no re-enrollment.

### 5.3 Access control — `app/security.py`
- API keys are sent in the `X-API-Key` header, stored only as **SHA-256 hashes** and compared in **constant time**.

| Permission | operator | auditor | admin |
|---|:-:|:-:|:-:|
| enroll, verify | ✅ | ❌ | ✅ |
| read_subject (metadata) | ✅ | ✅ | ✅ |
| read_audit | ❌ | ✅ | ✅ |
| rotate_keys, revoke, delete | ❌ | ❌ | ✅ |

### 5.4 Hash-chained audit log — `app/audit.py`
- `hash_i = HMAC-SHA256(k_audit, hash_{i-1} ‖ JSON(entry_i))`, with `hash_0 = 0…0`.
- `k_audit` is derived separately and is **distinct** from the encryption keys.
- Logged events: enrollments, verifications (with score), 401/403 refusals, integrity alerts, rotations, revocations, erasures.
- `GET /audit/verify` recomputes the chain and detects any **modification** or **deletion in the middle** of the log, pointing to the faulty entry.
- The log contains **no biometric data**.

### 5.5 Other protections
- **Brute-force protection**: 5 failures ⇒ subject locked for 15 minutes (`423` response).
- **Input validation**: 5 MB maximum, 4 megapixels maximum, format checked by Pillow.
- **Data minimization**: no image is stored; subjects are identified by a pseudonym (`external_ref`).
- **HTTP headers**: `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
- **SQLite foreign keys** enabled; templates are deleted in cascade with their subject.

---

## 6. Iris recognition engine

File `app/iris_engine.py`: an educational re-implementation of the pipeline described by Daugman (2004) and Masek (2003).

![Pipeline](docs/fig_pipeline.png)

| Step | Method | Parameters |
|---|---|---|
| Pupil segmentation | Thresholding, largest component, then integro-differential operator | full circle, 64 angles |
| Limbus segmentation | Daugman's integro-differential operator on **lateral** arcs (avoids eyelids), centre search ±3 px | |
| Normalization | Daugman's rubber sheet model, bilinear interpolation | **20 × 240** |
| Noise mask | Outside the image + outliers (median ± 4.5·MAD): eyelid, reflections | |
| Encoding | **1D log-Gabor** filter per row, phase quantized to 2 bits | λ = 18, σ/f = 0.5 |
| Template | **9,600 bits** + mask | |
| Matching | Masked fractional Hamming distance, minimum over circular shifts | ±8 columns (≈ ±12°), threshold 0.34 |

The engine sits behind `IrisEngine.extract(image) -> IrisTemplate`, so it can be swapped, for example for [Open-IRIS](https://github.com/worldcoin/open-iris), without touching the security layer.

**Synthetic generator** (`tools/synth_iris.py`): each subject has its own texture (60 radial and angular components, 18 crypts). Each capture varies the centre (±6 px), dilation (−10% to +12%), rotation (±8°), lighting, blur, noise, eyelid and specular reflection.

---

## 7. Repository layout

```
.
├── app/                         # Application (core of the project)
│   ├── config.py                # Settings and environment variables
│   ├── iris_engine.py           # Iris engine: segmentation, normalization, log-Gabor, Hamming
│   ├── template_codec.py        # Binary serialization + revocable transform
│   ├── crypto_service.py        # AES-256-GCM, DEK/KEK envelope, keystore, rotation
│   ├── models.py                # Tables: subjects, templates, audit_logs
│   ├── database.py              # SQLAlchemy engine, table creation
│   ├── audit.py                 # HMAC-chained log + verification
│   ├── security.py              # API keys, roles and permissions
│   ├── service.py               # Business logic: enroll, verify, revoke, erase, rotate
│   └── main.py                  # FastAPI application (Swagger at /docs)
├── streamlit_app.py             # Streamlit web interface (7 tabs, incl. attack simulation)
├── .streamlit/config.toml       # Streamlit theme and upload limit
├── tools/
│   ├── synth_iris.py            # Synthetic iris image generator
│   ├── demo.py                  # 10-step demonstration scenario
│   ├── benchmark.py             # Measurements: FAR/FRR/EER, rotation, crypto cost
│   └── figures.py               # Diagrams (architecture, pipeline, envelope)
├── tests/
│   ├── conftest.py              # Test setup (temporary database and keystore)
│   ├── test_engine.py           # Iris engine (4 tests)
│   ├── test_crypto.py           # Cryptography and transform (10 tests)
│   └── test_api.py              # API, RBAC and attacks (16 tests)
├── data/demo/                   # Ready-to-upload images (Swagger / Streamlit)
├── docs/
│   ├── results.json             # Raw measurement results
│   ├── fig_*.png                # Figures (architecture, pipeline, envelope, distributions, rotation)
│   └── STREAMLIT_ABOUT.md       # Text of the Streamlit "About" tab
├── Dockerfile                   # Image for online hosting (API or Streamlit)
├── render.yaml                  # One-click deployment on Render
├── requirements.txt
├── pytest.ini
└── .gitignore                   # Excludes databases, keystores and secrets
```

Files created at runtime (ignored by Git): `data/iris_secure.db`, `data/keystore.json`, `data/master.key`, and their `data/streamlit*` counterparts.

---

## 8. Installation

**Requirements**: Python **3.10 or later**, `pip` and Git. No database server is needed: SQLite is built in.

```bash
git clone https://github.com/lionelazlok/iris.git
cd iris

# Virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows (PowerShell or cmd)

pip install -r requirements.txt
```

Quick check:

```bash
pytest -q          # expected: 30 passed
```

---

## 9. Configuration (environment variables)

All variables are optional for the demo.

| Variable | Default | Purpose |
|---|---|---|
| `IRIS_MASTER_KEY` | *(unset: demo key generated in `data/master.key`)* | Master key, 32 bytes in base64. **Required in production.** |
| `IRIS_API_KEYS` | `admin-demo-key:admin,operator-demo-key:operator,auditor-demo-key:auditor` | API keys and their roles |
| `IRIS_DB_URL` | `sqlite:///./data/iris_secure.db` | SQLAlchemy URL (e.g. `postgresql+psycopg://user:pwd@host/iris`) |
| `IRIS_KEYSTORE` | `./data/keystore.json` | Location of the encrypted keystore |
| `IRIS_MATCH_THRESHOLD` | `0.34` | Decision threshold (Hamming distance) |
| `IRIS_MAX_FAILED` | `5` | Failures before lockout |
| `IRIS_LOCKOUT_MIN` | `15` | Lockout duration (minutes) |

Generate a master key:

```bash
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
export IRIS_MASTER_KEY="<value>"        # Windows PowerShell: $env:IRIS_MASTER_KEY="<value>"
```

> The master key must stay **the same** across restarts: without it, the keystore and therefore the whole database are unreadable. This is the intended behavior.

---

## 10. Usage

### 10.1 API + Swagger (built-in test interface)

```bash
uvicorn app.main:app --reload
```

1. Open **http://127.0.0.1:8000/docs**.
2. Click **Authorize** and enter `operator-demo-key`.
3. `POST /enroll` → *Try it out* → `external_ref = ALICE`, image = `data/demo/alice_enrolement.png` → *Execute*.
4. `POST /verify` → `ALICE` + `data/demo/alice_verification.png` ⇒ `"match": true`.
5. `POST /verify` → `ALICE` + `data/demo/imposteur.png` ⇒ `"match": false`.
6. *Authorize* with `admin-demo-key` → `POST /admin/rotate-keys`, `POST /subjects/ALICE/revoke`…
7. *Authorize* with `auditor-demo-key` → `GET /audit`, then `GET /audit/verify`.

Demo keys:

| Key | Role |
|---|---|
| `operator-demo-key` | operator |
| `auditor-demo-key` | auditor |
| `admin-demo-key` | admin |

### 10.2 Command line (curl)

```bash
H="X-API-Key: operator-demo-key"
curl -X POST localhost:8000/enroll -H "$H" -F external_ref=ALICE -F image=@data/demo/alice_enrolement.png
curl -X POST localhost:8000/verify -H "$H" -F external_ref=ALICE -F image=@data/demo/alice_verification.png
curl localhost:8000/subjects/ALICE -H "$H"
curl -X POST localhost:8000/admin/rotate-keys -H "X-API-Key: admin-demo-key"
curl localhost:8000/audit/verify -H "X-API-Key: auditor-demo-key"
```

### 10.3 Streamlit web interface

```bash
streamlit run streamlit_app.py          # → http://localhost:8501
```

| Tab | Content |
|---|---|
| ① Enrôlement (Enrollment) | Pseudonym + synthetic iris (person no., capture no.) or uploaded file |
| ② Vérification (Verification) | Decision, Hamming distance, time, gauge against the threshold |
| ③ Base de données (Database) | **Raw** table contents, as an attacker would see them: ciphertext only |
| ④ Administration | Key rotation, revocation, re-enrollment, erasure |
| ⑤ Audit | Full log + chain status (intact or broken) |
| ⑥ Attaques (Attacks) | Tamper with a template, swap templates, forge the log, reset |
| ℹ️ À propos (About) | Explanations and raw results |

The role is chosen in the sidebar. The interface labels are in French. **Same person + different capture** ⇒ accepted; **different person** ⇒ rejected.

### 10.4 Automated 10-step demo

```bash
python -m tools.demo                               # in memory, temporary database
python -m tools.demo --url http://127.0.0.1:8000   # against a running server
```

1. Enrollment of Alice and Bob
2. Metadata: only unreadable ciphertext exists in the database
3. Genuine verification ⇒ accepted (HD ≈ 0.16)
4. Impostor ⇒ rejected (HD ≈ 0.48)
5. No key ⇒ 401; wrong role ⇒ 403
6. KEK rotation; verification still works
7. **Attack**: Bob's template copied onto Alice's row ⇒ **INTEGRITY ALERT (409)**
8. Revocation ⇒ refused (403) ⇒ re-enrollment as version 2 ⇒ accepted
9. Erasure of Bob
10. Audit log, then **forgery detected** at the exact entry

### 10.5 Generating images

```bash
python -m tools.synth_iris --subjects 20 --sessions 4 --out data/synthetic
```

---

## 11. API reference

Every route except `/health` requires the `X-API-Key` header.

| Method | Route | Permission | Input | Output |
|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok"}` |
| POST | `/enroll` | enroll | form: `external_ref` (1–128 chars), `image` (file) | `subject_id`, `template_id`, `kek_id`, `quality`, `algorithm`, `cancelable_version` |
| POST | `/verify` | verify | form: `external_ref`, `image` | `match`, `hamming_distance`, `threshold`, `decision_ms` |
| GET | `/subjects/{ref}` | read_subject | — | status, version, list of templates (ciphertext size, KEK, quality), **never the template itself** |
| POST | `/subjects/{ref}/revoke` | revoke | — | `status: revoked`, `next_cancelable_version` |
| POST | `/subjects/{ref}/reenroll` | revoke | form: `image` | `status: active`, `cancelable_version` |
| DELETE | `/subjects/{ref}` | delete | — | `deleted: true` |
| POST | `/admin/rotate-keys` | rotate_keys | — | `old_kek`, `new_kek`, `templates_rewrapped`, `integrity_errors` |
| GET | `/admin/keys` | rotate_keys | — | list of KEKs (id, date, status), **without their values** |
| GET | `/audit?limit=50` | read_audit | — | latest entries (500 maximum) |
| GET | `/audit/verify` | read_audit | — | `valid`, `checked`, `broken_at`, `reason` |

**Response codes**

| Code | Meaning |
|---|---|
| 200 | Success (including a negative verification: `match: false`) |
| 400 | Invalid image file |
| 401 | Missing or invalid API key |
| 403 | Insufficient role, or revoked template |
| 404 | Unknown subject |
| 409 | Subject already enrolled, or **integrity alert** (template tampered with or swapped) |
| 413 | Image too large (> 5 MB or > 4 Mpx) |
| 422 | Unusable image (iris not found, insufficient quality) or missing parameter |
| 423 | Subject locked after too many failures |

API error messages are returned in French.

---

## 12. Data model

**`subjects`** — pseudonymized people

| Column | Type | Description |
|---|---|---|
| id | UUID | Internal identifier (used in the AAD) |
| external_ref | text, unique | Pseudonym supplied by the business application |
| status | text | `active`, `revoked` |
| cancel_version | integer | Version of the revocable transform |
| failed_attempts, locked_until | integer, date | Brute-force protection |
| created_at | date | |

**`templates`** — **encrypted templates only**

| Column | Description |
|---|---|
| id, subject_id | Identifiers (bound by the AAD) |
| ciphertext | Transformed template, AES-256-GCM encrypted, tag included |
| nonce | 96-bit nonce |
| wrapped_dek, dek_nonce | DEK encrypted by the KEK |
| kek_id | KEK version (`kek-v1`, `kek-v2`…) |
| algorithm, quality, created_at | Metadata |

**`audit_logs`** — append-only log: `id`, `ts`, `actor`, `role`, `action`, `subject_ref`, `outcome`, `details` (JSON), `prev_hash`, `hash`.

There is **no image column** and **no plaintext IrisCode**.

---

## 13. Automated tests

```bash
pytest -q        # 30 tests, about 6 seconds
```

| File | Test | Checks |
|---|---|---|
| test_engine | `test_same_eye_matches_despite_rotation` | Same eye rotated by 9° ⇒ accepted, rotation compensated |
| | `test_different_eyes_do_not_match` | Different eyes ⇒ HD > 0.40 |
| | `test_template_shape_and_quality` | Template 20×240×2, quality > 80% |
| | `test_blank_image_rejected` | Blank image rejected |
| test_crypto | `test_serialize_roundtrip` | Lossless serialization |
| | `test_encrypt_decrypt_roundtrip` | Reversible encryption, plaintext absent from ciphertext |
| | `test_nonces_and_ciphertexts_unique` | Different nonce and ciphertext every time |
| | `test_bitflip_detected` | 1 bit changed ⇒ refused |
| | `test_swap_to_other_subject_detected` | Ciphertext moved to another subject ⇒ refused (AAD) |
| | `test_wrong_master_key_rejected` | Wrong master key ⇒ keystore unreadable |
| | `test_keystore_file_has_no_plain_keys` | No plaintext key in the keystore |
| | `test_rotation_rewrap` | Rotation ⇒ `kek-v2`, data intact |
| | `test_cancelable_preserves_distance_and_hides_code` | HD preserved, raw code hidden |
| | `test_revoked_version_unlinkable` | Versions v1 and v2 unlinkable (HD > 0.45) |
| test_api | `test_enroll_and_verify_genuine` | Nominal flow |
| | `test_impostor_rejected` | Impostor rejected |
| | `test_duplicate_enrollment_refused` | Duplicate enrollment ⇒ 409 |
| | `test_no_api_key` | No key ⇒ 401 |
| | `test_rbac` | Role matrix (403) |
| | `test_invalid_image` | Invalid file ⇒ 400 |
| | `test_db_contains_no_plain_template` | **Attack**: reading the database ⇒ nothing usable |
| | `test_tampered_db_raises_integrity_alert` | **Attack**: tampering ⇒ 409 + audit |
| | `test_template_substitution_attack` | **Attack**: template swap ⇒ 409 |
| | `test_lockout_after_failures` | **Attack**: brute force ⇒ 423 |
| | `test_rotation_keeps_verification_working` | Transparent rotation |
| | `test_revoke_and_reenroll` | Revocation then re-enrollment |
| | `test_delete_rgpd` | Complete erasure |
| | `test_audit_chain_detects_tampering` | **Attack**: modified log ⇒ detected |
| | `test_audit_chain_detects_deletion` | **Attack**: deleted entry ⇒ detected |
| | `test_unauthenticated_access_logged` | Anonymous attempts are logged |

---

## 14. Experimental evaluation

```bash
python -m tools.benchmark --subjects 50 --sessions 4    # about 1 minute
```

Produces `docs/results.json`, `docs/fig_distributions.png` and `docs/fig_rotation.png`.

**Protocol**: 300 genuine comparisons (all pairs of captures of the same subject) and 2,450 impostor comparisons. The threshold is swept from 0 to 0.6. Timings are measured over 2,000 iterations.

![Distributions](docs/fig_distributions.png)

| Threshold | FAR | FRR |
|---|---|---|
| 0.30 | 0% | 0.67% |
| 0.32 | 0% | 0.67% |
| **0.34** | **0%** | **0.33%** |
| 0.36 | 0% | 0.33% |
| 0.40 | 0% | 0% |

| Rotation | 0° | 4° | 8° | 12° | 16° | 20° |
|---|---|---|---|---|---|---|
| Mean HD | 0.138 | 0.138 | 0.171 | 0.316 | 0.367 | 0.401 |

---

## 15. Running online

### Option A — Streamlit Community Cloud (free, recommended for demos)
1. Go to **https://share.streamlit.io** and sign in with GitHub.
2. **Create app** → *Deploy a public app from GitHub*.
3. Repository: `lionelazlok/iris` · Branch: `main` · Main file path: `streamlit_app.py`.
4. *Advanced settings* → Python 3.12 → **Secrets**:
   ```toml
   IRIS_MASTER_KEY = "<32-byte base64 key>"
   ```
5. **Deploy**. The URL looks like `https://<name>.streamlit.app`.

> Storage on the free tier is **ephemeral**: the database starts empty again whenever the app restarts. That is fine for a demo.

### Option B — FastAPI on Render (free)
1. **https://render.com** → *New* → *Blueprint* → pick the repository (`render.yaml` is detected).
2. Set `IRIS_MASTER_KEY` and `IRIS_API_KEYS` (**do not reuse the demo keys in public**).
3. Swagger is then available at `https://<service>.onrender.com/docs`.

### Option C — Hugging Face Spaces (Docker)
Create a **Docker** Space, push the repository to it, and set `PORT=7860` and `MODE=streamlit` (web interface) or leave `MODE` empty (API). Add `IRIS_MASTER_KEY` under *Settings → Secrets*.

### Option D — Docker, anywhere
```bash
docker build -t iris-secure .
docker run -p 8000:8000 -e IRIS_MASTER_KEY=<key> iris-secure                              # API
docker run -p 8501:8501 -e PORT=8501 -e MODE=streamlit -e IRIS_MASTER_KEY=<key> iris-secure  # Streamlit
```

### Option E — GitHub Codespaces (nothing to install)
On the repository page: **Code → Codespaces → Create codespace**, then in the terminal:
`pip install -r requirements.txt && streamlit run streamlit_app.py`. The port opens automatically in the browser.

---

## 16. Regenerating figures and results

| Output | Command |
|---|---|
| `docs/results.json`, `docs/fig_distributions.png`, `docs/fig_rotation.png` | `python -m tools.benchmark` |
| `docs/fig_architecture.png`, `docs/fig_pipeline.png`, `docs/fig_envelope.png` | `python -m tools.figures` |
| `data/demo/*.png` | `python -m tools.demo` |

Run `benchmark` before `figures` after changing the engine, so that every figure reflects the same measurements.

---

## 17. Production checklist

- [ ] Master key held in a **KMS or HSM** (AWS KMS, Azure Key Vault, HashiCorp Vault), never in a file.
- [ ] **TLS** enforced (Nginx or Caddy reverse proxy, or the hosting provider), mutual TLS between services.
- [ ] Strong, per-client API keys, or OAuth2/OIDC authentication.
- [ ] **PostgreSQL** with disk encryption and encrypted backups.
- [ ] Head of the audit log anchored externally (qualified timestamping, WORM storage).
- [ ] Periodic KEK rotation and an incident response procedure.
- [ ] Presentation attack detection (fake irises, ISO/IEC 30107).
- [ ] Engine evaluated on **real data** and threshold recalibrated.
- [ ] Data protection impact assessment (DPIA, GDPR Art. 35) and legal basis (Art. 9).
- [ ] Global rate limiting and monitoring.

---

## 18. Known limitations

| Limitation | Consequence | Way forward |
|---|---|---|
| Synthetic images | Optimistic FAR and FRR | CASIA-Iris, ND-IRIS (licensed) |
| Simplified engine | Eyelids and eyelashes poorly handled on real images | Open-IRIS, neural-network segmentation |
| Plaintext in memory during matching | Exposed if the server is compromised at runtime | Enclave (TEE), homomorphic encryption, match-on-card |
| Transform invertible if its secret leaks | Relies on separating the database from the keystore | HSM, fuzzy commitment |
| Truncation of the end of the log | Undetected without external anchoring | Timestamping, WORM |
| File-based keystore | Demo only | KMS / HSM |
| No built-in TLS | Must be provided by the infrastructure | Reverse proxy |
| 1:1 verification only | No 1:N identification | Indexing, search in the transformed domain |

No system offers absolute security: this prototype aims to **sharply reduce the impact of a database breach**.

---

## 19. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `IntegrityError: keystore illisible` at startup | `IRIS_MASTER_KEY` differs from the one that created the keystore | Restore the correct key, or delete `data/keystore.json`, `data/*.db` and `data/master.key` to start over |
| `401` in Swagger | Not authorized | **Authorize** button + demo key |
| `403` | Insufficient role | Use `admin-demo-key` |
| `422 image iris inexploitable` | Iris not found, image too dark or cropped | Use `data/demo/` or an image showing the whole eye |
| `423` | Subject locked (5 failures) | Wait 15 minutes, or lower `IRIS_LOCKOUT_MIN` |
| `409 ALERTE INTÉGRITÉ` | Template modified in the database (intended in the attack demo) | Reset (Attacks tab) or revoke then re-enroll |
| `ModuleNotFoundError: app` | Command run outside the repository root | `cd iris`, then use `python -m tools.…` |
| Port 8000 already in use | Another server is running | `uvicorn app.main:app --port 8001` |
| Blank Streamlit page after an update | Resource cache | ⋮ menu → *Clear cache*, or the Reset button |

---

## 20. References

- Daugman, J. (2004). *How iris recognition works*. IEEE Trans. Circuits and Systems for Video Technology, 14(1), 21–30.
- Masek, L. (2003). *Recognition of human iris patterns for biometric identification*. University of Western Australia.
- Ratha, N., Connell, J., Bolle, R. (2001). *Enhancing security and privacy in biometrics-based authentication systems*. IBM Systems Journal, 40(3).
- Hao, F., Anderson, R., Daugman, J. (2006). *Combining crypto with biometrics effectively*. IEEE Trans. Computers, 55(9).
- Juels, A., Sudan, M. (2006). *A fuzzy vault scheme*. Designs, Codes and Cryptography, 38(2).
- Venugopalan, S., Savvides, M. (2011). *How to generate spoofed irises from an iris code template*. IEEE TIFS, 6(2).
- Patel, V., Ratha, N., Chellappa, R. (2015). *Cancelable biometrics: a review*. IEEE Signal Processing Magazine, 32(5).
- ISO/IEC 24745:2022 — *Biometric information protection* · ISO/IEC 30107-1 — *Presentation attack detection*.
- NIST SP 800-38D (GCM) · NIST SP 800-57 Part 1 Rev. 5 (key management).
- Regulation (EU) 2016/679 (GDPR), Articles 9, 17, 25, 32 and 35.

---

*Project — Information Systems Security. The data used is entirely synthetic; no real biometric data is contained in this repository.*
