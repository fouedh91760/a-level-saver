"""Agent for automatically linking tickets to deals via custom fields."""
import logging
import re
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent
from src.ticket_deal_linker import TicketDealLinker
from src.zoho_client import ZohoDeskClient, ZohoCRMClient

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
        self.crm_client = None  # Lazy initialization to avoid import issues

    def _get_crm_client(self) -> ZohoCRMClient:
        """Lazy initialization of CRM client."""
        if self.crm_client is None:
            self.crm_client = ZohoCRMClient()
        return self.crm_client

    def _extract_email_from_thread(self, thread: Dict[str, Any]) -> Optional[str]:
        """
        Extract email address from a thread.

        Checks multiple fields: fromEmailAddress, from, author email, etc.
        """
        # Try fromEmailAddress first (most reliable)
        from_email = thread.get("fromEmailAddress")
        if from_email:
            # Extract email from "Name <email@domain.com>" format
            email_match = re.search(r'<([^>]+)>', from_email)
            if email_match:
                return email_match.group(1).lower().strip()
            # Or if it's just the email
            if '@' in from_email:
                return from_email.lower().strip()

        # Try "from" field
        from_field = thread.get("from")
        if from_field:
            # Extract email from "Name <email@domain.com>" format
            email_match = re.search(r'<([^>]+)>', from_field)
            if email_match:
                return email_match.group(1).lower().strip()
            # Or if it's just the email
            if '@' in from_field:
                return from_field.lower().strip()

        # Try author field
        author = thread.get("author")
        if isinstance(author, dict) and author.get("email"):
            return author["email"].lower().strip()

        return None

    def _extract_email_from_threads(self, threads: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract email from the LAST thread in the list (most recent).

        Threads are usually ordered chronologically, so the last one is the most recent.
        We prioritize customer emails over agent responses.
        """
        if not threads:
            return None

        # Try to get email from last thread (most recent)
        for thread in reversed(threads):
            # Skip internal notes and agent responses
            channel = thread.get("channel", "").lower()
            direction = thread.get("direction", "").lower()

            # Prioritize customer emails (incoming)
            if direction == "in" or channel in ["email", "web", "phone"]:
                email = self._extract_email_from_thread(thread)
                if email:
                    logger.info(f"Extracted email from thread: {email}")
                    return email

        # Fallback: try any thread
        for thread in reversed(threads):
            email = self._extract_email_from_thread(thread)
            if email:
                logger.info(f"Extracted email from thread (fallback): {email}")
                return email

        return None

    def _search_contacts_by_email(self, email: str) -> List[Dict[str, Any]]:
        """
        Search for ALL contacts in CRM with the given email.

        Returns:
            List of contact records
        """
        crm_client = self._get_crm_client()

        try:
            # Search contacts by email
            criteria = f"(Email:equals:{email})"
            url = f"{crm_client._make_request.__self__.__class__.__module__}"  # This is wrong, let me fix

            # Use the CRM API to search contacts
            from config import settings
            url = f"{settings.zoho_crm_api_url}/Contacts/search"
            params = {
                "criteria": criteria,
                "per_page": 200
            }

            response = crm_client._make_request("GET", url, params=params)
            contacts = response.get("data", [])

            logger.info(f"Found {len(contacts)} contacts with email {email}")
            return contacts

        except Exception as e:
            logger.error(f"Failed to search contacts by email {email}: {e}")
            return []

    def _get_deals_for_contacts(self, contact_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get ALL deals associated with the given contact IDs.

        Args:
            contact_ids: List of contact IDs

        Returns:
            List of all deals for these contacts
        """
        if not contact_ids:
            return []

        crm_client = self._get_crm_client()
        all_deals = []

        try:
            # Search deals for each contact
            for contact_id in contact_ids:
                criteria = f"(Contact_Name:equals:{contact_id})"
                deals = crm_client.search_all_deals(criteria=criteria)
                all_deals.extend(deals)
                logger.info(f"Found {len(deals)} deals for contact {contact_id}")

            logger.info(f"Total deals found: {len(all_deals)}")
            return all_deals

        except Exception as e:
            logger.error(f"Failed to get deals for contacts: {e}")
            return []

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a ticket to link it to deals and determine department routing.

        NEW WORKFLOW (as per business requirements):
        1. Get email from THREAD (not ticket contact)
        2. Find ALL contacts in CRM with that email
        3. Get ALL deals for those contacts
        4. Use BusinessRules.determine_department_from_deals_and_ticket() to route
        5. Return department determination + deal info for dispatcher

        Args:
            data: Dictionary containing:
                - ticket_id: The Zoho Desk ticket ID

        Returns:
            Dictionary with:
                - success: bool
                - ticket_id: str
                - email_found: bool
                - email: str (if found)
                - contacts_found: int
                - deals_found: int
                - all_deals: List[Dict] - ALL deals for the contact(s)
                - selected_deal: Dict - The deal selected by routing logic (if any)
                - recommended_department: str - Department from business rules
                - routing_explanation: str - Why this department was selected
                - deal_id: str - ID of selected deal (for backward compatibility)
                - deal: Dict - Selected deal data (for backward compatibility)
        """
        ticket_id = data.get("ticket_id")
        if not ticket_id:
            raise ValueError("ticket_id is required")

        logger.info(f"Processing ticket {ticket_id} - NEW WORKFLOW: Thread email → Contacts → Deals → Routing")

        result = {
            "success": False,
            "ticket_id": ticket_id,
            "email_found": False,
            "email": None,
            "contacts_found": 0,
            "deals_found": 0,
            "all_deals": [],
            "selected_deal": None,
            "recommended_department": None,
            "routing_explanation": "",
            "deal_id": None,
            "deal": None,
            "deal_found": False
        }

        # Step 1: Get ticket details
        try:
            ticket = self.desk_client.get_ticket(ticket_id)
        except Exception as e:
            logger.error(f"Could not fetch ticket {ticket_id}: {e}")
            result["error"] = f"Could not fetch ticket: {e}"
            return result

        # Step 2: Get all threads with FULL content
        try:
            threads = self.desk_client.get_all_threads_with_full_content(ticket_id)
            logger.info(f"Retrieved {len(threads)} threads for ticket {ticket_id}")
        except Exception as e:
            logger.error(f"Could not fetch threads for ticket {ticket_id}: {e}")
            threads = []

        # Step 3: Extract email from threads (NOT from ticket contact)
        email = self._extract_email_from_threads(threads)
        if not email:
            logger.warning(f"No email found in threads for ticket {ticket_id}")
            # Fallback: try ticket contact email
            contact = ticket.get("contact", {})
            if contact and contact.get("email"):
                email = contact["email"].lower().strip()
                logger.info(f"Using fallback: ticket contact email {email}")

        if not email:
            logger.warning(f"No email found for ticket {ticket_id} (neither in threads nor contact)")
            result["routing_explanation"] = "No email found - cannot link to CRM deals"
            result["success"] = True  # Success but no deal found
            return result

        result["email_found"] = True
        result["email"] = email
        logger.info(f"Email extracted: {email}")

        # Step 4: Search ALL contacts with this email
        contacts = self._search_contacts_by_email(email)
        result["contacts_found"] = len(contacts)

        if not contacts:
            logger.info(f"No contacts found in CRM for email {email}")
            result["routing_explanation"] = f"No CRM contacts found for email {email}"
            result["success"] = True  # Success but no deal found
            return result

        contact_ids = [c.get("id") for c in contacts if c.get("id")]
        logger.info(f"Found {len(contact_ids)} contact(s) for email {email}")

        # Step 5: Get ALL deals for these contacts
        all_deals = self._get_deals_for_contacts(contact_ids)
        result["deals_found"] = len(all_deals)
        result["all_deals"] = all_deals

        if not all_deals:
            logger.info(f"No deals found for contacts with email {email}")
            result["routing_explanation"] = f"No CRM deals found for email {email}"
            result["success"] = True  # Success but no deal found
            return result

        # Step 6: Get last thread content for document detection
        last_thread_content = None
        if threads:
            last_thread = threads[-1]  # Most recent thread
            last_thread_content = last_thread.get("content") or last_thread.get("plainText") or ""

        # Step 7: Use BusinessRules to determine department and select deal
        logger.info(f"Calling BusinessRules.determine_department_from_deals_and_ticket with {len(all_deals)} deals")

        try:
            recommended_department = BusinessRules.determine_department_from_deals_and_ticket(
                all_deals=all_deals,
                ticket=ticket,
                last_thread_content=last_thread_content
            )

            result["recommended_department"] = recommended_department

            # ================================================================
            # NOUVELLE LOGIQUE DE SÉLECTION DE DEAL (v2)
            # Priorité aux deals ACTIFS (Evalbox avancé, examen proche)
            # Les prospects (EN ATTENTE) sont en dernière position
            # ================================================================
            selected_deal = None
            selection_method = None

            # Statuts Evalbox indiquant un candidat ACTIF (pas un prospect)
            ADVANCED_EVALBOX = {
                "Convoc CMA reçue", "VALIDE CMA", "Dossier Synchronisé",
                "Pret a payer", "Dossier crée", "Refusé CMA"
            }

            # PRIORITÉ 0 : Deals avec Evalbox avancé (candidat actif dans le process)
            active_deals = [
                d for d in all_deals
                if d.get("Evalbox") in ADVANCED_EVALBOX and d.get("Stage") == "GAGNÉ"
            ]
            if active_deals:
                # Prendre le plus récent par date de clôture
                selected_deal = sorted(active_deals, key=lambda d: d.get("Closing_Date", ""), reverse=True)[0]
                selection_method = f"Priority 0 - Evalbox avancé ({selected_deal.get('Evalbox')})"
                logger.info(f"🎯 Deal sélectionné par Evalbox avancé: {selected_deal.get('Deal_Name')} - {selected_deal.get('Evalbox')}")

            # PRIORITÉ 1 : Deals avec date d'examen dans les 60 prochains jours
            if not selected_deal:
                from datetime import datetime, timedelta
                today = datetime.now().date()
                future_limit = today + timedelta(days=60)

                deals_with_exam = []
                for d in all_deals:
                    if d.get("Stage") != "GAGNÉ":
                        continue
                    exam_date_raw = d.get("Date_examen_VTC")
                    if exam_date_raw:
                        try:
                            # Le champ peut être un ID ou une date string
                            if isinstance(exam_date_raw, str) and "-" in exam_date_raw:
                                exam_date = datetime.strptime(exam_date_raw[:10], "%Y-%m-%d").date()
                                if today <= exam_date <= future_limit:
                                    deals_with_exam.append((d, exam_date))
                        except (ValueError, TypeError):
                            pass

                if deals_with_exam:
                    # Prendre celui avec la date la plus proche
                    deals_with_exam.sort(key=lambda x: x[1])
                    selected_deal = deals_with_exam[0][0]
                    exam_date = deals_with_exam[0][1]
                    selection_method = f"Priority 1 - Examen proche ({exam_date.strftime('%d/%m/%Y')})"
                    logger.info(f"🎯 Deal sélectionné par date d'examen: {selected_deal.get('Deal_Name')} - examen le {exam_date}")

            # PRIORITÉ 2 : Deals 20€ GAGNÉ (candidats payés en cours de traitement)
            if not selected_deal:
                deals_20_won = [d for d in all_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]
                if deals_20_won:
                    selected_deal = sorted(deals_20_won, key=lambda d: d.get("Closing_Date", ""), reverse=True)[0]
                    selection_method = "Priority 2 - 20€ GAGNÉ (most recent)"

            # PRIORITÉ 3 : Autres deals GAGNÉ
            if not selected_deal:
                other_won = [d for d in all_deals if d.get("Amount") != 20 and d.get("Stage") == "GAGNÉ"]
                if other_won:
                    selected_deal = sorted(other_won, key=lambda d: d.get("Closing_Date", ""), reverse=True)[0]
                    selection_method = "Priority 3 - Other GAGNÉ"

            # PRIORITÉ 4 (BASSE) : Deals 20€ EN ATTENTE (prospects)
            if not selected_deal:
                deals_20_pending = [d for d in all_deals if d.get("Amount") == 20 and d.get("Stage") == "EN ATTENTE"]
                if deals_20_pending:
                    selected_deal = deals_20_pending[0]
                    selection_method = "Priority 4 - 20€ EN ATTENTE (prospect)"
                    logger.info(f"⚠️ Deal sélectionné est un PROSPECT (EN ATTENTE): {selected_deal.get('Deal_Name')}")

            # PRIORITÉ 5 : Autres EN ATTENTE
            if not selected_deal:
                other_pending = [d for d in all_deals if d.get("Stage") == "EN ATTENTE"]
                if other_pending:
                    selected_deal = other_pending[0]
                    selection_method = "Priority 5 - Other EN ATTENTE"

            # Mise à jour du résultat
            if selected_deal:
                result["selected_deal"] = selected_deal
                result["deal_id"] = selected_deal.get("id")
                result["deal"] = selected_deal
                result["deal_found"] = True
                result["routing_explanation"] = (
                    f"Department: {recommended_department} | "
                    f"Deal: {selected_deal.get('Deal_Name')} (€{selected_deal.get('Amount')}) | "
                    f"Stage: {selected_deal.get('Stage')} | Evalbox: {selected_deal.get('Evalbox', 'N/A')} | "
                    f"Method: {selection_method}"
                )
            else:
                result["routing_explanation"] = (
                    f"Department: {recommended_department} | "
                    f"Found {len(all_deals)} deal(s) but none match priority criteria | "
                    f"Method: Fallback to keywords or AI"
                )

            if not recommended_department:
                result["routing_explanation"] = (
                    f"No department determined by deals - will fallback to keywords | "
                    f"Found {len(all_deals)} deal(s) for email {email}"
                )

            logger.info(f"Routing result: {result['routing_explanation']}")

            # Step 8: Update ticket with deal URL in custom field (if deal was selected)
            if result.get("deal_id") and result.get("selected_deal"):
                try:
                    deal_name = result["selected_deal"].get("Deal_Name", "Opportunité")
                    self._update_ticket_with_deal_url(ticket_id, result["deal_id"], deal_name)
                    logger.info(f"Updated ticket {ticket_id} with deal URL")
                except Exception as e:
                    logger.warning(f"Could not update ticket with deal URL: {e}")

            result["success"] = True
            return result

        except Exception as e:
            logger.error(f"Error in BusinessRules routing logic: {e}")
            result["error"] = f"Routing logic error: {e}"
            result["routing_explanation"] = f"Error in routing logic: {e}"
            result["success"] = False
            return result

    def _update_ticket_with_deal_url(self, ticket_id: str, deal_id: str, deal_name: str = "Opportunité") -> None:
        """
        Update ticket's custom field with a clickable link to the deal.

        Args:
            ticket_id: Zoho Desk ticket ID
            deal_id: Zoho CRM deal ID
            deal_name: Deal name to display as link text (default: "Opportunité")
        """
        from config import settings

        # Construct deal URL
        # Format: https://crm.zoho.{datacenter}/crm/tab/Potentials/{deal_id}
        deal_url = f"https://crm.zoho.{settings.zoho_datacenter}/crm/tab/Potentials/{deal_id}"

        # Format: just the URL (Zoho Desk will make it clickable)
        field_value = deal_url

        # Update ticket with custom field in the correct format
        # Zoho Desk requires custom fields to be nested under "cf" key
        update_data = {
            "cf": {
                "cf_opportunite": field_value
            }
        }

        try:
            self.desk_client.update_ticket(ticket_id, update_data)
            logger.info(f"Updated ticket {ticket_id} custom field 'cf_opportunite' with deal URL: {deal_url}")
        except Exception as e:
            logger.error(f"Failed to update ticket {ticket_id} with deal URL: {e}")
            raise e

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
        if self.crm_client:
            self.crm_client.close()
