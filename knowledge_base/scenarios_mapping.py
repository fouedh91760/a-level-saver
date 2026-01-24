"""
Scenario mapping and detection rules based on 03_AGENT_REDACTEUR knowledge base.

This module defines the 26+ scenarios from CAB Formations documentation
and provides detection logic to map tickets/responses to scenarios.
"""
from typing import List, Dict
import re


# ============================================================================
# SCENARIO DEFINITIONS (from 03_AGENT_REDACTEUR.md)
# ============================================================================

SCENARIOS = {
    # ========== NOUVEAUX CANDIDATS ==========
    "SC-00_NOUVEAU_CANDIDAT": {
        "name": "Nouveau candidat - Proposition dates examen",
        "triggers": [
            "nouveau candidat", "première inscription", "jamais inscrit",
            "pas encore inscrit", "voudrais m'inscrire"
        ],
        "required_fields": ["evalbox", "exam_dates"],
        "forbidden_actions": ["propose_session"],  # Propose exam dates, NOT sessions
        "template_notes": "Propose exam dates (not session dates)"
    },

    "SC-REINSCRIPTION": {
        "name": "Réinscription (2+ opportunités 20€)",
        "triggers": [
            "réinscription", "nouvelle inscription", "deuxième fois",
            "déjà inscrit", "2ème inscription"
        ],
        "required_fields": ["previous_opportunity", "previous_result"],
        "conditions": ["has_previous_20_euro_payment"],
        "template_notes": "Check previous opportunity has result"
    },

    # ========== IDENTIFIANTS ==========
    "SC-01_IDENTIFIANTS_EXAMENT3P": {
        "name": "Demande identifiants ExamenT3P",
        "triggers": [
            "identifiant", "mot de passe", "connexion exament3p",
            "login", "se connecter", "accès plateforme"
        ],
        "mandatory_blocks": [
            "identifiants_exament3p",
            "password_warning",
            "spam_check"
        ],
        "template_notes": "ALWAYS include password warning and spam check"
    },

    # ========== PAIEMENT ==========
    "SC-02_CONFIRMATION_PAIEMENT": {
        "name": "Confirmation de paiement",
        "triggers": [
            "payé", "paiement effectué", "réglé", "règlement",
            "facture", "20 euros", "20€"
        ],
        "required_fields": ["paiement_cma_status"],
        "source_of_truth": "exament3p_paiement_cma",
        "template_notes": "Source of truth: ExamenT3P paiement_cma"
    },

    "SC-03_PAIEMENT_EN_ATTENTE": {
        "name": "Paiement en attente",
        "triggers": [
            "paiement en attente", "pas encore payé", "attente de paiement"
        ],
        "required_fields": ["paiement_cma_status"],
        "template_notes": "Check paiement_cma object in ExamenT3P"
    },

    # ========== DOCUMENTS ==========
    "SC-04_DOCUMENT_MANQUANT": {
        "name": "Document manquant",
        "triggers": [
            "document manquant", "pièce manquante", "justificatif",
            "attestation", "document à fournir"
        ],
        "required_fields": ["exament3p_documents"],
        "source_of_truth": "exament3p_documents",
        "template_notes": "Source of truth: ExamenT3P documents list"
    },

    "SC-05_DOCUMENT_REFUSE": {
        "name": "Document refusé",
        "triggers": [
            "document refusé", "pièce refusée", "non conforme"
        ],
        "required_fields": ["exament3p_documents", "refusal_reason"],
        "template_notes": "Explain reason and what to provide"
    },

    # ========== STATUT DOSSIER ==========
    "SC-06_STATUT_DOSSIER": {
        "name": "Demande de statut du dossier",
        "triggers": [
            "où en est mon dossier", "statut dossier", "avancement",
            "suivi dossier", "état de mon dossier"
        ],
        "required_fields": [
            "exament3p_documents",
            "paiement_cma_status",
            "session_assigned"
        ],
        "template_notes": "Provide comprehensive status from all sources"
    },

    # ========== SESSIONS ==========
    "SC-17_CONFIRMATION_SESSION": {
        "name": "Confirmation choix de session",
        "triggers": [
            "je choisis", "je confirme la session", "session du",
            "je préfère la session", "je valide"
        ],
        "required_fields": ["chosen_session_id", "session_details"],
        "crm_update": True,
        "update_fields": [
            "Session_choisie",
            "Date_debut_session",
            "Date_fin_session"
        ],
        "template_notes": "MUST update CRM with chosen session"
    },

    # ========== REPORT ==========
    "SC-15a_REPORT_SANS_DOSSIER": {
        "name": "Report - Candidat sans dossier CMA",
        "triggers": ["report", "reporter", "décaler", "changer date"],
        "conditions": ["no_cma_file"],
        "detection": "Date_de_depot_CMA is null",
        "template_notes": "Can report easily, no CMA file yet"
    },

    "SC-15b_REPORT_AVANT_CLOTURE": {
        "name": "Report - Dossier CMA non clôturé",
        "triggers": ["report", "reporter", "décaler"],
        "conditions": ["has_cma_file", "not_closed"],
        "detection": "Date_de_depot_CMA exists but Date_de_cloture is null",
        "template_notes": "Report possible but need to inform CMA"
    },

    "SC-15c_REPORT_APRES_CLOTURE": {
        "name": "Report - Dossier CMA clôturé",
        "triggers": ["report", "reporter", "décaler"],
        "conditions": ["cma_file_closed"],
        "detection": "Date_de_cloture exists",
        "template_notes": "Report difficult, CMA file closed"
    },

    # ========== RÉSULTATS ==========
    "SC-20_RESULTAT_POSITIF": {
        "name": "Résultat examen positif (admis)",
        "triggers": [
            "admis", "réussi", "validé", "résultat positif",
            "j'ai réussi", "examen validé"
        ],
        "required_fields": ["exam_result"],
        "crm_update": True,
        "template_notes": "Congratulate and inform next steps"
    },

    "SC-21_RESULTAT_NEGATIF": {
        "name": "Résultat examen négatif (échec)",
        "triggers": [
            "échoué", "refusé", "non admis", "résultat négatif",
            "raté l'examen"
        ],
        "required_fields": ["exam_result"],
        "template_notes": "Empathetic tone, propose reinscription"
    },

    # ========== RÉCLAMATIONS ==========
    "SC-25_RECLAMATION": {
        "name": "Réclamation client",
        "triggers": [
            "réclamation", "inadmissible", "inacceptable",
            "pas de réponse", "insatisfait", "problème grave"
        ],
        "tone": "apologetic + reassuring",
        "escalation": True,
        "template_notes": "Apologize, explain, provide solution"
    },

    # ========== ANCIEN DOSSIER (ALERTE) ==========
    "SC-ANCIEN_DOSSIER": {
        "name": "Ancien dossier CMA (avant 01/11/2025)",
        "triggers": [],  # Detected by date, not keywords
        "detection": "Date_de_depot_CMA < 01/11/2025",
        "action": "create_internal_alert_draft",
        "stop_workflow": True,
        "template_notes": "STOP - Create internal alert, do not respond to customer"
    },

    # ========== HORS SCOPE ==========
    "SC-HORS_PARTENARIAT": {
        "name": "Formation hors partenariat Uber",
        "triggers": [
            "taxi", "ambulance", "autre formation", "pas uber",
            "sans uber", "hors uber"
        ],
        "detection": "Amount != 20€ (in CRM Deal) OR explicit keywords",
        "routing": "Contact department",
        "stop_workflow": True,
        "template_notes": "Route to Contact, do NOT draft response"
    },

    "SC-VTC_HORS_PARTENARIAT": {
        "name": "VTC hors partenariat",
        "triggers": [
            # Removed "vtc" alone - too broad, all DOC tickets contain "vtc"
            # Detection based on CRM Amount field instead
        ],
        "detection": "Amount != 20€ (checked via CRM data)",
        "routing": "DOCS CAB",
        "stop_workflow": True,
        "template_notes": "Route to DOCS CAB if not Uber partnership"
    },

    # ========== SPAM ==========
    "SC-SPAM": {
        "name": "Spam détecté",
        "triggers": [
            "viagra", "casino", "lottery", "prince nigerian",
            "enlarge", "click here"
        ],
        "action": "close_ticket",
        "no_crm_note": True,
        "stop_workflow": True,
        "template_notes": "Close ticket, NO CRM note"
    }
}


