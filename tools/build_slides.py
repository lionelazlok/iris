"""Génère docs/Presentation_Securisation_BD_Iris.pptx (23 diapositives + notes)."""
from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
R = json.loads((DOCS / "results.json").read_text())
M, SC = R["matching"], R["security_cost"]

NAVY, TEAL, CORAL, INK, GREY, LIGHT, WHITE = (RGBColor(0x1d, 0x35, 0x57), RGBColor(0x2a, 0x9d, 0x8f),
    RGBColor(0xe7, 0x6f, 0x51), RGBColor(0x26, 0x32, 0x38), RGBColor(0x6c, 0x75, 0x7d),
    RGBColor(0xf1, 0xf5, 0xf9), RGBColor(0xff, 0xff, 0xff))
AUTHORS = "Koffi ADJOVI · Aïcha SOSSOU"
COURSE = "Sécurité des systèmes d'information — Projet de groupe"
DATE = "Novembre 2026"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = prs.slide_width, prs.slide_height
count = 0


def rect(s, x, y, w, h, fill, line=None, shape=MSO_SHAPE.RECTANGLE):
    sh = s.shapes.add_shape(shape, x, y, w, h)
    sh.fill.solid(); sh.fill.fore_color.rgb = fill
    if line:
        sh.line.color.rgb = line; sh.line.width = Pt(1.25)
    else:
        sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def text(s, x, y, w, h, content, size=18, color=INK, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    lines = content if isinstance(content, list) else [content]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run(); r.text = ln
        r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold; r.font.name = "Calibri"
    return tb


def bullets(s, x, y, w, h, items, size=18, gap=8):
    tb = s.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    first = True
    for it in items:
        lvl = 1 if it.startswith("  ") else 0
        it = it.strip()
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        p.space_after = Pt(gap)
        bullet = "–  " if lvl else "■  "
        r0 = p.add_run(); r0.text = ("      " if lvl else "") + bullet
        r0.font.size = Pt(size - 6 if not lvl else size - 4); r0.font.color.rgb = TEAL if not lvl else GREY
        if "**" in it:
            parts = it.split("**")
            for k, part in enumerate(parts):
                r = p.add_run(); r.text = part
                r.font.size = Pt(size - 2 * lvl); r.font.bold = k % 2 == 1
                r.font.color.rgb = NAVY if k % 2 == 1 else INK; r.font.name = "Calibri"
        else:
            r = p.add_run(); r.text = it
            r.font.size = Pt(size - 2 * lvl); r.font.color.rgb = INK if not lvl else GREY; r.font.name = "Calibri"
    return tb


def slide(title, section=None, notes=""):
    global count
    count += 1
    s = prs.slides.add_slide(BLANK)
    rect(s, 0, 0, W, Inches(1.05), NAVY)
    rect(s, 0, Inches(1.05), W, Inches(0.06), TEAL)
    text(s, Inches(0.5), Inches(0.12), Inches(11), Inches(0.85), title, 28, WHITE, True, anchor=MSO_ANCHOR.MIDDLE)
    if section:
        text(s, Inches(9.3), Inches(0.12), Inches(3.6), Inches(0.85), section.upper(), 11, RGBColor(0x9f, 0xd8, 0xcf),
             True, PP_ALIGN.RIGHT, MSO_ANCHOR.MIDDLE)
    text(s, Inches(0.5), Inches(7.05), Inches(9), Inches(0.35), "Sécurisation des bases de données biométriques à iris",
         10, GREY)
    text(s, Inches(11.8), Inches(7.05), Inches(1.0), Inches(0.35), f"{count} / 23", 10, GREY, align=PP_ALIGN.RIGHT)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def card(s, x, y, w, h, title, body, color=TEAL, size=14):
    rect(s, x, y, w, h, LIGHT)
    rect(s, x, y, Inches(0.09), h, color)
    text(s, x + Inches(0.22), y + Inches(0.12), w - Inches(0.3), Inches(0.5), title, size + 3, color, True)
    text(s, x + Inches(0.22), y + Inches(0.62), w - Inches(0.3), h - Inches(0.7), body, size, INK)


def picture(s, path, x, y, w=None, h=None):
    return s.shapes.add_picture(str(path), x, y, w, h)


def table(s, x, y, w, rows, col_w=None, size=13, row_h=0.42, head=NAVY):
    nr, nc = len(rows), len(rows[0])
    t = s.shapes.add_table(nr, nc, x, y, w, Inches(row_h * nr)).table
    if col_w:
        for i, cw in enumerate(col_w):
            t.columns[i].width = Inches(cw)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j); c.text = str(val)
            c.margin_left = c.margin_right = Inches(0.08); c.margin_top = c.margin_bottom = Inches(0.03)
            p = c.text_frame.paragraphs[0]
            for r in p.runs:
                r.font.size = Pt(size); r.font.name = "Calibri"
                r.font.bold = i == 0; r.font.color.rgb = WHITE if i == 0 else INK
            c.fill.solid(); c.fill.fore_color.rgb = head if i == 0 else (LIGHT if i % 2 else WHITE)
    return t


def pct(x):
    return f"{x * 100:.2f} %".replace(".", ",")


# ---------------------------------------------------------------- 1. Titre
count += 1
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, W, H, NAVY)
rect(s, 0, Inches(4.55), W, Inches(0.07), TEAL)
for i, (r, c) in enumerate(((2.6, RGBColor(0x24, 0x45, 0x6b)), (1.9, RGBColor(0x2a, 0x9d, 0x8f)), (0.85, RGBColor(0x0f, 0x1f, 0x33)))):
    rect(s, Inches(10.4) - Inches(r), Inches(2.3) - Inches(r), Inches(2 * r), Inches(2 * r), c, shape=MSO_SHAPE.OVAL)
rect(s, Inches(10.1), Inches(2.0), Inches(0.28), Inches(0.28), WHITE, shape=MSO_SHAPE.OVAL)
text(s, Inches(0.7), Inches(1.2), Inches(8.2), Inches(0.5), COURSE.upper(), 13, RGBColor(0x9f, 0xd8, 0xcf), True)
text(s, Inches(0.7), Inches(1.8), Inches(8.5), Inches(2.2), ["Sécurisation des bases de", "données biométriques à iris"], 42, WHITE, True)
text(s, Inches(0.7), Inches(3.75), Inches(8.5), Inches(0.6),
     "Menaces, mécanismes de protection et prototype d'API sécurisée", 19, RGBColor(0xd6, 0xe4, 0xf0))
