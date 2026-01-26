"""
Extraction d'informations des tickets pour mise à jour CRM.

Ce helper analyse les threads de tickets pour détecter les confirmations
du candidat (date d'examen, session de formation, préférences).

RÈGLES CRITIQUES:
=================

1. JAMAIS MODIFIER Date_examen_VTC automatiquement SI:
   - Evalbox ∈ {"VALIDE CMA", "Convoc CMA reçue"}
   - ET Date_Cloture_Inscription < aujourd'hui (passée)
   → Seul un humain peut traiter

2. Les confirmations candidat doivent être prises avec précaution:
   - Report de date → vérifier si clôture passée
   - Si clôture passée + validé CMA → demander justificatif force majeure

3. Communication UNIQUEMENT par EMAIL, jamais par téléphone.

PATTERNS DÉTECTÉS:
==================
- Confirmation date examen: "je confirme pour le 15/03", "ok pour le 15 mars"
- Préférence session: "cours du soir", "cours du jour", "en journée"
- Confirmation session: "ok pour la session du 24/02"
- Demande de report: "je souhaite décaler", "reporter mon examen"
"""
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Patterns de détection des confirmations
CONFIRMATION_PATTERNS = {
    'date_examen': [
        # Confirmation explicite avec date
        r"(?:je\s+)?confirm[ée]?\s+(?:pour\s+)?(?:le\s+)?(\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?)",
        r"(?:ok|d'accord|parfait|c'est\s+bon)\s+pour\s+(?:le\s+)?(\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?)",
        r"(?:je\s+)?choisis?\s+(?:la\s+date\s+)?(?:du\s+)?(\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?)",
        r"examen\s+(?:du\s+)?(\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?)\s+(?:me\s+convient|ok|parfait)",
    ],
    # Réponses type "Option 1", "Option 2" (sans date explicite)
    'option_choice': [
        r"^option\s*([123])$",
        r"^([123])$",  # Juste le chiffre
        r"^choix\s*([123])$",
        r"^la\s+(première|premi[eè]re|1[eè]?re?)(?:\s+option)?$",
        r"^la\s+(deuxi[eè]me|seconde|2[eè]?me?)(?:\s+option)?$",
    ],
    'session_preference': [
        # Cours du jour
        r"(?:je\s+)?(?:préfère|choisis?|veux|souhaite)\s+(?:les?\s+)?cours\s+du\s+(jour)",
        r"cours\s+du\s+(jour)\s+(?:me\s+convient|ok|parfait|svp|s'il vous plait)",
        r"(?:en\s+)?(journée)\s+(?:me\s+convient|pour\s+moi|svp)",
        r"(?:je\s+suis\s+)?disponible\s+(?:en\s+)?(journée|la\s+journée)",
        # Cours du soir
        r"(?:je\s+)?(?:préfère|choisis?|veux|souhaite)\s+(?:les?\s+)?cours\s+du\s+(soir)",
        r"cours\s+du\s+(soir)\s+(?:me\s+convient|ok|parfait|svp|s'il vous plait)",
        r"(?:après\s+le\s+travail|le\s+soir|en\s+soirée)",
        r"(?:je\s+suis\s+)?disponible\s+(?:le\s+)?(soir|en\s+soirée)",
    ],
    'session_confirmation': [
        r"(?:je\s+)?confirm[ée]?\s+(?:la\s+)?session\s+(?:du\s+)?(\d{1,2}[/.\-]\d{1,2}(?:[/.\-]\d{2,4})?)",
        r"(?:ok|d'accord|parfait)\s+pour\s+(?:la\s+)?session\s+(?:du\s+)?(\d{1,2}[/.\-]\d{1,2})",
        r"session\s+(?:du\s+)?(\d{1,2}[/.\-]\d{1,2})\s+(?:me\s+convient|ok|parfait)",
    ],
    'report_request': [
        r"(?:je\s+)?(?:souhaite|veux|voudrais|peux)\s+(?:décaler|reporter|changer)\s+(?:ma\s+)?(?:date|l'examen)",
        r"report(?:er)?\s+(?:mon\s+)?examen",
        r"(?:pas|ne\s+peux\s+pas|impossible)\s+(?:le|à\s+cette\s+date)",
        r"changer\s+(?:de\s+)?date",
    ],
}


