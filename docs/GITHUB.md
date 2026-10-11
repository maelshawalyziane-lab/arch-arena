# Mettre le projet sur GitHub, pas à pas

Ce guide va du dossier sur votre machine au dépôt en ligne, puis branche les deux
hébergeurs. Comptez dix minutes.

---

## Avant de commencer : où est le projet ?

Le dossier du projet (`arch-arena`) est livré dans un fichier **`arch-arena-github.zip`**.
Téléchargez-le et décompressez-le (clic droit → *Extraire tout* sous Windows, double-clic
sous macOS). Vous obtenez un dossier qui contient déjà **tout** : le code, le corpus
(4 334 problèmes), le cache des traductions françaises, la vitrine, et l'historique Git.

> **Le fichier `.env` n'y est pas, et c'est volontaire.** Il contient votre clé Gemini et
> votre mot de passe : il reste chez vous. Le dépôt fournit à la place `.env.example`, un
> modèle sans aucune valeur. Sur un hébergeur, ces valeurs se saisissent dans son tableau
> de bord — voir `docs/PUBLIER.md`.

---

## Option 1 — GitHub Desktop (la plus simple, sans terminal)

1. **Installez GitHub Desktop** : <https://desktop.github.com>, puis connectez-le à votre
   compte GitHub (*Sign in*).
2. **Ajoutez le projet** : menu *File* → *Add local repository…* → choisissez le dossier
   `arch-arena` décompressé. GitHub Desktop reconnaît immédiatement un dépôt déjà prêt.
3. **Publiez** : cliquez sur le bouton **Publish repository** en haut à droite.
   - Laissez **« Keep this code private »** coché si vous voulez un dépôt privé
     (recommandé : personne ne voit votre travail, Netlify et Render y accèdent quand même) ;
     décochez-le pour un dépôt public.
4. **Publish**. Votre code est en ligne : GitHub Desktop affiche *View on GitHub*.

C'est terminé. Pour envoyer de futures modifications, le bouton *Push origin* suffit.

---

## Option 2 — le terminal (quatre commandes)

1. **Créez le dépôt** sur <https://github.com/new> :
   - *Repository name* : `arch-arena` ;
   - **ne cochez rien** (ni README, ni .gitignore, ni licence : le projet les a déjà) ;
   - *Create repository*.
2. Copiez l'adresse affichée, du type `https://github.com/VOTRE-NOM/arch-arena.git`.
3. Dans un terminal, placez-vous dans le dossier décompressé et lancez :

```bash
git remote add origin https://github.com/VOTRE-NOM/arch-arena.git
git push -u origin main
```

4. **Authentification** : GitHub n'accepte plus le mot de passe du compte. Deux solutions ;
   la première est la plus rapide :

   **a. Un jeton d'accès (token).** Sur GitHub : *Settings* → *Developer settings* →
   *Personal access tokens* → **Fine-grained tokens** → *Generate new token* :
   - *Repository access* : **Only select repositories** → `arch-arena` ;
   - *Permissions* → *Repository permissions* → **Contents : Read and write** ;
   - *Generate token*, puis **copiez la valeur** (`github_pat_…`) et collez-la comme mot de
     passe quand `git push` la demande.
   Le jeton ne sert qu'à ça : révoquez-le quand vous voulez depuis la même page.

   **b. Une clé SSH** (à faire une fois, très confortable ensuite) :

   ```bash
   ssh-keygen -t ed25519 -C "votre@email"     # Entrée, Entrée, Entrée
   cat ~/.ssh/id_ed25519.pub                  # copiez la ligne affichée
   ```
   puis GitHub → *Settings* → *SSH and GPG keys* → *New SSH key* → collez → et utilisez
   l'adresse SSH du dépôt :

   ```bash
   git remote set-url origin git@github.com:VOTRE-NOM/arch-arena.git
   git push -u origin main
   ```

---

## Option 3 — vous préférez que je le fasse

Créez le dépôt vide comme à l'étape 1 de l'option 2, générez un **jeton d'accès limité à ce
dépôt** (mêmes réglages qu'au 4.a : *Contents : Read and write*), donnez-le moi avec
l'adresse du dépôt : je pousse le contenu et je vous confirme que le dépôt est complet.
Ensuite, **révoquez le jeton** — il n'aura servi qu'une fois.

---

## Après le dépôt : brancher les hébergeurs

### Netlify (la vitrine, gratuite)

1. <https://app.netlify.com> → *Add new site* → **Import an existing project** → GitHub →
   autorisez Netlify → choisissez `arch-arena`.
2. Netlify lit `netlify.toml` : *publish directory* = `site`, commande de build
   `python3 scripts/build_site.py`. Laissez tel quel → *Deploy*.
3. Une adresse `https://…netlify.app` apparaît en une minute. Ouvrez la fiche verrouillée :
   le bandeau « 🔒 Solution officielle verrouillée… » doit être là, sans aucune solution.

### Render (la vraie plateforme, qui corrige)

1. <https://render.com> → *New* → **Blueprint** → choisissez le dépôt : `deploy/render.yaml`
   décrit le service et la base.
2. Renseignez les variables demandées :
   `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `GEMINI_API_KEY`,
   `ARCH_ADMIN_PASSWORD` (le mot de passe de votre compte `admin`).
3. Le premier déploiement crée le compte, importe les 4 334 problèmes et applique les
   énoncés français — environ vingt secondes, sans rien télécharger.

Les détails, les coûts et les pièges du plan gratuit sont dans **`docs/PUBLIER.md`**.

---

## Ensuite, à chaque modification

```bash
make publish ARCH_PASSWORD='votre-mot-de-passe'   # régénère les aperçus et site/
git add -A
git commit -m "vitrine à jour"
git push
```

Netlify republie automatiquement après chaque `git push`.

---

## Vérifier que tout est propre

```bash
git log --oneline                    # l'historique des changements
python manage.py test problems       # 154 tests : verrou, API, rendu LaTeX, vitrine
python manage.py bootstrap           # sur une machine neuve : compte + catalogue + français
```

Sur GitHub, l'onglet **Actions** exécute les mêmes contrôles à chaque envoi (`.github/workflows/ci.yml`) :
suite de tests, vérification système, amorçage, construction de la vitrine et contrôle
KaTeX sur 300 fiches. Une pastille verte signifie que tout va bien.

---

## Questions fréquentes

**Le dépôt pèse combien ?** Environ 24 Mo : le corpus (7 Mo), le cache de traduction (3 Mo),
les aperçus et la vitrine (11 Mo). C'est normal et volontaire — sans ces fichiers, un
déploiement neuf n'aurait ni problèmes, ni français, ni site à publier.

**Où est ma base de données ?** Elle n'est pas versionnée : elle se régénère en vingt
secondes avec `python manage.py bootstrap`. Ce qui compte (votre progression) vit en base
chez vous et sur l'hébergeur, pas dans Git.

**Puis-je changer le mot de passe ?** Oui : `python manage.py changepassword admin`, ou en
modifiant `ARCH_ADMIN_PASSWORD` sur l'hébergeur. Ne le mettez jamais dans un fichier du
dépôt — c'est exactement ce que ce guide évite.

**Et si j'ai déjà envoyé un secret par erreur ?** Considérez-le comme compromis :
changez-le d'abord (mot de passe et/ou clé API), nettoyez l'historique ensuite
(`git filter-repo` ou en repartant d'un dépôt neuf). Changer la valeur suffit à rendre
l'ancienne inutile.