text(s, Inches(0.7), Inches(5.0), Inches(9), Inches(0.5), AUTHORS, 20, WHITE, True)
text(s, Inches(0.7), Inches(5.55), Inches(9), Inches(0.5), DATE, 15, RGBColor(0xb8, 0xc7, 0xd6))
s.notes_slide.notes_text_frame.text = (
    "Bonjour. Nous présentons notre travail sur la sécurisation des bases de données biométriques à iris. "
    "L'exposé suit trois temps : le cadre théorique (biométrie, menaces, protections), l'architecture que nous "
    "proposons, puis un prototype fonctionnel que nous avons mesuré et attaqué nous-mêmes.")

# ---------------------------------------------------------------- 2. Plan
s = slide("Plan de la présentation", notes="Annoncer les quatre parties et la démonstration finale.")
parts = [("01", "Contexte & fondements", "Biométrie, spécificités de l'iris, IrisCode"),
         ("02", "Menaces", "Sensibilité des données, points d'attaque, attaques sur la base"),
         ("03", "Protections", "Exigences ISO/IEC 24745, chiffrement, clés, biométrie révocable, audit"),
         ("04", "Prototype & résultats", "Architecture, API, méthodologie, mesures, limites")]
for i, (n, t, d) in enumerate(parts):
    y = Inches(1.55 + i * 1.32)
    rect(s, Inches(0.9), y, Inches(1.05), Inches(1.05), TEAL if i % 2 == 0 else NAVY, shape=MSO_SHAPE.OVAL)
    text(s, Inches(0.9), y, Inches(1.05), Inches(1.05), n, 26, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    text(s, Inches(2.25), y + Inches(0.08), Inches(9), Inches(0.5), t, 24, NAVY, True)
    text(s, Inches(2.25), y + Inches(0.55), Inches(10), Inches(0.5), d, 16, GREY)

# ---------------------------------------------------------------- 3. Contexte
s = slide("Contexte : la biométrie se généralise… et les fuites aussi", "Contexte", notes=(
    "Aadhaar en Inde : plus de 1,3 milliard de personnes enrôlées avec iris et empreintes. "
    "Fuite OPM (États-Unis, 2015) : 5,6 millions d'empreintes digitales d'agents fédéraux dérobées. "
    "Biostar 2 (2019) : base de contrôle d'accès exposée sans chiffrement, plus d'un million d'empreintes. "
    "Message clé : un mot de passe volé se change ; un iris volé, non. La base devient une cible de grande valeur."))
for i, (big, small, col) in enumerate((("> 1,3 Md", "personnes enrôlées (iris + empreintes) dans Aadhaar, Inde", TEAL),
                                       ("5,6 M", "empreintes volées lors de la fuite OPM (USA, 2015)", CORAL),
                                       ("> 1 M", "empreintes exposées en clair, base Biostar 2 (2019)", CORAL))):
    x = Inches(0.6 + i * 4.15)
    rect(s, x, Inches(1.5), Inches(3.9), Inches(2.3), LIGHT)
    text(s, x, Inches(1.65), Inches(3.9), Inches(1.0), big, 44, col, True, PP_ALIGN.CENTER)
    text(s, x + Inches(0.25), Inches(2.7), Inches(3.4), Inches(1.0), small, 15, INK, align=PP_ALIGN.CENTER)
bullets(s, Inches(0.6), Inches(4.15), Inches(12.2), Inches(2.8), [
    "Usages : contrôle aux frontières, identité nationale, banque, contrôle d'accès, aide humanitaire",
    "Une base biométrique centralisée est une **cible à forte valeur** : données uniques, permanentes, réutilisables",
    "**Problématique** : comment stocker et comparer des gabarits d'iris sans qu'une fuite de la base ne compromette "
    "définitivement les personnes ?"], 18)

# ---------------------------------------------------------------- 4. Biométrie
s = slide("La biométrie : définitions", "Fondements", notes=(
    "Distinguer vérification (1:1, « suis-je bien X ? ») et identification (1:N, « qui suis-je ? »). "
    "Le gabarit (template) est la représentation numérique extraite ; c'est lui qui est stocké, pas l'image. "
    "Critères de Jain : universalité, unicité, permanence, mesurabilité, performance, acceptabilité, résistance au contournement."))
card(s, Inches(0.6), Inches(1.45), Inches(5.9), Inches(2.4), "Vérification (1:1)",
     "« Suis-je bien la personne que je prétends être ? »\nComparaison à UN gabarit de référence.\n→ Cas traité par notre prototype.")
card(s, Inches(6.8), Inches(1.45), Inches(5.9), Inches(2.4), "Identification (1:N)",
     "« Qui suis-je ? »\nRecherche dans toute la base.\n→ Plus coûteux, plus exposé (base entière consultée).", NAVY)
text(s, Inches(0.6), Inches(4.1), Inches(12), Inches(0.5), "Critères d'une bonne modalité (Jain et al.)", 18, NAVY, True)
crit = ["Universalité", "Unicité", "Permanence", "Mesurabilité", "Performance", "Acceptabilité", "Anti-contournement"]
for i, c in enumerate(crit):
    x = Inches(0.6 + i * 1.77)
    rect(s, x, Inches(4.7), Inches(1.65), Inches(0.75), TEAL if i < 3 else NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x, Inches(4.7), Inches(1.65), Inches(0.75), c, 13, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
bullets(s, Inches(0.6), Inches(5.7), Inches(12), Inches(1.3), [
    "**Gabarit** (template) : représentation compacte extraite de l'échantillon — c'est lui qu'on stocke et qu'on protège",
    "Erreurs : **FAR** (fausse acceptation) et **FRR** (faux rejet), arbitrées par un seuil"], 16)

# ---------------------------------------------------------------- 5. Iris
s = slide("Pourquoi l'iris ?", "Fondements", notes=(
    "La texture de l'iris (cryptes, sillons, collerette) se forme de façon aléatoire pendant la gestation (morphogenèse "
    "épigénétique) : même les vrais jumeaux et les deux yeux d'une même personne diffèrent. Daugman estime ~249 degrés "
    "de liberté statistiques, d'où des FAR extrêmement faibles. L'iris est protégé par la cornée et stable dans le temps. "
    "Revers : précisément parce qu'il est stable et unique, sa compromission est définitive."))
bullets(s, Inches(0.6), Inches(1.45), Inches(6.6), Inches(5.4), [
    "Texture **aléatoire** (morphogenèse) : jumeaux et œil gauche/droit différents",
    "≈ **249 degrés de liberté** statistiques (Daugman, 2004)",
    "Organe interne protégé, **stable** sur des décennies",
    "Capture sans contact (proche infrarouge)",
    "Taux de fausse acceptation parmi les plus faibles",
    "**Revers** : unique et permanent ⇒ une fuite est **irréversible**"], 18)
from PIL import Image
from tools.synth_iris import capture
Image.fromarray(capture(3, 0)).resize((640, 560)).save(DOCS / "_eye.png")
picture(s, DOCS / "_eye.png", Inches(7.5), Inches(1.5), h=Inches(4.7))
text(s, Inches(7.7), Inches(6.3), Inches(5), Inches(0.5), "Image d'iris synthétique de notre jeu de test", 12, GREY)

# ---------------------------------------------------------------- 6. Pipeline
s = slide("Chaîne de traitement : de l'image au gabarit", "Fondements", notes=(
    "1) Capture. 2) Segmentation : l'opérateur intégro-différentiel de Daugman cherche le cercle maximisant la variation "
    "de luminosité moyenne — frontière pupille puis limbe. 3) Normalisation rubber sheet : l'anneau est déplié en un "
    "rectangle 20×240, ce qui compense dilatation de la pupille et taille. 4) Filtrage log-Gabor (Masek) et quantification "
    "de la phase sur 2 bits → 9 600 bits. 5) Ce qui est stocké chez nous : le code transformé puis chiffré."))
picture(s, DOCS / "fig_pipeline.png", Inches(0.3), Inches(1.5), w=Inches(12.7))
bullets(s, Inches(0.6), Inches(4.45), Inches(12.2), Inches(2.5), [
    "**Segmentation** : opérateur intégro-différentiel  max(r,x₀,y₀) | G_σ(r) ∗ ∂/∂r ∮ I(x,y)/(2πr) ds |",
    "**Normalisation** « rubber sheet » de Daugman : anneau → rectangle 20 × 240 (invariance à la dilatation)",
    "**Encodage** : filtre log-Gabor 1D (Masek, 2003), phase quantifiée sur 2 bits ⇒ **IrisCode de 9 600 bits** + masque de bruit"], 16)

# ---------------------------------------------------------------- 7. IrisCode / Hamming
s = slide("Comparaison : distance de Hamming fractionnaire", "Fondements", notes=(
    "On compte les bits différents (XOR) uniquement là où les deux masques sont valides, puis on normalise. "
    "Deux iris différents donnent HD ≈ 0,5 (pile ou face) ; le même œil donne typiquement 0,1–0,25. "
    "La rotation de la tête décale le code circulairement : on teste plusieurs décalages et on garde le minimum. "
    "Point important pour la sécurité : cette opération XOR/popcount reste valable après une permutation + XOR secrets, "
    "c'est ce qui rend possible notre gabarit révocable."))
rect(s, Inches(0.6), Inches(1.5), Inches(12.1), Inches(1.35), LIGHT)
text(s, Inches(0.6), Inches(1.55), Inches(12.1), Inches(1.25),
     "HD = ‖ (codeA ⊕ codeB) ∩ maskA ∩ maskB ‖  /  ‖ maskA ∩ maskB ‖", 28, NAVY, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
card(s, Inches(0.6), Inches(3.15), Inches(3.9), Inches(2.3), "Même œil", f"HD moyenne mesurée : {M['genuine_hd_mean']:.3f}\n".replace(".", ",") + "Bits majoritairement identiques", TEAL)
card(s, Inches(4.7), Inches(3.15), Inches(3.9), Inches(2.3), "Yeux différents", f"HD moyenne mesurée : {M['impostor_hd_mean']:.3f}\n".replace(".", ",") + "≈ 0,5 : bits indépendants", CORAL)
card(s, Inches(8.8), Inches(3.15), Inches(3.9), Inches(2.3), "Décision", "HD ≤ 0,34 ⇒ accepté\nRotation : minimum sur ±8 décalages (≈ ±12°)", NAVY)
bullets(s, Inches(0.6), Inches(5.7), Inches(12), Inches(1.2), [
    "Opération très rapide (XOR + comptage de bits) : **0,5 ms** pour 17 décalages dans notre prototype",
    "Propriété clé : HD est **préservée** par une permutation et un XOR secrets ⇒ base de la biométrie révocable"], 16)

# ---------------------------------------------------------------- 8. Données sensibles & cadre légal
s = slide("Des données sensibles par nature — cadre légal", "Menaces", notes=(
    "RGPD article 9 : les données biométriques traitées aux fins d'identifier une personne sont une catégorie particulière, "
    "interdite sauf exception. Article 25 : protection dès la conception. Article 32 : sécurité adaptée (chiffrement, "
    "pseudonymisation). Article 35 : analyse d'impact obligatoire. ISO/IEC 24745 fixe les exigences de protection des "
    "informations biométriques. Les législations nationales de protection des données reprennent des principes équivalents."))
card(s, Inches(0.6), Inches(1.45), Inches(5.9), Inches(2.6), "Spécificités du risque",
     "• Non révocable : on ne change pas d'iris\n• Permanent et unique : identifiant à vie\n• Liable : relie une personne entre bases\n"
     "• Peut révéler des informations (santé, origine)", CORAL, 15)
card(s, Inches(6.8), Inches(1.45), Inches(5.9), Inches(2.6), "Conséquence de conception",
     "• Ne jamais stocker d'image\n• Ne jamais stocker de gabarit en clair\n• Pouvoir révoquer et effacer\n• Tracer chaque accès", TEAL, 15)
table(s, Inches(0.6), Inches(4.35), Inches(12.1), [
    ["Texte", "Exigence", "Réponse dans le prototype"],
    ["RGPD art. 9", "Donnée sensible, base légale spécifique", "Pseudonymisation des sujets"],
    ["RGPD art. 25 / 32", "Protection dès la conception, chiffrement", "AES-256-GCM, transformation révocable"],
    ["RGPD art. 17 / 35", "Effacement, analyse d'impact", "DELETE /subjects, journal d'audit"],
    ["ISO/IEC 24745", "Irréversibilité, non-liabilité, révocabilité", "Gabarit révocable, versions non liables"],
], [2.3, 4.6, 5.2], 13, 0.45)

# ---------------------------------------------------------------- 9. Points d'attaque (Ratha)
s = slide("Modèle de menaces : les 8 points d'attaque (Ratha et al., 2001)", "Menaces", notes=(
    "Ratha, Connell et Bolle ont identifié huit points d'attaque d'un système biométrique. Notre travail cible surtout "
    "le point 6 (la base de gabarits) et le point 7 (le canal base → comparateur), ainsi que le point 8 (décision) via l'audit. "
    "L'attaque du capteur (1, présentation d'un faux iris) relève de la détection d'attaque de présentation (ISO/IEC 30107), hors périmètre."))
stages = ["Capteur", "Extraction", "Comparateur", "Décision"]
for i, st in enumerate(stages):
    x = Inches(0.7 + i * 3.15)
    rect(s, x, Inches(1.75), Inches(2.4), Inches(0.95), NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x, Inches(1.75), Inches(2.4), Inches(0.95), st, 18, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    if i < 3:
        a = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x + Inches(2.45), Inches(2.05), Inches(0.65), Inches(0.35))
        a.fill.solid(); a.fill.fore_color.rgb = GREY; a.line.fill.background()
rect(s, Inches(6.5), Inches(3.3), Inches(2.9), Inches(0.95), CORAL, shape=MSO_SHAPE.CAN)
text(s, Inches(6.5), Inches(3.35), Inches(2.9), Inches(0.9), "Base de gabarits", 17, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
ln = s.shapes.add_connector(1, Inches(7.95), Inches(2.7), Inches(7.95), Inches(3.3)); ln.line.color.rgb = GREY; ln.line.width = Pt(2)
pts = [(0.4, 1.45, "1"), (2.95, 1.45, "2"), (3.55, 1.45, "3"), (6.1, 1.45, "4"), (9.5, 3.55, "6"), (8.1, 2.8, "7"),
       (9.25, 1.45, "5"), (12.1, 1.45, "8")]
for x, y, n in pts:
    c = rect(s, Inches(x), Inches(y), Inches(0.42), Inches(0.42), CORAL if n in "678" else TEAL, shape=MSO_SHAPE.OVAL)
    text(s, Inches(x), Inches(y), Inches(0.42), Inches(0.42), n, 13, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
table(s, Inches(0.6), Inches(4.55), Inches(12.1), [
    ["#", "Point d'attaque", "#", "Point d'attaque"],
    ["1", "Faux iris présenté au capteur (spoofing)", "5", "Substitution du comparateur / du score"],
    ["2", "Rejeu d'un échantillon intercepté", "6", "Vol / modification de la base de gabarits  ◀ cœur du sujet"],
    ["3", "Substitution du module d'extraction", "7", "Interception du canal base → comparateur"],
    ["4", "Falsification du gabarit transmis", "8", "Altération de la décision finale"],
], [0.5, 5.4, 0.5, 5.7], 13, 0.45)

# ---------------------------------------------------------------- 10. Attaques sur la base
s = slide("Attaques visant la base de données", "Menaces", notes=(
    "Le mythe : « un IrisCode n'est qu'une suite de bits, il ne révèle rien ». Faux : Venugopalan et Savvides (2011) ont "
    "reconstruit des images d'iris à partir d'IrisCodes, capables de tromper un système commercial. Autres risques : "
    "substitution (remplacer son propre gabarit par celui d'une victime pour entrer à sa place), liaison entre bases "
    "(le même IrisCode identifie la personne partout), menace interne (administrateur DBA), et effacement des traces."))
attacks = [("Vol de la base", "Copie du fichier / dump SQL ; sauvegardes non chiffrées", CORAL),
           ("Inversion du gabarit", "Reconstruction d'une image d'iris depuis l'IrisCode (Venugopalan & Savvides, 2011)", CORAL),
           ("Substitution", "Remplacer le gabarit de la victime par celui de l'attaquant", CORAL),
           ("Liaison inter-bases", "Le même code relie une personne entre plusieurs systèmes", NAVY),
           ("Menace interne", "Administrateur ou DBA aux droits excessifs", NAVY),
           ("Effacement des traces", "Modification du journal pour masquer l'intrusion", NAVY)]
for i, (t, d, c) in enumerate(attacks):
    x = Inches(0.6 + (i % 3) * 4.1); y = Inches(1.5 + (i // 3) * 2.65)
    card(s, x, y, Inches(3.85), Inches(2.4), t, d, c, 15)

# ---------------------------------------------------------------- 11. Exigences ISO 24745
s = slide("Exigences de protection — ISO/IEC 24745", "Protections", notes=(
    "La norme ISO/IEC 24745 définit trois propriétés pour une référence biométrique protégée : irréversibilité (on ne peut "
    "pas retrouver la donnée biométrique), non-liabilité (on ne peut pas relier deux références issues du même individu "
    "dans deux applications), révocabilité (on peut émettre une nouvelle référence). S'y ajoute la préservation des "
    "performances : une protection qui fait exploser le taux de faux rejet n'est pas acceptable."))
reqs = [("Irréversibilité", "Impossible de retrouver l'iris (ou le code brut) à partir de la référence stockée", "Chiffrement + transformation"),
        ("Non-liabilité", "Deux références du même iris dans deux systèmes ne sont pas reliables", "Transformation par sujet/version"),
        ("Révocabilité", "Émettre une nouvelle référence après compromission", "Version incrémentée, ré-enrôlement"),
        ("Performance", "La protection ne doit pas dégrader FAR / FRR", "HD strictement préservée")]
for i, (t, d, a) in enumerate(reqs):
    y = Inches(1.45 + i * 1.33)
    rect(s, Inches(0.6), y, Inches(3.0), Inches(1.15), TEAL if i < 3 else NAVY, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, Inches(0.6), y, Inches(3.0), Inches(1.15), t, 19, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    text(s, Inches(3.85), y + Inches(0.1), Inches(5.4), Inches(1.0), d, 16, INK, anchor=MSO_ANCHOR.MIDDLE)
    rect(s, Inches(9.4), y + Inches(0.15), Inches(3.3), Inches(0.85), LIGHT)
    text(s, Inches(9.4), y + Inches(0.15), Inches(3.3), Inches(0.85), "→ " + a, 14, NAVY, True, anchor=MSO_ANCHOR.MIDDLE)

# ---------------------------------------------------------------- 12. Panorama
s = slide("Panorama des techniques de protection", "Protections", notes=(
    "Chiffrement classique : simple et standard, mais il faut déchiffrer pour comparer. Biométrie révocable (Ratha 2001) : "
    "transformation répétable, comparaison dans le domaine transformé. Cryptosystèmes biométriques : fuzzy commitment "
    "(Hao, Anderson, Daugman 2006 — lie une clé à l'IrisCode par code correcteur), fuzzy vault (Juels & Sudan). "
    "Chiffrement homomorphe : comparaison sur données chiffrées, mais coût élevé. Match-on-card / TEE : le gabarit ne quitte "
    "jamais un composant sécurisé. Nous combinons les deux premières, les plus réalistes pour un prototype."))
table(s, Inches(0.6), Inches(1.45), Inches(12.1), [
    ["Technique", "Principe", "Forces", "Limites"],
    ["Chiffrement (AES-GCM)", "Gabarit chiffré au repos", "Standard, rapide, intégrité", "Clair en mémoire lors de la comparaison"],
    ["Biométrie révocable", "Transformation secrète répétable", "Révocable, non liable", "Inversible si le secret fuit"],
    ["Fuzzy commitment / vault", "Clé liée au gabarit (codes correcteurs)", "Aucun gabarit stocké", "Perte de précision, fuites statistiques"],
    ["Chiffrement homomorphe", "Calcul de HD sur données chiffrées", "Jamais de clair côté serveur", "Coût calcul et stockage élevés"],
    ["Match-on-card / TEE", "Comparaison dans un composant sûr", "Gabarit jamais exposé", "Matériel dédié, 1:N difficile"],
], [2.7, 3.3, 2.9, 3.2], 14, 0.62)
rect(s, Inches(0.6), Inches(5.55), Inches(12.1), Inches(1.15), RGBColor(0xe6, 0xf4, 0xf1))
text(s, Inches(0.85), Inches(5.6), Inches(11.7), Inches(1.05),
     "Notre choix : défense en profondeur = transformation révocable  +  chiffrement AES-256-GCM  +  gestion des clés  +  RBAC  +  audit chaîné",
     17, NAVY, True, anchor=MSO_ANCHOR.MIDDLE)

# ---------------------------------------------------------------- 13. AES-GCM
s = slide("Chiffrement authentifié AES-256-GCM", "Protections", notes=(
    "GCM est un mode AEAD : il chiffre (confidentialité) et produit un tag d'authentification de 128 bits (intégrité). "
    "Le nonce de 96 bits doit être unique pour une clé donnée : nous le tirons aléatoirement et chaque gabarit a sa propre "
    "DEK, ce qui écarte le risque de réutilisation. L'AAD n'est pas chiffrée mais authentifiée : nous y mettons l'identifiant "
    "du sujet, du gabarit et de la clé. Conséquence : copier le chiffré de Bob dans la ligne d'Alice fait échouer le tag."))
bullets(s, Inches(0.6), Inches(1.35), Inches(12.2), Inches(3.3), [
    "**AEAD** : confidentialité + intégrité en une seule primitive (NIST SP 800-38D)",
    "Clé **256 bits**, nonce **96 bits** aléatoire, tag **128 bits**",
    "**AAD** = sujet | id gabarit | id KEK : liaison du chiffré à SA ligne ⇒ substitution ou déplacement = tag invalide = alerte",
    "Toute modification d'**un seul bit** est détectée",
    f"Coût mesuré : **{SC['encrypt_us']:.1f} µs** chiffrement, **{SC['decrypt_us']:.1f} µs** déchiffrement".replace(".", ","),
], 16, 4)
picture(s, DOCS / "fig_envelope.png", Inches(0.4), Inches(4.0), w=Inches(9.2))
text(s, Inches(9.7), Inches(4.6), Inches(3.3), Inches(2.2), [
    f"Gabarit sérialisé : {SC['serialized_bytes']} octets",
    f"Stocké (chiffré + nonces + DEK enveloppée) : {SC['stored_bytes_encrypted']} octets",
    f"Surcoût de stockage : +{SC['storage_overhead_bytes']} octets ({SC['storage_overhead_bytes'] / SC['serialized_bytes'] * 100:.1f} %)".replace(".", ",")],
    15, GREY)

# ---------------------------------------------------------------- 14. Gestion des clés
s = slide("Gestion des clés : chiffrement d'enveloppe et rotation", "Protections", notes=(
    "La sécurité du chiffrement repose entièrement sur les clés. Hiérarchie : une clé maîtresse (idéalement dans un HSM/KMS) "
    "protège le coffre des KEK ; chaque KEK versionnée enveloppe des DEK ; chaque gabarit a sa DEK. "
    "La rotation crée une nouvelle KEK et rechiffre les gabarits sans demander aux personnes de revenir. "
    "Séparation des secrets : la base seule est inutile ; le coffre seul aussi. Référence : NIST SP 800-57."))
levels = [("Clé maîtresse", "HSM / KMS — jamais en base ni dans le code", NAVY),
          ("KEK versionnées (kek-v1, kek-v2…)", "Coffre chiffré · rotation périodique ou sur incident", TEAL),
          ("DEK — une par gabarit", "Aléatoire 256 bits · stockée enveloppée", RGBColor(0x5d, 0xb8, 0xab)),
          ("Gabarit chiffré", "En base de données, avec kek_id", CORAL)]
for i, (t, d, c) in enumerate(levels):
    w = Inches(6.4 - i * 0.9); x = Inches(0.6 + i * 0.45); y = Inches(1.5 + i * 1.3)
    rect(s, x, y, w, Inches(1.1), c, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x + Inches(0.2), y + Inches(0.05), w - Inches(0.3), Inches(0.5), t, 16, WHITE, True)
    text(s, x + Inches(0.2), y + Inches(0.52), w - Inches(0.3), Inches(0.5), d, 12, WHITE)
bullets(s, Inches(7.3), Inches(1.5), Inches(5.5), Inches(5.3), [
    "**Séparation** : la base volée sans le coffre est inexploitable",
    "**Rotation** : POST /admin/rotate-keys",
    "  nouvelle KEK active, ancienne retirée",
    "  gabarits rechiffrés, **sans ré-enrôlement**",
    "**Moindre exposition** : une DEK compromise n'expose qu'un gabarit",
    "Clés d'API stockées en **empreinte SHA-256**, comparées à temps constant",
    "Référence : NIST SP 800-57"], 16)

# ---------------------------------------------------------------- 15. Accès, audit, minimisation
s = slide("Contrôle d'accès, audit et minimisation", "Protections", notes=(
    "RBAC : trois rôles, chacun le strict nécessaire. L'opérateur enrôle et vérifie mais ne voit pas l'audit ; l'auditeur lit "
    "l'audit mais ne touche pas aux gabarits ; l'administrateur gère clés, révocation et effacement. Le journal est chaîné : "
    "chaque entrée contient le HMAC de la précédente, toute modification casse la chaîne. Verrouillage après 5 échecs "
    "contre la force brute (essais répétés d'images). Minimisation : pas d'image, pas de nom, uniquement un pseudonyme."))
table(s, Inches(0.6), Inches(1.45), Inches(6.4), [
    ["Rôle", "Droits"],
    ["operator", "enrôler, vérifier, lire métadonnées"],
    ["auditor", "lire et contrôler le journal"],
    ["admin", "tout + rotation, révocation, effacement"],
], [1.6, 4.8], 15, 0.55)
card(s, Inches(0.6), Inches(3.9), Inches(6.4), Inches(2.85), "Journal d'audit chaîné",
     "hᵢ = HMAC-SHA256(k, hᵢ₋₁ ‖ entréeᵢ)\n\n• Toute action, y compris refusée (401/403), est journalisée\n"
     "• Modification ou suppression d'entrée ⇒ chaîne rompue\n• Vérification : GET /audit/verify", NAVY, 15)
bullets(s, Inches(7.4), Inches(1.45), Inches(5.4), Inches(5.3), [
    "**Anti-force brute** : 5 échecs ⇒ verrouillage 15 min",
    "**Minimisation** : aucune image conservée, sujets pseudonymisés",
    "**Validation des entrées** : taille, format, résolution de l'image",
    "**Effacement** (RGPD art. 17) : suppression en cascade",
    "**Révocation** : gabarit compromis remplacé par une nouvelle version non liable",
    "En-têtes **no-store**, **nosniff**"], 16)

# ---------------------------------------------------------------- 16. Architecture
s = slide("Architecture sécurisée proposée", "Prototype", notes=(
    "Parcours d'un enrôlement : le client envoie l'image en HTTPS ; la clé d'API et le rôle sont vérifiés ; le moteur extrait "
    "l'IrisCode ; la transformation révocable est appliquée ; le service crypto chiffre avec une DEK neuve, enveloppée par la "
    "KEK active ; seule la ligne chiffrée est écrite ; l'événement est ajouté au journal chaîné. L'image n'est jamais écrite sur disque."))
picture(s, DOCS / "fig_architecture.png", Inches(0.9), Inches(1.3), h=Inches(5.7))

# ---------------------------------------------------------------- 17. Prototype
s = slide("Prototype : pile technique et API", "Prototype", notes=(
    "Tout est en Python. FastAPI génère automatiquement la documentation Swagger, ce qui permet de tester chaque route "
    "dans le navigateur. SQLite pour la démo, PostgreSQL en production sans changer le code grâce à SQLAlchemy. "
    "La bibliothèque cryptography (pyca) fournit AESGCM. 30 tests automatisés pytest couvrent moteur, crypto, API et attaques."))
table(s, Inches(0.6), Inches(1.45), Inches(5.3), [
    ["Composant", "Technologie"],
    ["Langage", "Python 3"],
    ["API + Swagger", "FastAPI, Uvicorn"],
    ["Moteur iris", "NumPy, SciPy (Daugman/Masek)"],
    ["Persistance", "SQLAlchemy · SQLite / PostgreSQL"],
    ["Cryptographie", "cryptography (AESGCM), HMAC"],
    ["Tests", "pytest — 30 tests"],
], [2.0, 3.3], 14, 0.5)
table(s, Inches(6.2), Inches(1.45), Inches(6.5), [
    ["Méthode & route", "Rôle", "Fonction"],
    ["POST /enroll", "operator", "Enrôlement"],
    ["POST /verify", "operator", "Vérification 1:1"],
    ["GET /subjects/{ref}", "op./aud.", "Métadonnées"],
    ["POST /subjects/{ref}/revoke", "admin", "Révocation"],
    ["POST /subjects/{ref}/reenroll", "admin", "Ré-enrôlement"],
    ["DELETE /subjects/{ref}", "admin", "Effacement"],
    ["POST /admin/rotate-keys", "admin", "Rotation KEK"],
    ["GET /audit · /audit/verify", "auditor", "Journal, intégrité"],
], [3.2, 1.2, 2.1], 13, 0.47)
text(s, Inches(0.6), Inches(5.35), Inches(5.3), Inches(1.4),
     ["Lancement :", "uvicorn app.main:app", "→ http://127.0.0.1:8000/docs"], 15, NAVY, True)

# ---------------------------------------------------------------- 18. Démo
s = slide("Scénario de démonstration (10 étapes)", "Prototype", notes=(
    "Commande : python -m tools.demo. Points forts à montrer en direct : étape 2 (le contenu en base est illisible), "
    "étape 7 (l'attaque par substitution est détectée par le tag GCM grâce à l'AAD), étape 10 (la falsification du journal "
    "est détectée à l'entrée exacte). On peut aussi tout refaire à la main dans Swagger avec les images de data/demo/."))
steps = ["Enrôlement d'Alice et Bob", "Métadonnées : seul le chiffré existe", "Vérification authentique → accepté (HD ≈ 0,16)",
         "Imposteur → rejeté (HD ≈ 0,48)", "Sans clé → 401 · mauvais rôle → 403", "Rotation de la KEK, vérification toujours OK",
         "Attaque : substitution de gabarit → ALERTE INTÉGRITÉ", "Révocation puis ré-enrôlement (version 2)",
         "Effacement de Bob (RGPD)", "Audit + falsification du journal détectée"]
for i, st in enumerate(steps):
    col, row = i // 5, i % 5
    x = Inches(0.6 + col * 6.15); y = Inches(1.45 + row * 1.08)
    attack = i in (6, 9)
    rect(s, x, y, Inches(0.8), Inches(0.85), CORAL if attack else TEAL, shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    text(s, x, y, Inches(0.8), Inches(0.85), f"{i + 1:02d}", 20, WHITE, True, PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)
    rect(s, x + Inches(0.9), y, Inches(5.0), Inches(0.85), LIGHT)
    text(s, x + Inches(1.05), y, Inches(4.8), Inches(0.85), st, 15, INK, attack, anchor=MSO_ANCHOR.MIDDLE)

# ---------------------------------------------------------------- 19. Méthodologie
d = R["dataset"]
s = slide("Méthodologie expérimentale", "Résultats", notes=(
    "Les bases publiques d'iris (CASIA, UBIRIS, ND-IRIS) exigent une demande de licence que nous ne pouvions pas obtenir dans "
    "les délais. Nous avons donc généré des iris synthétiques : chaque sujet a une texture propre, chaque capture varie en "
    "position, dilatation pupillaire, rotation, éclairage, flou, bruit, occultation par la paupière et reflet. "
    "C'est un choix assumé : il valide le pipeline et la sécurité, mais les taux d'erreur seront optimistes."))
card(s, Inches(0.6), Inches(1.45), Inches(5.9), Inches(2.6), "Jeu de données",
     f"{d['subjects']} sujets × {d['sessions']} captures = {d['subjects'] * d['sessions']} images synthétiques\n"
     "Variations : position, dilatation, rotation ±8°, éclairage, flou, bruit, paupière, reflet", TEAL, 15)
card(s, Inches(6.8), Inches(1.45), Inches(5.9), Inches(2.6), "Protocole",
     f"{M['genuine_pairs']} comparaisons authentiques (même sujet)\n{M['impostor_pairs']} comparaisons imposteurs (sujets différents)\n"
     "Balayage du seuil 0 → 0,6", NAVY, 15)
table(s, Inches(0.6), Inches(4.3), Inches(12.1), [
    ["Critère", "Mesure"],
    ["Performance biométrique", "FAR, FRR, EER, indice de décidabilité d′, robustesse à la rotation"],
    ["Coût de la sécurité", "Temps chiffrement / déchiffrement / transformation, surcoût de stockage"],
    ["Efficacité de la sécurité", "Tests d'attaque automatisés : altération, substitution, accès, force brute, journal"],
    ["Impact de la protection", "Écart de score entre gabarit en clair et gabarit transformé"],
], [3.4, 8.7], 14, 0.48)

# ---------------------------------------------------------------- 20. Résultats biométriques
s = slide("Résultats : performance biométrique", "Résultats", notes=(
    f"Les distributions sont nettement séparées : d′ = {M['decidability_dprime']}. Au seuil 0,34 : FAR = 0 sur "
    f"{M['impostor_pairs']} essais imposteurs, FRR = {pct(M['at_threshold']['0.34']['FRR'])} (un seul rejet à tort, sur une "
    "capture fortement tournée). La robustesse à la rotation tient jusqu'à environ 12°, limite fixée par les ±8 décalages. "
    "Rappel honnête : sur données réelles, ces chiffres seraient moins bons."))
picture(s, DOCS / "fig_distributions.png", Inches(0.4), Inches(1.35), w=Inches(7.0))
th = M["at_threshold"]["0.34"]
table(s, Inches(7.7), Inches(1.45), Inches(5.0), [
    ["Indicateur", "Valeur"],
    ["HD authentiques (moy.)", f"{M['genuine_hd_mean']:.3f}".replace(".", ",")],
    ["HD imposteurs (moy. / min)", f"{M['impostor_hd_mean']:.3f} / {M['impostor_hd_min']:.3f}".replace(".", ",")],
    ["Décidabilité d′", f"{M['decidability_dprime']}".replace(".", ",")],
    ["FAR @ 0,34", pct(th["FAR"])],
    ["FRR @ 0,34", pct(th["FRR"])],
    ["EER", pct(M["eer"])],
    ["Échec d'enrôlement", f"{R['extraction']['failure_to_enroll']} / {R['extraction']['images']}"],
    ["Extraction (moy.)", f"{R['extraction']['mean_ms']} ms".replace(".", ",")],
    ["Rotation tolérée", f"≈ 12° (HD {R['rotation_mean_hd']['12']:.2f})".replace(".", ",")],
], [3.0, 2.0], 13, 0.44)
text(s, Inches(0.5), Inches(5.75), Inches(12.3), Inches(1.0),
     "⚠ Données synthétiques : résultats optimistes. Ils valident le pipeline, pas une performance terrain.", 14, CORAL, True)

# ---------------------------------------------------------------- 21. Résultats sécurité
s = slide("Résultats : efficacité et coût de la sécurité", "Résultats", notes=(
    "Chaque ligne correspond à un test automatisé (pytest) qui joue le rôle de l'attaquant directement sur le fichier SQLite. "
    "Tous les scénarios sont bloqués ou détectés. Le coût : le chiffrement représente environ 0,02 % du temps d'une "
    "vérification, dominée par l'extraction de l'image. La transformation révocable ne modifie aucun score (écart 0)."))
table(s, Inches(0.6), Inches(1.45), Inches(7.6), [
    ["Scénario d'attaque", "Résultat"],
    ["Lecture directe de la base", "Aucune image, chiffré illisible"],
    ["Altération d'1 bit du chiffré", "Détectée (tag GCM) → 409"],
    ["Substitution du gabarit d'un autre", "Détectée (AAD) → 409"],
    ["Mauvaise clé maîtresse", "Coffre refusé"],
    ["Accès sans clé / mauvais rôle", "401 / 403, journalisés"],
    ["Force brute (5 essais)", "Verrouillage → 423"],
    ["Modification du journal", "Chaîne rompue, entrée localisée"],
    ["Suppression d'une entrée", "Détectée (séquence)"],
    ["Gabarit révoqué rejoué", "Refusé · v1/v2 non liables (HD > 0,45)"],
], [4.0, 3.6], 13, 0.47)
table(s, Inches(8.5), Inches(1.45), Inches(4.2), [
    ["Coût mesuré", "Valeur"],
    ["Chiffrement", f"{SC['encrypt_us']} µs".replace(".", ",")],
    ["Déchiffrement", f"{SC['decrypt_us']} µs".replace(".", ",")],
    ["Transformation", f"{SC['cancelable_transform_ms']} ms".replace(".", ",")],
    ["Extraction image", f"{SC['extraction_ms']} ms".replace(".", ",")],
    ["Part crypto / vérif.", f"{SC['crypto_share_of_verification_pct']} %".replace(".", ",")],
    ["Surcoût stockage", f"+{SC['storage_overhead_bytes']} octets"],
    ["Écart de score", f"{R['cancelable_score_deviation_max']:.0f}".replace(".", ",")],
], [2.3, 1.9], 13, 0.47)
rect(s, Inches(8.5), Inches(5.45), Inches(4.2), Inches(1.3), RGBColor(0xe6, 0xf4, 0xf1))
text(s, Inches(8.65), Inches(5.5), Inches(3.9), Inches(1.2), "30 / 30 tests automatisés réussis", 18, TEAL, True,
     PP_ALIGN.CENTER, MSO_ANCHOR.MIDDLE)

# ---------------------------------------------------------------- 22. Limites
s = slide("Limites et perspectives", "Discussion", notes=(
    "Nous ne prétendons pas à une sécurité absolue. Principales limites : données synthétiques ; moteur simplifié ; "
    "le gabarit est en clair en mémoire pendant la comparaison ; la transformation n'est pas irréversible si son secret fuit ; "
    "la troncature de la fin du journal nécessite un ancrage externe. Perspectives : bases réelles sous licence, Open-IRIS, "
    "chiffrement homomorphe (comparaison sur chiffré), enclave TEE ou HSM pour la comparaison, détection d'attaque de présentation."))
card(s, Inches(0.6), Inches(1.45), Inches(5.9), Inches(5.3), "Limites",
     "• Données synthétiques ⇒ FAR/FRR optimistes\n• Moteur pédagogique simplifié (paupières, cils)\n"
     "• Gabarit en clair en mémoire lors de la comparaison\n• Transformation inversible si son secret fuit avec la base\n"
     "• Troncature de fin de journal : ancrage externe nécessaire\n• Keystore fichier au lieu d'un HSM/KMS\n"
     "• Détection de faux iris (PAD) hors périmètre", CORAL, 15)
card(s, Inches(6.8), Inches(1.45), Inches(5.9), Inches(5.3), "Perspectives",
     "• Évaluation sur CASIA-Iris / ND-IRIS (licence)\n• Moteur Open-IRIS (Worldcoin) via l'interface existante\n"
     "• Chiffrement homomorphe pour comparer sur chiffré\n• Comparaison en enclave (TEE) ou dans le HSM\n"
     "• Fuzzy commitment pour dériver des clés\n• Ancrage du journal (horodatage, stockage WORM)\n"
     "• PostgreSQL + TLS mutuel + KMS cloud", TEAL, 15)

# ---------------------------------------------------------------- 23. Conclusion & références
s = slide("Conclusion et références", "Conclusion", notes=(
    "Conclusion : une base biométrique doit être conçue en partant du principe qu'elle sera un jour volée. Avec une défense "
    "en profondeur, transformation révocable, chiffrement authentifié, gestion des clés, contrôle d'accès et audit chaîné, "
    "une fuite de la base ne livre ni image ni IrisCode exploitable, et un gabarit compromis peut être révoqué. "
    "Le coût mesuré est négligeable. Merci, nous sommes prêts pour la démonstration et vos questions."))
rect(s, Inches(0.6), Inches(1.4), Inches(12.1), Inches(1.85), RGBColor(0xe6, 0xf4, 0xf1))
text(s, Inches(0.85), Inches(1.45), Inches(11.7), Inches(1.75), [
    "Concevoir la base comme si elle allait être volée : une fuite ne doit livrer ni image, ni IrisCode exploitable.",
    "Défense en profondeur validée : 30 tests d'attaque réussis, coût crypto ≈ 0,02 % du temps de vérification, "
    "performance biométrique inchangée."], 17, NAVY, True, anchor=MSO_ANCHOR.MIDDLE)
refs = [
    "Daugman J. (2004). How iris recognition works. IEEE Trans. Circuits Syst. Video Technol., 14(1), 21–30.",
    "Masek L. (2003). Recognition of human iris patterns for biometric identification. Univ. of Western Australia.",
    "Ratha N., Connell J., Bolle R. (2001). Enhancing security and privacy in biometrics-based authentication systems. IBM Systems Journal, 40(3).",
    "Hao F., Anderson R., Daugman J. (2006). Combining crypto with biometrics effectively. IEEE Trans. Computers, 55(9).",
    "Venugopalan S., Savvides M. (2011). How to generate spoofed irises from an iris code template. IEEE Trans. Inf. Forensics Security, 6(2).",
    "Patel V., Ratha N., Chellappa R. (2015). Cancelable biometrics: a review. IEEE Signal Processing Magazine, 32(5).",
    "ISO/IEC 24745:2022 — Biometric information protection · ISO/IEC 30107-1 — Presentation attack detection.",
    "NIST SP 800-38D (GCM) · NIST SP 800-57 Part 1 Rev. 5 (gestion des clés) · Règlement (UE) 2016/679 (RGPD).",
]
text(s, Inches(0.6), Inches(3.45), Inches(12.1), Inches(3.5), refs, 12, INK)

out = DOCS / "Presentation_Securisation_BD_Iris.pptx"
cp = prs.core_properties
cp.author = cp.last_modified_by = ", ".join([a.strip() for a in AUTHORS.split("·")])
cp.title = "Sécurisation des bases de données biométriques à iris"
cp.comments = ""
prs.save(out)
(DOCS / "_eye.png").unlink(missing_ok=True)
print("OK", out, count, "slides")
