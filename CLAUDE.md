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

### 2.1 — Règles de travail (valables en mode LOCAL et CLOUD)

- **Plan détaillé d'abord** : avant toute modification, présente un plan structuré (fichiers concernés, modifications prévues, ordre des étapes) et attends mon accord
- **Validation par bloc cohérent** : ne demande pas confirmation à chaque ligne, mais regroupe par unité logique (un fichier modifié = un point de validation)
- **Toujours travailler sur une branche dédiée** nommée `claude/<description-courte>`, créée depuis `develop`
- **Le test en local par moi est obligatoire** : avant tout merge vers `main`, je dois avoir testé sur `http://127.0.0.1:8000` avec ma vraie base de données. Tu ne peux pas tester à ma place.
- **Explique brièvement** ce que fait chaque commande avant de la lancer
- **Analyse les erreurs immédiatement** et propose une correction claire
- **Rassure en cas d'erreur** — les erreurs sont normales et toujours récupérables

### 2.2 — Workflow de fin de feature (LOCAL et CLOUD identiquement)

C'est le cœur de la collaboration. Le workflow est **le même dans les deux modes**, à un détail près : en cloud, c'est moi qui exécute le `git pull` local pour tester (Claude cloud n'a pas accès à mon PC).

**Étape A — Code prêt sur la branche `claude/<nom>`**
- Commit et push sur la branche `claude/<nom>` (en local : après ma validation ; en cloud : directement)
- Ne jamais merger dans `develop` ou `main` à ce stade

**Étape B — Donner spontanément les commandes pour tester en local**
Sans attendre que je te le demande, fournis-moi la séquence à exécuter dans Git Bash sur mon PC :
- En mode CLOUD :
  ```
  cd ~/OneDrive/Documents/"Appli gestion SCI"
  git pull origin claude/<nom>
  python manage.py migrate    # si migration créée
  python manage.py runserver
  ```
- En mode LOCAL :
  ```
  cd ~/OneDrive/Documents/"Appli gestion SCI"
  python manage.py migrate    # si migration créée
  python manage.py runserver
  ```
Puis précise ce que je dois tester sur `http://127.0.0.1:8000`.

**Étape C — Attendre mon retour**
Je teste et je te dis "OK déploie" (ou équivalent : "OK pour la prod", "go", "déploie", "ok merge", etc.). Si je signale un problème, on corrige avant de continuer.

**Étape D — Une fois mon OK reçu, exécuter automatiquement la séquence de déploiement**
Cette séquence s'applique partout (LOCAL comme CLOUD), sans redemander confirmation à chaque commande :

1. `git checkout develop && git pull origin develop`
2. `git merge claude/<nom>`
3. `git push origin develop`
4. `git checkout main && git pull origin main` (⚠️ pull obligatoire à cause du backup auto de 2h)
5. `git merge develop && git push origin main`
6. `git checkout develop`
7. `git branch -d claude/<nom>` puis `git push origin --delete claude/<nom>`

Conditions impératives :
- Affiche la sortie de chaque commande au fur et à mesure
- En cas de conflit, d'erreur ou de comportement inattendu : **arrêt immédiat**, affichage du problème, attente de validation explicite avant toute action corrective
- La suppression de branche (étape 7) ne se fait QUE si la branche source s'appelle `claude/<quelque-chose>`. Pour une branche au nom différent, demander confirmation avant suppression.

**Étape E — Donner la procédure PythonAnywhere**
Seule étape manuelle restante : la console PythonAnywhere n'est accessible que par moi. Donne-moi la séquence à exécuter :
```
cd ~/Gestion\ locative/gestion_locations
git pull
python manage.py migrate    # si migration concernée
```
Puis onglet **Web** → **Reload davidbenloulou.pythonanywhere.com**

**Étape F — Demander mon retour sur la production**
Vérifie que la fonctionnalité marche bien en prod avant de considérer la tâche terminée.

**Étape G — Mettre à jour CLAUDE.md silencieusement**
Si la feature a introduit l'un des éléments suivants, modifie `CLAUDE.md` directement (sur la branche `claude/<nom>` AVANT le merge, ou via un commit dédié sur `develop` puis re-merge si on est déjà après le déploiement) :
- Nouveaux champs de modèle ou nouvelles conventions de code
- Nouvelle leçon ou piège général qui peut se reproduire (ex. piège JavaScript, piège Git, etc.)
- Référence à une migration importante
- Modification du workflow lui-même

Ne me demande pas la permission — fais-le silencieusement et **informe-moi à la fin de ce qui a été ajouté/modifié** en quelques lignes. Si rien de notable n'est à documenter, ne fais rien et n'en parle pas.

⚠️ Quand `CLAUDE.md` est modifié, me rappeler à la toute fin :
> _« N'oublie pas d'aller dans le projet "Appli SCI" sur claude.ai → bouton "Sync now" sur la source GitHub de la knowledge base, pour que les nouvelles conversations claude.ai voient la version à jour. »_

### 2.3 — Spécificités résiduelles du mode CLOUD

Le mode CLOUD reste différent du LOCAL sur quelques points techniques inévitables :
- Pas d'accès à mes vraies données → le test final est TOUJOURS de mon côté
- Modifications de la config GitHub (app GitHub, permissions, tokens) en cours de session : créer une **nouvelle session** (les sessions existantes ne récupèrent pas les nouvelles permissions)
- Le sandbox cloud est éphémère : ne jamais y conserver de travail non poussé

Mais les **règles de workflow sont identiques** (section 2.2).

### 2.4 — Gestion des commits Git

- Tu **proposes** le message de commit (format clair, en français)
- Je valide le message implicitement (sauf si je te dis le contraire)
- Tu exécutes `git add`, `git commit -m "..."`, `git push`
- **Toujours** faire `git pull origin main` avant un merge sur `main` (le backup automatique de 2h peut avoir modifié `main`)
- Le message de commit doit décrire **ce qui change**, pas **ce qu'on a fait techniquement** : "Fix: conserver le bien pour les transactions travaux liées à la SCI" ✓ plutôt que "Modifie forms.py et views.py" ✗

### 2.5 — Style de dialogue

- **Demande de tester dans le navigateur** avant de proposer un déploiement
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
- **App GitHub officielle "Claude"** installée sur le dépôt `gestion-locative` uniquement (permissions read+write) — c'est ce qui permet à Claude Code en cloud de pousser des branches et de pousser sur `main` directement
- **PAT `Sauvegarde DB-SCI`** : token sans expiration utilisé par le script de backup PythonAnywhere — **ne pas supprimer**
- Tous les autres PAT historiques ont été supprimés (mai 2026)
- ⚠️ La protection de branche `main` a été désactivée pour permettre à Claude (local et cloud) de déployer après mon OK explicite — la sécurité repose désormais sur la règle "test en local obligatoire + OK explicite avant déploiement"

---

## 7. Procédure de déploiement complète

> Cette procédure est **exécutée automatiquement par Claude** une fois que j'ai dit "OK déploie" (voir section 2.2, étape D). La seule étape manuelle restante est l'étape PythonAnywhere ci-dessous.

### Étape PythonAnywhere (manuelle — la seule)
Dans la console Bash PythonAnywhere :
```bash
cd ~/Gestion\ locative/gestion_locations
git pull
python manage.py migrate    # si migration concernée
```
Puis onglet **Web** → **Reload davidbenloulou.pythonanywhere.com**

### Vérification en production
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

**Si Vim s'ouvre pour un message de merge** : appuyer sur **Échap**, taper `:wq` puis Entrée. Le merge se finalisera avec le message par défaut.

---

## 9. Modèles de données principaux

```python
SCI                    # Société Civile Immobilière
Bien                   # Bien immobilier (logement, parking, commerce)
Locataire              # Locataire
LocationBien           # Association locataire-bien avec dates, caution et prorata premier mois
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

### Prorata du premier mois (mai 2026)
- Migration : `0017_add_prorata_premier_mois_locationbien`
- Champs ajoutés sur `LocationBien` :
  - `montant_loyer_premier_mois` (nullable, default None)
  - `montant_charges_premier_mois` (nullable, default None)
- **Sémantique** :
  - `None` → loyer et charges standards du bien s'appliquent (cas par défaut)
  - Valeur renseignée → ce montant est utilisé partout (créances, état des paiements, relevé de compte) **pour le mois d'arrivée uniquement**
- **UI** : modale automatique qui s'ouvre à l'ouverture du formulaire de modification d'une `LocationBien` si `date_entree.day != 1`, pour proposer le prorata calculé ou laisser saisir des montants personnalisés
- ⚠️ Les locataires déjà en place avant cette feature ont `montant_loyer_premier_mois = None` — il faut les corriger manuellement un par un si leur date d'entrée n'est pas le 1er du mois et qu'on veut un relevé de compte juste
- ⚠️ Toute logique de calcul de loyer dû / charges dues pour le mois d'arrivée doit utiliser le pattern :
  ```python
  est_mois_arrivee = (d.year == location.date_entree.year and d.month == location.date_entree.month)
  loyer_du = location.montant_loyer_premier_mois if (est_mois_arrivee and location.montant_loyer_premier_mois is not None) else bien.loyer_mensuel
  ```

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

### ⚠️ Scripts JavaScript dépendants de Bootstrap (leçon mai 2026)
Bootstrap JS est chargé dans `base.html` **après** `{% block content %}` (vers la ligne 167). Donc un `<script>` placé dans `{% block content %}` s'exécute **avant** que `bootstrap.Modal` soit disponible → échec silencieux.

**Règle** : tout script qui utilise `new bootstrap.Modal(...)`, ou plus généralement toute API Bootstrap JS, doit être placé dans `{% block extra_js %}` (déclaré après le chargement de Bootstrap), pas dans `{% block content %}`.

```django
{% block content %}
   <!-- HTML, modales, formulaires -->
{% endblock %}

{% block extra_js %}
<script>
   // Ici le code qui utilise bootstrap.Modal, etc.
</script>
{% endblock %}
```

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

### Git Bash sur Windows — pièges courants

**Le copier-coller multiligne casse souvent** : les caractères `~[200~` apparaissent, ou les lignes sont interprétées comme des commandes séparées. Solution : commandes sur une seule ligne, ou créer le fichier dans VS Code.

**Vim s'ouvre tout seul** pour les messages de merge ou de commit si on oublie `-m "..."`. Solution : Échap puis `:wq` + Entrée pour sauver et quitter, ou toujours passer `-m "message"` explicitement.

**L'état `MERGING` non finalisé** : après un `git merge` interrompu, le prompt affiche `(branche|MERGING)`. Pour finaliser : `git status` pour voir les conflits éventuels, résoudre, puis `git commit -m "Merge ..."`.

**Le `git pull` sur PythonAnywhere peut déclencher Vim** : si le backup nocturne a poussé sur `main` entre-temps, le pull devient un merge et Vim s'ouvre. Échap + `:wq` + Entrée suffit pour le finaliser.

### Tokens GitHub

**Les Personal Access Tokens (PAT) expirent** : prévoir un nettoyage régulier dans `https://github.com/settings/tokens`. Le token `Sauvegarde DB-SCI` est sans expiration et sert au backup automatique — ne jamais le supprimer.

**Pour Claude Code, on n'utilise PAS de PAT** : c'est l'app GitHub officielle "Claude" qui gère l'authentification via OAuth. Plus stable, plus sûr.

### Scripts JavaScript et chargement des dépendances

**Piège du `<script>` dans `{% block content %}`** : si le script utilise une bibliothèque chargée en bas de `base.html` (Bootstrap, Chart.js, etc.), il s'exécute trop tôt et échoue silencieusement. Toujours placer ces scripts dans `{% block extra_js %}` (voir section 10).

### Historique notable

- **Mai 2026 (jour 1)** : installation et configuration de Claude Code en local + cloud. Découverte des différences de comportement entre les deux modes.
- **Mai 2026 (jour 2)** : correction du bug Travaux+SCI (3 endroits dans `forms.py` et `views.py`). Première session cloud réussie de bout en bout avec Mode planification activé et prompt verrouillé.
- **Mai 2026 (jour 3)** : ajout de la feature "prorata premier mois" (migration 0017, modale automatique, propagation à créances + état paiements + relevé de compte). Découverte du piège du `<script>` dans `{% block content %}` qui s'exécute avant le chargement de Bootstrap.
- **Mai 2026 (jour 4)** : refonte du workflow — suppression de la distinction LOCAL/CLOUD dans les règles de travail. Claude est désormais autorisé à exécuter la séquence complète de déploiement (merge develop+main, push, suppression de branche) après mon OK explicite, quel que soit le mode. La protection de branche `main` sur GitHub a été désactivée pour permettre cette nouvelle règle.
- **Mai 2026 (jour 5)** : simplification de la saisie prorata — suppression de la modale Bootstrap, remplacement par des champs directement dans le formulaire (cachés si date d'entrée = 1er du mois, visibles sinon avec loyer complet par défaut et prorata en texte indicatif). Ajout du `cd ~/OneDrive/Documents/"Appli gestion SCI"` en tête des commandes de test local dans le workflow.

---

*Dernière mise à jour : mai 2026 — simplification prorata (suppression modale) + ajout cd dans commandes de test*
