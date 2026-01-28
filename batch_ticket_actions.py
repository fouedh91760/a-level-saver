#!/usr/bin/env python3
"""
Actions en masse sur les tickets analysés.

Supporte différentes actions:
- SPAM_TO_CLOSE: Clôturer les tickets SPAM
- PROSPECT_TO_ROUTE: Router les prospects vers Contact
- ROUTE_TO_DEPT: Router vers un département spécifique
- Custom actions via filtres

Usage:
    python batch_ticket_actions.py <analysis_file.json> --action <ACTION> [--dry-run]

Exemples:
    # Clôturer les tickets SPAM
    python batch_ticket_actions.py data/lot2_analysis_11_20.json --action close-spam --dry-run

    # Router les prospects vers Contact
    python batch_ticket_actions.py data/lot2_analysis_11_20.json --action route-prospects --dry-run

    # Clôturer tous les tickets avec un statut spécifique
    python batch_ticket_actions.py data/lot2_analysis_11_20.json --action close --filter "status=SPAM_TO_CLOSE" --dry-run
"""

import json
import sys
import os
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.zoho_client import ZohoDeskClient


class BatchTicketActions:
    """Gestionnaire d'actions en masse sur les tickets."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.desk = ZohoDeskClient()
        self.results = {"success": [], "errors": []}

    def load_analysis(self, analysis_file: str) -> List[Dict]:
        """Charge le fichier d'analyse JSON."""
        with open(analysis_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def filter_tickets(self, tickets: List[Dict], filter_expr: Optional[str] = None) -> List[Dict]:
        """
        Filtre les tickets selon une expression.

        Format: "field=value" ou "field!=value"
        """
        if not filter_expr:
            return tickets

        if "!=" in filter_expr:
            field, value = filter_expr.split("!=", 1)
            return [t for t in tickets if str(t.get(field.strip())) != value.strip()]
        elif "=" in filter_expr:
            field, value = filter_expr.split("=", 1)
            return [t for t in tickets if str(t.get(field.strip())) == value.strip()]

        return tickets

    def close_ticket(self, ticket_id: str, reason: str = "Clôture automatique") -> bool:
        """Clôture un ticket."""
        if self.dry_run:
            print(f"    [DRY RUN] Serait cloture")
            return True

        try:
            self.desk.update_ticket(ticket_id, {
                "status": "Closed",
                "statusType": "Closed"
            })

            # Ajouter un commentaire interne
            try:
                self.desk.add_comment(
                    ticket_id,
                    content=f"[AUTO] {reason}",
                    is_public=False
                )
            except:
                pass

            print(f"    Cloture OK")
            return True

        except Exception as e:
            print(f"    ERREUR: {e}")
            return False

    def route_ticket(self, ticket_id: str, department: str, reason: str = "Routage automatique") -> bool:
        """Route un ticket vers un département."""
        if self.dry_run:
            print(f"    [DRY RUN] Serait route vers {department}")
            return True

        try:
            self.desk.move_ticket_to_department(ticket_id, department)

            # Ajouter un commentaire interne
            try:
                self.desk.add_comment(
                    ticket_id,
                    content=f"[AUTO] {reason} - Route vers {department}",
                    is_public=False
                )
            except:
                pass

            print(f"    Route vers {department} OK")
            return True

        except Exception as e:
            print(f"    ERREUR: {e}")
            return False

    def action_close_spam(self, tickets: List[Dict]) -> Dict:
        """Clôture les tickets SPAM."""
        spam_tickets = [t for t in tickets if t.get("status") == "SPAM_TO_CLOSE"]

        print(f"\nTickets SPAM a cloturer: {len(spam_tickets)}")

        for t in spam_tickets:
            ticket_id = t.get("ticket_id")
            ticket_num = t.get("ticket_number", "?")
            subject = t.get("subject", "")[:50]
            reason = t.get("spam_reason", "SPAM detecte automatiquement")

            print(f"\n  [{ticket_num}] {subject}")
            print(f"    Raison: {reason}")

            if self.close_ticket(ticket_id, f"SPAM: {reason}"):
                self.results["success"].append(ticket_id)
            else:
                self.results["errors"].append(ticket_id)

        return self.results

    def action_route_prospects(self, tickets: List[Dict], target_dept: str = "Contact") -> Dict:
        """Route les prospects vers un département."""
        prospect_tickets = [t for t in tickets if t.get("status") == "PROSPECT_TO_ROUTE"]

        print(f"\nProspects a router vers {target_dept}: {len(prospect_tickets)}")

        for t in prospect_tickets:
            ticket_id = t.get("ticket_id")
            ticket_num = t.get("ticket_number", "?")
            subject = t.get("subject", "")[:50]

            print(f"\n  [{ticket_num}] {subject}")

            if self.route_ticket(ticket_id, target_dept, "Prospect sans dossier"):
                self.results["success"].append(ticket_id)
            else:
                self.results["errors"].append(ticket_id)

        return self.results

    def action_close_filtered(self, tickets: List[Dict], filter_expr: str, reason: str = "Cloture par filtre") -> Dict:
        """Clôture des tickets selon un filtre."""
        filtered = self.filter_tickets(tickets, filter_expr)

        print(f"\nTickets correspondant au filtre '{filter_expr}': {len(filtered)}")

        for t in filtered:
            ticket_id = t.get("ticket_id")
            ticket_num = t.get("ticket_number", "?")
            subject = t.get("subject", "")[:50]

            print(f"\n  [{ticket_num}] {subject}")

            if self.close_ticket(ticket_id, reason):
                self.results["success"].append(ticket_id)
            else:
                self.results["errors"].append(ticket_id)

        return self.results


def main():
    parser = argparse.ArgumentParser(description="Actions en masse sur les tickets analysés")
    parser.add_argument("analysis_file", help="Fichier JSON d'analyse")
    parser.add_argument("--action", required=True, choices=["close-spam", "route-prospects", "close", "route"],
                        help="Action à effectuer")
    parser.add_argument("--filter", help="Filtre (ex: 'status=SPAM_TO_CLOSE')")
    parser.add_argument("--target-dept", default="Contact", help="Département cible pour le routage")
    parser.add_argument("--reason", default="Action automatique", help="Raison de l'action")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Mode preview (pas de modification)")
    args = parser.parse_args()

    if not os.path.exists(args.analysis_file):
        print(f"Erreur: Fichier non trouve: {args.analysis_file}")
        sys.exit(1)

    print("=" * 80)
    print(f"BATCH TICKET ACTIONS - {'DRY RUN' if args.dry_run else 'PRODUCTION'}")
    print(f"Action: {args.action}")
    print("=" * 80)

    batch = BatchTicketActions(dry_run=args.dry_run)
    tickets = batch.load_analysis(args.analysis_file)

    print(f"Tickets dans le fichier: {len(tickets)}")

    if args.action == "close-spam":
        results = batch.action_close_spam(tickets)
    elif args.action == "route-prospects":
        results = batch.action_route_prospects(tickets, args.target_dept)
    elif args.action == "close":
        if not args.filter:
            print("Erreur: --filter requis pour l'action 'close'")
            sys.exit(1)
        results = batch.action_close_filtered(tickets, args.filter, args.reason)
    elif args.action == "route":
        print("Action 'route' non implementee - utilisez route-prospects ou ajoutez la logique")
        sys.exit(1)

    # Résumé
    print(f"\n{'=' * 80}")
    print("RESUME")
    print("=" * 80)
    print(f"Succes: {len(results['success'])}")
    print(f"Erreurs: {len(results['errors'])}")

    if args.dry_run:
        print("\n[DRY RUN] Aucune modification effectuee.")
        print("Pour executer, relancez sans --dry-run")

    # Sauvegarder le rapport
    report = {
        "timestamp": datetime.now().isoformat(),
        "source_file": args.analysis_file,
        "action": args.action,
        "filter": args.filter,
        "dry_run": args.dry_run,
        "success": results["success"],
        "errors": results["errors"]
    }

    report_file = f"data/batch_action_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nRapport sauvegarde: {report_file}")


if __name__ == "__main__":
    main()
