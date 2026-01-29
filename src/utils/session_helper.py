"""
Helper pour gérer les sessions de formation et leur association avec les dates d'examen.

Logique métier:
1. Les sessions de formation doivent se terminer AVANT la date d'examen
2. On privilégie les sessions dont la Date_fin est la plus proche de la date d'examen
3. Convention de nommage: cdj-* = Cours Du Jour, cds-* = Cours Du Soir
4. On propose toujours une option CDJ et une option CDS sauf si préférence connue
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple

logger = logging.getLogger(__name__)

# Constantes
SESSION_TYPE_JOUR = "cdj"  # Cours Du Jour
SESSION_TYPE_SOIR = "cds"  # Cours Du Soir

# Délai minimum entre fin de formation et examen (en jours)
MIN_DAYS_BEFORE_EXAM = 3
# Délai maximum entre fin de formation et examen (en jours) - au delà, la session est trop éloignée
MAX_DAYS_BEFORE_EXAM = 60


def get_sessions_for_exam_date(
    crm_client,
    exam_date: str,
    session_type: Optional[str] = None,
    limit: int = 2
) -> List[Dict[str, Any]]:
    """
    Récupère les sessions de formation adaptées pour une date d'examen donnée.

    La session doit se terminer AVANT la date d'examen, idéalement proche.

    Args:
        crm_client: Client Zoho CRM
        exam_date: Date d'examen au format YYYY-MM-DD
        session_type: Type de session souhaité ('cdj', 'cds', ou None pour les deux)
        limit: Nombre de sessions à retourner par type

    Returns:
        Liste des sessions avec leurs infos
    """
    from config import settings

    logger.info(f"🔍 Recherche des sessions pour l'examen du {exam_date}")

    try:
        # Parser la date d'examen
        exam_date_obj = datetime.strptime(exam_date, "%Y-%m-%d")
        today = datetime.now()
        today_str = today.strftime('%Y-%m-%d')

        # Calculer la plage de dates pour la fin de formation
        # La session doit se terminer entre (exam - MAX_DAYS) et (exam - MIN_DAYS)
        min_end_date = exam_date_obj - timedelta(days=MAX_DAYS_BEFORE_EXAM)
        max_end_date = exam_date_obj - timedelta(days=MIN_DAYS_BEFORE_EXAM)

        logger.info(f"  Recherche sessions se terminant entre {min_end_date.strftime('%Y-%m-%d')} et {max_end_date.strftime('%Y-%m-%d')}")
        logger.info(f"  Filtrage: Date_debut >= {today_str} (sessions non commencées)")
        logger.info(f"  Filtrage: Lieu_de_formation = VISIO Zoom VTC (sessions Uber uniquement)")

        # Rechercher les sessions planifiées
        url = f"{settings.zoho_crm_api_url}/Sessions1/search"

        # Critère:
        # - Statut = PLANIFIÉ (ou null)
        # - Date_fin dans la plage (proche de l'examen)
        # - Date_debut >= aujourd'hui (pas encore commencée)
        # Note: Filtrage Lieu_de_formation = VISIO Zoom VTC fait en Python après récupération
        criteria = (
            f"(((Statut:equals:PLANIFIÉ)or(Statut:equals:null))"
            f"and(Date_fin:greater_equal:{min_end_date.strftime('%Y-%m-%d')})"
            f"and(Date_fin:less_equal:{max_end_date.strftime('%Y-%m-%d')})"
            f"and(Date_d_but:greater_equal:{today_str}))"
        )

        # Pagination - augmentée pour couvrir tous les cas
        all_sessions = []
        page = 1
        max_pages = 20  # 20 pages × 200 = 4000 sessions max

        while page <= max_pages:
            params = {
                "criteria": criteria,
                "page": page,
                "per_page": 200
            }

            response = crm_client._make_request("GET", url, params=params)
            sessions = response.get("data", [])

            if not sessions:
                break

            all_sessions.extend(sessions)
            logger.info(f"  Page {page}: {len(sessions)} session(s) récupérée(s)")

            if len(sessions) < 200:
                break

            page += 1

        if not all_sessions:
            logger.warning(f"Aucune session trouvée pour l'examen du {exam_date}")
            return []

        logger.info(f"  Total: {len(all_sessions)} session(s) trouvée(s) (avant filtrage Lieu)")

        # Filtrer par Lieu_de_formation = VISIO Zoom VTC (sessions Uber uniquement)
        uber_sessions = []
        for session in all_sessions:
            lieu = session.get('Lieu_de_formation')
            lieu_name = ""
            if isinstance(lieu, dict):
                lieu_name = lieu.get('name', '')
            elif lieu:
                lieu_name = str(lieu)

            # Garder uniquement les sessions VISIO Zoom VTC
            if 'VISIO' in lieu_name.upper() and 'VTC' in lieu_name.upper():
                uber_sessions.append(session)
                logger.debug(f"  Session Uber: {session.get('Name')} - Lieu: {lieu_name}")
            else:
                logger.debug(f"  Session ignorée (lieu={lieu_name}): {session.get('Name')}")

        if not uber_sessions:
            # Debug: lister les lieux trouvés
            lieux_trouves = set()
            for s in all_sessions[:10]:  # Limiter à 10 pour le log
                lieu = s.get('Lieu_de_formation')
                if isinstance(lieu, dict):
                    lieux_trouves.add(lieu.get('name', 'N/A'))
                elif lieu:
                    lieux_trouves.add(str(lieu))
            logger.warning(f"Aucune session Uber (VISIO Zoom VTC) trouvée pour l'examen du {exam_date}")
            logger.warning(f"  Lieux trouvés dans les {len(all_sessions)} sessions: {lieux_trouves}")
            return []

        logger.info(f"  ✅ {len(uber_sessions)} session(s) Uber (VISIO Zoom VTC)")

        # Filtrer et catégoriser par type (CDJ/CDS)
        sessions_jour = []
        sessions_soir = []

        for session in uber_sessions:
            session_name = session.get('Name', '').lower()
            date_fin = session.get('Date_fin', '')

            # Calculer la distance avec l'examen
            if date_fin:
                try:
                    date_fin_obj = datetime.strptime(date_fin, "%Y-%m-%d")
                    days_before_exam = (exam_date_obj - date_fin_obj).days
                    session['days_before_exam'] = days_before_exam
                except ValueError as e:
                    logger.warning(f"Erreur parsing date_fin '{date_fin}': {e}")
                    session['days_before_exam'] = 999

            # Catégoriser par type
            if session_name.startswith(SESSION_TYPE_JOUR):
                session['session_type'] = 'jour'
                session['session_type_label'] = 'Cours du jour'
                sessions_jour.append(session)
            elif session_name.startswith(SESSION_TYPE_SOIR):
                session['session_type'] = 'soir'
                session['session_type_label'] = 'Cours du soir'
                sessions_soir.append(session)

        # Trier par proximité avec l'examen (Date_fin la plus proche de l'examen)
        sessions_jour.sort(key=lambda x: x.get('days_before_exam', 999))
        sessions_soir.sort(key=lambda x: x.get('days_before_exam', 999))

        # Retourner selon le type demandé
        result = []

        if session_type == SESSION_TYPE_JOUR or session_type == 'jour':
            result = sessions_jour[:limit]
        elif session_type == SESSION_TYPE_SOIR or session_type == 'soir':
            result = sessions_soir[:limit]
        else:
            # Retourner les deux types
            if sessions_jour:
                result.append(sessions_jour[0])
            if sessions_soir:
                result.append(sessions_soir[0])

        logger.info(f"✅ {len(result)} session(s) sélectionnée(s) pour l'examen du {exam_date}")
        return result

    except Exception as e:
        logger.error(f"❌ Erreur lors de la recherche des sessions: {e}")
        return []


def get_sessions_for_multiple_exam_dates(
    crm_client,
    exam_dates: List[Dict[str, Any]],
    session_type: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Récupère les sessions de formation pour plusieurs dates d'examen.

    Args:
        crm_client: Client Zoho CRM
        exam_dates: Liste des dates d'examen (retournées par get_next_exam_dates)
        session_type: Type de session souhaité ('jour', 'soir', ou None pour les deux)

    Returns:
        Dict avec date_examen comme clé et liste de sessions comme valeur
    """
    result = {}

    for exam_info in exam_dates:
        exam_date = exam_info.get('Date_Examen')
        if exam_date:
            sessions = get_sessions_for_exam_date(crm_client, exam_date, session_type)
            result[exam_date] = {
                'exam_info': exam_info,
                'sessions': sessions
            }

    return result


