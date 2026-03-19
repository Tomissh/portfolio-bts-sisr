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
MAX_TOKENS = 6000   # rapport détaillé complet
MAX_TOKENS_CARTES = 3000  # fiches cartes seules
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
Règles IMPÉRATIVES :
- Ne rédige QUE des informations trouvées via tes recherches web. Pas d'inventions.
- Chaque chiffre et exemple DOIT provenir d'un article réel trouvé lors des recherches.
- Les URLs doivent être les liens directs vers les articles, pas les pages d'accueil.
- Si des chiffres ou exemples ne sont pas disponibles, indique :
  "Données chiffrées non disponibles dans les sources consultées."
- Niveau de langue : soutenu mais accessible à un lycéen en section technique.
- Réponds UNIQUEMENT avec le contenu du rapport, sans phrase d'intro ni de conclusion.
- Les titres, dates, sources et URLs doivent être exacts et vérifiables.
"""




def build_prompt_cartes(rapport_md: str, mois_iso: str) -> str:
    """Prompt secondaire : génère uniquement les fiches cartes à partir du rapport."""
    return f"""Tu as rédigé le rapport de veille ci-dessous.
Tu dois maintenant générer une fiche structurée pour CHAQUE actualité du rapport
(section "Actualités clés"), sans en omettre aucune.

RAPPORT :
{rapport_md}

---
Génère les fiches en commençant par exactement :
===DEBUT_CARTES===

Pour CHAQUE actualité, génère une fiche avec CE FORMAT EXACT.
Sépare chaque fiche par ---CARTE--- :

