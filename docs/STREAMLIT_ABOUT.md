### Comment ça marche

1. **Enrôlement** : l'image de l'œil est segmentée (opérateur de Daugman), dépliée en un rectangle 20 × 240, puis encodée en un **IrisCode** de 9 600 bits.
2. Le code est **brouillé** par une transformation secrète et révocable, qui préserve la distance de Hamming, puis **chiffré en AES-256-GCM**. Chaque gabarit a sa propre clé, elle-même protégée par une clé versionnée.
3. **Vérification** : la nouvelle image subit la même transformation ; on compare dans le domaine brouillé. Distance ≤ 0,34 ⇒ accepté.
4. Toute action est inscrite dans un **journal chaîné** dont toute retouche est détectable.

**Scénario conseillé** : enrôler `ALICE` (personne 1, photo 0) et `BOB` (personne 2, photo 0) → vérifier `ALICE` avec la personne 1, photo 2 (accepté) puis avec la personne 7 (refusé) → onglet *Attaques*, substituer le gabarit de BOB chez ALICE → vérifier `ALICE` avec la personne 2 : alerte → onglet *Audit* en rôle `auditor`.
