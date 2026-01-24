"""
Business rules for ticket-deal automation.

IMPORTANT: Customize these rules for your business!

See business_rules.example.py for detailed examples and documentation.

Modify the methods below to match your:
- Sales processes
- Deal stages
- Customer segmentation
- Automation preferences
"""
from typing import Dict, Any, Optional


class BusinessRules:
    """Your custom business rules. Modify these methods!"""

    @staticmethod
    def should_create_deal_for_ticket(ticket: Dict[str, Any]) -> bool:
        """
        Should we create a deal for this ticket?

        CUSTOMIZE THIS METHOD!

        Default: Only create deals for Sales department tickets
        """
        # Example rule: Create deals only for sales-related tickets
        department = ticket.get("departmentName", "")
        return department == "Sales"

    @staticmethod
    def get_deal_data_from_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        What data should the deal have?

        CUSTOMIZE THIS METHOD!
        """
        contact = ticket.get("contact", {})

        return {
            "Deal_Name": f"Deal - {contact.get('name', 'Unknown')} - A-Level Selection",
            "Stage": "Qualification",
            "Amount": 500,
            "Lead_Source": "Support Ticket",
            "Description": f"Created from ticket: {ticket.get('subject', '')}",
            "Type": "New Business",
        }

    @staticmethod
    def should_link_ticket_to_deal(
        ticket: Dict[str, Any],
        deal: Dict[str, Any]
    ) -> bool:
        """
        Should we link this ticket to this deal?

        CUSTOMIZE THIS METHOD!

        Default: Don't link to closed deals
        """
        stage = deal.get("Stage", "")
        return stage not in ["Closed Won", "Closed Lost"]

    @staticmethod
    def get_preferred_linking_strategies() -> list:
        """
        Which strategies to use and in what order?

        CUSTOMIZE THIS LIST!
        """
        return [
            "custom_field",
            "contact_email",
            "contact_phone",
            "account",
        ]

    @staticmethod
    def should_auto_process_ticket(ticket: Dict[str, Any]) -> bool:
        """
        Should this ticket be auto-processed or need manual review?

        CUSTOMIZE THIS METHOD!

        Default: Auto-process all tickets
        """
        # Don't auto-process urgent tickets
        if ticket.get("priority") == "Urgent":
            return False

        return True


# For detailed examples, see business_rules.example.py
