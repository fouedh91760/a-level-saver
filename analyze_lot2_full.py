#!/usr/bin/env python3
"""
Analyse complète du Lot 2 (tickets 11-20) avec:
- Historique complet des threads
- Données CRM
- Données ExamT3P
- Génération de réponse draft
- Analyse de cohérence
"""

import json
import sys
import os
from datetime import datetime

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.agents.deal_linking_agent import DealLinkingAgent
from src.agents.triage_agent import TriageAgent
from src.agents.examt3p_agent import ExamT3PAgent
from src.utils.examt3p_credentials_helper import get_credentials_with_validation
from src.state_engine.state_detector import StateDetector
from src.state_engine.template_engine import TemplateEngine
from src.utils.session_helper import analyze_session_situation
from src.utils.date_examen_vtc_helper import analyze_exam_date_situation


def analyze_ticket(ticket, desk, crm, deal_agent, triage_agent, state_detector, template_engine):
    """Analyse complète d'un ticket."""
    result = {
        "ticket_id": ticket.get("id"),
        "ticket_number": ticket.get("ticketNumber"),
        "subject": ticket.get("subject", "")[:80],
        "created_time": ticket.get("createdTime"),
        "status": ticket.get("status"),
    }

    try:
        # 1. Récupérer les threads complets
        threads = desk.get_all_threads_with_full_content(ticket["id"])
        result["threads_count"] = len(threads)

        # Extraire le message client (dernier thread incoming)
        customer_message = ""
        for thread in threads:
            if thread.get("direction") == "in":
                customer_message = thread.get("content", "")[:500]
                break
        result["customer_message_preview"] = customer_message[:200]

        # 2. Lier au deal CRM
        deal_result = deal_agent.process({"ticket_id": ticket["id"]})
        deal_id = deal_result.get("deal_id")
        result["deal_id"] = deal_id

        if not deal_id:
            result["error"] = "NO_DEAL_FOUND"
            return result

        # 3. Récupérer les données CRM directement
        deal_data = crm.get_deal(deal_id)
        if not deal_data:
            result["error"] = "DEAL_NOT_FETCHED"
            return result

        result["deal_name"] = deal_data.get("Deal_Name", "")
        result["evalbox"] = deal_data.get("Evalbox")
        result["amount"] = deal_data.get("Amount")
        result["stage"] = deal_data.get("Stage")
        result["date_examen"] = deal_data.get("Date_examen_VTC", {}).get("name") if isinstance(deal_data.get("Date_examen_VTC"), dict) else None
        result["session"] = deal_data.get("Session", {}).get("name") if isinstance(deal_data.get("Session"), dict) else None
        result["departement"] = deal_data.get("D_partement")
        result["identifiant_evalbox"] = deal_data.get("IDENTIFIANT_EVALBOX")
        result["doublon_uber"] = deal_result.get("has_duplicate_uber_offer", False)

        # 4. Triage IA
        triage_result = triage_agent.triage_ticket(
            ticket_subject=ticket.get("subject", ""),
            thread_content=customer_message,
            deal_data=deal_data,
            current_department="DOC"
        )
        result["triage_action"] = triage_result.get("action")
        result["triage_intention"] = triage_result.get("intent_context", {}).get("intention")
        result["triage_confidence"] = triage_result.get("confidence")

        # 5. ExamT3P (si identifiants disponibles)
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
                result["examt3p_compte_existe"] = examt3p_data.get("compte_existe", False)
            except Exception as e:
                result["examt3p_error"] = str(e)[:100]
        else:
            result["examt3p_status"] = "NO_CREDENTIALS"

        # 6. Détection d'état
        state = state_detector.detect(deal_data, examt3p_data or {})
        result["detected_state"] = state.name if state else "UNKNOWN"

        # 7. Analyse session
        try:
            session_result = analyze_session_situation(
                deal_data=deal_data,
                exam_dates=[],
                threads=threads,
                crm_client=crm
            )
            result["session_preference"] = session_result.get("session_preference")
            result["session_options_count"] = len(session_result.get("proposed_options", []))
        except Exception as e:
            result["session_error"] = str(e)[:100]

        # 8. Analyse date examen
        try:
            date_result = analyze_exam_date_situation(
                deal_data=deal_data,
                threads=threads,
                crm_client=crm,
                examt3p_data=examt3p_data
            )
            result["date_case"] = date_result.get("case")
            result["can_modify_date"] = date_result.get("can_modify_exam_date", True)
            result["next_dates_count"] = len(date_result.get("next_dates", []))
        except Exception as e:
            result["date_error"] = str(e)[:100]

        # 9. Génération template (State Engine)
        intention = triage_result.get("intent_context", {}).get("intention")
        if state and intention:
            try:
                template_result = template_engine.render(
                    state=state,
                    intention=intention,
                    deal_data=deal_data,
                    examt3p_data=examt3p_data or {},
                    session_data=session_result if 'session_result' in dir() else {},
                    date_data=date_result if 'date_result' in dir() else {}
                )
                result["template_used"] = template_result.get("template_key")
                result["response_preview"] = template_result.get("content", "")[:300]
            except Exception as e:
                result["template_error"] = str(e)[:100]

        # 10. Analyse de cohérence
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
            coherence_issues.append("DOUBLON UBER 20€ détecté")

        # Vérifier si date modifiable
        if not result.get("can_modify_date") and intention in ["REPORT_DATE", "DEMANDE_MODIF_DATE"]:
            coherence_issues.append("Intention=REPORT_DATE mais date non modifiable (VALIDE CMA + clôture passée)")

        # Vérifier session manquante
        if result.get("evalbox") in ["VALIDE CMA", "Convoc CMA reçue"] and not result.get("session"):
            coherence_issues.append("Session non choisie alors que dossier validé")

        result["coherence_issues"] = coherence_issues
        result["coherence_score"] = "OK" if not coherence_issues else f"{len(coherence_issues)} issues"

    except Exception as e:
        result["error"] = str(e)[:200]

    return result


