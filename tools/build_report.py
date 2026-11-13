"""Génère docs/Rapport_Securisation_BD_Iris.docx (rapport + code en annexe)."""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
R = json.loads((DOCS / "results.json").read_text())
M, SC, X = R["matching"], R["security_cost"], R["extraction"]
NAVY = RGBColor(0x1d, 0x35, 0x57)
AUTHORS = ["Koffi ADJOVI", "Aïcha SOSSOU"]


def fr(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


def pct(x):
    return f"{x * 100:.2f} %".replace(".", ",")


doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21)
sec.left_margin = sec.right_margin = Cm(2.5)
sec.top_margin = sec.bottom_margin = Cm(2.2)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(6); st.paragraph_format.line_spacing = 1.15
for lvl, size in ((1, 16), (2, 13), (3, 11.5)):
    h = doc.styles[f"Heading {lvl}"]; h.font.name = "Calibri"; h.font.size = Pt(size); h.font.color.rgb = NAVY
    h.font.bold = True


def P(text, bold=False, italic=False, align=None, size=None, after=None):
    p = doc.add_paragraph()
    parts = text.split("**")
    for i, part in enumerate(parts):
        r = p.add_run(part); r.bold = bold or i % 2 == 1; r.italic = italic
        if size:
            r.font.size = Pt(size)
    if align is not None:
        p.alignment = align
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def B(items, style="List Bullet"):
    for it in items:
        p = doc.add_paragraph(style=style)
        for i, part in enumerate(it.split("**")):
            r = p.add_run(part); r.bold = i % 2 == 1


def H(t, l=1):
    return doc.add_heading(t, l)


def fig(path, caption, width=15.5):
    doc.add_picture(str(path), width=Cm(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = P(caption, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=9.5)


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr(); s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), color); tcPr.append(s)


def T(rows, widths=None, caption=None, size=9.5):
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if widths:
        for j, wd in enumerate(widths):
            t.columns[j].width = Cm(wd)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.text = ""
            r = c.paragraphs[0].add_run(str(v)); r.font.size = Pt(size); r.bold = i == 0
            if i == 0:
                r.font.color.rgb = RGBColor(0xff, 0xff, 0xff); shade(c, "1D3557")
            elif i % 2 == 0:
                shade(c, "F1F5F9")
            if widths:
                c.width = Cm(widths[j])
    if caption:
        P(caption, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=9.5)
    else:
        doc.add_paragraph()
    return t


def toc():
    p = doc.add_paragraph(); r = p.add_run()
    for tag, txt in (("begin", None), (None, 'TOC \\o "1-2" \\h \\z \\u'), ("separate", None), ("t", "Clic droit → « Mettre à jour les champs » pour afficher le sommaire."), ("end", None)):
        if tag in ("begin", "separate", "end"):
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tag); r._r.append(e)
        elif tag == "t":
            e = OxmlElement("w:t"); e.text = txt; r._r.append(e)
        else:
            e = OxmlElement("w:instrText"); e.set(qn("xml:space"), "preserve"); e.text = txt; r._r.append(e)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def footer_page_numbers():
    p = sec.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), tag)
        else:
            e = OxmlElement("w:instrText"); e.text = txt
        r._r.append(e)


footer_page_numbers()

# ------------------------------------------------------------------ Page de garde
for _ in range(3):
    doc.add_paragraph()
P("SÉCURITÉ DES SYSTÈMES D'INFORMATION — PROJET DE GROUPE", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=11)
doc.add_paragraph()
p = P("Sécurisation des bases de données biométriques à iris", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=24)
for r in p.runs:
    r.font.color.rgb = NAVY
P("Menaces, mécanismes de protection et prototype d'API sécurisée", italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=14)
for _ in range(4):
    doc.add_paragraph()
P("Réalisé par", align=WD_ALIGN_PARAGRAPH.CENTER, size=11)
for a in AUTHORS:
    P(a, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=14, after=2)
for _ in range(6):
    doc.add_paragraph()
P("Année académique 2026–2027 · Novembre 2026", align=WD_ALIGN_PARAGRAPH.CENTER, size=11)
page_break()

