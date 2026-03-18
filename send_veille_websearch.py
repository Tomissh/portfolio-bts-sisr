"""
send_veille_websearch.py
------------------------
Version AMÉLIORÉE avec Web Search natif Anthropic.

Claude effectue de vraies recherches web en temps réel avant de rédiger
le rapport, ce qui garantit des actualités réelles du mois en cours.

Variables d'environnement requises :
  ANTHROPIC_API_KEY  – clé API Anthropic (web search doit être activé dans la Console)
  EMAIL_FROM         – adresse Gmail expéditrice
  EMAIL_TO           – adresse(s) destinataire(s) (séparées par une virgule)
  EMAIL_PASSWORD     – App Password Gmail (16 caractères)

Dépendances Python :
  pip install anthropic

⚠️  ACTIVATION REQUISE : allez sur console.anthropic.com → Settings → Web Search
    et activez l'option pour votre organisation avant d'exécuter ce script.

Coût estimé par exécution :
  - Tokens Haiku input/output  : ~0,001–0,002 €
  - Web search (max 5 requêtes): ~0,05 € (10 $ / 1 000 recherches)
  - Total estimé               : ~0,05 € / rapport (vs ~0,003 € sans web search)
  → Le surcoût vaut largement la fiabilité des informations réelles.

Modèle : claude-haiku-4-5-20251001
"""

import os
import smtplib
import datetime
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import anthropic


# ── Constantes ────────────────────────────────────────────────────────────────

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096   # élevé : résumés détaillés + chiffres + URLs par article
MAX_SEARCHES = 5    # nombre max de recherches web par rapport (coût : 5 × 0,01 $)

# Domaines de confiance pour la veille — uniquement des sources fiables
ALLOWED_DOMAINS = [
    "anssi.gouv.fr",
    "cnil.fr",
    "legifrance.gouv.fr",
    "europa.eu",
    "consilium.europa.eu",
    "numerique.gouv.fr",
    "silicon.fr",
    "lemondeinformatique.fr",
    "usine-digitale.fr",
    "nextinpact.com",
]


# ── Prompt ────────────────────────────────────────────────────────────────────

