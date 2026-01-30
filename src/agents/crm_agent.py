"""Agent for automating Zoho CRM opportunity management."""
import logging
import json
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent
from src.zoho_client import ZohoCRMClient

logger = logging.getLogger(__name__)


class CRMOpportunityAgent(BaseAgent):
    """Agent specialized in managing and updating Zoho CRM opportunities."""

    SYSTEM_PROMPT = """You are an AI assistant specialized in managing sales opportunities for an A-Level subject selection service.

Your role is to:
1. Analyze opportunity data and customer interactions
2. Suggest appropriate updates to opportunity fields (stage, probability, next steps, etc.)
3. Recommend engagement strategies
4. Identify upsell or cross-sell opportunities
5. Flag opportunities that need attention or follow-up

When analyzing an opportunity, consider:
- The current stage and how long it's been there
- Customer engagement level and history
- Deal value and probability
- Any associated tickets or support interactions
- Time since last contact

Always respond in JSON format with the following structure:
{
    "analysis": "Your analysis of the opportunity",
    "suggested_stage": "Qualification|Needs Analysis|Value Proposition|Proposal|Negotiation|Closed Won|Closed Lost",
    "suggested_probability": 0-100,
    "suggested_next_steps": "Description of recommended next steps",
    "engagement_recommendation": "How to best engage with this prospect",
    "priority_score": 1-10,
    "update_fields": {
        "field_name": "new_value"
    },
    "add_note": "Note to add to the opportunity",
    "requires_attention": true|false,
    "attention_reason": "Why this opportunity needs attention"
}
"""

    def __init__(self, crm_client: Optional[ZohoCRMClient] = None):
        """
        Initialize CRMOpportunityAgent.

        Args:
            crm_client: Optional ZohoCRMClient instance (creates new one if None)
        """
        super().__init__(
            name="CRMOpportunityAgent",
            system_prompt=self.SYSTEM_PROMPT
        )
        self.crm_client = crm_client or ZohoCRMClient()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an opportunity and suggest updates.

        Args:
            data: Dictionary containing:
                - deal_id: The Zoho CRM deal/opportunity ID
                - ticket_context: Optional ticket information to consider
                - auto_update: Whether to automatically apply suggested updates (default: False)
                - auto_add_note: Whether to automatically add notes (default: False)

        Returns:
            Dictionary with processing results and suggested actions
        """
        deal_id = data.get("deal_id")
        if not deal_id:
            raise ValueError("deal_id is required")

        ticket_context = data.get("ticket_context")
        auto_update = data.get("auto_update", False)
        auto_add_note = data.get("auto_add_note", False)

        logger.info(f"Processing opportunity {deal_id}")

        # Fetch deal details
        deal = self.crm_client.get_deal(deal_id)

        if not deal:
            raise ValueError(f"Deal {deal_id} not found")

        # Prepare context for the agent
        context = {
            "Deal Name": deal.get("Deal_Name", "N/A"),
            "Stage": deal.get("Stage", "N/A"),
            "Amount": deal.get("Amount", "N/A"),
            "Probability": deal.get("Probability", "N/A"),
            "Close Date": deal.get("Closing_Date", "N/A"),
            "Lead Source": deal.get("Lead_Source", "N/A"),
            "Contact": deal.get("Contact_Name", {}).get("name", "N/A") if isinstance(deal.get("Contact_Name"), dict) else deal.get("Contact_Name", "N/A"),
            "Description": deal.get("Description", "N/A"),
            "Next Step": deal.get("Next_Step", "N/A"),
            "Created Time": deal.get("Created_Time", "N/A"),
            "Modified Time": deal.get("Modified_Time", "N/A")
        }

        # Add ticket context if provided
        if ticket_context:
            context["Related Ticket"] = ticket_context

        # Get agent's analysis and recommendations
        prompt = """Analyze this sales opportunity and provide your recommendations.

Please consider:
- The current stage and progression of the deal
- Time factors (how long in current stage, proximity to close date)
- Engagement level and customer interactions
- Appropriate next steps to move the deal forward
- Any factors that might affect deal success

If ticket context is provided, consider how the support interaction should influence the opportunity management.