# ------------------------------------------------------------------ Résumé
H("Résumé")
P("Les systèmes de reconnaissance par l'iris stockent des gabarits biométriques dont la compromission est définitive : "
  "contrairement à un mot de passe, un iris ne se change pas. Ce travail étudie les menaces qui pèsent sur les bases de "
  "données biométriques à iris et propose une architecture de défense en profondeur, mise en œuvre dans un prototype. "
  "Les IrisCodes, extraits par un pipeline de type Daugman/Masek, sont rendus révocables par une transformation secrète "
  "(permutation et XOR) qui préserve la distance de Hamming, puis chiffrés en AES-256-GCM selon un schéma d'enveloppe "
  "(une clé de données par gabarit, protégée par une clé de chiffrement de clés versionnée). Les données associées "
  "authentifiées lient chaque chiffré à sa ligne, ce qui neutralise les attaques par substitution. Un contrôle d'accès par "
  "rôles, un verrouillage contre la force brute et un journal d'audit chaîné par HMAC complètent le dispositif. "
  f"Sur un jeu de {R['dataset']['subjects'] * R['dataset']['sessions']} images synthétiques, le système obtient un FAR nul et un FRR de "
  f"{pct(M['at_threshold']['0.34']['FRR'])} au seuil 0,34 ; la protection ne modifie aucun score et le chiffrement ne représente "
  f"qu'environ {fr(SC['crypto_share_of_verification_pct'], 3)} % du temps de vérification. Les 30 tests automatisés, dont neuf "
  "scénarios d'attaque, sont réussis. Les limites, en particulier l'usage de données synthétiques, sont discutées.")
P("**Mots-clés** : biométrie, iris, IrisCode, protection des gabarits, biométrie révocable, AES-GCM, gestion des clés, "
  "ISO/IEC 24745, RGPD.")
H("Abstract", 2)
P("Iris recognition systems store biometric templates whose compromise is permanent. We analyse the threats against iris "
  "template databases and implement a defence-in-depth prototype: Daugman/Masek-style IrisCodes are protected by a "
  "distance-preserving cancelable transform, then encrypted with AES-256-GCM using envelope encryption and context-binding "
  "associated data, with role-based access control, brute-force lockout and an HMAC-chained audit log. On synthetic data, "
  "protection has no effect on matching accuracy and negligible computational cost; all attack scenarios are detected or blocked.",
  italic=True)
page_break()
H("Sommaire")
toc()
page_break()

# ------------------------------------------------------------------ 1. Introduction
H("1. Introduction")
P("La biométrie s'est imposée dans l'identité nationale, le contrôle aux frontières, la banque et le contrôle d'accès. "
  "Le programme indien Aadhaar a ainsi enrôlé plus de 1,3 milliard de personnes avec leurs iris et leurs empreintes. "
  "Cette généralisation s'accompagne de fuites majeures : en 2015, l'Office of Personnel Management américain s'est fait "
  "dérober 5,6 millions d'empreintes digitales ; en 2019, la base du système de contrôle d'accès Biostar 2 a été retrouvée "
  "exposée, avec plus d'un million d'empreintes non chiffrées.")
P("Une base biométrique centralisée présente un risque particulier : les données qu'elle contient sont uniques, "
  "permanentes et réutilisables d'un système à l'autre. Un mot de passe divulgué se remplace ; un iris divulgué, non. "
  "**Problématique** : comment stocker et comparer des gabarits d'iris de sorte que la fuite de la base ne compromette "
  "pas définitivement les personnes enrôlées, sans dégrader la performance de reconnaissance ?")
P("**Objectifs** : (1) dresser le cadre théorique : biométrie de l'iris, menaces et techniques de protection ; "
  "(2) proposer une architecture sécurisée conforme aux exigences de l'ISO/IEC 24745 ; (3) l'implémenter dans un "
  "prototype doté d'une API testable ; (4) en mesurer la performance, le coût et l'efficacité face à des attaques concrètes.")
P("Le rapport présente l'état de l'art (section 2), l'architecture proposée (3), l'implémentation (4), la méthodologie et "
  "les résultats (5), puis discute des limites (6) avant de conclure (7). Le code source figure en annexe.")

# ------------------------------------------------------------------ 2. État de l'art
H("2. État de l'art")
H("2.1 Principes de la biométrie", 2)
P("Un système biométrique opère soit en **vérification** (1:1, « suis-je bien la personne que je prétends être ? »), soit en "
  "**identification** (1:N, « qui suis-je ? »). Dans les deux cas, l'échantillon capturé est transformé en un **gabarit** "
  "(template), représentation compacte qui est stockée puis comparée. Les erreurs se mesurent par le taux de fausse "
  "acceptation (FAR) et le taux de faux rejet (FRR), arbitrés par un seuil de décision ; le taux d'égale erreur (EER) "
  "résume ce compromis. Jain et al. retiennent sept critères pour une modalité : universalité, unicité, permanence, "
  "mesurabilité, performance, acceptabilité et résistance au contournement.")