def main():
    print("=" * 80)
    print("ANALYSE LOT 2 - Tickets DOC 11-20")
    print("=" * 80)

    # Initialisation
    desk = ZohoDeskClient()
    crm = ZohoCRMClient()
    deal_agent = DealLinkingAgent()
    triage_agent = TriageAgent()
    state_detector = StateDetector()
    template_engine = TemplateEngine()

    # Récupérer les tickets DOC ouverts
    print("\nRécupération des tickets DOC ouverts...")
    doc_dept_id = "198709000025523146"

    # list_all_tickets gère la pagination automatiquement
    all_tickets = desk.list_all_tickets(status="Open")
    doc_tickets = [t for t in all_tickets if t.get("departmentId") == doc_dept_id]

    print(f"Tickets DOC ouverts trouvés: {len(doc_tickets)}")

    # Prendre les tickets 11-20 (index 10-19)
    lot2_tickets = doc_tickets[10:20] if len(doc_tickets) >= 20 else doc_tickets[10:] if len(doc_tickets) > 10 else []

    if not lot2_tickets:
        print("Pas assez de tickets pour le lot 2, utilisation des tickets disponibles")
        # Fallback: prendre les 10 derniers tickets disponibles
        lot2_tickets = doc_tickets[-10:] if len(doc_tickets) >= 10 else doc_tickets

    print(f"Tickets à analyser: {len(lot2_tickets)}")

    results = []
    for i, ticket in enumerate(lot2_tickets):
        print(f"\n[{i+1}/{len(lot2_tickets)}] Analyse ticket {ticket.get('ticketNumber')} - {ticket.get('subject', '')[:50]}...")
        result = analyze_ticket(ticket, desk, crm, deal_agent, triage_agent, state_detector, template_engine)
        results.append(result)

        # Afficher résumé
        print(f"  État: {result.get('detected_state', 'N/A')}")
        print(f"  Triage: {result.get('triage_action', 'N/A')} / {result.get('triage_intention', 'N/A')}")
        print(f"  Evalbox: {result.get('evalbox', 'N/A')}")
        if result.get("coherence_issues"):
            print(f"  ⚠️  Issues: {result['coherence_issues']}")

    # Sauvegarder les résultats
    output_file = "lot2_analysis_full.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 80}")
    print(f"Résultats sauvegardés dans {output_file}")

    # Résumé
    print(f"\n{'=' * 80}")
    print("RÉSUMÉ LOT 2")
    print("=" * 80)

    states = {}
    intentions = {}
    issues_count = 0

    for r in results:
        state = r.get("detected_state", "UNKNOWN")
        states[state] = states.get(state, 0) + 1

        intention = r.get("triage_intention", "UNKNOWN")
        intentions[intention] = intentions.get(intention, 0) + 1

        if r.get("coherence_issues"):
            issues_count += len(r["coherence_issues"])

    print(f"\nÉtats détectés:")
    for state, count in sorted(states.items(), key=lambda x: -x[1]):
        print(f"  {state}: {count}")

    print(f"\nIntentions détectées:")
    for intention, count in sorted(intentions.items(), key=lambda x: -x[1]):
        print(f"  {intention}: {count}")

    print(f"\nProblèmes de cohérence: {issues_count}")

    # Détail des issues
    if issues_count > 0:
        print("\nDétail des incohérences:")
        for r in results:
            if r.get("coherence_issues"):
                print(f"\n  Ticket {r.get('ticket_number')}:")
                for issue in r["coherence_issues"]:
                    print(f"    - {issue}")


if __name__ == "__main__":
    main()