def parse_date_from_match(date_str: str) -> Optional[str]:
    """
    Parse une date depuis un match regex et la convertit en format YYYY-MM-DD.

    Gère les formats:
    - DD/MM/YYYY ou DD-MM-YYYY ou DD.MM.YYYY
    - DD/MM/YY
    - DD/MM (année courante assumée)
    """
    if not date_str:
        return None

    # Nettoyer
    date_str = date_str.strip()

    # Patterns de parsing
    patterns = [
        (r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", "%d/%m/%Y"),
        (r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2})", "%d/%m/%y"),
        (r"(\d{1,2})[/.\-](\d{1,2})", None),  # Année courante
    ]

    for pattern, date_format in patterns:
        match = re.match(pattern, date_str)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 3:
                    day, month, year = groups
                    if len(year) == 2:
                        year = f"20{year}"
                    date_obj = datetime(int(year), int(month), int(day))
                else:
                    day, month = groups
                    current_year = datetime.now().year
                    date_obj = datetime(current_year, int(month), int(day))
                    # Si la date est passée, on assume l'année prochaine
                    if date_obj.date() < datetime.now().date():
                        date_obj = datetime(current_year + 1, int(month), int(day))

                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue

    return None


def _extract_date_from_option_context(threads: List[Dict], current_thread: Dict, option_num: int) -> Optional[str]:
    """
    Extrait la date correspondant à une option depuis le message précédent de l'agent.

    Cherche des patterns comme:
    - "Option 1 - Examen du 31/03/2026"
    - "📅 **Option 1 - Examen du 31/03/2026**"

    Args:
        threads: Liste des threads
        current_thread: Thread actuel du candidat (pour trouver le précédent)
        option_num: Numéro de l'option choisie (1, 2, 3...)

    Returns:
        Date au format YYYY-MM-DD ou None
    """
    from src.utils.text_utils import get_clean_thread_content

    # Trouver le thread précédent de l'agent (direction = 'out')
    current_idx = None
    for i, t in enumerate(threads):
        if t.get('id') == current_thread.get('id'):
            current_idx = i
            break

    if current_idx is None:
        return None

    # Chercher le thread de l'agent juste avant
    agent_content = None
    for i in range(current_idx - 1, -1, -1):
        if threads[i].get('direction') == 'out':
            agent_content = get_clean_thread_content(threads[i])
            break

    if not agent_content:
        return None

    # Patterns pour extraire la date de l'option
    # Option 1 - Examen du 31/03/2026 ou Option 1 - Examen du 31/03
    option_patterns = [
        rf"option\s*{option_num}[^0-9]*examen[^0-9]*(\d{{1,2}}[/.\-]\d{{1,2}}(?:[/.\-]\d{{2,4}})?)",
        rf"option\s*{option_num}[^0-9]*(\d{{1,2}}[/.\-]\d{{1,2}}[/.\-]\d{{2,4}})",
    ]

    for pattern in option_patterns:
        match = re.search(pattern, agent_content, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            parsed = parse_date_from_match(date_str)
            if parsed:
                logger.info(f"  🔍 Extracted date from Option {option_num} context: {date_str} → {parsed}")
                return parsed

    return None


def extract_confirmations_from_threads(
    threads: List[Dict],
    deal_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Analyse les threads pour détecter les confirmations du candidat.

    Args:
        threads: Liste des threads du ticket
        deal_data: Données du deal (pour contexte Evalbox, date clôture)

    Returns:
        {
            'date_examen_confirmed': str or None,  # YYYY-MM-DD
            'session_preference': 'jour' or 'soir' or None,
            'session_confirmed': Dict or None,
            'report_requested': bool,
            'raw_confirmations': List[Dict],  # Détails des matchs
            'blocked_updates': List[Dict],  # Mises à jour bloquées
            'changes_to_apply': List[Dict]  # Changements CRM à appliquer
        }
    """
    from src.utils.text_utils import get_clean_thread_content

    result = {
        'date_examen_confirmed': None,
        'session_preference': None,
        'session_confirmed': None,
        'report_requested': False,
        'raw_confirmations': [],
        'blocked_updates': [],
        'changes_to_apply': []
    }

    if not threads:
        return result

    logger.info("🔍 Extraction des confirmations depuis les threads...")

    # Récupérer contexte pour règles critiques
    evalbox_status = deal_data.get('Evalbox', '') if deal_data else ''
    date_cloture = None
    date_examen_vtc = deal_data.get('Date_examen_VTC') if deal_data else None
    if date_examen_vtc and isinstance(date_examen_vtc, dict):
        date_cloture = date_examen_vtc.get('Date_Cloture_Inscription')

    # Analyser chaque thread entrant (du candidat)
    for thread in threads:
        if thread.get('direction') != 'in':
            continue

        content = get_clean_thread_content(thread).lower()
        thread_date = thread.get('createdTime', '')

        # 1. Détecter demande de report
        for pattern in CONFIRMATION_PATTERNS['report_request']:
            if re.search(pattern, content, re.IGNORECASE):
                result['report_requested'] = True
                result['raw_confirmations'].append({
                    'type': 'report_request',
                    'thread_date': thread_date,
                    'pattern_matched': pattern
                })
                logger.info(f"  📋 Demande de report détectée")
                break

        # 2. Détecter confirmation date examen (avec date explicite)
        for pattern in CONFIRMATION_PATTERNS['date_examen']:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed_date = parse_date_from_match(date_str)
                if parsed_date:
                    result['raw_confirmations'].append({
                        'type': 'date_examen',
                        'raw_value': date_str,
                        'parsed_value': parsed_date,
                        'thread_date': thread_date
                    })
                    result['date_examen_confirmed'] = parsed_date
                    logger.info(f"  📅 Confirmation date examen: {parsed_date}")
                break

        # 2b. Détecter choix "Option 1/2" et extraire date du contexte
        if not result['date_examen_confirmed']:
            for pattern in CONFIRMATION_PATTERNS.get('option_choice', []):
                match = re.search(pattern, content.strip(), re.IGNORECASE)
                if match:
                    option_value = match.group(1).lower()
                    # Convertir en numéro
                    if option_value in ['1', 'première', 'premiere', '1ère', '1ere', '1re']:
                        option_num = 1
                    elif option_value in ['2', 'deuxième', 'deuxieme', 'seconde', '2ème', '2eme']:
                        option_num = 2
                    elif option_value == '3':
                        option_num = 3
                    else:
                        option_num = int(option_value) if option_value.isdigit() else 1

                    # Chercher les dates dans le message précédent de l'agent
                    date_from_context = _extract_date_from_option_context(threads, thread, option_num)
                    if date_from_context:
                        result['raw_confirmations'].append({
                            'type': 'option_choice',
                            'option_number': option_num,
                            'parsed_value': date_from_context,
                            'thread_date': thread_date
                        })
                        result['date_examen_confirmed'] = date_from_context
                        logger.info(f"  📅 Option {option_num} choisie → date examen: {date_from_context}")
                    break

        # 3. Détecter préférence session (jour/soir)
        for pattern in CONFIRMATION_PATTERNS['session_preference']:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # Déterminer si c'est jour ou soir
                matched_text = match.group(0).lower()
                if any(x in matched_text for x in ['jour', 'journée']):
                    result['session_preference'] = 'jour'
                elif any(x in matched_text for x in ['soir', 'soirée', 'travail']):
                    result['session_preference'] = 'soir'

                if result['session_preference']:
                    result['raw_confirmations'].append({
                        'type': 'session_preference',
                        'value': result['session_preference'],
                        'thread_date': thread_date
                    })
                    logger.info(f"  📚 Préférence session: {result['session_preference']}")
                break

        # 4. Détecter confirmation session spécifique
        for pattern in CONFIRMATION_PATTERNS['session_confirmation']:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed_date = parse_date_from_match(date_str)
                if parsed_date:
                    result['raw_confirmations'].append({
                        'type': 'session_confirmation',
                        'raw_value': date_str,
                        'parsed_value': parsed_date,
                        'thread_date': thread_date
                    })
                    result['session_confirmed'] = {'date_debut': parsed_date}
                    logger.info(f"  📚 Confirmation session: {parsed_date}")
                break

    # ================================================================
    # VALIDATION DES RÈGLES CRITIQUES
    # ================================================================
    from src.utils.examt3p_crm_sync import can_modify_exam_date

    # Si confirmation de date ou demande de report
    if result['date_examen_confirmed'] or result['report_requested']:
        can_modify, reason = can_modify_exam_date(evalbox_status, date_cloture)

        if not can_modify:
            logger.warning(f"  🔒 BLOCAGE: {reason}")
            result['blocked_updates'].append({
                'field': 'Date_examen_VTC',
                'reason': reason,
                'evalbox': evalbox_status,
                'date_cloture': date_cloture,
                'action_required': 'HUMAN_REVIEW',
                'message_to_candidate': _get_blocked_update_message(evalbox_status, date_cloture)
            })
            # Ne pas ajouter aux changes_to_apply
        else:
            # Modification autorisée
            if result['date_examen_confirmed']:
                result['changes_to_apply'].append({
                    'field': 'Date_examen_VTC',
                    'value': result['date_examen_confirmed'],
                    'source': 'ticket_confirmation',
                    'requires_lookup': True  # Doit chercher l'ID de la date d'examen
                })

    # Préférence session → toujours OK à mettre à jour
    if result['session_preference']:
        result['changes_to_apply'].append({
            'field': 'Session_souhait_e',
            'value': 'Cours du jour' if result['session_preference'] == 'jour' else 'Cours du soir',
            'source': 'ticket_confirmation'
        })

    return result


def _get_blocked_update_message(evalbox_status: str, date_cloture: str) -> str:
    """
    Génère le message à envoyer au candidat quand une mise à jour est bloquée.

    IMPORTANT: Communication par EMAIL uniquement.
    """
    # Formater la date
    date_formatted = ""
    if date_cloture:
        try:
            if 'T' in str(date_cloture):
                date_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
            else:
                date_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
            date_formatted = date_obj.strftime("%d/%m/%Y")
        except:
            pass

    return f"""Votre dossier a été validé par la CMA et les inscriptions sont clôturées.

**Un report de date d'examen n'est possible qu'avec un justificatif de force majeure.**

Pour demander un report, merci de nous transmettre **par email** :
1. Votre justificatif de force majeure (certificat médical ou autre document officiel)
2. Une brève explication de votre situation

Nous soumettrons votre demande à la CMA pour validation du report.

**Sans justificatif valide**, des frais de réinscription de 241€ seront nécessaires pour une nouvelle inscription."""


def apply_ticket_confirmations_to_crm(
    deal_id: str,
    confirmations: Dict[str, Any],
    crm_client,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Applique les confirmations extraites au CRM.

    Args:
        deal_id: ID du deal
        confirmations: Résultat de extract_confirmations_from_threads
        crm_client: Client CRM
        dry_run: Simulation sans modification

    Returns:
        {
            'updates_applied': List[Dict],
            'updates_blocked': List[Dict],
            'crm_updated': bool
        }
    """
    result = {
        'updates_applied': [],
        'updates_blocked': confirmations.get('blocked_updates', []),
        'crm_updated': False
    }

    changes = confirmations.get('changes_to_apply', [])
    if not changes:
        logger.info("  ℹ️ Aucun changement à appliquer depuis le ticket")
        return result

    updates_to_apply = {}

    for change in changes:
        field = change['field']
        value = change['value']

        # Cas spécial: Date_examen_VTC nécessite un lookup
        if field == 'Date_examen_VTC' and change.get('requires_lookup'):
            # TODO: Implémenter la recherche de l'ID de la date d'examen
            # Pour l'instant, on log et on skip
            logger.info(f"  ⚠️ Date_examen_VTC nécessite recherche lookup - non implémenté")
            continue

        updates_to_apply[field] = value
        result['updates_applied'].append(change)

    if updates_to_apply and not dry_run:
        try:
            from config import settings
            url = f"{settings.zoho_crm_api_url}/Deals/{deal_id}"
            payload = {"data": [updates_to_apply]}

            response = crm_client._make_request("PUT", url, json=payload)

            if response.get('data'):
                result['crm_updated'] = True
                logger.info(f"  ✅ CRM mis à jour depuis ticket: {list(updates_to_apply.keys())}")
            else:
                logger.error(f"  ❌ Échec mise à jour CRM: {response}")

        except Exception as e:
            logger.error(f"  ❌ Erreur mise à jour CRM: {e}")

    elif updates_to_apply and dry_run:
        logger.info(f"  🔍 DRY RUN: {list(updates_to_apply.keys())}")

    return result
