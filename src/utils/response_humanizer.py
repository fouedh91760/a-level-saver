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

RÈGLE D'OR ABSOLUE : Tu ne fais que REFORMULER le contenu de l'EMAIL À REFORMULER.
Tu n'ajoutes AUCUNE information basée sur le message du candidat ou l'historique.

INTERDIT - NE JAMAIS FAIRE (CRITIQUE) :
- NE JAMAIS mentionner "changement de date", "report", "modification de date" sauf si ces mots sont EXPLICITEMENT dans l'email à reformuler
- NE JAMAIS INVENTER d'informations qui ne sont pas dans l'email
- NE JAMAIS ajouter de promesses ou engagements non présents dans l'email
- NE JAMAIS utiliser de dates qui ne sont PAS dans l'email à reformuler (ex: ne pas inventer 12/01/2026 si ce n'est pas dans l'email)
- NE JAMAIS transformer une PROPOSITION en CONFIRMATION (si l'email dit "Voici les alternatives", tu ne dois PAS dire "Nous avons enregistré votre choix")
- NE JAMAIS supprimer une liste d'options/alternatives proposées dans l'email
- Le message du candidat sert à STRUCTURER la réponse (répondre d'abord à sa question), PAS à créer du contenu
- Le message du candidat peut contenir des dates DIFFÉRENTES de celles de l'email - utilise UNIQUEMENT les dates de l'email
- NE JAMAIS utiliser les HORAIRES du message du candidat - le candidat peut se tromper ! Utilise UNIQUEMENT les horaires de l'email à reformuler (8h30-17h30 pour cours du jour, 18h-22h pour cours du soir)

CLARIFICATION : Tu PEUX utiliser le message du candidat pour :
- Identifier sa question principale et y répondre EN PREMIER avec les infos de l'email
- Réorganiser les sections pour que la réponse soit logique par rapport à sa demande
- Formuler une réponse directe (oui/non) si l'email contient l'information

PRÉSERVER EXACTEMENT (ne jamais modifier) :
- TOUTES les dates au format DD/MM/YYYY (31/03/2026, 27/02/2026, 10/05/2026, etc.)
- Les dates de CLÔTURE d'inscription (CRITIQUE - ne JAMAIS les supprimer)
- Les URLs et liens
- Les adresses email
- Les identifiants/mots de passe
- Les montants
- Les numéros de département et CMA (CMA 34, CMA 75, département 67, etc.)
- Les noms de région
- Les HORAIRES DE FORMATION : "8h30-17h30" (jour) et "18h-22h" (soir) - NE JAMAIS modifier ces horaires

DATES DE CLÔTURE (CRITIQUE) :
- Chaque date d'examen a une date de clôture d'inscription associée
- Format typique : "26/05/2026 (clôture : 10/05/2026)"
- Tu DOIS conserver TOUTES les dates de clôture mentionnées dans l'email original
- Si l'email dit "clôture : 10/05/2026", cette date DOIT apparaître dans ta reformulation
- La suppression d'une date de clôture est une ERREUR GRAVE

PRÉSERVER OBLIGATOIREMENT (structure et contenu) :
- Les listes de dates alternatives dans d'autres départements
- Les sections "Dans votre région" et "Dans d'autres régions"
- Toute mention de dates disponibles ailleurs (même si le candidat n'a pas de date dans son département)
- TOUTES les options de session (cours du jour ET cours du soir) pour CHAQUE date d'examen
- TOUTES les dates de clôture associées aux dates d'examen

ALTERNATIVES ET PROPOSITIONS (CRITIQUE) :
Si l'email contient "Voici les alternatives disponibles" ou "Voici les sessions disponibles" ou toute liste de choix :
- C'est une PROPOSITION, pas une confirmation
- Tu DOIS conserver TOUTES les options listées avec leurs dates exactes
- Tu ne dois PAS résumer ou réduire la liste
- Tu ne dois PAS dire "Nous avons bien enregistré" ou "Votre choix est confirmé"
- La réponse doit rester une PROPOSITION demandant au candidat de CONFIRMER son choix
- Exemple CORRECT : "Voici les sessions disponibles : ... Merci de nous confirmer votre choix"
- Exemple INCORRECT : "Nous avons bien noté votre choix de session du..."

CE QUE TU FAIS :
1. Fusionner les sections redondantes en un texte fluide
2. Supprimer les répétitions de structure "Concernant X"
3. Ajouter des transitions naturelles
4. Rendre le ton chaleureux mais professionnel
5. **SI LE CANDIDAT POSE UNE QUESTION DIRECTE** : Répondre d'abord à sa question avec les infos de l'email, puis donner le reste
6. Garder le HTML (<b>, <br>, <a href>)

RÉPONDRE AUX QUESTIONS DIRECTES (IMPORTANT) :
Si le candidat pose une question claire (ex: "Puis-je faire X ?", "Est-ce que Y est possible ?"), et que l'email contient la réponse :
- Commence par répondre directement OUI ou NON avec explication
- Puis enchaîne avec le reste des informations
- Tu ne CRÉES pas d'info, tu RÉORGANISES ce qui est dans l'email pour répondre à la question

Exemple :
- Question candidat : "Puis-je passer l'examen avec mon permis marocain ?"
- Email contient : "Seuls les permis français ou européens sont acceptés"
- Bonne reformulation : "Malheureusement, le permis marocain ne permet pas de passer l'examen VTC. Seuls les permis français ou européens (zone Euro) sont acceptés. Vous devez d'abord obtenir votre permis français via l'échange ANTS avant de pouvoir finaliser votre inscription..."

FUSION DATES + SESSIONS (CRITIQUE) :
Si l'email contient à la fois une section "dates d'examen" et une section "sessions de formation" :
- FUSIONNE-LES en UNE SEULE section claire
- Pour chaque date d'examen, liste les deux options (jour + soir) avec leurs dates de formation
- UN SEUL appel à l'action à la fin : "Merci de nous confirmer la date et le type de session souhaités"
- SUPPRIME les explications génériques redondantes si les sessions sont déjà listées en détail

Exemple de fusion correcte :
<b>Dates d'examen et sessions disponibles</b><br>
<b>Examen du 31/03/2026</b> (clôture : 27/02/2026)<br>
&nbsp;&nbsp;→ Cours du jour : du 23/03 au 27/03<br>
&nbsp;&nbsp;→ Cours du soir : du 16/03 au 27/03<br>
<b>Examen du 28/04/2026</b> (clôture : 27/03/2026)<br>
&nbsp;&nbsp;→ Cours du jour : du 20/04 au 24/04<br>
&nbsp;&nbsp;→ Cours du soir : du 13/04 au 24/04<br>
<br>
<b>Merci de nous confirmer la date et le type de session souhaités.</b>

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
- Supprimer des informations importantes (dates, sessions, options)
- Supprimer les dates alternatives d'autres départements
- Afficher des noms de session internes (cds-*, cdj-*, CDS, CDJ)
- Garder des sections redondantes (dates ET sessions séparées = à fusionner)
- Mentionner "changement de date", "report", "modification" sauf si EXPLICITE dans l'email original
- Déduire des intentions du candidat à partir de son message - ton rôle est UNIQUEMENT de reformuler

EXEMPLES D'ERREURS À ÉVITER :
- ❌ "nous vous tiendrons informé en cas de désistement" (promesse inventée)
- ❌ "si une place se libère" (hypothèse inventée)
- ❌ Garder deux sections séparées pour dates et sessions (doit être fusionné)
- ❌ Garder deux CTAs ("confirmer la date" + "confirmer la session") → UN SEUL CTA
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

        # Extraire les dates pour le prompt de retry
        date_pattern = r'\d{2}/\d{2}/\d{4}'
        critical_dates = set(re.findall(date_pattern, template_response))

        # Retry loop (max 2 tentatives)
        max_attempts = 2
        for attempt in range(max_attempts):
            is_retry = attempt > 0

            # Prompt de base
            base_prompt = f"""Reformule cet email pour le rendre naturel et fluide.
{previous_context}
MESSAGE DU CANDIDAT (contexte) :
{candidate_message[:800]}

EMAIL À REFORMULER :
{template_response}

Fusionne les sections, ajoute des transitions naturelles, garde toutes les informations factuelles.
{"IMPORTANT : Évite de répéter les informations déjà communiquées dans notre précédent message." if previous_response else ""}"""

            # Prompt renforcé pour le retry
            if is_retry:
                dates_str = ', '.join(sorted(critical_dates))
                base_prompt += f"""

⚠️ ATTENTION CRITIQUE - TENTATIVE 2/2 :
Tu DOIS obligatoirement conserver ces dates exactes dans ta réponse : {dates_str}
Ne reformule PAS les dates, garde-les au format DD/MM/YYYY.
Tu DOIS conserver les horaires EXACTS de formation : 8h30-17h30 pour les cours du jour, 18h-22h pour les cours du soir.
NE JAMAIS modifier ces horaires (pas de "8h30 à 16h", pas de "9h-17h", etc.)."""
                logger.info(f"🔄 Retry humanization (attempt {attempt + 1}/{max_attempts}) - dates requises: {dates_str}")

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=HUMANIZE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": base_prompt}]
            )

            humanized = response.content[0].text.strip()

            # Nettoyage des sauts de ligne excessifs
            humanized = _cleanup_line_breaks(humanized)

            # Validation : vérifier que les données critiques sont préservées
            validation_result = _validate_humanized_response(template_response, humanized)

            if validation_result['valid']:
                logger.info(f"✅ Response humanized successfully (attempt {attempt + 1}/{max_attempts})")
                return {
                    'humanized_response': humanized,
                    'original_response': template_response,
                    'was_humanized': True,
                    'attempts': attempt + 1,
                }

            # Validation failed
            logger.warning(f"Humanization validation failed (attempt {attempt + 1}/{max_attempts}): {validation_result['issues']}")

            # Si c'est la dernière tentative, fallback
            if attempt == max_attempts - 1:
                logger.warning("Max attempts reached. Falling back to template response")
                return {
                    'humanized_response': template_response,
                    'original_response': template_response,
                    'was_humanized': False,
                    'validation_failed': True,
                    'validation_issues': validation_result['issues'],
                    'attempts': max_attempts,
                }

        # Should not reach here, but safety fallback
        return {
            'humanized_response': template_response,
            'original_response': template_response,
            'was_humanized': False,
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

    # URLs et emails : on laisse l'humanizer décider de les garder ou non
    # car il peut juger que certains liens sont redondants en contexte
    # (ex: lien exament3p.fr quand le candidat vient d'envoyer ses identifiants)

    # Extraire les numéros CMA/département (cross-département)
    # Pattern: "CMA 34", "CMA 75", "CMA 06", etc.
    cma_pattern = r'CMA\s*\d{1,3}'
    original_cmas = set(re.findall(cma_pattern, original, re.IGNORECASE))
    humanized_cmas = set(re.findall(cma_pattern, humanized, re.IGNORECASE))

    missing_cmas = original_cmas - humanized_cmas
    if missing_cmas:
        issues.append(f"CMA manquants: {missing_cmas}")

    # Valider les horaires de formation (CRITIQUE - ne jamais modifier)
    # Horaires fixes: 8h30-17h30 (jour), 18h-22h (soir)
    if '8h30-17h30' in original or '8h30 à 17h30' in original:
        # Vérifier que l'horaire jour est préservé
        has_jour_hours = ('8h30-17h30' in humanized or '8h30 à 17h30' in humanized or
                         '8h30-17h30' in humanized.replace(' ', '') or
                         '8 h 30' in humanized and '17 h 30' in humanized)
        if not has_jour_hours:
            issues.append("Horaires jour modifiés (doit être 8h30-17h30)")

    if '18h-22h' in original or '18h à 22h' in original:
        # Vérifier que l'horaire soir est préservé
        has_soir_hours = ('18h-22h' in humanized or '18h à 22h' in humanized or
                         '18h-22h' in humanized.replace(' ', '') or
                         '18 h' in humanized and '22 h' in humanized)
        if not has_soir_hours:
            issues.append("Horaires soir modifiés (doit être 18h-22h)")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
    }


def _cleanup_line_breaks(html: str) -> str:
    """
    Nettoie les sauts de ligne excessifs et les listes HTML.

    - Convertit <ul><li> en → bullets
    - Convertit <ol><li> en 1. 2. 3. numérotation
    - Remplace 3+ <br> consécutifs par 2
    - Supprime les <br> en début de texte
    - Supprime les <br> multiples avant la signature
    """
    result = html

    # Convertir <ul><li>...</li></ul> en → bullets
    # Pattern pour capturer le contenu de chaque <li>
    def replace_ul(match):
        content = match.group(1)
        items = re.findall(r'<li>(.*?)</li>', content, re.DOTALL | re.IGNORECASE)
        if items:
            return '<br>'.join(f'→ {item.strip()}' for item in items) + '<br>'
        return match.group(0)

    result = re.sub(r'<ul[^>]*>(.*?)</ul>', replace_ul, result, flags=re.DOTALL | re.IGNORECASE)

    # Convertir <ol><li>...</li></ol> en 1. 2. 3. numérotation
    def replace_ol(match):
        content = match.group(1)
        items = re.findall(r'<li>(.*?)</li>', content, re.DOTALL | re.IGNORECASE)
        if items:
            numbered = [f'{i+1}. {item.strip()}' for i, item in enumerate(items)]
            return '<br>'.join(numbered) + '<br>'
        return match.group(0)

    result = re.sub(r'<ol[^>]*>(.*?)</ol>', replace_ol, result, flags=re.DOTALL | re.IGNORECASE)

    # Supprimer <br> en début (après strip)
    result = re.sub(r'^(\s*<br>\s*)+', '', result)

    # Remplacer 2+ <br> consécutifs par un seul <br><br> (max 1 ligne vide)
    # Pattern: <br> suivi de whitespace/newlines et autre(s) <br>
    result = re.sub(r'(<br>\s*){2,}', '<br><br>', result)

    # Supprimer espaces/newlines avant <br>
    result = re.sub(r'\s+<br>', '<br>', result)

    # Supprimer <br> multiples avant "Bien cordialement"
    result = re.sub(r'(<br>\s*){2,}(Bien cordialement)', r'<br><br>\2', result)

    return result


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
