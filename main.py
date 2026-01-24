"""
Main entry point for the Zoho automation system.

This script provides a simple CLI interface to run common automation tasks.
"""
import argparse
import logging
from src.utils.logging_config import setup_logging
from src.agents import DeskTicketAgent, CRMOpportunityAgent
from src.orchestrator import ZohoAutomationOrchestrator


def process_ticket(ticket_id: str, auto_respond: bool = False, auto_update: bool = False):
    """Process a single ticket."""
    agent = DeskTicketAgent()
    try:
        result = agent.process({
            "ticket_id": ticket_id,
            "auto_respond": auto_respond,
            "auto_update": auto_update
        })

        print(f"\n=== Ticket {result['ticket_number']} ===")
        analysis = result['agent_analysis']
        print(f"Priority: {analysis['priority']}")
        print(f"Status: {analysis['suggested_status']}")
        print(f"Escalate: {analysis['should_escalate']}")
        print(f"\nSuggested Response:\n{analysis['suggested_response']}")

        if result['actions_taken']:
            print(f"\nActions taken:")
            for action in result['actions_taken']:
                print(f"  ✓ {action}")

    finally:
        agent.close()


def process_deal(deal_id: str, auto_update: bool = False, auto_add_note: bool = False):
    """Process a single deal/opportunity."""
    agent = CRMOpportunityAgent()
    try:
        result = agent.process({
            "deal_id": deal_id,
            "auto_update": auto_update,
            "auto_add_note": auto_add_note
        })

        print(f"\n=== Deal: {result['deal_name']} ===")
        analysis = result['agent_analysis']
        print(f"Priority Score: {analysis['priority_score']}/10")
        print(f"Suggested Stage: {analysis['suggested_stage']}")
        print(f"Probability: {analysis['suggested_probability']}%")
        print(f"\nNext Steps:\n{analysis['suggested_next_steps']}")
        print(f"\nEngagement:\n{analysis['engagement_recommendation']}")

        if analysis['requires_attention']:
            print(f"\n⚠️  ATTENTION: {analysis['attention_reason']}")

        if result['actions_taken']:
            print(f"\nActions taken:")
            for action in result['actions_taken']:
                print(f"  ✓ {action}")

    finally:
        agent.close()


def batch_tickets(status: str = "Open", limit: int = 10, auto_respond: bool = False, auto_update: bool = False):
    """Process multiple tickets in batch."""
    orchestrator = ZohoAutomationOrchestrator()
    try:
        result = orchestrator.batch_process_tickets(
            status=status,
            limit=limit,
            auto_respond=auto_respond,
            auto_update=auto_update
        )

        print(f"\n=== Batch Processing Results ===")
        print(f"Total: {result['total_processed']}")
        print(f"Successful: {result['successful']}")
        print(f"Failed: {result['failed']}")
        print(f"Escalations: {result['escalations_needed']}")

    finally:
        orchestrator.close()


def full_cycle(auto_actions: bool = False):
    """Run a full automation cycle."""
    orchestrator = ZohoAutomationOrchestrator()
    try:
        result = orchestrator.run_full_automation_cycle(
            process_tickets=True,
            update_opportunities=True,
            ticket_status="Open",
            ticket_limit=10,
            auto_actions=auto_actions
        )

        print("\n=== Full Automation Cycle ===")
        if result['tickets_processed']:
            tp = result['tickets_processed']
            print(f"\nTickets: {tp['total_processed']} processed, {tp['escalations_needed']} escalations")

        if result['opportunities_updated']:
            op = result['opportunities_updated']
            print(f"\nOpportunities: {op['total_analyzed']} analyzed")
            print(f"  High Priority: {op['high_priority']}")
            print(f"  Medium Priority: {op['medium_priority']}")
            print(f"  Low Priority: {op['low_priority']}")

    finally:
        orchestrator.close()


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Zoho Desk & CRM Automation")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Ticket command
    ticket_parser = subparsers.add_parser("ticket", help="Process a ticket")
    ticket_parser.add_argument("ticket_id", help="Ticket ID to process")
    ticket_parser.add_argument("--auto-respond", action="store_true", help="Auto-respond to ticket")
    ticket_parser.add_argument("--auto-update", action="store_true", help="Auto-update ticket status")

    # Deal command
    deal_parser = subparsers.add_parser("deal", help="Process a deal/opportunity")
    deal_parser.add_argument("deal_id", help="Deal ID to process")
    deal_parser.add_argument("--auto-update", action="store_true", help="Auto-update deal fields")
    deal_parser.add_argument("--auto-add-note", action="store_true", help="Auto-add analysis note")

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch process tickets")
    batch_parser.add_argument("--status", default="Open", help="Ticket status filter")
    batch_parser.add_argument("--limit", type=int, default=10, help="Max tickets to process")
    batch_parser.add_argument("--auto-respond", action="store_true", help="Auto-respond to tickets")
    batch_parser.add_argument("--auto-update", action="store_true", help="Auto-update ticket statuses")

    # Cycle command
    cycle_parser = subparsers.add_parser("cycle", help="Run full automation cycle")
    cycle_parser.add_argument("--auto-actions", action="store_true", help="Enable auto-actions")

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    if args.command == "ticket":
        process_ticket(args.ticket_id, args.auto_respond, args.auto_update)
    elif args.command == "deal":
        process_deal(args.deal_id, args.auto_update, args.auto_add_note)
    elif args.command == "batch":
        batch_tickets(args.status, args.limit, args.auto_respond, args.auto_update)
    elif args.command == "cycle":
        full_cycle(args.auto_actions)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
