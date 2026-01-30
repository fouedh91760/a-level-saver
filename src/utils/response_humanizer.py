"""
Response Humanizer - Transforme les réponses templates en texte naturel.

Ce module prend la sortie structurée du TemplateEngine et la reformule
pour la rendre plus humaine et fluide, tout en préservant strictement
les informations factuelles (dates, liens, identifiants, etc.).
"""

import logging
import re
from typing import Dict, Any, Optional

import anthropic

logger = logging.getLogger(__name__)

# Prompt système pour l'humanisation
HUMANIZE_SYSTEM_PROMPT = """Tu reformules des emails professionnels pour les rendre naturels et chaleureux.

RÈGLE D'OR : Tu ne fais que REFORMULER. Tu n'ajoutes AUCUNE information qui n'est pas déjà présente.

PRÉSERVER EXACTEMENT (ne jamais modifier) :
- Les dates (31/03/2026, 27/02/2026, etc.)
- Les URLs et liens
- Les adresses email
- Les identifiants/mots de passe
- Les montants
- Les numéros de département et CMA (CMA 34, CMA 75, département 67, etc.)
- Les noms de région

PRÉSERVER OBLIGATOIREMENT (structure et contenu) :
- Les listes de dates alternatives dans d'autres départements
- Les sections "Dans votre région" et "Dans d'autres régions"
- Toute mention de dates disponibles ailleurs (même si le candidat n'a pas de date dans son département)

CE QUE TU FAIS :
1. Fusionner les sections redondantes en un texte fluide
2. Supprimer les répétitions de structure "Concernant X"
3. Ajouter des transitions naturelles
4. Rendre le ton chaleureux mais professionnel
5. Répondre dans l'ordre logique aux questions du candidat
6. Garder le HTML (<b>, <br>, <a href>)

NOMS DE SESSION INTERNES (à remplacer) :
- Les noms techniques comme "cds-montreuil-thu2", "cdj-paris-wed1", "CDS Montreuil", etc. sont des codes INTERNES
- REMPLACE-LES par une description claire : "cours du soir" ou "cours du jour" + les dates
- Exemple : "session cds-montreuil-thu2 du 13/04 au 24/04" → "session de cours du soir du 13/04 au 24/04"
- Ne JAMAIS afficher "cds", "cdj", "CDS", "CDJ" ou des noms de ville associés aux sessions

CE QUE TU NE FAIS PAS :
- Inventer des informations ou des explications
- Ajouter des promesses ou engagements ("nous vous tiendrons informé", "en cas de désistement", etc.)
- Inventer des raisons quand une date n'est pas disponible (si pas mentionné = ne pas expliquer)
- Ajouter des explications métier qui ne sont pas dans l'original
- Supprimer des informations importantes
- Supprimer les dates alternatives d'autres départements
- Afficher des noms de session internes (cds-*, cdj-*, CDS, CDJ)

EXEMPLES D'ERREURS À ÉVITER :
- ❌ "nous vous tiendrons informé en cas de désistement" (promesse inventée)
- ❌ "si une place se libère" (hypothèse inventée)
- ✅ Si le candidat demande une date qui n'est pas proposée, ne PAS expliquer pourquoi - ignorer simplement

FORMAT : Retourne UNIQUEMENT l'email reformulé en HTML."""


