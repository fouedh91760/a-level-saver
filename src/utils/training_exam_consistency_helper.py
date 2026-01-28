"""
Helper pour gérer la cohérence entre les dates de formation et d'examen.

Cas critiques détectés:
1. Formation manquée + Examen imminent → Proposer 2 options au candidat
2. Formation proposée APRÈS examen → ERREUR LOGIQUE à éviter

Règles métier:
- Report d'examen possible UNIQUEMENT pour force majeure (certificat médical, décès, etc.)
- Ne pas avoir suivi la formation ≠ force majeure
- Si e-learning complété, l'examen peut être maintenu
- En cas de report, la CMA positionne sur la prochaine date disponible
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)


def analyze_training_exam_consistency(
    deal_data: Dict,
    threads: List[Dict],
    session_data: Optional[Dict] = None,
    crm_client=None
) -> Dict:
    """
    Analyse la cohérence entre la formation suivie/manquée et la date d'examen.

    Détecte les situations problématiques:
    1. Candidat a manqué sa formation
    2. Examen est imminent
    3. Formation proposée serait après l'examen

    Returns:
        {
            'has_consistency_issue': bool,
            'issue_type': str or None,  # 'MISSED_TRAINING_IMMINENT_EXAM', 'TRAINING_AFTER_EXAM'
            'exam_date': str or None,
            'next_exam_date': str or None,  # Pour option de report
            'force_majeure_detected': bool,
            'force_majeure_type': str or None,  # 'medical', 'death', 'other'
            'should_present_options': bool,
            'response_message': str or None,
            'options': List[Dict]  # Les options à présenter au candidat
        }
    """
    result = {
        'has_consistency_issue': False,
        'issue_type': None,
        'exam_date': None,
        'exam_date_formatted': None,
        'next_exam_date': None,
        'next_exam_date_formatted': None,
        'force_majeure_detected': False,
        'force_majeure_type': None,
        'should_present_options': False,
        'response_message': None,
        'options': []
    }

    # ================================================================
    # 1. DÉTECTER SI LE CANDIDAT A MANQUÉ SA FORMATION
    # ================================================================
    missed_training = detect_missed_training_in_threads(threads)
    if not missed_training:
        logger.info("  ✅ Pas de formation manquée détectée")
        return result

    logger.warning(f"  🚨 Formation manquée détectée: {missed_training.get('reason', 'raison inconnue')}")

    # ================================================================
    # 2. VÉRIFIER SI L'EXAMEN EST IMMINENT
    # ================================================================
    exam_date_raw = deal_data.get('Date_examen_VTC')
    if not exam_date_raw:
        logger.info("  ℹ️ Pas de date d'examen enregistrée")
        return result

    # Extraire la date d'examen (format: {'name': '13_2026-01-27', 'id': '...'} ou string)
    if isinstance(exam_date_raw, dict):
        exam_date_str = exam_date_raw.get('name', '')
        # Format: "13_2026-01-27" → extraire "2026-01-27"
        if '_' in exam_date_str:
            exam_date_str = exam_date_str.split('_')[1]
    else:
        exam_date_str = str(exam_date_raw)

    try:
        exam_date = datetime.strptime(exam_date_str, "%Y-%m-%d")
        result['exam_date'] = exam_date_str
        result['exam_date_formatted'] = exam_date.strftime("%d/%m/%Y")
    except ValueError:
        logger.warning(f"  ⚠️ Format de date d'examen invalide: {exam_date_str}")
        return result

    # Vérifier si l'examen est dans les 14 prochains jours (imminent)
    today = datetime.now()
    days_until_exam = (exam_date - today).days

    if days_until_exam > 14:
        logger.info(f"  ℹ️ Examen dans {days_until_exam} jours - pas imminent")
        return result

    logger.warning(f"  🚨 EXAMEN IMMINENT: dans {days_until_exam} jours ({result['exam_date_formatted']})")

    # ================================================================
    # 3. DÉTECTER SI FORCE MAJEURE MENTIONNÉE
    # ================================================================
    force_majeure = detect_force_majeure_in_threads(threads)
    result['force_majeure_detected'] = force_majeure.get('detected', False)
    result['force_majeure_type'] = force_majeure.get('type')

    if result['force_majeure_detected']:
        logger.info(f"  📋 Force majeure détectée: {result['force_majeure_type']}")

    # ================================================================
    # 4. RÉCUPÉRER LA PROCHAINE DATE D'EXAMEN (pour option report)
    # ================================================================
    if crm_client:
        next_exam = get_next_exam_date_after(
            current_exam_date=exam_date,
            departement=deal_data.get('CMA_de_depot'),
            crm_client=crm_client
        )
        if next_exam:
            result['next_exam_date'] = next_exam.get('Date_Examen')
            try:
                next_date = datetime.strptime(result['next_exam_date'], "%Y-%m-%d")
                result['next_exam_date_formatted'] = next_date.strftime("%d/%m/%Y")
            except Exception as e:
                result['next_exam_date_formatted'] = result['next_exam_date']
            logger.info(f"  📅 Prochaine date d'examen disponible: {result['next_exam_date_formatted']}")

    # ================================================================
    # 5. PRÉPARER LES OPTIONS POUR LE CANDIDAT
    # ================================================================
    result['has_consistency_issue'] = True
    result['issue_type'] = 'MISSED_TRAINING_IMMINENT_EXAM'
    result['should_present_options'] = True

    result['options'] = [
        {
            'id': 'A',
            'title': 'Maintenir l\'examen',
            'description': f"Passer l'examen le {result['exam_date_formatted']} si le e-learning vous a suffi",
            'action': 'KEEP_EXAM'
        },
        {
            'id': 'B',
            'title': 'Reporter l\'examen',
            'description': f"Demander un report vers le {result['next_exam_date_formatted'] or 'prochaine date disponible'} (justificatif force majeure requis)",
            'action': 'RESCHEDULE_EXAM',
            'requires': 'Certificat médical ou justificatif de force majeure'
        }
    ]

    # ================================================================
    # 6. GÉNÉRER LE MESSAGE DE RÉPONSE
    # ================================================================
    result['response_message'] = generate_training_exam_options_message(
        exam_date=result['exam_date_formatted'],
        next_exam_date=result['next_exam_date_formatted'],
        force_majeure_detected=result['force_majeure_detected'],
        force_majeure_type=result['force_majeure_type'],
        missed_reason=missed_training.get('reason')
    )

    return result


def detect_missed_training_in_threads(threads: List[Dict]) -> Optional[Dict]:
    """
    Détecte si le candidat mentionne avoir manqué sa formation.

    Returns:
        Dict avec 'detected': True et 'reason' si trouvé, None sinon
    """
    from src.utils.text_utils import get_clean_thread_content

    # Patterns indiquant une formation manquée
    patterns = [
        (r"n'ai\s+pas\s+pu\s+(?:assister|participer|suivre)", "impossibilité"),
        (r"pas\s+pu\s+(?:assister|participer|suivre)", "impossibilité"),
        (r"manqu[ée]\s+(?:la\s+)?(?:formation|session|cours)", "formation manquée"),
        (r"absent[e]?\s+(?:à|de)\s+(?:la\s+)?(?:formation|session)", "absence"),
        (r"(?:état\s+de\s+)?sant[ée].*(?:pas\s+permis|emp[êe]ch[ée])", "raison médicale"),
        (r"hospitalis[ée]", "hospitalisation"),
        (r"maladie", "maladie"),
        (r"(?:ne\s+)?(?:pas\s+)?(?:pouvoir\s+)?rejoindre.*(?:formation|webinaire)", "impossibilité de rejoindre"),
        (r"dossier\s+m[ée]dical", "dossier médical"),
        (r"certificat\s+m[ée]dical", "certificat médical"),
    ]

    for thread in threads:
        if thread.get('direction') != 'in':
            continue

        content = get_clean_thread_content(thread)
        content_lower = content.lower()

        for pattern, reason in patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                logger.info(f"  🔍 Formation manquée détectée: {reason}")
                return {
                    'detected': True,
                    'reason': reason,
                    'pattern': pattern
                }

    return None


def detect_force_majeure_in_threads(threads: List[Dict]) -> Dict:
    """
    Détecte si le candidat mentionne un motif de force majeure.

    Force majeure valide:
    - Certificat médical / hospitalisation / maladie grave
    - Décès d'un proche
    - Accident
    - Convocation judiciaire

    Returns:
        Dict avec 'detected': bool et 'type': str
    """
    from src.utils.text_utils import get_clean_thread_content

    # Patterns de force majeure par type
    medical_patterns = [
        r'certificat\s+m[ée]dical',
        r'hospitalis[ée]',
        r'hospitalisation',
        r'maladie\s+grave',
        r'op[ée]ration',
        r'chirurgie',
        r'accident',
        r'blessure',
        r'arr[êe]t\s+(?:de\s+)?travail',
        r'(?:état\s+de\s+)?sant[ée]',
        r'dossier\s+m[ée]dical',
        r'probl[èe]me\s+(?:de\s+)?sant[ée]',
    ]

    death_patterns = [
        r'd[ée]c[èe]s',
        r'deuil',
        r'enterrement',
        r'fun[ée]railles',
    ]

    other_patterns = [
        r'convocation\s+(?:judiciaire|tribunal)',
        r'force\s+majeure',
        r'catastrophe',
        r'sinistre',
    ]

    for thread in threads:
        if thread.get('direction') != 'in':
            continue

        content = get_clean_thread_content(thread)
        content_lower = content.lower()

        # Vérifier médical
        for pattern in medical_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return {'detected': True, 'type': 'medical'}

        # Vérifier décès
        for pattern in death_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return {'detected': True, 'type': 'death'}

        # Vérifier autres
        for pattern in other_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return {'detected': True, 'type': 'other'}

    return {'detected': False, 'type': None}


def get_next_exam_date_after(
    current_exam_date: datetime,
    departement: str,
    crm_client
) -> Optional[Dict]:
    """
    Récupère la prochaine date d'examen APRÈS la date actuelle.

    En cas de report, la CMA positionne sur la prochaine date disponible,
    même si la date de clôture est passée.
    """
    try:
        # Extraire le numéro de département
        dept_num = str(departement)[:2] if departement else None
        if not dept_num:
            return None

        # Chercher les sessions d'examen pour ce département
        # Date_Examen > current_exam_date
        search_criteria = f"(Departement:equals:{dept_num})and(Date_Examen:greater_than:{current_exam_date.strftime('%Y-%m-%d')})"

        sessions = crm_client.search_records(
            module="Sessions1",
            criteria=search_criteria,
            fields=["Date_Examen", "Date_Cloture_Inscription", "Libelle_Affichage"],
            sort_by="Date_Examen",
            sort_order="asc",
            per_page=5
        )

        if sessions:
            # Retourner la première (prochaine) date
            return sessions[0]

        return None

    except Exception as e:
        logger.error(f"Erreur lors de la recherche de la prochaine date d'examen: {e}")
        return None


def generate_training_exam_options_message(
    exam_date: str,
    next_exam_date: Optional[str],
    force_majeure_detected: bool,
    force_majeure_type: Optional[str],
    missed_reason: Optional[str]
) -> str:
    """
    Génère le message présentant les 2 options au candidat.

    Points clés:
    - Informer le candidat de sa date d'examen (il peut ne pas être au courant)
    - Le justificatif force majeure doit couvrir le jour de l'EXAMEN (pas la formation)
    - La CMA gère les examens, pas la formation
    """
    # Adapter l'introduction selon si force majeure détectée
    if force_majeure_detected and force_majeure_type == 'medical':
        intro = """Nous avons bien pris connaissance de votre situation et comprenons que votre état de santé ne vous a pas permis de suivre la formation en visioconférence.

