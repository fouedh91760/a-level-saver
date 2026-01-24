"""
Debug script to understand why deals are not being found.

Tests different search strategies on a single ticket.
"""
import json
import logging
from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.ticket_deal_linker import TicketDealLinker

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def debug_ticket_deal_search():
    """Debug deal search for the first ticket."""

    # Load first ticket
    with open('fouad_tickets_analysis.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    tickets = data['tickets']
    ticket_data = tickets[0]  # First ticket

    ticket_id = ticket_data['ticket_id']
    email = ticket_data.get('contact_email', '')

    print("\n" + "=" * 80)
    print("DEBUG: DEAL SEARCH FOR FIRST TICKET")
    print("=" * 80)
    print(f"\nTicket ID: {ticket_id}")
    print(f"Contact Email: {email}")
    print(f"Subject: {ticket_data.get('subject', 'N/A')}")

    # Initialize clients
    desk_client = ZohoDeskClient()
    crm_client = ZohoCRMClient()
    deal_linker = TicketDealLinker()

    try:
        # Get full ticket from Desk API
        print("\n" + "-" * 80)
        print("STEP 1: Fetching full ticket from Zoho Desk")
        print("-" * 80)

        ticket = desk_client.get_ticket(ticket_id)

        print(f"\nTicket structure keys: {list(ticket.keys())}")
        print(f"\nContact info:")
        contact = ticket.get('contact', {})
        print(f"  - contact keys: {list(contact.keys())}")
        print(f"  - email: {contact.get('email')}")
        print(f"  - firstName: {contact.get('firstName')}")
        print(f"  - lastName: {contact.get('lastName')}")

        # Try to search deals manually
        print("\n" + "-" * 80)
        print("STEP 2: Manual deal search attempts")
        print("-" * 80)

        if email:
            # Try search 1: By Email field
            print(f"\n🔍 Search 1: (Email:equals:{email})")
            try:
                result = crm_client.search_deals(f"(Email:equals:{email})", per_page=5)
                deals = result.get('data', [])
                print(f"   Result: {len(deals)} deals found")
                if deals:
                    for i, deal in enumerate(deals, 1):
                        print(f"   {i}. {deal.get('Deal_Name')} - Amount: {deal.get('Amount')}€ - Stage: {deal.get('Stage')}")
            except Exception as e:
                print(f"   Error: {e}")

            # Try search 2: By Contact Name
            print(f"\n🔍 Search 2: Search deals for Contact (by name)")
            try:
                contact_first = contact.get('firstName', '')
                contact_last = contact.get('lastName', '')
                if contact_first and contact_last:
                    contact_name = f"{contact_first} {contact_last}"
                    result = crm_client.search_deals(f"(Contact_Name:equals:{contact_name})", per_page=5)
                    deals = result.get('data', [])
                    print(f"   Result: {len(deals)} deals found for '{contact_name}'")
                    if deals:
                        for i, deal in enumerate(deals, 1):
                            print(f"   {i}. {deal.get('Deal_Name')} - Amount: {deal.get('Amount')}€ - Stage: {deal.get('Stage')}")
            except Exception as e:
                print(f"   Error: {e}")

            # Try search 3: All deals (to check structure)
            print(f"\n🔍 Search 3: List all recent deals (first 3)")
            try:
                # Get recent deals
                result = crm_client.search_deals("(Stage:equals:Closed Won)", per_page=3)
                deals = result.get('data', [])
                print(f"   Result: {len(deals)} deals found")
                if deals:
                    print("\n   Sample deal structure:")
                    sample_deal = deals[0]
                    print(f"   Deal fields: {list(sample_deal.keys())}")
                    print(f"\n   Sample deal details:")
                    print(f"   - Deal_Name: {sample_deal.get('Deal_Name')}")
                    print(f"   - Amount: {sample_deal.get('Amount')}")
                    print(f"   - Stage: {sample_deal.get('Stage')}")
                    print(f"   - Contact_Name: {sample_deal.get('Contact_Name')}")
                    print(f"   - Email: {sample_deal.get('Email')}")
                    print(f"   - Type_formation: {sample_deal.get('Type_formation')}")
            except Exception as e:
                print(f"   Error: {e}")

        # Try using TicketDealLinker
        print("\n" + "-" * 80)
        print("STEP 3: Using TicketDealLinker")
        print("-" * 80)

        deal = deal_linker.find_deal_for_ticket(ticket_id)

        if deal:
            print(f"\n✅ Deal found!")
            print(f"   Deal Name: {deal.get('Deal_Name')}")
            print(f"   Amount: {deal.get('Amount')}€")
            print(f"   Stage: {deal.get('Stage')}")
        else:
            print(f"\n❌ No deal found")

    except Exception as e:
        logger.error(f"Error in debug: {e}")
        import traceback
        traceback.print_exc()

    finally:
        desk_client.close()
        crm_client.close()

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    debug_ticket_deal_search()
