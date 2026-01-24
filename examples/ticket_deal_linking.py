"""
Example: Linking tickets to deals with multiple strategies.

This example demonstrates the various ways to link Zoho Desk tickets
to Zoho CRM deals/opportunities.
"""
import logging
from src.ticket_deal_linker import TicketDealLinker
from src.orchestrator import ZohoAutomationOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_1_find_deal_for_ticket():
    """Example 1: Find a deal for a ticket using all strategies."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: FIND DEAL FOR TICKET (ALL STRATEGIES)")
    print("=" * 80)

    linker = TicketDealLinker()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID

        # Find deal using all available strategies
        deal = linker.find_deal_for_ticket(ticket_id)

        if deal:
            print(f"\n✅ Found deal!")
            print(f"  Deal ID: {deal.get('id')}")
            print(f"  Deal Name: {deal.get('Deal_Name')}")
            print(f"  Stage: {deal.get('Stage')}")
            print(f"  Amount: {deal.get('Amount')}")
            print(f"  Contact: {deal.get('Contact_Name')}")
        else:
            print("\n❌ No deal found for this ticket")

    finally:
        linker.close()


def example_2_find_deal_custom_strategies():
    """Example 2: Find deal using specific strategies only."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: FIND DEAL WITH CUSTOM STRATEGIES")
    print("=" * 80)

    linker = TicketDealLinker()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID

        # Try only email and phone strategies
        strategies = ["contact_email", "contact_phone"]

        deal = linker.find_deal_for_ticket(
            ticket_id,
            strategies=strategies
        )

        if deal:
            print(f"\n✅ Found deal using strategies: {strategies}")
            print(f"  Deal: {deal.get('Deal_Name')}")
        else:
            print(f"\n❌ No deal found with strategies: {strategies}")

    finally:
        linker.close()


def example_3_create_bidirectional_link():
    """Example 3: Create bidirectional link between ticket and deal."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: CREATE BIDIRECTIONAL LINK")
    print("=" * 80)

    linker = TicketDealLinker()

    try:
        ticket_id = "123456789"  # Replace with real IDs
        deal_id = "987654321"

        # Create bidirectional link
        result = linker.link_ticket_to_deal_bidirectional(
            ticket_id=ticket_id,
            deal_id=deal_id,
            update_ticket_field="cf_deal_id",  # Custom field in Desk
            update_deal_field="Ticket_ID"      # Custom field in CRM
        )

        print("\n📊 Link Result:")
        print(f"  Ticket updated: {result['ticket_updated']}")
        print(f"  Deal updated: {result['deal_updated']}")

        if result['errors']:
            print(f"  Errors: {result['errors']}")
        else:
            print("  ✅ Bidirectional link created successfully!")

    finally:
        linker.close()


def example_4_auto_link_ticket():
    """Example 4: Automatically find and link a ticket."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: AUTO-LINK TICKET")
    print("=" * 80)

    linker = TicketDealLinker()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID

        # Automatically find deal and create bidirectional link
        deal_id = linker.auto_link_ticket(
            ticket_id=ticket_id,
            create_bidirectional_link=True
        )

        if deal_id:
            print(f"\n✅ Ticket auto-linked successfully!")
            print(f"  Linked to deal: {deal_id}")
            print(f"  Bidirectional link created in custom fields")
        else:
            print("\n❌ Could not auto-link ticket (no deal found)")

    finally:
        linker.close()