def format_session_for_display(session: Dict[str, Any]) -> str:
    """
    Formate une session pour affichage au candidat.

    Args:
        session: Données de la session

    Returns:
        Texte formaté pour le candidat
    """
    name = session.get('Name', 'Session inconnue')
    date_debut = session.get('Date_d_but', '')
    date_fin = session.get('Date_fin', '')
    type_cours = session.get('Type_de_cours', '')
    session_type_label = session.get('session_type_label', '')
    days_before = session.get('days_before_exam', 0)

    # Formater les dates
    date_debut_formatted = ""
    date_fin_formatted = ""

    try:
        if date_debut:
            date_obj = datetime.strptime(date_debut, "%Y-%m-%d")
            date_debut_formatted = date_obj.strftime("%d/%m/%Y")
    except ValueError as e:
        logger.debug(f"Erreur parsing date_debut '{date_debut}': {e}")
        date_debut_formatted = date_debut

    try:
        if date_fin:
            date_obj = datetime.strptime(date_fin, "%Y-%m-%d")
            date_fin_formatted = date_obj.strftime("%d/%m/%Y")
    except ValueError as e:
        logger.debug(f"Erreur parsing date_fin '{date_fin}': {e}")
        date_fin_formatted = date_fin

    result = f"**{session_type_label}** : du {date_debut_formatted} au {date_fin_formatted}"
    if type_cours and type_cours != '-None-':
        result += f" ({type_cours})"

    return result