def build_prompt(mois_annee: str, mois_iso: str) -> str:
    return f"""Tu es un expert en souveraineté numérique et en droit du numérique européen.
Tu dois produire un rapport mensuel de veille technologique destiné à un étudiant
en 1ère année de BTS SIO option SISR (niveau lycée technique).

Mois du rapport : {mois_annee}
Mois ISO (pour data-mois dans les blocs HTML) : {mois_iso}

ÉTAPE 1 — RECHERCHES WEB (fais-les AVANT de rédiger)
Effectue des recherches web pour trouver des actualités RÉELLES et RÉCENTES sur :
- La réglementation numérique européenne (RGPD, NIS2, AI Act, Cyber Resilience Act)
- Le cloud souverain français et européen (OVHcloud, GAIA-X, SecNumCloud, S3ns)
- La stratégie cyber de l'ANSSI et les incidents majeurs du mois
- L'identité numérique (EUDIW, FranceConnect+, eIDAS 2.0)
- Les dépendances technologiques (semi-conducteurs, hyperscalers US, RISC-V)

Requêtes suggérées (adapte-les avec le mois réel) :
1. "souveraineté numérique actualité {mois_annee}"
2. "ANSSI NIS2 réglementation cyber {mois_annee}"
3. "cloud souverain GAIA-X OVHcloud {mois_annee}"
4. "AI Act identité numérique RGPD Europe {mois_annee}"
5. "stratégie numérique France Europe actualité"

ÉTAPE 2 — RÉDACTION DU RAPPORT
Sur la base des résultats trouvés, rédige le rapport en respectant EXACTEMENT
cette structure :

## 1. Synthèse du mois
4 à 5 lignes résumant le contexte global du mois, avec au moins un chiffre ou
fait concret issu des recherches.

## 2. Actualités clés (3 à 5 items, uniquement des faits réels trouvés)
Pour chaque actualité :
### [Titre exact de l'actualité]
**Source :** [Nom exact de la source] | **Date :** [Date réelle] | **Lien :** [URL complète de l'article]
**Résumé détaillé (8 à 12 lignes) :** Décris l'actualité avec précision en incluant :
- Les chiffres clés présents dans l'article (montants, pourcentages, délais, nombre d'entités, etc.)
- Des exemples concrets mentionnés dans la source (noms d'entreprises, pays, technologies, incidents)
- Les causes et conséquences expliquées clairement
- Le contexte européen ou international si l'article le mentionne
**À retenir :** une phrase synthétique résumant l'essentiel de l'actualité.

## 3. Chiffre ou stat du mois
Une donnée marquante extraite directement d'un article source, avec le nom
de la source et son URL. Explique en 2 à 3 lignes pourquoi ce chiffre est significatif.

## 4. À surveiller le mois prochain
1 à 2 échéances ou tendances réelles à venir, avec si possible une date précise
trouvée dans les articles.

---

ÉTAPE 3 — BLOCS HTML POUR LE PORTFOLIO
Après le rapport, génère un bloc HTML pour chaque actualité de la section 2.
Ces blocs sont à coller directement dans index.html, dans la div id="veilleTrack".

Commence cette section par exactement cette ligne :
<!-- ========== BLOCS HTML À COLLER DANS index.html ========== -->

Puis pour chaque actualité, génère un bloc en respectant CE MODÈLE EXACT
(remplace uniquement les valeurs entre crochets, ne modifie pas les attributs) :

<article class="veille-card"
  data-themes="[THEME1] [THEME2]"
  data-mois="{mois_iso}"
  data-detail="[DETAIL_COMPLET]"
  data-link="[URL_ARTICLE]"
  data-link-label="Lire sur [NOM_SOURCE]">
  <div class="veille-meta">
    <span class="veille-source">[NOM_SOURCE]</span>
    <span>[DATE_LISIBLE]</span>
  </div>
  <h4>[TITRE_ARTICLE]</h4>
  <p class="veille-short">[RESUME_COURT_2_3_PHRASES]</p>
  <span class="veille-hint">Cliquer pour lire l'article complet</span>
  <div class="veille-tags">
    <span class="tag" data-theme="[THEME1]">[THEME1]</span>
    <span class="tag" data-theme="[THEME2]">[THEME2]</span>
  </div>
</article>

Règles de remplissage des champs HTML :
- data-themes : thèmes séparés par un espace. Valeurs autorisées uniquement :
  RGPD, Cloud, IA, Cyber, Réglementation, Identité, Infra
- data-mois : format AAAA-MM (ex: {mois_iso})
- data-detail : le résumé détaillé complet de l'article (même contenu que le rapport).
  Remplace les guillemets droits " par des guillemets typographiques " et "
  pour ne pas casser l'attribut HTML. Les sauts de ligne sont autorisés.
- data-link : URL directe vers l'article (pas la page d'accueil)
- RESUME_COURT_2_3_PHRASES : 2 à 3 phrases maximum, sans chiffres complexes,
  juste l'essentiel pour donner envie de cliquer
- DATE_LISIBLE : format "JJ mois AAAA" en français (ex: 3 mars 2026)
- Si un article n'a qu'un seul thème, supprimer la deuxième ligne data-theme

Termine la section par :
<!-- ========== FIN DES BLOCS HTML ========== -->

---
Règles IMPÉRATIVES pour l'ensemble du rapport :
- Ne rédige QUE des informations trouvées via tes recherches web. Pas d'inventions.
- Chaque chiffre et exemple DOIT provenir d'un article réel trouvé lors des recherches.
- Les URLs doivent être les liens directs vers les articles, pas les pages d'accueil.
- Si des chiffres ou exemples ne sont pas disponibles : indique
  "Données chiffrées non disponibles dans les sources consultées."
- Niveau de langue : soutenu mais accessible à un lycéen en section technique.
- Réponds UNIQUEMENT avec le contenu du rapport puis les blocs HTML.
  Pas de phrase d'intro, pas de conclusion après les blocs HTML.
- Les titres, dates, sources et URLs doivent être exacts et vérifiables.
"""


# ── Appel API Claude avec Web Search ─────────────────────────────────────────

def generate_report_with_search(client: anthropic.Anthropic, mois_annee: str, mois_iso: str) -> tuple[str, int]:
    """
    Appelle Claude Haiku avec le web search tool activé.
    Retourne (rapport_markdown, nombre_de_recherches_effectuées).
    """
    prompt = build_prompt(mois_annee, mois_iso)

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": MAX_SEARCHES,
            "allowed_domains": ALLOWED_DOMAINS,  # sources de confiance uniquement
        }],
        messages=[{"role": "user", "content": prompt}],
    )

    # Compter les recherches effectuées
    search_count = 0
    report_text = ""

    for block in message.content:
        if block.type == "text":
            report_text += block.text
        elif hasattr(block, "type") and block.type == "server_tool_use":
            if block.name == "web_search":
                search_count += 1
                print(f"[SEARCH #{search_count}] Requête : {block.input.get('query', '?')}")

    # Extraire le nombre de recherches depuis les métadonnées d'usage si disponibles
    if hasattr(message, "usage") and hasattr(message.usage, "server_tool_use"):
        search_count = getattr(message.usage.server_tool_use, "web_search_requests", search_count)

    return report_text.strip(), search_count


