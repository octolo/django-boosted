# Problèmes qualité restants

Date : 14 novembre 2026. Périmètre : état de travail courant.

Ce rapport ne conserve que les limites qui restent après correction de l'audit.

## P2 — Couverture encore faible dans plusieurs modules

La couverture globale dépasse le seuil configuré de 65 %, mais plusieurs zones
restent insuffisamment protégées :

- `admin/fieldsets.py` : 9 % ;
- `managers/urls.py` : 25 % ;
- `models/fields.py` : 62 % ;
- `admin/views/confirm.py` : couverture partielle des variantes objet et annulation.

Priorité : ajouter des tests sur la collecte récursive d'URLs, les manipulations
de fieldsets et toutes les branches de `AuditUserField`.

## P2 — Résolution des dépendances non figée

Le projet est une bibliothèque et ne contient pas de lockfile. La CI audite
l'environnement résolu pour chaque version supportée, mais une résolution
future peut différer de celle validée aujourd'hui.

Priorité : générer des fichiers de contraintes pour les jobs CI si une
régression de dépendance apparaît.

## P3 — Vulture nécessite toujours une interprétation Django

Les hooks, attributs déclaratifs, template tags et méthodes découvertes par
Django ressemblent à du code mort pour une analyse purement statique. Le seuil
à 80 % ne remonte plus de candidat confirmé, mais Vulture ne doit pas supprimer
automatiquement un symbole sans vérification manuelle.

## P3 — Python 3.14 n'est pas dans la matrice supportée

Les validations locales ont été exécutées avec Python 3.14.10, tandis que la CI
supporte officiellement Python 3.11 à 3.13. Le résultat local ne remplace donc
pas la matrice GitHub Actions.
