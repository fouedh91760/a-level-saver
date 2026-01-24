"""Agent for automating Zoho Desk ticket responses."""
import logging
import json
from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from src.zoho_client import ZohoDeskClient
from src.utils.text_utils import get_clean_thread_content

logger = logging.getLogger(__name__)


class DeskTicketAgent(BaseAgent):
    """Agent specialized in analyzing and responding to Zoho Desk tickets."""

    SYSTEM_PROMPT = """You are an AI assistant specialized in customer support for an A-Level subject selection service.

Your role is to:
1. Analyze support tickets from students and their families
2. Provide helpful, accurate, and empathetic responses
3. Suggest appropriate actions (close ticket, escalate, request more info, etc.)
4. Maintain a professional yet friendly tone

When analyzing a ticket, you should:
- Understand the student's question or concern
- Provide clear guidance on A-Level subject selection
- Reference relevant information about subject combinations, career paths, and university requirements
- Suggest next steps for the ticket (response, status update, assignment, etc.)

Always respond in JSON format with the following structure:
{
    "analysis": "Your analysis of the ticket",
    "suggested_response": "The response to send to the customer",
    "suggested_status": "Open|Pending|Resolved|Closed",
    "priority": "Low|Medium|High|Urgent",
    "tags": ["tag1", "tag2"],
    "internal_notes": "Notes for internal use",
    "should_escalate": true|false,
    "escalation_reason": "Reason for escalation if should_escalate is true"
}
"""

    def __init__(self):
        super().__init__(
            name="DeskTicketAgent",
            system_prompt=self.SYSTEM_PROMPT
        )
        self.desk_client = ZohoDeskClient()

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a support ticket and generate automated response.

        Args:
            data: Dictionary containing:
                - ticket_id: The Zoho Desk ticket ID
                - auto_respond: Whether to automatically post the response (default: False)
                - auto_update: Whether to automatically update ticket status (default: False)

        Returns:
            Dictionary with processing results and suggested actions
        """
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            raise ValueError("ticket_id is required")

        auto_respond = data.get("auto_respond", False)
        auto_update = data.get("auto_update", False)

        logger.info(f"Processing ticket {ticket_id}")

        # Fetch complete ticket context including all threads, conversations, and history
        complete_context = self.desk_client.get_ticket_complete_context(ticket_id)
        ticket = complete_context["ticket"]
        threads = complete_context["threads"]
        conversations = complete_context["conversations"]
        history = complete_context["history"]

        # Build comprehensive context for the agent
        context = {
            "Ticket ID": ticket.get("ticketNumber", ticket_id),
            "Subject": ticket.get("subject", "N/A"),
            "Description": ticket.get("description", "N/A"),
            "Status": ticket.get("status", "N/A"),
            "Priority": ticket.get("priority", "N/A"),
            "Contact": ticket.get("contact", {}).get("name", "N/A"),
            "Created Time": ticket.get("createdTime", "N/A"),
            "Modified Time": ticket.get("modifiedTime", "N/A"),
            "Department": ticket.get("departmentName", "N/A"),
            "Channel": ticket.get("channel", "N/A"),
        }

        # Add complete thread history (emails, replies)
        if threads:
            thread_history = []
            for idx, thread in enumerate(threads, 1):
                thread_info = {
                    "Number": idx,
                    "Direction": thread.get("direction", "N/A"),
                    "From": thread.get("from", {}).get("emailId", "N/A") if isinstance(thread.get("from"), dict) else thread.get("from", "N/A"),
                    "To": thread.get("to", "N/A"),
                    "Subject": thread.get("subject", "N/A"),
                    "Content": get_clean_thread_content(thread),  # Clean text (plainText or cleaned HTML)
                    "Created Time": thread.get("createdTime", "N/A"),
                    "Is Forward": thread.get("isForward", False),
                    "Is Reply": thread.get("isReply", False)
                }
                thread_history.append(thread_info)
            context["Complete Thread History"] = thread_history

        # Add conversation history
        if conversations:
            conv_history = []
            for idx, conv in enumerate(conversations, 1):
                conv_info = {
                    "Number": idx,
                    "Type": conv.get("type", "N/A"),
                    "Content": conv.get("content", "N/A"),
                    "Author": conv.get("author", {}).get("name", "N/A") if isinstance(conv.get("author"), dict) else conv.get("author", "N/A"),
                    "Created Time": conv.get("createdTime", "N/A"),
                    "Is Public": conv.get("isPublic", True)
                }
                conv_history.append(conv_info)
            context["Conversation History"] = conv_history

        # Add modification history
        if history:
            history_summary = []
            for idx, hist in enumerate(history[-10:], 1):  # Last 10 changes
                hist_info = {
                    "Action": hist.get("fieldName", "N/A"),
                    "Old Value": hist.get("oldValue", "N/A"),
                    "New Value": hist.get("newValue", "N/A"),
                    "Modified By": hist.get("actor", {}).get("name", "N/A") if isinstance(hist.get("actor"), dict) else hist.get("actor", "N/A"),
                    "Modified Time": hist.get("modifiedTime", "N/A")
                }
                history_summary.append(hist_info)
            context["Recent Modification History"] = history_summary

        # Get agent's analysis and response
        prompt = """Analyze this support ticket with its COMPLETE history and provide your recommendations.