def format_exam_with_sessions(
    exam_info: Dict[str, Any],
    sessions: List[Dict[str, Any]]
) -> str:
    """
    Formate une date d'examen avec ses sessions associées.

    Args:
        exam_info: Infos sur la date d'examen
        sessions: Sessions de formation associées

    Returns:
        Texte formaté pour le candidat
    """
    # Formater la date d'examen
    exam_date = exam_info.get('Date_Examen', '')
    exam_date_formatted = ""

    try:
        if exam_date:
            date_obj = datetime.strptime(exam_date, "%Y-%m-%d")
            exam_date_formatted = date_obj.strftime("%d/%m/%Y")
    except ValueError as e:
        logger.debug(f"Erreur parsing exam_date '{exam_date}': {e}")
        exam_date_formatted = exam_date

    # Formater la date de clôture
    date_cloture = exam_info.get('Date_Cloture_Inscription', '')
    cloture_formatted = ""

    if date_cloture:
        try:
            if 'T' in str(date_cloture):
                cloture_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
            else:
                cloture_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
            cloture_formatted = cloture_obj.strftime("%d/%m/%Y")
        except (ValueError, TypeError) as e:
            logger.debug(f"Erreur parsing date_cloture '{date_cloture}': {e}")

    result = f"📅 **Examen du {exam_date_formatted}**"
    if cloture_formatted:
        result += f" (clôture inscriptions: {cloture_formatted})"
    result += "\n"

    if sessions:
        result += "   Sessions de formation disponibles :\n"
        for session in sessions:
            result += f"   • {format_session_for_display(session)}\n"
    else:
        result += "   ⚠️ Pas de session de formation disponible pour cette date\n"

    return result