H("2.2 Reconnaissance par l'iris", 2)
P("La texture de l'iris (cryptes, sillons, collerette) se forme de manière largement aléatoire pendant le développement "
  "embryonnaire : les deux yeux d'une même personne, comme ceux de vrais jumeaux, diffèrent. Daugman estime à environ 249 "
  "le nombre de degrés de liberté statistiques d'un IrisCode, ce qui explique les très faibles taux de fausse acceptation. "
  "La chaîne de traitement classique, décrite par Daugman (2004) et rendue accessible par l'implémentation de Masek (2003), "
  "comporte quatre étapes (figure 1).")
fig(DOCS / "fig_pipeline.png", "Figure 1 — Chaîne de traitement implémentée, de l'image au gabarit stocké.", 16)
B(["**Segmentation** : l'opérateur intégro-différentiel de Daugman recherche le cercle (x₀, y₀, r) qui maximise la dérivée "
   "radiale lissée de l'intensité moyenne le long du contour : max | G_σ(r) ∗ ∂/∂r ∮ I(x,y)/(2πr) ds |. On localise "
   "ainsi la frontière pupillaire puis le limbe.",
   "**Normalisation** (« rubber sheet ») : l'anneau irien est projeté sur un rectangle de dimensions fixes (ici 20 × 240), "
   "ce qui compense la dilatation pupillaire et la distance de capture.",
   "**Encodage** : chaque ligne est filtrée par un filtre log-Gabor 1D ; la phase de la réponse complexe est quantifiée sur "
   "deux bits. On obtient un IrisCode de 9 600 bits accompagné d'un masque des bits non fiables (paupières, reflets).",
   "**Comparaison** : distance de Hamming fractionnaire masquée, HD = ‖(A ⊕ B) ∩ mA ∩ mB‖ / ‖mA ∩ mB‖, minimisée sur "
   "plusieurs décalages circulaires pour compenser la rotation de l'œil. Deux iris différents donnent HD ≈ 0,5."])
H("2.3 Sensibilité des données et cadre réglementaire", 2)
P("Le RGPD classe les données biométriques utilisées pour identifier une personne parmi les catégories particulières "
  "(art. 9), impose la protection des données dès la conception (art. 25), des mesures de sécurité adaptées telles que le "
  "chiffrement et la pseudonymisation (art. 32), le droit à l'effacement (art. 17) et une analyse d'impact (art. 35). "
  "La norme ISO/IEC 24745 précise les exigences propres aux références biométriques protégées : **irréversibilité**, "
  "**non-liabilité** (impossibilité de relier deux références d'une même personne issues de systèmes différents) et "
  "**révocabilité**. Les législations nationales de protection des données reprennent des principes équivalents.")
H("2.4 Menaces", 2)
P("Ratha, Connell et Bolle (2001) identifient huit points d'attaque dans un système biométrique : le capteur (présentation "
  "d'un faux iris), le canal capteur–extraction (rejeu), le module d'extraction, le canal extraction–comparateur, le "
  "comparateur, **la base de gabarits**, **le canal base–comparateur** et la décision. Ce travail se concentre sur la base et "
  "son canal. Les attaques correspondantes sont :")
T([["Attaque", "Description", "Conséquence"],
   ["Vol de la base", "Copie du fichier, dump SQL, sauvegarde non chiffrée", "Exposition de tous les gabarits"],
   ["Inversion du gabarit", "Reconstruction d'une image d'iris à partir de l'IrisCode (Venugopalan & Savvides, 2011)", "Usurpation sur d'autres systèmes"],
   ["Substitution", "Remplacement du gabarit de la victime par celui de l'attaquant", "Accès frauduleux au nom de la victime"],
   ["Liaison inter-bases", "Rapprochement des gabarits d'une même personne entre systèmes", "Profilage, atteinte à la vie privée"],
   ["Menace interne", "Administrateur ou DBA disposant de droits excessifs", "Fuite ou altération non détectée"],
   ["Effacement des traces", "Modification du journal après intrusion", "Impossibilité d'enquêter"]],
  [3.3, 7.7, 5], "Tableau 1 — Attaques visant la base de gabarits.")