You have access to:
- The full thread history with all emails and replies (NOT summaries)
- The complete conversation history
- The modification history

Please consider:
- The FULL context of all previous communications
- The evolution of the conversation and how the issue has been addressed so far
- Any patterns in the customer's interactions
- The nature of the student's question or concern
- Previous responses and whether the issue is resolved or ongoing
- The appropriate next response that would be helpful and accurate
- The suggested status and priority based on the complete history
- Whether this requires escalation to a human agent

IMPORTANT: Base your analysis on the COMPLETE content of all threads and conversations, not just summaries.

Respond ONLY with a valid JSON object matching the specified format."""

        response = self.ask(prompt, context=context, reset_history=True)

        # Parse the JSON response
        try:
            # Extract JSON from the response (in case it's wrapped in markdown)
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
            "ticket_id": ticket_id,
            "ticket_number": ticket.get("ticketNumber"),
            "original_ticket": ticket,
            "complete_context": complete_context,  # Include full context
            "agent_analysis": analysis,
            "actions_taken": []
        }

        # Auto-respond if requested
        if auto_respond and not analysis.get("should_escalate", False):
            try:
                comment_response = self.desk_client.add_ticket_comment(
                    ticket_id=ticket_id,
                    content=analysis["suggested_response"],
                    is_public=True
                )
                result["actions_taken"].append("Added public response to ticket")
                result["response_id"] = comment_response.get("id")
                logger.info(f"Added response to ticket {ticket_id}")
            except Exception as e:
                logger.error(f"Failed to add comment to ticket: {e}")
                result["actions_taken"].append(f"Failed to add response: {str(e)}")

        # Auto-update status if requested
        if auto_update and not analysis.get("should_escalate", False):
            try:
                update_data = {
                    "status": analysis["suggested_status"]
                }

                # Add internal note
                if analysis.get("internal_notes"):
                    internal_note_response = self.desk_client.add_ticket_comment(
                        ticket_id=ticket_id,
                        content=f"[AI Agent] {analysis['internal_notes']}",
                        is_public=False
                    )
                    result["actions_taken"].append("Added internal note")

                self.desk_client.update_ticket(ticket_id, update_data)
                result["actions_taken"].append(f"Updated status to {analysis['suggested_status']}")
                logger.info(f"Updated ticket {ticket_id} status to {analysis['suggested_status']}")
            except Exception as e:
                logger.error(f"Failed to update ticket: {e}")
                result["actions_taken"].append(f"Failed to update status: {str(e)}")

        return result

    def analyze_ticket_batch(
        self,
        status: Optional[str] = "Open",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Analyze a batch of tickets.

        Args:
            status: Filter tickets by status
            limit: Maximum number of tickets to process

        Returns:
            List of analysis results
        """
        logger.info(f"Analyzing batch of tickets (status={status}, limit={limit})")

        tickets_response = self.desk_client.list_tickets(status=status, limit=limit)
        tickets = tickets_response.get("data", [])

        results = []
        for ticket in tickets:
            try:
                result = self.process({
                    "ticket_id": ticket["id"],
                    "auto_respond": False,
                    "auto_update": False
                })
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process ticket {ticket.get('id')}: {e}")
                results.append({
                    "ticket_id": ticket.get("id"),
                    "error": str(e)
                })

        return results

    def close(self):
        """Clean up resources."""
        self.desk_client.close()
