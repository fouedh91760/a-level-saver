"""
Example: Automated deal linking with business rules.

This example shows how to use the DealLinkingAgent to automatically
maintain ticket-deal links based on your business rules.
"""
import logging
from src.agents.deal_linking_agent import DealLinkingAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_1_link_single_ticket():
    """Example 1: Link a single ticket to its deal."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: LINK SINGLE TICKET")
    print("=" * 80)

    agent = DealLinkingAgent()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID

        # Process the ticket
        result = agent.process({
            "ticket_id": ticket_id
        })

        print(f"\n📊 Result:")
        print(f"  Success: {result['success']}")
        print(f"  Action: {result.get('action')}")

        if result.get('deal_found'):
            print(f"  Deal ID: {result['deal_id']}")
            print(f"  Deal Name: {result.get('deal_name', 'N/A')}")
            print(f"  Bidirectional link: {result.get('bidirectional_link', False)}")
        elif result.get('already_linked'):
            print(f"  Already linked to: {result['deal_id']}")
        else:
            print(f"  No deal found")

    finally:
        agent.close()


def example_2_batch_process_unlinked():
    """Example 2: Process all tickets without deal_id."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: BATCH PROCESS UNLINKED TICKETS")
    print("=" * 80)

    agent = DealLinkingAgent()

    try:
        # Process all open tickets without deal_id
        result = agent.process_unlinked_tickets(
            status="Open",
            limit=50,
            create_deal_if_missing=False  # Set to True if business rules allow
        )

        print(f"\n📊 Batch Processing Summary:")
        print(f"  Total tickets: {result['total_tickets']}")
        print(f"  Unlinked tickets: {result['unlinked_tickets']}")
        print(f"  Successfully linked: {result['successful_links']}")
        print(f"  No deal found: {result['no_deal_found']}")
        print(f"  Failed: {result['failed']}")

        # Show details of successful links
        successful = [r for r in result['results'] if r.get('action') == 'linked']
        if successful:
            print(f"\n✅ Successfully linked tickets:")
            for r in successful[:5]:  # Show first 5
                print(f"    - Ticket {r['ticket_id']} → Deal {r['deal_name']}")

        # Show tickets without deals
        no_deal = [r for r in result['results'] if r.get('action') == 'no_deal_found']
        if no_deal:
            print(f"\n⚠️  Tickets without deals ({len(no_deal)}):")
            for r in no_deal[:5]:  # Show first 5
                print(f"    - Ticket {r['ticket_id']}")

    finally:
        agent.close()


def example_3_validate_existing_links():
    """Example 3: Validate data quality of existing links."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: VALIDATE EXISTING LINKS")
    print("=" * 80)

    agent = DealLinkingAgent()

    try:
        # Validate existing ticket-deal links
        result = agent.validate_existing_links(limit=50)

        print(f"\n📊 Validation Summary:")
        print(f"  Total validated: {result['total_validated']}")
        print(f"  Correct links: {result['correct']}")
        print(f"  Mismatches: {result['mismatches']}")
        print(f"  Deals not found: {result['deal_not_found']}")

        # Show mismatches
        mismatches = [r for r in result['results'] if r['status'] == 'mismatch']
        if mismatches:
            print(f"\n⚠️  Link mismatches found ({len(mismatches)}):")
            for r in mismatches[:5]:  # Show first 5
                print(f"    - Ticket {r['ticket_id']}")
                print(f"      Currently linked to: {r['existing_deal_id']}")
                print(f"      Should be linked to: {r['suggested_deal_id']}")

        # Show broken links
        broken = [r for r in result['results'] if r['status'] == 'deal_not_found']
        if broken:
            print(f"\n❌ Broken links ({len(broken)}):")
            for r in broken[:5]:  # Show first 5
                print(f"    - Ticket {r['ticket_id']} → Deal {r['existing_deal_id']} (not found)")

    finally:
        agent.close()


def example_4_scheduled_maintenance():
    """Example 4: Scheduled maintenance job (for cron)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: SCHEDULED MAINTENANCE")
    print("=" * 80)
    print("\nThis example shows what a scheduled job would do:")

    agent = DealLinkingAgent()

    try:
        print("\n1️⃣ Processing new tickets without links...")
        result1 = agent.process_unlinked_tickets(
            status="Open",
            limit=50
        )
        print(f"   ✓ Linked {result1['successful_links']} tickets")

        print("\n2️⃣ Validating existing links...")
        result2 = agent.validate_existing_links(limit=50)
        print(f"   ✓ Validated {result2['total_validated']} links")
        print(f"   ⚠️  Found {result2['mismatches']} mismatches")

        print("\n3️⃣ Summary:")
        print(f"   - New links created: {result1['successful_links']}")
        print(f"   - Links validated: {result2['correct']}")
        print(f"   - Issues found: {result2['mismatches'] + result2['deal_not_found']}")

        print("\n✅ Maintenance complete!")

    finally:
        agent.close()


