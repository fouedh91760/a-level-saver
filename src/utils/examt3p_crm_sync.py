"""
Synchronisation ExamT3P → Zoho CRM.

Ce helper synchronise les données extraites d'ExamT3P vers le CRM Zoho.
ExamT3P est la SOURCE DE VÉRITÉ pour le statut du dossier candidat.

RÈGLES CRITIQUES DE MODIFICATION:
=================================

1. JAMAIS MODIFIER Date_examen_VTC automatiquement SI:
   - Evalbox ∈ {"VALIDE CMA", "Convoc CMA reçue"}
   - ET Date_Cloture_Inscription < aujourd'hui (passée)
   → Seul un humain peut traiter (report avec justif ou repayer)

2. Report POSSIBLE automatiquement SI:
   - Date_Cloture_Inscription >= aujourd'hui (pas encore passée)
   → La CMA accepte les reports avant clôture

3. CAS Refusé CMA + Clôture passée:
   - Le candidat sera décalé sur la prochaine session automatiquement
   - SEULEMENT s'il corrige avant la clôture de la nouvelle session

MAPPING EXAMT3P → CRM (Statut du Dossier):
==========================================
- "En cours de composition"     → Evalbox = "Dossier crée"
- "En attente de paiement"      → Evalbox = "Pret a payer"
- "En cours d'instruction"      → Evalbox = "Dossier Synchronisé"
- "Incomplet"                   → Evalbox = "Refusé CMA"
- "Valide"                      → Evalbox = "VALIDE CMA"
- "En attente de convocation"   → Evalbox = "Convoc CMA reçue"

NOTE: "Documents manquants" et "Documents refusés" sont utilisés
      AVANT la création du compte ExamT3P (gestion interne CAB).

Autres champs synchronisés:
- identifiant                   → IDENTIFIANT_EVALBOX (si vide)
- mot_de_passe                  → MDP_EVALBOX (si vide)
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Mapping ExamT3P "Statut du Dossier" → Evalbox CRM
# Basé sur les valeurs réelles de la plateforme ExamT3P
EXAMT3P_STATUT_DOSSIER_MAPPING = {
    # Statut exact ExamT3P → Evalbox CRM
    'En cours de composition': 'Dossier crée',
    'EN COURS DE COMPOSITION': 'Dossier crée',
    'En attente de paiement': 'Pret a payer',
    'EN ATTENTE DE PAIEMENT': 'Pret a payer',
    "En cours d'instruction": 'Dossier Synchronisé',
    "EN COURS D'INSTRUCTION": 'Dossier Synchronisé',
    'Incomplet': 'Refusé CMA',
    'INCOMPLET': 'Refusé CMA',
    'Valide': 'VALIDE CMA',
    'VALIDE': 'VALIDE CMA',
    'En attente de convocation': 'Convoc CMA reçue',
    'EN ATTENTE DE CONVOCATION': 'Convoc CMA reçue',
}

# Statuts qui bloquent la modification de Date_examen_VTC
BLOCKING_EVALBOX_STATUSES = ['VALIDE CMA', 'Convoc CMA reçue']


def is_date_past(date_str: str) -> bool:
    """Vérifie si une date est dans le passé."""
    if not date_str:
        return False
    try:
        if 'T' in str(date_str):
            date_obj = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
            date_obj = date_obj.replace(tzinfo=None)
        else:
            date_obj = datetime.strptime(str(date_str), "%Y-%m-%d")
        return date_obj.date() < datetime.now().date()
    except:
        return False


def can_modify_exam_date(evalbox_status: str, date_cloture: str) -> Tuple[bool, str]:
    """
    Vérifie si on peut modifier la date d'examen automatiquement.

    RÈGLE CRITIQUE:
    - Si Evalbox ∈ {"VALIDE CMA", "Convoc CMA reçue"} ET clôture passée
    - → JAMAIS modifier automatiquement

    Returns:
        (can_modify: bool, reason: str)
    """
    if evalbox_status in BLOCKING_EVALBOX_STATUSES:
        if is_date_past(date_cloture):
            return False, (
                f"BLOCAGE: Evalbox={evalbox_status} + clôture passée. "
                "Report uniquement avec justificatif de force majeure. "
                "Action humaine requise."
            )
        else:
            # Clôture pas encore passée, modification possible
            return True, "Clôture future, modification autorisée"

    return True, "Statut permet la modification"


def determine_evalbox_from_examt3p(examt3p_data: Dict[str, Any]) -> Optional[str]:
    """
    Détermine la valeur Evalbox à partir des données ExamT3P.

    Utilise le champ "Statut du Dossier" (statut_dossier ou statut_principal)
    de la plateforme ExamT3P pour déterminer la valeur Evalbox CRM.

    Mapping:
    - "En cours de composition"     → "Dossier crée"
    - "En attente de paiement"      → "Pret a payer"
    - "En cours d'instruction"      → "Dossier Synchronisé"
    - "Incomplet"                   → "Refusé CMA"
    - "Valide"                      → "VALIDE CMA"
    - "En attente de convocation"   → "Convoc CMA reçue"

    Returns:
        Valeur Evalbox ou None si pas de mapping trouvé
    """
    if not examt3p_data:
        return None

    # Récupérer le "Statut du Dossier" de ExamT3P
    # Le champ peut s'appeler statut_dossier ou statut_principal selon l'extraction
    statut_dossier = (
        examt3p_data.get('statut_dossier') or
        examt3p_data.get('statut_principal') or
        ''
    ).strip()

    if not statut_dossier:
        logger.warning("  ⚠️ Pas de statut_dossier dans les données ExamT3P")
        return None

    # Chercher le mapping exact
    for examt3p_value, evalbox_value in EXAMT3P_STATUT_DOSSIER_MAPPING.items():
        if statut_dossier.lower() == examt3p_value.lower():
            logger.info(f"  📊 Mapping ExamT3P '{statut_dossier}' → Evalbox '{evalbox_value}'")
            return evalbox_value

    # Chercher une correspondance partielle (au cas où)
    statut_lower = statut_dossier.lower()
    if 'composition' in statut_lower:
        logger.info(f"  📊 Mapping partiel '{statut_dossier}' → Evalbox 'Dossier crée'")
        return 'Dossier crée'
    elif 'paiement' in statut_lower:
        logger.info(f"  📊 Mapping partiel '{statut_dossier}' → Evalbox 'Pret a payer'")
        return 'Pret a payer'
    elif 'instruction' in statut_lower:
        logger.info(f"  📊 Mapping partiel '{statut_dossier}' → Evalbox 'Dossier Synchronisé'")
        return 'Dossier Synchronisé'
    elif 'incomplet' in statut_lower:
        logger.info(f"  📊 Mapping partiel '{statut_dossier}' → Evalbox 'Refusé CMA'")
        return 'Refusé CMA'
    elif 'valide' in statut_lower and 'convocation' not in statut_lower:
        logger.info(f"  📊 Mapping partiel '{statut_dossier}' → Evalbox 'VALIDE CMA'")
        return 'VALIDE CMA'
    elif 'convocation' in statut_lower:
        logger.info(f"  📊 Mapping partiel '{statut_dossier}' → Evalbox 'Convoc CMA reçue'")
        return 'Convoc CMA reçue'

    logger.warning(f"  ⚠️ Statut ExamT3P non reconnu: '{statut_dossier}'")
    return None


def sync_examt3p_to_crm(
    deal_id: str,
    deal_data: Dict[str, Any],
    examt3p_data: Dict[str, Any],
    crm_client,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Synchronise les données ExamT3P vers le CRM Zoho.

    Args:
        deal_id: ID du deal CRM
        deal_data: Données actuelles du deal
        examt3p_data: Données extraites d'ExamT3P
        crm_client: Client CRM Zoho
        dry_run: Si True, ne fait pas les mises à jour (simulation)

    Returns:
        {
            'sync_performed': bool,
            'changes_made': List[Dict],  # Liste des changements
            'blocked_changes': List[Dict],  # Changements bloqués par règles critiques
            'crm_updated': bool,
            'note_content': str  # Contenu pour note CRM
        }
    """
    logger.info(f"🔄 Synchronisation ExamT3P → CRM pour deal {deal_id}")

    result = {
        'sync_performed': False,
        'changes_made': [],
        'blocked_changes': [],
        'crm_updated': False,
        'note_content': ''
    }

    if not examt3p_data or not examt3p_data.get('compte_existe'):
        logger.info("  ℹ️ Pas de données ExamT3P à synchroniser")
        return result

    updates_to_apply = {}
    current_evalbox = deal_data.get('Evalbox', '')
    current_date_cloture = None

    # Récupérer la date de clôture si on a une date d'examen
    date_examen_vtc = deal_data.get('Date_examen_VTC')
    if date_examen_vtc and isinstance(date_examen_vtc, dict):
        current_date_cloture = date_examen_vtc.get('Date_Cloture_Inscription')

    # ================================================================
    # 1. SYNCHRONISATION EVALBOX
    # ================================================================
    new_evalbox = determine_evalbox_from_examt3p(examt3p_data)

    if new_evalbox and new_evalbox != current_evalbox:
        logger.info(f"  📊 Evalbox: '{current_evalbox}' → '{new_evalbox}'")
        updates_to_apply['Evalbox'] = new_evalbox
        result['changes_made'].append({
            'field': 'Evalbox',
            'old_value': current_evalbox,
            'new_value': new_evalbox,
            'source': 'examt3p'
        })

    # ================================================================
    # 2. SYNCHRONISATION IDENTIFIANTS (si vides dans CRM)
    # ================================================================
    crm_identifiant = deal_data.get('IDENTIFIANT_EVALBOX', '')
    crm_password = deal_data.get('MDP_EVALBOX', '')

    examt3p_identifiant = examt3p_data.get('identifiant', '')
    examt3p_password = examt3p_data.get('mot_de_passe', '')

    if not crm_identifiant and examt3p_identifiant:
        logger.info(f"  🔑 IDENTIFIANT_EVALBOX: vide → '{examt3p_identifiant}'")
        updates_to_apply['IDENTIFIANT_EVALBOX'] = examt3p_identifiant
        result['changes_made'].append({
            'field': 'IDENTIFIANT_EVALBOX',
            'old_value': '',
            'new_value': examt3p_identifiant,
            'source': 'examt3p'
        })

    if not crm_password and examt3p_password:
        logger.info(f"  🔑 MDP_EVALBOX: vide → '***'")
        updates_to_apply['MDP_EVALBOX'] = examt3p_password
        result['changes_made'].append({
            'field': 'MDP_EVALBOX',
            'old_value': '',
            'new_value': '***',  # Masqué pour le log
            'source': 'examt3p'
        })

    # ================================================================
    # 3. VÉRIFICATION RÈGLES CRITIQUES POUR DATE EXAMEN
    # ================================================================
    # Note: La modification de Date_examen_VTC n'est PAS faite automatiquement
    # depuis ExamT3P. Elle est gérée par ticket_info_extractor.py
    # Mais on vérifie quand même si on est dans un état bloqué

    effective_evalbox = new_evalbox or current_evalbox
    can_modify, reason = can_modify_exam_date(effective_evalbox, current_date_cloture)

    if not can_modify:
        result['blocked_changes'].append({
            'field': 'Date_examen_VTC',
            'reason': reason,
            'evalbox': effective_evalbox,
            'date_cloture': current_date_cloture
        })
        logger.warning(f"  🔒 {reason}")

    # ================================================================
    # 4. APPLIQUER LES MISES À JOUR
    # ================================================================
    if updates_to_apply and not dry_run:
        try:
            from config import settings
            url = f"{settings.zoho_crm_api_url}/Deals/{deal_id}"
            payload = {"data": [updates_to_apply]}

            response = crm_client._make_request("PUT", url, json=payload)

            if response.get('data'):
                result['crm_updated'] = True
                logger.info(f"  ✅ CRM mis à jour: {list(updates_to_apply.keys())}")
            else:
                logger.error(f"  ❌ Échec mise à jour CRM: {response}")

        except Exception as e:
            logger.error(f"  ❌ Erreur mise à jour CRM: {e}")
    elif updates_to_apply and dry_run:
        logger.info(f"  🔍 DRY RUN: Mises à jour simulées: {list(updates_to_apply.keys())}")
        result['crm_updated'] = False

    # ================================================================
    # 5. GÉNÉRER CONTENU POUR NOTE CRM
    # ================================================================
    if result['changes_made'] or result['blocked_changes']:
        note_lines = ["📊 SYNC EXAMT3P → CRM", f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}"]

        if result['changes_made']:
            note_lines.append("\n✅ CHANGEMENTS APPLIQUÉS:")
            for change in result['changes_made']:
                if change['field'] == 'MDP_EVALBOX':
                    note_lines.append(f"  - {change['field']}: *** → ***")
                else:
                    note_lines.append(f"  - {change['field']}: '{change['old_value']}' → '{change['new_value']}'")

        if result['blocked_changes']:
            note_lines.append("\n🔒 CHANGEMENTS BLOQUÉS (règle critique):")
            for blocked in result['blocked_changes']:
                note_lines.append(f"  - {blocked['field']}: {blocked['reason']}")

        result['note_content'] = "\n".join(note_lines)

    result['sync_performed'] = True
    return result


