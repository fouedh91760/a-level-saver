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
    def get_deal_search_criteria_for_department(
        department: str,
        contact_email: str,
        ticket: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get custom search criteria for specific departments.

        This allows department-specific logic for finding deals.

        Args:
            department: Department name
            contact_email: Contact email from ticket
            ticket: Full ticket data

        Returns:
            List of search criteria dictionaries in priority order, or None for default behavior.
            Each dict has:
            - criteria: Zoho CRM search query
            - description: What this searches for
            - max_results: How many to return

        Example return:
        [
            {"criteria": "(Stage:equals:Closed Won)", "description": "Won deals", "max_results": 1},
            {"criteria": "(Stage:equals:Pending)", "description": "Pending deals", "max_results": 1}
        ]
        """
        # DOC department: Specific Uber deal logic
        if department == "DOC":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Amount:equals:20)and(Stage:equals:Closed Won))",
                    "description": "Uber €20 deals - WON",
                    "max_results": 1,
                    "sort_by": "Modified_Time",  # Most recent
                    "sort_order": "desc"
                },
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Amount:equals:20)and(Stage:equals:Pending))",
                    "description": "Uber €20 deals - PENDING",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                },
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Amount:equals:20)and(Stage:equals:Closed Lost))",
                    "description": "Uber €20 deals - LOST",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                }
            ]

        # SALES department: Example of different logic
        elif department == "Sales":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Stage:not_equals:Closed Lost)and(Stage:not_equals:Closed Won))",
                    "description": "Open sales deals",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                }
            ]

        # SUPPORT department: Example
        elif department == "Support":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Type:equals:Renewal))",
                    "description": "Renewal deals",
                    "max_results": 1,
                    "sort_by": "Closing_Date",
                    "sort_order": "asc"
                }
            ]

        # Default: Return None to use standard strategies
        return None

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
