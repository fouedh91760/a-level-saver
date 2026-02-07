#!/usr/bin/env python3
"""
Enrichit les tickets ROUTE dans doc_tickets_processed.json avec le contenu client
récupéré depuis Zoho Desk (sujet + message client).

Usage:
    python enrich_route_tickets.py              # Enrichir tous les ROUTE
    python enrich_route_tickets.py --limit 10   # Enrichir 10 tickets max
    python enrich_route_tickets.py --dry-run    # Voir sans modifier
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.zoho_client import ZohoDeskClient
from src.utils.text_utils import get_clean_thread_content

PROCESSED_FILE = "doc_tickets_processed.json"


def enrich_route_tickets(limit=None, dry_run=False):
    # Charger les tickets
    with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
        all_tickets = json.load(f)

    # Filtrer les ROUTE sans message
    to_enrich = [
        (i, t) for i, t in enumerate(all_tickets)
        if t.get('triage_action') == 'ROUTE' and not t.get('customer_message')
    ]

    if limit:
        to_enrich = to_enrich[:limit]

    print(f"Tickets ROUTE a enrichir: {len(to_enrich)}")
    if dry_run:
        print("MODE DRY-RUN - aucune modification")
        for _, t in to_enrich[:10]:
            print(f"  {t['id']} | {t.get('ticketNumber', 'N/A')} | {(t.get('subject') or '')[:50]}")
        if len(to_enrich) > 10:
            print(f"  ... et {len(to_enrich) - 10} autres")
        return

    client = ZohoDeskClient()
    enriched_count = 0
    error_count = 0

    for idx, (pos, ticket) in enumerate(to_enrich, 1):
        ticket_id = ticket['id']
        ticket_num = ticket.get('ticketNumber', 'N/A')

        try:
            # Recuperer les threads
            threads = client.get_all_threads_with_full_content(ticket_id)

            # Extraire le message client (premier message entrant)
            customer_message = ""
            for thread in threads:
                if thread.get('direction') == 'in':
                    content = get_clean_thread_content(thread)
                    if content and len(content) > 20:
                        customer_message = content
                        break

            # Fallback: prendre le premier thread quel qu'il soit
            if not customer_message and threads:
                customer_message = get_clean_thread_content(threads[0])

            # Recuperer le sujet depuis le ticket si pas deja present
            ticket_subject = ticket.get('subject', '')
            if not ticket_subject:
                ticket_data = client.get_ticket(ticket_id)
                ticket_subject = ticket_data.get('subject', '')

            # Mettre a jour
            all_tickets[pos]['customer_message'] = customer_message[:3000] if customer_message else ''
            all_tickets[pos]['ticket_subject'] = ticket_subject

            enriched_count += 1
            msg_preview = (customer_message or '')[:80].replace('\n', ' ')
            print(f"[{idx}/{len(to_enrich)}] #{ticket_num} OK | {msg_preview}")

        except Exception as e:
            error_count += 1
            print(f"[{idx}/{len(to_enrich)}] #{ticket_num} ERREUR: {str(e)[:80]}")

        # Rate limit
        time.sleep(0.5)

        # Sauvegarder tous les 50 tickets (pour ne pas perdre la progression)
        if idx % 50 == 0:
            with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_tickets, f, ensure_ascii=False, indent=2)
            print(f"  [Sauvegarde intermediaire: {enriched_count} enrichis]")

    # Sauvegarde finale
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_tickets, f, ensure_ascii=False, indent=2)

    print(f"\nTermine: {enriched_count} enrichis, {error_count} erreurs")


def main():
    parser = argparse.ArgumentParser(description='Enrichir les tickets ROUTE avec le contenu client')
    parser.add_argument('--limit', '-n', type=int, help='Nombre max de tickets a enrichir')
    parser.add_argument('--dry-run', '-d', action='store_true', help='Mode test sans modification')
    args = parser.parse_args()

    enrich_route_tickets(limit=args.limit, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