H("2.5 Techniques de protection", 2)
P("La littérature distingue plusieurs familles de techniques, souvent combinées :")
T([["Technique", "Principe", "Forces", "Limites"],
   ["Chiffrement classique", "AES-GCM au repos", "Standard, rapide, intégrité", "Gabarit en clair lors de la comparaison"],
   ["Biométrie révocable (Ratha 2001 ; Patel et al. 2015)", "Transformation secrète répétable, comparaison dans le domaine transformé", "Révocable, non liable", "Inversible si le paramètre fuit"],
   ["Cryptosystèmes biométriques : fuzzy commitment (Hao, Anderson, Daugman 2006), fuzzy vault (Juels & Sudan)", "Liaison d'une clé au gabarit par code correcteur", "Aucun gabarit stocké", "Perte de précision, fuites statistiques"],
   ["Chiffrement homomorphe", "Calcul de la distance sur données chiffrées", "Aucun clair côté serveur", "Coût élevé"],
   ["Match-on-card, TEE", "Comparaison dans un composant sécurisé", "Gabarit jamais exposé", "Matériel dédié"]],
  [4.2, 4.3, 3.5, 4], "Tableau 2 — Familles de techniques de protection.")
P("Nous retenons la combinaison d'une transformation révocable et d'un chiffrement authentifié, complétée par une gestion "
  "rigoureuse des clés, un contrôle d'accès et un audit. C'est la solution la plus réaliste à mettre en œuvre et elle "
  "couvre les trois exigences de l'ISO/IEC 24745 sans dégrader la précision.")

# ------------------------------------------------------------------ 3. Architecture
H("3. Architecture proposée")
fig(DOCS / "fig_architecture.png", "Figure 2 — Architecture sécurisée (défense en profondeur).", 16)
H("3.1 Principes", 2)
B(["**Minimisation** : aucune image n'est écrite sur disque ; les sujets sont identifiés par un pseudonyme fourni par "
   "l'application métier.",
   "**Gabarit jamais stocké en clair** : il est transformé, puis chiffré ; le clair n'existe qu'en mémoire, le temps du calcul.",
   "**Séparation des secrets** : la base de données et le coffre de clés sont distincts ; l'un sans l'autre est inexploitable.",
   "**Moindre privilège** : trois rôles aux droits disjoints.",
   "**Traçabilité infalsifiable** : toute action, y compris refusée, est journalisée dans une chaîne HMAC."])
H("3.2 Transformation révocable", 2)
P("Pour chaque sujet s et chaque version v, une graine est dérivée par HMAC-SHA256(secret, « cancelable | s | v »). "
  "Elle détermine une permutation P des 9 600 positions et une chaîne aléatoire K. Le gabarit stocké vaut "
  "T(c) = P(c) ⊕ K, et le masque est permuté de la même façon. Comme une permutation et un XOR communs aux deux opérandes "
  "ne changent pas le nombre de bits différents, **HD(T(a), T(b)) = HD(a, b)** : la comparaison s'effectue dans le domaine "
  "transformé, sans perte de précision. Pour gérer la rotation, la sonde est décalée avant transformation, pour chacun "
  "des 17 décalages. Une révocation incrémente v : la nouvelle référence n'est pas reliable à l'ancienne (HD ≈ 0,5 entre "
  "versions).")
P("Limite assumée : si le secret de transformation fuit en même temps que la base, la transformation peut être inversée. "
  "Elle complète donc le chiffrement sans le remplacer.")
H("3.3 Chiffrement d'enveloppe AES-256-GCM", 2)
fig(DOCS / "fig_envelope.png", "Figure 3 — Chiffrement d'enveloppe.", 15)
P("Chaque gabarit est chiffré par une clé de données (DEK) aléatoire de 256 bits, avec un nonce aléatoire de 96 bits ; "
  "GCM produit un tag d'authentification de 128 bits (NIST SP 800-38D). La DEK est elle-même chiffrée (« enveloppée ») "
  "par la clé de chiffrement de clés (KEK) active, identifiée par sa version. Les KEK résident dans un coffre chiffré par "
  "une clé maîtresse qui, en production, doit être confiée à un HSM ou à un KMS (NIST SP 800-57). Les **données associées "
  "authentifiées** (AAD) valent « sujet | identifiant du gabarit | version de KEK » : déplacer un chiffré vers une autre "
  "ligne rend le tag invalide. La **rotation** crée une KEK, puis rechiffre chaque gabarit en mémoire, sans ré-enrôlement.")
H("3.4 Contrôle d'accès et audit", 2)
T([["Rôle", "Permissions"],
   ["operator", "enrôler, vérifier, lire les métadonnées"],
   ["auditor", "lire le journal, vérifier son intégrité, lire les métadonnées"],
   ["admin", "toutes les permissions, plus rotation des clés, révocation, ré-enrôlement et effacement"]],
  [3, 13], "Tableau 3 — Rôles et permissions (RBAC).")