# ============================================================================
# MANDATORY BLOCKS (from 03_AGENT_REDACTEUR.md)
# ============================================================================

MANDATORY_BLOCKS = {
    "identifiants_exament3p": {
        "when": "compte_exament3p_existe == True",
        "format": """
🔐 **Vos identifiants ExamenT3P** :
• **Identifiant** : [email du candidat]
• **Mot de passe** : [mot_de_passe_exament3p]

⚠️ Ces identifiants sont personnels et confidentiels. Ne les communiquez jamais à qui que ce soit.
"""
    },

    "password_warning": {
        "when": "always",
        "format": "⚠️ Ne communiquez jamais vos identifiants à qui que ce soit."
    },

    "elearning_link": {
        "when": "always",
        "format": "🎓 **Formation e-learning** : [lien_elearning_personnalisé]"
    },

    "spam_warning": {
        "when": "email_sent",
        "format": "📧 Vérifiez vos spams/courriers indésirables si vous ne recevez pas notre email."
    }
}


# ============================================================================
# FORBIDDEN TERMS (from 03_AGENT_REDACTEUR.md)
# ============================================================================

FORBIDDEN_TERMS = [
    "BFS",           # Internal code
    "Evalbox",       # Old system name
    "CDJ",           # Internal session code
    "CDS",           # Internal session code
    "20€",           # Say "frais de dossier" instead
    "Montreuil"      # Internal location
]


