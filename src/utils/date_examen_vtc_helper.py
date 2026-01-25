"""
Helper pour gérer les dates d'examen VTC et leur validation.

Workflow complet :
1. Vérifier si Date_examen_VTC est renseignée dans le Deal
2. Récupérer les infos de la session d'examen (date, date clôture, département)
3. Vérifier le statut Evalbox du candidat
4. Selon les cas, proposer les prochaines dates ou informer du statut

CAS GÉRÉS:
- CAS 1: Date vide → Proposer 2 prochaines dates (CMA du candidat)
- CAS 2: Date passée + Evalbox ≠ VALIDE CMA/Dossier Synchronisé → Proposer 2 prochaines dates
- CAS 3: Evalbox = Refusé CMA → Informer du refus + pièces + prochaine date
- CAS 4: Date future + Evalbox = VALIDE CMA → Rassurer (convocation ~10j avant)
- CAS 5: Date future + Evalbox = Dossier Synchronisé → Prévenir (instruction en cours)
- CAS 6: Date future + Evalbox = autre → En attente
- CAS 7: Date passée + Evalbox = VALIDE CMA/Dossier Synchronisé → Examen passé (sauf indices contraires)
- CAS 8: Date future + Date_Cloture passée + Evalbox ≠ VALIDE CMA/Dossier Synchronisé → Deadline ratée, proposer prochaines dates
"""
import logging
from datetime import datetime, date
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


def get_next_exam_dates(
    crm_client,
    departement: str,
    limit: int = 2
) -> List[Dict[str, Any]]:
    """
    Récupère les prochaines dates d'examen disponibles pour un département.

    Filtres appliqués:
    - Date_Cloture_Inscription > aujourd'hui
    - Statut = "Actif"
    - Même département que le candidat

    Args:
        crm_client: Client Zoho CRM
        departement: Département du candidat (ex: "75", "93")
        limit: Nombre de dates à retourner

    Returns:
        Liste des sessions d'examen avec leurs infos
    """
    from config import settings

    logger.info(f"🔍 Recherche des prochaines dates d'examen pour le département {departement}")

    try:
        # Construire la requête de recherche
        # On cherche les sessions actives pour ce département
        # Note: L'API search ne supporte pas sort_by/sort_order sur les modules custom
        url = f"{settings.zoho_crm_api_url}/Dates_Examens_VTC_TAXI/search"

        # Critère: Statut = Actif AND Departement = X
        criteria = f"((Statut:equals:Actif)and(Departement:equals:{departement}))"

        # Pagination: récupérer toutes les pages
        all_sessions = []
        page = 1
        max_pages = 10  # Sécurité pour éviter boucle infinie

        while page <= max_pages:
            params = {
                "criteria": criteria,
                "page": page,
                "per_page": 200  # Max autorisé par Zoho
            }

            response = crm_client._make_request("GET", url, params=params)
            sessions = response.get("data", [])

            if not sessions:
                break

            all_sessions.extend(sessions)
            logger.info(f"  Page {page}: {len(sessions)} session(s) récupérée(s)")

            # Si moins de 200 résultats, c'est la dernière page
            if len(sessions) < 200:
                break

            page += 1

        if not all_sessions:
            logger.warning(f"Aucune session trouvée pour le département {departement}")
            # Essayer sans filtre département pour avoir au moins des suggestions
            return get_next_exam_dates_any_department(crm_client, limit)

        logger.info(f"  Total: {len(all_sessions)} session(s) récupérée(s) pour le département {departement}")

        # Filtrer les sessions dont la date de clôture est dans le futur
        valid_sessions = []
        today_date = datetime.now()

        for session in all_sessions:
            date_cloture_str = session.get('Date_Cloture_Inscription')
            if date_cloture_str:
                try:
                    # Parser la date (format ISO ou datetime)
                    if 'T' in str(date_cloture_str):
                        date_cloture = datetime.fromisoformat(date_cloture_str.replace('Z', '+00:00'))
                    else:
                        date_cloture = datetime.strptime(str(date_cloture_str), "%Y-%m-%d")

                    if date_cloture > today_date:
                        valid_sessions.append(session)
                except Exception as e:
                    logger.warning(f"Erreur parsing date clôture {date_cloture_str}: {e}")
                    continue

        # Trier par date d'examen et prendre les N premières
        valid_sessions.sort(key=lambda x: x.get('Date_Examen', '9999-99-99'))

        result = valid_sessions[:limit]
        logger.info(f"✅ {len(result)} date(s) d'examen valide(s) pour le département {departement}")

        return result

    except Exception as e:
        logger.error(f"❌ Erreur lors de la recherche des dates d'examen: {e}")
        return []