P("Les clés d'API ne sont conservées que sous forme d'empreinte SHA-256 et comparées à temps constant. Après cinq échecs "
  "de vérification, le sujet est verrouillé pendant quinze minutes, ce qui limite la recherche exhaustive par présentation "
  "répétée d'images. Le journal d'audit est chaîné : hᵢ = HMAC-SHA256(k, hᵢ₋₁ ‖ entréeᵢ), avec une clé k dérivée et "
  "distincte des clés de chiffrement. Toute modification ou suppression intermédiaire rompt la chaîne. Le journal ne "
  "contient jamais de donnée biométrique.")

# ------------------------------------------------------------------ 4. Implémentation
H("4. Implémentation")
T([["Composant", "Technologie", "Fichier"],
   ["API REST et documentation Swagger", "FastAPI, Uvicorn", "app/main.py"],
   ["Moteur iris (Daugman/Masek)", "NumPy, SciPy", "app/iris_engine.py"],
   ["Sérialisation, transformation révocable", "NumPy, HMAC", "app/template_codec.py"],
   ["Chiffrement, coffre de clés, rotation", "cryptography (AESGCM)", "app/crypto_service.py"],
   ["Persistance", "SQLAlchemy, SQLite / PostgreSQL", "app/models.py, app/database.py"],
   ["Audit chaîné", "HMAC-SHA256", "app/audit.py"],
   ["Authentification, RBAC", "Clés d'API", "app/security.py"],
   ["Logique métier", "—", "app/service.py"],
   ["Tests (30)", "pytest", "tests/"],
   ["Jeu synthétique, mesures, démonstration", "Pillow, Matplotlib", "tools/"]],
  [5.5, 5, 5.5], "Tableau 4 — Organisation du prototype.")
P("Le moteur d'extraction a été réécrit d'après les publications de Daugman et de Masek plutôt que repris d'une "
  "bibliothèque. La bibliothèque Open-IRIS (Worldcoin) nécessite en effet le téléchargement de modèles de segmentation "
  "par réseau de neurones. Le moteur est isolé derrière la méthode `IrisEngine.extract`, si bien qu'Open-IRIS peut lui être "
  "substitué sans modifier le reste de l'architecture.")
T([["Route", "Rôle", "Fonction"],
   ["POST /enroll", "operator", "Enrôlement : image → IrisCode → transformation → chiffrement"],
   ["POST /verify", "operator", "Vérification 1:1, avec verrouillage anti-force brute"],
   ["GET /subjects/{ref}", "operator, auditor", "Métadonnées, jamais le gabarit"],
   ["POST /subjects/{ref}/revoke", "admin", "Révocation (version incrémentée)"],
   ["POST /subjects/{ref}/reenroll", "admin", "Ré-enrôlement avec une nouvelle transformation"],
   ["DELETE /subjects/{ref}", "admin", "Effacement (RGPD, art. 17)"],
   ["POST /admin/rotate-keys", "admin", "Rotation de la KEK"],
   ["GET /audit, GET /audit/verify", "auditor", "Consultation et contrôle d'intégrité du journal"]],
  [5, 3, 8], "Tableau 5 — Routes de l'API.")

# ------------------------------------------------------------------ 5. Méthodologie & résultats
H("5. Méthodologie et résultats")
H("5.1 Jeu de données", 2)
P("Les bases publiques d'iris (CASIA-Iris, UBIRIS, ND-IRIS) ne sont accessibles qu'après une demande de licence, "
  "incompatible avec les délais du projet. Nous avons donc développé un générateur d'iris synthétiques (tools/synth_iris.py). "
  f"Chacun des {R['dataset']['subjects']} sujets possède une texture propre (somme de composantes radiales et angulaires, "
  f"cryptes) ; chacune de ses {R['dataset']['sessions']} captures varie en position, dilatation pupillaire (±10 %), rotation "
  "(±8°), éclairage, flou, bruit, occultation par la paupière et reflet spéculaire. Ce choix valide le pipeline et les "
  "mécanismes de sécurité, mais les taux d'erreur obtenus sont optimistes.")
H("5.2 Protocole et critères", 2)
B([f"**Performance biométrique** : {M['genuine_pairs']} comparaisons authentiques (toutes les paires de captures d'un même sujet) "
   f"et {M['impostor_pairs']} comparaisons d'imposteurs ; FAR, FRR, EER et indice de décidabilité d′ = |μᵢ − μ_g| / √((σᵢ² + σ_g²)/2).",
   "**Robustesse** : distance moyenne en fonction d'une rotation imposée de 0 à 20°.",
   "**Coût de la sécurité** : temps moyen de chiffrement et de déchiffrement (2 000 itérations), de transformation et de "
   "comparaison, ainsi que le surcoût de stockage.",
   "**Impact de la protection** : écart de score entre comparaison en clair et comparaison dans le domaine transformé.",
   "**Efficacité de la sécurité** : scénarios d'attaque automatisés (pytest), dans lesquels l'attaquant agit directement sur "
   "le fichier de base de données."])
