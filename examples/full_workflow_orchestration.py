"""
Example: Full workflow orchestration.

This example shows how to use the orchestrator to:
1. Process a ticket and update the related CRM opportunity
2. Run batch processing of tickets
3. Find and update stale opportunities
4. Run a full automation cycle
"""
import logging
from src.orchestrator import ZohoAutomationOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    # Initialize the orchestrator
    orchestrator = ZohoAutomationOrchestrator()

    try:
        # Example 1: Process ticket with CRM update
        logger.info("Example 1: Processing ticket with CRM update")
        result = orchestrator.process_ticket_with_crm_update(
            ticket_id="123456789",      # Replace with actual ticket ID
            deal_id="987654321",        # Replace with actual deal ID
            auto_respond=False,         # Set to True to auto-respond to ticket
            auto_update_ticket=False,   # Set to True to auto-update ticket status
            auto_update_deal=False,     # Set to True to auto-update deal fields
            auto_add_note=False         # Set to True to auto-add notes to deal
        )

        if result['success']:
            print("\n=== Ticket & CRM Processing Results ===")
            print("\nTicket Analysis:")
            ticket_analysis = result['ticket_result']['agent_analysis']
            print(f"  Priority: {ticket_analysis['priority']}")
            print(f"  Suggested Response: {ticket_analysis['suggested_response'][:100]}...")

            print("\nCRM Analysis:")
            crm_analysis = result['crm_result']['agent_analysis']
            print(f"  Priority Score: {crm_analysis['priority_score']}/10")
            print(f"  Suggested Stage: {crm_analysis['suggested_stage']}")
            print(f"  Next Steps: {crm_analysis['suggested_next_steps']}")
        else:
            print(f"Error: {result['error']}")

        # Example 2: Batch process tickets
        logger.info("\nExample 2: Batch processing tickets")
        batch_result = orchestrator.batch_process_tickets(
            status="Open",
            limit=10,
            auto_respond=False,  # Set to True for auto-responses
            auto_update=False    # Set to True for auto-updates
        )

        print("\n=== Batch Processing Summary ===")
        print(f"  Total Processed: {batch_result['total_processed']}")
        print(f"  Successful: {batch_result['successful']}")
        print(f"  Failed: {batch_result['failed']}")
        print(f"  Escalations Needed: {batch_result['escalations_needed']}")

        # Example 3: Find and update stale opportunities
        logger.info("\nExample 3: Finding stale opportunities")
        stale_result = orchestrator.find_and_update_stale_opportunities(
            days_stale=14,
            auto_update=False,    # Set to True for auto-updates
            auto_add_note=False   # Set to True to add notes
        )

        print("\n=== Stale Opportunities Summary ===")
        print(f"  Total Analyzed: {stale_result['total_analyzed']}")
        print(f"  High Priority: {stale_result['high_priority']}")
        print(f"  Medium Priority: {stale_result['medium_priority']}")
        print(f"  Low Priority: {stale_result['low_priority']}")

        print("\n  Top 3 High-Priority Opportunities:")
        for opp in stale_result['opportunities'][:3]:
            print(f"    • {opp['deal_name']} (Score: {opp['priority_score']}/10)")
            print(f"      {opp['reason']}")

        # Example 4: Run full automation cycle
        logger.info("\nExample 4: Running full automation cycle")
        cycle_result = orchestrator.run_full_automation_cycle(
            process_tickets=True,
            update_opportunities=True,
            ticket_status="Open",
            ticket_limit=10,
            auto_actions=False  # Set to True to enable auto-actions
        )

        print("\n=== Full Automation Cycle Results ===")
        if cycle_result['tickets_processed']:
            print(f"\nTickets Processed: {cycle_result['tickets_processed']['total_processed']}")
        if cycle_result['opportunities_updated']:
            print(f"Opportunities Analyzed: {cycle_result['opportunities_updated']['total_analyzed']}")

        # Example 5: Link ticket to deal (useful for finding related opportunities)
        logger.info("\nExample 5: Linking ticket to deal")
        deal_id = orchestrator.link_ticket_to_deal(
            ticket_id="123456789",
            contact_email="student@example.com",  # Replace with actual email
            auto_create_deal=False
        )

        if deal_id:
            print(f"\n=== Ticket-Deal Link ===")
            print(f"  Found deal ID: {deal_id}")
        else:
            print("\n  No deal found for this contact")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    finally:
        # Clean up
        orchestrator.close()


if __name__ == "__main__":
    main()