def get_next_exam_dates_any_department(
    crm_client,
    limit: int = 2
) -> List[Dict[str, Any]]:
    """
    Récupère les prochaines dates d'examen sans filtre département (fallback).
    Avec pagination pour récupérer toutes les sessions.
    """
    from config import settings

    logger.info("🔍 Recherche des prochaines dates d'examen (tous départements)")

    try:
        url = f"{settings.zoho_crm_api_url}/Dates_Examens_VTC_TAXI/search"
        # Note: L'API search ne supporte pas sort_by/sort_order sur les modules custom
        criteria = "(Statut:equals:Actif)"

        # Pagination: récupérer toutes les pages
        all_sessions = []
        page = 1
        max_pages = 10  # Sécurité pour éviter boucle infinie

        while page <= max_pages:
            params = {
                "criteria": criteria,
                "page": page,
                "per_page": 200  # Max autorisé par Zoho
            }

            response = crm_client._make_request("GET", url, params=params)
            sessions = response.get("data", [])

            if not sessions:
                break

            all_sessions.extend(sessions)
            logger.info(f"  Page {page}: {len(sessions)} session(s) récupérée(s)")

            # Si moins de 200 résultats, c'est la dernière page
            if len(sessions) < 200:
                break

            page += 1

        if not all_sessions:
            logger.warning("Aucune session active trouvée")
            return []

        logger.info(f"  Total: {len(all_sessions)} session(s) actives récupérée(s)")

        # Filtrer les sessions avec clôture dans le futur
        valid_sessions = []
        today_date = datetime.now()

        for session in all_sessions:
            date_cloture_str = session.get('Date_Cloture_Inscription')
            if date_cloture_str:
                try:
                    if 'T' in str(date_cloture_str):
                        date_cloture = datetime.fromisoformat(date_cloture_str.replace('Z', '+00:00'))
                    else:
                        date_cloture = datetime.strptime(str(date_cloture_str), "%Y-%m-%d")

                    if date_cloture > today_date:
                        valid_sessions.append(session)
                except:
                    continue

        valid_sessions.sort(key=lambda x: x.get('Date_Examen', '9999-99-99'))
        logger.info(f"✅ {len(valid_sessions[:limit])} date(s) d'examen valide(s) (tous départements)")
        return valid_sessions[:limit]

    except Exception as e:
        logger.error(f"❌ Erreur lors de la recherche des dates d'examen: {e}")
        return []


def format_exam_date_for_display(session: Dict[str, Any]) -> str:
    """
    Formate une session d'examen pour affichage au candidat.

    Args:
        session: Données de la session d'examen

    Returns:
        Texte formaté pour le candidat
    """
    date_examen = session.get('Date_Examen', 'Date inconnue')
    libelle = session.get('Libelle_Affichage', '')
    adresse = session.get('Adresse_Centre', '')
    date_cloture = session.get('Date_Cloture_Inscription', '')

    # Formater la date d'examen
    try:
        if date_examen and date_examen != 'Date inconnue':
            date_obj = datetime.strptime(str(date_examen), "%Y-%m-%d")
            date_examen_formatted = date_obj.strftime("%d/%m/%Y")
        else:
            date_examen_formatted = date_examen
    except:
        date_examen_formatted = date_examen

    # Formater la date de clôture
    try:
        if date_cloture:
            if 'T' in str(date_cloture):
                date_cloture_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
            else:
                date_cloture_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
            date_cloture_formatted = date_cloture_obj.strftime("%d/%m/%Y")
        else:
            date_cloture_formatted = ""
    except:
        date_cloture_formatted = ""

    result = f"- **{date_examen_formatted}**"
    if libelle:
        result += f" ({libelle})"
    if date_cloture_formatted:
        result += f" - Clôture inscriptions: {date_cloture_formatted}"

    return result


