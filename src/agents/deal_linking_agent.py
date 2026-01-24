"""Agent for automatically linking tickets to deals via custom fields."""
import logging
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent
from src.ticket_deal_linker import TicketDealLinker
from src.zoho_client import ZohoDeskClient

logger = logging.getLogger(__name__)

try:
    from business_rules import BusinessRules
    logger.info("Loaded custom business rules")
except ImportError:
    logger.warning("business_rules.py not found or has errors. Using default permissive rules.")

    # Fallback to permissive default rules
    class BusinessRules:
        @staticmethod
        def should_create_deal_for_ticket(ticket):
            return False  # Conservative default: don't auto-create

        @staticmethod
        def should_link_ticket_to_deal(ticket, deal):
            return True  # Allow linking

        @staticmethod
        def get_preferred_linking_strategies():
            return ["custom_field", "contact_email", "contact_phone", "account"]

        @staticmethod
        def should_auto_process_ticket(ticket):
            return True


class DealLinkingAgent(BaseAgent):
    """
    Agent specialized in maintaining ticket-deal links via custom fields.

    This agent:
    1. Finds tickets without deal_id
    2. Searches for the corresponding deal
    3. Updates the ticket's cf_deal_id field
    4. Optionally creates deals if none exist
    5. Reports on linking success/failures
    """

    SYSTEM_PROMPT = """You are an AI assistant specialized in data quality and relationship management
for a customer support and CRM system.

Your role is to:
1. Analyze tickets and their associated deals
2. Determine if a ticket-deal link is appropriate
3. Identify potential matches between tickets and deals
4. Flag cases where no clear match exists
5. Suggest when a new deal should be created

When analyzing a ticket-deal pairing, consider:
- Is this the correct deal for this ticket?
- Are there multiple possible deals? Which is most relevant?
- Should this ticket be linked to a deal at all?
- If no deal exists, should one be created?

Always respond in JSON format with the following structure:
{
    "should_link": true|false,
    "confidence_score": 1-100,
    "reasoning": "Why this link is appropriate or not",
    "alternative_deals": ["deal_id1", "deal_id2"],
    "create_new_deal": true|false,
    "suggested_deal_name": "Name for new deal if create_new_deal is true",
    "notes": "Any additional observations"
}
"""

    def __init__(self):
        super().__init__(
            name="DealLinkingAgent",
            system_prompt=self.SYSTEM_PROMPT
        )
        self.linker = TicketDealLinker()
        self.desk_client = ZohoDeskClient()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a ticket to link it to a deal.

        Args:
            data: Dictionary containing:
                - ticket_id: The Zoho Desk ticket ID
                - force_update: Update even if cf_deal_id already exists (default: False)
                - create_deal_if_missing: Create a deal if none found (default: False)
                - use_ai_validation: Use AI to validate the link (default: False)
                - strategies: List of strategies to use (default: all)

        Returns:
            Dictionary with linking results
        """
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            raise ValueError("ticket_id is required")

        force_update = data.get("force_update", False)
        create_deal_if_missing = data.get("create_deal_if_missing", False)
        use_ai_validation = data.get("use_ai_validation", False)
        strategies = data.get("strategies")

        # If no strategies specified, use business rules
        if not strategies:
            strategies = BusinessRules.get_preferred_linking_strategies()
            logger.info(f"Using business rules strategies: {strategies}")

        logger.info(f"Processing ticket {ticket_id} for deal linking")

        # Get ticket details
        try:
            ticket = self.desk_client.get_ticket(ticket_id)
        except Exception as e:
            logger.error(f"Could not fetch ticket {ticket_id}: {e}")
            return {
                "success": False,
                "error": f"Could not fetch ticket: {e}",
                "ticket_id": ticket_id
            }

        # Check if already linked
        existing_deal_id = ticket.get("cf_deal_id") or ticket.get("cf_zoho_crm_deal_id")
        if existing_deal_id and not force_update:
            logger.info(f"Ticket {ticket_id} already linked to deal {existing_deal_id}")
            return {
                "success": True,
                "already_linked": True,
                "ticket_id": ticket_id,
                "deal_id": existing_deal_id,
                "action": "skipped"
            }

        # Find the deal
        logger.info(f"Searching for deal for ticket {ticket_id}")
        deal = self.linker.find_deal_for_ticket(ticket_id, strategies=strategies)

        if not deal:
            logger.warning(f"No deal found for ticket {ticket_id}")

            # Check business rules if we should create a deal
            if create_deal_if_missing:
                should_create = BusinessRules.should_create_deal_for_ticket(ticket)

                if should_create:
                    logger.info(f"Business rules allow deal creation for ticket {ticket_id}")
                    # TODO: Implement deal creation using BusinessRules.get_deal_data_from_ticket(ticket)
                    logger.info("Deal creation not yet implemented")
                    return {
                        "success": False,
                        "deal_found": False,
                        "ticket_id": ticket_id,
                        "action": "no_deal_found",
                        "create_deal_needed": True,
                        "business_rule_allows_creation": True
                    }
                else:
                    logger.info(f"Business rules do NOT allow deal creation for ticket {ticket_id}")
                    return {
                        "success": False,
                        "deal_found": False,
                        "ticket_id": ticket_id,
                        "action": "no_deal_found",
                        "business_rule_allows_creation": False
                    }
            else:
                return {
                    "success": False,
                    "deal_found": False,
                    "ticket_id": ticket_id,
                    "action": "no_deal_found"
                }

        deal_id = deal.get("id")
        logger.info(f"Found deal {deal_id} for ticket {ticket_id}")

        # Business rules validation
        should_link = BusinessRules.should_link_ticket_to_deal(ticket, deal)
        if not should_link:
            logger.warning(f"Business rules do NOT allow linking ticket {ticket_id} to deal {deal_id}")
            return {
                "success": False,
                "deal_found": True,
                "deal_id": deal_id,
                "ticket_id": ticket_id,
                "action": "business_rule_rejected",
                "reason": "Business rules validation failed"
            }

        # AI validation if requested
        if use_ai_validation:
            validation = self._validate_link_with_ai(ticket, deal)
            if not validation.get("should_link", True):
                logger.warning(f"AI recommends not linking: {validation['reasoning']}")
                return {
                    "success": False,
                    "deal_found": True,
                    "deal_id": deal_id,
                    "ticket_id": ticket_id,
                    "action": "ai_rejected",
                    "ai_validation": validation
                }

        # Update the ticket with deal_id
        try:
            self.desk_client.update_ticket(ticket_id, {
                "cf_deal_id": deal_id
            })
            logger.info(f"Updated ticket {ticket_id} with deal_id {deal_id}")

            # Also create reverse link in CRM
            try:
                self.linker.link_ticket_to_deal_bidirectional(
                    ticket_id, deal_id
                )
                bidirectional = True
            except Exception as e:
                logger.warning(f"Could not create bidirectional link: {e}")
                bidirectional = False

            return {
                "success": True,
                "deal_found": True,
                "ticket_id": ticket_id,
                "deal_id": deal_id,
                "deal_name": deal.get("Deal_Name"),
                "action": "linked",
                "bidirectional_link": bidirectional
            }

        except Exception as e:
            logger.error(f"Failed to update ticket {ticket_id}: {e}")
            return {
                "success": False,
                "deal_found": True,
                "deal_id": deal_id,
                "ticket_id": ticket_id,
                "action": "update_failed",
                "error": str(e)
            }

    def _validate_link_with_ai(
        self,
        ticket: Dict[str, Any],
        deal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use AI to validate if a ticket should be linked to a deal.

        Args:
            ticket: Ticket data
            deal: Deal data

        Returns:
            AI validation result
        """
        context = {
            "Ticket ID": ticket.get("ticketNumber"),
            "Ticket Subject": ticket.get("subject"),
            "Ticket Description": ticket.get("description"),
            "Ticket Contact": ticket.get("contact", {}).get("name"),
            "Ticket Contact Email": ticket.get("contact", {}).get("email"),
            "Deal ID": deal.get("id"),
            "Deal Name": deal.get("Deal_Name"),
            "Deal Stage": deal.get("Stage"),
            "Deal Amount": deal.get("Amount"),
            "Deal Contact": deal.get("Contact_Name")
        }

        prompt = """Analyze this ticket and deal to determine if they should be linked.

Consider:
- Do they relate to the same customer/contact?
- Is the ticket relevant to this deal?
- Is this the most appropriate deal for this ticket?
- Should a different deal be used instead?

Respond with a JSON object as specified in the system prompt."""

        response = self.ask(prompt, context=context, reset_history=True)

        try:
            # Extract JSON from response
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            else:
                json_str = response.strip()

            import json
            return json.loads(json_str)

        except Exception as e:
            logger.error(f"Failed to parse AI validation response: {e}")
            return {
                "should_link": True,  # Default to linking
                "confidence_score": 50,
                "reasoning": "AI validation failed, defaulting to link"
            }

    def process_unlinked_tickets(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        create_deal_if_missing: bool = False
    ) -> Dict[str, Any]:
        """
        Find and process all tickets without deal_id.

        This is the main batch processing method.

        Args:
            status: Filter by ticket status (None = all)
            limit: Maximum tickets to process
            create_deal_if_missing: Create deals for tickets without matches

        Returns:
            Summary of batch processing
        """
        logger.info(f"Processing unlinked tickets (status={status}, limit={limit})")

        # Get tickets
        try:
            tickets_response = self.desk_client.list_tickets(
                status=status,
                limit=limit
            )
            all_tickets = tickets_response.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch tickets: {e}")
            return {
                "success": False,
                "error": f"Failed to fetch tickets: {e}"
            }

        # Filter tickets without deal_id
        unlinked_tickets = []
        for ticket in all_tickets:
            if not ticket.get("cf_deal_id") and not ticket.get("cf_zoho_crm_deal_id"):
                unlinked_tickets.append(ticket)

        logger.info(f"Found {len(unlinked_tickets)} unlinked tickets out of {len(all_tickets)} total")

        # Process each unlinked ticket
        results = []
        for ticket in unlinked_tickets:
            try:
                result = self.process({
                    "ticket_id": ticket["id"],
                    "create_deal_if_missing": create_deal_if_missing
                })
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process ticket {ticket.get('id')}: {e}")
                results.append({
                    "success": False,
                    "ticket_id": ticket.get("id"),
                    "error": str(e)
                })

        # Summarize results
        summary = {
            "total_tickets": len(all_tickets),
            "unlinked_tickets": len(unlinked_tickets),
            "processed": len(results),
            "successful_links": len([r for r in results if r.get("success") and r.get("action") == "linked"]),
            "already_linked": len([r for r in results if r.get("already_linked")]),
            "no_deal_found": len([r for r in results if r.get("action") == "no_deal_found"]),
            "failed": len([r for r in results if not r.get("success")]),
            "results": results
        }

        logger.info(f"Batch processing complete: {summary['successful_links']} linked, "
                   f"{summary['no_deal_found']} no deal found, {summary['failed']} failed")

        return summary

    def validate_existing_links(
        self,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Validate existing ticket-deal links for accuracy.

        Useful for data quality checks.

        Args:
            limit: Maximum tickets to validate

        Returns:
            Validation report
        """
        logger.info(f"Validating existing ticket-deal links (limit={limit})")

        # Get tickets with deal_id
        try:
            all_tickets = self.desk_client.list_tickets(limit=limit).get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch tickets: {e}")
            return {
                "success": False,
                "error": str(e)
            }

        linked_tickets = [
            t for t in all_tickets
            if t.get("cf_deal_id") or t.get("cf_zoho_crm_deal_id")
        ]

        logger.info(f"Found {len(linked_tickets)} linked tickets")

        validation_results = []
        for ticket in linked_tickets:
            ticket_id = ticket["id"]
            existing_deal_id = ticket.get("cf_deal_id") or ticket.get("cf_zoho_crm_deal_id")

            # Find what deal SHOULD be linked
            suggested_deal = self.linker.find_deal_for_ticket(ticket_id)

            if not suggested_deal:
                validation_results.append({
                    "ticket_id": ticket_id,
                    "existing_deal_id": existing_deal_id,
                    "suggested_deal_id": None,
                    "status": "deal_not_found",
                    "action_needed": "investigate"
                })
            elif suggested_deal.get("id") == existing_deal_id:
                validation_results.append({
                    "ticket_id": ticket_id,
                    "existing_deal_id": existing_deal_id,
                    "suggested_deal_id": suggested_deal.get("id"),
                    "status": "correct",
                    "action_needed": None
                })
            else:
                validation_results.append({
                    "ticket_id": ticket_id,
                    "existing_deal_id": existing_deal_id,
                    "suggested_deal_id": suggested_deal.get("id"),
                    "status": "mismatch",
                    "action_needed": "update_link"
                })

        summary = {
            "total_validated": len(validation_results),
            "correct": len([r for r in validation_results if r["status"] == "correct"]),
            "mismatches": len([r for r in validation_results if r["status"] == "mismatch"]),
            "deal_not_found": len([r for r in validation_results if r["status"] == "deal_not_found"]),
            "results": validation_results
        }

        logger.info(f"Validation complete: {summary['correct']} correct, "
                   f"{summary['mismatches']} mismatches, "
                   f"{summary['deal_not_found']} deals not found")

        return summary

    def close(self):
        """Clean up resources."""
        self.linker.close()
        self.desk_client.close()