def humanize_response(
    template_response: str,
    candidate_message: str,
    candidate_name: str = "",
    previous_response: str = "",
    use_ai: bool = True
) -> Dict[str, Any]:
    """
    Humanise une réponse générée par le template engine.

    Args:
        template_response: La réponse HTML générée par le template engine
        candidate_message: Le dernier message du candidat (pour contexte)
        candidate_name: Prénom du candidat
        previous_response: Notre précédent message au candidat (pour éviter répétitions)
        use_ai: Si True, utilise l'IA pour humaniser. Sinon retourne tel quel.

    Returns:
        {
            'humanized_response': str,  # La réponse humanisée
            'original_response': str,   # La réponse originale
            'was_humanized': bool,      # True si l'IA a été utilisée
        }
    """
    if not use_ai:
        return {
            'humanized_response': template_response,
            'original_response': template_response,
            'was_humanized': False,
        }

    try:
        client = anthropic.Anthropic()

        # Construire le contexte du message précédent si disponible
        previous_context = ""
        if previous_response:
            previous_context = f"""
NOTRE PRÉCÉDENT MESSAGE AU CANDIDAT (éviter de répéter ces infos) :
{previous_response[:1000]}

"""

        # Construire le prompt utilisateur
        user_prompt = f"""Reformule cet email pour le rendre naturel et fluide.
{previous_context}
MESSAGE DU CANDIDAT (contexte) :
{candidate_message[:800]}

EMAIL À REFORMULER :
{template_response}

Fusionne les sections, ajoute des transitions naturelles, garde toutes les informations factuelles.
{"IMPORTANT : Évite de répéter les informations déjà communiquées dans notre précédent message." if previous_response else ""}"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=HUMANIZE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        humanized = response.content[0].text.strip()

        # Validation : vérifier que les données critiques sont préservées
        validation_result = _validate_humanized_response(template_response, humanized)

        if not validation_result['valid']:
            logger.warning(f"Humanization validation failed: {validation_result['issues']}")
            logger.warning("Falling back to template response")
            return {
                'humanized_response': template_response,
                'original_response': template_response,
                'was_humanized': False,
                'validation_failed': True,
                'validation_issues': validation_result['issues'],
            }

        logger.info("✅ Response humanized successfully")
        return {
            'humanized_response': humanized,
            'original_response': template_response,
            'was_humanized': True,
        }

    except Exception as e:
        logger.error(f"Error humanizing response: {e}")
        return {
            'humanized_response': template_response,
            'original_response': template_response,
            'was_humanized': False,
            'error': str(e),
        }


def _validate_humanized_response(original: str, humanized: str) -> Dict[str, Any]:
    """
    Valide que la réponse humanisée préserve les données critiques.

    Returns:
        {'valid': bool, 'issues': List[str]}
    """
    issues = []

    # Extraire les dates du format DD/MM/YYYY
    date_pattern = r'\d{2}/\d{2}/\d{4}'
    original_dates = set(re.findall(date_pattern, original))
    humanized_dates = set(re.findall(date_pattern, humanized))

    missing_dates = original_dates - humanized_dates
    if missing_dates:
        issues.append(f"Dates manquantes: {missing_dates}")

    # Extraire les URLs
    url_pattern = r'https?://[^\s<>"\']+(?=[<\s"\']|$)'
    original_urls = set(re.findall(url_pattern, original))
    humanized_urls = set(re.findall(url_pattern, humanized))

    missing_urls = original_urls - humanized_urls
    if missing_urls:
        issues.append(f"URLs manquantes: {missing_urls}")

    # Extraire les emails
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    original_emails = set(re.findall(email_pattern, original))
    humanized_emails = set(re.findall(email_pattern, humanized))

    missing_emails = original_emails - humanized_emails
    if missing_emails:
        issues.append(f"Emails manquants: {missing_emails}")

    # Extraire les numéros CMA/département (cross-département)
    # Pattern: "CMA 34", "CMA 75", "CMA 06", etc.
    cma_pattern = r'CMA\s*\d{1,3}'
    original_cmas = set(re.findall(cma_pattern, original, re.IGNORECASE))
    humanized_cmas = set(re.findall(cma_pattern, humanized, re.IGNORECASE))

    missing_cmas = original_cmas - humanized_cmas
    if missing_cmas:
        issues.append(f"CMA manquants: {missing_cmas}")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
    }


def quick_humanize(template_response: str) -> str:
    """
    Version simplifiée qui fait juste un nettoyage basique sans IA.
    Utile pour les cas où on veut éviter le coût/latence de l'IA.
    """
    result = template_response

    # Supprimer les lignes vides multiples
    result = re.sub(r'(<br>\s*){3,}', '<br><br>', result)

    # Supprimer les espaces avant <br>
    result = re.sub(r'\s+<br>', '<br>', result)

    return result