def is_date_in_past(date_str: str) -> bool:
    """
    Vérifie si une date est dans le passé.
    """
    if not date_str:
        return False

    try:
        if 'T' in str(date_str):
            date_obj = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
        else:
            date_obj = datetime.strptime(str(date_str), "%Y-%m-%d")

        return date_obj.date() < datetime.now().date()
    except:
        return False


def analyze_exam_date_situation(
    deal_data: Dict[str, Any],
    threads: List[Dict] = None,
    crm_client = None,
    examt3p_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Analyse la situation de date d'examen VTC du candidat et détermine l'action à prendre.

    Args:
        deal_data: Données du deal CRM
        threads: Threads du ticket (pour détecter indices examen non passé)
        crm_client: Client Zoho CRM (pour récupérer les prochaines dates)
        examt3p_data: Données ExamT3P (pour pièces refusées)

    Returns:
        {
            'case': int (1-7),
            'case_description': str,
            'date_examen_vtc': str or None,
            'date_examen_info': Dict or None,
            'evalbox_status': str or None,
            'should_include_in_response': bool,
            'response_message': str or None,
            'next_dates': List[Dict],
            'pieces_refusees': List[str] (pour cas 3),
            'date_cloture': str or None
        }
    """
    result = {
        'case': 0,
        'case_description': '',
        'date_examen_vtc': None,
        'date_examen_info': None,
        'evalbox_status': None,
        'should_include_in_response': False,
        'response_message': None,
        'next_dates': [],
        'pieces_refusees': [],
        'date_cloture': None
    }

    logger.info("🔍 Analyse de la situation date d'examen VTC...")

    # Récupérer les données du deal
    date_examen_vtc = deal_data.get('Date_examen_VTC')
    evalbox_status = deal_data.get('Evalbox', '')
    cma_depot = deal_data.get('CMA_de_depot', '')

    result['evalbox_status'] = evalbox_status

    # Extraire le département de la CMA (si format "CMA XX" ou numéro direct)
    departement = extract_departement_from_cma(cma_depot)

    logger.info(f"  Date_examen_VTC: {date_examen_vtc}")
    logger.info(f"  Evalbox: {evalbox_status}")
    logger.info(f"  CMA_de_depot: {cma_depot} (département: {departement})")

    # Si date_examen_vtc est un lookup, on doit récupérer l'ID et les infos
    if date_examen_vtc:
        if isinstance(date_examen_vtc, dict):
            # C'est un lookup, on a l'ID et le name
            result['date_examen_vtc'] = date_examen_vtc.get('id')
            result['date_examen_info'] = date_examen_vtc
            # Récupérer les infos complètes de la session
            if crm_client and date_examen_vtc.get('id'):
                session_info = get_exam_session_details(crm_client, date_examen_vtc.get('id'))
                if session_info:
                    result['date_examen_info'] = session_info
                    result['date_cloture'] = session_info.get('Date_Cloture_Inscription')
        else:
            result['date_examen_vtc'] = date_examen_vtc

    # ================================================================
    # DÉTERMINATION DU CAS
    # ================================================================

    # CAS 1: Date vide
    if not date_examen_vtc:
        result['case'] = 1
        result['case_description'] = "Date examen VTC vide - Proposer 2 prochaines dates"
        result['should_include_in_response'] = True

        if crm_client and departement:
            result['next_dates'] = get_next_exam_dates(crm_client, departement, limit=2)

        result['response_message'] = generate_propose_dates_message(result['next_dates'], departement)
        logger.info(f"  ➡️ CAS 1: Date vide")
        return result

    # Déterminer si la date est passée
    date_examen_str = None
    if result.get('date_examen_info'):
        if isinstance(result['date_examen_info'], dict):
            date_examen_str = result['date_examen_info'].get('Date_Examen')

    date_is_past = is_date_in_past(date_examen_str) if date_examen_str else False

    # CAS 3: Evalbox = Refusé CMA (prioritaire car peut arriver avec date passée ou future)
    if evalbox_status == 'Refusé CMA':
        result['case'] = 3
        result['case_description'] = "Refusé CMA - Informer du refus et prochaines dates"
        result['should_include_in_response'] = True

        # Récupérer les pièces refusées depuis ExamT3P
        if examt3p_data:
            result['pieces_refusees'] = examt3p_data.get('pieces_refusees', [])

        if crm_client and departement:
            result['next_dates'] = get_next_exam_dates(crm_client, departement, limit=1)

        result['response_message'] = generate_refus_cma_message(
            result['pieces_refusees'],
            result['date_cloture'],
            result['next_dates']
        )
        logger.info(f"  ➡️ CAS 3: Refusé CMA")
        return result

    # CAS avec date dans le passé
    if date_is_past:
        # CAS 7: Date passée + VALIDE CMA ou Dossier Synchronisé
        if evalbox_status in ['VALIDE CMA', 'Dossier Synchronisé']:
            result['case'] = 7
            result['case_description'] = "Date passée + dossier validé - Examen probablement passé"

            # Vérifier s'il y a des indices dans les threads que l'examen n'a pas été passé
            has_indices_not_passed = check_threads_for_exam_not_passed(threads) if threads else False

            if has_indices_not_passed:
                result['should_include_in_response'] = True
                result['response_message'] = generate_clarification_exam_message()
            else:
                result['should_include_in_response'] = False
                result['response_message'] = None

            logger.info(f"  ➡️ CAS 7: Date passée + validé (indices non passé: {has_indices_not_passed})")
            return result

        # CAS 2: Date passée + Evalbox autre
        else:
            result['case'] = 2
            result['case_description'] = "Date passée + dossier non validé - Proposer 2 prochaines dates"
            result['should_include_in_response'] = True

            if crm_client and departement:
                result['next_dates'] = get_next_exam_dates(crm_client, departement, limit=2)

            result['response_message'] = generate_propose_dates_past_message(result['next_dates'], departement)
            logger.info(f"  ➡️ CAS 2: Date passée + non validé")
            return result

    # CAS avec date dans le futur
    else:
        # CAS 4: Date future + VALIDE CMA
        if evalbox_status == 'VALIDE CMA':
            result['case'] = 4
            result['case_description'] = "Date future + VALIDE CMA - Dossier validé, convocation à venir"
            result['should_include_in_response'] = True
            result['response_message'] = generate_valide_cma_message(date_examen_str)
            logger.info(f"  ➡️ CAS 4: Date future + VALIDE CMA")
            return result

        # CAS 5: Date future + Dossier Synchronisé
        if evalbox_status == 'Dossier Synchronisé':
            result['case'] = 5
            result['case_description'] = "Date future + Dossier Synchronisé - Instruction en cours"
            result['should_include_in_response'] = True
            result['response_message'] = generate_dossier_synchronise_message(
                date_examen_str,
                result['date_cloture'],
                result['next_dates']
            )
            logger.info(f"  ➡️ CAS 5: Date future + Dossier Synchronisé")
            return result

        # Vérifier si la date de clôture est passée
        date_cloture_is_past = is_date_in_past(result['date_cloture']) if result.get('date_cloture') else False

        # CAS 8: Date future + Date_Cloture passée + Evalbox ≠ VALIDE CMA/Dossier Synchronisé
        # = Le candidat a raté la date limite d'inscription, il sera reporté sur la prochaine session
        if date_cloture_is_past:
            result['case'] = 8
            result['case_description'] = "Date future + Deadline passée + dossier non validé - Report sur prochaine session"
            result['should_include_in_response'] = True

            if crm_client and departement:
                result['next_dates'] = get_next_exam_dates(crm_client, departement, limit=2)

            result['response_message'] = generate_deadline_missed_message(
                date_examen_str,
                result['date_cloture'],
                evalbox_status,
                result['next_dates']
            )
            logger.info(f"  ➡️ CAS 8: Date future + Deadline passée + non validé ({evalbox_status})")
            return result

        # CAS 6: Date future + autre statut + deadline pas encore passée
        result['case'] = 6
        result['case_description'] = "Date future + autre statut - En attente"
        result['should_include_in_response'] = False
        result['response_message'] = None
        logger.info(f"  ➡️ CAS 6: Date future + autre statut ({evalbox_status})")
        return result


def extract_departement_from_cma(cma_depot: str) -> Optional[str]:
    """
    Extrait le numéro de département depuis le champ CMA_de_depot.

    Args:
        cma_depot: Valeur du champ CMA_de_depot (ex: "CMA 75", "93", "CMA IDF")

    Returns:
        Numéro de département ou None
    """
    import re

    if not cma_depot:
        return None

    cma_str = str(cma_depot).strip()

    # Chercher un numéro à 2-3 chiffres
    match = re.search(r'\b(\d{2,3})\b', cma_str)
    if match:
        return match.group(1)

    # Mappings connus pour les régions
    region_mapping = {
        'IDF': '75',
        'Ile De France': '75',
        'PACA': '13',
        'Rhone': '69',
        'Lyon': '69',
    }

    for key, value in region_mapping.items():
        if key.lower() in cma_str.lower():
            return value

    return None


def get_exam_session_details(crm_client, session_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère les détails complets d'une session d'examen.
    """
    from config import settings

    try:
        url = f"{settings.zoho_crm_api_url}/Dates_Examens_VTC_TAXI/{session_id}"
        response = crm_client._make_request("GET", url)
        data = response.get("data", [])
        return data[0] if data else None
    except Exception as e:
        logger.error(f"Erreur récupération session {session_id}: {e}")
        return None


def check_threads_for_exam_not_passed(threads: List[Dict]) -> bool:
    """
    Vérifie dans les threads s'il y a des indices que le candidat n'a pas passé l'examen.

    Patterns recherchés:
    - "je n'ai pas pu passer"
    - "je n'ai pas passé"
    - "absent"
    - "pas présenté"
    - "reporté"
    - etc.
    """
    from src.utils.text_utils import get_clean_thread_content
    import re

    if not threads:
        return False

    patterns = [
        r"n'ai pas pu passer",
        r"n'ai pas passé",
        r"pas présenté",
        r"pas pu me présenter",
        r"absent à l'examen",
        r"j'étais absent",
        r"reporté mon examen",
        r"annulé mon examen",
        r"pas encore passé",
        r"quand est.mon examen",
        r"date de.mon examen",
    ]

    for thread in threads:
        if thread.get('direction') != 'in':
            continue

        content = get_clean_thread_content(thread).lower()

        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                logger.info(f"Indice trouvé dans thread: pattern '{pattern}'")
                return True

    return False


# ================================================================
# GÉNÉRATEURS DE MESSAGES
# ================================================================

def generate_propose_dates_message(next_dates: List[Dict], departement: str) -> str:
    """
    Génère le message proposant les prochaines dates d'examen (CAS 1).
    """
    if not next_dates:
        return """Concernant votre inscription à l'examen VTC, nous n'avons pas encore de date d'examen enregistrée pour votre dossier.

Merci de nous indiquer vos disponibilités afin que nous puissions vous proposer les prochaines dates d'examen disponibles dans votre région."""

    dates_formatted = "\n".join([format_exam_date_for_display(d) for d in next_dates])

    return f"""Concernant votre inscription à l'examen VTC, nous n'avons pas encore de date d'examen enregistrée pour votre dossier.

Voici les prochaines dates d'examen disponibles :

{dates_formatted}

Merci de nous confirmer la date qui vous convient le mieux afin que nous puissions procéder à votre inscription."""


def generate_propose_dates_past_message(next_dates: List[Dict], departement: str) -> str:
    """
    Génère le message proposant les prochaines dates quand la date précédente est passée (CAS 2).
    """
    if not next_dates:
        return """Nous constatons que la date d'examen initialement prévue est maintenant passée et votre dossier n'a pas été validé à temps.

Merci de nous contacter pour que nous puissions vous proposer les prochaines dates d'examen disponibles."""

    dates_formatted = "\n".join([format_exam_date_for_display(d) for d in next_dates])

    return f"""Nous constatons que la date d'examen initialement prévue est maintenant passée.

Pour vous permettre de passer votre examen, voici les prochaines dates disponibles :

{dates_formatted}

Merci de nous confirmer la date qui vous convient afin que nous puissions mettre à jour votre inscription."""


def generate_refus_cma_message(
    pieces_refusees: List[str],
    date_cloture: str,
    next_dates: List[Dict]
) -> str:
    """
    Génère le message pour informer d'un refus CMA (CAS 3).
    """
    # Formater la date de clôture
    date_cloture_formatted = ""
    if date_cloture:
        try:
            if 'T' in str(date_cloture):
                date_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
            else:
                date_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
            date_cloture_formatted = date_obj.strftime("%d/%m/%Y")
        except:
            date_cloture_formatted = str(date_cloture)

    # Formater les pièces refusées
    pieces_text = ""
    if pieces_refusees:
        pieces_list = "\n".join([f"- {piece}" for piece in pieces_refusees])
        pieces_text = f"""Les pièces suivantes ont été refusées :

{pieces_list}

"""

    # Formater la prochaine date
    next_date_text = ""
    if next_dates:
        next_date = next_dates[0]
        next_date_formatted = format_exam_date_for_display(next_date)
        next_date_text = f"""

Si vous nous fournissez les documents corrigés avant la date de clôture, nous pourrons vous inscrire sur la prochaine date :
{next_date_formatted}"""

    date_cloture_text = f" (date limite : {date_cloture_formatted})" if date_cloture_formatted else ""

    return f"""Nous vous informons que la CMA a refusé certaines pièces de votre dossier.

{pieces_text}Pour que votre inscription puisse être validée, merci de nous transmettre les documents corrigés dans les plus brefs délais{date_cloture_text}.{next_date_text}"""


def generate_valide_cma_message(date_examen_str: str) -> str:
    """
    Génère le message pour un dossier validé CMA (CAS 4).
    """
    date_formatted = ""
    if date_examen_str:
        try:
            date_obj = datetime.strptime(str(date_examen_str), "%Y-%m-%d")
            date_formatted = date_obj.strftime("%d/%m/%Y")
        except:
            date_formatted = str(date_examen_str)

    date_text = f" du {date_formatted}" if date_formatted else ""

    return f"""Bonne nouvelle ! Votre dossier a été validé par la CMA pour l'examen{date_text}.

Vous recevrez votre convocation officielle environ 10 jours avant la date de l'examen. Cette convocation vous sera envoyée directement par la CMA à l'adresse email que vous avez renseignée.

En attendant, nous vous conseillons de bien préparer votre examen. N'hésitez pas à nous contacter si vous avez des questions."""


def generate_dossier_synchronise_message(
    date_examen_str: str,
    date_cloture: str,
    next_dates: List[Dict]
) -> str:
    """
    Génère le message pour un dossier synchronisé (en cours d'instruction) (CAS 5).
    """
    date_formatted = ""
    if date_examen_str:
        try:
            date_obj = datetime.strptime(str(date_examen_str), "%Y-%m-%d")
            date_formatted = date_obj.strftime("%d/%m/%Y")
        except:
            date_formatted = str(date_examen_str)

    date_cloture_formatted = ""
    if date_cloture:
        try:
            if 'T' in str(date_cloture):
                date_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
            else:
                date_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
            date_cloture_formatted = date_obj.strftime("%d/%m/%Y")
        except:
            date_cloture_formatted = str(date_cloture)

    date_text = f" du {date_formatted}" if date_formatted else ""
    cloture_text = f" avant le {date_cloture_formatted}" if date_cloture_formatted else " rapidement"

    return f"""Votre dossier a bien été transmis à la CMA pour l'examen{date_text} et est actuellement en cours d'instruction.

**Important :** Pendant cette période, la CMA peut vous demander des corrections ou des pièces complémentaires. Nous vous conseillons de surveiller attentivement vos emails (y compris les spams).

Si la CMA refuse certains documents, vous devrez nous transmettre les corrections{cloture_text} pour que votre inscription soit maintenue sur cette date d'examen. Dans le cas contraire, votre dossier sera automatiquement décalé sur la prochaine session disponible.

N'hésitez pas à nous contacter si vous recevez une demande de la CMA."""


def generate_clarification_exam_message() -> str:
    """
    Génère le message demandant clarification sur le passage de l'examen (CAS 7).
    """
    return """Nous constatons que la date de votre examen est passée. Votre dossier avait été validé par la CMA.

Pourriez-vous nous confirmer si vous avez bien pu passer votre examen ?

Si ce n'est pas le cas, merci de nous en informer afin que nous puissions vous proposer une nouvelle date d'inscription."""


def generate_deadline_missed_message(
    date_examen_str: str,
    date_cloture: str,
    evalbox_status: str,
    next_dates: List[Dict]
) -> str:
    """
    Génère le message informant que la deadline est passée et le candidat sera reporté (CAS 8).

    Ce cas se produit quand:
    - La date d'examen est dans le futur
    - MAIS la date de clôture des inscriptions est passée
    - ET le dossier n'a pas été validé (Evalbox ≠ VALIDE CMA/Dossier Synchronisé)

    Conséquence: Le candidat a raté la deadline et sera automatiquement reporté
    sur la prochaine session disponible.
    """
    # Formater la date d'examen
    date_examen_formatted = ""
    if date_examen_str:
        try:
            date_obj = datetime.strptime(str(date_examen_str), "%Y-%m-%d")
            date_examen_formatted = date_obj.strftime("%d/%m/%Y")
        except:
            date_examen_formatted = str(date_examen_str)

    # Formater la date de clôture
    date_cloture_formatted = ""
    if date_cloture:
        try:
            if 'T' in str(date_cloture):
                date_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
            else:
                date_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
            date_cloture_formatted = date_obj.strftime("%d/%m/%Y")
        except:
            date_cloture_formatted = str(date_cloture)

    date_examen_text = f" du {date_examen_formatted}" if date_examen_formatted else ""
    date_cloture_text = f" (clôturées le {date_cloture_formatted})" if date_cloture_formatted else ""

    # Formater les prochaines dates
    next_dates_text = ""
    if next_dates:
        dates_formatted = "\n".join([format_exam_date_for_display(d) for d in next_dates])
        next_dates_text = f"""

Voici les prochaines dates d'examen disponibles :

{dates_formatted}

Merci de nous confirmer la date qui vous convient afin que nous puissions vous inscrire sur cette nouvelle session."""
    else:
        next_dates_text = """

Nous allons vous recontacter rapidement pour vous proposer les prochaines dates disponibles."""

    return f"""Nous vous informons que les inscriptions pour l'examen{date_examen_text} sont maintenant clôturées{date_cloture_text}.

Votre dossier n'ayant pas été validé avant cette date limite, vous ne pourrez malheureusement pas passer l'examen sur cette session. Votre inscription sera automatiquement reportée sur la prochaine session disponible.{next_dates_text}"""
