"""
DOC Ticket Workflow - Complete orchestration for DOC department tickets.

This workflow implements the 8-step process from 00_CHECKLIST_EXECUTION.md:

1. AGENT TRIEUR (Triage with STOP & GO logic)
2. AGENT ANALYSTE (6-source data extraction)
3. AGENT RÉDACTEUR (Response generation with Claude + RAG)
4. CRM Note Creation (before draft)
5. Ticket Update (status, tags)
6. Deal Update (if scenario requires)
7. Draft Creation (Zoho Desk)
8. Final Validation

Gates:
- If AGENT TRIEUR says STOP (routing) → no draft, end workflow
- If AGENT ANALYSTE finds ANCIEN_DOSSIER → internal alert, end workflow
- If data missing → escalate, end workflow
"""
import logging
import sys
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables (for Anthropic API key)
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from src.agents.deal_linking_agent import DealLinkingAgent
from src.agents.examt3p_agent import ExamT3PAgent
from src.agents.dispatcher_agent import TicketDispatcherAgent
from src.agents.crm_update_agent import CRMUpdateAgent
from src.agents.triage_agent import TriageAgent
from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from knowledge_base.scenarios_mapping import (
    detect_scenario_from_text,
    should_stop_workflow,
    requires_crm_update,
    get_crm_update_fields,
    SCENARIOS
)

# State Engine - Architecture State-Driven
from src.state_engine import StateDetector, TemplateEngine, ResponseValidator, CRMUpdater
from src.utils.crm_lookup_helper import enrich_deal_lookups
import anthropic

logger = logging.getLogger(__name__)


