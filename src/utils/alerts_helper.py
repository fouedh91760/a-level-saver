"""
Helper pour gérer les alertes temporaires.

Les alertes sont stockées dans alerts/active_alerts.yaml et permettent
d'informer l'agent rédacteur de bugs/situations temporaires à prendre
en compte dans les réponses aux candidats.
"""
import logging
import yaml
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Chemin vers le fichier d'alertes
ALERTS_FILE = Path(__file__).parent.parent.parent / "alerts" / "active_alerts.yaml"


def load_alerts() -> List[Dict[str, Any]]:
    """
    Charge toutes les alertes depuis le fichier YAML.

    Returns:
        Liste des alertes (actives et inactives)
    """
    try:
        if not ALERTS_FILE.exists():
            logger.warning(f"Fichier d'alertes non trouvé: {ALERTS_FILE}")
            return []

        with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        return data.get('alerts', []) if data else []

    except Exception as e:
        logger.error(f"Erreur chargement alertes: {e}")
        return []


def get_active_alerts(
    evalbox_status: Optional[str] = None,
    department: Optional[str] = None,
    reference_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    Récupère les alertes actives et applicables au contexte.

    Args:
        evalbox_status: Statut Evalbox du candidat (pour filtrage)
        department: Département du candidat (pour filtrage)
        reference_date: Date de référence (défaut: aujourd'hui)

    Returns:
        Liste des alertes actives et applicables
    """
    if reference_date is None:
        reference_date = date.today()

    all_alerts = load_alerts()
    active_alerts = []

    for alert in all_alerts:
        # Vérifier si active
        if not alert.get('active', True):
            continue

        # Vérifier date de début
        start_date_str = alert.get('start_date')
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                if reference_date < start_date:
                    continue
            except ValueError:
                logger.warning(f"Format date invalide pour alerte {alert.get('id')}: {start_date_str}")

        # Vérifier date de fin
        end_date_str = alert.get('end_date')
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                if reference_date > end_date:
                    continue
            except ValueError:
                logger.warning(f"Format date invalide pour alerte {alert.get('id')}: {end_date_str}")

        # Vérifier filtres applies_to
        applies_to = alert.get('applies_to', {})

        # Filtre Evalbox
        if evalbox_status and applies_to.get('evalbox'):
            if evalbox_status not in applies_to['evalbox']:
                continue

        # Filtre département
        if department and applies_to.get('departments'):
            if department not in applies_to['departments']:
                continue

        active_alerts.append(alert)

    logger.info(f"📢 {len(active_alerts)} alerte(s) active(s) trouvée(s)")
    return active_alerts


def format_alerts_for_prompt(alerts: List[Dict[str, Any]]) -> str:
    """
    Formate les alertes pour inclusion dans le prompt de l'agent rédacteur.

    Args:
        alerts: Liste des alertes actives

    Returns:
        Texte formaté pour le prompt
    """
    if not alerts:
        return ""

    lines = [
        "",
        "=" * 60,
        "🚨 ALERTES TEMPORAIRES - À PRENDRE EN COMPTE",
        "=" * 60,
    ]

    for alert in alerts:
        lines.append("")
        lines.append(f"📌 {alert.get('title', 'Alerte')}")
        lines.append("-" * 40)

        context = alert.get('context', '').strip()
        if context:
            lines.append(f"Contexte: {context}")

        instruction = alert.get('instruction', '').strip()
        if instruction:
            lines.append("")
            lines.append(f"INSTRUCTION: {instruction}")

        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


def get_alerts_for_response(
    deal_data: Dict[str, Any] = None,
    examt3p_data: Dict[str, Any] = None
) -> str:
    """
    Fonction simplifiée pour récupérer les alertes formatées pour une réponse.

    Args:
        deal_data: Données du deal CRM
        examt3p_data: Données ExamT3P

    Returns:
        Texte formaté des alertes pour le prompt, ou chaîne vide si aucune
    """
    evalbox_status = None
    department = None

    if deal_data:
        evalbox_status = deal_data.get('Evalbox')
        # Extraire département de CMA_de_depot
        cma = deal_data.get('CMA_de_depot', '')
        if cma:
            import re
            match = re.search(r'\b(\d{2,3})\b', str(cma))
            if match:
                department = match.group(1)

    if examt3p_data and not department:
        department = examt3p_data.get('departement')

    alerts = get_active_alerts(
        evalbox_status=evalbox_status,
        department=department
    )

    return format_alerts_for_prompt(alerts)
