"""Agent for automatically linking tickets to deals via custom fields."""
import logging
import re
from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent
from src.ticket_deal_linker import TicketDealLinker
from src.zoho_client import ZohoDeskClient, ZohoCRMClient

logger = logging.getLogger(__name__)

# Emails système à ignorer lors de l'extraction de l'email candidat
SYSTEM_EMAILS_TO_IGNORE = [
    'contact@evalbox.com',
    'noreply@evalbox.com',
    'doc@cab-formations.fr',
    'contact@cab-formations.fr',
    'admin@cab-formations.fr',
]

# Domaines internes CAB - si l'expéditeur est de ce domaine, c'est peut-être un forward
INTERNAL_DOMAINS = [
    '@cab-formations.fr',
    '@formalogistics.fr',
]

# Patterns pour détecter un message transféré
FORWARD_PATTERNS = [
    r'---------- Forwarded message ---------',
    r'---------- Message transféré ---------',
    r'----- Forwarded Message -----',
    r'----- Message transféré -----',
    r'Begin forwarded message:',
    r'Début du message transféré :',
]

# Patterns pour extraire l'email de l'expéditeur original dans un forward
# Note: Les espaces autour de < > sont fréquents dans les forwards
FORWARD_FROM_PATTERNS = [
    r'De\s*:\s*[^<]*<\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\s*>',  # De : Nom < email@domain.com >
    r'From\s*:\s*[^<]*<\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\s*>',  # From : Nom < email@domain.com >
    r'De\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # De : email@domain.com
    r'From\s*:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # From : email@domain.com
    r'&lt;\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\s*&gt;',  # HTML encoded < email >
    r'&lt;[^>]*mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # &lt;<a href="mailto:email">
    r'href=["\']mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})["\']',  # href="mailto:email"
]

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