# ── Conversion Markdown → HTML ────────────────────────────────────────────────

def apply_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def markdown_to_html(md: str) -> str:
    lines = md.split("\n")
    html_lines = []
    in_ul = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("### "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(
                f'<h3 style="margin-top:1.4rem;color:#3b3b6d;font-size:1rem;">'
                f'{apply_inline(stripped[4:])}</h3>'
            )
        elif stripped.startswith("## "):
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(
                f'<h2 style="margin-top:2rem;padding-bottom:6px;'
                f'border-bottom:2px solid #667eea;color:#222;">'
                f'{stripped[3:]}</h2>'
            )
        elif stripped == "---":
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append('<hr style="border:none;border-top:1px solid #eee;margin:1.5rem 0;">')
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul:
                html_lines.append('<ul style="padding-left:1.4rem;margin:0.4rem 0;">'); in_ul = True
            html_lines.append(f"<li>{apply_inline(stripped[2:])}</li>")
        elif stripped == "":
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append("")
        else:
            if in_ul: html_lines.append("</ul>"); in_ul = False
            html_lines.append(
                f'<p style="margin:0.5rem 0;line-height:1.7;">{apply_inline(stripped)}</p>'
            )

    if in_ul:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


# ── Enveloppe HTML du mail ────────────────────────────────────────────────────

def split_report(report_md: str) -> tuple[str, str]:
    """Sépare le rapport lisible des blocs HTML à coller dans index.html."""
    marker_start = "<!-- ========== BLOCS HTML À COLLER DANS index.html =========="
    marker_end   = "<!-- ========== FIN DES BLOCS HTML =========="
    if marker_start in report_md:
        parts = report_md.split(marker_start, 1)
        rapport_part = parts[0].strip()
        html_part = marker_start + parts[1]
        if marker_end in html_part:
            html_part = html_part[:html_part.index(marker_end) + len(marker_end) + 4]
        return rapport_part, html_part
    return report_md, ""


def build_email_html(report_md: str, mois_annee: str, search_count: int) -> str:
    rapport_part, html_part = split_report(report_md)
    report_html = markdown_to_html(rapport_part)

    badge = (
        f'<span style="background:rgba(255,255,255,0.25);color:#fff;'
        f'font-size:0.72rem;padding:3px 10px;border-radius:100px;'
        f'font-weight:700;letter-spacing:0.05em;">'
        f'🔍 {search_count} recherche{"s" if search_count > 1 else ""} web effectuée{"s" if search_count > 1 else ""}'
        f'</span>'
    )

    # Section blocs HTML si présente
    if html_part:
        html_section = f"""
    <!-- Section blocs HTML -->
    <div style="background:#1e1e2e;border-radius:0 0 10px 10px;padding:24px 32px;">
      <p style="margin:0 0 12px;font-size:0.8rem;font-weight:700;color:#a0a0c0;
                letter-spacing:0.1em;text-transform:uppercase;">
        ✂ Blocs HTML prêts à coller dans index.html
      </p>
      <p style="margin:0 0 14px;font-size:0.75rem;color:#8888aa;">
        Dans votre dépôt GitHub, ouvrez <code style="background:#2d2d44;padding:1px 5px;
        border-radius:3px;color:#c9d1d9;">index.html</code> → cherchez
        <code style="background:#2d2d44;padding:1px 5px;border-radius:3px;color:#c9d1d9;">
        id="veilleTrack"</code> → collez les blocs ci-dessous en PREMIER (avant les autres cartes).
        Ajoutez aussi une ligne &lt;option&gt; dans le &lt;select&gt; des mois.
      </p>
      <pre style="margin:0;padding:16px;background:#13131f;border-radius:8px;
                  font-family:monospace;font-size:0.72rem;color:#e2e8f0;
                  white-space:pre-wrap;word-break:break-word;line-height:1.6;
                  border:1px solid #333355;overflow-x:auto;">{html_part}</pre>
    </div>"""
    else:
        html_section = ""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Veille Souveraineté Numérique – {mois_annee}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Georgia,serif;">

  <div style="max-width:680px;margin:30px auto;background:#fff;border-radius:10px;
              overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);">

    <div style="background:linear-gradient(135deg,#667eea,#d48236);
                padding:28px 32px;text-align:center;">
      <p style="margin:0;color:rgba(255,255,255,0.8);font-size:0.8rem;
                letter-spacing:0.12em;text-transform:uppercase;">
        Veille Technologique BTS SIO SISR
      </p>
      <h1 style="margin:6px 0 4px;color:#fff;font-size:1.6rem;font-weight:700;">
        Souveraineté Numérique
      </h1>
      <p style="margin:0 0 10px;color:rgba(255,255,255,0.9);font-size:1rem;">
        Rapport mensuel — {mois_annee}
      </p>
      {badge}
    </div>

    <div style="background:#f0f4ff;border-left:4px solid #667eea;
                padding:10px 20px;font-size:0.8rem;color:#555;">
      ✅ Ce rapport est basé sur des <strong>actualités réelles</strong> recherchées
      en temps réel sur des sources institutionnelles et spécialisées françaises/européennes.
    </div>

    <div style="padding:28px 32px;color:#333;font-size:0.93rem;line-height:1.7;">
      {report_html}
    </div>

    <div style="background:#f8f8f8;border-top:1px solid #eee;
                padding:16px 32px;text-align:center;">
      <p style="margin:0;font-size:0.75rem;color:#aaa;">
        Rapport généré via Claude {MODEL} avec Web Search Anthropic ·
        Portfolio Tom Omnès · BTS SIO SISR
      </p>
    </div>

    {html_section}

  </div>
