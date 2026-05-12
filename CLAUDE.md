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
- ⚠️ Le copier-coller multiligne dans Git Bash casse souvent (caractères parasites `~[200~`, interprétation ligne par ligne). **Toujours préférer des commandes sur une seule ligne**. Pour créer un fichier multiligne, utiliser `echo 'contenu' > fichier` plutôt que `cat > fichier << 'EOF' … EOF`.
- Pour arrêter le serveur Django : `Ctrl+C` ou fermer la fenêtre
- Si Vim s'ouvre (éditeur de merge) : taper `:wq` puis Entrée pour sauvegarder et quitter
- Pour les commits Git : **toujours utiliser `git commit -m "message"` en ligne**, jamais `git commit` tout court (qui ouvre Vim)

---

## 2. Comment je veux que tu travailles avec moi

### 2.1 — Règles communes (valables en LOCAL ET en CLOUD)

- **Plan détaillé d'abord** : avant toute modification, présente un plan structuré (fichiers concernés, modifications prévues, ordre des étapes) et attends mon accord
- **Validation par bloc cohérent** : ne demande pas confirmation à chaque ligne, mais regroupe par unité logique (un fichier modifié = un point de validation)
- **JAMAIS de merge automatique sur `develop` ou `main`** : tu travailles toujours sur une branche dédiée nommée `claude/<description-courte>`. Le merge vers `develop` et `main` se fait MANUELLEMENT par moi, en Git Bash, après test en local
- **JAMAIS de Pull Request automatique** : si je veux une PR, je la créerai moi-même
- **Le test en local par moi est obligatoire** : avant tout merge vers `main`, je dois avoir testé sur `http://127.0.0.1:8000` avec ma vraie base de données. Tu ne peux pas tester à ma place.
- **Explique brièvement** ce que fait chaque commande avant de la lancer
- **Analyse les erreurs immédiatement** et propose une correction claire
- **Rassure en cas d'erreur** — les erreurs sont normales et toujours récupérables

### 2.2 — Spécificités du MODE LOCAL (Git Bash + Claude Code CLI)

- Le mode plan strict est configuré dans `.claude/settings.json` (`defaultMode: plan`). Tu ne peux **rien modifier** sans accord explicite.
- Commandes auto-autorisées (sans demande) : `git status/diff/log/branch/show`, `ls`, `cat`, `pwd`, `head`, `tail`, `grep`, `python manage.py runserver`
- Toute autre commande (Edit, Write, `git add/commit/push/checkout/merge/pull`, `migrate`, `makemigrations`, `pip install`, etc.) nécessite ma validation explicite
- Les modifications affectent directement mes fichiers Windows — je peux tester immédiatement sur `http://127.0.0.1:8000`

### 2.3 — Spécificités du MODE CLOUD (claude.ai/code)

⚠️ **Le mode cloud se comporte différemment** du mode local. Les règles de `.claude/settings.json` ne sont **pas appliquées strictement** : Claude Code peut prendre plus d'initiatives une fois le plan validé. D'où des règles renforcées :

- **Toujours activer "Mode planification"** dans l'interface AVANT d'envoyer le premier prompt (bouton en bas de la zone de saisie)
- **Toujours formuler un prompt verrouillé** au démarrage qui interdit explicitement :
  - Tout merge dans `develop` ou `main`
  - Toute création automatique de Pull Request
  - Tout push sur `develop` ou `main` directement
  - Toute modification au-delà de la tâche décrite
