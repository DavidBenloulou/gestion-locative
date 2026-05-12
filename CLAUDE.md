# CLAUDE.md — Instructions pour Claude Code

> Ce fichier est lu automatiquement par Claude Code au démarrage de chaque session. Il décrit qui je suis (l'utilisateur), comment je veux travailler, et tout ce qu'il faut savoir sur le projet **Gestion Locative SCI**.

---

## 1. À propos de l'utilisateur — David

### Niveau technique
Je suis **novice en développement**. Je n'ai pas de connaissances préalables en Git, Python, Django ou ligne de commande. Toutes les explications doivent être **accessibles, sans jargon technique non expliqué**. Quand tu emploies un terme technique, prends 5 secondes pour le définir.

### Environnement de travail
- **OS** : Windows
- **Shell** : Git Bash exclusivement (jamais PowerShell ni CMD)
- **Éditeur** : VS Code (mais je préfère passer par Git Bash pour les modifications de fichiers via `sed`, `cat`, etc.)
- **Navigateur** : pour tester sur `http://127.0.0.1:8000`
- **Dossier projet local** : `C:\Users\david\OneDrive\Documents\Appli gestion SCI`
- **Python** : 3.11

### Particularités Windows / Git Bash
- Les chemins avec espaces doivent être entre guillemets : `"Appli gestion SCI"`
- Le copier-coller multiligne dans Git Bash peut casser (ajout de caractères parasites `~[200~`, interprétation ligne par ligne). **Préférer les commandes sur une seule ligne** quand on m'en propose à exécuter.
- Pour arrêter le serveur Django : `Ctrl+C` ou fermer la fenêtre
- Si Vim s'ouvre (éditeur de merge) : taper `:wq` puis Entrée pour sauvegarder et quitter

---

## 2. Comment je veux que tu travailles avec moi

### Mode Claude Code
- **Mode plan par défaut** (configuré dans `.claude/settings.json`) — tu ne peux rien modifier sans m'avoir présenté un plan d'abord
- **Validation par bloc cohérent** : présente-moi un plan détaillé complet une fois, puis pendant l'exécution, valide bloc par bloc (ex. "OK pour modifier `views.py` ?" puis "OK pour modifier le template ?" puis "OK pour le commit ?"). Ne demande pas confirmation pour chaque petite ligne, mais regroupe par unité logique.

### Commandes auto-autorisées (dans `.claude/settings.json`)
Tu peux lancer **sans demander** :
- Lecture/observation : `git status`, `git diff`, `git log`, `git branch`, `git show`, `ls`, `cat`, `pwd`, `head`, `tail`, `grep`
- Serveur local : `python manage.py runserver`

Tu **dois demander** pour :
- Toute modification de fichier (Edit, Write)
- Tout `git add`, `git commit`, `git push`, `git checkout`, `git merge`, `git pull`
- Toute commande Django qui modifie l'état : `migrate`, `makemigrations`, `shell`, `dbshell`, `loaddata`, `dumpdata`
- `pip install`, `npm install`, etc.
- Toute commande qui n'est pas dans la liste auto-autorisée

### Gestion des commits Git
- Tu **proposes** le message de commit
- Je valide le message
- Tu exécutes `git add`, `git commit`, `git push` (avec ma validation par bloc)
- **Toujours** faire `git pull origin main` avant un merge sur `main` (le backup automatique de 2h peut avoir modifié `main`)

### Style de dialogue
- **Explique brièvement** ce que fait chaque commande avant de la lancer
- **Analyse les erreurs immédiatement** et propose une correction claire
- **Demande de tester dans le navigateur** avant de proposer un commit/déploiement
- **Rassure en cas d'erreur** — les erreurs sont normales et toujours récupérables
- **Ne suppose pas** qu'une étape est faite — demande confirmation aux étapes importantes

---

## 3. Description du projet

**Nom** : Gestion Locative SCI
**Type** : Application web Django de gestion locative pour plusieurs SCI (Sociétés Civiles Immobilières)
**Statut** : **En production active**, utilisée quotidiennement — toute modification doit être testée en local avant déploiement
**Fonctionnalités** : gestion des biens immobiliers, locataires, transactions financières, cautions, ordures ménagères (OM), bilans comptables et créances

**SCI gérées** : SCI Jonquilles, SCI Ancolie, SCI Accacias, SCI Iris, SCI Muguets, SCI Parkings Jonquilles, SCI Giroflées, SCI Dallas, et d'autres.

---

## 4. Stack technique

- **Langage** : Python 3.11
- **Framework** : Django 5.1.7
- **Base de données** : SQLite (`db.sqlite3`)
- **PDF** : ReportLab, WeasyPrint
- **Excel** : xlsxwriter
- **Frontend** : Bootstrap 5, FontAwesome, HTML/CSS/JS vanilla

---

## 5. Structure des fichiers

```
Appli gestion SCI/
├── gestion_locations/          # Configuration Django
│   ├── settings.py             # Paramètres (IS_PYTHONANYWHERE pour détection env)
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── principale/                 # Application principale
│   ├── models.py               # Modèles de données
│   ├── views.py                # Vues (TRÈS long fichier ~4500+ lignes)
│   ├── forms.py                # Formulaires Django
│   ├── urls.py                 # URLs
│   ├── middleware.py           # Middleware SCI (gestion SCI active)
│   ├── context_processors.py
│   ├── templatetags/
│   │   ├── __init__.py
│   │   └── montant_filters.py  # Filtre |euros
│   ├── templates/principale/
│   ├── static/principale/css/
│   └── migrations/
├── backups/
│   └── latest_backup.json      # Dernière sauvegarde données
├── staticfiles/
├── db.sqlite3
├── manage.py
└── requirements.txt
```

> ⚠️ `principale/views.py` est très long (~4500 lignes). Toujours vérifier le numéro de ligne exact avant de modifier, et préférer `grep` ou la recherche par nom de fonction pour localiser le code à éditer.

---

## 6. Hébergement et déploiement

| Environnement | Détails |
|---|---|
| **Production** | PythonAnywhere — `davidbenloulou.pythonanywhere.com` |
| **Dépôt Git** | GitHub — `github.com/DavidBenloulou/gestion-locative` |
| **Local Windows** | `C:\Users\david\OneDrive\Documents\Appli gestion SCI` |
| **Branche prod** | `main` |
| **Branche dev** | `develop` |

### Structure sur PythonAnywhere
⚠️ Le dépôt Git n'est **pas** à la racine mais dans : `~/Gestion locative/gestion_locations/`

**Pour aller dans le dépôt sur PythonAnywhere** :
```bash
cd ~/Gestion\ locative/gestion_locations
```

### Sauvegarde automatique
Un script bash quotidien à **2h00** sur PythonAnywhere exporte les données en JSON et pousse sur GitHub (`backups/latest_backup.json` sur la branche `main`). C'est pour ça qu'il faut **toujours `git pull origin main` avant de merger develop dans main**.

---

## 7. Procédure de déploiement complète

### Étape 1 — Tester en local (branche `develop`)
```bash
python manage.py runserver
# Tester sur http://127.0.0.1:8000
# Ctrl+C pour arrêter
```

### Étape 2 — Committer et pousser sur `develop`
```bash
git add .
git commit -m "Description du changement"
git push
```

### Étape 3 — Merger `develop` sur `main`
```bash
git checkout main
git pull origin main      # ⚠️ NE PAS OUBLIER
git merge develop
git push
git checkout develop
```

### Étape 4 — Déployer sur PythonAnywhere
Console Bash PythonAnywhere :
```bash
cd ~/Gestion\ locative/gestion_locations
git pull
```
Puis onglet Web → **Reload davidbenloulou.pythonanywhere.com**

### Étape 5 — Vérifier en production
Aller sur https://davidbenloulou.pythonanywhere.com et tester la fonctionnalité déployée.

---

## 8. Gestion des conflits Git

Le backup automatique de 2h pousse sur `main` chaque nuit. Cela peut créer un conflit si on oublie de puller d'abord.

**Si un conflit survient malgré tout** :
```bash
# Voir où est le conflit
grep -rn "<<<<<<\|======\|>>>>>>" .

# Garder la version develop (notre travail)
git checkout --theirs <fichier_en_conflit>
git add <fichier_en_conflit>
git commit -m "Résolution conflit merge"

# Puis récupérer les changements distants et pousser
git pull origin main
git push
```

---

## 9. Modèles de données principaux

```python
SCI                    # Société Civile Immobilière
Bien                   # Bien immobilier (logement, parking, commerce)
Locataire              # Locataire
LocationBien           # Association locataire-bien avec dates et caution
TypeTransaction        # Type de transaction (Loyer, Charges, Dépôt de garantie...)
Transaction            # Transaction financière
ParametresComptables   # Paramètres comptables par année et SCI
MontantOM              # Montants ordures ménagères attendus par locataire/bien/année
CommentaireCreance     # Commentaires sur les créances
```

**Types de transactions importants** :
- ID 18 : `RECETTE - Dépôt de garantie` (caution versée)
- ID 19 : `DEPENSE - Rbt Dépôt garantie` (caution remboursée)

---

## 10. Conventions et architecture

### Cautions
- `Bien.montant_caution` = montant de référence attendu (**source de vérité**)
- `LocationBien.montant_caution` = montant historique (ne plus utiliser comme référence)
- Montant versé = somme des transactions `type_transaction_id=18`
- La saisie manuelle de caution est supprimée — tout passe par les transactions
- `LocationBien.date_versement_caution` = mise à jour automatique à la saisie d'une transaction caution
- `LocationBien.date_restitution_caution` = mise à jour automatique à la saisie d'un remboursement
- ⚠️ Les transactions de caution n'ont **pas** de `mois_concerne` — les requêtes de caution ne doivent pas filtrer par `mois_concerne`

### Bilan comptable
- Démarre au **01/01/2025**
- Les transactions avec date < 2025 sont des migrations historiques (n'impactent pas le bilan)
- `ParametresComptables` stocke solde initial et CC initial par année et SCI

### Multi-SCI
- La SCI active est gérée par `middleware.py` via `request.current_sci`
- Toutes les vues filtrent par `request.current_sci`

### Pagination
- Utiliser `query_params` dans le contexte (sans `page`) pour conserver les filtres dans les liens de pagination

### ⚠️ Zéro en base de données
Toujours utiliser `is not None` pour tester si un montant est renseigné. **Ne jamais utiliser `if montant`** car `0` est falsy en Python.

Dans les templates Django :
```django
{% if montant != None %}...{% endif %}
{# ou #}
{% if montant is not None %}...{% endif %}
```

### Formatage des montants
- **Ne jamais utiliser** `|floatformat:2 }} &nbsp;€` dans les templates
- **Toujours utiliser** `|euros }}` à la place
- Le filtre `|euros` est déclaré en `builtins` dans `settings.py` : disponible dans tous les templates **sans `{% load %}`**
- Le filtre gère automatiquement : séparateurs de milliers (espace fine), virgule décimale, symbole €, et valeur `None`
- Exemples :
  - `1250.5` → `1 250,50 €`
  - `None` → `` (vide)
  - `0` → `0,00 €`
- Filtre `|euros_abs` pour afficher en valeur absolue (utile pour les dépenses)

### Template `confirmer_suppression.html` (générique)
Variables attendues dans le contexte :
- `objet` : description textuelle de l'objet à supprimer
- `type_objet` : type d'objet (bien, locataire, transaction, location...)
- `url_retour` : nom de l'URL Django pour le bouton Annuler
- `id_retour` : ⚠️ **doit s'appeler `id_retour`** (pas `url_retour_id`) si l'URL nécessite un argument

### Conservation des filtres au retour de pages détail/modifier/supprimer
Pattern à appliquer pour les listes filtrables. Quand l'utilisateur clique sur une action depuis une liste filtrée, le retour doit ramener à la même vue filtrée.

Dans la liste :
```django
<a href="{% url 'detail_xxx' obj.id %}{% if request.GET %}?{{ request.GET.urlencode }}{% endif %}">
```

Dans les templates de retour :
```django
<a href="{% url 'liste_xxx' %}{% if request.GET %}?{{ request.GET.urlencode }}{% endif %}">
```

Dans les vues, après une opération réussie :
```python
querystring = request.GET.urlencode()
return redirect(f"{reverse('liste_xxx')}?{querystring}" if querystring else 'liste_xxx')
```
(nécessite `from django.urls import reverse`)

Le template `confirmer_suppression.html` est déjà adapté. Le `{% if request.GET %}` évite un `?` parasite quand il n'y a aucun filtre. Déjà implémenté pour les transactions (mai 2026).

---

## 11. Filtre de template `|euros`

Fichier : `principale/templatetags/montant_filters.py`

```python
from django import template

register = template.Library()

@register.filter(name='euros')
def euros(value):
    if value is None:
        return ''
    try:
        formatted = f"{float(value):,.2f}"
        formatted = formatted.replace(',', '\u202f').replace('.', ',')
        return f"{formatted}\u00a0€"
    except (ValueError, TypeError):
        return value

@register.filter(name='euros_abs')
def euros_abs(value):
    if value is None:
        return ''
    try:
        return euros(abs(float(value)))
    except (ValueError, TypeError):
        return value
```

Déclaration dans `gestion_locations/settings.py` :
```python
'OPTIONS': {
    'context_processors': [...],
    'builtins': ['principale.templatetags.montant_filters'],
},
```

---

## 12. Points d'attention critiques

- **`views.py` est très long** (~4500 lignes) — utiliser `grep` pour localiser le code
- **Ne jamais modifier directement sur PythonAnywhere** (sauf corrections urgentes en prod)
- **Backup automatique à 2h00** — ne pas créer de transactions test en prod sans vérifier l'impact bilan
- **Avant tout `git push` sur `main`** : toujours `git pull origin main` d'abord
- **Cautions sans `mois_concerne`** : requêtes de caution séparées sans filtre date
- **PythonAnywhere compte gratuit** : renouveler régulièrement l'appli Web et la tâche planifiée
- **Comptabilité démarre au 01/01/2025** : transactions antérieures = migrations historiques

---

## 13. Commandes utiles

```bash
# Aller dans le projet
cd ~/OneDrive/Documents/"Appli gestion SCI"

# Lancer le serveur local
python manage.py runserver

# Importer les données depuis GitHub
git pull
python manage.py loaddata backups/latest_backup.json

# Shell Django
python manage.py shell

# Voir l'historique récent
git log --oneline -10

# Voir ce qui a changé
git status
git diff
```

---

*Dernière mise à jour : mai 2026*