# ============================================================================
# SCENARIO DETECTION FUNCTIONS
# ============================================================================

def detect_scenario_from_text(
    subject: str,
    customer_message: str,
    crm_data: Dict = None
) -> List[str]:
    """
    Detect which scenarios apply based on subject, message, and CRM data.

    Returns list of scenario IDs (can be multiple scenarios).
    """
    detected_scenarios = []
    combined_text = (subject + " " + customer_message).lower()

    # =========================================================================
    # PRIORITY 1: CRM-based detection (HORS_PARTENARIAT)
    # =========================================================================
    if crm_data:
        # Check Amount field - Uber partnership = 20€
        amount = crm_data.get("Amount", 0)

        # If Amount != 20€ and != 0 (0 means not set yet) → HORS PARTENARIAT
        if amount != 0 and amount != 20:
            detected_scenarios.append("SC-HORS_PARTENARIAT")
            # Also check if it's VTC specifically (vs taxi/ambulance)
            if "vtc" in combined_text and "taxi" not in combined_text and "ambulance" not in combined_text:
                detected_scenarios.append("SC-VTC_HORS_PARTENARIAT")

    # =========================================================================
    # PRIORITY 2: Text-based detection
    # =========================================================================
    # Check each scenario's triggers
    for scenario_id, scenario_def in SCENARIOS.items():
        # Skip if already detected via CRM
        if scenario_id in detected_scenarios:
            continue

        # Skip scenarios without triggers (CRM-based or date-based detection)
        triggers = scenario_def.get("triggers", [])
        if not triggers:
            continue

        # Check if any trigger matches
        for trigger in triggers:
            if trigger.lower() in combined_text:
                detected_scenarios.append(scenario_id)
                break

    # =========================================================================
    # Special detection: ANCIEN_DOSSIER (date-based)
    # =========================================================================
    if crm_data:
        date_depot_cma = crm_data.get("Date_de_depot_CMA")
        if date_depot_cma and date_depot_cma < "2025-11-01":
            detected_scenarios.append("SC-ANCIEN_DOSSIER")

    # =========================================================================
    # Special detection: REPORT type (SANS_DOSSIER, AVANT_CLOTURE, APRES_CLOTURE)
    # =========================================================================
    if any("report" in s.lower() for s in detected_scenarios):
        if crm_data:
            date_depot = crm_data.get("Date_de_depot_CMA")
            date_cloture = crm_data.get("Date_de_cloture")

            if not date_depot:
                detected_scenarios.append("SC-15a_REPORT_SANS_DOSSIER")
            elif not date_cloture:
                detected_scenarios.append("SC-15b_REPORT_AVANT_CLOTURE")
            else:
                detected_scenarios.append("SC-15c_REPORT_APRES_CLOTURE")

    return detected_scenarios