H("5.3 Performance biométrique", 2)
fig(DOCS / "fig_distributions.png", "Figure 4 — Distributions des distances de Hamming.", 13)
th = M["at_threshold"]
T([["Seuil", "FAR", "FRR"]] + [[k.replace(".", ","), pct(v["FAR"]), pct(v["FRR"])] for k, v in th.items()],
  [4, 4, 4], "Tableau 6 — Taux d'erreur selon le seuil.")
T([["Indicateur", "Valeur"],
   ["HD authentiques : moyenne / maximum", f"{fr(M['genuine_hd_mean'])} / {fr(M['genuine_hd_max'])}"],
   ["HD imposteurs : moyenne / minimum", f"{fr(M['impostor_hd_mean'])} / {fr(M['impostor_hd_min'])}"],
   ["Indice de décidabilité d′", fr(M["decidability_dprime"], 2)],
   ["EER", pct(M["eer"])],
   ["Échecs d'enrôlement", f"{X['failure_to_enroll']} / {X['images']}"],
   ["Temps d'extraction : moyenne / 95e centile", f"{fr(X['mean_ms'], 1)} ms / {fr(X['p95_ms'], 1)} ms"]],
  [9, 6], "Tableau 7 — Synthèse de la performance biométrique.")
P(f"Les deux distributions sont nettement séparées (d′ = {fr(M['decidability_dprime'], 2)}). Au seuil retenu de 0,34, aucune "
  f"fausse acceptation n'est observée sur {M['impostor_pairs']} essais ; un seul faux rejet survient sur {M['genuine_pairs']}, "
  "lié à une paire de captures dont les rotations cumulées dépassent la plage compensée.")
fig(DOCS / "fig_rotation.png", "Figure 5 — Robustesse à la rotation.", 11)
P("La compensation par ±8 décalages de colonnes (≈ ±12°) maintient la distance moyenne sous le seuil jusqu'à environ 12° ; "
  "au-delà, il faudrait élargir la plage de recherche, au prix d'un léger accroissement du FAR.")
H("5.4 Coût et impact de la sécurité", 2)
T([["Mesure", "Valeur"],
   ["Taille de l'IrisCode", f"{SC['iriscode_bits']} bits"],
   ["Gabarit sérialisé (code et masque)", f"{SC['serialized_bytes']} octets"],
   ["Stockage chiffré (chiffré, nonces, DEK enveloppée)", f"{SC['stored_bytes_encrypted']} octets (+{SC['storage_overhead_bytes']})"],
   ["Chiffrement AES-256-GCM (avec enveloppe)", f"{fr(SC['encrypt_us'], 1)} µs"],
   ["Déchiffrement", f"{fr(SC['decrypt_us'], 1)} µs"],
   ["Transformation révocable", f"{fr(SC['cancelable_transform_ms'], 2)} ms"],
   ["Comparaison (17 décalages)", f"{fr(SC['match_17_shifts_ms'], 2)} ms"],
   ["Part du déchiffrement dans une vérification", f"{fr(SC['crypto_share_of_verification_pct'], 3)} %"],
   ["Écart maximal de score dû à la transformation", fr(R["cancelable_score_deviation_max"], 1)]],
  [10, 5], "Tableau 8 — Coût de la sécurité (mesures sur la machine de test).")
P("Le coût cryptographique est négligeable : la vérification est dominée par l'extraction depuis l'image (≈ 23 ms). La "
  "transformation révocable n'altère aucun score, ce qui confirme la propriété HD(T(a), T(b)) = HD(a, b). En vérification "
  "par l'API, la transformation est appliquée aux 17 décalages de la sonde, soit environ 3 ms : le temps total observé "
  "reste d'environ 30 ms.")