- **Toujours travailler sur une branche dédiée** : `claude/<description>` créée depuis `develop`
- **Le cloud ne peut PAS tester avec mes vraies données** (pas d'accès à ma base SQLite locale, ni à mon serveur). Donc le test final est TOUJOURS de mon côté, après `git pull` en local.
- **Si je modifie la configuration GitHub** (app GitHub, permissions, tokens) en cours de route : **créer une NOUVELLE session**. Les sessions existantes ne récupèrent pas les nouvelles permissions.
- **Le push sur `main` est bloqué par protection de branche GitHub** — c'est volontaire et sécurisant, ne pas chercher à contourner.

### Modèle de prompt cloud verrouillé (à copier au démarrage)

```
Contexte : projet gestion-locative, branche develop.

Tâche : <description précise>

Règles strictes :
1. Lis le code pour confirmer ton diagnostic avant toute proposition
2. Présente-moi un plan détaillé (fichiers, diffs, étapes)
3. ATTENDS MA VALIDATION EXPLICITE avant toute modification
4. Crée une branche dédiée nommée claude/<nom-court> depuis develop
5. Effectue les modifications, commit, push sur cette branche UNIQUEMENT
6. NE merge PAS dans develop ou main
7. NE crée PAS de Pull Request automatiquement
8. Arrête-toi après le push et résume ce que tu as fait

Contraintes du projet : voir CLAUDE.md (notamment is not None, filtre |euros, conventions cautions)
```

### 2.4 — Gestion des commits Git

- Tu **proposes** le message de commit (format clair, en français)
- Je valide le message
- Tu exécutes `git add`, `git commit -m "..."`, `git push` (avec validation par bloc)
- **Toujours** faire `git pull origin main` avant un merge sur `main` (le backup automatique de 2h peut avoir modifié `main`)
- Le message de commit doit décrire **ce qui change**, pas **ce qu'on a fait techniquement** : "Fix: conserver le bien pour les transactions travaux liées à la SCI" ✓ plutôt que "Modifie forms.py et views.py" ✗

### 2.5 — Style de dialogue

- **Demande de tester dans le navigateur** avant de proposer un commit/déploiement
- **Ne suppose pas** qu'une étape est faite — demande confirmation aux étapes importantes
- Pas de jargon non expliqué
- Si tu détectes que je suis sur la mauvaise branche, dans un état inattendu, ou que je m'apprête à faire une bêtise, **arrête-moi avant que j'exécute**

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

### Authentification GitHub
- **App GitHub officielle "Claude"** installée sur le dépôt `gestion-locative` uniquement (permissions read+write) — c'est ce qui permet à Claude Code en cloud de pousser des branches
- **PAT `Sauvegarde DB-SCI`** : token sans expiration utilisé par le script de backup PythonAnywhere — **ne pas supprimer**
- Tous les autres PAT historiques ont été supprimés (mai 2026)

---

## 7. Procédure de déploiement complète

### Étape 1 — Tester en local (branche `develop` ou `claude/<nom>`)
```bash
python manage.py runserver
# Tester sur http://127.0.0.1:8000
# Ctrl+C pour arrêter
```

### Étape 2 — Si travail sur une branche `claude/<nom>` : merger dans `develop`
```bash
git checkout develop
git pull origin develop
git merge claude/<nom>
git push origin develop
```

### Étape 3 — Merger `develop` sur `main`
```bash
git checkout main
git pull origin main      # ⚠️ NE PAS OUBLIER (backup auto de nuit)
git merge develop
git push origin main
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

**Si un merge est en cours et qu'il faut le finaliser** : `git status` indique "All conflicts fixed but you are still merging". Il suffit alors de faire `git commit -m "Merge ..."` pour clôturer.

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

### Transactions Travaux + SCI (bug corrigé mai 2026)
- Une transaction de type "travaux" cochée "Transaction liée à la SCI" peut avoir un bien associé (par exemple : facture de chaudière payée par la SCI mais affectée à un appartement précis)
- ⚠️ Dans `forms.py` (méthode `save()` de `TransactionForm`) et `views.py` (`ajouter_transaction`, `modifier_transaction`), bien tester `'travaux' in type_transaction.nom.lower()` **avant** de mettre `bien = None` quand `sci_transaction=True`
- L'affichage de la case "Transaction SCI" à la réouverture se base sur `locataire is None AND bien is None` → cas particulier à gérer pour les travaux SCI avec bien

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
- **Mode plan en cloud ≠ Mode plan en local** : voir section 2.3 pour les règles renforcées en cloud
- **Une session cloud démarrée avant un changement de config GitHub ne profite pas des nouvelles permissions** : créer une nouvelle session

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

# Voir l'historique de toutes les branches
git log --oneline --all -10

# Voir ce qui a changé
git status
git diff

# Voir les branches (locales + distantes)
git branch -a

# Récupérer les infos GitHub sans modifier le local
git fetch origin

# Supprimer une branche locale
git branch -d nom-de-branche

# Supprimer une branche distante (sur GitHub)
git push origin --delete nom-de-branche
```

---

## 14. Pièges connus et leçons des sessions précédentes

### Sessions Claude Code Cloud — comportements à anticiper

**Une session cloud peut "reprendre" toute seule** après que tu l'as quittée. Ces "reprises" consomment du quota. Pour vraiment arrêter une session sans la supprimer : refuser tout plan en cours via le bouton "Refuser", puis quitter.

**Une session cloud ne sait pas qu'on a installé une nouvelle app GitHub** : elle continue avec ses credentials initiaux. Toujours créer une **nouvelle session** après modification des permissions GitHub.

**Le sandbox cloud est éphémère mais persiste plusieurs heures** : les commits non poussés peuvent rester dans le sandbox jusqu'au timeout, mais ils sont **invisibles** depuis GitHub et depuis le PC local. Ne jamais compter sur le sandbox pour conserver du travail.

**Claude Code en cloud peut être tenté de merger sur `develop` ou `main` directement** quand il ne peut pas créer de PR. Le prompt verrouillé de la section 2.3 évite ça en l'interdisant explicitement.

**La protection de branche `main` sur GitHub bloque le push cloud sur `main`** : c'est une sécurité voulue, pas un bug. Le push sur `main` doit toujours se faire depuis Git Bash local.

### Git Bash sur Windows — pièges courants

**Le copier-coller multiligne casse souvent** : les caractères `~[200~` apparaissent, ou les lignes sont interprétées comme des commandes séparées. Solution : commandes sur une seule ligne, ou créer le fichier dans VS Code.

**Vim s'ouvre tout seul** pour les messages de merge ou de commit si on oublie `-m "..."`. Solution : `:wq` pour sauver et quitter, ou toujours passer `-m "message"` explicitement.

**L'état `MERGING` non finalisé** : après un `git merge` interrompu, le prompt affiche `(branche|MERGING)`. Pour finaliser : `git status` pour voir les conflits éventuels, résoudre, puis `git commit -m "Merge ..."`.

### Tokens GitHub

**Les Personal Access Tokens (PAT) expirent** : prévoir un nettoyage régulier dans `https://github.com/settings/tokens`. Le token `Sauvegarde DB-SCI` est sans expiration et sert au backup automatique — ne jamais le supprimer.

**Pour Claude Code, on n'utilise PAS de PAT** : c'est l'app GitHub officielle "Claude" qui gère l'authentification via OAuth. Plus stable, plus sûr.

### Historique notable

- **Mai 2026 (jour 1)** : installation et configuration de Claude Code en local + cloud. Découverte des différences de comportement entre les deux modes.
- **Mai 2026 (jour 2)** : correction du bug Travaux+SCI (3 endroits dans `forms.py` et `views.py`). Première session cloud réussie de bout en bout avec Mode planification activé et prompt verrouillé.

---

*Dernière mise à jour : mai 2026 — après correction du bug Travaux+SCI et première utilisation réussie de Claude Code cloud*
