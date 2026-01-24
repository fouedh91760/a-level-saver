"""
Example: Ticket dispatcher and department routing.

This example demonstrates how the TicketDispatcherAgent ensures tickets
are routed to the correct department BEFORE deal linking and processing.
"""
import logging
from src.agents import TicketDispatcherAgent
from src.orchestrator import ZohoAutomationOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_1_validate_single_ticket():
    """Example 1: Validate department routing for a single ticket."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: VALIDATE DEPARTMENT ROUTING")
    print("=" * 80)

    agent = TicketDispatcherAgent()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID

        # Validate department (no auto-reassign)
        result = agent.process({
            "ticket_id": ticket_id,
            "auto_reassign": False  # Just check, don't reassign
        })

        print(f"\n📊 Routing Analysis:")
        print(f"  Current department: {result['current_department']}")
        print(f"  Recommended department: {result['recommended_department']}")
        print(f"  Should reassign: {result['should_reassign']}")
        print(f"  Confidence: {result['confidence']}%")
        print(f"  Method: {result['method']}")
        print(f"  Reasoning: {result['reasoning']}")

        if result['should_reassign']:
            print(f"\n⚠️  RECOMMENDATION: Move to {result['recommended_department']}")
            print(f"   Signals found: {', '.join(result['signals'])}")
        else:
            print(f"\n✅ Ticket is in correct department")

    finally:
        agent.close()


def example_2_auto_reassign_ticket():
    """Example 2: Automatically reassign ticket to correct department."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: AUTO-REASSIGN TO CORRECT DEPARTMENT")
    print("=" * 80)

    agent = TicketDispatcherAgent()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID

        # Auto-reassign if needed
        result = agent.process({
            "ticket_id": ticket_id,
            "auto_reassign": True  # Automatically reassign
        })

        print(f"\n📊 Routing Result:")
        print(f"  Current department: {result['current_department']}")
        print(f"  Recommended department: {result['recommended_department']}")

        if result.get('reassigned'):
            print(f"\n✅ REASSIGNED to {result['recommended_department']}")
            print(f"   Confidence: {result['confidence']}%")
            print(f"   Reasoning: {result['reasoning']}")
        elif result['should_reassign']:
            print(f"\n❌ FAILED to reassign (check permissions or department ID)")
        else:
            print(f"\n✅ No reassignment needed - already in correct department")

    finally:
        agent.close()


def example_3_batch_validate_departments():
    """Example 3: Validate department routing for all open tickets."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: BATCH VALIDATE DEPARTMENTS")
    print("=" * 80)

    agent = TicketDispatcherAgent()

    try:
        # Validate all open tickets
        result = agent.batch_validate_departments(
            status="Open",
            limit=50
        )

        print(f"\n📊 Batch Validation Summary:")
        print(f"  Total checked: {result['total_checked']}")
        print(f"  Correct department: {result['correct_department']}")
        print(f"  Should reassign: {result['should_reassign']}")

        # Show tickets that need reassignment
        if result['should_reassign'] > 0:
            print(f"\n⚠️  Tickets needing reassignment:")
            for ticket_result in result['results']:
                if ticket_result.get('should_reassign'):
                    print(f"    - Ticket {ticket_result['ticket_id']}")
                    print(f"      From: {ticket_result['current_department']}")
                    print(f"      To: {ticket_result['recommended_department']}")
                    print(f"      Confidence: {ticket_result['confidence']}%")
                    print()

    finally:
        agent.close()


def example_4_complete_workflow():
    """Example 4: Complete workflow with dispatcher."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: COMPLETE WORKFLOW WITH DISPATCHER")
    print("=" * 80)
    print("\nThis shows the RECOMMENDED workflow that includes all agents:")

    orchestrator = ZohoAutomationOrchestrator()

    try:
        ticket_id = "123456789"  # Replace with real ticket ID

        # Run complete workflow
        result = orchestrator.process_ticket_complete_workflow(
            ticket_id=ticket_id,
            auto_dispatch=True,    # Auto-route to correct department
            auto_link=True,        # Auto-link to deal
            auto_respond=False,    # Don't auto-respond (review first)
            auto_update_ticket=False,
            auto_update_deal=False
        )

        print(f"\n📊 Complete Workflow Results:")
        print(f"  Success: {result['success']}")

        # Step 1: Dispatch
        dispatch = result.get('dispatch_result', {})
        print(f"\n1️⃣ Dispatch:")
        print(f"  Current dept: {dispatch.get('current_department')}")
        print(f"  Recommended: {dispatch.get('recommended_department')}")
        if dispatch.get('reassigned'):
            print(f"  ✅ Reassigned to correct department")

        # Step 2: Linking
        linking = result.get('linking_result', {})
        print(f"\n2️⃣ Deal Linking:")
        if linking.get('deal_found'):
            print(f"  ✅ Linked to deal {linking.get('deal_id')}")
            print(f"  Deal: {linking.get('deal_name')}")
        else:
            print(f"  ❌ No deal found")

        # Step 3: Ticket processing
        ticket = result.get('ticket_result', {})
        print(f"\n3️⃣ Ticket Processing:")
        if ticket:
            print(f"  Response generated: Yes")
            print(f"  Escalation needed: {ticket.get('agent_analysis', {}).get('should_escalate', False)}")

        # Step 4: CRM update
        crm = result.get('crm_result', {})
        print(f"\n4️⃣ CRM Update:")
        if crm.get('skipped'):
            print(f"  ⏭️  Skipped (no deal)")
        elif crm:
            print(f"  ✅ Deal updated")

    finally:
        orchestrator.close()