Nous espérons sincèrement que vous allez mieux."""
    elif force_majeure_detected and force_majeure_type == 'death':
        intro = """Nous avons bien pris connaissance de votre situation et vous présentons nos sincères condoléances.

Nous comprenons que les circonstances ne vous ont pas permis de suivre la formation."""
    else:
        intro = """Nous avons bien pris connaissance de votre message concernant la formation."""

    # Message principal avec les 2 options
    # IMPORTANT: Informer le candidat de sa date d'examen car il peut ne pas être au courant
    next_exam_info = f"le **{next_exam_date}**" if next_exam_date else "la prochaine date disponible"

    message = f"""Bonjour,

{intro}

**⚠️ Information importante : Vous êtes inscrit(e) à l'examen VTC du {exam_date}.**

La formation en visioconférence et le e-learning sont des outils de préparation, mais votre inscription à l'examen est déjà validée auprès de la CMA (Chambre des Métiers et de l'Artisanat).

Vous avez deux possibilités :

---

## Option A : Maintenir votre examen au {exam_date}

Si vous estimez que le **e-learning** (formation à distance) vous a permis d'acquérir les connaissances nécessaires, vous pouvez passer l'examen à la date prévue.

📚 **Rappel** : Vous avez accès aux cours en ligne sur : **https://elearning.cab-formations.fr**

