"""
Script pour lister les tickets récents afin d'obtenir un ID de ticket valide pour les tests.
"""
import sys
from pathlib import Path

# Ajouter le projet au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.zoho_client import ZohoClient
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.WARNING)

def list_recent_tickets(status="Open", limit=20):
    """Liste les tickets récents."""
    print("\n" + "=" * 80)
    print(f"📋 TICKETS RÉCENTS (Status: {status}, Limit: {limit})")
    print("=" * 80)

    client = ZohoClient()

    try:
        # Récupérer les tickets
        tickets = client.list_tickets(status=status, limit=limit)

        if not tickets:
            print(f"\n⚠️  Aucun ticket trouvé avec le statut '{status}'")
            return

        print(f"\n✅ {len(tickets)} ticket(s) trouvé(s):\n")

        for idx, ticket in enumerate(tickets, 1):
            ticket_id = ticket.get('id')
            subject = ticket.get('subject', 'N/A')
            contact_name = ticket.get('contactId', {}).get('firstName', 'N/A') if isinstance(ticket.get('contactId'), dict) else 'N/A'
            department = ticket.get('departmentId', 'N/A')
            created_time = ticket.get('createdTime', 'N/A')

            print(f"{idx}. ID: {ticket_id}")
            print(f"   Sujet: {subject[:60]}...")
            print(f"   Contact: {contact_name}")
            print(f"   Département: {department}")
            print(f"   Créé: {created_time}")
            print()

        # Afficher la commande de test
        first_ticket_id = tickets[0].get('id')
        print("\n" + "=" * 80)
        print("🧪 COMMANDE DE TEST")
        print("=" * 80)
        print(f"\nPour tester avec le premier ticket :")
        print(f"\npython test_new_workflow.py {first_ticket_id} --full-workflow")
        print("\n" + "=" * 80)

    except Exception as e:
        print(f"\n❌ Erreur lors de la récupération des tickets: {e}")
        import traceback
        traceback.print_exc()

    finally:
        client.close()


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Liste les tickets récents')
    parser.add_argument('--status', default='Open', help='Statut des tickets (default: Open)')
    parser.add_argument('--limit', type=int, default=20, help='Nombre de tickets à afficher (default: 20)')

    args = parser.parse_args()

    list_recent_tickets(status=args.status, limit=args.limit)


if __name__ == "__main__":
    main()