def show_business_rules_impact():
    """Show how business rules affect the linking."""
    print("\n" + "=" * 80)
    print("HOW BUSINESS RULES WORK")
    print("=" * 80)

    print("\nYour business rules (in business_rules.py) control:")

    print("\n1️⃣ WHICH TICKETS GET DEALS CREATED")
    print("   Method: should_create_deal_for_ticket()")
    print("   Example rules:")
    print("   - Only create for 'Sales' department")
    print("   - Only if ticket contains 'pricing', 'quote', etc.")
    print("   - Only from certain channels (email, web form)")

    print("\n2️⃣ WHAT DATA GOES IN THE DEAL")
    print("   Method: get_deal_data_from_ticket()")
    print("   Example data:")
    print("   - Deal_Name: From contact name")
    print("   - Amount: Based on service tier")
    print("   - Stage: 'Qualification' for new deals")
    print("   - Lead_Source: 'Support Ticket'")

    print("\n3️⃣ WHICH LINKS ARE ALLOWED")
    print("   Method: should_link_ticket_to_deal()")
    print("   Example rules:")
    print("   - Don't link to closed deals")
    print("   - Don't link technical support to sales deals")
    print("   - Emails must match")

    print("\n4️⃣ WHICH STRATEGIES TO USE")
    print("   Method: get_preferred_linking_strategies()")
    print("   Default order:")
    print("   1. custom_field (fastest)")
    print("   2. contact_email (most reliable)")
    print("   3. contact_phone (fallback)")
    print("   4. account (for B2B)")

    print("\n5️⃣ WHICH TICKETS TO AUTO-PROCESS")
    print("   Method: should_auto_process_ticket()")
    print("   Example rules:")
    print("   - Skip VIP customers (manual review)")
    print("   - Skip urgent tickets")
    print("   - Skip complaints")

    print("\n" + "=" * 80)
    print("TO CUSTOMIZE:")
    print("=" * 80)
    print("\n1. Edit business_rules.py")
    print("2. Modify the methods to match your processes")
    print("3. Test with: python business_rules.py")
    print("4. Run the agent - it will use your rules automatically!")
    print("\n" + "=" * 80)


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("AUTOMATED DEAL LINKING EXAMPLES")
    print("=" * 80)
    print("\nThis agent automatically maintains ticket-deal links using your")
    print("business rules defined in business_rules.py")

    # Show how business rules work
    show_business_rules_impact()

    print("\n\n" + "=" * 80)
    print("PRACTICAL EXAMPLES")
    print("=" * 80)
    print("\nUncomment the examples you want to run:")

    # Uncomment to run:
    # example_1_link_single_ticket()
    # example_2_batch_process_unlinked()
    # example_3_validate_existing_links()
    # example_4_scheduled_maintenance()

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("\n1. ✅ Customize business_rules.py for your business")
    print("2. ✅ Test with a few tickets first")
    print("3. ✅ Run batch processing: example_2")
    print("4. ✅ Schedule maintenance: example_4 in cron")
    print("\n✅ The agent will keep your links up to date automatically!")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
