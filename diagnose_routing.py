#!/usr/bin/env python3
"""
Diagnostic: Pourquoi ces tickets ont été routés vers Contact ?

Récupère chaque ticket par numéro, rejoue le triage en dry-run,
et affiche la règle exacte qui a déclenché le routage.
"""
import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

from src.zoho_client import ZohoDeskClient
from src.workflows.doc_ticket_workflow import DOCTicketWorkflow

# Configurer logging pour capturer les détails du triage
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

# Tickets du screenshot (numéros)
TICKET_NUMBERS = [
    "1105458", "1105500", "1105437", "1105424", "1105938",
    "1106939", "1106967", "1103673", "1105216",
    "1107699",
    "1099056", "1107836", "1107841", "1096558", "1094840",
    "1092620", "1093739", "1104949", "1104546", "1104658",
    "1104135", "1102340", "1098618", "1097827", "1104453",
]

def find_ticket_ids(desk_client, ticket_numbers):
    """Cherche les IDs internes à partir des numéros de tickets."""
    print("=" * 70)
    print("ÉTAPE 1: Recherche des ticket IDs par numéro")
    print("=" * 70)

    # Récupérer tous les tickets ouverts du département DOC + Contact
    # (les tickets ont pu être transférés à Contact)
    print("Récupération des tickets ouverts...")
    all_tickets = desk_client.list_all_tickets(status="Open")
    print(f"  Total tickets ouverts: {len(all_tickets)}")

    # Créer un mapping ticketNumber -> ticket
    number_to_ticket = {}
    for t in all_tickets:
        tn = str(t.get("ticketNumber", ""))
        number_to_ticket[tn] = t

    # Chercher nos tickets
    found = {}
    not_found = []
    for num in ticket_numbers:
        num_clean = num.lstrip("#")
        if num_clean in number_to_ticket:
            t = number_to_ticket[num_clean]
            found[num_clean] = t
            dept = t.get("department", {}).get("name", "?") if isinstance(t.get("department"), dict) else t.get("departmentId", "?")
            print(f"  #{num_clean} → ID: {t['id']} | Dept: {dept} | {(t.get('subject') or '')[:50]}")
        else:
            not_found.append(num_clean)

    if not_found:
        print(f"\n  ⚠️ Non trouvés dans tickets ouverts: {not_found}")
        print("  Tentative dans tickets fermés/tous...")
        # Essayer sans filtre status
        all_tickets_any = desk_client.list_all_tickets()
        for t in all_tickets_any:
            tn = str(t.get("ticketNumber", ""))
            if tn in not_found:
                found[tn] = t
                dept = t.get("department", {}).get("name", "?") if isinstance(t.get("department"), dict) else t.get("departmentId", "?")
                print(f"  #{tn} → ID: {t['id']} | Dept: {dept} | {(t.get('subject') or '')[:50]}")
                not_found.remove(tn)

    if not_found:
        print(f"\n  ❌ Pas trouvés du tout: {not_found}")

    return found


def diagnose_ticket(workflow, ticket_id, ticket_number):
    """Exécute le triage en dry-run et retourne le diagnostic."""
    print(f"\n{'─' * 60}")
    print(f"TICKET #{ticket_number} (ID: {ticket_id})")
    print(f"{'─' * 60}")

    try:
        # Exécuter le triage SANS transfert automatique (dry-run)
        triage_result = workflow._run_triage(ticket_id, auto_transfer=False)

        action = triage_result.get('action', '?')
        target = triage_result.get('target_department', '?')
        method = triage_result.get('method', '?')
        reason = triage_result.get('reason', '?')
        intent = triage_result.get('detected_intent', 'N/A')
        confidence = triage_result.get('confidence', 'N/A')

        print(f"  ACTION: {action}")
        print(f"  TARGET: {target}")
        print(f"  METHOD: {method}")
        print(f"  REASON: {reason}")
        print(f"  INTENT: {intent}")
        if confidence != 'N/A':
            print(f"  CONFIDENCE: {confidence}")

        return {
            'ticket_number': ticket_number,
            'ticket_id': ticket_id,
            'action': action,
            'target_department': target,
            'method': method,
            'reason': reason,
            'detected_intent': intent,
        }

    except Exception as e:
        print(f"  ❌ ERREUR: {e}")
        return {
            'ticket_number': ticket_number,
            'ticket_id': ticket_id,
            'error': str(e),
        }


def main():
    desk_client = ZohoDeskClient()
    workflow = DOCTicketWorkflow()

    # Étape 1: Trouver les IDs
    found_tickets = find_ticket_ids(desk_client, TICKET_NUMBERS)

    if not found_tickets:
        print("\n❌ Aucun ticket trouvé.")
        return

    print(f"\n{'=' * 70}")
    print(f"ÉTAPE 2: Diagnostic du triage pour {len(found_tickets)} tickets")
    print(f"{'=' * 70}")

    results = []
    for ticket_num, ticket_data in found_tickets.items():
        ticket_id = ticket_data['id']
        result = diagnose_ticket(workflow, ticket_id, ticket_num)
        results.append(result)

    # Résumé
    print(f"\n{'=' * 70}")
    print("RÉSUMÉ")
    print(f"{'=' * 70}")

    # Grouper par method
    by_method = {}
    for r in results:
        method = r.get('method', 'error')
        if method not in by_method:
            by_method[method] = []
        by_method[method].append(r)

    for method, tickets in sorted(by_method.items()):
        print(f"\n{method} ({len(tickets)} tickets):")
        for t in tickets:
            print(f"  #{t['ticket_number']} → {t.get('action', '?')} → {t.get('target_department', '?')}")
            if t.get('reason'):
                print(f"    Raison: {t['reason'][:100]}")

    # Sauvegarder
    output_file = "data/routing_diagnostic.json"
    os.makedirs("data", exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nRésultats sauvegardés dans {output_file}")


if __name__ == "__main__":
    main()
