"""
Example: Department-specific deal linking.

This example demonstrates how different departments can have
different logic for finding deals.

Example: DOC department
- Priority 1: Uber €20 deals in "WON" status
- Priority 2: Uber €20 deals in "PENDING" status
- Priority 3: Uber €20 deals in "LOST" status

Always takes the most recent deal from each category.
"""
import logging
from src.ticket_deal_linker import TicketDealLinker
from src.agents import DealLinkingAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_doc_department_logic():
    """
    Example: DOC department with specific Uber deal logic.
    """
    print("\n" + "=" * 80)
    print("DEPARTMENT-SPECIFIC LINKING: DOC DEPARTMENT")
    print("=" * 80)

    print("\n📋 Business Logic for DOC Department:")
    print("   1. Search: Uber €20 deals - WON status (most recent)")
    print("   2. Fallback: Uber €20 deals - PENDING status (most recent)")
    print("   3. Fallback: Uber €20 deals - LOST status (most recent)")
    print("\nContact email must match ticket email.")

    linker = TicketDealLinker()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID from DOC department

        # Find deal using department-specific logic
        deal = linker.find_deal_for_ticket(
            ticket_id=ticket_id,
            strategies=["department_specific"]  # Only use department logic
        )

        if deal:
            print(f"\n✅ Deal found!")
            print(f"  Deal ID: {deal.get('id')}")
            print(f"  Deal Name: {deal.get('Deal_Name')}")
            print(f"  Stage: {deal.get('Stage')}")
            print(f"  Amount: {deal.get('Amount')}")

            # Check if it's an Uber deal
            if "Uber" in deal.get("Deal_Name", ""):
                print(f"  Type: Uber Deal ✅")
        else:
            print(f"\n❌ No deal found")
            print(f"   Possible reasons:")
            print(f"   - Ticket not in DOC department")
            print(f"   - No Uber €20 deals for this contact")
            print(f"   - Contact email doesn't match")

    finally:
        linker.close()


def example_all_departments():
    """
    Example: Process tickets from multiple departments.
    """
    print("\n" + "=" * 80)
    print("MULTI-DEPARTMENT PROCESSING")
    print("=" * 80)

    print("\n📋 Each department has its own logic:")
    print("   DOC: Uber €20 deals (Won → Pending → Lost)")
    print("   Sales: Open sales deals")
    print("   Support: Renewal deals")
    print("   Others: Standard email/phone search")

    agent = DealLinkingAgent()

    try:
        # Process tickets from various departments
        result = agent.process_unlinked_tickets(
            status="Open",
            limit=50
        )

        print(f"\n📊 Results:")
        print(f"  Total processed: {result['processed']}")
        print(f"  Successfully linked: {result['successful_links']}")
        print(f"  No deal found: {result['no_deal_found']}")

        # Show which departments were processed
        departments = {}
        for ticket_result in result.get('results', []):
            dept = ticket_result.get('department', 'Unknown')
            departments[dept] = departments.get(dept, 0) + 1

        if departments:
            print(f"\n  By department:")
            for dept, count in departments.items():
                print(f"    - {dept}: {count} tickets")

    finally:
        agent.close()


