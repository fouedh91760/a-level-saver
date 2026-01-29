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
HUMANIZE_SYSTEM_PROMPT = """Tu es un assistant qui reformule des emails professionnels pour les rendre plus naturels et humains.

RÈGLES STRICTES - NE JAMAIS MODIFIER :
- Les dates (ex: 31/03/2026, 27/02/2026)
- Les liens URL (ex: https://cab-formations.fr)
- Les adresses email
- Les identifiants et mots de passe
- Les noms propres
- Les montants (ex: 241€)
- Le contenu des balises HTML <a>, <b>, <i>

CE QUE TU DOIS FAIRE :
1. Fusionner les sections qui traitent du même sujet
2. Ajouter des transitions naturelles entre les idées
3. Supprimer les répétitions de structure "Concernant X"
4. Rendre le ton chaleureux mais professionnel
5. Garder le message concis et direct
6. Conserver le format HTML pour la mise en forme

CE QUE TU NE DOIS PAS FAIRE :
- Inventer des informations
- Supprimer des informations importantes
- Changer le sens du message
- Ajouter des promesses ou engagements
- Modifier les données factuelles

FORMAT DE SORTIE : Retourne UNIQUEMENT le texte reformulé en HTML, sans commentaires."""


def humanize_response(
    template_response: str,
    candidate_message: str,
    candidate_name: str = "",
    use_ai: bool = True
) -> Dict[str, Any]:
    """
    Humanise une réponse générée par le template engine.

    Args:
        template_response: La réponse HTML générée par le template engine
        candidate_message: Le dernier message du candidat (pour contexte)
        candidate_name: Prénom du candidat
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

        # Construire le prompt utilisateur
        user_prompt = f"""Voici un email de réponse à reformuler pour le rendre plus naturel et humain.

MESSAGE DU CANDIDAT (pour contexte) :
{candidate_message[:500]}

RÉPONSE À REFORMULER :
{template_response}

Reformule cette réponse pour qu'elle soit plus fluide et naturelle, en respectant strictement les règles données."""

        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
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
