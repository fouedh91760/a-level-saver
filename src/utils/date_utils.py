"""
Utilitaires centralisés pour le parsing de dates.

Ce module fournit des fonctions robustes pour parser les dates
provenant de diverses sources (CRM, ExamT3P, API) avec support
de multiples formats.
"""
from datetime import datetime, date, timedelta
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

# Formats de date supportés (ordre de priorité)
DATE_FORMATS = [
    "%Y-%m-%d",                    # 2026-03-31
    "%Y-%m-%dT%H:%M:%S",           # 2026-03-31T10:30:00
    "%Y-%m-%dT%H:%M:%S.%f",        # 2026-03-31T10:30:00.000
    "%Y-%m-%dT%H:%M:%S%z",         # 2026-03-31T10:30:00+00:00
    "%Y-%m-%dT%H:%M:%SZ",          # 2026-03-31T10:30:00Z
    "%d/%m/%Y",                    # 31/03/2026
    "%d-%m-%Y",                    # 31-03-2026
]


def parse_date_flexible(
    date_input: Union[str, date, datetime, None],
    field_name: str = "date"
) -> Optional[date]:
    """
    Parse une date avec support de multiples formats.

    Args:
        date_input: La valeur à parser (string, date, datetime ou None)
        field_name: Nom du champ pour le logging (optionnel)

    Returns:
        Un objet date ou None si le parsing échoue

    Examples:
        >>> parse_date_flexible("2026-03-31")
        datetime.date(2026, 3, 31)
        >>> parse_date_flexible("2026-03-31T10:30:00Z")
        datetime.date(2026, 3, 31)
        >>> parse_date_flexible("31/03/2026")
        datetime.date(2026, 3, 31)
        >>> parse_date_flexible(None)
        None
    """
    if date_input is None:
        return None

    # Si c'est déjà un objet date
    if isinstance(date_input, date) and not isinstance(date_input, datetime):
        return date_input

    # Si c'est un datetime
    if isinstance(date_input, datetime):
        return date_input.date()

    # Convertir en string
    date_str = str(date_input).strip()
    if not date_str:
        return None

    # Nettoyer la string (remplacer Z par +00:00 pour fromisoformat)
    date_str_clean = date_str.replace('Z', '+00:00')

    # Essayer fromisoformat d'abord (plus robuste pour les formats ISO)
    try:
        # Prendre juste les 10 premiers caractères pour la date pure
        if len(date_str) >= 10:
            base_date = date_str[:10]
            return datetime.strptime(base_date, "%Y-%m-%d").date()
    except ValueError:
        pass

    # Essayer les formats standards
    for fmt in DATE_FORMATS:
        try:
            # Tronquer la string à la longueur du format attendu
            expected_len = len(datetime.now().strftime(fmt))
            truncated = date_str_clean[:expected_len] if len(date_str_clean) > expected_len else date_str_clean
            return datetime.strptime(truncated, fmt).date()
        except ValueError:
            continue

    # Aucun format n'a fonctionné
    logger.warning(f"Impossible de parser {field_name}: '{date_str}'")
    return None


def parse_datetime_flexible(
    datetime_input: Union[str, date, datetime, None],
    field_name: str = "datetime"
) -> Optional[datetime]:
    """
    Parse une datetime avec support de multiples formats.

    Args:
        datetime_input: La valeur à parser
        field_name: Nom du champ pour le logging

    Returns:
        Un objet datetime ou None si le parsing échoue
    """
    if datetime_input is None:
        return None

    # Si c'est déjà un datetime
    if isinstance(datetime_input, datetime):
        return datetime_input

    # Si c'est une date
    if isinstance(datetime_input, date):
        return datetime.combine(datetime_input, datetime.min.time())

    # Convertir en string
    dt_str = str(datetime_input).strip()
    if not dt_str:
        return None

    # Nettoyer
    dt_str_clean = dt_str.replace('Z', '+00:00')

    # Essayer fromisoformat
    try:
        return datetime.fromisoformat(dt_str_clean)
    except ValueError:
        pass

    # Essayer les formats standards
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue

    logger.warning(f"Impossible de parser {field_name}: '{dt_str}'")
    return None


def format_date_for_display(
    date_input: Union[str, date, datetime, None],
    output_format: str = "%d/%m/%Y"
) -> str:
    """
    Formate une date pour affichage (par défaut: DD/MM/YYYY).

    Args:
        date_input: La valeur à formater
        output_format: Format de sortie (défaut: %d/%m/%Y)

    Returns:
        String formatée ou chaîne vide si parsing échoue
    """
    parsed = parse_date_flexible(date_input)
    if parsed is None:
        return ""
    return parsed.strftime(output_format)


def is_date_before(
    date1: Union[str, date, datetime, None],
    date2: Union[str, date, datetime, None]
) -> Optional[bool]:
    """
    Compare deux dates. Retourne True si date1 < date2.

    Returns:
        True/False ou None si une date n'est pas parsable
    """
    d1 = parse_date_flexible(date1)
    d2 = parse_date_flexible(date2)

    if d1 is None or d2 is None:
        return None

    return d1 < d2


def is_date_after(
    date1: Union[str, date, datetime, None],
    date2: Union[str, date, datetime, None]
) -> Optional[bool]:
    """
    Compare deux dates. Retourne True si date1 > date2.

    Returns:
        True/False ou None si une date n'est pas parsable
    """
    d1 = parse_date_flexible(date1)
    d2 = parse_date_flexible(date2)

    if d1 is None or d2 is None:
        return None

    return d1 > d2


def days_between(
    date1: Union[str, date, datetime, None],
    date2: Union[str, date, datetime, None]
) -> Optional[int]:
    """
    Calcule le nombre de jours entre deux dates (date2 - date1).

    Returns:
        Nombre de jours (positif si date2 > date1) ou None si parsing échoue
    """
    d1 = parse_date_flexible(date1)
    d2 = parse_date_flexible(date2)

    if d1 is None or d2 is None:
        return None

    return (d2 - d1).days


def add_days(
    date_input: Union[str, date, datetime, None],
    days: int
) -> Optional[date]:
    """
    Ajoute des jours à une date.

    Args:
        date_input: Date de départ
        days: Nombre de jours à ajouter (peut être négatif)

    Returns:
        Nouvelle date ou None si parsing échoue
    """
    parsed = parse_date_flexible(date_input)
    if parsed is None:
        return None

    return parsed + timedelta(days=days)