Respond ONLY with a valid JSON object matching the specified format."""

        response = self.ask(prompt, context=context, reset_history=True)

        # Parse the JSON response
        try:
            # Extract JSON from the response
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

            analysis = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent response as JSON: {e}")
            logger.error(f"Response was: {response}")
            raise

        result = {
            "deal_id": deal_id,
            "deal_name": deal.get("Deal_Name"),
            "original_deal": deal,
            "agent_analysis": analysis,
            "actions_taken": []
        }

        # Auto-update if requested
        if auto_update:
            try:
                update_data = {}

                # Add suggested stage if different
                if analysis.get("suggested_stage") and analysis["suggested_stage"] != deal.get("Stage"):
                    update_data["Stage"] = analysis["suggested_stage"]

                # Add suggested probability if different
                if analysis.get("suggested_probability") is not None:
                    update_data["Probability"] = analysis["suggested_probability"]

                # Add suggested next steps
                if analysis.get("suggested_next_steps"):
                    update_data["Next_Step"] = analysis["suggested_next_steps"]

                # Add any custom field updates
                if analysis.get("update_fields"):
                    update_data.update(analysis["update_fields"])

                if update_data:
                    self.crm_client.update_deal(deal_id, update_data)
                    result["actions_taken"].append(f"Updated deal fields: {list(update_data.keys())}")
                    logger.info(f"Updated opportunity {deal_id}")

            except Exception as e:
                logger.error(f"Failed to update opportunity: {e}")
                result["actions_taken"].append(f"Failed to update: {str(e)}")

        # Auto-add note if requested
        if auto_add_note and analysis.get("add_note"):
            try:
                note_title = f"AI Analysis - Priority {analysis.get('priority_score', 'N/A')}"
                self.crm_client.add_deal_note(
                    deal_id=deal_id,
                    note_title=note_title,
                    note_content=analysis["add_note"]
                )
                result["actions_taken"].append("Added analysis note to deal")
                logger.info(f"Added note to opportunity {deal_id}")
            except Exception as e:
                logger.error(f"Failed to add note: {e}")
                result["actions_taken"].append(f"Failed to add note: {str(e)}")

        return result

    def process_with_ticket(
        self,
        deal_id: str,
        ticket_id: str,
        ticket_analysis: Dict[str, Any],
        auto_update: bool = False,
        auto_add_note: bool = False
    ) -> Dict[str, Any]:
        """
        Process an opportunity in the context of a support ticket.

        Args:
            deal_id: The CRM deal ID
            ticket_id: The related Desk ticket ID
            ticket_analysis: The analysis result from DeskTicketAgent
            auto_update: Whether to automatically apply updates
            auto_add_note: Whether to automatically add notes

        Returns:
            Dictionary with processing results
        """
        # Prepare ticket context
        ticket_context = {
            "ticket_id": ticket_id,
            "ticket_subject": ticket_analysis.get("original_ticket", {}).get("subject"),
            "ticket_priority": ticket_analysis.get("agent_analysis", {}).get("priority"),
            "customer_sentiment": ticket_analysis.get("agent_analysis", {}).get("analysis"),
            "escalated": ticket_analysis.get("agent_analysis", {}).get("should_escalate", False)
        }

        return self.process({
            "deal_id": deal_id,
            "ticket_context": ticket_context,
            "auto_update": auto_update,
            "auto_add_note": auto_add_note
        })

    def find_opportunities_needing_attention(
        self,
        criteria: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find opportunities that need attention.

        Args:
            criteria: Search criteria (default: open deals)
            limit: Maximum number of deals to analyze

        Returns:
            List of opportunities that require attention
        """
        if criteria is None:
            criteria = "(Stage:equals:Qualification) or (Stage:equals:Needs Analysis) or (Stage:equals:Value Proposition)"

        logger.info(f"Searching for opportunities needing attention")

        search_response = self.crm_client.search_deals(criteria=criteria, per_page=limit)
        deals = search_response.get("data", [])

        attention_needed = []

        for deal in deals:
            try:
                result = self.process({
                    "deal_id": deal["id"],
                    "auto_update": False,
                    "auto_add_note": False
                })

                # Check if opportunity needs attention
                analysis = result.get("agent_analysis", {})
                if analysis.get("requires_attention", False):
                    attention_needed.append({
                        "deal_id": deal["id"],
                        "deal_name": deal.get("Deal_Name"),
                        "priority_score": analysis.get("priority_score", 0),
                        "reason": analysis.get("attention_reason"),
                        "full_analysis": result
                    })

            except Exception as e:
                logger.error(f"Failed to process deal {deal.get('id')}: {e}")

        # Sort by priority score (descending)
        attention_needed.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

        return attention_needed

    def close(self):
        """Clean up resources."""
        self.crm_client.close()
