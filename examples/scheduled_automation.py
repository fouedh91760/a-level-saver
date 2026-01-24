"""
Example: Scheduled automation script.

This script is designed to be run on a schedule (e.g., via cron) to:
- Process new tickets automatically
- Update stale opportunities
- Generate reports

You can run this script every hour, or customize the schedule as needed.
"""
import logging
from datetime import datetime
from src.orchestrator import ZohoAutomationOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Run scheduled automation tasks."""
    logger.info("=" * 80)
    logger.info(f"Starting scheduled automation run at {datetime.now()}")
    logger.info("=" * 80)

    orchestrator = ZohoAutomationOrchestrator()

    try:
        # Configuration - adjust these settings
        CONFIG = {
            # Ticket processing
            "process_tickets": True,
            "ticket_status": "Open",
            "ticket_limit": 20,
            "auto_respond_tickets": True,    # Set to True to auto-respond
            "auto_update_tickets": True,     # Set to True to auto-update status

            # Opportunity management
            "update_opportunities": True,
            "days_stale": 7,
            "auto_update_deals": True,       # Set to True to auto-update deals
            "auto_add_notes": True,          # Set to True to add notes

            # Reporting
            "generate_report": True
        }

        results = {}

        # Process tickets
        if CONFIG["process_tickets"]:
            logger.info("Processing tickets...")
            ticket_result = orchestrator.batch_process_tickets(
                status=CONFIG["ticket_status"],
                limit=CONFIG["ticket_limit"],
                auto_respond=CONFIG["auto_respond_tickets"],
                auto_update=CONFIG["auto_update_tickets"]
            )
            results["tickets"] = ticket_result

            logger.info(f"Processed {ticket_result['total_processed']} tickets")
            logger.info(f"  - Successful: {ticket_result['successful']}")
            logger.info(f"  - Failed: {ticket_result['failed']}")
            logger.info(f"  - Escalations: {ticket_result['escalations_needed']}")

        # Update opportunities
        if CONFIG["update_opportunities"]:
            logger.info("Updating stale opportunities...")
            opp_result = orchestrator.find_and_update_stale_opportunities(
                days_stale=CONFIG["days_stale"],
                auto_update=CONFIG["auto_update_deals"],
                auto_add_note=CONFIG["auto_add_notes"]
            )
            results["opportunities"] = opp_result

            logger.info(f"Analyzed {opp_result['total_analyzed']} opportunities")
            logger.info(f"  - High Priority: {opp_result['high_priority']}")
            logger.info(f"  - Medium Priority: {opp_result['medium_priority']}")
            logger.info(f"  - Low Priority: {opp_result['low_priority']}")

        # Generate report
        if CONFIG["generate_report"]:
            generate_report(results)

        logger.info("=" * 80)
        logger.info(f"Scheduled automation completed successfully at {datetime.now()}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error during scheduled automation: {e}", exc_info=True)
        raise

    finally:
        orchestrator.close()


def generate_report(results: dict):
    """Generate a summary report of the automation run."""
    logger.info("\n" + "=" * 80)
    logger.info("AUTOMATION SUMMARY REPORT")
    logger.info("=" * 80)

    if "tickets" in results:
        ticket_data = results["tickets"]
        logger.info("\nTICKET PROCESSING:")
        logger.info(f"  Total Tickets: {ticket_data['total_processed']}")
        logger.info(f"  Success Rate: {ticket_data['successful'] / max(ticket_data['total_processed'], 1) * 100:.1f}%")

        # Find tickets that need escalation
        escalations = [
            r for r in ticket_data.get('results', [])
            if 'error' not in r and r.get('agent_analysis', {}).get('should_escalate', False)
        ]

        if escalations:
            logger.info(f"\n  ⚠ ESCALATIONS NEEDED ({len(escalations)}):")
            for ticket in escalations[:5]:  # Show top 5
                logger.info(f"    - Ticket {ticket['ticket_number']}: "
                           f"{ticket['agent_analysis']['escalation_reason']}")

    if "opportunities" in results:
        opp_data = results["opportunities"]
        logger.info("\nOPPORTUNITY MANAGEMENT:")
        logger.info(f"  Total Opportunities: {opp_data['total_analyzed']}")
        logger.info(f"  High Priority: {opp_data['high_priority']}")
        logger.info(f"  Medium Priority: {opp_data['medium_priority']}")

        # Show top priority opportunities
        top_opps = opp_data.get('opportunities', [])[:3]
        if top_opps:
            logger.info(f"\n  🎯 TOP PRIORITY OPPORTUNITIES:")
            for opp in top_opps:
                logger.info(f"    - {opp['deal_name']} (Score: {opp['priority_score']}/10)")
                logger.info(f"      Reason: {opp['reason']}")

    logger.info("\n" + "=" * 80)


if __name__ == "__main__":
    main()
