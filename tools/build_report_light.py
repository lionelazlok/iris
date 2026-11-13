"""Génère docs/Rapport_Synthese_Securisation_Iris.docx : rapport léger, sans code,
rédigé pour être compris par un lecteur non spécialiste."""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
R = json.loads((DOCS / "results.json").read_text())
M, SC, X = R["matching"], R["security_cost"], R["extraction"]
NAVY, TEAL, CORAL = RGBColor(0x1d, 0x35, 0x57), RGBColor(0x2a, 0x9d, 0x8f), RGBColor(0xc6, 0x4b, 0x2e)
AUTHORS = ["Koffi ADJOVI", "Aïcha SOSSOU"]
REPO = "https://github.com/lionelazlok/iris"


def fr(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21)
sec.left_margin = sec.right_margin = Cm(2.4)
sec.top_margin = sec.bottom_margin = Cm(2.2)
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11.5)
st.paragraph_format.space_after = Pt(7); st.paragraph_format.line_spacing = 1.2
for lvl, size in ((1, 18), (2, 13.5)):
    h = doc.styles[f"Heading {lvl}"]; h.font.name = "Calibri"; h.font.size = Pt(size); h.font.color.rgb = NAVY; h.font.bold = True


def runs(p, text, size=None, color=None):
    for i, part in enumerate(text.split("**")):
        r = p.add_run(part); r.bold = i % 2 == 1
        if size: r.font.size = Pt(size)
        if color: r.font.color.rgb = color


def P(text, align=WD_ALIGN_PARAGRAPH.LEFT, size=None, color=None, italic=False):
    p = doc.add_paragraph(); runs(p, text, size, color); p.alignment = align
    if italic:
        for r in p.runs: r.italic = True
    return p


def B(items):
    for it in items:
        runs(doc.add_paragraph(style="List Bullet"), it)


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr(); s = OxmlElement("w:shd")
    s.set(qn("w:val"), "clear"); s.set(qn("w:color"), "auto"); s.set(qn("w:fill"), color); tcPr.append(s)


def box(title, lines, fill="E6F4F1", color=TEAL):
    """Encadré coloré (tableau d'une cellule)."""
    t = doc.add_table(rows=1, cols=1); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False; t.columns[0].width = Cm(16)
    c = t.cell(0, 0); shade(c, fill); c.width = Cm(16)
    p = c.paragraphs[0]; r = p.add_run(title); r.bold = True; r.font.size = Pt(12.5); r.font.color.rgb = color
    for ln in lines:
        q = c.add_paragraph(); runs(q, ln, 11)
        q.paragraph_format.space_after = Pt(3)
    doc.add_paragraph()


def T(rows, widths, size=10.5):
    t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    if widths:
        for j, wd in enumerate(widths):
            t.columns[j].width = Cm(wd)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j); c.text = ""; c.width = Cm(widths[j])
            p = c.paragraphs[0]
            for k, part in enumerate(str(v).split("**")):
                r = p.add_run(part); r.font.size = Pt(size); r.bold = i == 0 or k % 2 == 1
                if i == 0: r.font.color.rgb = RGBColor(0xff, 0xff, 0xff)
            if i == 0: shade(c, "1D3557")
            elif i % 2 == 0: shade(c, "F1F5F9")
    doc.add_paragraph()