def show_department_logic_configuration():
    """
    Show how to configure department-specific logic.
    """
    print("\n" + "=" * 80)
    print("HOW TO CONFIGURE DEPARTMENT LOGIC")
    print("=" * 80)

    print("\n1️⃣ Edit business_rules.py")
    print("=" * 80)

    example_code = '''
@staticmethod
def get_deal_search_criteria_for_department(
    department: str,
    contact_email: str,
    ticket: Dict[str, Any]
) -> Optional[List[Dict[str, Any]]]:
    """Define department-specific search logic."""

    # DOC department: Uber €20 deals with fallback
    if department == "DOC":
        return [
            {
                "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Amount:equals:20)and(Stage:equals:Closed Won))",
                "description": "Uber €20 - WON",
                "max_results": 1
            },
            {
                "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Amount:equals:20)and(Stage:equals:Pending))",
                "description": "Uber €20 - PENDING",
                "max_results": 1
            },
            {
                "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Amount:equals:20)and(Stage:equals:Closed Lost))",
                "description": "Uber €20 - LOST",
                "max_results": 1
            }
        ]

    # YOUR_DEPARTMENT: Add your logic here
    elif department == "YOUR_DEPARTMENT":
        return [
            {
                "criteria": f"((Email:equals:{contact_email})and(YOUR_CRITERIA))",
                "description": "Your description",
                "max_results": 1
            }
        ]

    # Default: None = use standard strategies
    return None
'''

    print(example_code)

    print("\n2️⃣ Understanding the Configuration")
    print("=" * 80)
    print("\nEach department returns a LIST of search criteria.")
    print("The system tries them IN ORDER until it finds a deal.")
    print("\nThis is a FALLBACK mechanism:")
    print("  - Try criteria 1 → found? Return it")
    print("  - Not found? Try criteria 2 → found? Return it")
    print("  - Not found? Try criteria 3 → and so on...")

    print("\n3️⃣ Search Criteria Format")
    print("=" * 80)
    print("\nEach criteria dict has:")
    print("  - criteria: Zoho CRM search query")
    print("  - description: What you're searching for (for logs)")
    print("  - max_results: How many to return (usually 1)")
    print("  - sort_by: (optional) Field to sort by")
    print("  - sort_order: (optional) 'asc' or 'desc'")

    print("\n4️⃣ Zoho CRM Search Query Examples")
    print("=" * 80)
    print("\nBasic search:")
    print('  "(Email:equals:john@example.com)"')
    print("\nMultiple conditions (AND):")
    print('  "((Email:equals:john@example.com)and(Stage:equals:Won))"')
    print("\nContains text:")
    print('  "(Deal_Name:contains:Uber)"')
    print("\nEquals number:")
    print('  "(Amount:equals:20)"')
    print("\nNot equals:")
    print('  "(Stage:not_equals:Closed Lost)"')
    print("\nOR condition:")
    print('  "((Stage:equals:Won)or(Stage:equals:Pending))"')

    print("\n5️⃣ Testing Your Configuration")
    print("=" * 80)
    print("\nAfter editing business_rules.py:")
    print("  1. Run: python business_rules.py")
    print("  2. Test with one ticket:")
    print("     python examples/department_specific_linking.py")
    print("  3. Process batch:")
    print("     from src.agents import DealLinkingAgent")
    print("     agent = DealLinkingAgent()")
    print('     result = agent.process_unlinked_tickets(status="Open")')


def show_doc_workflow():
    """
    Show the complete workflow for DOC department.
    """
    print("\n" + "=" * 80)
    print("DOC DEPARTMENT WORKFLOW")
    print("=" * 80)

    print("\n📥 Ticket arrives in DOC department")
    print("   Contact: student@example.com")
    print("   Subject: 'Question about my Uber service'")

    print("\n🔍 DealLinkingAgent processes:")
    print("   1. Checks if ticket already has cf_deal_id → No")
    print("   2. Department = 'DOC' → Use department_specific strategy")

    print("\n🎯 Department-specific search:")
    print("   Step 1: Search Uber €20 deals - WON status")
    print("           Criteria: (Email=student@example.com AND")
    print("                      Deal_Name contains 'Uber' AND")
    print("                      Amount=20 AND")
    print("                      Stage='Closed Won')")
    print("           Result: Found deal #12345 'Uber - Student X' ✅")

    print("\n✅ Deal found! Linking...")
    print("   - Update ticket cf_deal_id = #12345")
    print("   - Update deal Ticket_ID = ticket_id")

    print("\n📊 Next time this contact creates a ticket:")
    print("   1. Checks cf_deal_id → No (new ticket)")
    print("   2. Department = 'DOC'")
    print("   3. Search Uber WON deals → Found same deal #12345 ✅")
    print("   4. Link created instantly!")

    print("\n💡 If no WON deal found:")
    print("   Step 2: Search Uber €20 deals - PENDING status")
    print("   Step 3: Search Uber €20 deals - LOST status")
    print("   Step 4: No deal found → Report 'no_deal_found'")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("DEPARTMENT-SPECIFIC DEAL LINKING")
    print("=" * 80)
    print("\nDifferent departments can have completely different logic")
    print("for finding the right deal.")

    # Show configuration
    show_department_logic_configuration()

    # Show DOC workflow
    show_doc_workflow()

    print("\n\n" + "=" * 80)
    print("PRACTICAL EXAMPLES")
    print("=" * 80)
    print("\nUncomment to test with your data:")

    # Uncomment to run:
    # example_doc_department_logic()
    # example_all_departments()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\n✅ Each department can define its own search logic")
    print("✅ Fallback mechanism tries multiple criteria in order")
    print("✅ Takes the most recent deal if multiple matches")
    print("✅ Falls back to standard strategies if no dept logic")
    print("\n💡 Perfect for complex business rules like:")
    print("   - DOC: Uber deals with status priority")
    print("   - Sales: Only open deals")
    print("   - Support: Renewal deals by close date")
    print("   - Premium: High-value deals only")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