def show_routing_rules_configuration():
    """Show how to configure department routing rules."""
    print("\n" + "=" * 80)
    print("HOW TO CONFIGURE ROUTING RULES")
    print("=" * 80)

    print("\n1️⃣ Edit business_rules.py")
    print("=" * 80)

    example_code = '''
@staticmethod
def get_department_routing_rules() -> Dict[str, Any]:
    """Define department routing rules."""
    return {
        "DOC": {
            "keywords": [
                "uber",
                "a-level",
                "student",
                "education"
            ],
            "contact_domains": []
        },
        "Sales": {
            "keywords": [
                "pricing",
                "quote",
                "demo",
                "purchase"
            ],
            "contact_domains": []
        },
        "Support": {
            "keywords": [
                "technical",
                "error",
                "bug",
                "issue"
            ],
            "contact_domains": []
        }
    }
'''

    print(example_code)

    print("\n2️⃣ How Routing Works")
    print("=" * 80)
    print("\nThe dispatcher uses a 2-step approach:")
    print("\n  Step 1: Business Rules (Fast & Deterministic)")
    print("    - Check keywords in subject/description")
    print("    - Check contact email domains")
    print("    - If match found → 95% confidence")
    print("\n  Step 2: AI Analysis (Smart & Contextual)")
    print("    - If no rule match, use Claude AI")
    print("    - Analyzes full ticket context")
    print("    - Provides reasoning and confidence score")

    print("\n3️⃣ Workflow Integration")
    print("=" * 80)
    print("\nWHY dispatcher is the first step:")
    print("  1. Ticket arrives")
    print("  2. ✅ Dispatcher validates department → Reassign if needed")
    print("  3. DealLinkingAgent uses department-specific logic")
    print("  4. DeskAgent processes ticket")
    print("  5. CRMAgent updates deal")
    print("\nWithout dispatcher:")
    print("  ❌ Wrong department → Wrong business rules → Wrong deal linked")
    print("\nWith dispatcher:")
    print("  ✅ Correct department → Correct business rules → Correct deal linked")

    print("\n4️⃣ Testing Your Configuration")
    print("=" * 80)
    print("\nAfter editing business_rules.py:")
    print("  1. Test single ticket:")
    print("     python examples/ticket_dispatcher.py")
    print("  2. Validate batch:")
    print("     from src.agents import TicketDispatcherAgent")
    print("     agent = TicketDispatcherAgent()")
    print("     result = agent.batch_validate_departments(limit=50)")
    print("  3. Check misrouted tickets and adjust rules")


def show_complete_workflow_diagram():
    """Show the complete workflow with all agents."""
    print("\n" + "=" * 80)
    print("COMPLETE AUTOMATION WORKFLOW")
    print("=" * 80)

    print("""
┌─────────────────────────────────────────────────────────────┐
│                    TICKET ARRIVES                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: TicketDispatcherAgent                             │
│  ────────────────────────────────────────────────────────── │
│  • Check business rules for keywords                        │
│  • Use AI if no rule match                                  │
│  • Reassign to correct department if needed                 │
│  • Confidence: 95% (rules) or variable (AI)                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: DealLinkingAgent                                   │
│  ────────────────────────────────────────────────────────── │
│  • Check if ticket already has cf_deal_id                   │
│  • Use department-specific search logic                     │
│  • DOC: Uber €20 (Won → Pending → Lost)                    │
│  • Sales: Open deals                                        │
│  • Fallback to email/phone/account search                   │
│  • Create bidirectional link                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: DeskTicketAgent                                    │
│  ────────────────────────────────────────────────────────── │
│  • Analyze ticket content                                   │
│  • Generate response recommendation                         │
│  • Check if escalation needed                               │
│  • Auto-respond if enabled                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: CRMOpportunityAgent                                │
│  ────────────────────────────────────────────────────────── │
│  • Analyze deal in context of ticket                        │
│  • Update deal fields (stage, priority, etc.)               │
│  • Add notes about customer interaction                     │
│  • Score engagement level                                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                      ✅ COMPLETE
    """)

    print("Each step is OPTIONAL and configurable via parameters.")
    print("The complete workflow ensures:")
    print("  ✅ Ticket in correct department")
    print("  ✅ Linked to correct deal")
    print("  ✅ Appropriate response generated")
    print("  ✅ CRM updated with context")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("TICKET DISPATCHER - DEPARTMENT ROUTING")
    print("=" * 80)
    print("\nWhy dispatcher is critical:")
    print("  Before processing ANY ticket, we must ensure it's in the")
    print("  CORRECT department. Otherwise, department-specific business")
    print("  rules will apply incorrectly!")

    # Show configuration
    show_routing_rules_configuration()

    # Show workflow
    show_complete_workflow_diagram()

    print("\n\n" + "=" * 80)
    print("PRACTICAL EXAMPLES")
    print("=" * 80)
    print("\nUncomment to test with your data:")

    # Uncomment to run:
    # example_1_validate_single_ticket()
    # example_2_auto_reassign_ticket()
    # example_3_batch_validate_departments()
    # example_4_complete_workflow()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\n✅ TicketDispatcherAgent ensures correct department routing")
    print("✅ Runs BEFORE deal linking to apply correct business rules")
    print("✅ Uses business rules (fast) + AI fallback (smart)")
    print("✅ Can auto-reassign or just validate")
    print("\n💡 Use process_ticket_complete_workflow() for full automation:")
    print("   Dispatcher → Deal Linking → Ticket Processing → CRM Update")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
