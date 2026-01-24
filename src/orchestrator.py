"""Orchestrator for coordinating multiple agents in automated workflows."""
import logging
from typing import Dict, Any, List, Optional
from src.agents import DeskTicketAgent, CRMOpportunityAgent
from src.zoho_client import ZohoDeskClient, ZohoCRMClient

logger = logging.getLogger(__name__)


class ZohoAutomationOrchestrator:
    """
    Orchestrates automated workflows between Zoho Desk and Zoho CRM.

    This class coordinates multiple agents to handle complex automation scenarios
    such as:
    - Processing tickets and updating related opportunities
    - Batch processing of tickets with CRM updates
    - Finding and addressing opportunities that need attention
    """

    def __init__(self):
        self.desk_agent = DeskTicketAgent()
        self.crm_agent = CRMOpportunityAgent()
        self.desk_client = ZohoDeskClient()
        self.crm_client = ZohoCRMClient()

    def process_ticket_with_crm_update(
        self,
        ticket_id: str,
        deal_id: str,
        auto_respond: bool = False,
        auto_update_ticket: bool = False,
        auto_update_deal: bool = False,
        auto_add_note: bool = False
    ) -> Dict[str, Any]:
        """
        Process a support ticket and update the related CRM opportunity.

        This is a common workflow where a customer interaction (ticket) should
        influence the sales opportunity status.

        Args:
            ticket_id: Zoho Desk ticket ID
            deal_id: Zoho CRM deal ID
            auto_respond: Auto-respond to the ticket
            auto_update_ticket: Auto-update ticket status
            auto_update_deal: Auto-update deal fields
            auto_add_note: Auto-add notes to the deal

        Returns:
            Combined results from both agents
        """
        logger.info(f"Processing ticket {ticket_id} with CRM update to deal {deal_id}")

        try:
            # Step 1: Process the ticket
            ticket_result = self.desk_agent.process({
                "ticket_id": ticket_id,
                "auto_respond": auto_respond,
                "auto_update": auto_update_ticket
            })

            # Step 2: Update the CRM opportunity based on ticket context
            crm_result = self.crm_agent.process_with_ticket(
                deal_id=deal_id,
                ticket_id=ticket_id,
                ticket_analysis=ticket_result,
                auto_update=auto_update_deal,
                auto_add_note=auto_add_note
            )

            return {
                "success": True,
                "ticket_result": ticket_result,
                "crm_result": crm_result,
                "workflow": "ticket_with_crm_update"
            }

        except Exception as e:
            logger.error(f"Error in ticket-CRM workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "workflow": "ticket_with_crm_update"
            }

    def batch_process_tickets(
        self,
        status: Optional[str] = "Open",
        limit: int = 10,
        auto_respond: bool = False,
        auto_update: bool = False
    ) -> Dict[str, Any]:
        """
        Process multiple tickets in batch.

        Args:
            status: Filter tickets by status
            limit: Maximum number of tickets to process
            auto_respond: Auto-respond to tickets
            auto_update: Auto-update ticket statuses

        Returns:
            Summary of batch processing results
        """
        logger.info(f"Starting batch ticket processing (status={status}, limit={limit})")

        results = self.desk_agent.analyze_ticket_batch(status=status, limit=limit)

        summary = {
            "total_processed": len(results),
            "successful": len([r for r in results if "error" not in r]),
            "failed": len([r for r in results if "error" in r]),
            "escalations_needed": len([
                r for r in results
                if "error" not in r and r.get("agent_analysis", {}).get("should_escalate", False)
            ]),
            "results": results
        }

        # If auto-actions are enabled, process them
        if auto_respond or auto_update:
            for result in results:
                if "error" not in result and not result.get("agent_analysis", {}).get("should_escalate", False):
                    try:
                        self.desk_agent.process({
                            "ticket_id": result["ticket_id"],
                            "auto_respond": auto_respond,
                            "auto_update": auto_update
                        })
                    except Exception as e:
                        logger.error(f"Failed auto-action for ticket {result['ticket_id']}: {e}")

        return summary

    def find_and_update_stale_opportunities(
        self,
        days_stale: int = 14,
        auto_update: bool = False,
        auto_add_note: bool = False
    ) -> Dict[str, Any]:
        """
        Find opportunities that haven't been updated recently and analyze them.

        Args:
            days_stale: Number of days without update to consider stale
            auto_update: Auto-update opportunity fields
            auto_add_note: Auto-add analysis notes

        Returns:
            Summary of stale opportunities and actions taken
        """
        logger.info(f"Finding stale opportunities (>{days_stale} days)")

        # Search for opportunities needing attention
        attention_needed = self.crm_agent.find_opportunities_needing_attention()

        summary = {
            "total_analyzed": len(attention_needed),
            "high_priority": len([a for a in attention_needed if a.get("priority_score", 0) >= 8]),
            "medium_priority": len([a for a in attention_needed if 5 <= a.get("priority_score", 0) < 8]),
            "low_priority": len([a for a in attention_needed if a.get("priority_score", 0) < 5]),
            "opportunities": attention_needed
        }

        # If auto-actions are enabled, process them
        if auto_update or auto_add_note:
            for opportunity in attention_needed:
                try:
                    self.crm_agent.process({
                        "deal_id": opportunity["deal_id"],
                        "auto_update": auto_update,
                        "auto_add_note": auto_add_note
                    })
                except Exception as e:
                    logger.error(f"Failed auto-action for deal {opportunity['deal_id']}: {e}")

        return summary

    def link_ticket_to_deal(
        self,
        ticket_id: str,
        contact_email: str,
        auto_create_deal: bool = False
    ) -> Optional[str]:
        """
        Find or create a deal associated with a ticket's contact.

        Args:
            ticket_id: The ticket ID
            contact_email: Contact email to search for in CRM
            auto_create_deal: Whether to create a deal if none exists

        Returns:
            Deal ID if found or created, None otherwise
        """
        logger.info(f"Linking ticket {ticket_id} to deal for contact {contact_email}")

        try:
            # Search for deals associated with this contact
            search_criteria = f"(Contact_Name:equals:{contact_email})"
            search_result = self.crm_client.search_deals(criteria=search_criteria, per_page=1)

            deals = search_result.get("data", [])

            if deals:
                deal_id = deals[0]["id"]
                logger.info(f"Found existing deal {deal_id} for contact {contact_email}")
                return deal_id

            elif auto_create_deal:
                # TODO: Implement deal creation logic
                logger.info("Auto-create deal is not yet implemented")
                return None

            else:
                logger.info(f"No deal found for contact {contact_email}")
                return None

        except Exception as e:
            logger.error(f"Error linking ticket to deal: {e}")
            return None

    def run_full_automation_cycle(
        self,
        process_tickets: bool = True,
        update_opportunities: bool = True,
        ticket_status: str = "Open",
        ticket_limit: int = 10,
        auto_actions: bool = False
    ) -> Dict[str, Any]:
        """
        Run a complete automation cycle across both Desk and CRM.

        This is useful for scheduled automation runs.

        Args:
            process_tickets: Whether to process tickets
            update_opportunities: Whether to update opportunities
            ticket_status: Status filter for tickets
            ticket_limit: Max tickets to process
            auto_actions: Whether to auto-execute suggested actions

        Returns:
            Summary of the full automation cycle
        """
        logger.info("Starting full automation cycle")

        results = {
            "timestamp": None,
            "tickets_processed": None,
            "opportunities_updated": None
        }

        # Process tickets
        if process_tickets:
            ticket_results = self.batch_process_tickets(
                status=ticket_status,
                limit=ticket_limit,
                auto_respond=auto_actions,
                auto_update=auto_actions
            )
            results["tickets_processed"] = ticket_results

        # Update opportunities
        if update_opportunities:
            opportunity_results = self.find_and_update_stale_opportunities(
                auto_update=auto_actions,
                auto_add_note=auto_actions
            )
            results["opportunities_updated"] = opportunity_results

        logger.info("Full automation cycle completed")
        return results

    def close(self):
        """Clean up all resources."""
        self.desk_agent.close()
        self.crm_agent.close()
        self.desk_client.close()
        self.crm_client.close()
