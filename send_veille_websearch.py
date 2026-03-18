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
MAX_TOKENS = 3000   # plus élevé car le modèle raisonne + cherche + rédige
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

def build_prompt(mois_annee: str) -> str:
    return f"""Tu es un expert en souveraineté numérique et en droit du numérique européen.
Tu dois produire un rapport mensuel de veille technologique destiné à un étudiant
en 1ère année de BTS SIO option SISR (niveau lycée technique).

Mois du rapport : {mois_annee}

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
3 à 4 lignes résumant le contexte global basé sur les actualités trouvées.

## 2. Actualités clés (3 à 5 items, uniquement des faits réels trouvés)
Pour chaque actualité :
### [Titre exact de l'actualité]
**Source :** [Source réelle] | **Date :** [Date réelle]
**Résumé :** 5 à 8 lignes accessibles niveau BTS, rigoureuses et précises.
**Lien SISR :** en quoi cela concerne la sécurité, les infrastructures ou la réglementation côté technicien.
**Contexte :** comparaison Europe / France / reste du monde si pertinent.

## 3. Chiffre ou stat du mois
Une donnée marquante et réelle trouvée dans tes recherches (avec la source).

## 4. À surveiller le mois prochain
1 à 2 échéances ou tendances réelles à venir.

---
Règles IMPÉRATIVES :
- Ne rédige QUE des informations trouvées via tes recherches web. Pas d'inventions.
- Si une information n'est pas trouvée, indique clairement "Information non disponible ce mois".
- Niveau de langue : soutenu mais accessible à un lycéen en section technique.
- Réponds UNIQUEMENT avec le contenu du rapport, sans phrase d'intro ni de conclusion.
- Les titres, dates et sources doivent être exacts et vérifiables.
"""


# ── Appel API Claude avec Web Search ─────────────────────────────────────────

def generate_report_with_search(client: anthropic.Anthropic, mois_annee: str) -> tuple[str, int]:
    """
    Appelle Claude Haiku avec le web search tool activé.
    Retourne (rapport_markdown, nombre_de_recherches_effectuées).
    """
    prompt = build_prompt(mois_annee)

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

def build_email_html(report_md: str, mois_annee: str, search_count: int) -> str:
    report_html = markdown_to_html(report_md)
    badge = (
        f'<span style="background:rgba(255,255,255,0.25);color:#fff;'
        f'font-size:0.72rem;padding:3px 10px;border-radius:100px;'
        f'font-weight:700;letter-spacing:0.05em;">'
        f'🔍 {search_count} recherche{"s" if search_count > 1 else ""} web effectuée{"s" if search_count > 1 else ""}'
        f'</span>'
    )
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

    <!-- Bandeau "sources vérifiées" -->
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
      <p style="margin:4px 0 0;font-size:0.75rem;color:#aaa;">
        Sources vérifiées · Domaines autorisés : anssi.gouv.fr, cnil.fr, europa.eu et sources tech FR
      </p>
    </div>

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

    print(f"[INFO] Rapport pour : {mois_annee}")
    print(f"[INFO] Modèle : {MODEL} | Web Search activé | Max {MAX_SEARCHES} requêtes")
    print(f"[INFO] Domaines autorisés : {len(ALLOWED_DOMAINS)} sources de confiance")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # 1. Générer le rapport avec recherches web réelles
    print("[INFO] Lancement des recherches et génération du rapport...")
    report_md, search_count = generate_report_with_search(client, mois_annee)
    print(f"[INFO] Rapport généré — {search_count} recherche(s) web, {len(report_md)} caractères")

    # 2. Construire le HTML
    html_body = build_email_html(report_md, mois_annee, search_count)

    # 3. Envoyer
    send_email(html_body, mois_annee)
    print("[DONE] Pipeline terminé avec succès.")


if __name__ == "__main__":
    main()
