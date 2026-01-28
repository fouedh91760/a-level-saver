#!/usr/bin/env python3
"""
Analyse d'un lot de tickets depuis data/open_doc_tickets.txt
Usage: python analyze_lot.py <start> <end>
Exemple: python analyze_lot.py 11 20  # Pour le lot 2
"""

import json
import sys
import os
from datetime import datetime

# Load .env
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.agents.deal_linking_agent import DealLinkingAgent
from src.agents.triage_agent import TriageAgent
from src.agents.examt3p_agent import ExamT3PAgent
from src.state_engine.state_detector import StateDetector
from src.state_engine.template_engine import TemplateEngine
from src.utils.session_helper import analyze_session_situation
from src.utils.date_examen_vtc_helper import analyze_exam_date_situation


def load_ticket_ids(start: int, end: int) -> list:
    """Charge les IDs des tickets du lot spécifié (1-indexed)."""
    with open("data/open_doc_tickets.txt", "r") as f:
        all_ids = [line.strip() for line in f if line.strip()]
    return all_ids[start-1:end]  # Convert to 0-indexed


def analyze_ticket(ticket_id: str, desk, crm, deal_agent, triage_agent, state_detector, template_engine) -> dict:
    """Analyse complète d'un ticket."""
    result = {"ticket_id": ticket_id}

    try:
        # 1. Récupérer le ticket
        ticket = desk.get_ticket(ticket_id)
        if not ticket:
            result["error"] = "TICKET_NOT_FOUND"
            return result

        result["ticket_number"] = ticket.get("ticketNumber")
        result["subject"] = ticket.get("subject", "")[:80]
        result["status"] = ticket.get("status")

        # 2. Récupérer les threads complets
        threads = desk.get_all_threads_with_full_content(ticket_id)
        result["threads_count"] = len(threads)

        # Extraire le message client (dernier thread incoming)
        customer_message = ""
        for thread in threads:
            if thread.get("direction") == "in":
                customer_message = thread.get("content", "")[:1000]
                break
        result["customer_message_preview"] = customer_message[:300]

        # 3. Lier au deal CRM
        deal_result = deal_agent.process({"ticket_id": ticket_id})
        deal_id = deal_result.get("deal_id")
        result["deal_id"] = deal_id
        result["doublon_uber"] = deal_result.get("has_duplicate_uber_offer", False)

        if not deal_id:
            # Pas de deal trouvé - vérifier si SPAM ou PROSPECT
            spam_check = triage_agent.triage_ticket(
                ticket_subject=ticket.get("subject", ""),
                thread_content=customer_message,
                deal_data=None,  # Pas de deal
                current_department="DOC"
            )
            result["triage_action"] = spam_check.get("action")
            result["triage_intention"] = spam_check.get("detected_intent")
            result["triage_confidence"] = spam_check.get("confidence")

            if spam_check.get("action") == "SPAM":
                result["status"] = "SPAM_TO_CLOSE"
                result["spam_reason"] = spam_check.get("reason")
            elif spam_check.get("action") == "ROUTE":
                result["status"] = "PROSPECT_TO_ROUTE"
                result["route_to"] = spam_check.get("target_department")
            else:
                result["status"] = "NO_DEAL_NEEDS_REVIEW"

            result["error"] = "NO_DEAL_FOUND"
            return result

        # 4. Récupérer les données CRM directement
        deal_data = crm.get_deal(deal_id)
        if not deal_data:
            result["error"] = "DEAL_NOT_FETCHED"
            return result

        result["deal_name"] = deal_data.get("Deal_Name", "")
        result["evalbox"] = deal_data.get("Evalbox")
        result["amount"] = deal_data.get("Amount")
        result["stage"] = deal_data.get("Stage")

        # Date examen
        date_examen = deal_data.get("Date_examen_VTC")
        if isinstance(date_examen, dict):
            result["date_examen"] = date_examen.get("name")
        else:
            result["date_examen"] = date_examen

        # Session
        session = deal_data.get("Session")
        if isinstance(session, dict):
            result["session"] = session.get("name")
        else:
            result["session"] = session

        result["departement"] = deal_data.get("D_partement")
        result["identifiant_evalbox"] = deal_data.get("IDENTIFIANT_EVALBOX")

        # 5. Triage IA
        triage_result = triage_agent.triage_ticket(
            ticket_subject=ticket.get("subject", ""),
            thread_content=customer_message,
            deal_data=deal_data,
            current_department="DOC"
        )
        result["triage_action"] = triage_result.get("action")
        result["triage_intention"] = triage_result.get("detected_intent")  # FIXED: was intent_context.intention
        result["triage_confidence"] = triage_result.get("confidence")
        result["intent_context"] = triage_result.get("intent_context", {})

        # 6. ExamT3P (si identifiants disponibles)
        examt3p_data = None
        if deal_data.get("IDENTIFIANT_EVALBOX") and deal_data.get("MDP_EVALBOX"):
            try:
                examt3p_agent = ExamT3PAgent()
                examt3p_data = examt3p_agent.extract_data(
                    deal_data["IDENTIFIANT_EVALBOX"],
                    deal_data["MDP_EVALBOX"]
                )
                result["examt3p_status"] = examt3p_data.get("statut_dossier")
                result["examt3p_num_dossier"] = examt3p_data.get("num_dossier")
                result["examt3p_compte_existe"] = True
            except Exception as e:
                result["examt3p_error"] = str(e)[:100]
        else:
            result["examt3p_status"] = "NO_CREDENTIALS"

        # 7. Détection d'état
        state = state_detector.detect_state(
            deal_data=deal_data,
            examt3p_data=examt3p_data or {},
            triage_result=triage_result,
            linking_result=deal_result,
            threads_data=threads
        )
        result["detected_state"] = state.name if state else "UNKNOWN"

        # 8. Génération template (State Engine)
        intention = triage_result.get("detected_intent")  # FIXED: was intent_context.intention
        if state:
            try:
                # generate_response prend un DetectedState avec context_data enrichi
                # Le state a déjà son context_data, on l'enrichit avec l'intention
                if intention:
                    state.context_data["detected_intention"] = intention
                    state.context_data["intent_context"] = triage_result.get("intent_context", {})

                template_result = template_engine.generate_response(state=state)
                result["template_used"] = template_result.get("template_used")
                result["response_preview"] = template_result.get("response_text", "")[:500]
                result["blocks_used"] = template_result.get("blocks_used", [])
            except Exception as e:
                result["template_error"] = str(e)[:150]

        # 9. Analyse de cohérence
        coherence_issues = []

        # Vérifier cohérence Evalbox vs ExamT3P
        if examt3p_data and examt3p_data.get("statut_dossier"):
            expected_evalbox = {
                "En cours de composition": "Dossier crée",
                "En attente de paiement": "Pret a payer",
                "En cours d'instruction": "Dossier Synchronisé",
                "Incomplet": "Refusé CMA",
                "Valide": "VALIDE CMA",
                "En attente de convocation": "Convoc CMA reçue"
            }.get(examt3p_data["statut_dossier"])

            if expected_evalbox and deal_data.get("Evalbox") != expected_evalbox:
                coherence_issues.append(f"Evalbox mismatch: CRM={deal_data.get('Evalbox')}, Expected={expected_evalbox}")

        # Vérifier doublon Uber
        if result.get("doublon_uber"):
            coherence_issues.append("DOUBLON UBER 20€")

        # Session manquante si validé
        if result.get("evalbox") in ["VALIDE CMA", "Convoc CMA reçue"] and not result.get("session"):
            coherence_issues.append("Session non choisie (dossier validé)")

        result["coherence_issues"] = coherence_issues
        result["status"] = "OK" if not coherence_issues else f"{len(coherence_issues)} issues"

    except Exception as e:
        result["error"] = str(e)[:200]

    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python analyze_lot.py <start> <end>")
        print("Exemple: python analyze_lot.py 11 20")
        sys.exit(1)

    start = int(sys.argv[1])
    end = int(sys.argv[2])
    lot_num = (start - 1) // 10 + 1

    print("=" * 80)
    print(f"ANALYSE LOT {lot_num} - Tickets {start}-{end}")
    print("=" * 80)

    # Charger les IDs
    ticket_ids = load_ticket_ids(start, end)
    print(f"\nTickets à analyser: {len(ticket_ids)}")

    if not ticket_ids:
        print("Aucun ticket à analyser")
        sys.exit(1)

    # Initialisation
    print("\nInitialisation des composants...")
    desk = ZohoDeskClient()
    crm = ZohoCRMClient()
    deal_agent = DealLinkingAgent()
    triage_agent = TriageAgent()
    state_detector = StateDetector()
    template_engine = TemplateEngine()
    print("OK")

    results = []
    for i, ticket_id in enumerate(ticket_ids):
        print(f"\n[{i+1}/{len(ticket_ids)}] Ticket {ticket_id}...")
        result = analyze_ticket(ticket_id, desk, crm, deal_agent, triage_agent, state_detector, template_engine)
        results.append(result)

        # Afficher résumé
        print(f"  Sujet: {result.get('subject', 'N/A')[:50]}")
        print(f"  État: {result.get('detected_state', 'N/A')} | Triage: {result.get('triage_action', 'N/A')}/{result.get('triage_intention', 'N/A')}")
        print(f"  Evalbox: {result.get('evalbox', 'N/A')} | ExamT3P: {result.get('examt3p_status', 'N/A')}")
        if result.get("coherence_issues"):
            print(f"  [!] {result['coherence_issues']}")
        if result.get("error"):
            print(f"  [X] {result['error']}")

    # Sauvegarder
    output_file = f"data/lot{lot_num}_analysis_{start}_{end}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 80}")
    print(f"Résultats sauvegardés: {output_file}")

    # Résumé
    print(f"\n{'=' * 80}")
    print(f"RÉSUMÉ LOT {lot_num}")
    print("=" * 80)

    states = {}
    intentions = {}
    errors = 0
    issues = 0

    for r in results:
        if r.get("error"):
            errors += 1
        if r.get("coherence_issues"):
            issues += len(r["coherence_issues"])

        state = r.get("detected_state", "UNKNOWN")
        states[state] = states.get(state, 0) + 1

        intention = r.get("triage_intention", "N/A")
        intentions[intention] = intentions.get(intention, 0) + 1

    print(f"\nÉtats: {dict(sorted(states.items(), key=lambda x: -x[1]))}")
    print(f"Intentions: {dict(sorted(intentions.items(), key=lambda x: -x[1]))}")
    print(f"Erreurs: {errors} | Issues cohérence: {issues}")


if __name__ == "__main__":
    main()