def get_mandatory_blocks_for_scenario(scenario_id: str) -> List[str]:
    """Get list of mandatory blocks for a given scenario."""
    scenario_def = SCENARIOS.get(scenario_id, {})
    return scenario_def.get("mandatory_blocks", [])


def validate_response_compliance(response_text: str, scenario_id: str) -> Dict:
    """
    Validate if a response complies with mandatory elements for scenario.

    Returns:
        {
            "compliant": bool,
            "missing_blocks": List[str],
            "forbidden_terms_found": List[str]
        }
    """
    missing_blocks = []
    forbidden_found = []

    # Check mandatory blocks
    required_blocks = get_mandatory_blocks_for_scenario(scenario_id)
    for block_id in required_blocks:
        block_def = MANDATORY_BLOCKS.get(block_id, {})
        # Simple keyword check (can be enhanced)
        if block_id == "identifiants_exament3p":
            if "identifiant" not in response_text.lower():
                missing_blocks.append(block_id)
        elif block_id == "password_warning":
            if "ne communiquez jamais" not in response_text.lower():
                missing_blocks.append(block_id)
        elif block_id == "elearning_link":
            if "e-learning" not in response_text.lower() and "formation" not in response_text.lower():
                missing_blocks.append(block_id)
        elif block_id == "spam_warning":
            if "spam" not in response_text.lower():
                missing_blocks.append(block_id)

    # Check forbidden terms
    for term in FORBIDDEN_TERMS:
        if term.lower() in response_text.lower():
            forbidden_found.append(term)

    return {
        "compliant": len(missing_blocks) == 0 and len(forbidden_found) == 0,
        "missing_blocks": missing_blocks,
        "forbidden_terms_found": forbidden_found
    }


def get_scenario_template_notes(scenario_id: str) -> str:
    """Get template notes for a scenario."""
    scenario_def = SCENARIOS.get(scenario_id, {})
    return scenario_def.get("template_notes", "")


def should_stop_workflow(scenario_id: str) -> bool:
    """Check if scenario requires stopping the workflow."""
    scenario_def = SCENARIOS.get(scenario_id, {})
    return scenario_def.get("stop_workflow", False)


def requires_crm_update(scenario_id: str) -> bool:
    """Check if scenario requires CRM update."""
    scenario_def = SCENARIOS.get(scenario_id, {})
    return scenario_def.get("crm_update", False)


def get_crm_update_fields(scenario_id: str) -> List[str]:
    """Get list of CRM fields to update for scenario."""
    scenario_def = SCENARIOS.get(scenario_id, {})
    return scenario_def.get("update_fields", [])


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Example usage
    subject = "Demande d'identifiants pour ExamenT3P"
    message = "Bonjour, je n'arrive pas à me connecter, pouvez-vous me renvoyer mes identifiants ?"

    scenarios = detect_scenario_from_text(subject, message)
    print(f"Scénarios détectés : {scenarios}")

    for scenario_id in scenarios:
        print(f"\n{scenario_id}:")
        print(f"  - Template notes: {get_scenario_template_notes(scenario_id)}")
        print(f"  - Mandatory blocks: {get_mandatory_blocks_for_scenario(scenario_id)}")
        print(f"  - Stop workflow: {should_stop_workflow(scenario_id)}")
        print(f"  - Requires CRM update: {requires_crm_update(scenario_id)}")