La formation en visioconférence est un complément, mais n'est pas obligatoire pour se présenter à l'examen.

---

## Option B : Reporter votre examen

Si vous souhaitez reporter votre examen, **un justificatif de force majeure couvrant la date du {exam_date} est obligatoire**.

⚠️ **Attention** : Le certificat médical doit couvrir **le jour de l'examen** ({exam_date}), pas seulement la période de la formation.

En cas de report accepté par la CMA, vous serez repositionné(e) sur {next_exam_info}.

**Pour demander un report :**
1. Envoyez-nous un **certificat médical** (ou autre justificatif de force majeure) **couvrant la date du {exam_date}**
2. Nous transmettrons votre demande à la CMA
3. La CMA vous repositionnera sur la prochaine date d'examen disponible

⚠️ **Important** : Le simple fait de ne pas avoir suivi la formation n'est **pas** un motif valable de report auprès de la CMA. Seule la force majeure (maladie le jour de l'examen, accident, décès d'un proche, etc.) permet de reporter.

---

**Merci de nous indiquer votre choix** afin que nous puissions vous accompagner au mieux.

Cordialement,
L'équipe Cab Formations"""

    return message


def check_session_dates_consistency(
    proposed_sessions: List[Dict],
    exam_date: datetime
) -> Dict:
    """
    Vérifie que les sessions de formation proposées se terminent AVANT l'examen.

    Returns:
        {
            'consistent': bool,
            'valid_sessions': List[Dict],  # Sessions qui se terminent avant l'examen
            'invalid_sessions': List[Dict]  # Sessions qui se terminent après l'examen
        }
    """
    result = {
        'consistent': True,
        'valid_sessions': [],
        'invalid_sessions': []
    }

    for session in proposed_sessions:
        date_fin_str = session.get('Date_fin') or session.get('date_fin')
        if not date_fin_str:
            continue

        try:
            date_fin = datetime.strptime(str(date_fin_str), "%Y-%m-%d")

            # La formation doit se terminer AU MOINS 3 jours avant l'examen
            if date_fin <= exam_date - timedelta(days=3):
                result['valid_sessions'].append(session)
            else:
                result['invalid_sessions'].append(session)
                result['consistent'] = False
                logger.warning(
                    f"  ⚠️ Session invalide: fin le {date_fin.strftime('%d/%m/%Y')} "
                    f"mais examen le {exam_date.strftime('%d/%m/%Y')}"
                )
        except ValueError:
            continue

    return result