</body>
</html>"""


# ── Envoi SMTP ────────────────────────────────────────────────────────────────

def send_email(html_body: str, mois_annee: str) -> None:
    email_from     = os.environ["EMAIL_FROM"]
    email_to_raw   = os.environ["EMAIL_TO"]
    email_password = os.environ["EMAIL_PASSWORD"]
    recipients     = [e.strip() for e in email_to_raw.split(",")]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔐 Veille Souveraineté Numérique – {mois_annee} (sources réelles)"
    msg["From"]    = email_from
    msg["To"]      = ", ".join(recipients)

    plain = (
        f"Rapport de veille – Souveraineté Numérique – {mois_annee}\n\n"
        "Ce rapport a été généré avec le Web Search Anthropic (sources réelles).\n"
        "Consultez-le dans un client mail compatible HTML."
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"[INFO] Envoi via SMTP Gmail...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(email_from, email_password)
        server.sendmail(email_from, recipients, msg.as_string())

    print(f"[OK]   Mail envoyé à : {', '.join(recipients)}")


# ── Point d'entrée ────────────────────────────────────────────────────────────

def main() -> None:
    required_vars = ["ANTHROPIC_API_KEY", "EMAIL_FROM", "EMAIL_TO", "EMAIL_PASSWORD"]
    missing = [v for v in required_vars if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(f"Variables manquantes : {', '.join(missing)}")

    today = datetime.date.today()
    mois_fr = {
        "January":"Janvier","February":"Février","March":"Mars",
        "April":"Avril","May":"Mai","June":"Juin",
        "July":"Juillet","August":"Août","September":"Septembre",
        "October":"Octobre","November":"Novembre","December":"Décembre",
    }
    mois_annee = f"{mois_fr.get(today.strftime('%B'), today.strftime('%B'))} {today.year}"
    mois_iso = today.strftime("%Y-%m")

    print(f"[INFO] Rapport pour : {mois_annee}")
    print(f"[INFO] Modèle : {MODEL} | Web Search activé | Max {MAX_SEARCHES} requêtes")
    print(f"[INFO] Domaines autorisés : {len(ALLOWED_DOMAINS)} sources de confiance")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # 1. Générer le rapport avec recherches web réelles
    print("[INFO] Lancement des recherches et génération du rapport...")
    report_md, search_count = generate_report_with_search(client, mois_annee, mois_iso)
    print(f"[INFO] Rapport généré — {search_count} recherche(s) web, {len(report_md)} caractères")

    # 2. Construire le HTML
    html_body = build_email_html(report_md, mois_annee, search_count)

    # 3. Envoyer
    send_email(html_body, mois_annee)
    print("[DONE] Pipeline terminé avec succès.")


if __name__ == "__main__":
    main()