H("5.5 Efficacité face aux attaques", 2)
T([["Scénario", "Test", "Résultat"],
   ["Lecture directe de la base", "test_db_contains_no_plain_template", "Aucune image, aucun en-tête de gabarit en clair"],
   ["Altération d'un bit du chiffré", "test_bitflip_detected, test_tampered_db…", "Tag GCM invalide, refus 409, alerte journalisée"],
   ["Substitution du gabarit d'un autre sujet", "test_template_substitution_attack", "Détectée grâce à l'AAD, refus 409"],
   ["Clé maîtresse erronée", "test_wrong_master_key_rejected", "Ouverture du coffre refusée"],
   ["Accès sans clé ou avec un rôle insuffisant", "test_no_api_key, test_rbac", "401 / 403, tentative journalisée"],
   ["Force brute (5 échecs)", "test_lockout_after_failures", "Verrouillage, 423"],
   ["Modification d'une entrée du journal", "test_audit_chain_detects_tampering", "Chaîne rompue, entrée localisée"],
   ["Suppression d'une entrée du journal", "test_audit_chain_detects_deletion", "Rupture de séquence détectée"],
   ["Réutilisation d'un gabarit révoqué", "test_revoke_and_reenroll, test_revoked_version_unlinkable", "Refus ; versions non reliables (HD > 0,45)"],
   ["Rotation des clés", "test_rotation_keeps_verification_working", "100 % des gabarits rechiffrés, vérification intacte"]],
  [4.5, 5.5, 6], "Tableau 9 — Scénarios d'attaque (30/30 tests réussis).", 9)

# ------------------------------------------------------------------ 6. Discussion
H("6. Discussion et limites")
P("Le prototype montre qu'une protection complète du gabarit est compatible avec une reconnaissance précise et rapide. "
  "Aucune sécurité n'est toutefois absolue, et plusieurs limites doivent être soulignées :")
B(["**Données synthétiques** : elles sont plus régulières que des images réelles (cils, flou de bougé, lentilles, "
   "éclairage infrarouge non uniforme). Les FAR et FRR mesurés sont donc optimistes ; une évaluation sur CASIA-Iris ou "
   "ND-IRIS est nécessaire.",
   "**Moteur simplifié** : la détection des paupières et des cils repose sur un seuillage robuste, et non sur une "
   "segmentation fine.",
   "**Clair en mémoire** : pendant la comparaison, le gabarit déchiffré réside dans la mémoire du serveur. Une "
   "compromission de l'hôte en cours d'exécution reste donc une menace ; le chiffrement homomorphe ou une enclave (TEE) y répondraient.",
   "**Irréversibilité conditionnelle** : la transformation par permutation et XOR est inversible si son secret est connu. "
   "La protection repose alors sur la séparation entre base et coffre de clés.",
   "**Troncature du journal** : la suppression des dernières entrées n'est détectable que si l'empreinte de tête est "
   "ancrée à l'extérieur (horodatage qualifié, stockage WORM).",
   "**Infrastructure de démonstration** : le coffre de clés est un fichier, le TLS est à assurer par un proxy inverse, et "
   "la détection d'attaque de présentation (faux iris, ISO/IEC 30107) est hors périmètre."])
P("**Perspectives** : évaluation sur bases réelles, intégration d'Open-IRIS, comparaison homomorphe des IrisCodes, "
  "dérivation de clés par fuzzy commitment, intégration à un KMS ou un HSM, ancrage externe du journal et passage à "
  "PostgreSQL avec TLS mutuel.")

# ------------------------------------------------------------------ 7. Conclusion
H("7. Conclusion")
P("Une base biométrique doit être conçue en partant de l'hypothèse qu'elle sera un jour volée. En combinant une "
  "transformation révocable, un chiffrement authentifié AES-256-GCM lié à son contexte, une gestion des clés par enveloppe "
  "avec rotation, un contrôle d'accès par rôles et un journal d'audit chaîné, notre prototype garantit qu'une fuite de la "
  "base ne livre ni image ni IrisCode exploitable, qu'un gabarit compromis peut être révoqué et que toute altération est "
  "détectée. Ces protections n'ont aucun effet mesurable sur la précision et un coût négligeable. Les limites identifiées "
  "tracent la voie vers un système de production : données réelles, matériel de confiance et calcul sur données chiffrées.")

# ------------------------------------------------------------------ Références
H("Références")
for r in [
    "Daugman, J. (2004). How iris recognition works. IEEE Transactions on Circuits and Systems for Video Technology, 14(1), 21–30.",
    "Masek, L. (2003). Recognition of human iris patterns for biometric identification. Bachelor's thesis, The University of Western Australia.",
    "Ratha, N. K., Connell, J. H., & Bolle, R. M. (2001). Enhancing security and privacy in biometrics-based authentication systems. IBM Systems Journal, 40(3), 614–634.",
    "Hao, F., Anderson, R., & Daugman, J. (2006). Combining crypto with biometrics effectively. IEEE Transactions on Computers, 55(9), 1081–1088.",
    "Juels, A., & Sudan, M. (2006). A fuzzy vault scheme. Designs, Codes and Cryptography, 38(2), 237–257.",
    "Venugopalan, S., & Savvides, M. (2011). How to generate spoofed irises from an iris code template. IEEE Transactions on Information Forensics and Security, 6(2), 385–395.",
    "Patel, V. M., Ratha, N. K., & Chellappa, R. (2015). Cancelable biometrics: A review. IEEE Signal Processing Magazine, 32(5), 54–65.",
    "Jain, A. K., Ross, A., & Prabhakar, S. (2004). An introduction to biometric recognition. IEEE Transactions on Circuits and Systems for Video Technology, 14(1), 4–20.",
    "ISO/IEC 24745:2022. Information security, cybersecurity and privacy protection — Biometric information protection.",
    "ISO/IEC 30107-1:2016. Biometric presentation attack detection — Part 1: Framework.",
    "NIST SP 800-38D (2007). Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC.",
    "NIST SP 800-57 Part 1 Rev. 5 (2020). Recommendation for Key Management.",
    "Règlement (UE) 2016/679 du Parlement européen et du Conseil du 27 avril 2016 (RGPD).",
]:
    doc.add_paragraph(r, style="List Number")