def detect_session_preference_from_deal(
    deal_data: Dict[str, Any],
    enriched_lookups: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Détecte la préférence de session (jour/soir) à partir des données du deal.

    Args:
        deal_data: Données du deal CRM
        enriched_lookups: Lookups enrichis depuis crm_lookup_helper (optionnel, recommandé)

    Returns:
        'jour', 'soir', ou None si pas de préférence détectée
    """
    # Méthode préférée: utiliser les lookups enrichis
    if enriched_lookups and enriched_lookups.get('session_type'):
        session_type = enriched_lookups['session_type']
        if session_type in ('jour', 'soir'):
            return session_type

    # Vérifier le champ Session existant (fallback)
    session = deal_data.get('Session')
    if session:
        if isinstance(session, dict):
            # Fallback: parser le name (legacy)
            session_name = session.get('name', '').lower()
        else:
            session_name = str(session).lower()

        if session_name.startswith(SESSION_TYPE_JOUR):
            return 'jour'
        elif session_name.startswith(SESSION_TYPE_SOIR):
            return 'soir'

    # Vérifier le champ Session_souhait_e
    session_souhaitee = deal_data.get('Session_souhait_e', '')
    if session_souhaitee:
        session_lower = str(session_souhaitee).lower()
        if 'jour' in session_lower or 'cdj' in session_lower:
            return 'jour'
        elif 'soir' in session_lower or 'cds' in session_lower:
            return 'soir'

    return None


def detect_session_preference_from_threads(threads: List[Dict]) -> Optional[str]:
    """
    Détecte la préférence de session (jour/soir) à partir des messages du candidat.

    Args:
        threads: Liste des threads du ticket

    Returns:
        'jour', 'soir', ou None si pas de préférence détectée
    """
    import re

    # Patterns plus spécifiques - éviter les faux positifs
    patterns_jour = [
        r"cours du jour",
        r"en journée",
        r"la journée",
        r"formation.{0,20}jour",  # "formation en jour", "formation du jour"
        r"préfère.{0,20}jour",
        r"choisis.{0,20}jour",
    ]

    patterns_soir = [
        r"cours du soir",
        r"le soir",
        r"en soirée",
        r"formation.{0,20}soir",  # "formation du soir"
        r"préfère.{0,20}soir",
        r"choisis.{0,20}soir",
        r"après.{0,10}travail",
    ]

    found_jour = False
    found_soir = False

    for thread in threads:
        if thread.get('direction') != 'in':
            continue

        content = thread.get('content', '') or thread.get('plainText', '')
        content_lower = content.lower()

        for pattern in patterns_jour:
            if re.search(pattern, content_lower):
                logger.info(f"Pattern 'jour' trouvé: '{pattern}'")
                found_jour = True
                break

        for pattern in patterns_soir:
            if re.search(pattern, content_lower):
                logger.info(f"Pattern 'soir' trouvé: '{pattern}'")
                found_soir = True
                break

    # Si les deux sont trouvés, c'est ambigu (peut-être email quoté)
    if found_jour and found_soir:
        logger.warning("Préférence ambiguë: patterns jour ET soir trouvés")
        return None

    if found_soir:
        logger.info("Préférence 'soir' détectée")
        return 'soir'

    if found_jour:
        logger.info("Préférence 'jour' détectée")
        return 'jour'

    return None


def analyze_session_situation(
    deal_data: Dict[str, Any],
    exam_dates: List[Dict[str, Any]],
    threads: List[Dict] = None,
    crm_client = None,
    triage_session_preference: Optional[str] = None
) -> Dict[str, Any]:
    """
    Analyse la situation et propose les sessions appropriées pour les dates d'examen.

    Args:
        deal_data: Données du deal CRM
        exam_dates: Liste des prochaines dates d'examen
        threads: Threads du ticket (pour détecter préférence)
        crm_client: Client Zoho CRM
        triage_session_preference: Préférence détectée par TriageAgent ('jour'/'soir')
                                   Si fournie, override la détection automatique

    Returns:
        {
            'session_preference': 'jour' | 'soir' | None,
            'current_session': Dict or None,
            'current_session_is_past': bool,
            'refresh_session_available': bool,
            'refresh_session': Dict or None,
            'proposed_options': List of {exam_date, sessions},
            'message': str (message à inclure dans la réponse)
        }
    """
    result = {
        'session_preference': None,
        'current_session': None,
        'current_session_is_past': False,
        'refresh_session_available': False,
        'refresh_session': None,
        'proposed_options': [],
        'message': None
    }

    logger.info("🔍 Analyse de la situation session de formation...")

    # 1. Vérifier si une session est déjà assignée
    current_session = deal_data.get('Session')
    if current_session:
        result['current_session'] = current_session
        logger.info(f"  Session actuelle: {current_session}")

        # Vérifier si la session actuelle est passée
        session_end_date = None
        if isinstance(current_session, dict):
            # Si c'est un lookup, on a besoin de récupérer les détails
            session_id = current_session.get('id')
            session_name = current_session.get('name', '')

            # Extraire la date de fin du nom si possible (format: xxx - DD mois - DD mois YYYY)
            # ou récupérer via API
            if crm_client and session_id:
                try:
                    from config import settings
                    url = f"{settings.zoho_crm_api_url}/Sessions1/{session_id}"
                    response = crm_client._make_request("GET", url)
                    session_data = response.get("data", [])
                    if session_data:
                        session_end_date = session_data[0].get('Date_fin')
                        logger.info(f"  Date fin session actuelle: {session_end_date}")
                except Exception as e:
                    logger.warning(f"  Erreur récupération session: {e}")

        if session_end_date:
            try:
                session_end_obj = datetime.strptime(session_end_date, "%Y-%m-%d")
                if session_end_obj.date() < datetime.now().date():
                    result['current_session_is_past'] = True
                    logger.info("  ⚠️ Session actuelle TERMINÉE (dans le passé)")
            except ValueError as e:
                logger.debug(f"Erreur parsing session_end_date '{session_end_date}': {e}")

    # 2. Détecter la préférence jour/soir
    # Priorité: 1) TriageAgent 2) Deal CRM 3) Threads
    if triage_session_preference:
        preference = triage_session_preference
        logger.info(f"  Préférence TriageAgent: {preference}")
    else:
        preference = detect_session_preference_from_deal(deal_data)
        if not preference and threads:
            preference = detect_session_preference_from_threads(threads)

    result['session_preference'] = preference
    logger.info(f"  Préférence finale: {preference or 'aucune'}")

    # 3. Si pas de dates d'examen, pas de proposition
    if not exam_dates:
        logger.info("  Pas de dates d'examen, pas de proposition de session")
        return result

    # 3.5. Si session DÉJÀ ASSIGNÉE et PAS dans le passé → NE PAS proposer de nouvelles sessions
    if current_session and not result['current_session_is_past']:
        session_name = current_session.get('name', str(current_session)) if isinstance(current_session, dict) else str(current_session)
        logger.info(f"  ✅ Session déjà assignée ({session_name}) et valide → Pas de proposition")
        result['message'] = f"Votre session de formation est déjà programmée : {session_name}"
        return result

    # 4. Récupérer les sessions pour chaque date d'examen UNIQUE (cache pour éviter doublons)
    if crm_client:
        # Cache: date_string -> sessions
        sessions_cache = {}

        for exam_info in exam_dates:
            exam_date = exam_info.get('Date_Examen')
            if exam_date:
                # Utiliser le cache si on a déjà cherché cette date
                if exam_date not in sessions_cache:
                    sessions_cache[exam_date] = get_sessions_for_exam_date(
                        crm_client,
                        exam_date,
                        session_type=preference
                    )

                result['proposed_options'].append({
                    'exam_info': exam_info,
                    'sessions': sessions_cache[exam_date]
                })

    # 5. CAS SPÉCIAL: Session passée + Examen futur = Proposer rafraîchissement
    if result['current_session_is_past'] and result['proposed_options']:
        # Chercher la meilleure session de rafraîchissement (la plus proche de l'examen)
        for option in result['proposed_options']:
            sessions = option.get('sessions', [])
            if sessions:
                # Prendre la session la plus proche de l'examen
                best_session = sessions[0]  # Déjà triée par proximité
                result['refresh_session_available'] = True
                result['refresh_session'] = {
                    'session': best_session,
                    'exam_info': option.get('exam_info')
                }
                logger.info(f"  ✅ Session de rafraîchissement disponible: {best_session.get('Name')}")
                break

    # 6. Générer le message
    result['message'] = generate_session_proposal_message(
        result['proposed_options'],
        preference,
        refresh_available=result['refresh_session_available'],
        refresh_session=result['refresh_session']
    )

    return result


def generate_session_proposal_message(
    options: List[Dict],
    preference: Optional[str] = None,
    refresh_available: bool = False,
    refresh_session: Optional[Dict] = None
) -> str:
    """
    Génère le message proposant les sessions de formation avec les dates d'examen.

    Args:
        options: Liste des options {exam_info, sessions}
        preference: Préférence jour/soir du candidat
        refresh_available: Si une session de rafraîchissement est disponible
        refresh_session: Infos sur la session de rafraîchissement proposée

    Returns:
        Message formaté pour le candidat
    """
    if not options:
        return ""

    lines = []

    # CAS SPÉCIAL: Formation terminée mais examen à venir = proposer rafraîchissement
    if refresh_available and refresh_session:
        lines.append(generate_refresh_session_message(refresh_session))
        lines.append("")  # Ligne vide de séparation

    for option in options:
        exam_info = option.get('exam_info', {})
        sessions = option.get('sessions', [])

        lines.append(format_exam_with_sessions(exam_info, sessions))

    message = "\n".join(lines)

    if not preference:
        message += "\nMerci de nous indiquer votre préférence (cours du jour ou cours du soir) ainsi que la date d'examen qui vous convient."
    else:
        pref_label = "cours du jour" if preference == 'jour' else "cours du soir"
        message += f"\nMerci de nous confirmer la date d'examen qui vous convient pour votre formation en {pref_label}."

    return message


def generate_refresh_session_message(refresh_session: Dict) -> str:
    """
    Génère le message proposant une session de rafraîchissement.

    Ce cas se produit quand:
    - Le candidat a déjà suivi une formation (session terminée)
    - Son examen est dans le futur
    - Une nouvelle session est disponible avant l'examen

    On lui propose de rejoindre cette session GRATUITEMENT pour rafraîchir
    ses connaissances et maximiser ses chances de réussite.
    """
    session = refresh_session.get('session', {})
    exam_info = refresh_session.get('exam_info', {})

    # Formater les dates de la session de rafraîchissement
    date_debut = session.get('Date_d_but', '')
    date_fin = session.get('Date_fin', '')
    type_cours = session.get('Type_de_cours', '')
    session_type_label = session.get('session_type_label', 'Formation')

    date_debut_formatted = ""
    date_fin_formatted = ""

    try:
        if date_debut:
            date_obj = datetime.strptime(date_debut, "%Y-%m-%d")
            date_debut_formatted = date_obj.strftime("%d/%m/%Y")
    except ValueError as e:
        logger.debug(f"Erreur parsing date_debut '{date_debut}': {e}")
        date_debut_formatted = date_debut

    try:
        if date_fin:
            date_obj = datetime.strptime(date_fin, "%Y-%m-%d")
            date_fin_formatted = date_obj.strftime("%d/%m/%Y")
    except ValueError as e:
        logger.debug(f"Erreur parsing date_fin '{date_fin}': {e}")
        date_fin_formatted = date_fin

    # Formater la date d'examen
    exam_date = exam_info.get('Date_Examen', '')
    exam_date_formatted = ""
    try:
        if exam_date:
            date_obj = datetime.strptime(exam_date, "%Y-%m-%d")
            exam_date_formatted = date_obj.strftime("%d/%m/%Y")
    except ValueError as e:
        logger.debug(f"Erreur parsing exam_date '{exam_date}': {e}")
        exam_date_formatted = exam_date

    message = f"""📚 **PROPOSITION DE RAFRAÎCHISSEMENT (sans frais supplémentaires)**

Nous avons constaté que vous avez déjà suivi votre formation, mais votre examen est prévu pour le {exam_date_formatted}.

**Pour nous, votre réussite est notre priorité.** Plus vos connaissances sont fraîches au moment de l'examen, plus vos chances de succès sont élevées.

C'est pourquoi nous vous proposons, **sans aucun coût additionnel**, de rejoindre la prochaine session de formation pour rafraîchir vos acquis :

• **{session_type_label}** : du {date_debut_formatted} au {date_fin_formatted}"""

    if type_cours and type_cours != '-None-':
        message += f" ({type_cours})"

    message += """

Si vous souhaitez bénéficier de ce rafraîchissement gratuit, merci de nous le confirmer et nous vous ajouterons à cette session."""

    return message
