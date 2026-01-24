"""
Example: CRM opportunity management with the CRM agent.

This example shows how to:
1. Analyze an opportunity
2. Get AI recommendations for next steps
3. Update opportunity fields automatically
4. Find opportunities that need attention
"""
import logging
from src.agents import CRMOpportunityAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    # Initialize the CRM agent
    agent = CRMOpportunityAgent()

    try:
        # Example 1: Analyze an opportunity
        logger.info("Example 1: Analyzing opportunity")
        result = agent.process({
            "deal_id": "123456789",  # Replace with actual deal ID
            "auto_update": False,
            "auto_add_note": False
        })

        print("\n=== Opportunity Analysis ===")
        print(f"Deal Name: {result['deal_name']}")
        print(f"\nAgent Analysis:")
        analysis = result['agent_analysis']
        print(f"  - Current Assessment: {analysis['analysis']}")
        print(f"  - Suggested Stage: {analysis['suggested_stage']}")
        print(f"  - Suggested Probability: {analysis['suggested_probability']}%")
        print(f"  - Priority Score: {analysis['priority_score']}/10")
        print(f"\nRecommended Next Steps:")
        print(analysis['suggested_next_steps'])
        print(f"\nEngagement Recommendation:")
        print(analysis['engagement_recommendation'])

        if analysis['requires_attention']:
            print(f"\n⚠ ATTENTION NEEDED: {analysis['attention_reason']}")

        # Example 2: Update opportunity with AI recommendations
        logger.info("\nExample 2: Auto-updating opportunity")
        result = agent.process({
            "deal_id": "123456789",  # Replace with actual deal ID
            "auto_update": True,     # Apply suggested updates
            "auto_add_note": True    # Add analysis as a note
        })

        print("\n=== Actions Taken ===")
        for action in result['actions_taken']:
            print(f"  ✓ {action}")

        # Example 3: Find opportunities needing attention
        logger.info("\nExample 3: Finding opportunities that need attention")
        attention_needed = agent.find_opportunities_needing_attention(limit=10)

        print(f"\n=== Opportunities Needing Attention ({len(attention_needed)}) ===")
        for opp in attention_needed[:5]:  # Show top 5
            print(f"\n  • {opp['deal_name']} (Priority: {opp['priority_score']}/10)")
            print(f"    Reason: {opp['reason']}")

        # Example 4: Process opportunity with ticket context
        logger.info("\nExample 4: Processing opportunity with ticket context")

        # Simulated ticket analysis result
        ticket_analysis = {
            "original_ticket": {
                "subject": "Question about A-Level subject selection"
            },
            "agent_analysis": {
                "priority": "High",
                "analysis": "Student is actively engaged and seeking guidance",
                "should_escalate": False
            }
        }

        result = agent.process_with_ticket(
            deal_id="123456789",  # Replace with actual deal ID
            ticket_id="987654321",  # Replace with actual ticket ID
            ticket_analysis=ticket_analysis,
            auto_update=False,
            auto_add_note=False
        )

        print("\n=== Opportunity Analysis with Ticket Context ===")
        analysis = result['agent_analysis']
        print(f"Analysis considering customer interaction:")
        print(analysis['analysis'])
        print(f"\nRecommended engagement:")
        print(analysis['engagement_recommendation'])

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    finally:
        # Clean up
        agent.close()


if __name__ == "__main__":
    main()
