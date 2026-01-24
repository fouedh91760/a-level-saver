"""
Business rules configuration for ticket-deal linking and deal creation.

Copy this file to business_rules.py and customize it for your needs.
"""
from typing import Dict, Any, Optional


class BusinessRules:
    """
    Define your business rules for ticket-deal automation.

    Customize these methods to match your business processes.
    """

    # ==========================================================================
    # DEAL CREATION RULES
    # ==========================================================================

    @staticmethod
    def should_create_deal_for_ticket(ticket: Dict[str, Any]) -> bool:
        """
        Determine if a deal should be created for a ticket.

        Args:
            ticket: The ticket data from Zoho Desk

        Returns:
            True if a deal should be created, False otherwise

        Example rules:
        - Only create deals for sales-related tickets
        - Don't create deals for technical support
        - Create deals only from certain channels (email, web form)
        - Create deals only if contact doesn't have an existing open deal
        """
        # Example 1: Only create deals for tickets in "Sales" department
        department = ticket.get("departmentName", "")
        if department == "Sales":
            return True

        # Example 2: Create deals from web form submissions
        channel = ticket.get("channel", "")
        if channel == "WEB":
            return True

        # Example 3: Check ticket subject for sales keywords
        subject = ticket.get("subject", "").lower()
        sales_keywords = ["pricing", "quote", "purchase", "buy", "trial", "demo"]
        if any(keyword in subject for keyword in sales_keywords):
            return True

        # Example 4: Check custom fields
        # If ticket has "Interested in Service" = Yes
        if ticket.get("cf_interested_in_service") == "Yes":
            return True

        # Default: Don't create deals
        return False

    @staticmethod
    def get_deal_data_from_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract deal data from a ticket when creating a new deal.

        Args:
            ticket: The ticket data

        Returns:
            Dictionary with CRM deal fields

        Common fields:
        - Deal_Name: Name of the deal
        - Amount: Deal value
        - Stage: Initial stage
        - Closing_Date: Expected close date
        - Description: Deal description
        - Lead_Source: Where it came from
        - Type: Deal type (New Business, Renewal, etc.)
        """
        contact = ticket.get("contact", {})
        subject = ticket.get("subject", "")

        deal_data = {
            # Required fields
            "Deal_Name": f"Deal - {contact.get('name', 'Unknown')} - A-Level Selection",

            # Stage (customize based on your sales stages)
            "Stage": "Qualification",  # Or: "Lead", "Prospect", etc.

            # Amount (you might want to set a default or calculate based on ticket)
            "Amount": 500,  # Default value in your currency

            # Lead source
            "Lead_Source": "Support Ticket",

            # Description from ticket
            "Description": f"Created from ticket: {subject}\n\nOriginal request: {ticket.get('description', '')}",

            # Type
            "Type": "New Business",

            # Closing date (e.g., 30 days from now)
            # "Closing_Date": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),

            # Priority based on ticket priority
            "Priority": ticket.get("priority", "Medium"),

            # Custom fields based on your CRM
            # "Product_Interest": "A-Level Guidance",
            # "Service_Type": "Individual Consultation",
        }

        # Customize based on ticket department
        department = ticket.get("departmentName", "")
        if department == "Premium Support":
            deal_data["Amount"] = 1000
            deal_data["Stage"] = "Proposal"

        # Customize based on ticket custom fields
        if ticket.get("cf_service_tier") == "Premium":
            deal_data["Amount"] = 2000
            deal_data["Type"] = "Upsell"

        return deal_data

    @staticmethod
    def get_contact_data_from_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract contact data for CRM from a ticket.

        This is used when creating a deal to ensure the contact exists in CRM.

        Args:
            ticket: The ticket data

        Returns:
            Dictionary with CRM contact fields
        """
        contact = ticket.get("contact", {})

        return {
            "First_Name": contact.get("firstName", ""),
            "Last_Name": contact.get("lastName", contact.get("name", "Unknown")),
            "Email": contact.get("email", ""),
            "Phone": contact.get("phone", ""),
            "Mobile": contact.get("mobile", ""),
            # Add any custom fields your CRM needs
        }

    # ==========================================================================
    # LINKING RULES
    # ==========================================================================

    @staticmethod
    def should_link_ticket_to_deal(
        ticket: Dict[str, Any],
        deal: Dict[str, Any]
    ) -> bool:
        """
        Determine if a ticket should be linked to a specific deal.

        This is used for validation when a deal is found.

        Args:
            ticket: The ticket data
            deal: The deal data from CRM

        Returns:
            True if the link is appropriate, False otherwise

        Example rules:
        - Don't link to closed/lost deals
        - Don't link technical support tickets to sales deals
        - Don't link if contact email doesn't match
        """
        # Rule 1: Don't link to closed deals
        stage = deal.get("Stage", "")
        if stage in ["Closed Won", "Closed Lost"]:
            return False

        # Rule 2: Check if contacts match
        ticket_email = ticket.get("contact", {}).get("email", "").lower()
        deal_contact = deal.get("Contact_Name", {})
        if isinstance(deal_contact, dict):
            deal_email = deal_contact.get("email", "").lower()
        else:
            deal_email = ""

        if ticket_email and deal_email and ticket_email != deal_email:
            return False

        # Rule 3: Check ticket type vs deal type
        ticket_dept = ticket.get("departmentName", "")
        if ticket_dept == "Technical Support":
            # Technical support tickets shouldn't link to new business deals
            if deal.get("Type") == "New Business":
                return False

        # Default: Allow linking
        return True

    @staticmethod
    def get_preferred_linking_strategies() -> list:
        """
        Define the order of strategies to use for finding deals.

        Returns:
            List of strategy names in preferred order

        Available strategies:
        - "custom_field": Check if ticket already has deal_id
        - "contact_email": Search by contact email
        - "contact_phone": Search by phone
        - "account": Search by organization
        - "recent_deal": Get most recent deal
        """
        # Customize this based on your data quality
        return [
            "custom_field",      # Always check this first
            "contact_email",     # Most reliable
            "contact_phone",     # Good fallback
            "account",           # For B2B scenarios
            # "recent_deal",     # Uncomment if you want this fallback
        ]

    # ==========================================================================
    # DEAL UPDATE RULES
    # ==========================================================================

    @staticmethod
    def get_deal_updates_from_ticket(
        ticket: Dict[str, Any],
        ticket_analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Determine what updates should be made to a deal based on a ticket.

        Args:
            ticket: The ticket data
            ticket_analysis: AI analysis of the ticket

        Returns:
            Dictionary of CRM fields to update, or None if no updates needed

        Example rules:
        - High priority tickets → increase deal probability
        - Positive tickets → advance stage
        - Complaints → flag deal for review
        """
        updates = {}

        # Rule 1: Update based on ticket priority
        ticket_priority = ticket.get("priority", "")
        if ticket_priority == "High" or ticket_priority == "Urgent":
            updates["Priority"] = "High"

        # Rule 2: Update based on AI analysis
        if ticket_analysis:
            ai_priority = ticket_analysis.get("priority", "")

            # Customer is very engaged
            if "engaged" in ticket_analysis.get("analysis", "").lower():
                updates["Customer_Engagement"] = "High"

            # Customer has concerns
            if ticket_analysis.get("should_escalate"):
                updates["Deal_Status"] = "At Risk"
                updates["Next_Step"] = "Address customer concerns urgently"

        # Rule 3: Track ticket count
        # You might want to increment a custom field
        # updates["Support_Tickets_Count"] = existing_count + 1

        return updates if updates else None

    # ==========================================================================
    # AUTOMATION RULES
    # ==========================================================================

    @staticmethod
    def should_auto_process_ticket(ticket: Dict[str, Any]) -> bool:
        """
        Determine if a ticket should be automatically processed.

        Args:
            ticket: The ticket data

        Returns:
            True if automation should run, False if manual review needed

        Example rules:
        - Auto-process simple inquiries
        - Manual review for high-value customers
        - Manual review for complex issues
        """
        # Don't auto-process VIP customers
        if ticket.get("cf_customer_tier") == "VIP":
            return False

        # Don't auto-process escalated tickets
        if ticket.get("priority") == "Urgent":
            return False

        # Don't auto-process complaints
        subject = ticket.get("subject", "").lower()
        if "complaint" in subject or "refund" in subject:
            return False

        # Auto-process everything else
        return True

    @staticmethod
    def get_batch_processing_schedule() -> Dict[str, Any]:
        """
        Define when and how batch processing should run.

        Returns:
            Configuration for batch processing
        """
        return {
            # How often to run (in minutes)
            "frequency_minutes": 60,

            # What ticket statuses to process
            "ticket_statuses": ["Open", "Pending"],

            # Maximum tickets per batch
            "batch_size": 50,

            # Whether to create deals automatically
            "auto_create_deals": False,  # Set to True to enable

            # Whether to link tickets automatically
            "auto_link_tickets": True,

            # Hours when automation should run (24h format)
            "active_hours": {
                "start": 8,  # 8 AM
                "end": 20    # 8 PM
            }
        }


# ==========================================================================
# VALIDATION HELPERS
# ==========================================================================

def validate_business_rules():
    """
    Validate that your business rules are properly configured.

    Run this to test your configuration.
    """
    print("Validating business rules configuration...")

    rules = BusinessRules()

    # Test sample ticket
    sample_ticket = {
        "id": "123",
        "subject": "Interested in A-Level guidance",
        "departmentName": "Sales",
        "channel": "EMAIL",
        "priority": "Medium",
        "contact": {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+33612345678"
        }
    }

    # Test deal creation rules
    should_create = rules.should_create_deal_for_ticket(sample_ticket)
    print(f"✓ Should create deal: {should_create}")

    if should_create:
        deal_data = rules.get_deal_data_from_ticket(sample_ticket)
        print(f"✓ Deal data: {deal_data}")

    # Test linking strategies
    strategies = rules.get_preferred_linking_strategies()
    print(f"✓ Linking strategies: {strategies}")

    # Test automation
    should_auto = rules.should_auto_process_ticket(sample_ticket)
    print(f"✓ Should auto-process: {should_auto}")

    print("\n✅ Business rules validation complete!")


if __name__ == "__main__":
    validate_business_rules()