def example_5_workflow_with_auto_linking():
    """Example 5: Process ticket with automatic CRM linking."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: COMPLETE WORKFLOW WITH AUTO-LINKING")
    print("=" * 80)

    orchestrator = ZohoAutomationOrchestrator()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID

        # Process ticket and automatically find/update related deal
        result = orchestrator.process_ticket_with_auto_crm_link(
            ticket_id=ticket_id,
            auto_respond=False,           # Don't auto-respond (just analyze)
            auto_update_ticket=False,     # Don't update ticket
            auto_update_deal=True,        # Auto-update the deal
            auto_add_note=True,           # Add note to deal
            create_bidirectional_link=True  # Link them together
        )

        print("\n📊 Workflow Result:")
        print(f"  Success: {result['success']}")
        print(f"  Deal found: {result.get('deal_found', False)}")

        if result.get('deal_found'):
            print(f"  Deal ID: {result['deal_id']}")
            print(f"  Deal Name: {result['deal_name']}")

            # Ticket analysis
            ticket_analysis = result['ticket_result']['agent_analysis']
            print(f"\n  Ticket Analysis:")
            print(f"    Priority: {ticket_analysis['priority']}")
            print(f"    Suggested Status: {ticket_analysis['suggested_status']}")

            # CRM analysis
            crm_analysis = result['crm_result']['agent_analysis']
            print(f"\n  CRM Analysis:")
            print(f"    Priority Score: {crm_analysis['priority_score']}/10")
            print(f"    Suggested Stage: {crm_analysis['suggested_stage']}")
            print(f"    Next Steps: {crm_analysis['suggested_next_steps'][:100]}...")

            # Actions taken
            if result['crm_result']['actions_taken']:
                print(f"\n  Actions Taken:")
                for action in result['crm_result']['actions_taken']:
                    print(f"    ✓ {action}")
        else:
            print("\n  ℹ️ No deal found - ticket processed without CRM update")

    finally:
        orchestrator.close()


def example_6_linking_strategies_explained():
    """Example 6: Explanation of all linking strategies."""
    print("\n" + "=" * 80)
    print("LINKING STRATEGIES EXPLAINED")
    print("=" * 80)

    strategies = {
        "custom_field": {
            "description": "Check if ticket has a custom field with deal_id",
            "fields": ["cf_deal_id", "cf_zoho_crm_deal_id", "Deal_ID"],
            "priority": "⭐⭐⭐ (Highest - direct link)",
            "use_case": "When tickets are already linked via custom fields"
        },
        "contact_email": {
            "description": "Search deals by contact email",
            "search": "Queries CRM for deals with matching contact email",
            "priority": "⭐⭐ (High - most reliable contact info)",
            "use_case": "Most common - email is usually unique"
        },
        "contact_phone": {
            "description": "Search deals by contact phone number",
            "search": "Queries CRM for deals with matching phone",
            "priority": "⭐⭐ (High - good fallback)",
            "use_case": "When email not available or to confirm match"
        },
        "account": {
            "description": "Search deals by account/organization",
            "search": "Queries CRM for deals with matching company",
            "priority": "⭐ (Medium - may return multiple)",
            "use_case": "For B2B scenarios with organizational tickets"
        },
        "recent_deal": {
            "description": "Get most recent deal for contact",
            "search": "Gets latest modified deal for the contact",
            "priority": "⭐ (Low - fallback only)",
            "use_case": "Last resort when other methods fail"
        }
    }

    for strategy_name, info in strategies.items():
        print(f"\n📌 {strategy_name.upper().replace('_', ' ')}")
        print(f"  Description: {info['description']}")
        if 'search' in info:
            print(f"  How it works: {info['search']}")
        if 'fields' in info:
            print(f"  Checks fields: {', '.join(info['fields'])}")
        print(f"  Priority: {info['priority']}")
        print(f"  Use case: {info['use_case']}")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("TICKET-DEAL LINKING EXAMPLES")
    print("=" * 80)
    print("\nThese examples show how to link Zoho Desk tickets to Zoho CRM deals")
    print("using multiple intelligent strategies.")

    # Show strategy explanations
    example_6_linking_strategies_explained()

    print("\n\n" + "=" * 80)
    print("PRACTICAL EXAMPLES")
    print("=" * 80)

    # Uncomment the examples you want to run:

    # example_1_find_deal_for_ticket()
    # example_2_find_deal_custom_strategies()
    # example_3_create_bidirectional_link()
    # example_4_auto_link_ticket()
    # example_5_workflow_with_auto_linking()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\n✅ The system provides multiple ways to link tickets to deals:")
    print("   1. Manual linking with known deal_id")
    print("   2. Automatic linking using intelligent search")
    print("   3. Bidirectional linking via custom fields")
    print("   4. Complete workflow automation")
    print("\n✅ Strategies are tried in priority order until a match is found")
    print("\n✅ Bidirectional links ensure data consistency")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
