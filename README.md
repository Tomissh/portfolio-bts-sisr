# Portfolio BTS SIO SISR — Tom Omnès

Portfolio personnel (BTS SIO option SISR) en **site statique d'une seule page**, avec une section de veille technologique alimentée chaque mois par un script IA.

- **Repo** : https://github.com/Tomissh/portfolio-bts-sisr
- **En ligne** : https://tomissh.github.io/portfolio-bts-sisr/ (GitHub Pages, branche `main`)
- **Dossier local** : `C:\Users\tomom\Proton Drive\tom.omnes\My files\CN` (synchronisé par Proton Drive)

## Contenu du dépôt

| Fichier / dossier | Rôle |
|---|---|
| `index.html` | **Tout le site** : HTML, CSS (`<style>` inline) et JS (`<script>` en fin de page). Bootstrap 5.3.2 via CDN jsDelivr. |
| `Style.css` | Reliquat minimal (`#PhT`, photo de profil) |
| `images/PhotoTom.jpg` | Photo de profil |
| `documents/CV-Tom-Omnes.pdf` | CV (bouton « CV » du header) |
| `documents/E5-Tableau-de-synthese.pdf` | Tableau de synthèse de l'épreuve E5 (section Alternance) |
| `send_veille_websearch.py` | Génère le rapport de veille mensuel (Claude + web search) et l'envoie par email |
| `.github/workflows/veille.yml` | Lance le script le 1er de chaque mois à 7h UTC (+ déclenchement manuel) |
| `.claude/launch.json` | Configs de preview : `portfolio-dev` (`python -m http.server 5500`) et `caisse-noire-dev` |

## Lancer en local

```bash
python -m http.server 5500
```

Puis ouvrir http://localhost:5500. Pas de build : chaque push sur `main` est publié par GitHub Pages.

## Sections de `index.html` (ancres)

`#top` (hero), `#propos`, `#parcours` (timeline verticale), `#alternance` (+ lien PDF E5), `#projets` (cartes avec popup de détail : la modale est remplie à partir du `.projet-detail` de la carte cliquée), `#veille` (carrousel filtrable), `#contact` (formulaire).

Le JS gère : le lien actif de la nav au scroll, les animations d'apparition (`IntersectionObserver`), la timeline, l'effet au survol de la souris (`pointermove`), le carrousel de compétences, les filtres et le carrousel de veille, les modales et la validation du formulaire de contact.

## Veille technologique (thème : souveraineté numérique)

### Pipeline automatique

1. Le 1er du mois, `veille.yml` exécute `send_veille_websearch.py` (Python 3.11, `pip install anthropic`).
2. Le script appelle Claude (`claude-haiku-4-5-20251001`) avec l'outil **web search** (5 recherches max, domaines de confiance seulement : ANSSI, CNIL, Légifrance, europa.eu, numerique.gouv.fr, silicon.fr, LeMondeInformatique, Usine Digitale, Next INpact).
3. Un email part avec le rapport HTML **et une pièce jointe `.txt` contenant les blocs HTML des nouvelles cartes**, prêts à coller.
4. **Étape manuelle** : coller ces cartes dans `index.html`, puis committer.

Secrets GitHub nécessaires (Settings → Secrets → Actions) : `ANTHROPIC_API_KEY` (web search activé dans la Console Anthropic), `EMAIL_FROM`, `EMAIL_TO`, `EMAIL_PASSWORD` (App Password Gmail). Coût ≈ 0,05 € par rapport.

> ⚠️ En changeant de compte Anthropic/Claude, si la clé API venait de l'ancien compte : créer une nouvelle clé, activer le web search, et mettre à jour le secret `ANTHROPIC_API_KEY` du repo.

### Ajouter des cartes à la main

Dans `#veilleTrack`, ajouter les nouvelles cartes **en haut** (avant `CARTE 10`), selon la structure documentée en commentaire :

- `data-themes` : thèmes séparés par un espace (filtres existants : Cyber, Réglementation, Identité…)
- `data-mois` : `AAAA-MM`
- `data-detail` : texte long de la modale (`\n` autorisé)
- `data-link` / `data-link-label` : article source

Pour un nouveau mois, ajouter aussi l'option dans `<select id="filterMois">` : `<option value="mois-AAAA-MM">Mois AAAA</option>`. Le commentaire d'exemple dans le HTML contient une faute (`mosis-`), le bon préfixe est `mois-`.

## Formulaire de contact

`<form id="contactForm" data-endpoint="" data-email="...">` :
- `data-endpoint` vide : ouvre la messagerie du visiteur avec le message prérempli (`mailto:`).
- Pour recevoir les messages directement : créer un formulaire sur formspree.io et mettre son URL dans `data-endpoint`.
- Champ `_gotcha` caché = piège anti-spam.

## État (au 2026-10-22, dernier commit `4cececb` « Add contact form » du 2026-09-25)

Fait : refonte du header et du style, carrousel de compétences, animations, bouton CV, popups de projets, timeline verticale, section Alternance + PDF E5, formulaire de contact.

À faire / à vérifier :
- [ ] Le téléphone affiché (`06 12 34 56 78`) est un **placeholder**, à remplacer ou retirer.
- [ ] Footer `© 2025`, à mettre à jour.
- [ ] Les cartes de veille s'arrêtent à **avril 2026** : intégrer les rapports reçus depuis (et ajouter les options de mois).
- [ ] Choisir entre le mode `mailto:` et Formspree pour le formulaire de contact.
- [ ] Vérifier que le workflow `veille.yml` tourne toujours (onglet Actions) et que la clé API est valide.

## Conventions

- Site 100 % en français.
- Tout reste dans `index.html` (pas de framework, pas de build). Garder Bootstrap via CDN.
- Commits en anglais, style « Add … / Update … / Fix … ».
