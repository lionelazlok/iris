# 👁️ Iris Secure DB — Sécurisation des bases de données biométriques à iris

> Projet académique : étude des menaces qui pèsent sur les bases de données biométriques à iris, conception d'une architecture de protection et **prototype fonctionnel** (API REST + interface web), mesuré et attaqué.

Le système enregistre et vérifie des personnes par l'iris **sans jamais conserver ni la photo de l'œil, ni son code lisible**. Ce qui est stocké est brouillé par une transformation révocable, puis chiffré en AES-256-GCM. Chaque accès est contrôlé par rôle et inscrit dans un journal d'audit infalsifiable.

| | |
|---|---|
| **Langage** | Python 3.10+ |
| **API** | FastAPI + Swagger (`/docs`) |
| **Interface web** | Streamlit (déployable gratuitement) |
| **Base de données** | SQLite (démo) / PostgreSQL (production) via SQLAlchemy |
| **Cryptographie** | AES-256-GCM, chiffrement d'enveloppe, HMAC-SHA256 (`cryptography`) |
| **Tests** | 30 tests `pytest`, dont 10 scénarios d'attaque |
| **Auteurs** | Koffi ADJOVI, Aïcha SOSSOU |

---

## Sommaire

1. [Résumé des résultats](#1-résumé-des-résultats)
2. [Contexte et objectifs](#2-contexte-et-objectifs)
3. [Fonctionnalités](#3-fonctionnalités)
4. [Architecture](#4-architecture)
5. [Mécanismes de sécurité en détail](#5-mécanismes-de-sécurité-en-détail)
6. [Moteur de reconnaissance de l'iris](#6-moteur-de-reconnaissance-de-liris)
7. [Arborescence du dépôt](#7-arborescence-du-dépôt)
8. [Installation](#8-installation)
9. [Configuration](#9-configuration-variables-denvironnement)
10. [Utilisation](#10-utilisation)
11. [Référence de l'API](#11-référence-de-lapi)
12. [Modèle de données](#12-modèle-de-données)
13. [Tests automatisés](#13-tests-automatisés)
14. [Évaluation expérimentale](#14-évaluation-expérimentale)
15. [Exécution en ligne](#15-exécution-en-ligne)
16. [Documents du projet et régénération](#16-documents-du-projet-et-régénération)
17. [Passage en production : liste de contrôle](#17-passage-en-production--liste-de-contrôle)
18. [Limites connues](#18-limites-connues)
19. [Dépannage](#19-dépannage)
20. [Références](#20-références)

---

## 1. Résumé des résultats

Les mesures portent sur 200 images synthétiques (50 personnes × 4 photos). Elles se régénèrent avec `python -m tools.benchmark`.

| Indicateur | Résultat | Interprétation |
|---|---|---|
| Imposteurs acceptés (FAR, seuil 0,34) | **0 / 2 450** | Aucune fausse acceptation |
| Vraies personnes refusées (FRR) | **1 / 300 (0,33 %)** | Une photo trop tournée |
| Indice de décidabilité d′ | **14,48** | Classes très bien séparées |
| Échecs d'enrôlement | 0 / 200 | Toutes les images sont exploitables |
| Rotation de l'œil tolérée | ≈ 12° | Compensée par ±8 décalages |
| Temps d'extraction (moyenne) | ≈ 23 ms | — |
| Vérification complète par l'API | ≈ 30 ms | Instantanée pour l'utilisateur |
| Chiffrement / déchiffrement | 6,6 µs / 4,4 µs | ≈ 0,02 % du temps de vérification |
| Surcoût de stockage | +88 octets par gabarit (+3,7 %) | Négligeable |
| Effet de la protection sur les scores | **0** | Précision strictement inchangée |
| Scénarios d'attaque | **10 / 10 bloqués ou détectés** | Voir [§13](#13-tests-automatisés) |

> ⚠️ **Images synthétiques** : les bases réelles (CASIA-Iris, UBIRIS, ND-IRIS) exigent une licence. Sur des photos réelles, les taux d'erreur seraient plus élevés. Les résultats valident le pipeline et la sécurité, pas une performance de terrain.

---

## 2. Contexte et objectifs

Un mot de passe volé se change ; **un iris volé, non**. Une base biométrique centralisée est donc une cible de grande valeur, et sa fuite est définitive (fuite OPM, États-Unis, 2015 : 5,6 millions d'empreintes ; Biostar 2, 2019 : plus d'un million d'empreintes non chiffrées). Le RGPD classe ces données comme sensibles (art. 9). La norme **ISO/IEC 24745** exige trois propriétés :

| Exigence | Signification | Réponse du prototype |
|---|---|---|
| Irréversibilité | Impossible de retrouver l'iris à partir de ce qui est stocké | Transformation, puis chiffrement |
| Non-liabilité | Impossible de relier une personne entre deux bases | Transformation propre à chaque sujet et à chaque version |
| Révocabilité | Annuler et réémettre une référence compromise | Version incrémentée, ré-enrôlement |
| *(+) Performance* | Ne pas dégrader la reconnaissance | Distance de Hamming préservée exactement |

**Objectifs** : (1) cadre théorique (biométrie, menaces, protections) ; (2) architecture sécurisée ; (3) prototype doté d'une API testable ; (4) mesures de performance, de coût et de résistance aux attaques.

---

## 3. Fonctionnalités

- **Enrôlement** d'une personne à partir d'une image d'œil (PNG, JPG, BMP).
- **Vérification 1:1** (« cette personne est-elle bien EMP-001 ? ») avec score, décision et temps de traitement.
- **Révocation** d'un gabarit compromis, puis **ré-enrôlement** avec une nouvelle transformation non reliable à l'ancienne.
- **Effacement définitif** (droit à l'effacement, RGPD art. 17).
- **Rotation des clés** de chiffrement sans ré-enrôlement des personnes.
- **Contrôle d'accès par rôles** : `operator`, `auditor`, `admin`.
- **Journal d'audit chaîné** avec vérification d'intégrité.
- **Verrouillage** après 5 échecs consécutifs (15 minutes).
- **Interface Streamlit** avec un onglet de **simulation d'attaques** sur la base.
- **Générateur d'iris synthétiques**, **banc de mesures**, **démonstration en 10 étapes**.

---

## 4. Architecture

![Architecture](docs/fig_architecture.png)

### Flux d'enrôlement

```
Image ──► validation (taille, format, résolution)
      ──► segmentation ─► normalisation 20×240 ─► IrisCode 9 600 bits + masque
      ──► transformation révocable T(sujet, version)          [jamais stocké en clair]
      ──► sérialisation ─► AES-256-GCM (DEK aléatoire, AAD = sujet|gabarit|KEK)
      ──► DEK enveloppée par la KEK active
      ──► INSERT templates (chiffré, nonces, DEK enveloppée, kek_id)
      ──► entrée d'audit chaînée                             [l'image n'est jamais écrite]
```

### Flux de vérification

```
Image sonde ─► IrisCode sonde
Base ─► déchiffrement (le tag GCM et l'AAD vérifient l'intégrité et le contexte)
        └─ échec ⇒ ALERTE INTÉGRITÉ (409) + audit
Pour chaque décalage s ∈ [-8, +8] : HD( stocké , T(décaler(sonde, s)) )
Décision : min HD ≤ 0,34 ⇒ accepté ; sinon compteur d'échecs (verrouillage à 5)
```

---

## 5. Mécanismes de sécurité en détail

### 5.1 Transformation révocable (biométrie annulable) — `app/template_codec.py`
- Graine = `HMAC-SHA256(secret, "cancelable|<sujet>|<version>")`.
- La graine détermine une **permutation P** des 9 600 positions et une **chaîne K** de 9 600 bits.
- Gabarit stocké : `T(c) = P(c) ⊕ K` ; le masque est permuté de la même manière.
- Propriété : `HD(T(a), T(b)) = HD(a, b)`. On compare donc **dans le domaine transformé**, sans perte de précision.
- Révocation : `version + 1` ⇒ nouvelle transformation ; entre deux versions du même œil, HD ≈ 0,5, donc aucun lien.
- **Limite** : inversible si le secret fuit en même temps que la base. Elle complète le chiffrement, elle ne le remplace pas.

### 5.2 Chiffrement authentifié AES-256-GCM, par enveloppe — `app/crypto_service.py`
| Élément | Valeur |
|---|---|
| Algorithme | AES-256-GCM (AEAD, NIST SP 800-38D) |
| Clé de données (DEK) | 256 bits aléatoires, **une par gabarit** |
| Nonce | 96 bits aléatoires (`os.urandom`), un par opération |
| Tag | 128 bits : toute modification d'un seul bit est détectée |
| AAD | `iris-template-v1|<sujet>|<id gabarit>|<kek_id>` : lie le chiffré à **sa** ligne |
| Enveloppe | DEK chiffrée par la KEK active (même AAD) |
| Coffre (keystore) | Fichier JSON entièrement chiffré en AES-GCM par la **clé maîtresse** |
| Clé maîtresse | `IRIS_MASTER_KEY` ; en production : KMS ou HSM |

**Rotation** (`POST /admin/rotate-keys`) : une nouvelle KEK `kek-vN` devient active et l'ancienne est retirée. Chaque gabarit est déchiffré en mémoire, puis rechiffré avec une DEK neuve sous la nouvelle KEK, sans ré-enrôlement.

### 5.3 Contrôle d'accès — `app/security.py`
- Clés d'API transmises dans l'en-tête `X-API-Key`, conservées sous forme d'**empreinte SHA-256** et comparées à **temps constant**.

| Permission | operator | auditor | admin |
|---|:-:|:-:|:-:|
| enroll, verify | ✅ | ❌ | ✅ |
| read_subject (métadonnées) | ✅ | ✅ | ✅ |
| read_audit | ❌ | ✅ | ✅ |
| rotate_keys, revoke, delete | ❌ | ❌ | ✅ |

### 5.4 Journal d'audit chaîné — `app/audit.py`
- `hash_i = HMAC-SHA256(k_audit, hash_{i-1} ‖ JSON(entrée_i))`, avec `hash_0 = 0…0`.
- `k_audit` est dérivée et **distincte** des clés de chiffrement.
- Sont journalisés : enrôlements, vérifications (avec le score), refus 401/403, alertes d'intégrité, rotations, révocations, effacements.
- `GET /audit/verify` recalcule la chaîne et détecte toute **modification** ou **suppression intermédiaire**, en indiquant l'entrée fautive.
- Le journal ne contient **aucune donnée biométrique**.

### 5.5 Autres protections
- **Anti-force brute** : 5 échecs ⇒ sujet verrouillé 15 minutes (réponse `423`).
- **Validation des entrées** : 5 Mo maximum, 4 mégapixels maximum, format vérifié par Pillow.
- **Minimisation** : aucune image stockée ; les sujets sont désignés par un pseudonyme (`external_ref`).
- **En-têtes HTTP** : `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
- **Clés étrangères SQLite** activées ; suppression en cascade des gabarits.

---

## 6. Moteur de reconnaissance de l'iris

Fichier `app/iris_engine.py` : réimplémentation pédagogique du pipeline décrit par Daugman (2004) et Masek (2003).

![Pipeline](docs/fig_pipeline.png)

| Étape | Méthode | Paramètres |
|---|---|---|
| Segmentation pupille | Seuillage, plus grande composante, puis opérateur intégro-différentiel | cercle complet, 64 angles |
| Segmentation limbe | Opérateur intégro-différentiel de Daugman sur arcs **latéraux** (évite les paupières), recherche du centre ±3 px | |
| Normalisation | « Rubber sheet » de Daugman, interpolation bilinéaire | **20 × 240** |
| Masque de bruit | Hors image + valeurs aberrantes (médiane ± 4,5·MAD) : paupière, reflets | |
| Encodage | Filtre **log-Gabor 1D** par ligne, phase sur 2 bits | λ = 18, σ/f = 0,5 |
| Gabarit | **9 600 bits** + masque | |
| Comparaison | Distance de Hamming fractionnaire masquée, minimum sur décalages | ±8 colonnes (≈ ±12°), seuil 0,34 |

Le moteur est isolé derrière `IrisEngine.extract(image) -> IrisTemplate`. Il peut être remplacé, par exemple par [Open-IRIS](https://github.com/worldcoin/open-iris), sans modifier la couche sécurité.

**Générateur synthétique** (`tools/synth_iris.py`) : chaque sujet possède une texture propre (60 composantes radiales et angulaires, 18 cryptes). Chaque photo fait varier le centre (±6 px), la dilatation (−10 % à +12 %), la rotation (±8°), l'éclairage, le flou, le bruit, la paupière et le reflet.

---

## 7. Arborescence du dépôt

```
.
├── app/                         # Application (cœur du projet)
│   ├── config.py                # Paramètres et variables d'environnement
│   ├── iris_engine.py           # Moteur iris : segmentation, normalisation, log-Gabor, Hamming
│   ├── template_codec.py        # Sérialisation binaire + transformation révocable
│   ├── crypto_service.py        # AES-256-GCM, enveloppe DEK/KEK, keystore, rotation
│   ├── models.py                # Tables : subjects, templates, audit_logs
│   ├── database.py              # Moteur SQLAlchemy, création des tables
│   ├── audit.py                 # Journal chaîné HMAC + vérification
│   ├── security.py              # Clés d'API, rôles et permissions
│   ├── service.py               # Logique métier : enrôler, vérifier, révoquer, effacer, rotation
│   └── main.py                  # API FastAPI (Swagger sur /docs)
├── streamlit_app.py             # Interface web Streamlit (7 onglets, dont la simulation d'attaques)
├── .streamlit/config.toml       # Thème et limite d'upload Streamlit
├── tools/
│   ├── synth_iris.py            # Générateur d'images d'iris synthétiques
│   ├── demo.py                  # Scénario de démonstration en 10 étapes
│   ├── benchmark.py             # Mesures : FAR/FRR/EER, rotation, coût crypto
│   ├── figures.py               # Schémas (architecture, pipeline, enveloppe)
│   ├── build_slides.py          # Génère la présentation PowerPoint
│   ├── build_report.py          # Génère le rapport technique complet (avec code)
│   └── build_report_light.py    # Génère le rapport de synthèse (sans code)
├── tests/
│   ├── conftest.py              # Configuration de test (base et coffre temporaires)
│   ├── test_engine.py           # Moteur iris (4 tests)
│   ├── test_crypto.py           # Cryptographie et transformation (10 tests)
│   └── test_api.py              # API, RBAC et attaques (16 tests)
├── data/demo/                   # Images prêtes à téléverser (Swagger / Streamlit)
├── docs/
│   ├── Presentation_Securisation_BD_Iris.pptx      # 23 diapositives + notes d'orateur
│   ├── Rapport_Securisation_BD_Iris.docx           # Rapport technique complet (code en annexe)
│   ├── Rapport_Synthese_Securisation_Iris.docx/.pdf # Rapport de synthèse, sans code, grand public
│   ├── results.json                                # Résultats bruts des mesures
│   ├── fig_*.png                                   # Figures
│   └── STREAMLIT_ABOUT.md                          # Texte de l'onglet « À propos »
├── Dockerfile                   # Image pour un hébergement en ligne (API ou Streamlit)
├── render.yaml                  # Déploiement en un clic sur Render
├── requirements.txt
├── pytest.ini
└── .gitignore                   # Exclut bases, coffres de clés et secrets
```

Fichiers créés à l'exécution (ignorés par Git) : `data/iris_secure.db`, `data/keystore.json`, `data/master.key`, et leurs équivalents `data/streamlit*`.

---

## 8. Installation

**Prérequis** : Python **3.10 ou plus récent**, `pip` et Git. Aucune base de données à installer : SQLite est intégré.

```bash
git clone https://github.com/lionelazlok/iris.git
cd iris

# Environnement virtuel
python -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows (PowerShell ou cmd)

pip install -r requirements.txt
```

Vérification rapide :

```bash
pytest -q          # attendu : 30 passed
```

---

## 9. Configuration (variables d'environnement)

Toutes sont facultatives en démonstration.

| Variable | Défaut | Rôle |
|---|---|---|
| `IRIS_MASTER_KEY` | *(absente : clé de démo générée dans `data/master.key`)* | Clé maîtresse, 32 octets en base64. **Obligatoire en production.** |
| `IRIS_API_KEYS` | `admin-demo-key:admin,operator-demo-key:operator,auditor-demo-key:auditor` | Clés d'API et leurs rôles |
| `IRIS_DB_URL` | `sqlite:///./data/iris_secure.db` | URL SQLAlchemy (ex. `postgresql+psycopg://user:mdp@hote/iris`) |
| `IRIS_KEYSTORE` | `./data/keystore.json` | Emplacement du coffre de clés chiffré |
| `IRIS_MATCH_THRESHOLD` | `0.34` | Seuil de décision (distance de Hamming) |
| `IRIS_MAX_FAILED` | `5` | Échecs avant verrouillage |
| `IRIS_LOCKOUT_MIN` | `15` | Durée du verrouillage (minutes) |

Générer une clé maîtresse :

```bash
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
export IRIS_MASTER_KEY="<valeur>"        # Windows PowerShell : $env:IRIS_MASTER_KEY="<valeur>"
```

> La clé maîtresse doit rester **la même** d'un lancement à l'autre : sans elle, le coffre et donc toute la base sont illisibles. C'est le comportement attendu.

---

## 10. Utilisation

### 10.1 API + Swagger (interface de test intégrée)

```bash
uvicorn app.main:app --reload
```

1. Ouvrir **http://127.0.0.1:8000/docs**.
2. Cliquer sur **Authorize** et saisir `operator-demo-key`.
3. `POST /enroll` → *Try it out* → `external_ref = ALICE`, image = `data/demo/alice_enrolement.png` → *Execute*.
4. `POST /verify` → `ALICE` + `data/demo/alice_verification.png` ⇒ `"match": true`.
5. `POST /verify` → `ALICE` + `data/demo/imposteur.png` ⇒ `"match": false`.
6. *Authorize* avec `admin-demo-key` → `POST /admin/rotate-keys`, `POST /subjects/ALICE/revoke`…
7. *Authorize* avec `auditor-demo-key` → `GET /audit`, puis `GET /audit/verify`.

Clés de démonstration :

| Clé | Rôle |
|---|---|
| `operator-demo-key` | operator |
| `auditor-demo-key` | auditor |
| `admin-demo-key` | admin |

### 10.2 En ligne de commande (curl)

```bash
H="X-API-Key: operator-demo-key"
curl -X POST localhost:8000/enroll -H "$H" -F external_ref=ALICE -F image=@data/demo/alice_enrolement.png
curl -X POST localhost:8000/verify -H "$H" -F external_ref=ALICE -F image=@data/demo/alice_verification.png
curl localhost:8000/subjects/ALICE -H "$H"
curl -X POST localhost:8000/admin/rotate-keys -H "X-API-Key: admin-demo-key"
curl localhost:8000/audit/verify -H "X-API-Key: auditor-demo-key"
```

### 10.3 Interface web Streamlit

```bash
streamlit run streamlit_app.py          # → http://localhost:8501
```

| Onglet | Contenu |
|---|---|
| ① Enrôlement | Pseudonyme + iris synthétique (n° de personne, n° de photo) ou fichier téléversé |
| ② Vérification | Décision, distance de Hamming, temps, jauge par rapport au seuil |
| ③ Base de données | Contenu **brut** des tables, vu comme par un attaquant : uniquement du chiffré |
| ④ Administration | Rotation des clés, révocation, ré-enrôlement, effacement |
| ⑤ Audit | Journal complet + état de la chaîne (intègre ou rompue) |
| ⑥ Attaques | Altérer un gabarit, substituer un gabarit, falsifier le journal, réinitialiser |
| ℹ️ À propos | Explications et résultats bruts |

Le rôle se choisit dans la barre latérale. **Même personne + autre photo** ⇒ accepté ; **autre personne** ⇒ refusé.

### 10.4 Démonstration automatique en 10 étapes

```bash
python -m tools.demo                               # en mémoire, base temporaire
python -m tools.demo --url http://127.0.0.1:8000   # contre un serveur lancé
```

1. Enrôlement d'Alice et de Bob
2. Métadonnées : seul un chiffré illisible existe en base
3. Vérification authentique ⇒ acceptée (HD ≈ 0,16)
4. Imposteur ⇒ rejeté (HD ≈ 0,48)
5. Sans clé ⇒ 401 ; mauvais rôle ⇒ 403
6. Rotation de la KEK ; la vérification fonctionne toujours
7. **Attaque** : gabarit de Bob copié chez Alice ⇒ **ALERTE INTÉGRITÉ (409)**
8. Révocation ⇒ refus (403) ⇒ ré-enrôlement en version 2 ⇒ accepté
9. Effacement de Bob
10. Journal d'audit, puis **falsification détectée** à l'entrée exacte

### 10.5 Générer des images

```bash
python -m tools.synth_iris --subjects 20 --sessions 4 --out data/synthetic
```

---

## 11. Référence de l'API

Toutes les routes, sauf `/health`, exigent l'en-tête `X-API-Key`.

| Méthode | Route | Permission | Entrée | Sortie |
|---|---|---|---|---|
| GET | `/health` | — | — | `{"status":"ok"}` |
| POST | `/enroll` | enroll | form : `external_ref` (1–128 car.), `image` (fichier) | `subject_id`, `template_id`, `kek_id`, `quality`, `algorithm`, `cancelable_version` |
| POST | `/verify` | verify | form : `external_ref`, `image` | `match`, `hamming_distance`, `threshold`, `decision_ms` |
| GET | `/subjects/{ref}` | read_subject | — | statut, version, liste des gabarits (taille du chiffré, KEK, qualité), **jamais le gabarit** |
| POST | `/subjects/{ref}/revoke` | revoke | — | `status: revoked`, `next_cancelable_version` |
| POST | `/subjects/{ref}/reenroll` | revoke | form : `image` | `status: active`, `cancelable_version` |
| DELETE | `/subjects/{ref}` | delete | — | `deleted: true` |
| POST | `/admin/rotate-keys` | rotate_keys | — | `old_kek`, `new_kek`, `templates_rewrapped`, `integrity_errors` |
| GET | `/admin/keys` | rotate_keys | — | liste des KEK (identifiant, date, statut), **sans leur valeur** |
| GET | `/audit?limit=50` | read_audit | — | dernières entrées (500 au maximum) |
| GET | `/audit/verify` | read_audit | — | `valid`, `checked`, `broken_at`, `reason` |

**Codes de réponse**

| Code | Signification |
|---|---|
| 200 | Succès (y compris une vérification négative : `match: false`) |
| 400 | Fichier image invalide |
| 401 | Clé d'API absente ou invalide |
| 403 | Rôle insuffisant, ou gabarit révoqué |
| 404 | Sujet inconnu |
| 409 | Sujet déjà enrôlé, ou **alerte d'intégrité** (gabarit altéré ou substitué) |
| 413 | Image trop volumineuse (> 5 Mo ou > 4 Mpx) |
| 422 | Image inexploitable (iris non trouvé, qualité insuffisante) ou paramètre manquant |
| 423 | Sujet verrouillé après trop d'échecs |

---

## 12. Modèle de données

**`subjects`** — personnes pseudonymisées

| Colonne | Type | Description |
|---|---|---|
| id | UUID | Identifiant interne (utilisé dans l'AAD) |
| external_ref | texte, unique | Pseudonyme fourni par l'application métier |
| status | texte | `active`, `revoked` |
| cancel_version | entier | Version de la transformation révocable |
| failed_attempts, locked_until | entier, date | Anti-force brute |
| created_at | date | |

**`templates`** — gabarits **chiffrés uniquement**

| Colonne | Description |
|---|---|
| id, subject_id | Identifiants (liés par l'AAD) |
| ciphertext | Gabarit transformé, chiffré AES-256-GCM, tag inclus |
| nonce | Nonce de 96 bits |
| wrapped_dek, dek_nonce | DEK chiffrée par la KEK |
| kek_id | Version de la KEK (`kek-v1`, `kek-v2`…) |
| algorithm, quality, created_at | Métadonnées |

**`audit_logs`** — journal append-only : `id`, `ts`, `actor`, `role`, `action`, `subject_ref`, `outcome`, `details` (JSON), `prev_hash`, `hash`.

Il n'existe **aucune colonne image** et **aucun IrisCode en clair**.

---

## 13. Tests automatisés

```bash
pytest -q        # 30 tests, environ 6 secondes
```

| Fichier | Test | Vérifie |
|---|---|---|
| test_engine | `test_same_eye_matches_despite_rotation` | Même œil tourné de 9° ⇒ accepté, rotation compensée |
| | `test_different_eyes_do_not_match` | Yeux différents ⇒ HD > 0,40 |
| | `test_template_shape_and_quality` | Gabarit 20×240×2, qualité > 80 % |
| | `test_blank_image_rejected` | Image vide refusée |
| test_crypto | `test_serialize_roundtrip` | Sérialisation sans perte |
| | `test_encrypt_decrypt_roundtrip` | Chiffrement réversible, clair absent du chiffré |
| | `test_nonces_and_ciphertexts_unique` | Nonce et chiffré différents à chaque fois |
| | `test_bitflip_detected` | 1 bit modifié ⇒ refus |
| | `test_swap_to_other_subject_detected` | Chiffré déplacé vers un autre sujet ⇒ refus (AAD) |
| | `test_wrong_master_key_rejected` | Mauvaise clé maîtresse ⇒ coffre illisible |
| | `test_keystore_file_has_no_plain_keys` | Aucune clé en clair dans le coffre |
| | `test_rotation_rewrap` | Rotation ⇒ `kek-v2`, données intactes |
| | `test_cancelable_preserves_distance_and_hides_code` | HD préservée, code brut masqué |
| | `test_revoked_version_unlinkable` | Versions v1 et v2 non reliables (HD > 0,45) |
| test_api | `test_enroll_and_verify_genuine` | Parcours nominal |
| | `test_impostor_rejected` | Imposteur refusé |
| | `test_duplicate_enrollment_refused` | Double enrôlement ⇒ 409 |
| | `test_no_api_key` | Sans clé ⇒ 401 |
| | `test_rbac` | Matrice des rôles (403) |
| | `test_invalid_image` | Fichier invalide ⇒ 400 |
| | `test_db_contains_no_plain_template` | **Attaque** : lecture de la base ⇒ rien d'exploitable |
| | `test_tampered_db_raises_integrity_alert` | **Attaque** : altération ⇒ 409 + audit |
| | `test_template_substitution_attack` | **Attaque** : substitution ⇒ 409 |
| | `test_lockout_after_failures` | **Attaque** : force brute ⇒ 423 |
| | `test_rotation_keeps_verification_working` | Rotation transparente |
| | `test_revoke_and_reenroll` | Révocation puis ré-enrôlement |
| | `test_delete_rgpd` | Effacement complet |
| | `test_audit_chain_detects_tampering` | **Attaque** : journal modifié ⇒ détecté |
| | `test_audit_chain_detects_deletion` | **Attaque** : entrée supprimée ⇒ détecté |
| | `test_unauthenticated_access_logged` | Tentatives anonymes journalisées |

---

## 14. Évaluation expérimentale

```bash
python -m tools.benchmark --subjects 50 --sessions 4    # environ 1 minute
```

Produit `docs/results.json`, `docs/fig_distributions.png` et `docs/fig_rotation.png`.

**Protocole** : 300 comparaisons authentiques (toutes les paires de photos d'un même sujet) et 2 450 comparaisons d'imposteurs. Le seuil est balayé de 0 à 0,6. Les temps sont mesurés sur 2 000 itérations.

![Distributions](docs/fig_distributions.png)

| Seuil | FAR | FRR |
|---|---|---|
| 0,30 | 0 % | 0,67 % |
| 0,32 | 0 % | 0,67 % |
| **0,34** | **0 %** | **0,33 %** |
| 0,36 | 0 % | 0,33 % |
| 0,40 | 0 % | 0 % |

| Rotation | 0° | 4° | 8° | 12° | 16° | 20° |
|---|---|---|---|---|---|---|
| HD moyenne | 0,138 | 0,138 | 0,171 | 0,316 | 0,367 | 0,401 |

---

## 15. Exécution en ligne

### Option A — Streamlit Community Cloud (gratuit, recommandé pour la démo)
1. Aller sur **https://share.streamlit.io** et se connecter avec GitHub.
2. **Create app** → *Deploy a public app from GitHub*.
3. Repository : `lionelazlok/iris` · Branch : `main` · Main file path : `streamlit_app.py`.
4. *Advanced settings* → Python 3.12 → **Secrets** :
   ```toml
   IRIS_MASTER_KEY = "<clé base64 de 32 octets>"
   ```
5. **Deploy**. L'URL est du type `https://<nom>.streamlit.app`.

> Le stockage de l'hébergement gratuit est **éphémère** : la base repart à zéro à chaque redémarrage de l'application. C'est sans gravité pour une démonstration.

### Option B — API FastAPI sur Render (gratuit)
1. **https://render.com** → *New* → *Blueprint* → choisir le dépôt (le fichier `render.yaml` est détecté).
2. Renseigner `IRIS_MASTER_KEY` et `IRIS_API_KEYS` (**ne pas réutiliser les clés de démonstration en public**).
3. Swagger est alors disponible sur `https://<service>.onrender.com/docs`.

### Option C — Hugging Face Spaces (Docker)
Créer un Space de type **Docker**, y pousser le dépôt et définir les variables `PORT=7860` et `MODE=streamlit` (interface web) ou laisser `MODE` vide (API). Ajouter `IRIS_MASTER_KEY` dans *Settings → Secrets*.

### Option D — Docker, partout
```bash
docker build -t iris-secure .
docker run -p 8000:8000 -e IRIS_MASTER_KEY=<clé> iris-secure                              # API
docker run -p 8501:8501 -e PORT=8501 -e MODE=streamlit -e IRIS_MASTER_KEY=<clé> iris-secure  # Streamlit
```

### Option E — GitHub Codespaces (sans rien installer)
Sur la page du dépôt : **Code → Codespaces → Create codespace**, puis dans le terminal :
`pip install -r requirements.txt && streamlit run streamlit_app.py`. Le port est ouvert automatiquement dans le navigateur.

---

## 16. Documents du projet et régénération

| Document | Contenu | Régénérer |
|---|---|---|
| `docs/Presentation_Securisation_BD_Iris.pptx` | 23 diapositives modifiables, notes d'orateur | `python -m tools.build_slides` |
| `docs/Rapport_Securisation_BD_Iris.docx` | Rapport technique complet, code en annexe | `python -m tools.build_report` |
| `docs/Rapport_Synthese_Securisation_Iris.docx` / `.pdf` | Rapport court, sans code, accessible | `python -m tools.build_report_light` |
| `docs/fig_architecture.png`, `fig_pipeline.png`, `fig_envelope.png` | Schémas | `python -m tools.figures` |
| `docs/results.json`, `fig_distributions.png`, `fig_rotation.png` | Mesures | `python -m tools.benchmark` |

Ordre conseillé après une modification : `benchmark` → `figures` → `build_slides` → `build_report` → `build_report_light`. Les présentations et rapports lisent `docs/results.json` : les chiffres restent cohérents. Dans Word, faire un clic droit sur le sommaire puis « Mettre à jour les champs ».

---

## 17. Passage en production : liste de contrôle

- [ ] Clé maîtresse dans un **KMS ou HSM** (AWS KMS, Azure Key Vault, HashiCorp Vault), jamais dans un fichier.
- [ ] **TLS** obligatoire (proxy inverse Nginx ou Caddy, ou hébergeur), TLS mutuel entre services.
- [ ] Clés d'API fortes et uniques par client, ou authentification OAuth2/OIDC.
- [ ] **PostgreSQL** avec chiffrement du disque et sauvegardes chiffrées.
- [ ] Ancrage externe de la tête du journal d'audit (horodatage qualifié, stockage WORM).
- [ ] Rotation périodique des KEK et procédure de réponse à incident.
- [ ] Détection d'attaque de présentation (faux iris, ISO/IEC 30107).
- [ ] Moteur évalué sur des **données réelles** et seuil recalibré.
- [ ] Analyse d'impact (AIPD, RGPD art. 35) et base légale (art. 9).
- [ ] Limitation de débit globale (rate limiting) et supervision.

---

## 18. Limites connues

| Limite | Conséquence | Piste |
|---|---|---|
| Images synthétiques | FAR et FRR optimistes | CASIA-Iris, ND-IRIS (sous licence) |
| Moteur simplifié | Paupières et cils mal gérés sur images réelles | Open-IRIS, segmentation par réseau de neurones |
| Clair en mémoire pendant la comparaison | Exposé si le serveur est compromis en cours d'exécution | Enclave (TEE), chiffrement homomorphe, match-on-card |
| Transformation inversible si son secret fuit | Repose sur la séparation base / coffre | HSM, fuzzy commitment |
| Troncature de la fin du journal | Non détectée sans ancrage externe | Horodatage, WORM |
| Coffre de clés sous forme de fichier | Démonstration uniquement | KMS / HSM |
| Pas de TLS intégré | À fournir par l'infrastructure | Proxy inverse |
| Vérification 1:1 uniquement | Pas d'identification 1:N | Indexation, recherche dans le domaine transformé |

Aucun système n'offre une sécurité absolue : ce prototype vise à **réduire fortement l'impact d'une fuite de la base**.

---

## 19. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `IntegrityError: keystore illisible` au démarrage | `IRIS_MASTER_KEY` différente de celle qui a créé le coffre | Remettre la bonne clé, ou supprimer `data/keystore.json`, `data/*.db` et `data/master.key` pour repartir de zéro |
| `401` dans Swagger | Pas d'autorisation | Bouton **Authorize** + clé de démonstration |
| `403` | Rôle insuffisant | Utiliser `admin-demo-key` |
| `422 image iris inexploitable` | Iris introuvable, image trop sombre ou recadrée | Utiliser `data/demo/` ou une image où l'œil entier est visible |
| `423` | Sujet verrouillé (5 échecs) | Attendre 15 minutes, ou réduire `IRIS_LOCKOUT_MIN` |
| `409 ALERTE INTÉGRITÉ` | Gabarit modifié en base (voulu dans la démo d'attaque) | Réinitialiser (onglet Attaques) ou révoquer puis ré-enrôler |
| `ModuleNotFoundError: app` | Commande lancée hors de la racine du dépôt | `cd iris`, puis utiliser `python -m tools.…` |
| Port 8000 déjà pris | Autre serveur actif | `uvicorn app.main:app --port 8001` |
| Streamlit vide après une mise à jour | Cache de ressources | Menu ⋮ → *Clear cache*, ou bouton Réinitialiser |

---

## 20. Références

- Daugman, J. (2004). *How iris recognition works*. IEEE Trans. Circuits and Systems for Video Technology, 14(1), 21–30.
- Masek, L. (2003). *Recognition of human iris patterns for biometric identification*. University of Western Australia.
- Ratha, N., Connell, J., Bolle, R. (2001). *Enhancing security and privacy in biometrics-based authentication systems*. IBM Systems Journal, 40(3).
- Hao, F., Anderson, R., Daugman, J. (2006). *Combining crypto with biometrics effectively*. IEEE Trans. Computers, 55(9).
- Juels, A., Sudan, M. (2006). *A fuzzy vault scheme*. Designs, Codes and Cryptography, 38(2).
- Venugopalan, S., Savvides, M. (2011). *How to generate spoofed irises from an iris code template*. IEEE TIFS, 6(2).
- Patel, V., Ratha, N., Chellappa, R. (2015). *Cancelable biometrics: a review*. IEEE Signal Processing Magazine, 32(5).
- ISO/IEC 24745:2022 — *Biometric information protection* · ISO/IEC 30107-1 — *Presentation attack detection*.
- NIST SP 800-38D (GCM) · NIST SP 800-57 Part 1 Rev. 5 (gestion des clés).
- Règlement (UE) 2016/679 (RGPD), articles 9, 17, 25, 32 et 35.

---

*Projet académique — Sécurité des systèmes d'information, novembre 2026. Les données utilisées sont entièrement synthétiques ; aucune donnée biométrique réelle n'est contenue dans ce dépôt.*