def fig(path, caption, width=15.5):
    doc.add_picture(str(path), width=Cm(width)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    P(caption, WD_ALIGN_PARAGRAPH.CENTER, 9.5, RGBColor(0x6c, 0x75, 0x7d), True)


def br():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# numéros de page
p = sec.footer.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = p.add_run()
for tag, txt in (("begin", None), (None, "PAGE"), ("end", None)):
    e = OxmlElement("w:fldChar" if tag else "w:instrText")
    if tag: e.set(qn("w:fldCharType"), tag)
    else: e.text = txt
    r._r.append(e)

# ---------------------------------------------------------------- Couverture
for _ in range(4): doc.add_paragraph()
P("RAPPORT DE SYNTHÈSE", WD_ALIGN_PARAGRAPH.CENTER, 12, TEAL)
P("**Sécurisation des bases de données biométriques à iris**", WD_ALIGN_PARAGRAPH.CENTER, 24, NAVY)
P("Version courte et accessible — sans code informatique", WD_ALIGN_PARAGRAPH.CENTER, 13, italic=True)
for _ in range(5): doc.add_paragraph()
P("Réalisé par", WD_ALIGN_PARAGRAPH.CENTER, 11)
for a in AUTHORS: P(f"**{a}**", WD_ALIGN_PARAGRAPH.CENTER, 14)
for _ in range(5): doc.add_paragraph()
P("Novembre 2026", WD_ALIGN_PARAGRAPH.CENTER, 11)
P(f"Code source et rapport technique complet : {REPO}", WD_ALIGN_PARAGRAPH.CENTER, 10)
br()

# ---------------------------------------------------------------- En une page
doc.add_heading("Le projet en une page", 1)
box("Le problème", [
    "Les systèmes de reconnaissance par l'iris gardent une « empreinte numérique » de l'œil de chaque personne dans une "
    "base de données. Si cette base est volée, le dommage est **définitif** : on peut changer un mot de passe, pas son iris."],
    "FDECEA", CORAL)
box("Notre réponse", [
    "Nous avons conçu et programmé un système qui **ne garde jamais ni la photo de l'œil, ni son empreinte lisible**. "
    "Ce qui est stocké est brouillé, puis chiffré : volé, il est inutilisable. Chaque accès est contrôlé et enregistré "
    "dans un journal impossible à falsifier sans que cela se voie."])
box("Ce que montrent nos mesures", [
    f"• **0 erreur** d'acceptation : aucun imposteur accepté sur {M['impostor_pairs']} tentatives.",
    f"• **1 seul refus à tort** sur {M['genuine_pairs']} vérifications de vraies personnes.",
    "• La protection **ne dégrade pas** la reconnaissance et ne coûte presque rien en temps de calcul.",
    "• Les **10 attaques** simulées sur la base de données ont toutes été bloquées ou détectées.",
    "• Réserve : les tests ont été faits sur des **images d'iris générées par ordinateur**, plus faciles que des photos réelles."],
    "EEF2F7", NAVY)
br()

# ---------------------------------------------------------------- 1
doc.add_heading("1. Pourquoi protéger une base d'iris ?", 1)
P("La biométrie, c'est reconnaître une personne à une caractéristique de son corps : empreinte digitale, visage, voix ou "
  "iris. L'iris, la partie colorée de l'œil, est l'une des plus fiables : son motif est unique, même chez de vrais "
  "jumeaux, et il reste stable toute la vie.")
P("Cette fiabilité a un revers. Ce que l'on stocke est un **identifiant à vie**. Or des fuites massives ont déjà eu lieu :")
B(["**2015, États-Unis** : 5,6 millions d'empreintes digitales de fonctionnaires volées (fuite de l'OPM).",
   "**2019, Biostar 2** : une base de contrôle d'accès retrouvée en ligne, avec plus d'un million d'empreintes non chiffrées."])
box("Une comparaison simple", [
    "**Mot de passe volé** → on le change, l'incident est clos.",
    "**Iris volé** → impossible à changer ; la personne reste exposée sur tous les systèmes qui utilisent son iris."],
    "FFF6E5", RGBColor(0x9a, 0x67, 0x00))
P("La loi en tient compte. Le RGPD classe les données biométriques parmi les données **sensibles**, qui exigent des "
  "protections renforcées. La norme internationale ISO/IEC 24745 demande trois propriétés à une base biométrique protégée :")
T([["Exigence", "En clair"],
   ["**Irréversibilité**", "À partir de ce qui est stocké, on ne doit pas pouvoir retrouver l'iris."],
   ["**Non-liabilité**", "On ne doit pas pouvoir reconnaître la même personne d'une base à une autre."],
   ["**Révocabilité**", "Si une donnée fuit, on doit pouvoir l'annuler et en émettre une nouvelle."]], [4, 12])

# ---------------------------------------------------------------- 2
doc.add_heading("2. Comment un ordinateur reconnaît un iris", 1)
fig(DOCS / "fig_pipeline.png", "Les étapes, de la photo à ce qui est réellement stocké.", 16.2)
T([["Étape", "Ce qui se passe", "Pourquoi"],
   ["1. Photo", "L'œil est photographié.", "Point de départ."],
   ["2. Repérage", "Le logiciel trouve deux cercles : le bord de la pupille et le bord de l'iris.", "Isoler l'anneau coloré."],
   ["3. Dépliage", "L'anneau est « déroulé » en un rectangle, comme on déplie un bracelet.", "Comparer des yeux plus ou moins dilatés."],
   ["4. Code", "Le motif est résumé en 9 600 cases noires ou blanches : l'**IrisCode**.", "Comparer vite et précisément."],
   ["5. Stockage", "Le code est brouillé puis chiffré : il ressemble à du bruit.", "Le rendre inutile en cas de vol."]],
  [2.6, 8.4, 5])
P("**Pour comparer deux yeux**, on compte le pourcentage de cases différentes entre leurs codes ; c'est la « distance de "
  "Hamming ». Pour deux yeux différents, environ la moitié des cases diffèrent (≈ 0,50), comme si l'on tirait à pile ou "
  "face. Pour le même œil photographié deux fois, peu de cases diffèrent (≈ 0,15). **En dessous de 0,34, nous concluons "
  "qu'il s'agit de la même personne.**")

# ---------------------------------------------------------------- 3
doc.add_heading("3. Les dangers qui menacent la base", 1)
T([["Menace", "Ce que ça veut dire", "Notre parade"],
   ["Vol de la base", "Quelqu'un copie le fichier de données.", "Tout est chiffré : la copie est illisible."],
   ["Reconstruction de l'œil", "Des chercheurs ont montré qu'on peut recréer une image d'iris à partir de son code.", "Le code n'est jamais stocké en clair."],
   ["Substitution", "L'attaquant remplace l'iris de la victime par le sien pour entrer à sa place.", "Chaque donnée est scellée à sa ligne : l'échange est détecté."],
   ["Recoupement", "Retrouver la même personne dans plusieurs bases.", "Chaque base et chaque version brouillent différemment."],
   ["Abus interne", "Un employé consulte ou modifie ce qu'il ne devrait pas.", "Rôles séparés et journal de tous les accès."],
   ["Effacer ses traces", "Modifier le journal après une intrusion.", "Journal chaîné : toute retouche se voit."],
   ["Essais répétés", "Présenter des centaines d'images pour finir par passer.", "Blocage après 5 échecs."]],
  [3.4, 6.6, 6])

# ---------------------------------------------------------------- 4
doc.add_heading("4. Notre solution : cinq couches de protection", 1)
P("Le principe est celui de la **défense en profondeur** : si une protection cède, les autres tiennent encore. On peut "
  "comparer le système à une banque, qui combine un coffre, des clés gardées ailleurs, des badges et des caméras.")
T([["Couche", "Image", "Ce qu'elle fait"],
   ["1. Brouillage révocable", "Un code secret propre à chaque personne", "Le code de l'iris est mélangé selon une recette secrète. La comparaison reste aussi précise, et en cas de fuite on change de recette (on « révoque »)."],
   ["2. Chiffrement AES-256", "Le coffre-fort", "Le code brouillé est chiffré avec un standard reconnu mondialement. Toute modification, même d'un seul bit, est détectée."],
   ["3. Gestion des clés", "Les clés rangées dans une autre pièce", "Les clés ne sont pas dans la base. Chaque personne a sa propre clé, et les clés peuvent être renouvelées sans réenregistrer personne."],
   ["4. Contrôle d'accès", "Les badges", "Trois profils : l'opérateur enregistre et vérifie, l'auditeur consulte les traces, l'administrateur gère les clés et les suppressions."],
   ["5. Journal infalsifiable", "La caméra de surveillance", "Chaque action est enregistrée. Chaque ligne est liée à la précédente comme les maillons d'une chaîne : en retoucher une casse la chaîne."]],
  [3.6, 3.8, 8.6])
fig(DOCS / "fig_architecture.png", "Vue d'ensemble du système.", 16.2)
P("**Ce que le système ne garde jamais** : la photo de l'œil, le code lisible de l'iris et le nom de la personne (seul "
  "un identifiant anonyme, par exemple « EMP-001 », est conservé).")

# ---------------------------------------------------------------- 5
doc.add_heading("5. Comment nous avons testé", 1)
P("Nous avons réalisé un **prototype qui fonctionne réellement** : un service web qui enregistre et vérifie des personnes, "
  "testable depuis un navigateur. Pour l'évaluer :")
B([f"**Images** : {R['dataset']['subjects']} « personnes » × {R['dataset']['sessions']} photos = "
   f"{R['dataset']['subjects'] * R['dataset']['sessions']} images générées par ordinateur, avec des variations réalistes "
   "(œil tourné, pupille dilatée, éclairage, flou, paupière, reflet). Les bases de photos réelles exigent une licence que "
   "nous ne pouvions pas obtenir à temps.",
   f"**Fiabilité** : {M['genuine_pairs']} comparaisons entre photos d'une même personne et {M['impostor_pairs']} entre "
   "personnes différentes.",
   "**Sécurité** : 30 tests automatiques, dont 10 où nous jouons le rôle d'un pirate qui a accès à la base."])

# ---------------------------------------------------------------- 6
doc.add_heading("6. Résultats", 1)
doc.add_heading("6.1 Le système reconnaît-il bien les personnes ?", 2)
fig(DOCS / "fig_distributions.png", "Répartition des scores de comparaison.", 13.5)
box("Comment lire ce graphique", [
    "• **Montagne verte** (à gauche) : comparaisons d'une personne avec elle-même ; les scores sont bas, autour de 0,15.",
    "• **Montagne orange** (à droite) : comparaisons entre personnes différentes ; les scores sont proches de 0,48.",
    "• **Ligne pointillée** : notre seuil de décision (0,34). À gauche on accepte, à droite on refuse.",
    "• Plus l'écart entre les deux montagnes est grand, plus le système est fiable. Ici, elles ne se chevauchent pas."],
    "EEF2F7", NAVY)
T([["Indicateur", "Résultat", "Interprétation"],
   ["Imposteurs acceptés (FAR)", f"0 sur {M['impostor_pairs']}", "Aucune fausse personne n'est entrée."],
   ["Vraies personnes refusées (FRR)", f"1 sur {M['genuine_pairs']} (0,33 %)", "Une personne aurait dû réessayer (œil très tourné)."],
   ["Échecs d'enregistrement", f"{X['failure_to_enroll']} sur {X['images']}", "Toutes les images ont pu être traitées."],
   ["Rotation de l'œil tolérée", "jusqu'à environ 12°", "Au-delà, il faut redemander une photo."],
   ["Temps d'une vérification", "≈ 30 millisecondes", "Instantané pour l'utilisateur."]], [4.8, 4.2, 7])
doc.add_heading("6.2 La protection a-t-elle un coût ?", 2)
T([["Question", "Réponse mesurée", "Interprétation"],
   ["Le brouillage change-t-il les scores ?", "Écart de 0", "La reconnaissance reste exactement aussi précise."],
   ["Combien de temps prend le chiffrement ?", f"{fr(SC['encrypt_us'], 1)} µs (millionièmes de seconde)", f"≈ {fr(SC['crypto_share_of_verification_pct'], 2)} % du temps total : négligeable."],
   ["Quelle place en plus sur le disque ?", f"+{SC['storage_overhead_bytes']} octets par personne", f"+{fr(SC['storage_overhead_bytes'] / SC['serialized_bytes'] * 100, 1)} % : négligeable."]],
  [5.2, 4.8, 6])
doc.add_heading("6.3 Les attaques sont-elles arrêtées ?", 2)
T([["Ce que fait le pirate", "Ce qui se passe", "Bilan"],
   ["Ouvre le fichier de la base", "Il ne voit que des données illisibles, aucune photo.", "✔ Protégé"],
   ["Modifie un seul bit d'une donnée", "Alerte d'intégrité, vérification refusée.", "✔ Détecté"],
   ["Met son iris à la place de celui de la victime", "Alerte d'intégrité, accès refusé.", "✔ Détecté"],
   ["Tente d'ouvrir le coffre avec une mauvaise clé", "Ouverture refusée.", "✔ Bloqué"],
   ["Se connecte sans autorisation", "Accès refusé, tentative enregistrée.", "✔ Bloqué"],
   ["Opérateur qui veut lire le journal", "Refusé : ce n'est pas son rôle.", "✔ Bloqué"],
   ["Essaie 5 fausses images de suite", "Compte bloqué 15 minutes.", "✔ Bloqué"],
   ["Transforme un « échec » en « succès » dans le journal", "La chaîne est cassée, la ligne modifiée est pointée.", "✔ Détecté"],
   ["Supprime une ligne du journal", "Trou dans la chaîne détecté.", "✔ Détecté"],
   ["Réutilise une donnée annulée", "Refusée ; l'ancienne et la nouvelle ne se ressemblent pas.", "✔ Bloqué"]],
  [5.6, 7.4, 3])

# ---------------------------------------------------------------- 7
doc.add_heading("7. Ce que le système ne garantit pas", 1)
P("Aucun système n'est sûr à 100 %. Voici, en toute transparence, ses limites :")
T([["Limite", "Explication simple", "Piste d'amélioration"],
   ["Images de synthèse", "Les vraies photos (cils, flou, lunettes) sont plus difficiles : les vrais taux d'erreur seraient plus élevés.", "Tester sur une base réelle (CASIA, ND-IRIS)."],
   ["Moment de la comparaison", "Pendant quelques millisecondes, le code est déchiffré dans la mémoire du serveur.", "Comparer dans une puce sécurisée ou sur données chiffrées."],
   ["Recette de brouillage", "Si un pirate vole à la fois la base et la recette, le brouillage peut être défait (le chiffrement reste).", "Garder les secrets dans un boîtier matériel dédié (HSM)."],
   ["Dernières lignes du journal", "Supprimer les toutes dernières lignes peut passer inaperçu.", "Copier régulièrement l'empreinte du journal ailleurs."],
   ["Faux iris imprimé", "Détecter une photo ou une lentille présentée au capteur n'était pas dans notre périmètre.", "Ajouter une détection de vivacité."]],
  [3.4, 7.4, 5.2])

# ---------------------------------------------------------------- 8
doc.add_heading("8. Conclusion", 1)
P("Une base biométrique doit être conçue **comme si elle allait un jour être volée**. En empilant cinq protections "
  "complémentaires, notre prototype garantit qu'un vol de la base ne livre ni photo ni code d'iris exploitable, qu'une "
  "donnée compromise peut être annulée et que toute manipulation est repérée. Tout cela sans perte de précision et pour "
  "un coût de calcul négligeable. La prochaine étape serait une validation sur des photos réelles et l'utilisation de "
  "matériel de sécurité dédié.")

# ---------------------------------------------------------------- Glossaire
doc.add_heading("Glossaire", 1)
T([["Terme", "Définition simple"],
   ["AES-256-GCM", "Méthode de chiffrement standard et très robuste, qui détecte aussi toute modification des données."],
   ["Biométrie", "Reconnaissance d'une personne par une caractéristique physique (iris, empreinte, visage…)."],
   ["Chiffrement", "Transformer des données pour qu'elles soient illisibles sans la clé."],
   ["Clé (KEK, DEK)", "Secret qui permet de chiffrer et de déchiffrer. La DEK protège une donnée, la KEK protège les DEK."],
   ["Distance de Hamming", "Pourcentage de cases différentes entre deux codes d'iris : 0 = identiques, 0,5 = sans rapport."],
   ["FAR / FRR", "Taux d'imposteurs acceptés à tort / taux de vraies personnes refusées à tort."],
   ["Gabarit", "Résumé numérique de l'iris, ce qui est stocké à la place de la photo."],
   ["HSM / KMS", "Boîtier matériel ou service spécialisé qui garde les clés en sécurité."],
   ["IrisCode", "Code de 9 600 cases noires ou blanches qui résume le motif d'un iris."],
   ["Journal d'audit", "Registre de toutes les actions effectuées sur le système."],
   ["RGPD", "Règlement européen sur la protection des données personnelles."],
   ["Révocation", "Annuler une donnée biométrique compromise et en créer une nouvelle, différente."],
   ["Rotation des clés", "Remplacer périodiquement les clés de chiffrement par de nouvelles."]], [4, 12])

doc.add_heading("Pour aller plus loin", 1)
B([f"Code source, guide d'installation et rapport technique complet : **{REPO}**",
   "Daugman J. (2004), How iris recognition works, IEEE TCSVT 14(1).",
   "Ratha N. et al. (2001), Enhancing security and privacy in biometrics-based authentication systems, IBM Systems Journal 40(3).",
   "ISO/IEC 24745:2022, Protection des informations biométriques · Règlement (UE) 2016/679 (RGPD)."])

out = DOCS / "Rapport_Synthese_Securisation_Iris.docx"
cp = doc.core_properties
cp.author = cp.last_modified_by = ", ".join(AUTHORS)
cp.title = "Sécurisation des bases de données biométriques à iris"
cp.comments = ""
doc.save(out)
print("OK", out)
