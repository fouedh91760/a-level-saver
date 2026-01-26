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

from src.agents.response_generator_agent import ResponseGeneratorAgent
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

logger = logging.getLogger(__name__)


class DOCTicketWorkflow:
    """Complete workflow orchestrator for DOC tickets."""

    def __init__(self):
        """Initialize workflow with all required components."""
        self.desk_client = ZohoDeskClient()
        self.crm_client = ZohoCRMClient()
        self.response_generator = ResponseGeneratorAgent()
        self.deal_linker = DealLinkingAgent()
        self.examt3p_agent = ExamT3PAgent()
        self.dispatcher = TicketDispatcherAgent()
        self.crm_update_agent = CRMUpdateAgent()
        self.triage_agent = TriageAgent()

        logger.info("✅ DOCTicketWorkflow initialized")

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

            triage_result = self._run_triage(ticket_id)
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

            # FEU VERT → Continue
            logger.info("✅ TRIAGE → FEU VERT (continue workflow)")

            # ================================================================
            # STEP 2: AGENT ANALYSTE (6-source data extraction)
            # ================================================================
            logger.info("\n2️⃣  AGENT ANALYSTE - Extraction des données...")
            result['workflow_stage'] = 'ANALYSIS'

            analysis_result = self._run_analysis(ticket_id, triage_result)
            result['analysis_result'] = analysis_result

            # Check VÉRIFICATION #0: Connexion ExamT3P (SEUL critère de blocage)
            exament3p_data = analysis_result.get('exament3p_data', {})
            if not exament3p_data.get('compte_existe') and not exament3p_data.get('extraction_success', True):
                logger.warning("⚠️  ÉCHEC CONNEXION EXAMENT3P → Alerte interne")
                logger.warning("🛑 STOP WORKFLOW (impossible d'extraire les données ExamT3P)")
                result['workflow_stage'] = 'STOPPED_EXAMT3P_FAILED'
                result['success'] = True
                return result

            # Check VÉRIFICATION #1: Identifiants ExamenT3P
            # exament3p_data already retrieved above
            if exament3p_data.get('should_respond_to_candidate'):
                logger.warning("⚠️  IDENTIFIANTS EXAMENT3P INVALIDES OU MANQUANTS")
                logger.info("→ L'agent rédacteur intégrera la demande d'identifiants dans la réponse globale")
            elif not exament3p_data.get('compte_existe'):
                logger.warning("⚠️  COMPTE EXAMENT3P N'EXISTE PAS OU EXTRACTION ÉCHOUÉE")
            else:
                logger.info(f"✅ Identifiants validés (source: {exament3p_data.get('credentials_source')})")

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
            has_ai_updates = bool(response_result.get('crm_updates'))
            scenario_requires_update = response_result.get('requires_crm_update')

            if has_ai_updates or scenario_requires_update:
                if scenario_requires_update:
                    logger.info(f"Champs à updater (scénario): {response_result.get('crm_update_fields', [])}")
                if has_ai_updates:
                    logger.info(f"Champs à updater (AI): {response_result.get('crm_updates', {})}")

                if auto_update_crm and analysis_result.get('deal_id'):
                    # Utiliser CRMUpdateAgent pour centraliser la logique
                    crm_update_result = self.crm_update_agent.update_from_ticket_response(
                        deal_id=analysis_result['deal_id'],
                        ai_updates=response_result.get('crm_updates', {}),
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
                draft_content = response_result['response_text']
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

            if is_vtc_hors_partenariat and result.get('draft_created'):
                logger.info("\n8️⃣b TRANSFER DOCS CAB - Deal VTC classique (hors partenariat)...")
                try:
                    self.desk_client.move_ticket_to_department(ticket_id, "DOCS CAB")
                    logger.info("✅ TRANSFER → Ticket transféré vers DOCS CAB")
                    result['transferred_to'] = "DOCS CAB"
                except Exception as transfer_error:
                    logger.warning(f"⚠️ Impossible de transférer vers DOCS CAB: {transfer_error}")
                    result['transfer_error'] = str(transfer_error)

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
        threads = self.desk_client.get_all_threads_with_full_content(ticket_id)
        last_thread_content = ""
        for thread in threads:
            if thread.get('direction') == 'in':
                last_thread_content = get_clean_thread_content(thread)
                break

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

        # Copier l'intention détectée et son contexte (pour ResponseGeneratorAgent)
        triage_result['detected_intent'] = ai_triage.get('detected_intent')
        triage_result['intent_context'] = ai_triage.get('intent_context', {})

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
                'exament3p_data': Dict,
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

        contact_data = {}
        if email:
            contact_data = {
                'email': email,
                'contact_id': deal_data.get('Contact_Name', {}).get('id') if deal_data else None
            }

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

        # Initialiser exament3p_data
        exament3p_data = {
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

            # Ajouter le flag dans exament3p_data pour visibilité
            exament3p_data['duplicate_payment_alert'] = True
            exament3p_data['duplicate_accounts'] = duplicate_accounts

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
            exament3p_data['switched_to_paid_account'] = True

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
                    # Fusionner les données extraites avec exament3p_data
                    exament3p_data.update(examt3p_result)
                    exament3p_data['compte_existe'] = True
                    logger.info("  ✅ Données ExamenT3P extraites avec succès")
                else:
                    logger.warning(f"  ⚠️  Échec extraction ExamenT3P: {examt3p_result.get('error')}")
                    exament3p_data['extraction_error'] = examt3p_result.get('error')

            except Exception as e:
                logger.error(f"  ❌ Erreur lors de l'extraction ExamenT3P: {e}")
                exament3p_data['extraction_error'] = str(e)

        elif credentials_result.get('credentials_found'):
            # Identifiants trouvés mais connexion échouée
            logger.warning(f"  ❌ Identifiants trouvés mais connexion échouée: {credentials_result.get('connection_error')}")
            exament3p_data['extraction_error'] = f"Connexion échouée: {credentials_result.get('connection_error')}"

        else:
            # Identifiants non trouvés
            logger.warning("  ⚠️  Identifiants ExamenT3P introuvables")
            exament3p_data['extraction_error'] = "Identifiants non trouvés dans le CRM ni dans les threads"

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
        if exament3p_data.get('compte_existe') and deal_id:
            logger.info("  🔄 Synchronisation ExamT3P → CRM...")
            sync_result = sync_examt3p_to_crm(
                deal_id=deal_id,
                deal_data=deal_data,
                examt3p_data=exament3p_data,
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
                examt3p_data=exament3p_data,
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
        # FLAG: Blocage dates/sessions si CAS A, B, D ou E
        # A = documents non envoyés
        # B = test sélection non passé
        # D = Compte_Uber non vérifié (email ≠ compte Uber Driver)
        # E = Non éligible selon Uber (raisons inconnues)
        # ================================================================
        uber_case_blocks_dates = False
        if uber_eligibility_result.get('is_uber_20_deal'):
            blocking_cases = ['A', 'B', 'D', 'E']
            if uber_eligibility_result.get('case') in blocking_cases:
                logger.warning(f"  🚨 CAS {uber_eligibility_result['case']}: {uber_eligibility_result['case_description']}")
                logger.warning("  ⛔ BLOCAGE DATES/SESSIONS: Candidat doit résoudre le problème")
                uber_case_blocks_dates = True
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
        if exament3p_data.get('should_respond_to_candidate') and not exament3p_data.get('compte_existe'):
            if exament3p_data.get('credentials_request_sent'):
                logger.warning("  🚨 DEMANDE D'IDENTIFIANTS DÉJÀ ENVOYÉE MAIS PAS DE RÉPONSE")
                logger.warning("  → La réponse doit confirmer que c'est normal et redemander les identifiants")
            elif exament3p_data.get('account_creation_requested'):
                logger.warning("  🚨 CRÉATION DE COMPTE DEMANDÉE MAIS PAS D'IDENTIFIANTS REÇUS")
                logger.warning("  → La réponse doit relancer le candidat sur la création de compte")
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
                examt3p_data=exament3p_data
            )

            if date_examen_vtc_result.get('should_include_in_response'):
                logger.info(f"  ➡️ CAS {date_examen_vtc_result['case']}: {date_examen_vtc_result['case_description']}")
            else:
                logger.info(f"  ✅ Date examen VTC OK (CAS {date_examen_vtc_result['case']})")
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

        # Vérifier si session déjà assignée dans CRM
        current_session = deal_data.get('Session')
        session_is_empty = not current_session

        # Dates à utiliser pour la proposition de sessions:
        # - Si next_dates existe → utiliser next_dates (nouvelles dates proposées)
        # - Si next_dates vide MAIS date_examen_info existe ET session vide → utiliser la date existante
        exam_dates_for_session = next_dates

        if not next_dates and session_is_empty:
            # Pas de nouvelles dates, mais on a peut-être une date d'examen déjà assignée
            date_examen_info = date_examen_vtc_result.get('date_examen_info')
            if date_examen_info and isinstance(date_examen_info, dict):
                # Utiliser la date d'examen existante pour proposer des sessions
                exam_dates_for_session = [date_examen_info]
                logger.info("  📚 Session vide mais date examen assignée - recherche sessions correspondantes...")

        should_analyze_sessions = (
            not skip_date_session_analysis
            and exam_dates_for_session
            and (date_examen_vtc_result.get('should_include_in_response') or session_is_empty)
        )

        if should_analyze_sessions:
            logger.info("  📚 Recherche des sessions de formation associées...")
            session_data = analyze_session_situation(
                deal_data=deal_data,
                exam_dates=exam_dates_for_session,
                threads=threads_data,
                crm_client=self.crm_client
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

        return {
            'contact_data': contact_data,
            'deal_id': deal_id,
            'deal_data': deal_data,
            'exament3p_data': exament3p_data,
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
            # Pour les cas Uber (A, B, D, E), on utilise uber_case_response avec le message pré-généré
            'credentials_only_response': skip_reason == 'credentials_invalid',
            'uber_case_response': skip_reason and skip_reason.startswith('uber_case_'),
            'skip_reason': skip_reason,  # Raison du skip (credentials_invalid, uber_case_X, dossier_not_received)
            'dossier_not_received': dossier_not_received_blocks_dates,
            'uber_case_blocks_dates': uber_case_blocks_dates,
            # Cohérence formation/examen (cas manqué formation + examen imminent)
            'training_exam_consistency_result': training_exam_consistency_result,
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

Après vérification de votre dossier, je constate que vous avez déjà bénéficié de l'offre Uber à 20€ pour le passage de l'examen VTC. **Cette offre n'est valable qu'une seule fois par candidat.**

Si vous souhaitez vous réinscrire à l'examen VTC, voici vos options :

**Option 1 : Inscription autonome**
- Vous pouvez vous inscrire vous-même sur le site de la CMA (ExamT3P)
- Les frais d'inscription à l'examen s'élèvent à **241€**, à votre charge
- Site d'inscription : https://exament3p.cma-france.fr

**Option 2 : Formation avec CAB Formations**
Si vous souhaitez suivre une formation de préparation à l'examen VTC, nous pouvons vous proposer :

📚 **Formation en présentiel** : sur l'un de nos centres de formation

📚 **Formation E-learning** : finançable via votre **CPF** (Compte Personnel de Formation)

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

    def _run_response_generation(
        self,
        ticket_id: str,
        triage_result: Dict,
        analysis_result: Dict
    ) -> Dict:
        """
        Run AGENT RÉDACTEUR - Generate response with Claude + RAG.

        Returns response_result from ResponseGeneratorAgent.
        """
        # Get ticket info
        ticket = self.desk_client.get_ticket(ticket_id)

        # Extract customer message with proper content extraction
        from src.utils.text_utils import get_clean_thread_content

        customer_message = ""
        for thread in analysis_result.get('threads', []):
            if thread.get('direction') == 'in':
                customer_message = get_clean_thread_content(thread)
                break

        # Generate response with FULL THREAD HISTORY
        # Le générateur doit voir TOUT l'historique pour ne pas répéter
        # et adapter sa réponse au contexte complet des échanges
        response_result = self.response_generator.generate_with_validation_loop(
            ticket_subject=ticket.get('subject', ''),
            customer_message=customer_message,
            crm_data=analysis_result.get('deal_data'),
            exament3p_data=analysis_result.get('exament3p_data'),
            evalbox_data=analysis_result.get('evalbox_data'),
            date_examen_vtc_data=analysis_result.get('date_examen_vtc_result'),
            session_data=analysis_result.get('session_data'),
            uber_eligibility_data=analysis_result.get('uber_eligibility_result'),
            credentials_only_response=analysis_result.get('credentials_only_response', False),
            threads=analysis_result.get('threads'),  # Historique complet des échanges
            training_exam_consistency_data=analysis_result.get('training_exam_consistency_result'),  # Cohérence formation/examen
            triage_result=triage_result  # Intention détectée par IA (REPORT_DATE, etc.)
        )

        return response_result

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
        - Lien vers le ticket Desk
        - Mises à jour CRM effectuées
        - Next steps candidat (généré par IA)
        - Next steps CAB (généré par IA)
        - Alertes si nécessaire
        """
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

        # === NEXT STEPS (généré par IA) ===
        next_steps = self._generate_next_steps_with_ai(analysis_result, response_result)
        if next_steps:
            lines.append(next_steps)
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
        examt3p_data = analysis_result.get('exament3p_data', {})
        if examt3p_data.get('duplicate_paid_accounts'):
            alerts.append("⚠️ DOUBLE COMPTE PAYÉ - vérifier paiement")

        if alerts:
            lines.append("Alertes:")
            lines.extend(alerts)
        else:
            lines.append("✓ Aucune alerte")

        return "\n".join(lines)

    def _generate_next_steps_with_ai(
        self,
        analysis_result: Dict,
        response_result: Dict
    ) -> str:
        """
        Utilise Claude Haiku pour générer les next steps intelligents.
        """
        import anthropic

        # Préparer le contexte pour l'IA
        deal_data = analysis_result.get('deal_data', {})
        examt3p_data = analysis_result.get('exament3p_data', {})
        date_result = analysis_result.get('date_examen_vtc_result', {})
        session_data = analysis_result.get('session_data', {})
        uber_result = analysis_result.get('uber_eligibility_result', {})

        context = f"""Contexte candidat VTC:
- Statut Evalbox: {deal_data.get('Evalbox', 'Non défini')}
- Statut ExamT3P: {examt3p_data.get('statut_dossier', 'N/A')}
- Date examen: {date_result.get('date_examen_info', {}).get('Date_Examen', 'Non définie') if isinstance(date_result.get('date_examen_info'), dict) else 'Non définie'}
- Session formation: {'Assignée' if deal_data.get('Session') else 'Non assignée'}
- Cas date examen: {date_result.get('case_description', 'N/A')}
- Deal Uber 20€: {'Oui - ' + uber_result.get('case_description', '') if uber_result.get('is_uber_20_deal') else 'Non'}
"""

        prompt = f"""{context}

Génère les prochaines étapes en 2-3 bullet points MAX par section.
Sois TRÈS concis (5-10 mots par point).

Format EXACT à respecter:
Next steps candidat:
• [action 1]
• [action 2]

Next steps CAB:
• [action 1]
• [action 2]

Réponds UNIQUEMENT avec ce format, rien d'autre."""

        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.warning(f"Erreur génération next steps IA: {e}")
            # Fallback basique
            return "Next steps candidat:\n• Consulter le draft de réponse\n\nNext steps CAB:\n• Vérifier et envoyer la réponse"

    def _prepare_ticket_updates(self, response_result: Dict) -> Dict:
        """Prepare ticket field updates."""
        updates = {}

        # Could update tags, status, priority based on scenario
        scenarios = response_result.get('detected_scenarios', [])

        if scenarios:
            # Add scenario tags
            updates['tags'] = scenarios[:3]  # Max 3 tags

        return updates

    def _prepare_deal_updates(
        self,
        response_result: Dict,
        analysis_result: Dict
    ) -> Dict:
        """
        Prepare CRM deal field updates.

        Uses AI-extracted updates from ResponseGeneratorAgent (crm_updates)
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
        # ExamT3PAgent and TriageAgent don't have close() method, skip them


def test_workflow():
    """Test workflow with a sample ticket."""
    print("\n" + "=" * 80)
    print("TEST DOC TICKET WORKFLOW")
    print("=" * 80)

    workflow = DOCTicketWorkflow()

    # Test with a real ticket ID (would need actual ticket)
    # For now, just show structure is correct
    print("\n✅ Workflow initialized successfully")
    print("\n📋 Workflow stages:")
    print("  1. AGENT TRIEUR (triage with STOP & GO)")
    print("  2. AGENT ANALYSTE (6-source data extraction)")
    print("  3. AGENT RÉDACTEUR (Claude + RAG response generation)")
    print("  4. CRM NOTE (mandatory before draft)")
    print("  5. TICKET UPDATE (status, tags)")
    print("  6. DEAL UPDATE (if scenario requires)")
    print("  7. DRAFT CREATION (Zoho Desk)")
    print("  8. FINAL VALIDATION")

    print("\n🎯 To run with a real ticket:")
    print("  workflow.process_ticket(")
    print("    ticket_id='198709000445353417',")
    print("    auto_create_draft=False,")
    print("    auto_update_crm=False,")
    print("    auto_update_ticket=False")
    print("  )")

    workflow.close()


if __name__ == "__main__":
    test_workflow()
