#!/usr/bin/env python3
"""
Clôture automatique des tickets identifiés comme SPAM.

Usage:
    python close_spam_tickets.py <analysis_file.json> [--dry-run]

Exemples:
    python close_spam_tickets.py data/lot2_analysis_11_20.json --dry-run
    python close_spam_tickets.py data/lot2_analysis_11_20.json  # Clôture réelle
"""

import json
import sys
import os
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.zoho_client import ZohoDeskClient


def close_spam_tickets(analysis_file: str, dry_run: bool = True):
    """
    Clôture les tickets marqués comme SPAM_TO_CLOSE.

    Args:
        analysis_file: Fichier JSON d'analyse contenant les résultats
        dry_run: Si True, affiche seulement sans clôturer
    """
    print("=" * 80)
    print(f"CLÔTURE SPAM - {'DRY RUN' if dry_run else 'PRODUCTION'}")
    print("=" * 80)

    # Charger les résultats d'analyse
    with open(analysis_file, "r", encoding="utf-8") as f:
        results = json.load(f)

    # Filtrer les tickets SPAM
    spam_tickets = [r for r in results if r.get("status") == "SPAM_TO_CLOSE"]

    print(f"\nTickets SPAM trouvés: {len(spam_tickets)}")

    if not spam_tickets:
        print("Aucun ticket SPAM à clôturer.")
        return

    desk = ZohoDeskClient()
    closed = []
    errors = []

    for ticket in spam_tickets:
        ticket_id = ticket.get("ticket_id")
        ticket_number = ticket.get("ticket_number")
        subject = ticket.get("subject", "")[:50]
        spam_reason = ticket.get("spam_reason", "SPAM détecté automatiquement")

        print(f"\n[{ticket_number}] {subject}")
        print(f"  Raison: {spam_reason}")

        if dry_run:
            print(f"  -> [DRY RUN] Serait clôturé")
            closed.append(ticket_id)
        else:
            try:
                # Clôturer le ticket avec un commentaire interne
                desk.update_ticket(ticket_id, {
                    "status": "Closed",
                    "statusType": "Closed"
                })

                # Ajouter un commentaire interne expliquant la clôture
                try:
                    desk.add_comment(
                        ticket_id,
                        content=f"[AUTO] Ticket clôturé automatiquement - SPAM détecté.\nRaison: {spam_reason}",
                        is_public=False
                    )
                except Exception as e:
                    print(f"  [!] Commentaire non ajouté: {e}")

                print(f"  -> Clôturé avec succès")
                closed.append(ticket_id)

            except Exception as e:
                print(f"  -> ERREUR: {e}")
                errors.append({"ticket_id": ticket_id, "error": str(e)})

    # Résumé
    print(f"\n{'=' * 80}")
    print("RÉSUMÉ")
    print("=" * 80)
    print(f"Tickets traités: {len(spam_tickets)}")
    print(f"Clôturés: {len(closed)}")
    print(f"Erreurs: {len(errors)}")

    if dry_run:
        print("\n[DRY RUN] Aucun ticket n'a été réellement clôturé.")
        print("Pour clôturer, relancez sans --dry-run")

    # Sauvegarder le rapport
    report = {
        "timestamp": datetime.now().isoformat(),
        "source_file": analysis_file,
        "dry_run": dry_run,
        "spam_count": len(spam_tickets),
        "closed": closed,
        "errors": errors
    }

    report_file = f"data/spam_closure_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\nRapport sauvegardé: {report_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python close_spam_tickets.py <analysis_file.json> [--dry-run]")
        print("Exemple: python close_spam_tickets.py data/lot2_analysis_11_20.json --dry-run")
        sys.exit(1)

    analysis_file = sys.argv[1]
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv

    if not os.path.exists(analysis_file):
        print(f"Erreur: Fichier non trouvé: {analysis_file}")
        sys.exit(1)

    close_spam_tickets(analysis_file, dry_run)


if __name__ == "__main__":
    main()
