"""
Example: Basic ticket processing with the Desk agent.

This example shows how to:
1. Process a single ticket
2. Get AI analysis and suggested response
3. Optionally auto-respond and update the ticket
"""
import logging
from src.agents import DeskTicketAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    # Initialize the Desk agent
    agent = DeskTicketAgent()

    try:
        # Example 1: Analyze a ticket without taking action
        logger.info("Example 1: Analyzing ticket without auto-actions")
        result = agent.process({
            "ticket_id": "123456789",  # Replace with actual ticket ID
            "auto_respond": False,
            "auto_update": False
        })

        print("\n=== Ticket Analysis ===")
        print(f"Ticket Number: {result['ticket_number']}")
        print(f"\nAgent Analysis:")
        analysis = result['agent_analysis']
        print(f"  - Priority: {analysis['priority']}")
        print(f"  - Suggested Status: {analysis['suggested_status']}")
        print(f"  - Should Escalate: {analysis['should_escalate']}")
        print(f"\nSuggested Response:")
        print(analysis['suggested_response'])
        print(f"\nInternal Notes:")
        print(analysis['internal_notes'])

        # Example 2: Process ticket with auto-response
        logger.info("\nExample 2: Processing ticket with auto-response")
        result = agent.process({
            "ticket_id": "123456789",  # Replace with actual ticket ID
            "auto_respond": True,  # Will post the response to the ticket
            "auto_update": True    # Will update ticket status
        })

        print("\n=== Actions Taken ===")
        for action in result['actions_taken']:
            print(f"  ✓ {action}")

        # Example 3: Batch analyze multiple open tickets
        logger.info("\nExample 3: Batch analyzing open tickets")
        batch_results = agent.analyze_ticket_batch(
            status="Open",
            limit=5
        )

        print(f"\n=== Batch Analysis ({len(batch_results)} tickets) ===")
        for result in batch_results:
            if "error" in result:
                print(f"  ✗ Ticket {result['ticket_id']}: {result['error']}")
            else:
                analysis = result['agent_analysis']
                print(f"  • Ticket {result['ticket_number']}: {analysis['priority']} priority")
                if analysis['should_escalate']:
                    print(f"    ⚠ ESCALATION NEEDED: {analysis['escalation_reason']}")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    finally:
        # Clean up
        agent.close()


if __name__ == "__main__":
    main()