# ------------------------------------------------------------------ Annexes
page_break()
H("Annexe A — Guide d'installation et d'utilisation")
for line in ["python -m venv .venv && source .venv/bin/activate   (Windows : .venv\\Scripts\\activate)",
             "pip install -r requirements.txt",
             "uvicorn app.main:app --reload        → http://127.0.0.1:8000/docs (bouton Authorize)",
             "python -m tools.demo                 → scénario en 10 étapes",
             "pytest -q                            → 30 tests",
             "python -m tools.benchmark            → mesures (docs/results.json, figures)"]:
    p = doc.add_paragraph(); r = p.add_run(line); r.font.name = "Consolas"; r.font.size = Pt(9.5)
T([["Clé d'API de démonstration", "Rôle"], ["operator-demo-key", "operator"], ["auditor-demo-key", "auditor"],
   ["admin-demo-key", "admin"]], [8, 5])
P("En production : définir IRIS_MASTER_KEY (32 octets en base64, idéalement fournie par un KMS) et IRIS_API_KEYS, "
  "placer l'API derrière un proxy inverse TLS et utiliser PostgreSQL (IRIS_DB_URL).")
H("Annexe B — Scénario de démonstration")
for i, s in enumerate(["Enrôlement d'Alice et de Bob (rôle operator).",
                       "Consultation des métadonnées : seul un chiffré illisible existe en base.",
                       "Vérification authentique d'Alice avec une autre capture : acceptée (HD ≈ 0,16).",
                       "Imposteur se présentant comme Alice : rejeté (HD ≈ 0,48).",
                       "Requête sans clé (401), puis opérateur tentant de lire l'audit (403).",
                       "Rotation de la KEK ; la vérification fonctionne toujours.",
                       "Attaque : le gabarit d'Alice est remplacé en base par celui de Bob ; alerte d'intégrité (409).",
                       "Révocation du gabarit d'Alice, refus de vérification, ré-enrôlement en version 2.",
                       "Effacement définitif de Bob.",
                       "Journal d'audit, contrôle de la chaîne, puis falsification du journal détectée à l'entrée exacte."], 1):
    doc.add_paragraph(f"Étape {i} — {s}")

H("Annexe C — Code source")
P("Le code complet est fourni dans l'archive du projet. Les fichiers principaux sont reproduits ci-dessous.")
files = ["app/iris_engine.py", "app/template_codec.py", "app/crypto_service.py", "app/models.py", "app/database.py",
         "app/audit.py", "app/security.py", "app/config.py", "app/service.py", "app/main.py", "tools/synth_iris.py",
         "tests/conftest.py", "tests/test_crypto.py", "tests/test_api.py", "tests/test_engine.py"]
for f in files:
    H(f"C.{files.index(f) + 1}  {f}", 2)
    code = (ROOT / f).read_text()
    p = doc.add_paragraph(); p.paragraph_format.line_spacing = 1.0; p.paragraph_format.space_after = Pt(4)
    pPr = p._p.get_or_add_pPr(); shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), "F6F8FA"); pPr.append(shd)
    r = p.add_run(code.rstrip()); r.font.name = "Consolas"; r.font.size = Pt(7.5)
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")

H("Annexe D — Résultats bruts (docs/results.json)")
p = doc.add_paragraph(); r = p.add_run(json.dumps(R, indent=2, ensure_ascii=False)); r.font.name = "Consolas"; r.font.size = Pt(7.5)

out = DOCS / "Rapport_Securisation_BD_Iris.docx"
cp = doc.core_properties
cp.author = cp.last_modified_by = ", ".join(AUTHORS)
cp.title = "Sécurisation des bases de données biométriques à iris"
cp.comments = ""
doc.save(out)
print("OK", out)