def _check_has_paid_formation_after_uber(all_deals: List[Dict], deals_20_won: List[Dict]) -> Dict[str, Any]:
    """
    Vérifie si le candidat a une formation payante (>20€) plus récente que son offre Uber 20€.

    Si oui, le candidat a souscrit une formation après avoir utilisé l'offre Uber,
    donc on doit traiter ses documents normalement (pas de blocage doublon).

    Args:
        all_deals: Tous les deals du candidat
        deals_20_won: Les deals 20€ GAGNÉ (doublons détectés)

    Returns:
        {
            'has_paid_formation': bool,  # True si formation payante plus récente
            'paid_formation_deal': dict or None,  # Le deal de la formation payante
            'override_duplicate': bool  # True si on doit ignorer le doublon
        }
    """
    result = {
        'has_paid_formation': False,
        'paid_formation_deal': None,
        'override_duplicate': False
    }

    if not deals_20_won:
        return result

    # Trouver la date du deal 20€ le plus récent
    most_recent_20 = max(deals_20_won, key=lambda d: d.get('Closing_Date', '') or '')
    date_20_recent = most_recent_20.get('Closing_Date', '')

    # Chercher un deal avec montant > 20€ et GAGNÉ, plus récent que le deal 20€
    deals_paid_formation = [
        d for d in all_deals
        if d.get('Stage') == 'GAGNÉ'
        and d.get('Amount') is not None
        and float(d.get('Amount', 0)) > 25  # Plus de 25€ pour éviter les variations de l'offre 20€
        and (d.get('Closing_Date', '') or '') > date_20_recent
    ]

    if deals_paid_formation:
        # Prendre le plus récent
        most_recent_paid = max(deals_paid_formation, key=lambda d: d.get('Closing_Date', '') or '')
        result['has_paid_formation'] = True
        result['paid_formation_deal'] = most_recent_paid
        result['override_duplicate'] = True
        logger.info(f"  ✅ FORMATION PAYANTE DÉTECTÉE après offre Uber:")
        logger.info(f"     → Deal: {most_recent_paid.get('Deal_Name')} (€{most_recent_paid.get('Amount')})")
        logger.info(f"     → Date: {most_recent_paid.get('Closing_Date')}")
        logger.info(f"     → Le doublon Uber sera ignoré, documents à traiter normalement")

    return result


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

    def __init__(
        self,
        desk_client: Optional[ZohoDeskClient] = None,
        crm_client: Optional[ZohoCRMClient] = None
    ):
        """
        Initialize DealLinkingAgent.

        Args:
            desk_client: Optional ZohoDeskClient instance (creates new one if None)
            crm_client: Optional ZohoCRMClient instance (lazy init if None)
        """
        super().__init__(
            name="DealLinkingAgent",
            system_prompt=self.SYSTEM_PROMPT
        )
        # Use injected clients or create new ones
        self.desk_client = desk_client or ZohoDeskClient()
        self._injected_crm_client = crm_client
        self.crm_client = crm_client  # May be None for lazy initialization
        # Create linker with the same clients to avoid duplication
        self.linker = TicketDealLinker(
            desk_client=self.desk_client,
            crm_client=crm_client
        )

    def _get_crm_client(self) -> ZohoCRMClient:
        """Lazy initialization of CRM client."""
        if self.crm_client is None:
            self.crm_client = self._injected_crm_client or ZohoCRMClient()
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

    def _is_internal_email(self, email: str) -> bool:
        """Check if an email belongs to an internal CAB domain."""
        if not email:
            return False
        email_lower = email.lower()
        return any(domain in email_lower for domain in INTERNAL_DOMAINS)

    def _is_forwarded_message(self, content: str) -> bool:
        """Check if the content contains a forwarded message pattern."""
        if not content:
            return False
        for pattern in FORWARD_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _extract_forwarded_email(self, content: str) -> Optional[str]:
        """
        Extract the original sender's email from a forwarded message.

        Looks for patterns like:
        - De : Nom <email@domain.com>
        - From : Nom <email@domain.com>
        """
        if not content:
            return None

        # First check if this is a forwarded message
        if not self._is_forwarded_message(content):
            return None

        # Try to extract email from forward header
        for pattern in FORWARD_FROM_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                email = match.group(1).lower().strip()
                # Validate it's not an internal email
                if not self._is_internal_email(email):
                    logger.info(f"📧 Extracted forwarded email: {email}")
                    return email

        return None

    def _extract_email_from_threads(self, threads: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract email from the LAST thread in the list (most recent).

        Threads are usually ordered chronologically, so the last one is the most recent.
        We prioritize customer emails over agent responses.

        Special handling: If the sender is an internal CAB employee who forwarded
        a customer email, extract the original customer's email from the forwarded content.
        """
        if not threads:
            return None

        # Try to get email from most recent thread first (threads are ordered oldest to newest)
        # So we iterate in reverse to get newest first
        for thread in threads:
            # Skip internal notes and agent responses
            channel = thread.get("channel", "").lower()
            direction = thread.get("direction", "").lower()

            # Prioritize customer emails (incoming)
            if direction == "in" or channel in ["email", "web", "phone"]:
                email = self._extract_email_from_thread(thread)
                if email:
                    # Ignorer les emails système (Evalbox, CAB Formations, etc.)
                    if email.lower() in [e.lower() for e in SYSTEM_EMAILS_TO_IGNORE]:
                        logger.info(f"Skipping system email: {email}")
                        continue

                    # Check if this is an internal employee forwarding a customer email
                    if self._is_internal_email(email):
                        content = thread.get("content") or thread.get("plainText") or ""
                        forwarded_email = self._extract_forwarded_email(content)
                        if forwarded_email:
                            logger.info(f"📧 Internal email {email} forwarded customer email from: {forwarded_email}")
                            return forwarded_email
                        else:
                            logger.info(f"⚠️ Internal email {email} but no forwarded customer found - skipping")
                            continue

                    logger.info(f"Extracted email from thread: {email}")
                    return email

        # Fallback: try any thread (but still skip system emails and check for forwards)
        for thread in threads:
            email = self._extract_email_from_thread(thread)
            if email:
                if email.lower() in [e.lower() for e in SYSTEM_EMAILS_TO_IGNORE]:
                    continue

                # Check if this is an internal employee forwarding a customer email
                if self._is_internal_email(email):
                    content = thread.get("content") or thread.get("plainText") or ""
                    forwarded_email = self._extract_forwarded_email(content)
                    if forwarded_email:
                        logger.info(f"📧 Internal email {email} forwarded customer email from: {forwarded_email} (fallback)")
                        return forwarded_email
                    else:
                        continue

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

    def _normalize_phone(self, phone: str) -> Optional[str]:
        """
        Normalize phone number for search.

        Removes spaces, dashes, dots, and country code prefix.
        Returns None if phone is invalid.
        """
        if not phone:
            return None

        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)

        # Remove leading country code (33 for France)
        if digits.startswith('33') and len(digits) > 10:
            digits = '0' + digits[2:]

        # French mobile numbers should be 10 digits starting with 0
        if len(digits) == 10 and digits.startswith('0'):
            return digits

        # Accept 9 digits (missing leading 0) - add it back
        if len(digits) == 9 and digits.startswith(('6', '7')):
            return '0' + digits

        return digits if len(digits) >= 9 else None

    def _extract_phone_from_ticket(self, ticket: Dict[str, Any], threads: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract phone number from ticket or threads.

        Priority:
        1. Ticket contact phone
        2. Ticket custom fields
        3. Thread content (regex search)

        Returns:
            Normalized phone number or None
        """
        # 1. From ticket contact
        contact = ticket.get("contact", {})
        if contact:
            phone = contact.get("phone") or contact.get("mobile")
            if phone:
                normalized = self._normalize_phone(phone)
                if normalized:
                    logger.info(f"  📱 Phone from ticket contact: {normalized}")
                    return normalized

        # 2. From ticket custom fields
        cf = ticket.get("cf", {})
        if cf:
            for field in ['cf_telephone', 'cf_phone', 'cf_mobile', 'cf_tel']:
                phone = cf.get(field)
                if phone:
                    normalized = self._normalize_phone(phone)
                    if normalized:
                        logger.info(f"  📱 Phone from ticket cf.{field}: {normalized}")
                        return normalized

        # 3. From threads - search for phone patterns in customer messages
        phone_pattern = re.compile(r'(?:(?:\+33|0033|33)|0)[67][\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}')

        for thread in reversed(threads):
            direction = thread.get("direction", "").lower()
            if direction == "in":  # Only customer messages
                content = thread.get("content") or thread.get("plainText") or ""
                # Strip HTML tags
                content_clean = re.sub(r'<[^>]+>', ' ', content)

                matches = phone_pattern.findall(content_clean)
                for match in matches:
                    normalized = self._normalize_phone(match)
                    if normalized:
                        logger.info(f"  📱 Phone from thread content: {normalized}")
                        return normalized

        return None

    def _search_contacts_by_phone(self, phone: str) -> List[Dict[str, Any]]:
        """
        Search for ALL contacts in CRM with the given phone number.

        Searches both Phone and Mobile fields.

        Args:
            phone: Normalized phone number (e.g., "0612345678")

        Returns:
            List of contact records
        """
        crm_client = self._get_crm_client()
        all_contacts = []

        try:
            from config import settings

            # Search variations of the phone number
            phone_variations = [phone]

            # Add version with spaces
            if len(phone) == 10:
                spaced = f"{phone[:2]} {phone[2:4]} {phone[4:6]} {phone[6:8]} {phone[8:10]}"
                phone_variations.append(spaced)

            # Add version with +33
            if phone.startswith('0'):
                intl = '+33' + phone[1:]
                phone_variations.append(intl)
                intl_spaced = '+33 ' + phone[1:2] + ' ' + phone[2:4] + ' ' + phone[4:6] + ' ' + phone[6:8] + ' ' + phone[8:10]
                phone_variations.append(intl_spaced)

            for phone_var in phone_variations:
                # Search by Phone field
                try:
                    criteria = f"(Phone:equals:{phone_var})"
                    url = f"{settings.zoho_crm_api_url}/Contacts/search"
                    params = {"criteria": criteria, "per_page": 200}
                    response = crm_client._make_request("GET", url, params=params)
                    contacts = response.get("data", [])
                    for c in contacts:
                        if c.get("id") not in [x.get("id") for x in all_contacts]:
                            all_contacts.append(c)
                except Exception:
                    pass

                # Search by Mobile field
                try:
                    criteria = f"(Mobile:equals:{phone_var})"
                    url = f"{settings.zoho_crm_api_url}/Contacts/search"
                    params = {"criteria": criteria, "per_page": 200}
                    response = crm_client._make_request("GET", url, params=params)
                    contacts = response.get("data", [])
                    for c in contacts:
                        if c.get("id") not in [x.get("id") for x in all_contacts]:
                            all_contacts.append(c)
                except Exception:
                    pass

            logger.info(f"Found {len(all_contacts)} contacts with phone {phone}")
            return all_contacts

        except Exception as e:
            logger.error(f"Failed to search contacts by phone {phone}: {e}")
            return []

    def _normalize_name_for_comparison(self, name: str) -> str:
        """
        Normalise un nom pour comparaison (supprime accents, met en minuscules).

        Args:
            name: Nom à normaliser

        Returns:
            Nom normalisé
        """
        import unicodedata
        if not name:
            return ""
        # Supprimer les accents
        normalized = unicodedata.normalize('NFD', name)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        # Mettre en minuscules et supprimer espaces multiples
        normalized = ' '.join(normalized.lower().split())
        return normalized

    def _search_duplicate_by_name_and_postal(
        self,
        candidate_name: str,
        postal_code: str,
        exclude_deal_ids: List[str] = None,
        candidate_email: str = None,
        candidate_phone: str = None
    ) -> Dict[str, Any]:
        """
        Recherche des doublons potentiels par nom + code postal avec évaluation de confiance.

        Cherche des deals 20€ GAGNÉ avec le même nom (normalisé) et code postal.
        Évalue la confiance du match en comparant email/téléphone.

        Args:
            candidate_name: Nom complet du candidat (ex: "Gaël Carole")
            postal_code: Code postal (ex: "93330")
            exclude_deal_ids: IDs de deals à exclure de la recherche
            candidate_email: Email du candidat actuel (pour comparaison)
            candidate_phone: Téléphone du candidat actuel (pour comparaison)

        Returns:
            {
                'duplicates': List[Dict] - Liste des deals 20€ GAGNÉ correspondants
                'confidence': str - 'HIGH_CONFIDENCE' ou 'NEEDS_CONFIRMATION'
                'match_details': Dict - Détails du match (email_match, phone_match)
                'duplicate_type': str - 'TRUE_DUPLICATE', 'RECOVERABLE_REFUS_CMA',
                                        'RECOVERABLE_NOT_PAID', ou None
            }
        """
        result = {
            'duplicates': [],
            'confidence': None,
            'match_details': {
                'email_match': False,
                'phone_match': False,
                'different_email': False,
                'different_phone': False
            },
            'duplicate_type': None
        }

        if not candidate_name or not postal_code:
            return result

        exclude_deal_ids = exclude_deal_ids or []
        crm_client = self._get_crm_client()

        try:
            from config import settings

            # Normaliser le nom pour comparaison
            normalized_candidate_name = self._normalize_name_for_comparison(candidate_name)
            logger.info(f"  🔍 Recherche doublon par nom+CP: '{candidate_name}' ({normalized_candidate_name}) + {postal_code}")

            # Extraire prénom et nom pour recherche
            name_parts = candidate_name.split()
            if len(name_parts) < 2:
                logger.info(f"  ⚠️ Nom incomplet, recherche par nom uniquement")
                search_term = name_parts[0] if name_parts else ""
            else:
                # Chercher par le nom de famille (généralement le dernier mot)
                search_term = name_parts[-1]

            if not search_term:
                return result

            # Rechercher les deals par nom
            url = f"{settings.zoho_crm_api_url}/Deals/search"
            params = {"word": search_term, "per_page": 100}

            response = crm_client._make_request("GET", url, params=params)
            all_deals = response.get("data", [])

            if not all_deals:
                logger.info(f"  📭 Aucun deal trouvé pour '{search_term}'")
                return result

            logger.info(f"  📋 {len(all_deals)} deals trouvés pour '{search_term}', filtrage...")

            # Normaliser les infos candidat pour comparaison
            candidate_email_norm = candidate_email.lower().strip() if candidate_email else None
            candidate_phone_norm = self._normalize_phone(candidate_phone) if candidate_phone else None

            # Filtrer: 20€ GAGNÉ + même code postal + nom similaire
            duplicate_deals = []
            has_email_match = False
            has_phone_match = False
            has_different_email = False
            has_different_phone = False

            for deal in all_deals:
                deal_id = deal.get('id')

                # Exclure les deals déjà connus
                if deal_id in exclude_deal_ids:
                    continue

                # Vérifier Stage et Amount
                stage = deal.get('Stage', '')
                amount = deal.get('Amount')
                if stage != 'GAGNÉ' or amount != 20:
                    continue

                # Vérifier code postal
                deal_postal = deal.get('Mailing_Zip', '')
                if str(deal_postal) != str(postal_code):
                    continue

                # Vérifier nom (normalisé)
                deal_name = deal.get('Deal_Name', '')
                contact_name = deal.get('Contact_Name', {})
                contact_id = None
                if isinstance(contact_name, dict):
                    contact_id = contact_name.get('id')
                    contact_name = contact_name.get('name', '')

                # Normaliser et comparer
                normalized_deal_name = self._normalize_name_for_comparison(deal_name)
                normalized_contact = self._normalize_name_for_comparison(contact_name)

                # Match si le nom normalisé du candidat est contenu dans le deal_name ou contact_name
                name_match = (
                    normalized_candidate_name in normalized_deal_name or
                    normalized_candidate_name in normalized_contact or
                    normalized_deal_name in normalized_candidate_name or
                    normalized_contact == normalized_candidate_name
                )

                if name_match:
                    logger.info(f"  ✅ MATCH: {deal_name} (CP: {deal_postal}, Stage: {stage})")

                    # Récupérer email/phone du contact du deal pour comparaison
                    deal_email = None
                    deal_phone = None

                    if contact_id:
                        try:
                            contact_data = crm_client.get_contact(contact_id)
                            if contact_data:
                                deal_email = contact_data.get('Email', '').lower().strip() if contact_data.get('Email') else None
                                deal_phone_raw = contact_data.get('Phone') or contact_data.get('Mobile')
                                deal_phone = self._normalize_phone(deal_phone_raw) if deal_phone_raw else None
                        except Exception as e:
                            logger.warning(f"  ⚠️ Erreur récupération contact {contact_id}: {e}")

                    # Comparer email/phone
                    if candidate_email_norm and deal_email:
                        if candidate_email_norm == deal_email:
                            has_email_match = True
                            logger.info(f"    📧 Email IDENTIQUE: {deal_email}")
                        else:
                            has_different_email = True
                            logger.info(f"    📧 Email DIFFÉRENT: candidat={candidate_email_norm}, deal={deal_email}")

                    if candidate_phone_norm and deal_phone:
                        if candidate_phone_norm == deal_phone:
                            has_phone_match = True
                            logger.info(f"    📱 Téléphone IDENTIQUE: {deal_phone}")
                        else:
                            has_different_phone = True
                            logger.info(f"    📱 Téléphone DIFFÉRENT: candidat={candidate_phone_norm}, deal={deal_phone}")

                    # Ajouter les infos de contact au deal pour référence
                    deal['_duplicate_contact_email'] = deal_email
                    deal['_duplicate_contact_phone'] = deal_phone
                    duplicate_deals.append(deal)

            result['duplicates'] = duplicate_deals
            result['match_details'] = {
                'email_match': has_email_match,
                'phone_match': has_phone_match,
                'different_email': has_different_email,
                'different_phone': has_different_phone
            }

            if duplicate_deals:
                logger.warning(f"  ⚠️ {len(duplicate_deals)} doublon(s) potentiel(s) trouvé(s) par nom+CP")

                # Déterminer la confiance
                if has_email_match or has_phone_match:
                    result['confidence'] = 'HIGH_CONFIDENCE'
                    logger.info(f"  🔒 CONFIANCE HAUTE: email ou téléphone identique")
                elif has_different_email and has_different_phone:
                    result['confidence'] = 'NEEDS_CONFIRMATION'
                    logger.info(f"  ❓ CONFIRMATION REQUISE: email ET téléphone différents")
                elif has_different_email or has_different_phone:
                    # Un seul est différent, l'autre peut être absent
                    result['confidence'] = 'NEEDS_CONFIRMATION'
                    logger.info(f"  ❓ CONFIRMATION REQUISE: données de contact différentes")
                else:
                    # Pas de données de contact pour comparer → demander confirmation
                    result['confidence'] = 'NEEDS_CONFIRMATION'
                    logger.info(f"  ❓ CONFIRMATION REQUISE: impossible de vérifier email/téléphone")

                # Classifier le type de doublon
                result['duplicate_type'] = self._classify_duplicate_type(duplicate_deals[0])
            else:
                logger.info(f"  📭 Aucun doublon trouvé par nom+CP")

            return result

        except Exception as e:
            logger.error(f"Erreur recherche doublon par nom+CP: {e}")
            return result

    def _has_examt3p_account(self, deal: Dict[str, Any]) -> bool:
        """
        Vérifie si un deal a un compte ExamT3P existant.

        Un compte ExamT3P existe si :
        - Evalbox = "Dossier Synchronisé" ou "Refusé CMA"
        - OU NUM_DOSSIER_EVALBOX n'est pas vide

        Args:
            deal: Le deal à vérifier

        Returns:
            True si compte ExamT3P existe
        """
        evalbox = deal.get('Evalbox', '')
        num_dossier = deal.get('NUM_DOSSIER_EVALBOX', '')

        # Statuts qui prouvent qu'un compte existe
        COMPTE_EXISTE_EVALBOX = ['Dossier Synchronisé', 'Refusé CMA']

        has_account = evalbox in COMPTE_EXISTE_EVALBOX or bool(num_dossier)

        if has_account:
            logger.info(f"  ✅ Compte ExamT3P existe: Evalbox={evalbox}, NUM_DOSSIER={num_dossier or 'N/A'}")
        else:
            logger.info(f"  ❌ Pas de compte ExamT3P: Evalbox={evalbox}, NUM_DOSSIER={num_dossier or 'vide'}")

        return has_account

    def _is_already_paid_to_cma(self, deal: Dict[str, Any]) -> bool:
        """
        Vérifie si les frais d'examen ont déjà été payés à la CMA pour ce deal.

        Les frais sont payés si Evalbox = "Dossier Synchronisé" ou "Refusé CMA"

        Args:
            deal: Le deal à vérifier

        Returns:
            True si frais déjà payés
        """
        evalbox = deal.get('Evalbox', '')
        PAID_STATUSES = ['Dossier Synchronisé', 'Refusé CMA']
        return evalbox in PAID_STATUSES

    def _select_deal_for_duplicate_recovery(
        self,
        current_deal: Dict[str, Any],
        duplicate_deal: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sélectionne le deal sur lequel travailler quand on a 2 deals GAGNÉ.

        Règle :
        - Si le doublon (ancien) a un compte ExamT3P → travailler sur l'ancien
        - Sinon → travailler sur le nouveau (current)

        Args:
            current_deal: Le deal lié au ticket actuel
            duplicate_deal: Le deal doublon trouvé

        Returns:
            {
                'deal_to_work_on': Dict - Le deal sur lequel continuer
                'deal_to_disable': Dict - Le deal à désactiver (EXAM_INCLUS=Non)
                'already_paid_to_cma': bool - Si les frais CMA ont déjà été payés
                'reason': str - Explication du choix
            }
        """
        result = {
            'deal_to_work_on': None,
            'deal_to_disable': None,
            'already_paid_to_cma': False,
            'reason': ''
        }

        # Vérifier si l'ancien deal (doublon) a un compte ExamT3P
        duplicate_has_account = self._has_examt3p_account(duplicate_deal)

        if duplicate_has_account:
            # Travailler sur l'ancien deal (doublon) car il a un compte ExamT3P
            result['deal_to_work_on'] = duplicate_deal
            result['deal_to_disable'] = current_deal
            result['already_paid_to_cma'] = self._is_already_paid_to_cma(duplicate_deal)
            result['reason'] = f"Ancien deal a compte ExamT3P (Evalbox: {duplicate_deal.get('Evalbox', 'N/A')})"
            logger.info(f"  🎯 Sélection: ANCIEN deal (compte ExamT3P existe)")
            logger.info(f"     → Travailler sur: {duplicate_deal.get('Deal_Name')}")
            logger.info(f"     → Désactiver: {current_deal.get('Deal_Name')}")
        else:
            # Travailler sur le nouveau deal (current)
            result['deal_to_work_on'] = current_deal
            result['deal_to_disable'] = duplicate_deal
            result['already_paid_to_cma'] = False
            result['reason'] = "Ancien deal sans compte ExamT3P → utiliser nouveau deal"
            logger.info(f"  🎯 Sélection: NOUVEAU deal (ancien sans compte ExamT3P)")
            logger.info(f"     → Travailler sur: {current_deal.get('Deal_Name')}")
            logger.info(f"     → Désactiver: {duplicate_deal.get('Deal_Name')}")

        if result['already_paid_to_cma']:
            logger.warning(f"  ⚠️ ATTENTION: Frais CMA déjà payés sur l'ancien deal !")

        return result

    def _classify_duplicate_type(self, duplicate_deal: Dict[str, Any]) -> str:
        """
        Classifie le type de doublon trouvé.

        Args:
            duplicate_deal: Le deal doublon trouvé

        Returns:
            'TRUE_DUPLICATE' - Examen déjà passé ou dossier validé (irrécupérable)
            'RECOVERABLE_PAID' - Dossier Synchronisé (payé mais pas encore validé), peut reprendre
            'RECOVERABLE_REFUS_CMA' - Refusé par la CMA (payé), peut se réinscrire
            'RECOVERABLE_NOT_PAID' - Jamais payé, peut se réinscrire
        """
        resultat = duplicate_deal.get('Resultat', '')
        evalbox = duplicate_deal.get('Evalbox', '')

        # Statuts d'examen passé
        COMPLETED_RESULTAT_VALUES = ['ADMISSIBLE', 'NON ADMISSIBLE', 'NON ADMIS', 'ABSENT']

        # Statuts de dossier validé/en cours d'examen (irrécupérable)
        VALIDATED_EVALBOX_VALUES = ['VALIDE CMA', 'Convoc CMA reçue', 'Convoc CMA recue']

        # Statut de refus CMA (payé mais refusé)
        REFUS_CMA_VALUES = ['Refusé CMA', 'Refuse CMA']

        # Statut Dossier Synchronisé (payé, en cours d'instruction)
        PAID_WAITING_VALUES = ['Dossier Synchronisé']

        # Vérifier si examen passé
        if resultat and resultat.upper() in [r.upper() for r in COMPLETED_RESULTAT_VALUES]:
            logger.info(f"  🔴 TRUE_DUPLICATE: Résultat={resultat}")
            return 'TRUE_DUPLICATE'

        # Vérifier si dossier validé
        if evalbox and evalbox in VALIDATED_EVALBOX_VALUES:
            logger.info(f"  🔴 TRUE_DUPLICATE: Evalbox={evalbox}")
            return 'TRUE_DUPLICATE'

        # Vérifier si Dossier Synchronisé (payé, en attente validation)
        if evalbox and evalbox in PAID_WAITING_VALUES:
            logger.info(f"  🟡 RECOVERABLE_PAID: Evalbox={evalbox} (frais CMA déjà payés)")
            return 'RECOVERABLE_PAID'

        # Vérifier si refus CMA (payé mais refusé)
        if evalbox and evalbox in REFUS_CMA_VALUES:
            logger.info(f"  🟡 RECOVERABLE_REFUS_CMA: Evalbox={evalbox} (frais CMA déjà payés)")
            return 'RECOVERABLE_REFUS_CMA'

        # Sinon: pas encore payé
        logger.info(f"  🟢 RECOVERABLE_NOT_PAID: Evalbox={evalbox or 'N/A'}, Resultat={resultat or 'N/A'}")
        return 'RECOVERABLE_NOT_PAID'

    def _extract_alternative_emails_from_threads(
        self,
        threads: List[Dict[str, Any]],
        primary_email: str
    ) -> List[str]:
        """
        Utilise l'IA pour extraire les emails alternatifs mentionnés dans la conversation.

        Par exemple, si le candidat dit "Essayez avec celle-ci : autre@email.com",
        cette méthode extraira "autre@email.com".

        Args:
            threads: Liste des threads de conversation
            primary_email: Email principal du ticket (à exclure des résultats)

        Returns:
            Liste d'emails alternatifs trouvés (sans le primary_email)
        """
        if not threads or len(threads) < 2:
            # Pas assez d'historique pour chercher des emails alternatifs
            return []

        # Construire le contenu de la conversation
        conversation_text = ""
        for thread in threads:
            content = thread.get("content") or thread.get("plainText") or ""
            from_email = thread.get("fromEmailAddress") or thread.get("from") or ""
            direction = thread.get("direction", "")

            # On s'intéresse surtout aux messages du candidat
            if direction == "in":
                conversation_text += f"\n---\nMessage du candidat:\n{content}\n"

        if not conversation_text.strip():
            return []

        # Utiliser l'IA pour extraire les emails alternatifs
        try:
            from anthropic import Anthropic
            import os

            client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

            prompt = f"""Analyse cette conversation et trouve les adresses email alternatives mentionnées par le candidat.

Le candidat utilise actuellement l'email: {primary_email}

Conversation:
{conversation_text}

INSTRUCTIONS:
- Cherche les emails que le candidat a mentionné comme alternative (ex: "essayez avec...", "mon autre email est...", "utilisez plutôt...")
- Ignore l'email principal ({primary_email})
- Ignore les emails de CAB Formations (doc@cab-formations.fr, etc.)
- Retourne UNIQUEMENT les emails alternatifs, un par ligne
- Si aucun email alternatif trouvé, retourne "AUCUN"

Emails alternatifs trouvés:"""

            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            result = response.content[0].text.strip()

            if result == "AUCUN" or not result:
                logger.info("  Aucun email alternatif trouvé dans l'historique")
                return []

            # Parser les emails trouvés
            alternative_emails = []
            for line in result.split("\n"):
                line = line.strip().lower()
                # Vérifier que c'est bien un email
                if "@" in line and "." in line:
                    # Nettoyer (enlever puces, tirets, etc.)
                    email = re.sub(r'^[\-\*\•\s]+', '', line).strip()
                    if email and email != primary_email.lower() and "cab-formations" not in email:
                        alternative_emails.append(email)

            if alternative_emails:
                logger.info(f"  📧 Emails alternatifs trouvés: {alternative_emails}")

            return alternative_emails

        except Exception as e:
            logger.warning(f"  Erreur extraction emails alternatifs: {e}")
            return []

    def _extract_deal_id_from_cf_opportunite(self, cf_value: str) -> Optional[str]:
        """
        Extrait l'ID du deal depuis le champ cf_opportunite.

        Le champ peut contenir :
        - Un ID direct : "1234567890"
        - Une URL Zoho CRM : "https://crm.zoho.com/crm/org123/tab/Potentials/1234567890"

        Returns:
            ID du deal ou None si non trouvé
        """
        if not cf_value:
            return None

        cf_value = str(cf_value).strip()

        # Cas 1: C'est un ID direct (juste des chiffres)
        if cf_value.isdigit():
            return cf_value

        # Cas 2: C'est une URL Zoho CRM
        # Format: https://crm.zoho.com/crm/org.../tab/Potentials/1234567890
        url_match = re.search(r'/Potentials/(\d+)', cf_value)
        if url_match:
            return url_match.group(1)

        # Cas 3: URL avec Deals au lieu de Potentials
        url_match = re.search(r'/Deals/(\d+)', cf_value)
        if url_match:
            return url_match.group(1)

        # Cas 4: Chercher n'importe quel grand nombre (ID Zoho = 19 chiffres typiquement)
        id_match = re.search(r'(\d{10,})', cf_value)
        if id_match:
            return id_match.group(1)

        logger.warning(f"  ⚠️ Impossible d'extraire l'ID du deal depuis cf_opportunite: {cf_value}")
        return None

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
            "deal_found": False,
            "has_duplicate_uber_offer": False,  # True si candidat a déjà bénéficié de l'offre Uber 20€
            "duplicate_deals": [],  # Liste des deals 20€ GAGNÉ si doublon détecté
            # Nouveaux champs pour la détection de doublons par nom+CP
            "duplicate_confidence": None,  # 'HIGH_CONFIDENCE' ou 'NEEDS_CONFIRMATION'
            "duplicate_type": None,  # 'TRUE_DUPLICATE', 'RECOVERABLE_REFUS_CMA', 'RECOVERABLE_NOT_PAID', 'RECOVERABLE_PAID'
            "needs_duplicate_confirmation": False,  # True si on doit demander confirmation au candidat
            "duplicate_contact_info": {},  # Infos de contact du doublon pour clarification
            # Champs pour la gestion des 2 deals GAGNÉ (doublon récupérable)
            "deal_to_work_on": None,  # Deal sur lequel travailler
            "deal_to_disable": None,  # Deal à désactiver (EXAM_INCLUS=Non)
            "already_paid_to_cma": False,  # True si frais CMA déjà payés (note à ajouter)
            "duplicate_selection_reason": None  # Raison du choix de deal
        }

        # Step 1: Get ticket details
        try:
            ticket = self.desk_client.get_ticket(ticket_id)
        except Exception as e:
            logger.error(f"Could not fetch ticket {ticket_id}: {e}")
            result["error"] = f"Could not fetch ticket: {e}"
            return result

        # Step 1.5: PRIORITÉ #1 - Vérifier si le ticket a déjà un lien vers une opportunité
        cf_opportunite = ticket.get('cf', {}).get('cf_opportunite') or ticket.get('cf_opportunite')
        deal_already_linked = False

        if cf_opportunite:
            logger.info(f"  📎 Ticket déjà lié à une opportunité: {cf_opportunite}")
            # Extraire l'ID du deal depuis l'URL ou la valeur
            deal_id = self._extract_deal_id_from_cf_opportunite(cf_opportunite)
            if deal_id:
                try:
                    crm_client = self._get_crm_client()
                    deal_data = crm_client.get_deal(deal_id)
                    if deal_data:
                        logger.info(f"  ✅ Deal trouvé via cf_opportunite: {deal_data.get('Deal_Name', deal_id)}")
                        result["success"] = True
                        result["deal_found"] = True
                        result["deal_id"] = deal_id
                        result["deal"] = deal_data
                        result["selected_deal"] = deal_data
                        result["all_deals"] = [deal_data]
                        result["deals_found"] = 1
                        result["routing_explanation"] = "Deal trouvé via champ cf_opportunite du ticket"
                        result["link_source"] = "cf_opportunite"
                        deal_already_linked = True

                        # Vérifier doublon Uber même pour les tickets déjà liés
                        # (au cas où le lien a été fait manuellement sans vérification)
                        # IMPORTANT: Chercher par EMAIL pour trouver les deals sur tous les contacts
                        # du même candidat (cas de contacts dupliqués dans le CRM)
                        contact_id = deal_data.get('Contact_Name', {}).get('id')
                        all_deals = []
                        if contact_id:
                            # D'abord récupérer l'email du contact
                            try:
                                crm_client = self._get_crm_client()
                                contact_data = crm_client.get_contact(contact_id)
                                contact_email = contact_data.get('Email', '').lower().strip() if contact_data else None

                                if contact_email:
                                    # Chercher TOUS les contacts avec cet email
                                    all_contacts = self._search_contacts_by_email(contact_email)
                                    all_contact_ids = [c.get('id') for c in all_contacts if c.get('id')]

                                    # S'assurer que le contact_id actuel est inclus
                                    if contact_id not in all_contact_ids:
                                        all_contact_ids.append(contact_id)

                                    # Récupérer les deals de TOUS ces contacts
                                    all_deals = self._get_deals_for_contacts(all_contact_ids)
                                    logger.info(f"  📧 Recherche par email {contact_email}: {len(all_contacts)} contact(s), {len(all_deals)} deal(s)")
                                else:
                                    # Fallback: recherche par contact_id uniquement
                                    all_deals = self._get_deals_for_contacts([contact_id])
                            except Exception as e:
                                logger.warning(f"  ⚠️ Erreur recherche par email: {e}")
                                all_deals = self._get_deals_for_contacts([contact_id])

                        if all_deals:
                            result["all_deals"] = all_deals
                            result["deals_found"] = len(all_deals)

                            # Check for duplicate Uber 20€
                            deals_20_won = [d for d in all_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]

                            # Si 1 seul deal 20€ trouvé par email, chercher par téléphone pour détecter doublons
                            if len(deals_20_won) == 1:
                                logger.info(f"  📱 1 deal 20€ GAGNÉ trouvé - recherche doublon via téléphone...")
                                phone = None
                                if contact_data:
                                    contact_phone = contact_data.get('Phone') or contact_data.get('Mobile')
                                    if contact_phone:
                                        phone = self._normalize_phone(contact_phone)

                                if phone:
                                    logger.info(f"  📱 Téléphone: {phone} - recherche de contacts...")
                                    phone_contacts = self._search_contacts_by_phone(phone)

                                    if phone_contacts:
                                        new_phone_contact_ids = [
                                            c.get("id") for c in phone_contacts
                                            if c.get("id") and c.get("id") not in all_contact_ids
                                        ]

                                        if new_phone_contact_ids:
                                            logger.info(f"  📱 {len(new_phone_contact_ids)} nouveau(x) contact(s) trouvé(s) par téléphone")
                                            phone_deals = self._get_deals_for_contacts(new_phone_contact_ids)
                                            phone_deals_20_won = [d for d in phone_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]

                                            if phone_deals_20_won:
                                                existing_ids = {d.get("id") for d in all_deals}
                                                for deal in phone_deals:
                                                    if deal.get("id") not in existing_ids:
                                                        all_deals.append(deal)
                                                        if deal.get("Amount") == 20 and deal.get("Stage") == "GAGNÉ":
                                                            deals_20_won.append(deal)

                                                result["phone_duplicate_check"] = True
                                                result["phone_used"] = phone
                                                result["all_deals"] = all_deals
                                                result["deals_found"] = len(all_deals)
                                                logger.info(f"  ✅ DOUBLON DÉTECTÉ VIA TÉLÉPHONE: {len(phone_deals_20_won)} deal(s) 20€ GAGNÉ supplémentaire(s)")
                                            else:
                                                logger.info(f"  📱 Pas de deal 20€ GAGNÉ supplémentaire via téléphone")
                                        else:
                                            logger.info(f"  📱 Contacts téléphone = mêmes que contacts email")
                                    else:
                                        logger.info(f"  📱 Aucun contact trouvé par téléphone")
                                else:
                                    logger.info(f"  📱 Aucun téléphone disponible pour vérification doublon")

                            # ==================================================================
                            # VÉRIFICATION DOUBLON PAR NOM + CODE POSTAL
                            # ==================================================================
                            current_deal = result.get("selected_deal") or deal_data
                            if len(deals_20_won) <= 1 and current_deal:
                                contact_name_data = current_deal.get('Contact_Name', {})
                                if isinstance(contact_name_data, dict):
                                    candidate_name = contact_name_data.get('name', '')
                                else:
                                    candidate_name = str(contact_name_data) if contact_name_data else ''

                                postal_code = current_deal.get('Mailing_Zip', '')

                                # Récupérer email/phone du candidat actuel pour comparaison
                                current_email = contact_data.get('Email', '').lower().strip() if contact_data and contact_data.get('Email') else None
                                current_phone_raw = contact_data.get('Phone') or contact_data.get('Mobile') if contact_data else None
                                current_phone = self._normalize_phone(current_phone_raw) if current_phone_raw else None

                                if candidate_name and postal_code:
                                    existing_deal_ids = [d.get('id') for d in all_deals if d.get('id')]
                                    name_postal_result = self._search_duplicate_by_name_and_postal(
                                        candidate_name=candidate_name,
                                        postal_code=str(postal_code),
                                        exclude_deal_ids=existing_deal_ids,
                                        candidate_email=current_email,
                                        candidate_phone=current_phone
                                    )

                                    name_postal_duplicates = name_postal_result.get('duplicates', [])
                                    if name_postal_duplicates:
                                        for dup_deal in name_postal_duplicates:
                                            if dup_deal.get('id') not in existing_deal_ids:
                                                all_deals.append(dup_deal)
                                                deals_20_won.append(dup_deal)

                                        result["name_postal_duplicate_check"] = True
                                        result["deals_found"] = len(all_deals)
                                        result["all_deals"] = all_deals
                                        result["duplicate_confidence"] = name_postal_result.get('confidence')
                                        result["duplicate_type"] = name_postal_result.get('duplicate_type')
                                        logger.warning(f"  ⚠️ DOUBLON DÉTECTÉ VIA NOM+CP: {len(name_postal_duplicates)} deal(s) 20€ GAGNÉ")

                                        # Si NEEDS_CONFIRMATION → demander clarification
                                        if name_postal_result.get('confidence') == 'NEEDS_CONFIRMATION':
                                            result["needs_duplicate_confirmation"] = True
                                            # Stocker les infos de contact du doublon pour la clarification
                                            dup_deal = name_postal_duplicates[0]
                                            result["duplicate_contact_info"] = {
                                                "duplicate_deal_id": dup_deal.get('id'),
                                                "duplicate_email": dup_deal.get('_duplicate_contact_email'),
                                                "duplicate_phone": dup_deal.get('_duplicate_contact_phone'),
                                                "duplicate_deal_name": dup_deal.get('Deal_Name')
                                            }
                                            logger.info(f"  ❓ CONFIRMATION REQUISE: email/téléphone différents")
                                        elif current_deal.get('Amount') == 20:
                                            # HIGH_CONFIDENCE → doublon confirmé
                                            result["has_duplicate_uber_offer"] = True
                                            result["duplicate_deals"] = name_postal_duplicates
                                            logger.warning(f"  ⚠️ DOUBLON UBER détecté (HIGH_CONFIDENCE): candidat a déjà un deal 20€ GAGNÉ")

                            if len(deals_20_won) > 1 and not result.get("has_duplicate_uber_offer"):
                                result["has_duplicate_uber_offer"] = True
                                result["duplicate_deals"] = deals_20_won
                                logger.warning(f"  ⚠️ DOUBLON UBER détecté: {len(deals_20_won)} opportunités 20€ GAGNÉ")

                            # Check for offer already used (Resultat filled = exam taken)
                            COMPLETED_RESULTAT_VALUES = ['ADMISSIBLE', 'NON ADMISSIBLE', 'NON ADMIS']
                            if len(deals_20_won) == 1 and not result["has_duplicate_uber_offer"]:
                                deal = deals_20_won[0]
                                resultat = deal.get('Resultat', '')
                                if resultat and resultat.upper() in [r.upper() for r in COMPLETED_RESULTAT_VALUES]:
                                    result["has_duplicate_uber_offer"] = True
                                    result["duplicate_deals"] = deals_20_won
                                    result["offer_already_used"] = True
                                    logger.warning(f"  ⚠️ OFFRE DÉJÀ UTILISÉE: Resultat='{resultat}'")

                            # ==================================================================
                            # VÉRIFICATION FORMATION PAYANTE PLUS RÉCENTE
                            # Si le candidat a une formation payante (>20€) après l'offre Uber,
                            # on annule le flag doublon et on traite normalement
                            # ==================================================================
                            if result["has_duplicate_uber_offer"]:
                                paid_check = _check_has_paid_formation_after_uber(all_deals, deals_20_won)
                                if paid_check['override_duplicate']:
                                    result["has_duplicate_uber_offer"] = False
                                    result["has_paid_formation"] = True
                                    result["paid_formation_deal"] = paid_check['paid_formation_deal']
                                    # Mettre à jour le deal sélectionné vers la formation payante
                                    result["selected_deal"] = paid_check['paid_formation_deal']
                                    result["deal_id"] = paid_check['paid_formation_deal'].get('id')
                                    result["deal"] = paid_check['paid_formation_deal']
                                    logger.info("  ✅ Doublon Uber annulé: formation payante plus récente détectée")
                                    logger.info(f"  🎯 Deal mis à jour: {paid_check['paid_formation_deal'].get('Deal_Name')} (€{paid_check['paid_formation_deal'].get('Amount')})")

                            # Calculer le département recommandé même pour les tickets déjà liés
                            # (pour gérer les cas comme "examen pratique" qui doivent aller vers Contact)
                            try:
                                recommended_department = BusinessRules.determine_department_from_deals_and_ticket(
                                    all_deals, ticket
                                )
                                result["recommended_department"] = recommended_department
                                logger.info(f"  📍 Département recommandé: {recommended_department}")
                            except Exception as e:
                                logger.warning(f"  ⚠️ Erreur calcul département: {e}")

                        # NOTE: On ne retourne PAS ici - on continue pour extraire l'email du forward
                except Exception as e:
                    logger.warning(f"  ⚠️ Erreur récupération deal depuis cf_opportunite: {e}")
                    # Continuer avec la recherche normale

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
            # Si le deal est déjà lié, on retourne quand même (le draft utilisera l'email du ticket en fallback)
            if deal_already_linked:
                logger.info(f"  ⚠️ Deal déjà lié mais pas d'email client trouvé - le draft utilisera l'email du ticket")
                return result
            result["routing_explanation"] = "No email found - cannot link to CRM deals"
            result["success"] = True  # Success but no deal found
            return result

        result["email_found"] = True
        result["email"] = email
        logger.info(f"Email extracted: {email}")

        # Si le deal est déjà lié via cf_opportunite, on a juste besoin de l'email pour le draft
        # Pas besoin de refaire la recherche de contacts/deals
        if deal_already_linked:
            logger.info(f"  ✅ Deal déjà lié + email extrait ({email}) - retour anticipé")
            return result

        # Step 4: Search ALL contacts with this email
        contacts = self._search_contacts_by_email(email)
        result["contacts_found"] = len(contacts)

        # Step 4b: Si pas de contacts trouvés, chercher des emails alternatifs dans l'historique
        alternative_email_used = None
        if not contacts:
            logger.info(f"No contacts found in CRM for email {email}")

            # Chercher des emails alternatifs mentionnés dans la conversation
            alternative_emails = self._extract_alternative_emails_from_threads(threads, email)

            for alt_email in alternative_emails:
                logger.info(f"  🔄 Tentative avec email alternatif: {alt_email}")
                alt_contacts = self._search_contacts_by_email(alt_email)
                if alt_contacts:
                    contacts = alt_contacts
                    alternative_email_used = alt_email
                    result["alternative_email_used"] = alt_email
                    result["contacts_found"] = len(contacts)
                    logger.info(f"  ✅ Contacts trouvés avec email alternatif: {alt_email}")
                    break

        # Si toujours pas de contacts trouvés → TOUJOURS demander clarification
        # Sans deal CRM, on ne peut pas répondre correctement (risque d'hallucination)
        if not contacts:
            logger.warning(f"  ⚠️ Aucun contact CRM trouvé - clarification nécessaire")
            result["needs_clarification"] = True
            result["clarification_reason"] = "candidate_not_found"
            result["routing_explanation"] = f"No CRM contacts found for email {email}"
            result["success"] = True  # Success but no deal found
            return result

        contact_ids = [c.get("id") for c in contacts if c.get("id")]
        used_email = alternative_email_used or email
        logger.info(f"Found {len(contact_ids)} contact(s) for email {used_email}")

        # Step 5: Get ALL deals for these contacts
        all_deals = self._get_deals_for_contacts(contact_ids)
        result["deals_found"] = len(all_deals)
        result["all_deals"] = all_deals

        # Step 5b: PHONE FALLBACK - Si pas de deal 20€ GAGNÉ trouvé, chercher par téléphone
        deals_20_won_initial = [d for d in all_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]
        phone_fallback_used = False

        if not deals_20_won_initial:
            logger.info(f"  📱 Aucun deal 20€ GAGNÉ trouvé par email - tentative fallback téléphone")

            # Extraire le numéro de téléphone:
            # 1. D'abord depuis le contact CRM trouvé (plus fiable)
            # 2. Sinon depuis le ticket Desk
            phone = None

            # 1. Depuis le contact CRM
            for contact in contacts:
                contact_phone = contact.get('Phone') or contact.get('Mobile')
                if contact_phone:
                    phone = self._normalize_phone(contact_phone)
                    if phone:
                        logger.info(f"  📱 Phone from CRM contact: {phone}")
                        break

            # 2. Fallback: depuis le ticket Desk
            if not phone:
                phone = self._extract_phone_from_ticket(ticket, threads)

            if phone:
                logger.info(f"  📱 Téléphone extrait: {phone} - recherche de contacts...")

                # Chercher des contacts par téléphone
                phone_contacts = self._search_contacts_by_phone(phone)

                if phone_contacts:
                    # Filtrer les contacts déjà trouvés par email
                    new_contact_ids = [
                        c.get("id") for c in phone_contacts
                        if c.get("id") and c.get("id") not in contact_ids
                    ]

                    if new_contact_ids:
                        logger.info(f"  📱 {len(new_contact_ids)} nouveau(x) contact(s) trouvé(s) par téléphone")

                        # Récupérer les deals de ces nouveaux contacts
                        phone_deals = self._get_deals_for_contacts(new_contact_ids)

                        # Vérifier s'il y a des deals 20€ GAGNÉ parmi eux
                        phone_deals_20_won = [d for d in phone_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]

                        if phone_deals_20_won:
                            # Fusionner avec les deals existants (éviter doublons)
                            existing_ids = {d.get("id") for d in all_deals}
                            for deal in phone_deals:
                                if deal.get("id") not in existing_ids:
                                    all_deals.append(deal)

                            phone_fallback_used = True
                            result["phone_fallback_used"] = True
                            result["phone_used"] = phone
                            result["deals_found"] = len(all_deals)
                            result["all_deals"] = all_deals
                            logger.info(f"  ✅ PHONE FALLBACK SUCCESS: {len(phone_deals_20_won)} deal(s) 20€ GAGNÉ trouvé(s) par téléphone")
                        else:
                            logger.info(f"  📱 Deals trouvés par téléphone mais aucun 20€ GAGNÉ")
                    else:
                        logger.info(f"  📱 Contacts téléphone = mêmes que contacts email")
                else:
                    logger.info(f"  📱 Aucun contact trouvé par téléphone")
            else:
                logger.info(f"  📱 Aucun téléphone extractible du ticket")

        # Si pas de deals trouvés → TOUJOURS demander clarification
        # Contact existe mais pas d'opportunité = situation anormale
        if not all_deals:
            logger.warning(f"  ⚠️ Contact trouvé mais aucun deal - clarification nécessaire")
            result["needs_clarification"] = True
            result["clarification_reason"] = "no_deal_for_contact"
            result["routing_explanation"] = f"Contact found but no deals for email {used_email}"
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
            # NOUVELLE LOGIQUE DE SÉLECTION DE DEAL (v3)
            # Règle simple : prendre le deal GAGNÉ le plus récent
            # avec le même TYPE_DE_FORMATION
            # ================================================================
            selected_deal = None
            selection_method = None

            # PRIORITÉ 0 : Deal GAGNÉ le plus récent (même TYPE_DE_FORMATION)
            # Identifier le type de formation le plus courant parmi les deals GAGNÉ
            deals_gagne = [d for d in all_deals if d.get("Stage") == "GAGNÉ"]

            if deals_gagne:
                # Trouver le TYPE_DE_FORMATION le plus récent
                deals_gagne_sorted = sorted(
                    deals_gagne,
                    key=lambda d: d.get("Closing_Date", "") or d.get("Created_Time", ""),
                    reverse=True
                )

                # Prendre le deal GAGNÉ le plus récent
                selected_deal = deals_gagne_sorted[0]
                selection_method = f"Priority 0 - Deal GAGNÉ le plus récent ({selected_deal.get('TYPE_DE_FORMATION', 'N/A')})"
                logger.info(f"🎯 Deal sélectionné (plus récent GAGNÉ): {selected_deal.get('Deal_Name')} - Type: {selected_deal.get('TYPE_DE_FORMATION', 'N/A')}")

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

            # ==================================================================
            # DÉTECTION DOUBLON UBER 20€ (candidat ayant déjà bénéficié de l'offre)
            # ==================================================================
            deals_20_won = [d for d in all_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]

            # Si 1 seul deal 20€ trouvé par email, chercher par téléphone pour détecter doublons
            if len(deals_20_won) == 1 and not phone_fallback_used:
                logger.info(f"  📱 1 deal 20€ GAGNÉ trouvé par email - recherche doublon via téléphone...")

                # Extraire le téléphone du contact ou du ticket
                phone = None
                for contact in contacts:
                    contact_phone = contact.get('Phone') or contact.get('Mobile')
                    if contact_phone:
                        phone = self._normalize_phone(contact_phone)
                        if phone:
                            break

                if not phone:
                    phone = self._extract_phone_from_ticket(ticket, threads)

                if phone:
                    logger.info(f"  📱 Téléphone: {phone} - recherche de contacts...")
                    phone_contacts = self._search_contacts_by_phone(phone)

                    if phone_contacts:
                        # Filtrer les contacts déjà trouvés par email
                        new_contact_ids = [
                            c.get("id") for c in phone_contacts
                            if c.get("id") and c.get("id") not in contact_ids
                        ]

                        if new_contact_ids:
                            logger.info(f"  📱 {len(new_contact_ids)} nouveau(x) contact(s) trouvé(s) par téléphone")
                            phone_deals = self._get_deals_for_contacts(new_contact_ids)
                            phone_deals_20_won = [d for d in phone_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]

                            if phone_deals_20_won:
                                # Fusionner avec all_deals et deals_20_won
                                existing_ids = {d.get("id") for d in all_deals}
                                for deal in phone_deals:
                                    if deal.get("id") not in existing_ids:
                                        all_deals.append(deal)
                                        if deal.get("Amount") == 20 and deal.get("Stage") == "GAGNÉ":
                                            deals_20_won.append(deal)

                                result["phone_duplicate_check"] = True
                                result["phone_used"] = phone
                                result["deals_found"] = len(all_deals)
                                result["all_deals"] = all_deals
                                logger.info(f"  ✅ DOUBLON DÉTECTÉ VIA TÉLÉPHONE: {len(phone_deals_20_won)} deal(s) 20€ GAGNÉ supplémentaire(s)")
                            else:
                                logger.info(f"  📱 Pas de deal 20€ GAGNÉ supplémentaire via téléphone")
                        else:
                            logger.info(f"  📱 Contacts téléphone = mêmes que contacts email")
                    else:
                        logger.info(f"  📱 Aucun contact trouvé par téléphone")
                else:
                    logger.info(f"  📱 Aucun téléphone disponible pour vérification doublon")

            # ==================================================================
            # VÉRIFICATION DOUBLON PAR NOM + CODE POSTAL
            # Si on n'a qu'un seul deal 20€ ou aucun, chercher par nom+CP
            # pour détecter les doublons avec des données email/téléphone différentes
            # ==================================================================
            if len(deals_20_won) <= 1 and selected_deal:
                # Extraire nom et code postal du deal sélectionné
                contact_name_data = selected_deal.get('Contact_Name', {})
                if isinstance(contact_name_data, dict):
                    candidate_name = contact_name_data.get('name', '')
                else:
                    candidate_name = str(contact_name_data) if contact_name_data else ''

                postal_code = selected_deal.get('Mailing_Zip', '')

                # Récupérer email/phone du candidat actuel pour comparaison
                current_email = email  # Email extrait du ticket
                current_phone = None
                for contact in contacts:
                    contact_phone = contact.get('Phone') or contact.get('Mobile')
                    if contact_phone:
                        current_phone = self._normalize_phone(contact_phone)
                        break
                if not current_phone:
                    current_phone = self._extract_phone_from_ticket(ticket, threads)

                if candidate_name and postal_code:
                    # Exclure les deals déjà trouvés
                    existing_deal_ids = [d.get('id') for d in all_deals if d.get('id')]

                    name_postal_result = self._search_duplicate_by_name_and_postal(
                        candidate_name=candidate_name,
                        postal_code=str(postal_code),
                        exclude_deal_ids=existing_deal_ids,
                        candidate_email=current_email,
                        candidate_phone=current_phone
                    )

                    name_postal_duplicates = name_postal_result.get('duplicates', [])
                    if name_postal_duplicates:
                        # Fusionner avec all_deals et deals_20_won
                        for dup_deal in name_postal_duplicates:
                            if dup_deal.get('id') not in existing_deal_ids:
                                all_deals.append(dup_deal)
                                deals_20_won.append(dup_deal)

                        result["name_postal_duplicate_check"] = True
                        result["deals_found"] = len(all_deals)
                        result["all_deals"] = all_deals
                        result["duplicate_confidence"] = name_postal_result.get('confidence')
                        result["duplicate_type"] = name_postal_result.get('duplicate_type')
                        logger.warning(f"  ⚠️ DOUBLON DÉTECTÉ VIA NOM+CP: {len(name_postal_duplicates)} deal(s) 20€ GAGNÉ")

                        # Si NEEDS_CONFIRMATION → demander clarification
                        if name_postal_result.get('confidence') == 'NEEDS_CONFIRMATION':
                            result["needs_duplicate_confirmation"] = True
                            # Stocker les infos de contact du doublon pour la clarification
                            dup_deal = name_postal_duplicates[0]
                            result["duplicate_contact_info"] = {
                                "duplicate_deal_id": dup_deal.get('id'),
                                "duplicate_email": dup_deal.get('_duplicate_contact_email'),
                                "duplicate_phone": dup_deal.get('_duplicate_contact_phone'),
                                "duplicate_deal_name": dup_deal.get('Deal_Name')
                            }
                            logger.info(f"  ❓ CONFIRMATION REQUISE: email/téléphone différents")
                        elif selected_deal and selected_deal.get('Amount') == 20:
                            # HIGH_CONFIDENCE → doublon confirmé
                            result["has_duplicate_uber_offer"] = True
                            result["duplicate_deals"] = name_postal_duplicates
                            logger.warning(f"  ⚠️ DOUBLON UBER détecté (HIGH_CONFIDENCE): candidat a déjà un deal 20€ GAGNÉ")
                else:
                    if not candidate_name:
                        logger.info(f"  📛 Pas de nom de contact pour vérification doublon par nom+CP")
                    if not postal_code:
                        logger.info(f"  📮 Pas de code postal pour vérification doublon par nom+CP")

            if len(deals_20_won) > 1 and not result.get("has_duplicate_uber_offer"):
                # DOUBLON DÉTECTÉ : Le candidat a plusieurs opportunités 20€ GAGNÉ
                # Cela signifie qu'il a déjà bénéficié de l'offre Uber une fois
                result["has_duplicate_uber_offer"] = True
                result["duplicate_deals"] = deals_20_won
                logger.warning(f"⚠️ DOUBLON UBER 20€ DÉTECTÉ: {len(deals_20_won)} opportunités 20€ GAGNÉ pour ce contact")
                for d in deals_20_won:
                    logger.warning(f"   - {d.get('Deal_Name')} (ID: {d.get('id')}, Closing: {d.get('Closing_Date')})")

            # ==================================================================
            # DÉTECTION OFFRE DÉJÀ UTILISÉE (Resultat rempli = examen passé)
            # Si le seul deal 20€ GAGNÉ a un Resultat (ADMISSIBLE, NON ADMISSIBLE, NON ADMIS)
            # cela signifie que le candidat a déjà passé l'examen avec cette offre
            # ==================================================================
            COMPLETED_RESULTAT_VALUES = ['ADMISSIBLE', 'NON ADMISSIBLE', 'NON ADMIS']
            if len(deals_20_won) == 1 and not result["has_duplicate_uber_offer"]:
                deal = deals_20_won[0]
                resultat = deal.get('Resultat', '')
                if resultat and resultat.upper() in [r.upper() for r in COMPLETED_RESULTAT_VALUES]:
                    # Le candidat a déjà utilisé cette offre (examen déjà passé)
                    result["has_duplicate_uber_offer"] = True
                    result["duplicate_deals"] = deals_20_won
                    result["offer_already_used"] = True  # Flag spécifique pour ce cas
                    logger.warning(f"⚠️ OFFRE DÉJÀ UTILISÉE: Le deal a Resultat='{resultat}' (examen déjà passé)")
                    logger.warning(f"   - {deal.get('Deal_Name')} (ID: {deal.get('id')}, Resultat: {resultat})")

            # ==================================================================
            # VÉRIFICATION FORMATION PAYANTE PLUS RÉCENTE
            # Si le candidat a une formation payante (>20€) après l'offre Uber,
            # on annule le flag doublon et on traite normalement
            # ==================================================================
            if result["has_duplicate_uber_offer"]:
                paid_check = _check_has_paid_formation_after_uber(all_deals, deals_20_won)
                if paid_check['override_duplicate']:
                    result["has_duplicate_uber_offer"] = False
                    result["has_paid_formation"] = True
                    result["paid_formation_deal"] = paid_check['paid_formation_deal']
                    logger.info("✅ Doublon Uber annulé: formation payante plus récente détectée")

            # PRIORITÉ 1.5 : Formation payante plus récente (après offre Uber utilisée)
            # Si le candidat a utilisé l'offre Uber et a ensuite souscrit une formation payante,
            # on sélectionne cette formation comme deal principal
            if not selected_deal and result.get("has_paid_formation") and result.get("paid_formation_deal"):
                selected_deal = result["paid_formation_deal"]
                selection_method = "Priority 1.5 - Formation payante après Uber"
                logger.info(f"🎯 Deal sélectionné: formation payante {selected_deal.get('Deal_Name')} (€{selected_deal.get('Amount')})")

            # ==================================================================
            # PRIORITÉ 1.6 : DOUBLON RECOVERABLE - Sélection du bon deal
            # Si on a détecté un doublon RECOVERABLE et qu'on a 2 deals GAGNÉ,
            # on doit choisir sur lequel travailler (celui avec compte ExamT3P)
            # ==================================================================
            duplicate_type = result.get("duplicate_type")
            is_recoverable_duplicate = (
                result.get("has_duplicate_uber_offer") and
                duplicate_type in ['RECOVERABLE_PAID', 'RECOVERABLE_REFUS_CMA', 'RECOVERABLE_NOT_PAID']
            )

            if is_recoverable_duplicate and len(deals_20_won) >= 2:
                logger.info(f"  🔄 DOUBLON RECOVERABLE avec 2+ deals GAGNÉ - sélection du deal à utiliser")

                # Trouver le deal actuel (le plus récent) et le doublon (l'ancien)
                deals_sorted = sorted(deals_20_won, key=lambda d: d.get("Closing_Date", "") or "", reverse=True)
                current_deal = deals_sorted[0]  # Le plus récent
                duplicate_deal = deals_sorted[1]  # L'ancien (doublon)

                # Appeler la logique de sélection
                selection_result = self._select_deal_for_duplicate_recovery(current_deal, duplicate_deal)

                result["deal_to_work_on"] = selection_result["deal_to_work_on"]
                result["deal_to_disable"] = selection_result["deal_to_disable"]
                result["already_paid_to_cma"] = selection_result["already_paid_to_cma"]
                result["duplicate_selection_reason"] = selection_result["reason"]

                # Mettre à jour le deal sélectionné
                selected_deal = selection_result["deal_to_work_on"]
                selection_method = f"Priority 1.6 - Doublon RECOVERABLE ({selection_result['reason']})"

                if selection_result["already_paid_to_cma"]:
                    logger.warning(f"  ⚠️ ATTENTION: Frais CMA déjà payés - ne pas repayer !")

            # PRIORITÉ 2 : Deals 20€ GAGNÉ (candidats payés en cours de traitement)
            if not selected_deal:
                if deals_20_won:
                    selected_deal = sorted(deals_20_won, key=lambda d: d.get("Closing_Date", ""), reverse=True)[0]
                    selection_method = "Priority 2 - 20€ GAGNÉ (most recent)"
                    if result["has_duplicate_uber_offer"]:
                        selection_method += " [DOUBLON DÉTECTÉ]"

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