THEMES: [1 ou 2 valeurs parmi : RGPD Cloud IA Cyber Réglementation Identité Infra]
MOIS: {mois_iso}
SOURCE: [nom de la source]
DATE: [JJ mois AAAA en français]
LIEN: [URL de l'article]
TITRE: [titre de l'article]
RESUME_COURT: [2 phrases maximum pour donner envie de cliquer]
DETAIL_DEBUT
[résumé détaillé tel qu'il apparaît dans le rapport, avec les chiffres et exemples]
DETAIL_FIN

---CARTE---

Termine par exactement :
===FIN_CARTES===

Règles :
- Une fiche par actualité du rapport, TOUTES les actualités.
- RESUME_COURT : maximum 2 phrases, accessible, sans jargon.
- DETAIL_DEBUT...DETAIL_FIN : copie fidèle du résumé détaillé du rapport.
- Réponds UNIQUEMENT avec les fiches, rien d'autre.
"""

# ── Appel API Claude avec Web Search ─────────────────────────────────────────

def generate_report_with_search(client: anthropic.Anthropic, mois_annee: str, mois_iso: str) -> tuple[str, str, int]:
    """
    Appel 1 : rapport complet avec web search.
    Appel 2 : fiches cartes sans web search (à partir du rapport).
    Retourne (rapport_markdown, cartes_raw, search_count).
    """
    # ── Appel 1 : rapport avec web search ────────────────────────────────────
    prompt = build_prompt(mois_annee, mois_iso)

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": MAX_SEARCHES,
            "allowed_domains": ALLOWED_DOMAINS,
        }],
        messages=[{"role": "user", "content": prompt}],
    )

    search_count = 0
    rapport_md = ""

    for block in message.content:
        if block.type == "text":
            rapport_md += block.text
        elif hasattr(block, "type") and block.type == "server_tool_use":
            if block.name == "web_search":
                search_count += 1
                print(f"[SEARCH #{search_count}] Requête : {block.input.get('query', '?')}")

    if hasattr(message, "usage") and hasattr(message.usage, "server_tool_use"):
        search_count = getattr(message.usage.server_tool_use, "web_search_requests", search_count)

    rapport_md = rapport_md.strip()
    print(f"[INFO] Rapport généré ({len(rapport_md)} caractères, {search_count} recherche(s))")

    # ── Appel 2 : fiches cartes sans web search ───────────────────────────────
    print("[INFO] Génération des fiches cartes...")
    prompt_cartes = build_prompt_cartes(rapport_md, mois_iso)

    message2 = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_CARTES,
        messages=[{"role": "user", "content": prompt_cartes}],
    )

    cartes_raw = ""
    for block in message2.content:
        if block.type == "text":
            cartes_raw += block.text

    cartes_raw = cartes_raw.strip()
    print(f"[INFO] Fiches cartes générées ({len(cartes_raw)} caractères)")

    return rapport_md, cartes_raw, search_count


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

def parse_cartes(cartes_raw: str) -> list[dict]:
    """
    Parse le texte brut des fiches cartes généré par le second appel API.
    Retourne une liste de dicts avec les clés :
      themes, mois, source, date, lien, titre, resume_court, detail
    Robuste aux variations de formatage (espaces, casse, marqueurs absents).
    """
    # Extraire uniquement ce qui est entre les marqueurs si présents
    if "===DEBUT_CARTES===" in cartes_raw:
        cartes_raw = cartes_raw.split("===DEBUT_CARTES===", 1)[1]
    if "===FIN_CARTES===" in cartes_raw:
        cartes_raw = cartes_raw.split("===FIN_CARTES===", 1)[0]

    # Séparer les blocs — accepte ---CARTE---, --- CARTE ---, ou ligne vide multiple
    import re as _re
    blocs = _re.split(r"-{2,}\s*CARTE\s*-{2,}|\n{3,}", cartes_raw)

    cartes = []
    for bloc in blocs:
        bloc = bloc.strip()
        if not bloc:
            continue
        carte = {}

        # Extraire DETAIL entre DETAIL_DEBUT et DETAIL_FIN (robuste aux variantes)
        detail_match = _re.search(
            r"DETAIL_DEBUT\s*\n(.*?)\n?DETAIL_FIN",
            bloc, _re.DOTALL | _re.IGNORECASE
        )
        if detail_match:
            carte["detail"] = detail_match.group(1).strip()
            bloc = bloc[:detail_match.start()] + bloc[detail_match.end():]
        else:
            carte["detail"] = ""

        # Parser les champs clé: valeur ligne par ligne
        # Supporte aussi les multi-lignes pour RESUME_COURT
        current_key = None
        current_val = []
        for line in bloc.splitlines():
            m = _re.match(r"^(THEMES|MOIS|SOURCE|DATE|LIEN|TITRE|RESUME_COURT):\s*(.*)", line, _re.IGNORECASE)
            if m:
                if current_key:
                    carte[current_key] = " ".join(current_val).strip()
                current_key = m.group(1).upper()
                current_val = [m.group(2).strip()] if m.group(2).strip() else []
            elif current_key and line.strip():
                current_val.append(line.strip())
        if current_key:
            carte[current_key.lower()] = " ".join(current_val).strip()

        # Normaliser les clés en minuscules
        carte = {k.lower(): v for k, v in carte.items()}

        if carte.get("titre"):
            cartes.append(carte)

    return cartes


def cartes_to_html_blocks(cartes: list[dict]) -> str:
    """Convertit la liste de cartes en blocs HTML prêts à coller."""
    if not cartes:
        return ""
    out = []
    out.append("<!-- Coller ces blocs dans index.html, dans id=\"veilleTrack\", AVANT les autres cartes -->\n\n")
    for c in cartes:
        themes = c.get("themes", "")
        mois   = c.get("mois", "")
        source = c.get("source", "")
        date   = c.get("date", "")
        lien   = c.get("lien", "#")
        titre  = c.get("titre", "")
        court  = c.get("resume_court", "")
        # Escape double quotes in detail to avoid breaking the HTML attribute
        detail = c.get("detail", "").replace('"', "“").replace("'", "’")

        tag_lines = ""
        for th in themes.split():
            tag_lines += f'    <span class="tag" data-theme="{th}">{th}</span>\n'

        bloc = (
            '<article class="veille-card"\n'
            f'  data-themes="{themes}"\n'
            f'  data-mois="{mois}"\n'
            f'  data-detail="{detail}"\n'
            f'  data-link="{lien}"\n'
            f'  data-link-label="Lire sur {source}">\n'
            f'  <div class="veille-meta">\n'
            f'    <span class="veille-source">{source}</span>\n'
            f'    <span>{date}</span>\n'
            f'  </div>\n'
            f'  <h4>{titre}</h4>\n'
            f'  <p class="veille-short">{court}</p>\n'
            f'  <span class="veille-hint">Cliquer pour lire l\'article complet</span>\n'
            f'  <div class="veille-tags">\n'
            f'{tag_lines}'
            f'  </div>\n'
            f'</article>\n\n'
        )
        out.append(bloc)

    out.append("<!-- Ne pas oublier d\'ajouter dans <select id=\"filterMois\"> :\n")
    out.append("  <option value=\"mois-AAAA-MM\">Mois AAAA</option> -->\n")
    return "".join(out)

def build_email_html(rapport_md: str, cartes_raw: str, mois_annee: str, search_count: int) -> tuple[str, str]:
    """
    Retourne (html_du_mail, contenu_txt_piece_jointe).
    La pièce jointe .txt contient les blocs HTML prêts à coller.
    """
    cartes = parse_cartes(cartes_raw)
    report_html = markdown_to_html(rapport_md)
    txt_attachment = cartes_to_html_blocks(cartes)
    nb_cartes = len(cartes)

    badge = (
        f'<span style="background:rgba(255,255,255,0.25);color:#fff;'
        f'font-size:0.72rem;padding:3px 10px;border-radius:100px;'
        f'font-weight:700;letter-spacing:0.05em;">'
        f'🔍 {search_count} recherche{"s" if search_count > 1 else ""} web · '
        f'{nb_cartes} carte{"s" if nb_cartes > 1 else ""} générée{"s" if nb_cartes > 1 else ""}'
        f'</span>'
    )

    if nb_cartes:
        bandeau_cartes = f"""
    <div style="background:#f0f7ee;border-left:4px solid #2b8a3e;
                padding:12px 20px;font-size:0.82rem;color:#2b5a1e;">
      📎 <strong>{nb_cartes} carte{"s" if nb_cartes > 1 else ""} générée{"s" if nb_cartes > 1 else ""}</strong>
      — Les blocs HTML à coller dans <code>index.html</code> sont joints en pièce jointe
      (<code>cartes_veille.txt</code>). Ouvrez ce fichier, copiez son contenu et
      collez-le dans <code>id="veilleTrack"</code> AVANT les autres cartes.
      Ajoutez aussi une ligne &lt;option&gt; dans le &lt;select&gt; des mois.
    </div>"""
    else:
        bandeau_cartes = """
    <div style="background:#fff3e0;border-left:4px solid #e65100;
                padding:12px 20px;font-size:0.82rem;color:#7f3b00;">
      ⚠️ Aucune fiche carte générée ce mois-ci (données insuffisantes dans les sources).
    </div>"""

    html = f"""<!DOCTYPE html>
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

    {bandeau_cartes}

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

  </div>
</body>
</html>"""
    return html, txt_attachment


# ── Envoi SMTP ────────────────────────────────────────────────────────────────

def send_email(html_body: str, txt_attachment: str, mois_annee: str) -> None:
    """Envoie le rapport HTML avec la pièce jointe .txt des blocs HTML."""
    from email.mime.base import MIMEBase
    from email import encoders

    email_from     = os.environ["EMAIL_FROM"]
    email_to_raw   = os.environ["EMAIL_TO"]
    email_password = os.environ["EMAIL_PASSWORD"]
    recipients     = [e.strip() for e in email_to_raw.split(",")]

    # MIMEMultipart "mixed" pour supporter pièces jointes
    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"🔐 Veille Souveraineté Numérique – {mois_annee}"
    msg["From"]    = email_from
    msg["To"]      = ", ".join(recipients)

    # Corps HTML dans une sous-partie "alternative"
    body_part = MIMEMultipart("alternative")
    plain = (
        f"Rapport de veille – Souveraineté Numérique – {mois_annee}\n\n"
        "Ce rapport a été généré avec le Web Search Anthropic.\n"
        "Consultez-le dans un client mail compatible HTML.\n"
        "Les blocs HTML pour le portfolio sont en pièce jointe (cartes_veille.txt)."
    )
    body_part.attach(MIMEText(plain, "plain", "utf-8"))
    body_part.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body_part)

    # Pièce jointe .txt si des cartes ont été générées
    if txt_attachment:
        filename = f"cartes_veille_{mois_annee.replace(' ', '_')}.txt"
        att = MIMEBase("text", "plain")
        att.set_payload(txt_attachment.encode("utf-8"))
        encoders.encode_base64(att)
        att.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(att)
        print(f"[INFO] Pièce jointe : {filename}")

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
    rapport_md, cartes_raw, search_count = generate_report_with_search(client, mois_annee, mois_iso)

    # 2. Construire le HTML + extraire la pièce jointe cartes
    html_body, txt_attachment = build_email_html(rapport_md, cartes_raw, mois_annee, search_count)
    print(f"[INFO] {len(txt_attachment)} caractères de blocs HTML générés pour la pièce jointe")

    # 3. Envoyer
    send_email(html_body, txt_attachment, mois_annee)
    print("[DONE] Pipeline terminé avec succès.")


if __name__ == "__main__":
    main()