def get_sync_status_message(
    evalbox_status: str,
    date_cloture: str,
    is_report_request: bool = False
) -> Optional[str]:
    """
    Génère un message approprié pour le candidat selon le statut de sync.

    Utilisé quand le candidat demande un report mais qu'on ne peut pas le faire.

    IMPORTANT: Ne jamais dire "nous contacter" - communication par EMAIL uniquement.
    """
    can_modify, reason = can_modify_exam_date(evalbox_status, date_cloture)

    if not can_modify and is_report_request:
        # Formater la date de clôture
        date_formatted = ""
        if date_cloture:
            try:
                if 'T' in str(date_cloture):
                    date_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
                else:
                    date_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
                date_formatted = date_obj.strftime("%d/%m/%Y")
            except:
                date_formatted = str(date_cloture)

        return f"""Votre inscription à l'examen VTC a été validée par la CMA et les inscriptions sont maintenant clôturées.

**Un report n'est possible qu'avec un justificatif de force majeure** (certificat médical ou autre document attestant de l'impossibilité de vous présenter à l'examen).

**Pour demander un report, merci de nous transmettre par email :**
1. Votre justificatif de force majeure (certificat médical, etc.)
2. Une brève explication de votre situation

Nous soumettrons votre demande à la CMA pour validation.

**Important :** Sans justificatif valide, des frais de réinscription de 241€ seront à prévoir pour une nouvelle inscription."""

    return None
