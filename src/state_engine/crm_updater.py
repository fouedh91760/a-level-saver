"""
CRMUpdater - Mises à jour CRM déterministes.

Ce module remplace l'extraction [CRM_UPDATES] par l'IA avec une logique
déterministe basée sur l'état détecté et les confirmations explicites.

Principes:
1. Les mises à jour sont définies par l'état, PAS par l'IA
2. Les confirmations candidat sont extraites par matching, PAS par interprétation IA
3. Les règles de blocage (B1) sont toujours respectées
4. Chaque mise à jour est loggée et traceable
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date

from .state_detector import DetectedState

logger = logging.getLogger(__name__)


class CRMUpdateResult:
    """Résultat des mises à jour CRM."""

    def __init__(self):
        self.updates_applied: Dict[str, Any] = {}
        self.updates_blocked: Dict[str, str] = {}  # field -> reason
        self.updates_skipped: Dict[str, str] = {}  # field -> reason
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'updates_applied': self.updates_applied,
            'updates_blocked': self.updates_blocked,
            'updates_skipped': self.updates_skipped,
            'errors': self.errors,
            'success': len(self.errors) == 0
        }


class CRMUpdater:
    """
    Gère les mises à jour CRM de manière déterministe.

    Cas de mise à jour:
    1. CONFIRMATION_SESSION: Extraire le choix du candidat → Session + Preference_horaire
    2. CONFIRMATION_DATE_EXAMEN: Extraire la date choisie → Date_examen_VTC
    3. Sync ExamT3P: Identifiants, Evalbox, etc. (géré ailleurs, mais validation ici)

    Règles de blocage:
    - B1: Ne pas modifier Date_examen_VTC si VALIDE CMA + clôture passée
    """

    # Patterns pour extraire les confirmations de session
    SESSION_CHOICE_PATTERNS = {
        'jour': [
            r'cours du jour',
            r'journée',
            r'matin',
            r'option\s*1',
            r'première option',
            r'cdj',
        ],
        'soir': [
            r'cours du soir',
            r'soirée',
            r'soir',
            r'option\s*2',
            r'deuxième option',
            r'seconde option',
            r'cds',
        ]
    }

    # Patterns pour extraire les confirmations de date
    DATE_CHOICE_PATTERNS = [
        r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
        r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
        r'(\d{1,2})\s+(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})',
    ]

    def __init__(self, crm_client=None):
        """
        Initialise le CRMUpdater.

        Args:
            crm_client: Client Zoho CRM (optionnel, injecté si nécessaire)
        """
        self.crm_client = crm_client

    def determine_updates(
        self,
        state: DetectedState,
        candidate_message: str,
        proposed_sessions: Optional[List[Dict]] = None,
        proposed_dates: Optional[List[Dict]] = None
    ) -> CRMUpdateResult:
        """
        Détermine les mises à jour CRM à effectuer.

        Args:
            state: État détecté
            candidate_message: Message du candidat (pour extraction confirmations)
            proposed_sessions: Sessions qui ont été proposées
            proposed_dates: Dates d'examen qui ont été proposées

        Returns:
            CRMUpdateResult avec les mises à jour à appliquer
        """
        result = CRMUpdateResult()
        context = state.context_data

        # Récupérer la config des mises à jour depuis l'état
        crm_config = state.crm_updates_config

        if not crm_config:
            logger.info("Pas de mise à jour CRM définie pour cet état")
            return result

        method = crm_config.get('method', '')

        # Dispatch selon la méthode
        if method == 'extract_session_choice':
            self._extract_session_choice(
                result, candidate_message, proposed_sessions, context
            )

        elif method == 'extract_date_choice':
            self._extract_date_choice(
                result, candidate_message, proposed_dates, context
            )

        # Vérifier les règles de blocage
        self._apply_blocking_rules(result, context)

        return result

    def _extract_session_choice(
        self,
        result: CRMUpdateResult,
        message: str,
        proposed_sessions: Optional[List[Dict]],
        context: Dict[str, Any]
    ):
        """Extrait le choix de session du message candidat."""
        message_lower = message.lower()

        # Détecter la préférence jour/soir
        preference = None
        confidence_jour = 0
        confidence_soir = 0

        for pattern in self.SESSION_CHOICE_PATTERNS['jour']:
            if re.search(pattern, message_lower):
                confidence_jour += 1

        for pattern in self.SESSION_CHOICE_PATTERNS['soir']:
            if re.search(pattern, message_lower):
                confidence_soir += 1

        if confidence_jour > 0 and confidence_soir == 0:
            preference = 'jour'
        elif confidence_soir > 0 and confidence_jour == 0:
            preference = 'soir'
        elif confidence_jour > 0 and confidence_soir > 0:
            # Ambigu - ne pas mettre à jour
            result.updates_skipped['Preference_horaire'] = "Choix ambigu (jour ET soir mentionnés)"
            logger.warning("Choix de session ambigu - pas de mise à jour")
            return

        if not preference:
            result.updates_skipped['Preference_horaire'] = "Aucune préférence détectée"
            return

        # Mettre à jour Preference_horaire
        result.updates_applied['Preference_horaire'] = preference
        logger.info(f"Préférence horaire détectée: {preference}")

        # Trouver la session correspondante dans les propositions
        if proposed_sessions:
            matching_session = None
            for session in proposed_sessions:
                session_type = session.get('session_type', '')
                if session_type == preference:
                    matching_session = session
                    break

            if matching_session:
                session_id = matching_session.get('id')
                if session_id:
                    result.updates_applied['Session'] = session_id
                    logger.info(f"Session sélectionnée: {matching_session.get('Name', session_id)}")
                else:
                    result.updates_skipped['Session'] = "Session trouvée mais sans ID"
            else:
                result.updates_skipped['Session'] = f"Pas de session {preference} dans les propositions"

    def _extract_date_choice(
        self,
        result: CRMUpdateResult,
        message: str,
        proposed_dates: Optional[List[Dict]],
        context: Dict[str, Any]
    ):
        """Extrait le choix de date d'examen du message candidat."""
        # Extraire les dates du message
        dates_found = []

        for pattern in self.DATE_CHOICE_PATTERNS:
            matches = re.findall(pattern, message)
            for match in matches:
                if isinstance(match, tuple):
                    # Date en lettres (jour, mois, année)
                    try:
                        day, month_name, year = match
                        month_map = {
                            'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4,
                            'mai': 5, 'juin': 6, 'juillet': 7, 'août': 8,
                            'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12
                        }
                        month = month_map.get(month_name.lower(), 0)
                        if month:
                            dt = datetime(int(year), month, int(day))
                            dates_found.append(dt.strftime('%Y-%m-%d'))
                    except:
                        pass
                else:
                    # Date en chiffres
                    normalized = self._normalize_date(match)
                    if normalized:
                        dates_found.append(normalized)

        if not dates_found:
            result.updates_skipped['Date_examen_VTC'] = "Aucune date détectée dans le message"
            return

        if len(dates_found) > 1:
            # Plusieurs dates - essayer de trouver celle qui correspond aux propositions
            if proposed_dates:
                proposed_date_strs = {d.get('Date_Examen') for d in proposed_dates if d.get('Date_Examen')}
                matching = [d for d in dates_found if d in proposed_date_strs]
                if len(matching) == 1:
                    dates_found = matching
                else:
                    result.updates_skipped['Date_examen_VTC'] = "Plusieurs dates mentionnées, choix ambigu"
                    return
            else:
                result.updates_skipped['Date_examen_VTC'] = "Plusieurs dates mentionnées sans référence"
                return

        chosen_date = dates_found[0]

        # Vérifier que la date fait partie des propositions
        if proposed_dates:
            proposed_date_strs = {d.get('Date_Examen') for d in proposed_dates if d.get('Date_Examen')}
            if chosen_date not in proposed_date_strs:
                result.updates_skipped['Date_examen_VTC'] = f"Date {chosen_date} non proposée"
                logger.warning(f"Date choisie {chosen_date} n'est pas dans les propositions")
                return

            # Trouver l'ID de la session d'examen
            for date_info in proposed_dates:
                if date_info.get('Date_Examen') == chosen_date:
                    exam_session_id = date_info.get('id')
                    if exam_session_id:
                        result.updates_applied['Date_examen_VTC'] = exam_session_id
                        logger.info(f"Date d'examen sélectionnée: {chosen_date} (ID: {exam_session_id})")
                    else:
                        result.updates_skipped['Date_examen_VTC'] = "Date trouvée mais sans ID session"
                    break
        else:
            result.updates_skipped['Date_examen_VTC'] = "Pas de dates proposées pour valider le choix"

    def _apply_blocking_rules(
        self,
        result: CRMUpdateResult,
        context: Dict[str, Any]
    ):
        """Applique les règles de blocage (B1, etc.)."""
        # Règle B1: Ne pas modifier Date_examen_VTC si VALIDE CMA + clôture passée
        if 'Date_examen_VTC' in result.updates_applied:
            if not context.get('can_modify_exam_date', True):
                blocked_value = result.updates_applied.pop('Date_examen_VTC')
                result.updates_blocked['Date_examen_VTC'] = (
                    f"Dossier validé (Evalbox={context.get('evalbox')}) "
                    f"et clôture passée - modification impossible sans force majeure"
                )
                logger.warning(f"Mise à jour Date_examen_VTC bloquée par règle B1")

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalise une date en YYYY-MM-DD."""
        try:
            # Essayer DD/MM/YYYY
            dt = datetime.strptime(date_str, '%d/%m/%Y')
            return dt.strftime('%Y-%m-%d')
        except:
            pass

        try:
            # Essayer YYYY-MM-DD
            dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            return dt.strftime('%Y-%m-%d')
        except:
            pass

        return None

    def apply_updates(
        self,
        deal_id: str,
        updates: Dict[str, Any],
        crm_client=None
    ) -> Dict[str, Any]:
        """
        Applique les mises à jour au CRM.

        Args:
            deal_id: ID du deal à mettre à jour
            updates: Dictionnaire des champs à mettre à jour
            crm_client: Client CRM (optionnel, utilise self.crm_client si non fourni)

        Returns:
            Résultat de la mise à jour
        """
        client = crm_client or self.crm_client

        if not client:
            return {'success': False, 'error': 'Pas de client CRM disponible'}

        if not updates:
            return {'success': True, 'message': 'Aucune mise à jour à appliquer'}

        try:
            logger.info(f"Application des mises à jour CRM pour deal {deal_id}: {updates}")
            client.update_deal(deal_id, updates)
            return {
                'success': True,
                'updates_applied': updates
            }
        except Exception as e:
            logger.error(f"Erreur mise à jour CRM: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def format_updates_for_note(self, result: CRMUpdateResult) -> str:
        """Formate les mises à jour pour inclusion dans une note CRM."""
        lines = []

        if result.updates_applied:
            lines.append("**Mises à jour appliquées:**")
            for field, value in result.updates_applied.items():
                lines.append(f"• {field}: {value}")

        if result.updates_blocked:
            lines.append("\n**Mises à jour bloquées:**")
            for field, reason in result.updates_blocked.items():
                lines.append(f"• {field}: {reason}")

        if result.updates_skipped:
            lines.append("\n**Mises à jour ignorées:**")
            for field, reason in result.updates_skipped.items():
                lines.append(f"• {field}: {reason}")

        if result.errors:
            lines.append("\n**Erreurs:**")
            for error in result.errors:
                lines.append(f"• {error}")

        return "\n".join(lines) if lines else "Aucune mise à jour CRM"