class DOCTicketWorkflow:
    """Complete workflow orchestrator for DOC tickets."""

    def __init__(self):
        """Initialize workflow with all required components."""
        self.desk_client = ZohoDeskClient()
        self.crm_client = ZohoCRMClient()
        self.deal_linker = DealLinkingAgent()
        self.examt3p_agent = ExamT3PAgent()
        self.dispatcher = TicketDispatcherAgent()
        self.crm_update_agent = CRMUpdateAgent()
        self.triage_agent = TriageAgent()

        # State Engine - Architecture State-Driven (seul mode supporté)
        self.state_detector = StateDetector()
        self.template_engine = TemplateEngine()
        self.response_validator = ResponseValidator()
        self.state_crm_updater = CRMUpdater(crm_client=self.crm_client)
        # Anthropic client for AI personalization (using Sonnet for best quality)
        self.anthropic_client = anthropic.Anthropic()
        self.personalization_model = "claude-sonnet-4-5-20250929"

        logger.info("✅ DOCTicketWorkflow initialized (State Engine)")

    def process_ticket(
        self,
        ticket_id: str,
        auto_create_draft: bool = False,
        auto_update_crm: bool = False,
        auto_update_ticket: bool = False
    ) -> Dict:
        """
        Process a DOC ticket through the complete workflow.

        Args:
            ticket_id: Zoho Desk ticket ID
            auto_create_draft: Automatically create draft in Zoho Desk
            auto_update_crm: Automatically update CRM deal fields
            auto_update_ticket: Automatically update ticket status/tags

        Returns:
            {
                'success': bool,
                'ticket_id': str,
                'workflow_stage': str,  # Which stage we stopped at
                'triage_result': Dict,
                'analysis_result': Dict,
                'response_result': Dict,
                'crm_note': str,
                'draft_created': bool,
                'errors': List[str]
            }
        """
        logger.info(f"=" * 80)
        logger.info(f"Processing DOC ticket: {ticket_id}")
        logger.info(f"=" * 80)

        result = {
            'success': False,
            'ticket_id': ticket_id,
            'workflow_stage': '',
            'triage_result': {},
            'analysis_result': {},
            'response_result': {},
            'crm_note': '',
            'draft_created': False,
            'crm_updated': False,
            'ticket_updated': False,
            'errors': []
        }

        try:
            # ================================================================
            # STEP 1: AGENT TRIEUR (Triage with STOP & GO)
            # ================================================================
            logger.info("\n1️⃣  AGENT TRIEUR - Triage du ticket...")
            result['workflow_stage'] = 'TRIAGE'

            # auto_transfer=False if we're in dry-run mode (no ticket updates)
            triage_result = self._run_triage(ticket_id, auto_transfer=auto_update_ticket)
            result['triage_result'] = triage_result

            # Check if we should STOP (routing to another department)
            if triage_result.get('action') == 'ROUTE':
                logger.warning(f"⚠️  TRIAGE → ROUTE to {triage_result['target_department']}")
                logger.warning("🛑 STOP WORKFLOW (pas de draft selon règles)")
                result['workflow_stage'] = 'STOPPED_AT_TRIAGE'
                result['success'] = True
                return result

            # Check if SPAM
            if triage_result.get('action') == 'SPAM':
                logger.warning("⚠️  SPAM détecté → Clôturer sans note CRM")
                result['workflow_stage'] = 'STOPPED_SPAM'
                if auto_update_ticket:
                    self.desk_client.update_ticket(ticket_id, {"status": "Closed"})
                result['success'] = True
                return result

            # Check if DUPLICATE UBER 20€
            if triage_result.get('action') == 'DUPLICATE_UBER':
                logger.warning("⚠️  DOUBLON UBER 20€ → Candidat a déjà bénéficié de l'offre")
                result['workflow_stage'] = 'DUPLICATE_UBER_OFFER'
                result['duplicate_deals'] = triage_result.get('duplicate_deals', [])

                # Générer une réponse spécifique pour ce cas
                duplicate_response = self._generate_duplicate_uber_response(
                    ticket_id=ticket_id,
                    triage_result=triage_result
                )
                result['response_result'] = duplicate_response
                result['duplicate_response'] = duplicate_response.get('response_text', '')

                # Créer le brouillon si demandé
                if auto_create_draft and duplicate_response.get('response_text'):
                    try:
                        from config import settings

                        # Récupérer les infos du ticket pour l'email
                        ticket = self.desk_client.get_ticket(ticket_id)
                        to_email = ticket.get('email', '')
                        department = ticket.get('departmentId', '')

                        # Convertir en HTML
                        html_content = duplicate_response['response_text'].replace('\n', '<br>')

                        # Email source selon le département
                        from_email = settings.zoho_desk_email_doc or settings.zoho_desk_email_default

                        logger.info(f"📧 Draft DOUBLON: from={from_email}, to={to_email}")

                        self.desk_client.create_ticket_reply_draft(
                            ticket_id=ticket_id,
                            content=html_content,
                            content_type="html",
                            from_email=from_email,
                            to_email=to_email
                        )
                        logger.info("✅ DRAFT DOUBLON → Brouillon créé dans Zoho Desk")
                        result['draft_created'] = True
                    except Exception as e:
                        logger.error(f"Erreur création brouillon doublon: {e}")
                        result['draft_created'] = False

                result['success'] = True
                return result

            # Check if NEEDS_CLARIFICATION (candidat non trouvé)
            if triage_result.get('action') == 'NEEDS_CLARIFICATION':
                logger.warning("⚠️  CANDIDAT NON TROUVÉ → Demande de clarification")
                result['workflow_stage'] = 'NEEDS_CLARIFICATION'
                result['clarification_reason'] = triage_result.get('clarification_reason')

                # Générer une réponse de clarification
                clarification_response = self._generate_clarification_response(
                    ticket_id=ticket_id,
                    triage_result=triage_result
                )
                result['response_result'] = clarification_response
                result['clarification_response'] = clarification_response.get('response_text', '')

                # Créer le brouillon si demandé
                if auto_create_draft and clarification_response.get('response_text'):
                    try:
                        from config import settings

                        # Récupérer les infos du ticket pour l'email
                        ticket = self.desk_client.get_ticket(ticket_id)
                        to_email = ticket.get('email', '')

                        # Convertir en HTML
                        html_content = clarification_response['response_text'].replace('\n', '<br>')

                        # Email source selon le département
                        from_email = settings.zoho_desk_email_doc or settings.zoho_desk_email_default

                        logger.info(f"📧 Draft CLARIFICATION: from={from_email}, to={to_email}")

                        self.desk_client.create_ticket_reply_draft(
                            ticket_id=ticket_id,
                            content=html_content,
                            content_type="html",
                            from_email=from_email,
                            to_email=to_email
                        )
                        logger.info("✅ DRAFT CLARIFICATION → Brouillon créé dans Zoho Desk")
                        result['draft_created'] = True
                    except Exception as e:
                        logger.error(f"Erreur création brouillon clarification: {e}")
                        result['draft_created'] = False

                result['success'] = True
                return result

            # FEU VERT → Continue
            logger.info("✅ TRIAGE → FEU VERT (continue workflow)")

            # ================================================================
            # STEP 2: AGENT ANALYSTE (6-source data extraction)
            # ================================================================
            logger.info("\n2️⃣  AGENT ANALYSTE - Extraction des données...")
            result['workflow_stage'] = 'ANALYSIS'

            analysis_result = self._run_analysis(ticket_id, triage_result)
            result['analysis_result'] = analysis_result

            # Check VÉRIFICATION #1: Identifiants ExamenT3P
            examt3p_data = analysis_result.get('examt3p_data', {})
            if examt3p_data.get('should_respond_to_candidate'):
                logger.warning("⚠️  IDENTIFIANTS EXAMENT3P INVALIDES OU MANQUANTS")
                logger.info("→ L'agent rédacteur intégrera la demande d'identifiants dans la réponse globale")
            elif not examt3p_data.get('compte_existe'):
                # Pas de compte ExamT3P = cas normal (compte à créer par CAB)
                # Le State Engine détectera l'état approprié (NO_COMPTE_EXAMT3P, UBER_DOCS_MISSING, etc.)
                logger.info("ℹ️  Pas de compte ExamT3P → compte à créer")
            else:
                logger.info(f"✅ Identifiants validés (source: {examt3p_data.get('credentials_source')})")

            # Check VÉRIFICATION #2: Date examen VTC
            date_examen_vtc_result = analysis_result.get('date_examen_vtc_result', {})
            if date_examen_vtc_result.get('should_include_in_response'):
                logger.warning(f"⚠️  DATE EXAMEN VTC - CAS {date_examen_vtc_result.get('case')}: {date_examen_vtc_result.get('case_description')}")
                logger.info("→ L'agent rédacteur intégrera les infos date examen dans la réponse globale")
            else:
                logger.info(f"✅ Date examen VTC OK (CAS {date_examen_vtc_result.get('case', 'N/A')})")

            logger.info("✅ ANALYSIS → Données extraites")

            # ================================================================
            # STEP 3: AGENT RÉDACTEUR (Response generation with Claude + RAG)
            # ================================================================
            logger.info("\n3️⃣  AGENT RÉDACTEUR - Génération de la réponse...")
            result['workflow_stage'] = 'RESPONSE_GENERATION'

            response_result = self._run_response_generation(
                ticket_id=ticket_id,
                triage_result=triage_result,
                analysis_result=analysis_result
            )
            result['response_result'] = response_result

            # Check if workflow should stop based on scenario
            if response_result.get('should_stop_workflow'):
                logger.warning("🛑 Workflow should STOP based on scenario")
                result['workflow_stage'] = 'STOPPED_AT_SCENARIO'
                result['success'] = True
                return result

            logger.info("✅ RESPONSE → Réponse générée")

            # ================================================================
            # STEP 4: CRM NOTE (OBLIGATOIRE avant draft)
            # ================================================================
            logger.info("\n4️⃣  CRM NOTE - Création de la note CRM...")
            result['workflow_stage'] = 'CRM_NOTE'

            crm_note = self._create_crm_note(
                ticket_id=ticket_id,
                triage_result=triage_result,
                analysis_result=analysis_result,
                response_result=response_result
            )
            result['crm_note'] = crm_note

            if auto_update_crm and analysis_result.get('deal_id'):
                # Add note to deal
                self.crm_client.add_deal_note(
                    deal_id=analysis_result['deal_id'],
                    note_title="Note automatique - Ticket DOC",
                    note_content=crm_note
                )
                logger.info("✅ CRM NOTE → Note ajoutée au deal")
            else:
                logger.info("✅ CRM NOTE → Note générée (pas d'auto-update)")

            # ================================================================
            # STEP 5: TICKET UPDATE (status, tags)
            # ================================================================
            logger.info("\n5️⃣  TICKET UPDATE - Mise à jour du ticket...")
            result['workflow_stage'] = 'TICKET_UPDATE'

            if auto_update_ticket:
                ticket_updates = self._prepare_ticket_updates(response_result)
                if ticket_updates:
                    self.desk_client.update_ticket(ticket_id, ticket_updates)
                    logger.info(f"✅ TICKET UPDATE → {len(ticket_updates)} champs mis à jour")
                    result['ticket_updated'] = True
            else:
                logger.info("✅ TICKET UPDATE → Préparé (pas d'auto-update)")

            # ================================================================
            # STEP 6: DEAL UPDATE (via CRMUpdateAgent)
            # ================================================================
            logger.info("\n6️⃣  DEAL UPDATE - Mise à jour CRM via CRMUpdateAgent...")
            result['workflow_stage'] = 'DEAL_UPDATE'

            # Check both scenario flag and AI-extracted updates
            ai_updates = response_result.get('crm_updates', {}).copy() if response_result.get('crm_updates') else {}

            # D-8: Si deadline passée avant paiement, injecter la nouvelle date d'examen
            date_examen_vtc_result = analysis_result.get('date_examen_vtc_result', {})
            if date_examen_vtc_result.get('deadline_passed_reschedule') and date_examen_vtc_result.get('new_exam_date'):
                new_date = date_examen_vtc_result['new_exam_date']
                logger.info(f"  📅 D-8: Deadline passée → inscription sur prochaine date: {new_date}")
                ai_updates['Date_examen_VTC'] = new_date
                result['deadline_passed_reschedule'] = True
                result['new_exam_date'] = new_date

            has_ai_updates = bool(ai_updates)
            scenario_requires_update = response_result.get('requires_crm_update')

            if has_ai_updates or scenario_requires_update:
                if scenario_requires_update:
                    logger.info(f"Champs à updater (scénario): {response_result.get('crm_update_fields', [])}")
                if has_ai_updates:
                    logger.info(f"Champs à updater: {ai_updates}")

                if auto_update_crm and analysis_result.get('deal_id'):
                    # Utiliser CRMUpdateAgent pour centraliser la logique
                    crm_update_result = self.crm_update_agent.update_from_ticket_response(
                        deal_id=analysis_result['deal_id'],
                        ai_updates=ai_updates,
                        deal_data=analysis_result.get('deal_data', {}),
                        session_data=analysis_result.get('session_data', {}),
                        ticket_id=ticket_id
                    )

                    if crm_update_result.get('updates_applied'):
                        logger.info(f"✅ DEAL UPDATE → {len(crm_update_result['updates_applied'])} champs mis à jour: {list(crm_update_result['updates_applied'].keys())}")
                        result['crm_updated'] = True

                    if crm_update_result.get('updates_blocked'):
                        logger.warning(f"🔒 DEAL UPDATE → {len(crm_update_result['updates_blocked'])} champs bloqués (règles métier)")
                        result['crm_updates_blocked'] = crm_update_result['updates_blocked']

                    if crm_update_result.get('errors'):
                        for error in crm_update_result['errors']:
                            logger.warning(f"⚠️ DEAL UPDATE: {error}")
                        result['crm_update_error'] = '; '.join(crm_update_result['errors'])

                    if not crm_update_result.get('updates_applied') and not crm_update_result.get('updates_blocked'):
                        logger.info("✅ DEAL UPDATE → Aucune mise à jour après mapping")
                else:
                    logger.info("✅ DEAL UPDATE → Préparé (pas d'auto-update)")
            else:
                logger.info("✅ DEAL UPDATE → Non requis pour ce scénario")

            # ================================================================
            # STEP 7: DRAFT CREATION (Zoho Desk)
            # ================================================================
            logger.info("\n7️⃣  DRAFT CREATION - Création du brouillon...")
            result['workflow_stage'] = 'DRAFT_CREATION'

            if auto_create_draft:
                # Convertir markdown en HTML pour des liens cliquables
                draft_content = response_result.get('response_text', '')
                import re
                html_content = draft_content

                # Convertir liens markdown [text](url) → <a href="url">text</a>
                html_content = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html_content)
                # Convertir **gras** → <strong>gras</strong>
                html_content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html_content)
                # Convertir ## headers → <h3>
                html_content = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
                # Convertir sauts de ligne en <br>
                html_content = html_content.replace('\n\n', '</p><p>').replace('\n', '<br>')
                # Wrapper dans des paragraphes
                html_content = f'<p>{html_content}</p>'

                try:
                    # Récupérer from_email selon le département
                    from config import settings

                    # Récupérer le ticket pour le département et l'email destinataire
                    ticket = self.desk_client.get_ticket(ticket_id)
                    department = ticket.get('departmentId') or ticket.get('department', {}).get('name', '')
                    to_email = ticket.get('email')

                    # Mapping département → email expéditeur
                    dept_email_map = {
                        'DOC': settings.zoho_desk_email_doc,
                        'Contact': settings.zoho_desk_email_contact,
                        'Comptabilité': settings.zoho_desk_email_compta,
                    }

                    # Déterminer l'email selon le département
                    from_email = dept_email_map.get(department) or settings.zoho_desk_email_doc or settings.zoho_desk_email_default

                    logger.info(f"📧 Draft: from={from_email}, to={to_email}, dept={department}")

                    self.desk_client.create_ticket_reply_draft(
                        ticket_id=ticket_id,
                        content=html_content,
                        content_type="html",
                        from_email=from_email,
                        to_email=to_email
                    )
                    logger.info("✅ DRAFT CREATION → Brouillon créé dans Zoho Desk")
                    result['draft_created'] = True
                except Exception as draft_error:
                    logger.warning(f"⚠️ Impossible de créer le draft dans Zoho Desk: {draft_error}")
                    logger.info("📋 La réponse est disponible ci-dessus pour copier-coller manuellement")
                    result['draft_created'] = False

                # Note: la note CRM consolidée est créée au STEP 4
            else:
                logger.info("✅ DRAFT CREATION → Préparé (pas d'auto-create)")

            # ================================================================
            # STEP 8: FINAL VALIDATION
            # ================================================================
            logger.info("\n8️⃣  FINAL VALIDATION - Vérifications finales...")
            result['workflow_stage'] = 'COMPLETED'

            validation_errors = []

            # Check mandatory blocks compliance
            for scenario_id, validation in response_result.get('validation', {}).items():
                if not validation['compliant']:
                    validation_errors.append(
                        f"Scenario {scenario_id}: missing {validation['missing_blocks']}"
                    )
                if validation['forbidden_terms_found']:
                    validation_errors.append(
                        f"Forbidden terms used: {validation['forbidden_terms_found']}"
                    )

            if validation_errors:
                logger.warning(f"⚠️  Validation warnings: {validation_errors}")
                result['errors'].extend(validation_errors)
            else:
                logger.info("✅ VALIDATION → Tous les contrôles passés")

            # ================================================================
            # STEP 8b: TRANSFER TO DOCS CAB (si VTC hors partenariat)
            # ================================================================
            # Les deals VTC classiques (Amount != 20€) doivent être transférés
            # vers DOCS CAB après création du draft
            deal_amount = analysis_result.get('deal_data', {}).get('Amount', 0)
            is_vtc_hors_partenariat = (deal_amount != 0 and deal_amount != 20)

            if is_vtc_hors_partenariat and result.get('draft_created') and auto_update_ticket:
                logger.info("\n8️⃣b TRANSFER DOCS CAB - Deal VTC classique (hors partenariat)...")
                try:
                    self.desk_client.move_ticket_to_department(ticket_id, "DOCS CAB")
                    logger.info("✅ TRANSFER → Ticket transféré vers DOCS CAB")
                    result['transferred_to'] = "DOCS CAB"
                except Exception as transfer_error:
                    logger.warning(f"⚠️ Impossible de transférer vers DOCS CAB: {transfer_error}")
                    result['transfer_error'] = str(transfer_error)
            elif is_vtc_hors_partenariat and not auto_update_ticket:
                logger.info("\n8️⃣b TRANSFER DOCS CAB → Préparé (pas d'auto-update)")
                result['transfer_prepared'] = "DOCS CAB"

            result['success'] = True
            logger.info("\n" + "=" * 80)
            logger.info("✅ WORKFLOW COMPLET TERMINÉ")
            logger.info("=" * 80)

            return result

        except Exception as e:
            logger.error(f"❌ Error in workflow: {e}")
            result['errors'].append(str(e))
            import traceback
            traceback.print_exc()
            return result

    def _run_triage(self, ticket_id: str, auto_transfer: bool = True) -> Dict:
        """
        Run AGENT TRIEUR logic with AI-based triage.

        Uses TriageAgent (Claude) for intelligent context-aware routing:
        - Comprend le SENS du message, pas juste les mots-clés
        - Évite les faux positifs ("j'ai envoyé mes documents" ≠ Refus CMA)
        - Deal-based routing (Uber €20, CMA, etc.)
        - Evalbox status (Refusé CMA, Documents manquants, etc.)

        Args:
            ticket_id: Ticket to triage
            auto_transfer: If True, automatically transfer ticket to target department

        Returns:
            {
                'action': 'GO' | 'ROUTE' | 'SPAM',
                'target_department': str (if ROUTE),
                'reason': str,
                'transferred': bool (if auto_transfer and ROUTE)
            }
        """
        from src.utils.text_utils import get_clean_thread_content

        # Get ticket details
        ticket = self.desk_client.get_ticket(ticket_id)
        subject = ticket.get('subject', '')
        current_department = ticket.get('departmentId') or ticket.get('department', {}).get('name', 'DOC')

        # Get threads for content analysis
        # API returns newest first, but we want the most MEANINGFUL customer message
        # Skip: feedback/ratings, very short messages, "lisez mon mail précédent"
        threads = self.desk_client.get_all_threads_with_full_content(ticket_id)
        last_thread_content = ""
        min_meaningful_length = 80  # Ignore very short messages

        # Patterns to skip (feedback, automated, follow-ups asking to read previous)
        skip_patterns = [
            "a évalué la réponse",
            "a evalué la reponse",
            "lisez mon mail",
            "lire mon mail",
            "voir mon message",
            "mon précédent mail",
            "mon precedent mail",
        ]

        for thread in threads:
            if thread.get('direction') == 'in':
                content = get_clean_thread_content(thread)
                content_lower = content.lower()

                # Skip feedback/automated messages
                if any(pattern in content_lower for pattern in skip_patterns):
                    continue

                # Take the first customer message that's meaningful (>80 chars)
                if len(content) >= min_meaningful_length:
                    last_thread_content = content
                    break
                # Fallback to any customer message if none are long enough
                elif not last_thread_content:
                    last_thread_content = content

        # Default result
        triage_result = {
            'action': 'GO',
            'target_department': 'DOC',
            'reason': 'Ticket reste dans DOC',
            'transferred': False,
            'current_department': current_department,
            'method': 'default'
        }

        # Rule #1: SPAM detection (simple keywords - pas besoin d'IA)
        spam_keywords = ['viagra', 'casino', 'lottery', 'prince nigerian', 'bitcoin gratuit']
        combined_content = (subject + ' ' + last_thread_content).lower()
        if any(kw in combined_content for kw in spam_keywords):
            triage_result['action'] = 'SPAM'
            triage_result['reason'] = 'Spam détecté'
            triage_result['method'] = 'spam_filter'
            logger.info("🚫 SPAM détecté → Clôturer sans réponse")
            return triage_result

        # Rule #2: Get deals from CRM for context
        linking_result = self.deal_linker.process({"ticket_id": ticket_id})
        all_deals = linking_result.get('all_deals', [])
        selected_deal = linking_result.get('selected_deal') or linking_result.get('deal') or {}

        # Rule #2.5: VÉRIFICATION DOUBLON UBER 20€
        # Si le candidat a déjà bénéficié de l'offre Uber 20€, il ne peut pas en bénéficier à nouveau
        if linking_result.get('has_duplicate_uber_offer'):
            duplicate_deals = linking_result.get('duplicate_deals', [])
            logger.warning(f"⚠️ DOUBLON UBER 20€ DÉTECTÉ: {len(duplicate_deals)} opportunités 20€ GAGNÉ")
            triage_result['action'] = 'DUPLICATE_UBER'
            triage_result['reason'] = f"Candidat a déjà bénéficié de l'offre Uber 20€ ({len(duplicate_deals)} opportunités GAGNÉ)"
            triage_result['method'] = 'duplicate_detection'
            triage_result['duplicate_deals'] = duplicate_deals
            triage_result['selected_deal'] = selected_deal
            logger.info("🚫 DOUBLON UBER → Workflow spécifique (pas de gratuité)")
            return triage_result

        # Rule #2.6: CANDIDAT NON TROUVÉ - CLARIFICATION NÉCESSAIRE
        # Si c'est un nouveau ticket et qu'on ne trouve pas le candidat dans le CRM,
        # demander des informations pour l'identifier
        if linking_result.get('needs_clarification'):
            logger.warning(f"⚠️ CANDIDAT NON TROUVÉ - Clarification nécessaire")
            triage_result['action'] = 'NEEDS_CLARIFICATION'
            triage_result['reason'] = f"Candidat non trouvé dans le CRM avec l'email {linking_result.get('email', 'inconnu')}"
            triage_result['method'] = 'candidate_not_found'
            triage_result['clarification_reason'] = linking_result.get('clarification_reason', 'candidate_not_found')
            triage_result['email_searched'] = linking_result.get('email')
            triage_result['alternative_email_used'] = linking_result.get('alternative_email_used')
            logger.info("❓ CLARIFICATION → Demander coordonnées au candidat")
            return triage_result

        # If no deals found, also check by email directly
        if not all_deals:
            email = ticket.get('email', '')
            if email:
                try:
                    all_deals = self.crm_client.search_deals_by_email(email) or []
                    if all_deals:
                        selected_deal = all_deals[0]
                except Exception as e:
                    logger.warning(f"Erreur recherche deals: {e}")
                    all_deals = []

        # Rule #3: UTILISER L'IA POUR LE TRIAGE INTELLIGENT
        # L'IA comprend le contexte et évite les faux positifs

        # IMPORTANT: Enrichir le deal avec la vraie date d'examen (lookup → module)
        # Les champs lookup contiennent juste {'name': '...', 'id': '...'}, pas les vraies données
        if selected_deal and selected_deal.get('Date_examen_VTC'):
            date_lookup = selected_deal.get('Date_examen_VTC')
            if isinstance(date_lookup, dict) and date_lookup.get('id'):
                try:
                    exam_session = self.crm_client.get_record('Dates_Examens_VTC_TAXI', date_lookup['id'])
                    if exam_session:
                        selected_deal['_real_exam_date'] = exam_session.get('Date_Examen')
                        selected_deal['_real_exam_departement'] = exam_session.get('Departement')
                        logger.info(f"  📅 Date examen enrichie: {selected_deal['_real_exam_date']} (dept {selected_deal['_real_exam_departement']})")
                except Exception as e:
                    logger.warning(f"  ⚠️ Impossible d'enrichir Date_examen_VTC: {e}")

        logger.info("🤖 Triage IA en cours...")
        ai_triage = self.triage_agent.triage_ticket(
            ticket_subject=subject,
            thread_content=last_thread_content,
            deal_data=selected_deal,
            current_department='DOC'
        )

        logger.info(f"  🤖 Résultat IA: {ai_triage['action']} → {ai_triage['target_department']} ({ai_triage['reason']})")
        logger.info(f"  🤖 Confiance: {ai_triage['confidence']:.0%} | Méthode: {ai_triage['method']}")

        # Appliquer le résultat de l'IA
        triage_result['action'] = ai_triage['action']
        triage_result['target_department'] = ai_triage['target_department']
        triage_result['reason'] = ai_triage['reason']
        triage_result['method'] = ai_triage['method']
        triage_result['confidence'] = ai_triage['confidence']

        # Copier l'intention détectée et son contexte (pour State Engine)
        triage_result['detected_intent'] = ai_triage.get('detected_intent')
        triage_result['intent_context'] = ai_triage.get('intent_context', {})
        # Multi-intentions
        triage_result['primary_intent'] = ai_triage.get('primary_intent')
        triage_result['secondary_intents'] = ai_triage.get('secondary_intents', [])

        # Log intention si détectée
        if triage_result.get('detected_intent'):
            logger.info(f"  🎯 Intention: {triage_result['detected_intent']}")
            if triage_result.get('intent_context', {}).get('mentions_force_majeure'):
                logger.info(f"  ⚠️ Force majeure: {triage_result['intent_context'].get('force_majeure_type')}")

        # Determine action based on AI recommendation
        if ai_triage['action'] == 'ROUTE' and ai_triage['target_department'] != 'DOC':
            # Auto-transfer if enabled
            if auto_transfer:
                logger.info(f"🔄 Transfert automatique vers {ai_triage['target_department']}...")
                try:
                    # Use dispatcher to reassign
                    transfer_success = self.dispatcher._reassign_ticket(ticket_id, ai_triage['target_department'])
                    triage_result['transferred'] = transfer_success
                    if transfer_success:
                        logger.info(f"✅ Ticket transféré vers {ai_triage['target_department']}")
                    else:
                        logger.warning(f"⚠️ Échec transfert vers {ai_triage['target_department']}")
                except Exception as e:
                    logger.error(f"❌ Erreur transfert: {e}")
                    triage_result['transferred'] = False
        else:
            # Stay in DOC
            triage_result['action'] = 'GO'
            triage_result['target_department'] = 'DOC'
            triage_result['reason'] = 'Ticket DOC valide - continuer workflow'

        return triage_result

    def _run_analysis(self, ticket_id: str, triage_result: Dict) -> Dict:
        """
        Run AGENT ANALYSTE logic - extract data from 6 sources.

        Sources:
        1. CRM Zoho (contact, deal)
        2. ExamenT3P (documents, paiement, compte)
        3. Evalbox (Google Sheet - eligibility)
        4. Sessions sheet (SESSIONSUBER2026.xlsx)
        5. Ticket threads (conversation history)
        6. Google Drive (if needed)

        Returns:
            {
                'contact_data': Dict,
                'deal_id': str,
                'deal_data': Dict,
                'examt3p_data': Dict,
                'evalbox_data': Dict,
                'session_data': Dict,
                'ancien_dossier': bool
            }
        """
        # Get ticket
        ticket = self.desk_client.get_ticket(ticket_id)
        email = ticket.get('email', '')

        # Source 1: CRM - Find contact and deal
        logger.info("  📊 Source 1/6: CRM Zoho...")

        # Use DealLinkingAgent.process() to find deal
        linking_result = self.deal_linker.process({"ticket_id": ticket_id})

        deal_id = linking_result.get('deal_id')
        deal_data = linking_result.get('selected_deal') or linking_result.get('deal') or {}

        # ================================================================
        # RÉCUPÉRER LES DONNÉES DU CONTACT LIÉ (First_Name, Last_Name)
        # ================================================================
        contact_data = {}
        contact_id = deal_data.get('Contact_Name', {}).get('id') if deal_data else None
        if contact_id:
            try:
                contact_data = self.crm_client.get_contact(contact_id)
                logger.info(f"  ✅ Contact récupéré: {contact_data.get('First_Name', '')} {contact_data.get('Last_Name', '')}")
            except Exception as e:
                logger.warning(f"  ⚠️  Erreur récupération contact: {e}")

        if email:
            contact_data['email'] = email
            contact_data['contact_id'] = contact_id

        # ================================================================
        # ENRICHIR LES LOOKUPS CRM (Date_examen_VTC et Session)
        # ================================================================
        # Utilise le helper centralisé pour récupérer les vraies données
        # des modules Zoho CRM au lieu de parser le champ "name"
        lookup_cache = {}  # Cache partagé pour éviter les appels répétés
        enriched_lookups = enrich_deal_lookups(self.crm_client, deal_data, lookup_cache)

        # Extraire la date d'examen enrichie pour compatibilité
        date_examen_vtc_value = enriched_lookups.get('date_examen')
        if not date_examen_vtc_value:
            # Fallback: essayer de récupérer depuis le lookup name (compatibilité legacy)
            date_examen_lookup = deal_data.get('Date_examen_VTC')
            if date_examen_lookup:
                if isinstance(date_examen_lookup, dict):
                    date_examen_vtc_value = date_examen_lookup.get('name')
                else:
                    date_examen_vtc_value = date_examen_lookup
        logger.debug(f"  📅 Date_examen_VTC extraite: {date_examen_vtc_value}")

        if not deal_id:
            logger.warning("  ⚠️  No deal found for this ticket")

        # Source 2: ExamenT3P avec gestion complète des identifiants
        logger.info("  🌐 Source 2/6: ExamenT3P...")

        # Import du helper pour la gestion des identifiants
        from src.utils.examt3p_credentials_helper import get_credentials_with_validation
        from src.utils.date_examen_vtc_helper import analyze_exam_date_situation

        # Récupérer les threads du ticket avec contenu complet
        threads_data = self.desk_client.get_all_threads_with_full_content(ticket_id)

        # Workflow complet de validation des identifiants
        credentials_result = get_credentials_with_validation(
            deal_data=deal_data,
            threads=threads_data,
            crm_client=self.crm_client,
            deal_id=deal_id,
            auto_update_crm=True  # Toujours mettre à jour le CRM si identifiants trouvés dans mails
        )

        # Initialiser examt3p_data
        examt3p_data = {
            'compte_existe': False,
            'identifiant': credentials_result.get('identifiant'),
            'mot_de_passe': credentials_result.get('mot_de_passe'),  # Sera masqué dans les logs
            'credentials_source': credentials_result.get('credentials_source'),
            'connection_test_success': credentials_result.get('connection_test_success'),
            'documents': [],
            'documents_manquants': [],
            'paiement_cma_status': 'N/A',
            'should_respond_to_candidate': credentials_result.get('should_respond_to_candidate', False),
            'candidate_response_message': credentials_result.get('candidate_response_message'),
            # Flag compte personnel potentiel
            'potential_personal_account': credentials_result.get('potential_personal_account', False),
            'potential_personal_email': credentials_result.get('potential_personal_email'),
            'personal_account_warning': credentials_result.get('personal_account_warning')
        }

        # ================================================================
        # ALERTE COMPTE PERSONNEL POTENTIEL
        # ================================================================
        if credentials_result.get('potential_personal_account'):
            personal_email = credentials_result.get('potential_personal_email', 'inconnu')
            logger.warning(f"  🚨 COMPTE PERSONNEL POTENTIEL: {personal_email}")
            logger.warning(f"     → Le candidat pourrait voir un statut différent sur son compte perso")
            logger.warning(f"     → La réponse doit clarifier d'utiliser UNIQUEMENT le compte CAB")

        # ================================================================
        # ALERTE DOUBLON DE PAIEMENT
        # ================================================================
        if credentials_result.get('duplicate_payment_alert'):
            logger.error("  🚨🚨🚨 ALERTE CRITIQUE: DEUX COMPTES EXAMT3P PAYÉS DÉTECTÉS! 🚨🚨🚨")
            duplicate_accounts = credentials_result.get('duplicate_accounts', {})
            logger.error(f"     → Compte CRM: {duplicate_accounts.get('crm', {}).get('identifiant')}")
            logger.error(f"     → Compte Candidat: {duplicate_accounts.get('thread', {}).get('identifiant')}")
            logger.error("     → INTERVENTION MANUELLE REQUISE - Vérifier les paiements!")

            # Ajouter le flag dans examt3p_data pour visibilité
            examt3p_data['duplicate_payment_alert'] = True
            examt3p_data['duplicate_accounts'] = duplicate_accounts

            # Créer une note CRM d'alerte
            try:
                alert_content = f"""⚠️ ATTENTION - INTERVENTION MANUELLE REQUISE ⚠️

Deux comptes ExamenT3P fonctionnels ont été détectés pour ce candidat, et les deux semblent avoir été payés.

📧 Compte 1 (CRM): {duplicate_accounts.get('crm', {}).get('identifiant')}
📧 Compte 2 (Candidat): {duplicate_accounts.get('thread', {}).get('identifiant')}

✅ Action requise:
1. Vérifier les deux comptes sur ExamenT3P
2. Identifier lequel a réellement été payé par CAB Formations
3. Si double paiement confirmé, demander remboursement
4. Mettre à jour le CRM avec le bon compte

⚠️ Risque: Paiement en double des frais CMA (60€)"""

                self.crm_client.add_deal_note(
                    deal_id=deal_id,
                    note_title="🚨 ALERTE: DOUBLE COMPTE EXAMT3P PAYÉ",
                    note_content=alert_content
                )
                logger.info("  ✅ Note CRM d'alerte créée")
            except Exception as e:
                logger.error(f"  ❌ Erreur création note CRM d'alerte: {e}")

        # Info si basculement vers compte payé du candidat
        if credentials_result.get('switched_to_paid_account'):
            logger.info("  🔄 Basculement vers le compte ExamT3P déjà payé du candidat")
            examt3p_data['switched_to_paid_account'] = True

        # Si les identifiants sont valides, procéder à l'extraction
        if credentials_result.get('connection_test_success'):
            logger.info(f"  ✅ Identifiants validés (source: {credentials_result['credentials_source']})")

            if credentials_result.get('crm_updated'):
                logger.info("  ✅ CRM mis à jour avec les nouveaux identifiants")

            try:
                # Extraction complète des données ExamenT3P
                logger.info("  📥 Extraction des données ExamenT3P...")
                examt3p_result = self.examt3p_agent.process({
                    'username': credentials_result['identifiant'],
                    'password': credentials_result['mot_de_passe']
                })

                if examt3p_result.get('success'):
                    # Fusionner les données extraites avec examt3p_data
                    examt3p_data.update(examt3p_result)
                    examt3p_data['compte_existe'] = True
                    logger.info("  ✅ Données ExamenT3P extraites avec succès")
                else:
                    logger.warning(f"  ⚠️  Échec extraction ExamenT3P: {examt3p_result.get('error')}")
                    examt3p_data['extraction_error'] = examt3p_result.get('error')

            except Exception as e:
                logger.error(f"  ❌ Erreur lors de l'extraction ExamenT3P: {e}")
                examt3p_data['extraction_error'] = str(e)

        elif credentials_result.get('credentials_found'):
            # Identifiants trouvés mais connexion échouée
            logger.warning(f"  ❌ Identifiants trouvés mais connexion échouée: {credentials_result.get('connection_error')}")
            examt3p_data['extraction_error'] = f"Connexion échouée: {credentials_result.get('connection_error')}"

        else:
            # Identifiants non trouvés
            logger.warning("  ⚠️  Identifiants ExamenT3P introuvables")
            examt3p_data['extraction_error'] = "Identifiants non trouvés dans le CRM ni dans les threads"

        # Source 3: Evalbox (Google Sheet)
        logger.info("  📊 Source 3/6: Evalbox...")
        evalbox_data = {
            'eligible_uber': None,
            'scope': None
        }
        # TODO: Query Evalbox Google Sheet

        # Source 4: Sessions (CRM module Sessions1)
        logger.info("  📅 Source 4/6: Sessions...")
        session_data = {}
        # Les sessions seront récupérées après l'analyse date_examen_vtc

        # Source 5: Ticket threads (déjà récupérés pour ExamenT3P)
        logger.info("  💬 Source 5/6: Ticket threads...")
        # threads déjà récupérés plus haut pour la validation des identifiants

        # Source 6: Google Drive (if needed)
        logger.info("  📁 Source 6/6: Google Drive...")
        # Only if specific documents needed

        # ================================================================
        # VÉRIFICATION ÉLIGIBILITÉ UBER 20€ (PRIORITAIRE)
        # ================================================================
        # Pour les candidats Uber 20€, ils doivent d'abord:
        # 1. Envoyer leurs documents (Date_Dossier_re_u non vide)
        # 2. Passer le test de sélection (Date_test_selection non vide)
        # Si ces étapes ne sont pas complétées, on ne peut pas les inscrire à l'examen
        from src.utils.uber_eligibility_helper import analyze_uber_eligibility
        from src.utils.examt3p_crm_sync import sync_examt3p_to_crm, sync_exam_date_from_examt3p
        from src.utils.ticket_info_extractor import extract_confirmations_from_threads

        # ================================================================
        # SYNC EXAMT3P → CRM (AVANT toute analyse)
        # ================================================================
        # ExamT3P est la SOURCE DE VÉRITÉ - on synchronise d'abord vers CRM
        sync_result = None
        if examt3p_data.get('compte_existe') and deal_id:
            logger.info("  🔄 Synchronisation ExamT3P → CRM...")
            sync_result = sync_examt3p_to_crm(
                deal_id=deal_id,
                deal_data=deal_data,
                examt3p_data=examt3p_data,
                crm_client=self.crm_client,
                dry_run=False
            )
            if sync_result.get('crm_updated'):
                logger.info("  ✅ CRM synchronisé avec ExamT3P")
                # Recharger deal_data après mise à jour
                updated_deal = self.crm_client.get_deal(deal_id)
                if updated_deal:
                    deal_data = updated_deal
            # Note: sync_result sera inclus dans la note consolidée finale

            # ================================================================
            # SYNC DATE D'EXAMEN DEPUIS EXAMT3P
            # ================================================================
            # Si la date d'examen ExamT3P diffère du CRM → mettre à jour automatiquement
            # (sauf si règle de blocage: VALIDE CMA + clôture passée)
            logger.info("  📅 Synchronisation date d'examen ExamT3P → CRM...")
            date_sync_result = sync_exam_date_from_examt3p(
                deal_id=deal_id,
                deal_data=deal_data,
                examt3p_data=examt3p_data,
                crm_client=self.crm_client,
                dry_run=False
            )

            if date_sync_result.get('date_changed'):
                logger.info(f"  ✅ Date_examen_VTC mis à jour: {date_sync_result['old_date'] or 'VIDE'} → {date_sync_result['new_date']}")
                # Recharger deal_data après mise à jour
                updated_deal = self.crm_client.get_deal(deal_id)
                if updated_deal:
                    deal_data = updated_deal
                # Ajouter au sync_result pour la note CRM
                sync_result['date_sync'] = date_sync_result
            elif date_sync_result.get('blocked'):
                logger.warning(f"  🔒 Date_examen_VTC non modifiée: {date_sync_result['blocked_reason']}")
                sync_result['date_sync'] = date_sync_result
            elif date_sync_result.get('error'):
                logger.warning(f"  ⚠️ Erreur sync date: {date_sync_result['error']}")

        # ================================================================
        # EXTRACTION CONFIRMATIONS DU TICKET
        # ================================================================
        ticket_confirmations = None
        if threads_data and deal_id:
            logger.info("  📥 Extraction des confirmations du ticket...")
            ticket_confirmations = extract_confirmations_from_threads(
                threads=threads_data,
                deal_data=deal_data
            )
            if ticket_confirmations.get('raw_confirmations'):
                logger.info(f"  📋 {len(ticket_confirmations['raw_confirmations'])} confirmation(s) détectée(s)")

            # Alerter sur les mises à jour bloquées (règle critique)
            if ticket_confirmations.get('blocked_updates'):
                for blocked in ticket_confirmations['blocked_updates']:
                    logger.warning(f"  🔒 BLOCAGE: {blocked['reason']}")

        logger.info("  🚗 Vérification éligibilité Uber 20€...")
        uber_eligibility_result = analyze_uber_eligibility(deal_data)

        # ================================================================
        # FLAG: Blocage dates/sessions si CAS A ou B
        # A = documents non envoyés → BLOCAGE (pas d'info candidat)
        # B = test sélection non passé → BLOCAGE (workflow pas complet)
        # D = Compte_Uber non vérifié → ALERTE (peut être résolu)
        # E = Non éligible selon Uber → ALERTE (peut être résolu)
        # ================================================================
        uber_case_blocks_dates = False
        uber_case_alert = None  # Pour CAS D/E: alerte à inclure dans la réponse normale
        if uber_eligibility_result.get('is_uber_20_deal'):
            uber_case = uber_eligibility_result.get('case')
            blocking_cases = ['A', 'B']  # Seuls A et B bloquent
            alert_cases = ['D', 'E']  # D et E = alerte sans blocage

            if uber_case in blocking_cases:
                logger.warning(f"  🚨 CAS {uber_case}: {uber_eligibility_result['case_description']}")
                logger.warning("  ⛔ BLOCAGE DATES/SESSIONS: Candidat doit résoudre le problème")
                uber_case_blocks_dates = True
            elif uber_case in alert_cases:
                logger.warning(f"  ⚠️ CAS {uber_case}: {uber_eligibility_result['case_description']}")
                logger.info("  📝 Traitement normal + ALERTE Uber à inclure dans la réponse")
                uber_case_alert = {
                    'case': uber_case,
                    'description': uber_eligibility_result.get('case_description', ''),
                    'response_message': uber_eligibility_result.get('response_message', '')
                }
            else:
                logger.info("  ✅ Candidat Uber éligible - peut être inscrit à l'examen")
        else:
            logger.info("  ℹ️ Pas une opportunité Uber 20€")

        # ================================================================
        # RÈGLE: Si pas de Date_Dossier_re_u → pas de dates/sessions
        # ================================================================
        # IMPORTANT: Cette règle ne s'applique QU'AUX DEALS 20€ (Uber)
        # Pour les deals classiques (1299€, etc.), pas besoin de Date_Dossier_re_u
        dossier_not_received_blocks_dates = False
        deal_amount = deal_data.get('Amount', 0)
        is_uber_20_deal = (deal_amount == 20)

        if is_uber_20_deal:
            date_dossier_recu = deal_data.get('Date_Dossier_re_u')
            evalbox_status = deal_data.get('Evalbox', '')

            # Statuts Evalbox qui prouvent que le dossier a été traité
            ADVANCED_EVALBOX_STATUSES = {
                "VALIDE CMA", "Convoc CMA reçue", "Dossier Synchronisé",
                "Pret a payer", "Refusé CMA"
            }

            if not date_dossier_recu:
                if evalbox_status in ADVANCED_EVALBOX_STATUSES:
                    logger.info(f"  ℹ️ Deal 20€: Date_Dossier_re_u vide MAIS Evalbox='{evalbox_status}' → OK")
                else:
                    logger.warning("  🚨 Deal 20€: PAS DE DATE_DOSSIER_RECU")
                    logger.warning("  ⛔ BLOCAGE: On ne peut pas proposer de dates sans dossier")
                    dossier_not_received_blocks_dates = True
        else:
            logger.info(f"  ℹ️ Deal {deal_amount}€ (non-Uber): règle Date_Dossier_re_u non applicable")

        # ================================================================
        # RÈGLE CRITIQUE: SI IDENTIFIANTS NON ACCESSIBLES → SKIP DATES/SESSIONS
        # ================================================================
        # On ne peut RIEN faire tant qu'on n'a pas accès au compte ExamT3P
        # Cas possibles:
        # 1. Identifiants trouvés mais connexion échouée → demander réinitialisation
        # 2. Création de compte demandée mais pas d'identifiants → relancer le candidat
        skip_date_session_analysis = False
        skip_reason = None

        # Raison 1: Identifiants non accessibles
        # EXCEPTION: Pour les candidats Uber ÉLIGIBLES, CAB gère le compte pour eux
        # Donc on NE BLOQUE PAS sur les identifiants manquants
        is_uber_eligible = uber_eligibility_result.get('is_eligible', False)
        has_exam_date = bool(deal_data.get('Date_examen_VTC'))

        if examt3p_data.get('should_respond_to_candidate') and not examt3p_data.get('compte_existe'):
            if is_uber_eligible or has_exam_date:
                # Uber éligible ou date déjà assignée → on continue l'analyse
                logger.info("  ℹ️ Identifiants manquants MAIS candidat Uber éligible ou date assignée")
                logger.info("  → On continue l'analyse dates/sessions (CAB gère le compte)")
                # Ne pas skip, on répond à la question du candidat
            elif examt3p_data.get('credentials_request_sent'):
                logger.warning("  🚨 DEMANDE D'IDENTIFIANTS DÉJÀ ENVOYÉE MAIS PAS DE RÉPONSE")
                logger.warning("  → La réponse doit confirmer que c'est normal et redemander les identifiants")
                skip_date_session_analysis = True
                skip_reason = 'credentials_invalid'
            elif examt3p_data.get('account_creation_requested'):
                logger.warning("  🚨 CRÉATION DE COMPTE DEMANDÉE MAIS PAS D'IDENTIFIANTS REÇUS")
                logger.warning("  → La réponse doit relancer le candidat sur la création de compte")
                skip_date_session_analysis = True
                skip_reason = 'credentials_invalid'
            else:
                logger.warning("  🚨 IDENTIFIANTS INVALIDES → SKIP analyse dates/sessions")
                logger.warning("  → La réponse doit UNIQUEMENT demander les bons identifiants")
                skip_date_session_analysis = True
                skip_reason = 'credentials_invalid'

        # Raison 2: CAS A, B, D ou E (problème Uber - vérification/éligibilité)
        if uber_case_blocks_dates:
            skip_date_session_analysis = True
            uber_case = uber_eligibility_result.get('case', '?')
            skip_reason = skip_reason or f'uber_case_{uber_case}'
            logger.warning(f"  → La réponse doit UNIQUEMENT traiter CAS {uber_case}: {uber_eligibility_result.get('case_description', '')}")

        # Raison 3: Dossier non reçu (pour tous les deals)
        if dossier_not_received_blocks_dates and not skip_date_session_analysis:
            skip_date_session_analysis = True
            skip_reason = skip_reason or 'dossier_not_received'
            logger.warning("  → La réponse doit demander de finaliser l'inscription / envoyer le dossier")

        # ================================================================
        # VÉRIFICATION DATE EXAMEN VTC
        # ================================================================
        date_examen_vtc_result = {}
        if not skip_date_session_analysis:
            logger.info("  📅 Vérification date examen VTC...")
            date_examen_vtc_result = analyze_exam_date_situation(
                deal_data=deal_data,
                threads=threads_data,
                crm_client=self.crm_client,
                examt3p_data=examt3p_data
            )

            if date_examen_vtc_result.get('should_include_in_response'):
                logger.info(f"  ➡️ CAS {date_examen_vtc_result['case']}: {date_examen_vtc_result['case_description']}")
            else:
                logger.info(f"  ✅ Date examen VTC OK (CAS {date_examen_vtc_result['case']})")

            # ================================================================
            # ENRICHISSEMENT: Si intention REPORT_DATE avec mois/lieu spécifiques
            # ================================================================
            if triage_result.get('primary_intent') == 'REPORT_DATE':
                intent_context = triage_result.get('intent_context', {})
                requested_month = intent_context.get('requested_month')
                requested_location = intent_context.get('requested_location')  # Nom original (ex: "Montpellier")
                requested_dept_code = intent_context.get('requested_dept_code')  # Code département (ex: "34")

                if requested_month or requested_location or requested_dept_code:
                    from src.utils.date_examen_vtc_helper import search_dates_for_month_and_location

                    # Utiliser le code département extrait par TriageAgent (prioritaire)
                    dept_for_search = requested_dept_code or requested_location
                    if requested_dept_code:
                        logger.info(f"  📍 Département extrait par TriageAgent: {requested_dept_code} (location: {requested_location})")

                    # Récupérer la date d'examen actuelle pour l'exclure des alternatives
                    current_exam_date = date_examen_vtc_result.get('date_examen_info', {}).get('Date_Examen')

                    search_result = search_dates_for_month_and_location(
                        crm_client=self.crm_client,
                        requested_month=requested_month,
                        requested_location=dept_for_search,
                        candidate_region=date_examen_vtc_result.get('candidate_region'),
                        current_exam_date=current_exam_date
                    )

                    # Propager les résultats
                    date_examen_vtc_result['no_date_for_requested_month'] = search_result['no_date_for_requested_month']
                    date_examen_vtc_result['requested_month_name'] = search_result['requested_month_name']
                    date_examen_vtc_result['requested_location'] = requested_location  # Nom original pour l'affichage
                    date_examen_vtc_result['requested_dept_code'] = requested_dept_code  # Code département
                    date_examen_vtc_result['same_month_other_depts'] = search_result['same_month_other_depts']
                    date_examen_vtc_result['same_dept_other_months'] = search_result['same_dept_other_months']

                    if search_result['no_date_for_requested_month']:
                        logger.info(f"  ⚠️ Pas de date en {search_result['requested_month_name']} sur {requested_location or requested_dept_code}")

            # ================================================================
            # ENRICHISSEMENT: Dates alternatives si candidat demande date plus tôt
            # ================================================================
            # Si le candidat demande explicitement une date plus proche ET peut changer de département
            # → Charger les dates alternatives d'autres départements
            intent_context = triage_result.get('intent_context', {}) if triage_result else {}
            wants_earlier_date = intent_context.get('wants_earlier_date', False)
            can_choose_other_dept = date_examen_vtc_result.get('can_choose_other_department', False)
            current_dept = date_examen_vtc_result.get('departement')

            if wants_earlier_date and can_choose_other_dept and current_dept:
                logger.info("  🚀 Candidat demande date plus tôt + peut changer de département")
                from src.utils.date_examen_vtc_helper import get_earlier_dates_other_departments

                # Trouver la date de référence (date actuelle assignée ou première date du dept)
                current_dates = date_examen_vtc_result.get('next_dates', [])
                reference_date = None
                if date_examen_vtc_result.get('date_examen_info', {}).get('Date_Examen'):
                    reference_date = date_examen_vtc_result['date_examen_info']['Date_Examen']
                elif current_dates:
                    reference_date = current_dates[0].get('Date_Examen')

                if reference_date:
                    alt_dates = get_earlier_dates_other_departments(
                        self.crm_client,
                        current_departement=current_dept,
                        reference_date=reference_date,
                        limit=5
                    )
                    if alt_dates:
                        date_examen_vtc_result['alternative_department_dates'] = alt_dates
                        date_examen_vtc_result['should_include_in_response'] = True
                        logger.info(f"  📅 {len(alt_dates)} date(s) plus tôt dans d'autres départements")
        else:
            # Construire le message de raison du skip
            skip_reason_msg = {
                'credentials_invalid': 'identifiants invalides',
                'dossier_not_received': 'dossier non reçu'
            }.get(skip_reason, None)
            # Gérer les cas Uber dynamiquement (uber_case_A, uber_case_B, uber_case_D, uber_case_E)
            if not skip_reason_msg and skip_reason and skip_reason.startswith('uber_case_'):
                uber_case = skip_reason.replace('uber_case_', '')
                skip_reason_msg = f'CAS {uber_case} Uber'
            skip_reason_msg = skip_reason_msg or skip_reason or 'raison inconnue'
            logger.info(f"  📅 Vérification date examen VTC... SKIPPED ({skip_reason_msg})")

        # ================================================================
        # VÉRIFICATION COHÉRENCE FORMATION / EXAMEN
        # ================================================================
        # Cas critique: candidat a manqué sa formation + examen imminent
        # → Proposer 2 options: maintenir examen (e-learning suffit) ou reporter (force majeure requise)
        from src.utils.training_exam_consistency_helper import analyze_training_exam_consistency

        training_exam_consistency_result = {}
        if not skip_date_session_analysis:
            logger.info("  🔍 Vérification cohérence formation/examen...")
            training_exam_consistency_result = analyze_training_exam_consistency(
                deal_data=deal_data,
                threads=threads_data,
                session_data=session_data,
                crm_client=self.crm_client
            )

            if training_exam_consistency_result.get('has_consistency_issue'):
                logger.warning(f"  🚨 PROBLÈME DE COHÉRENCE DÉTECTÉ: {training_exam_consistency_result['issue_type']}")
                logger.info(f"  📅 Examen prévu le: {training_exam_consistency_result['exam_date_formatted']}")
                if training_exam_consistency_result.get('next_exam_date_formatted'):
                    logger.info(f"  📅 Prochaine date disponible: {training_exam_consistency_result['next_exam_date_formatted']}")
                if training_exam_consistency_result.get('force_majeure_detected'):
                    logger.info(f"  📋 Force majeure détectée: {training_exam_consistency_result['force_majeure_type']}")
                logger.info("  → Réponse avec options A/B sera proposée au candidat")
            else:
                logger.info("  ✅ Pas de problème de cohérence formation/examen")
        else:
            logger.info(f"  🔍 Vérification cohérence formation/examen... SKIPPED ({skip_reason_msg})")

        # ================================================================
        # ANALYSE SESSIONS DE FORMATION
        # ================================================================
        # Si des dates d'examen sont proposées OU si date examen assignée mais pas de session
        from src.utils.session_helper import analyze_session_situation

        next_dates = date_examen_vtc_result.get('next_dates', [])
        date_examen_info = date_examen_vtc_result.get('date_examen_info')

        # Vérifier si session déjà assignée dans CRM
        current_session = deal_data.get('Session')
        session_is_empty = not current_session

        # ================================================================
        # LOGIQUE PRIORITÉ DATES POUR SESSIONS:
        # ================================================================
        # 1. Si CONFIRMATION_SESSION + date assignée → sessions pour cette date uniquement
        # 2. Si REPORT_DATE + alternatives trouvées → sessions pour les dates ALTERNATIVES (pas la date actuelle)
        # 3. Sinon si next_dates existe → utiliser next_dates
        # 4. Sinon si date assignée + session vide → utiliser date assignée
        # ================================================================
        detected_intent = triage_result.get('detected_intent', '') if triage_result else ''
        has_assigned_date = date_examen_info and isinstance(date_examen_info, dict) and date_examen_info.get('Date_Examen')

        if has_assigned_date and detected_intent == 'CONFIRMATION_SESSION':
            # CAS 1: Candidat confirme sa session → utiliser SA date assignée
            exam_dates_for_session = [date_examen_info]
            logger.info(f"  📚 CONFIRMATION_SESSION + date assignée ({date_examen_info.get('Date_Examen')}) → sessions pour cette date uniquement")
        elif detected_intent == 'REPORT_DATE':
            # CAS 2: REPORT_DATE → charger les dates SPÉCIFIQUES au département et exclure la date actuelle
            current_date = date_examen_info.get('Date_Examen') if date_examen_info else None
            current_dept = date_examen_vtc_result.get('current_departement') or date_examen_vtc_result.get('date_examen_info', {}).get('Departement')

            if current_dept:
                # Charger les dates spécifiques au département (pas la liste globale)
                from src.utils.date_examen_vtc_helper import get_next_exam_dates
                dept_dates = get_next_exam_dates(self.crm_client, current_dept, limit=10)
                # Filtrer la date actuelle
                exam_dates_for_session = [d for d in dept_dates if d.get('Date_Examen') != current_date]
                logger.info(f"  📚 REPORT_DATE: {len(exam_dates_for_session)} date(s) du département {current_dept} (date actuelle {current_date} exclue)")
            else:
                exam_dates_for_session = []
                logger.warning(f"  📚 REPORT_DATE: département non trouvé, pas de dates chargées")
        elif next_dates:
            # CAS 3: Nouvelles dates proposées (changement de date ou première attribution)
            exam_dates_for_session = next_dates
        elif has_assigned_date and session_is_empty:
            # CAS 4: Pas de nouvelles dates, mais date existante et session vide
            exam_dates_for_session = [date_examen_info]
            logger.info("  📚 Session vide mais date examen assignée - recherche sessions correspondantes...")
        else:
            exam_dates_for_session = []

        # Pour REPORT_DATE, toujours chercher les sessions des dates alternatives
        is_report_date = detected_intent == 'REPORT_DATE'
        should_analyze_sessions = (
            not skip_date_session_analysis
            and exam_dates_for_session
            and (date_examen_vtc_result.get('should_include_in_response') or session_is_empty or is_report_date)
        )

        if should_analyze_sessions:
            logger.info("  📚 Recherche des sessions de formation associées...")
            # Récupérer la préférence du TriageAgent si disponible
            intent_context = triage_result.get('intent_context', {}) if triage_result else {}
            triage_session_pref = intent_context.get('session_preference')

            session_data = analyze_session_situation(
                deal_data=deal_data,
                exam_dates=exam_dates_for_session,
                threads=threads_data,
                crm_client=self.crm_client,
                triage_session_preference=triage_session_pref
            )
            if session_data.get('session_preference'):
                logger.info(f"  ➡️ Préférence détectée: {session_data['session_preference']}")
            if session_data.get('proposed_options'):
                logger.info(f"  ✅ {len(session_data['proposed_options'])} option(s) de session proposée(s)")
        elif skip_date_session_analysis:
            logger.info(f"  📚 Recherche sessions... SKIPPED (raison: {skip_reason})")

        # INFO: Ancien dossier (pour information uniquement, ne bloque plus)
        ancien_dossier = False
        if deal_data.get('Date_de_depot_CMA'):
            date_depot = deal_data['Date_de_depot_CMA']
            if date_depot < '2025-11-01':
                ancien_dossier = True
                logger.info("ℹ️  Ancien dossier (avant 01/11/2025) - traitement normal")

        # ================================================================
        # NETTOYAGE date_examen_vtc_result POUR CONFIRMATION_SESSION
        # ================================================================
        # Si c'est une confirmation de session avec date assignée,
        # on ne veut pas que l'IA propose des dates alternatives
        if has_assigned_date and detected_intent == 'CONFIRMATION_SESSION':
            # Remplacer next_dates par uniquement la date assignée
            date_examen_vtc_result = dict(date_examen_vtc_result)  # Copie pour ne pas modifier l'original
            date_examen_vtc_result['next_dates'] = [date_examen_info]
            date_examen_vtc_result['alternative_department_dates'] = []  # Pas d'alternatives
            logger.info("  📝 CONFIRMATION_SESSION: dates alternatives supprimées du contexte IA")

        return {
            'contact_data': contact_data,  # Données du contact lié (First_Name, Last_Name)
            'deal_id': deal_id,
            'deal_data': deal_data,
            'date_examen_vtc_value': date_examen_vtc_value,  # Date réelle extraite du lookup
            'examt3p_data': examt3p_data,
            'uber_eligibility_result': uber_eligibility_result,  # Éligibilité Uber 20€
            'date_examen_vtc_result': date_examen_vtc_result,
            'evalbox_data': evalbox_data,
            'session_data': session_data,
            'threads': threads_data,  # threads_data déjà récupérés au début
            'ancien_dossier': ancien_dossier,
            # Nouveaux champs pour traçabilité
            'sync_result': sync_result,  # Résultat sync ExamT3P → CRM
            'ticket_confirmations': ticket_confirmations,  # Confirmations extraites du ticket
            # Flag critique: identifiants invalides = SEUL sujet de la réponse
            # IMPORTANT: credentials_only_response = True UNIQUEMENT si skip_reason == 'credentials_invalid'
            # Pour les cas Uber A/B, on utilise uber_case_response avec le message pré-généré
            # Pour D/E, on utilise uber_case_alert (alerte dans réponse normale)
            'credentials_only_response': skip_reason == 'credentials_invalid',
            'uber_case_response': uber_case_blocks_dates,  # True seulement pour CAS A/B
            'uber_case_alert': uber_case_alert,  # Pour CAS D/E: alerte à inclure dans réponse normale
            'skip_reason': skip_reason,  # Raison du skip (credentials_invalid, uber_case_X, dossier_not_received)
            'dossier_not_received': dossier_not_received_blocks_dates,
            'uber_case_blocks_dates': uber_case_blocks_dates,
            # Cohérence formation/examen (cas manqué formation + examen imminent)
            'training_exam_consistency_result': training_exam_consistency_result,
            # Lookups CRM enrichis (v2.2) - données complètes depuis les modules Zoho
            'enriched_lookups': enriched_lookups,
            'lookup_cache': lookup_cache,
        }

    def _generate_duplicate_uber_response(
        self,
        ticket_id: str,
        triage_result: Dict
    ) -> Dict:
        """
        Génère une réponse pour les candidats ayant déjà bénéficié de l'offre Uber 20€.

        L'offre Uber 20€ n'est valable qu'UNE SEULE FOIS.
        Si le candidat souhaite se réinscrire, il devra :
        - Payer lui-même les frais d'examen (241€)
        - Gérer son inscription sur ExamT3P
        - Nous pouvons lui proposer la formation (VISIO ou présentiel)
        """
        logger.info("📝 Génération de la réponse DOUBLON UBER 20€...")

        duplicate_deals = triage_result.get('duplicate_deals', [])
        selected_deal = triage_result.get('selected_deal', {})

        # Formater les dates des opportunités précédentes
        previous_dates = []
        for deal in duplicate_deals:
            closing_date = deal.get('Closing_Date', 'N/A')
            deal_name = deal.get('Deal_Name', 'Opportunité')
            previous_dates.append(f"{deal_name} ({closing_date})")

        # Générer la réponse
        response_text = """Bonjour,

Je vous remercie pour votre message.

Après vérification de votre dossier, je constate que vous avez déjà bénéficié de l'offre Uber à 20€ pour le passage de l'examen VTC. Cette offre n'est valable qu'une seule fois par candidat.

Si vous souhaitez vous réinscrire à l'examen VTC, voici vos options :

OPTION 1 : Inscription autonome
• Vous pouvez vous inscrire vous-même sur le site de la CMA (ExamT3P)
• Les frais d'inscription à l'examen s'élèvent à 241€, à votre charge
• Site d'inscription : https://exament3p.cma-france.fr

OPTION 2 : Formation avec CAB Formations
Si vous souhaitez suivre une formation de préparation à l'examen VTC, nous pouvons vous proposer :

📚 Formation en présentiel : sur l'un de nos centres de formation

📚 Formation E-learning

Ces deux formations sont finançables via votre CPF (Compte Personnel de Formation).

Merci de me préciser si vous êtes intéressé(e) par l'une de ces options, et je vous transmettrai les tarifs et disponibilités.

Bien cordialement,

L'équipe Cab Formations"""

        logger.info(f"✅ Réponse DOUBLON générée ({len(response_text)} caractères)")

        return {
            'response_text': response_text,
            'is_duplicate_uber_response': True,
            'duplicate_deals_count': len(duplicate_deals),
            'previous_dates': previous_dates,
            'crm_updates': {},  # Pas de mise à jour CRM pour les doublons
            'detected_scenarios': ['DUPLICATE_UBER_OFFER']
        }

    def _generate_clarification_response(
        self,
        ticket_id: str,
        triage_result: Dict
    ) -> Dict:
        """
        Génère une réponse pour demander des clarifications quand le candidat
        n'est pas trouvé dans le CRM.

        Reconnaît l'intention du candidat avant de demander les informations.
        """
        logger.info("📝 Génération de la réponse de CLARIFICATION...")

        email_searched = triage_result.get('email_searched', 'non identifié')
        alternative_email = triage_result.get('alternative_email_used')
        primary_intent = triage_result.get('primary_intent', '')

        # Adapter l'intro selon l'intention détectée
        intent_acknowledgment = ""
        if primary_intent == 'STATUT_DOSSIER':
            intent_acknowledgment = "Concernant votre demande sur l'avancement de votre dossier : "
        elif primary_intent in ('DEMANDE_DATES_FUTURES', 'DEMANDE_DATE_EXAMEN'):
            intent_acknowledgment = "Concernant votre demande sur les dates d'examen : "
        elif primary_intent == 'REPORT_DATE':
            intent_acknowledgment = "Concernant votre demande de changement de date : "
        elif primary_intent == 'DEMANDE_IDENTIFIANTS':
            intent_acknowledgment = "Concernant votre demande d'identifiants : "
        elif primary_intent == 'DEMANDE_CONVOCATION':
            intent_acknowledgment = "Concernant votre demande de convocation : "
        elif primary_intent == 'CONFIRMATION_SESSION':
            intent_acknowledgment = "Concernant votre choix de session de formation : "
        elif primary_intent == 'RESULTAT_EXAMEN':
            intent_acknowledgment = "Concernant votre demande de résultat d'examen : "
        elif primary_intent:
            intent_acknowledgment = "Concernant votre demande : "

        # Générer la réponse
        response_text = f"""Bonjour,

Je vous remercie pour votre message.

{intent_acknowledgment}Nous avons du mal à retrouver votre dossier via l'adresse mail **{email_searched}**.

Afin de pouvoir accéder à votre dossier et vous apporter une réponse précise, pourriez-vous nous communiquer les informations suivantes :

- **Votre nom et prénom** (tels qu'indiqués lors de l'inscription)
- **L'adresse email utilisée lors de votre inscription** (si différente de celle-ci)
- **Votre numéro de téléphone**

Dès réception de ces informations, nous reviendrons vers vous rapidement.

Bien cordialement,

L'équipe CAB Formations"""

        logger.info(f"✅ Réponse CLARIFICATION générée ({len(response_text)} caractères), intent={primary_intent}")

        return {
            'response_text': response_text,
            'is_clarification_response': True,
            'email_searched': email_searched,
            'alternative_email_tried': alternative_email,
            'intent_acknowledged': primary_intent,
            'crm_updates': {},  # Pas de mise à jour CRM - candidat non trouvé
            'detected_scenarios': ['CANDIDATE_NOT_FOUND']
        }

    def _run_response_generation(
        self,
        ticket_id: str,
        triage_result: Dict,
        analysis_result: Dict
    ) -> Dict:
        """
        Run AGENT RÉDACTEUR - Generate response using State Engine.

        Uses deterministic state detection + templates + validation.

        Returns response_result dict.
        """
        # Get ticket info
        ticket = self.desk_client.get_ticket(ticket_id)
        ticket_subject = ticket.get('subject', '')

        # Extract customer message with proper content extraction
        from src.utils.text_utils import get_clean_thread_content

        customer_message = ""
        for thread in analysis_result.get('threads', []):
            if thread.get('direction') == 'in':
                customer_message = get_clean_thread_content(thread)
                break

        # State Engine - Deterministic response generation
        logger.info("  🎯 Mode: STATE ENGINE (deterministic)")
        return self._run_state_driven_response(
            ticket_id=ticket_id,
            triage_result=triage_result,
            analysis_result=analysis_result,
            customer_message=customer_message,
            ticket_subject=ticket_subject
        )

    def _run_state_driven_response(
        self,
        ticket_id: str,
        triage_result: Dict,
        analysis_result: Dict,
        customer_message: str,
        ticket_subject: str
    ) -> Dict:
        """
        Run State-Driven response generation (deterministic).

        Uses:
        1. StateDetector → Detect candidate state from context
        2. TemplateEngine → Generate response from templates
        3. ResponseValidator → Validate response (forbidden terms, etc.)
        4. CRMUpdater → Determine CRM updates (pattern matching)

        Args:
            ticket_id: Ticket ID
            triage_result: Result from triage step (contains detected_intent)
            analysis_result: Result from analysis step (contains all data)
            customer_message: Candidate's message content
            ticket_subject: Ticket subject

        Returns:
            response_result dict compatible with current workflow
        """
        logger.info("  🎯 STATE ENGINE: Détection de l'état...")

        # ================================================================
        # STEP 1: Detect State
        # ================================================================
        deal_data = analysis_result.get('deal_data', {})
        examt3p_data = analysis_result.get('examt3p_data', {})
        threads_data = analysis_result.get('threads', [])

        # Build linking_result from analysis data
        linking_result = {
            'deal_id': analysis_result.get('deal_id'),
            'deal': deal_data,
            'selected_deal': deal_data,
            'has_duplicate_uber_offer': analysis_result.get('has_duplicate_uber_offer', False),
            'needs_clarification': analysis_result.get('needs_clarification', False),
        }

        # MULTI-ÉTATS: Utiliser detect_all_states pour collecter tous les états
        detected_states = self.state_detector.detect_all_states(
            deal_data=deal_data,
            examt3p_data=examt3p_data,
            triage_result=triage_result,
            linking_result=linking_result,
            threads_data=threads_data
        )

        # Pour rétrocompatibilité, on utilise primary_state comme référence principale
        detected_state = detected_states.primary_state

        state_id = detected_state.id
        state_name = detected_state.name
        priority = detected_state.priority

        logger.info(f"  ✅ État primaire: {state_id} - {state_name} (priorité {priority})")

        # Log multi-états détaillés
        if detected_states.blocking_state:
            logger.info(f"  🚫 État BLOCKING: {detected_states.blocking_state.name}")
        if detected_states.warning_states:
            warning_names = [s.name for s in detected_states.warning_states]
            logger.info(f"  ⚠️ États WARNING: {warning_names}")
        if detected_states.info_states:
            info_names = [s.name for s in detected_states.info_states]
            logger.info(f"  ℹ️ États INFO: {info_names}")

        # Log intentions (multi-intentions)
        primary_intent = triage_result.get('primary_intent') or triage_result.get('detected_intent')
        secondary_intents = triage_result.get('secondary_intents', [])
        if primary_intent:
            logger.info(f"  🎯 Intention principale: {primary_intent}")
        if secondary_intents:
            logger.info(f"  🎯 Intentions secondaires: {secondary_intents}")

        # Log context for debugging
        ctx = detected_state.context_data
        logger.debug(f"     Evalbox: {ctx.get('evalbox')}")
        logger.debug(f"     Uber case: {ctx.get('uber_case')}")
        logger.debug(f"     Date case: {ctx.get('date_case')}")

        # ================================================================
        # STEP 2: Generate Response from Template
        # ================================================================
        logger.info("  📝 STATE ENGINE: Génération de la réponse...")

        # Enrich context_data with additional analysis data
        # (TemplateEngine uses state.context_data for placeholders)
        date_examen_vtc_result = analysis_result.get('date_examen_vtc_result', {})
        session_data = analysis_result.get('session_data', {})
        uber_result = analysis_result.get('uber_eligibility_result', {})

        # Récupérer contact_data et date_examen_vtc_value depuis analysis_result
        contact_data = analysis_result.get('contact_data', {})
        date_examen_vtc_value = analysis_result.get('date_examen_vtc_value')

        detected_state.context_data.update({
            # Données brutes
            'deal_data': deal_data,
            'contact_data': contact_data,  # Données du contact (First_Name, Last_Name)
            'examt3p_data': examt3p_data,
            'date_examen_vtc_data': date_examen_vtc_result,
            'date_examen_vtc_value': date_examen_vtc_value,  # Date réelle extraite du lookup
            'session_data': session_data,
            'uber_eligibility_data': uber_result,
            'training_exam_consistency_data': analysis_result.get('training_exam_consistency_result', {}),
            'ticket_subject': ticket_subject,
            'customer_message': customer_message,
            'threads': analysis_result.get('threads', []),

            # Données extraites pour les placeholders (niveau racine)
            'next_dates': date_examen_vtc_result.get('next_dates', []),
            'date_case': date_examen_vtc_result.get('case'),
            'date_cloture': date_examen_vtc_result.get('date_cloture'),
            'can_choose_other_department': date_examen_vtc_result.get('can_choose_other_department', False),
            'alternative_department_dates': date_examen_vtc_result.get('alternative_department_dates', []),
            'deadline_passed_reschedule': date_examen_vtc_result.get('deadline_passed_reschedule', False),
            'new_exam_date': date_examen_vtc_result.get('new_exam_date'),
            'new_exam_date_cloture': date_examen_vtc_result.get('new_exam_date_cloture'),

            # Données de recherche par mois/lieu (REPORT_DATE intelligent)
            'no_date_for_requested_month': date_examen_vtc_result.get('no_date_for_requested_month', False),
            'requested_month_name': date_examen_vtc_result.get('requested_month_name', ''),
            'requested_location': date_examen_vtc_result.get('requested_location', ''),
            'same_month_other_depts': date_examen_vtc_result.get('same_month_other_depts', []),
            'same_dept_other_months': date_examen_vtc_result.get('same_dept_other_months', []),

            # Session
            'proposed_sessions': session_data.get('proposed_options', []),
            'session_preference': session_data.get('session_preference'),

            # Uber
            'is_uber_20_deal': uber_result.get('is_uber_20_deal', False),
            'uber_case': uber_result.get('case', ''),
        })

        # RECALCULATE cloture_passed et can_modify_exam_date avec date_cloture enrichi
        # (le StateDetector n'a pas accès à date_cloture lors de la détection)
        date_cloture = date_examen_vtc_result.get('date_cloture')
        if date_cloture:
            from datetime import datetime
            try:
                if 'T' in str(date_cloture):
                    cloture_date = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00')).date()
                else:
                    cloture_date = datetime.strptime(str(date_cloture)[:10], '%Y-%m-%d').date()
                today = datetime.now().date()
                cloture_passed = cloture_date < today

                # Toujours mettre à jour cloture_passed (utilisé par d'autres logiques)
                detected_state.context_data['cloture_passed'] = cloture_passed

                # Recalculer can_modify_exam_date selon règle B1
                evalbox = detected_state.context_data.get('evalbox', '')
                blocking_statuses = {'VALIDE CMA', 'Convoc CMA reçue'}
                if evalbox in blocking_statuses and cloture_passed:
                    detected_state.context_data['can_modify_exam_date'] = False
                    logger.info(f"  ⚠️ can_modify_exam_date recalculé: False (clôture {date_cloture} passée)")
            except Exception as e:
                logger.warning(f"  ⚠️ Erreur parsing date_cloture: {e}")

        # LOAD next_dates si intention REPORT_DATE mais dates vides
        # (CAS 9 et autres cas ne chargent pas next_dates par défaut)
        detected_intent = detected_state.context_data.get('detected_intent', '')
        next_dates = detected_state.context_data.get('next_dates', [])
        if detected_intent == 'REPORT_DATE' and not next_dates:
            from src.utils.date_examen_vtc_helper import get_next_exam_dates
            departement = detected_state.context_data.get('departement')
            if departement and self.crm_client:
                logger.info(f"  📅 Chargement next_dates pour REPORT_DATE (dept {departement})...")
                next_dates = get_next_exam_dates(self.crm_client, departement, limit=5)
                detected_state.context_data['next_dates'] = next_dates
                logger.info(f"  ✅ {len(next_dates)} date(s) chargées")

        # FILTRER next_dates selon le mois demandé par le candidat
        intent_context = triage_result.get('intent_context', {})
        requested_month = intent_context.get('requested_month')
        requested_location = intent_context.get('requested_location')

        # Validation: requested_month doit être entre 1 et 12
        if requested_month and isinstance(requested_month, int) and 1 <= requested_month <= 12 and next_dates:
            from datetime import datetime
            filtered_dates = []
            has_date_in_exact_month = False
            for date_info in next_dates:
                date_str = date_info.get('Date_Examen') or date_info.get('date_examen')
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        # Garder les dates du mois demandé ou après
                        if date_obj.month >= requested_month:
                            filtered_dates.append(date_info)
                            # Vérifier si on a une date exactement dans le mois demandé
                            if date_obj.month == requested_month:
                                has_date_in_exact_month = True
                    except ValueError:
                        filtered_dates.append(date_info)  # En cas d'erreur, garder la date

            month_names = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                           'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

            if filtered_dates:
                logger.info(f"  📅 Filtrage par mois {requested_month}: {len(next_dates)} → {len(filtered_dates)} date(s)")
                detected_state.context_data['next_dates'] = filtered_dates

                # Si pas de date exactement dans le mois demandé, ajouter le message explicatif
                if not has_date_in_exact_month:
                    logger.info(f"  ℹ️ Pas de date exactement en {month_names[requested_month]} - dates ultérieures proposées")
                    detected_state.context_data['no_date_for_requested_month'] = True
                    detected_state.context_data['requested_month_name'] = month_names[requested_month] if 1 <= requested_month <= 12 else str(requested_month)
            else:
                # Aucune date ne correspond - garder toutes les dates et ajouter message
                logger.warning(f"  ⚠️ Aucune date en mois {requested_month} ou après - on garde toutes les dates")
                detected_state.context_data['no_date_for_requested_month'] = True
                detected_state.context_data['requested_month_name'] = month_names[requested_month] if 1 <= requested_month <= 12 else str(requested_month)

        # Create AI generator for personalization sections
        # This uses Sonnet to generate contextual personalization based on threads/message
        def ai_personalization_generator(state, instructions="", max_length=150):
            return self._generate_personalization(
                state=state,
                customer_message=customer_message,
                threads=threads_data,
                instructions=instructions,
                max_length=max_length
            )

        # MULTI-ÉTATS: Generate response using generate_response_multi
        # Enrichir le primary_state avec le contexte combiné (y compris warnings)
        detected_states.primary_state = detected_state  # Avec le context_data enrichi

        template_result = self.template_engine.generate_response_multi(
            detected_states=detected_states,
            triage_result=triage_result,
            ai_generator=ai_personalization_generator
        )
        response_text = template_result.get('response_text', '')

        logger.info(f"  ✅ Réponse générée ({len(response_text)} caractères)")
        if template_result.get('template_used'):
            logger.info(f"     Template: {template_result['template_used']}")
        if template_result.get('states_used'):
            logger.info(f"     États utilisés: {template_result['states_used']}")
        if template_result.get('intents_handled'):
            logger.info(f"     Intentions traitées: {template_result['intents_handled']}")

        # ================================================================
        # STEP 3: Validate Response
        # ================================================================
        logger.info("  🔍 STATE ENGINE: Validation de la réponse...")

        # Get proposed dates for validation
        proposed_dates = analysis_result.get('date_examen_vtc_result', {}).get('next_dates', [])

        validation_result = self.response_validator.validate(
            response_text=response_text,
            state=detected_state,
            proposed_dates=proposed_dates,
            template_used=template_result.get('template_used')
        )

        if validation_result.valid:
            logger.info("  ✅ Validation OK")
        else:
            logger.warning(f"  ⚠️ Validation échouée: {len(validation_result.errors)} erreur(s)")
            for error in validation_result.errors:
                logger.warning(f"     - {error.message}")

            # Log warnings too
            for warning in validation_result.warnings:
                logger.info(f"     ⚡ {warning.message}")

        # ================================================================
        # STEP 4: Determine CRM Updates (Deterministic)
        # ================================================================
        logger.info("  📊 STATE ENGINE: Détermination des mises à jour CRM...")

        # Get proposed sessions/dates for CRM updates
        proposed_sessions = []
        session_data = analysis_result.get('session_data', {})
        for option in session_data.get('proposed_options', []):
            for sess in option.get('sessions', []):
                proposed_sessions.append(sess)

        proposed_dates = analysis_result.get('date_examen_vtc_result', {}).get('next_dates', [])

        crm_update_result = self.state_crm_updater.determine_updates(
            state=detected_state,
            candidate_message=customer_message,
            proposed_sessions=proposed_sessions,
            proposed_dates=proposed_dates
        )

        crm_updates = crm_update_result.updates_applied

        if crm_updates:
            logger.info(f"  ✅ Mises à jour CRM déterminées: {list(crm_updates.keys())}")
        else:
            logger.info("  ✅ Aucune mise à jour CRM nécessaire")

        if crm_update_result.updates_blocked:
            for field, reason in crm_update_result.updates_blocked.items():
                logger.warning(f"  🔒 {field} bloqué: {reason}")

        # ================================================================
        # BUILD RESPONSE RESULT (compatible with current workflow)
        # ================================================================
        # Extract forbidden terms found from validation errors
        forbidden_terms_found = [
            e.message for e in validation_result.errors
            if e.error_type == 'forbidden_term'
        ]

        response_result = {
            'response_text': response_text,
            'detected_scenarios': [state_id],
            'crm_updates': crm_updates,
            'requires_crm_update': len(crm_updates) > 0,
            'should_stop_workflow': detected_state.response_config.get('stop_workflow', False),
            'validation': {
                state_id: {
                    'compliant': validation_result.valid,
                    'errors': [e.message for e in validation_result.errors],
                    'warnings': [w.message for w in validation_result.warnings],
                    'missing_blocks': [],
                    'forbidden_terms_found': forbidden_terms_found,
                }
            },
            # State Engine specific metadata
            'state_engine': {
                'state_id': state_id,
                'state_name': state_name,
                'priority': priority,
                'context': ctx,
                'crm_updates_blocked': crm_update_result.updates_blocked,
                'crm_updates_skipped': crm_update_result.updates_skipped,
            },
            # Multi-états / Multi-intentions metadata
            'states_used': template_result.get('states_used', []),
            'warning_states': template_result.get('warning_states', []),
            'info_states': template_result.get('info_states', []),
            'intents_handled': template_result.get('intents_handled', []),
            'is_blocking': template_result.get('is_blocking', False),
            'primary_intent': template_result.get('primary_intent'),
            'secondary_intents': template_result.get('secondary_intents', []),
        }

        return response_result

    def _generate_personalization(
        self,
        state,
        customer_message: str,
        threads: list,
        instructions: str = "",
        max_length: int = 150
    ) -> str:
        """
        Generate personalized introduction using Sonnet.

        This creates a contextual 1-3 sentence introduction that:
        - Acknowledges the candidate's specific concern/question
        - Takes into account the thread history
        - Sets up the factual content that follows in the template

        Args:
            state: DetectedState with context data
            customer_message: The candidate's last message
            threads: Thread history
            instructions: Additional instructions for personalization
            max_length: Max characters for personalization (soft limit)

        Returns:
            Personalized text (1-3 sentences)
        """
        # Format thread history for context
        thread_history = self._format_thread_history_for_personalization(threads)

        # Get state context
        state_name = state.name
        state_description = state.description if hasattr(state, 'description') else state_name

        # Build the system prompt
        system_prompt = """Tu es un assistant de CAB Formations, organisme de formation VTC.

Tu dois rédiger une COURTE introduction personnalisée (1 à 3 phrases maximum) pour une réponse email.

Cette introduction doit:
1. Reconnaître la demande ou préoccupation spécifique du candidat
2. Être empathique et professionnelle
3. Préparer le terrain pour les informations factuelles qui suivront

RÈGLES STRICTES:
- NE JAMAIS inventer de dates, numéros de dossier, identifiants ou informations factuelles
- NE JAMAIS mentionner de montants (prix, frais)
- NE JAMAIS promettre quoi que ce soit de spécifique
- Être concis: 1 à 3 phrases, pas plus
- Utiliser un ton professionnel mais chaleureux
- Ne pas répéter le sujet de l'email
- Ne pas commencer par "Je" ou "Nous"

TERMES INTERDITS (ne jamais utiliser):
- "Evalbox", "BFS", "deal", "CRM", "CAS", "workflow"
- Tout jargon technique interne

FORMAT DE SORTIE:
Écris UNIQUEMENT le texte de personnalisation, sans guillemets, sans préfixe, sans explication."""

        # Build user prompt
        user_prompt = f"""## CONTEXTE

**État détecté du dossier**: {state_description}

**Dernier message du candidat**:
{customer_message}

---

## HISTORIQUE DES ÉCHANGES:

{thread_history}

---

## INSTRUCTION SPÉCIFIQUE:
{instructions if instructions else "Rédige une introduction adaptée à la situation."}

---

Génère maintenant la personnalisation (1-3 phrases):"""

        try:
            response = self.anthropic_client.messages.create(
                model=self.personalization_model,
                max_tokens=200,
                temperature=0.3,  # Low temperature for consistency
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            personalization = response.content[0].text.strip()

            # Safety: truncate if too long
            if len(personalization) > max_length * 2:
                # Find last sentence end before limit
                truncated = personalization[:max_length * 2]
                last_period = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
                if last_period > 0:
                    personalization = truncated[:last_period + 1]

            logger.info(f"  ✅ Personnalisation générée ({len(personalization)} caractères)")
            return personalization

        except Exception as e:
            logger.error(f"  ❌ Erreur génération personnalisation: {e}")
            # Fallback to a generic but appropriate response
            return "Nous avons bien reçu votre message et nous vous remercions de votre patience."

    def _format_thread_history_for_personalization(self, threads: list) -> str:
        """Format thread history for personalization prompt."""
        if not threads:
            return "(Premier contact - aucun historique)"

        lines = []

        # Sort by date
        sorted_threads = sorted(
            threads,
            key=lambda t: t.get('createdTime', '') or t.get('created_time', '') or '',
            reverse=False
        )

        # Show last 5 exchanges max to avoid context overflow
        recent_threads = sorted_threads[-5:] if len(sorted_threads) > 5 else sorted_threads

        for i, thread in enumerate(recent_threads, 1):
            direction = thread.get('direction', 'unknown')
            created_time = thread.get('createdTime', '') or thread.get('created_time', '')

            # Format date
            date_str = ""
            if created_time:
                try:
                    from datetime import datetime
                    if 'T' in str(created_time):
                        dt = datetime.fromisoformat(str(created_time).replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(str(created_time), "%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%d/%m/%Y")
                except Exception as e:
                    date_str = ""

            # Sender
            sender = "CANDIDAT" if direction == 'in' else "CAB Formations" if direction == 'out' else "?"

            # Content (truncated)
            content = thread.get('content', '') or thread.get('summary', '') or thread.get('plainText', '') or ''
            content = content.strip()
            if len(content) > 500:
                content = content[:500] + "..."

            lines.append(f"[{date_str}] {sender}:\n{content}\n")

        return "\n".join(lines) if lines else "(Aucun contenu)"

    def _create_crm_note(
        self,
        ticket_id: str,
        triage_result: Dict,
        analysis_result: Dict,
        response_result: Dict
    ) -> str:
        """
        Crée une note CRM unique et consolidée avec toutes les infos du traitement.

        Format:
        1. Lien vers le ticket Desk
        2. Résumé de la réponse envoyée au candidat
        3. Mises à jour CRM effectuées
        4. Next steps (candidat + CAB)
        5. Alertes si nécessaire
        """
        import anthropic

        lines = []

        # === EN-TÊTE avec lien ticket ===
        lines.append(f"Ticket #{ticket_id}")
        lines.append(f"https://desk.zoho.com/agent/cabformations/cab-formations/tickets/{ticket_id}")
        lines.append("")

        # === MISES À JOUR CRM ===
        updates = []

        # Sync ExamT3P
        sync_result = analysis_result.get('sync_result', {})
        if sync_result and sync_result.get('changes_made'):
            for change in sync_result['changes_made']:
                field = change['field']
                old_val = change.get('old_value', '') or '—'
                new_val = change.get('new_value', '')
                if 'MDP' in field:
                    new_val = '***'
                    old_val = '***' if old_val != '—' else '—'
                updates.append(f"• {field}: {old_val} → {new_val}")

        # Date sync
        date_sync = sync_result.get('date_sync', {}) if sync_result else {}
        if date_sync.get('date_changed'):
            old_date = date_sync.get('old_date') or '—'
            new_date = date_sync.get('new_date', '')
            updates.append(f"• Date_examen_VTC: {old_date} → {new_date}")

        # Mises à jour depuis la réponse
        crm_updates = response_result.get('crm_updates', {})
        if crm_updates:
            for field, value in crm_updates.items():
                # Éviter les doublons
                if not any(field in u for u in updates):
                    updates.append(f"• {field}: → {value}")

        if updates:
            lines.append("Mises à jour CRM:")
            lines.extend(updates)
        else:
            lines.append("Mises à jour CRM: aucune")
        lines.append("")

        # === GÉNÉRER RÉSUMÉ + NEXT STEPS avec Claude ===
        note_content = self._generate_note_content_with_ai(analysis_result, response_result)
        if note_content:
            lines.append(note_content)
            lines.append("")

        # === ALERTES ===
        alerts = []

        # Blocages de sync
        if sync_result and sync_result.get('blocked_changes'):
            for blocked in sync_result['blocked_changes']:
                alerts.append(f"⚠️ {blocked['field']}: {blocked['reason']}")

        # Date sync bloquée
        if date_sync.get('blocked'):
            alerts.append(f"⚠️ Date_examen_VTC: {date_sync.get('blocked_reason', 'bloqué')}")

        # Incohérences détectées
        training_result = analysis_result.get('training_exam_consistency_result', {})
        if training_result and training_result.get('problem_detected'):
            alerts.append(f"⚠️ {training_result.get('problem_description', 'Cohérence formation/examen à vérifier')}")

        # Double compte ExamT3P
        examt3p_data = analysis_result.get('examt3p_data', {})
        if examt3p_data.get('duplicate_paid_accounts'):
            alerts.append("⚠️ DOUBLE COMPTE PAYÉ - vérifier paiement")

        if alerts:
            lines.append("Alertes:")
            lines.extend(alerts)
        else:
            lines.append("✓ Aucune alerte")

        return "\n".join(lines)

    def _generate_note_content_with_ai(
        self,
        analysis_result: Dict,
        response_result: Dict
    ) -> str:
        """
        Utilise Claude Sonnet pour générer:
        1. Résumé de ce qui a été répondu au candidat
        2. Next steps candidat et CAB
        """
        import anthropic

        # Récupérer la réponse envoyée
        response_text = response_result.get('response_text', '')

        # Préparer le contexte
        deal_data = analysis_result.get('deal_data', {})
        examt3p_data = analysis_result.get('examt3p_data', {})
        date_result = analysis_result.get('date_examen_vtc_result', {})
        uber_result = analysis_result.get('uber_eligibility_result', {})

        # État détecté
        detected_state = response_result.get('detected_state', {})
        state_name = detected_state.get('name', 'N/A') if isinstance(detected_state, dict) else str(detected_state)

        # Uber status
        is_uber = uber_result.get('is_uber_20_deal', False)
        uber_case = uber_result.get('case', '')

        prompt = f"""Tu es un assistant qui génère des notes CRM concises pour le suivi des candidats VTC.

CONTEXTE:
- État: {state_name}
- Evalbox: {deal_data.get('Evalbox', 'N/A')}
- Deal Uber 20€: {'Oui - ' + uber_case if is_uber else 'Non'}
- Date examen: {date_result.get('date_examen_info', {}).get('Date_Examen', 'N/A') if isinstance(date_result.get('date_examen_info'), dict) else 'N/A'}
- Session assignée: {'Oui' if deal_data.get('Session') else 'Non'}

RÉPONSE ENVOYÉE AU CANDIDAT:
{response_text[:1500]}

---

Génère une note CRM avec EXACTEMENT ce format:

Réponse envoyée:
• [point clé 1 de ce qui a été communiqué]
• [point clé 2]
• [point clé 3 si pertinent]

Next steps candidat:
• [action concrète 1]
• [action concrète 2 si nécessaire]

Next steps CAB:
• [action concrète 1]
• [action concrète 2 si nécessaire]

RÈGLES:
- Résumer ce qui a RÉELLEMENT été dit dans la réponse (pas d'invention)
- Next steps SPÉCIFIQUES au contexte actuel
- Si Uber ÉLIGIBLE et frais pris en charge: ne PAS dire au candidat de payer
- Maximum 3 points par section
- Phrases courtes (5-10 mots max)
- Pas de formules vides comme "suivre le dossier"

Réponds UNIQUEMENT avec le format demandé, rien d'autre."""

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.warning(f"Erreur génération note IA: {e}")
            # Fallback basique
            return "Réponse envoyée:\n• Voir brouillon dans Zoho Desk\n\nNext steps candidat:\n• Consulter la réponse\n\nNext steps CAB:\n• Vérifier et envoyer"

    def _prepare_ticket_updates(self, response_result: Dict) -> Dict:
        """Prepare ticket field updates."""
        updates = {}

        # Note: Les tags Zoho Desk ne peuvent pas être mis à jour via l'API standard
        # (erreur "An extra parameter 'tags' is found")
        # Pour le moment, on ne met pas à jour les tags automatiquement

        return updates

    def _prepare_deal_updates(
        self,
        response_result: Dict,
        analysis_result: Dict
    ) -> Dict:
        """
        Prepare CRM deal field updates.

        Uses pattern-matched updates from State Engine (crm_updates)
        which analyzes the conversation context to determine what needs updating.

        IMPORTANT: Utilise les fonctions existantes de examt3p_crm_sync.py pour
        convertir les valeurs string en IDs CRM (lookup fields).
        """
        from src.utils.examt3p_crm_sync import find_exam_session_by_date_and_dept
        import re

        # Get AI-extracted updates (primary source)
        ai_updates = response_result.get('crm_updates', {})

        if not ai_updates:
            logger.info(f"  📊 No CRM updates extracted by AI")
            return {}

        logger.info(f"  📊 AI extracted CRM updates (raw): {ai_updates}")

        crm_updates = {}
        deal_data = analysis_result.get('deal_data', {})
        session_data = analysis_result.get('session_data', {})

        # ================================================================
        # 1. Date_examen_VTC (string → session ID via existing function)
        # ================================================================
        if 'Date_examen_VTC' in ai_updates:
            date_str = ai_updates['Date_examen_VTC']
            # Récupérer le département depuis le deal
            departement = deal_data.get('CMA_de_depot', '')
            if departement:
                match = re.search(r'\b(\d{2,3})\b', str(departement))
                if match:
                    departement = match.group(1)

            if departement:
                # Utiliser la fonction existante de examt3p_crm_sync.py
                session = find_exam_session_by_date_and_dept(
                    self.crm_client, date_str, departement
                )
                if session and session.get('id'):
                    crm_updates['Date_examen_VTC'] = session['id']
                    logger.info(f"  📊 Date_examen_VTC: {date_str} → ID {session['id']}")
                else:
                    logger.warning(f"  ⚠️ Session examen non trouvée: {date_str} / dept {departement}")
            else:
                logger.warning(f"  ⚠️ Département non trouvé, impossible de mapper Date_examen_VTC")

        # ================================================================
        # 2. Session_choisie (session name → session ID from proposed options)
        # ================================================================
        if 'Session_choisie' in ai_updates:
            session_name = ai_updates['Session_choisie']
            # Chercher dans les sessions proposées par l'analyse
            proposed_options = session_data.get('proposed_options', [])

            session_found = False
            for option in proposed_options:
                for sess in option.get('sessions', []):
                    sess_id = sess.get('id')
                    sess_debut = sess.get('Date_d_but', '')
                    sess_fin = sess.get('Date_fin', '')
                    sess_type = sess.get('session_type_label', '')

                    # Matching: soit par dates, soit par type (jour/soir)
                    if sess_id:
                        match_date = (sess_debut and sess_debut in session_name) or \
                                    (sess_fin and sess_fin in session_name)
                        match_type = ('soir' in session_name.lower() and 'soir' in sess_type.lower()) or \
                                    ('jour' in session_name.lower() and 'jour' in sess_type.lower())

                        if match_date or match_type:
                            crm_updates['Session_choisie'] = sess_id
                            logger.info(f"  📊 Session_choisie: {session_name} → ID {sess_id}")
                            session_found = True
                            break
                if session_found:
                    break

            if not session_found:
                logger.warning(f"  ⚠️ Session formation non trouvée: {session_name}")

        # ================================================================
        # 3. Autres champs (texte simple - pas de mapping nécessaire)
        # ================================================================
        for key, value in ai_updates.items():
            if key not in ['Date_examen_VTC', 'Session_choisie']:
                crm_updates[key] = value
                logger.info(f"  📊 {key}: {value}")

        if crm_updates:
            logger.info(f"  ✅ Final CRM updates: {list(crm_updates.keys())}")
        else:
            logger.warning(f"  ⚠️ No valid CRM updates after mapping")

        return crm_updates

    def close(self):
        """Clean up resources."""
        if hasattr(self, 'desk_client'):
            self.desk_client.close()
        if hasattr(self, 'crm_client'):
            self.crm_client.close()
        if hasattr(self, 'deal_linker') and hasattr(self.deal_linker, 'close'):
            self.deal_linker.close()
        if hasattr(self, 'dispatcher') and hasattr(self.dispatcher, 'close'):
            self.dispatcher.close()
        if hasattr(self, 'crm_update_agent') and hasattr(self.crm_update_agent, 'close'):
            self.crm_update_agent.close()
        # ExamT3PAgent, TriageAgent, and State Engine components don't have close() method


def test_workflow():
    """Test workflow with a sample ticket."""
    print("\n" + "=" * 80)
    print("TEST DOC TICKET WORKFLOW")
    print("=" * 80)

    print("\n🎯 Initializing workflow (State Engine)...")
    workflow = DOCTicketWorkflow()

    print("\n✅ Workflow initialized successfully")

    print("\n📋 Workflow stages:")
    print("  1. AGENT TRIEUR (triage with STOP & GO)")
    print("  2. AGENT ANALYSTE (6-source data extraction)")
    print("  3. STATE ENGINE (deterministic response generation)")
    print("     - StateDetector → Detect candidate state")
    print("     - TemplateEngine → Generate from templates")
    print("     - ResponseValidator → Validate response")
    print("     - CRMUpdater → Deterministic CRM updates")
    print("  4. CRM NOTE (mandatory before draft)")
    print("  5. TICKET UPDATE (status, tags)")
    print("  6. DEAL UPDATE (if scenario requires)")
    print("  7. DRAFT CREATION (Zoho Desk)")
    print("  8. FINAL VALIDATION")

    print("\n🎯 To run with a real ticket:")
    print("  workflow = DOCTicketWorkflow()")
    print("  workflow.process_ticket(")
    print("    ticket_id='198709000445353417',")
    print("    auto_create_draft=False,")
    print("    auto_update_crm=False,")
    print("    auto_update_ticket=False")
    print("  )")

    workflow.close()


if __name__ == "__main__":
    test_workflow()
