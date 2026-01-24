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
        # ===== DÉPARTEMENTS PRIORITAIRES =====

        # DOC department: Specific Uber deal logic
        if department == "DOC":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Amount:equals:20)and(Stage:equals:Closed Won))",
                    "description": "Uber €20 deals - WON",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
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

        # DOCS CAB: Search for CAB-related deals
        elif department == "DOCS CAB":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:CAB)and(Stage:not_equals:Closed Lost))",
                    "description": "Active CAB deals",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                },
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Capacité)and(Stage:not_equals:Closed Lost))",
                    "description": "Active Capacité deals",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                }
            ]

        # Inscription CMA: Search for CMA registration deals
        elif department == "Inscription CMA":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:CMA)and(Stage:equals:Qualification))",
                    "description": "CMA deals in qualification",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                },
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:CMA)and(Stage:not_equals:Closed Lost))",
                    "description": "Any active CMA deals",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                }
            ]

        # Refus CMA: Search for rejected CMA deals
        elif department == "Refus CMA":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:CMA)and(Stage:equals:Closed Lost))",
                    "description": "Rejected CMA deals",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                }
            ]

        # Contact: General contact deals (any recent deal)
        elif department == "Contact":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Stage:not_equals:Closed Lost)and(Stage:not_equals:Closed Won))",
                    "description": "Any open deals",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                },
                {
                    "criteria": f"((Email:equals:{contact_email}))",
                    "description": "Most recent deal (any stage)",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
                }
            ]

        # Uber department: Similar to DOC but dedicated
        elif department == "Uber":
            return [
                {
                    "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Stage:not_equals:Closed Lost))",
                    "description": "Active Uber deals",
                    "max_results": 1,
                    "sort_by": "Modified_Time",
                    "sort_order": "desc"
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

    @staticmethod
    def get_department_routing_rules() -> Dict[str, Any]:
        """
        Get department routing rules for the TicketDispatcherAgent.

        These rules are checked BEFORE AI analysis for faster routing.
        Rules are deterministic and keyword-based.

        CUSTOMIZE THIS METHOD!

        Returns:
            Dict mapping department names to routing rules.
            Each department can have:
            - keywords: List of keywords to match in subject/description
            - subject_patterns: List of regex patterns for subject
            - contact_domains: List of email domains

        Example:
        {
            "DOC": {
                "keywords": ["uber", "a-level", "student", "education"],
                "contact_domains": ["@university.edu"]
            },
            "Sales": {
                "keywords": ["pricing", "quote", "demo", "purchase", "buy"]
            }
        }
        """
        return {
            # ===== DÉPARTEMENTS PRIORITAIRES =====

            "DOC": {
                "keywords": [
                    # Mots-clés basés sur l'analyse de 100 tickets réels de Fouad (01/11/2025)
                    # Top occurrences dans les sujets de tickets
                    "examen",           # 42 occurrences - #1
                    "inscription",      # 22 occurrences - #2
                    "formation",        # 13 occurrences - #4
                    "convocation",      # 12 occurrences - #5
                    "dossier",          # 11 occurrences
                    "test",             # 10 occurrences
                    "rappel",           # 10 occurrences
                    "demande",          # 10 occurrences
                    "sélection",        # 9 occurrences
                    "admissibilité",    # 8 occurrences
                    "épreuve",          # 7 occurrences
                    "récapitulatif",    # 7 occurrences
                    "uber",             # Historique
                    "a-level",          # Historique
                    "vtc",              # VTC exams
                    "passage",          # Passage d'examen
                    "réussi",           # Test réussi
                    "théorique",        # Examen théorique
                    "pratique"          # Examen pratique
                ],
                "contact_domains": []
            },

            "DOCS CAB": {
                "keywords": [
                    "cab",
                    "capacité",
                    "capacite",
                    "candidat",
                    "candidate",
                    "dossier cab",
                    "dossier de candidat",
                    "certificat",
                    "attestation"
                ],
                "contact_domains": []
            },

            "Contact": {
                "keywords": [
                    "contact",
                    "renseignement",
                    "information",
                    "question",
                    "demande",
                    "inquiry",
                    "general",
                    "assistance",
                    "help"
                ],
                "contact_domains": []
            },

            "Inscription CMA": {
                "keywords": [
                    "inscription",
                    "inscription cma",
                    "cma",
                    "registration",
                    "enregistrement",
                    "register",
                    "s'inscrire",
                    "adhésion",
                    "membership"
                ],
                "contact_domains": []
            },

            "Refus CMA": {
                "keywords": [
                    "refus",
                    "refus cma",
                    "rejet",
                    "declined",
                    "rejection",
                    "denied",
                    "refuse",
                    "non accepté",
                    "non-accepté"
                ],
                "contact_domains": []
            },

            # ===== AUTRES DÉPARTEMENTS =====

            "FACTURATION": {
                "keywords": [
                    "facture",
                    "facturation",
                    "invoice",
                    "payment",
                    "paiement",
                    "billing",
                    "refund",
                    "remboursement"
                ],
                "contact_domains": []
            },

            "Comptabilité": {
                "keywords": [
                    "comptabilité",
                    "comptable",
                    "accounting",
                    "financial",
                    "finance",
                    "trésorerie"
                ],
                "contact_domains": []
            },

            "Pédagogie": {
                "keywords": [
                    "pédagogie",
                    "pedagogie",
                    "enseignement",
                    "teaching",
                    "formation",
                    "training",
                    "learning"
                ],
                "contact_domains": []
            },

            "Uber": {
                "keywords": [
                    "uber",
                    "uber eats",
                    "livraison",
                    "delivery",
                    "chauffeur",
                    "driver"
                ],
                "contact_domains": []
            }
        }


# For detailed examples, see business_rules.example.py
