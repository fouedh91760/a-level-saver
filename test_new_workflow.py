"""
Test script for the new workflow: Thread email → Contacts → All Deals → Routing

This script tests the complete implementation:
1. DealLinkingAgent extracts email from threads
2. Searches contacts by email
3. Retrieves all deals for contacts
4. Determines department using BusinessRules
5. DispatcherAgent uses the recommended department
6. Complete orchestrator workflow

Usage:
    python test_new_workflow.py <ticket_id>

Examples:
    # Test with a specific ticket
    python test_new_workflow.py 123456789

    # Test the complete workflow (linking + routing)
    python test_new_workflow.py 123456789 --full-workflow
"""
import logging
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_deal_linking_agent(ticket_id: str):
    """Test DealLinkingAgent with new workflow."""
    print("\n" + "=" * 80)
    print("TEST 1: DealLinkingAgent - Thread email → Contacts → Deals")
    print("=" * 80)

    from src.agents import DealLinkingAgent

    agent = DealLinkingAgent()

    try:
        print(f"\n🎫 Processing ticket {ticket_id}...")
        result = agent.process({"ticket_id": ticket_id})

        print("\n📊 RESULTS:")
        print(f"   Success: {result.get('success')}")
        print(f"   Email found: {result.get('email_found')}")
        print(f"   Email: {result.get('email')}")
        print(f"   Contacts found: {result.get('contacts_found')}")
        print(f"   Deals found: {result.get('deals_found')}")

        if result.get('selected_deal'):
            deal = result['selected_deal']
            print(f"\n💼 SELECTED DEAL:")
            print(f"   ID: {deal.get('id')}")
            print(f"   Name: {deal.get('Deal_Name')}")
            print(f"   Amount: €{deal.get('Amount')}")
            print(f"   Stage: {deal.get('Stage')}")
            print(f"   Evalbox: {deal.get('Evalbox', 'N/A')}")

        print(f"\n🎯 ROUTING:")
        print(f"   Recommended department: {result.get('recommended_department', 'None')}")
        print(f"   Routing explanation: {result.get('routing_explanation')}")

        if result.get('all_deals'):
            print(f"\n📋 ALL DEALS ({len(result['all_deals'])}):")
            for idx, deal in enumerate(result['all_deals'][:5], 1):  # Show first 5
                print(f"   {idx}. {deal.get('Deal_Name')} - €{deal.get('Amount')} - {deal.get('Stage')}")
            if len(result['all_deals']) > 5:
                print(f"   ... and {len(result['all_deals']) - 5} more")

        print("\n" + "=" * 80)
        return result

    except Exception as e:
        logger.error(f"Error in DealLinkingAgent test: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        agent.close()


def test_dispatcher_agent(ticket_id: str, linking_result: dict):
    """Test DispatcherAgent with linking result."""
    print("\n" + "=" * 80)
    print("TEST 2: DispatcherAgent - Using recommended department from linking")
    print("=" * 80)

    from src.agents import TicketDispatcherAgent

    agent = TicketDispatcherAgent()

    try:
        print(f"\n🎫 Processing ticket {ticket_id} with linking result...")
        result = agent.process({
            "ticket_id": ticket_id,
            "linking_result": linking_result,
            "auto_reassign": False  # Don't actually reassign during test
        })

        print("\n📊 DISPATCHER RESULTS:")
        print(f"   Success: {result.get('success')}")
        print(f"   Current department: {result.get('current_department')}")
        print(f"   Recommended department: {result.get('recommended_department')}")
        print(f"   Should reassign: {result.get('should_reassign')}")
        print(f"   Routing method: {result.get('routing_method')}")
        print(f"   Confidence: {result.get('confidence')}%")
        print(f"   Reasoning: {result.get('reasoning')}")

        print("\n" + "=" * 80)
        return result

    except Exception as e:
        logger.error(f"Error in DispatcherAgent test: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        agent.close()


def test_full_workflow(ticket_id: str):
    """Test the complete orchestrator workflow."""
    print("\n" + "=" * 80)
    print("TEST 3: Complete Orchestrator Workflow")
    print("=" * 80)

    from src.orchestrator import ZohoAutomationOrchestrator

    orchestrator = ZohoAutomationOrchestrator()

    try:
        print(f"\n🎫 Running complete workflow for ticket {ticket_id}...")
        result = orchestrator.process_ticket_complete_workflow(
            ticket_id=ticket_id,
            auto_dispatch=False,  # Don't reassign during test
            auto_link=False,      # Don't create links during test
            auto_respond=False,   # Don't respond during test
            auto_update_ticket=False,
            auto_update_deal=False,
            auto_add_note=False
        )

        print("\n📊 WORKFLOW RESULTS:")
        print(f"   Success: {result.get('success')}")

        # Linking result
        linking = result.get('linking_result', {})
        print(f"\n   🔗 LINKING:")
        print(f"      Email: {linking.get('email')}")
        print(f"      Deals found: {linking.get('deals_found')}")
        print(f"      Recommended dept: {linking.get('recommended_department')}")

        # Dispatch result
        dispatch = result.get('dispatch_result', {})
        print(f"\n   🎯 ROUTING:")
        print(f"      Current dept: {dispatch.get('current_department')}")
        print(f"      Recommended dept: {dispatch.get('recommended_department')}")
        print(f"      Should reassign: {dispatch.get('should_reassign')}")
        print(f"      Method: {dispatch.get('routing_method')}")

        # Ticket processing
        ticket_result = result.get('ticket_result', {})
        print(f"\n   📧 TICKET PROCESSING:")
        print(f"      Processed: {'Yes' if ticket_result else 'No'}")

        # CRM update
        crm_result = result.get('crm_result', {})
        print(f"\n   💼 CRM UPDATE:")
        if crm_result:
            if crm_result.get('skipped'):
                print(f"      Skipped: {crm_result.get('reason')}")
            else:
                print(f"      Updated: Yes")
        else:
            print(f"      Updated: No")

        print("\n" + "=" * 80)
        return result

    except Exception as e:
        logger.error(f"Error in full workflow test: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        orchestrator.close()


def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    ticket_id = sys.argv[1]
    full_workflow = "--full-workflow" in sys.argv

    print("\n" + "=" * 80)
    print("🧪 TESTING NEW WORKFLOW IMPLEMENTATION")
    print("=" * 80)
    print(f"Ticket ID: {ticket_id}")
    print(f"Full workflow: {full_workflow}")

    # Test 1: DealLinkingAgent
    linking_result = test_deal_linking_agent(ticket_id)

    if not linking_result:
        print("\n❌ DealLinkingAgent test failed. Stopping.")
        return

    # Test 2: DispatcherAgent
    dispatcher_result = test_dispatcher_agent(ticket_id, linking_result)

    if not dispatcher_result:
        print("\n❌ DispatcherAgent test failed. Stopping.")
        return

    # Test 3: Full workflow (optional)
    if full_workflow:
        workflow_result = test_full_workflow(ticket_id)

        if not workflow_result:
            print("\n❌ Full workflow test failed.")
            return

    # Summary
    print("\n" + "=" * 80)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 80)
    print("\n📋 SUMMARY:")
    print(f"   Email extracted: {linking_result.get('email')}")
    print(f"   Contacts found: {linking_result.get('contacts_found')}")
    print(f"   Deals found: {linking_result.get('deals_found')}")
    print(f"   Department recommended: {linking_result.get('recommended_department')}")
    print(f"   Dispatcher agrees: {dispatcher_result.get('recommended_department') == linking_result.get('recommended_department')}")
    print(f"   Current dept: {dispatcher_result.get('current_department')}")
    print(f"   Needs reassignment: {dispatcher_result.get('should_reassign')}")

    # Save results to file
    output_file = f"test_results_{ticket_id}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "ticket_id": ticket_id,
            "linking_result": linking_result,
            "dispatcher_result": dispatcher_result,
            "full_workflow_result": workflow_result if full_workflow else None
        }, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Results saved to: {output_file}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
