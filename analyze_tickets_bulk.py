#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analyse en masse des tickets ouverts - MODE DRY RUN COMPLET

Lance le workflow complet sur chaque ticket SAUF:
- Création de draft Zoho Desk
- Mise à jour CRM (notes, champs)

Analyse la cohérence des réponses générées avec les données et threads.

Usage:
    python analyze_tickets_bulk.py [--limit N] [--department DOC]
"""

import sys
import json
import logging
import argparse
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional

# Configurer le logging pour réduire le bruit
logging.basicConfig(level=logging.WARNING)
logging.getLogger('src.workflows').setLevel(logging.WARNING)
logging.getLogger('src.agents').setLevel(logging.WARNING)
logging.getLogger('src.utils').setLevel(logging.WARNING)
logging.getLogger('src.zoho_client').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# Imports projet
from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.agents.triage_agent import TriageAgent
from src.agents.deal_linking_agent import DealLinkingAgent
from src.agents.examt3p_agent import ExamT3PAgent
from src.state_engine.state_detector import StateDetector
from src.state_engine.template_engine import TemplateEngine
from src.state_engine.response_validator import ResponseValidator
from src.utils.examt3p_credentials_helper import get_credentials_with_validation
from src.utils.date_examen_vtc_helper import analyze_exam_date_situation, get_next_exam_dates
from src.utils.uber_eligibility_helper import analyze_uber_eligibility
from src.utils.session_helper import analyze_session_situation
from src.utils.examt3p_crm_sync import determine_evalbox_from_examt3p


class BulkWorkflowAnalyzer:
    """Analyse en masse avec workflow complet - Mode DRY RUN."""

    def __init__(self):
        print("🔧 Initialisation des composants...")
        self.desk_client = ZohoDeskClient()
        self.crm_client = ZohoCRMClient()
        self.triage_agent = TriageAgent()
        self.linking_agent = DealLinkingAgent()
        self.examt3p_agent = ExamT3PAgent()
        self.state_detector = StateDetector()
        self.template_engine = TemplateEngine()
        self.validator = ResponseValidator()
        print("   ✅ Composants initialisés")

        # Résultats détaillés
        self.results = []
        self.ecarts = []
        self.ajustements_suggeres = defaultdict(list)

    def get_open_tickets(self, department: str = "DOC", limit: int = 20) -> List[Dict]:
        """Récupère les tickets ouverts d'un département."""
        print(f"\n📥 Récupération des tickets ouverts ({department})...")

        dept_id = self.desk_client.get_department_id_by_name(department)
        if not dept_id:
            print(f"   ❌ Département '{department}' non trouvé")
            return []

        all_tickets = self.desk_client.list_tickets(status="Open", limit=100)
        tickets_data = all_tickets.get('data', [])
        tickets = [t for t in tickets_data if t.get('departmentId') == dept_id][:limit]

        print(f"   ✅ {len(tickets)} tickets récupérés")
        return tickets

    def run_workflow_dry_run(self, ticket_id: str) -> Dict[str, Any]:
        """
        Lance le workflow complet en mode DRY RUN.

        Exécute toutes les étapes SAUF:
        - Création de draft
        - Mise à jour CRM
        """
        result = {
            'ticket_id': ticket_id,
            'success': False,
            'step_reached': 'INIT',
            'data': {},
            'response': {},
            'analysis': {},
            'ecarts': [],
            'ajustements': []
        }

        try:
            # ============================================================
            # STEP 1: Récupérer ticket et threads
            # ============================================================
            ticket = self.desk_client.get_ticket(ticket_id)
            threads = self.desk_client.get_all_threads_with_full_content(ticket_id)

            result['data']['subject'] = ticket.get('subject', '')
            result['data']['contact_email'] = ticket.get('email', '')
            result['step_reached'] = 'TICKET_LOADED'

            # Extraire le dernier message client
            customer_message = ""
            for thread in threads:
                if thread.get('direction') == 'in':
                    customer_message = thread.get('content', thread.get('summary', ''))
                    break

            result['data']['customer_message'] = customer_message[:500] if customer_message else "N/A"

            # ============================================================
            # STEP 2: Deal Linking
            # ============================================================
            linking_result = self.linking_agent.process({
                'ticket_id': ticket_id,
                'ticket': ticket,
                'threads': threads
            })

            deal_data = linking_result.get('deal_data', {})
            result['data']['deal_id'] = linking_result.get('deal_id')
            result['data']['deal_name'] = deal_data.get('Deal_Name', 'N/A')
            result['data']['stage'] = deal_data.get('Stage', 'N/A')
            result['data']['amount'] = deal_data.get('Amount')
            result['data']['evalbox'] = deal_data.get('Evalbox', 'N/A')
            result['step_reached'] = 'DEAL_LINKED'

            if not deal_data:
                result['ecarts'].append({
                    'type': 'NO_DEAL',
                    'message': "Aucun deal CRM trouvé pour ce ticket",
                    'details': f"Email: {result['data']['contact_email']}"
                })
                return result

            # Vérifier doublon Uber
            if linking_result.get('has_duplicate_uber_offer'):
                result['data']['doublon_uber'] = True
                result['ecarts'].append({
                    'type': 'DOUBLON_UBER',
                    'message': "Doublon offre Uber 20€ détecté",
                    'details': f"{len(linking_result.get('duplicate_deals', []))} deals 20€ GAGNÉ"
                })

            # ============================================================
            # STEP 3: Triage IA
            # ============================================================
            triage_result = self.triage_agent.triage_ticket(ticket_id)

            result['data']['triage_action'] = triage_result.get('action')
            result['data']['triage_intention'] = triage_result.get('detected_intent')
            result['data']['triage_confidence'] = triage_result.get('confidence')
            result['data']['force_majeure_type'] = triage_result.get('intent_context', {}).get('force_majeure_type')
            result['step_reached'] = 'TRIAGE_DONE'

            if triage_result.get('action') == 'ROUTE':
                result['data']['route_to'] = triage_result.get('target_department')
                result['ecarts'].append({
                    'type': 'ROUTED',
                    'message': f"Ticket routé vers {triage_result.get('target_department')}",
                    'details': triage_result.get('reason')
                })
                result['success'] = True
                return result

            if triage_result.get('action') == 'SPAM':
                result['ecarts'].append({
                    'type': 'SPAM',
                    'message': "Ticket détecté comme SPAM"
                })
                result['success'] = True
                return result

            # ============================================================
            # STEP 4: ExamT3P (extraction données seulement, pas de sync CRM)
            # ============================================================
            examt3p_data = {'compte_existe': False, 'connection_test_success': False}

            try:
                creds = get_credentials_with_validation(
                    deal_data=deal_data,
                    threads=threads,
                    examt3p_agent=self.examt3p_agent
                )

                result['data']['examt3p_identifiant'] = creds.get('identifiant', 'N/A')
                result['data']['examt3p_source'] = creds.get('credentials_source', 'N/A')
                result['data']['examt3p_compte_existe'] = creds.get('compte_existe', False)
                result['data']['examt3p_connection_ok'] = creds.get('connection_test_success', False)

                if creds.get('connection_test_success'):
                    extracted = self.examt3p_agent.extract_data(
                        creds['identifiant'],
                        creds['mot_de_passe']
                    )
                    examt3p_data = {**extracted, **creds}

                    result['data']['examt3p_statut'] = extracted.get('statut_dossier', 'N/A')
                    result['data']['examt3p_num_dossier'] = extracted.get('num_dossier', 'N/A')
                    result['data']['examt3p_docs_count'] = len(extracted.get('documents', []))

                    # Déterminer l'Evalbox attendu
                    expected_evalbox = determine_evalbox_from_examt3p(extracted.get('statut_dossier'))
                    if expected_evalbox and expected_evalbox != deal_data.get('Evalbox'):
                        result['ecarts'].append({
                            'type': 'EVALBOX_MISMATCH',
                            'message': f"Evalbox CRM ({deal_data.get('Evalbox')}) ≠ ExamT3P ({expected_evalbox})",
                            'details': f"Statut ExamT3P: {extracted.get('statut_dossier')}"
                        })
                else:
                    examt3p_data.update(creds)

            except Exception as e:
                result['data']['examt3p_error'] = str(e)[:100]

            result['step_reached'] = 'EXAMT3P_DONE'

            # ============================================================
            # STEP 5: Analyse date examen
            # ============================================================
            date_result = analyze_exam_date_situation(
                deal_data=deal_data,
                threads=threads,
                crm_client=self.crm_client,
                examt3p_data=examt3p_data
            )

            result['data']['date_case'] = date_result.get('case')
            result['data']['date_case_desc'] = date_result.get('description', '')[:100]
            result['data']['can_modify_date'] = date_result.get('can_modify_exam_date', True)
            result['step_reached'] = 'DATE_ANALYSIS_DONE'

            # ============================================================
            # STEP 6: Uber eligibility
            # ============================================================
            uber_result = analyze_uber_eligibility(deal_data)
            result['data']['uber_case'] = uber_result.get('case')
            result['data']['uber_eligible'] = uber_result.get('is_eligible')

            # ============================================================
            # STEP 7: State Detection
            # ============================================================
            detected_state = self.state_detector.detect(
                triage_result=triage_result,
                linking_result=linking_result,
                deal_data=deal_data,
                examt3p_data=examt3p_data,
                date_result=date_result,
                uber_result=uber_result
            )

            result['data']['state_id'] = detected_state.state_id
            result['data']['state_name'] = detected_state.name
            result['data']['state_priority'] = detected_state.priority
            result['step_reached'] = 'STATE_DETECTED'

            # Enrichir le contexte pour REPORT_DATE
            if triage_result.get('detected_intent') == 'REPORT_DATE':
                dept = deal_data.get('CMA_de_depot') or examt3p_data.get('departement')
                if dept:
                    next_dates = get_next_exam_dates(self.crm_client, dept, limit=5)
                    detected_state.context_data['next_dates'] = next_dates

            # ============================================================
            # STEP 8: Template Generation
            # ============================================================
            template_result = self.template_engine.generate_response(
                state=detected_state,
                ai_generator=None  # Pas de personnalisation IA pour l'analyse
            )

            response_text = template_result.get('response_text', '')
            result['response']['template_used'] = template_result.get('template_used')
            result['response']['blocks_included'] = template_result.get('blocks_included', [])
            result['response']['length'] = len(response_text)
            result['response']['text_preview'] = response_text[:300].replace('\n', ' ')
            result['step_reached'] = 'RESPONSE_GENERATED'

            # ============================================================
            # STEP 9: Validation
            # ============================================================
            validation_result = self.validator.validate(
                response_text=response_text,
                state=detected_state,
                template_used=template_result.get('template_used')
            )

            result['response']['validation_valid'] = validation_result.valid
            result['response']['validation_errors'] = [e.message for e in validation_result.errors]
            result['response']['validation_warnings'] = [w.message for w in validation_result.warnings]
            result['step_reached'] = 'VALIDATED'

            for error in validation_result.errors:
                result['ecarts'].append({
                    'type': 'VALIDATION_ERROR',
                    'message': error.message
                })

            # ============================================================
            # STEP 10: Analyse de cohérence
            # ============================================================
            self._analyze_coherence(result, customer_message, deal_data, examt3p_data, response_text)

            result['success'] = True
            result['step_reached'] = 'COMPLETED'

        except Exception as e:
            result['error'] = str(e)
            result['ecarts'].append({
                'type': 'EXCEPTION',
                'message': str(e)[:200]
            })

        return result

    def _analyze_coherence(
        self,
        result: Dict,
        customer_message: str,
        deal_data: Dict,
        examt3p_data: Dict,
        response_text: str
    ):
        """Analyse la cohérence entre la réponse et les données."""

        analysis = result['analysis']
        ecarts = result['ecarts']
        ajustements = result['ajustements']

        # 1. Vérifier que les identifiants sont inclus si disponibles
        identifiant = examt3p_data.get('identifiant') or deal_data.get('IDENTIFIANT_EVALBOX')
        if identifiant and examt3p_data.get('compte_existe'):
            if identifiant not in response_text and 'identifiant' not in response_text.lower():
                if result['data'].get('state_name') not in ['PROSPECT_UBER_20', 'UBER_CAS_A']:
                    ecarts.append({
                        'type': 'MISSING_CREDENTIALS',
                        'message': "Identifiants ExamT3P disponibles mais non inclus dans la réponse"
                    })
                    ajustements.append("Ajouter bloc identifiants_examt3p au template")

        # 2. Vérifier cohérence intention vs réponse
        intention = result['data'].get('triage_intention')

        if intention == 'REPORT_DATE' and 'report' not in response_text.lower():
            ecarts.append({
                'type': 'INTENTION_MISMATCH',
                'message': "Intention REPORT_DATE mais réponse ne mentionne pas le report"
            })

        if intention == 'DEMANDE_IDENTIFIANTS' and identifiant and identifiant not in response_text:
            ecarts.append({
                'type': 'INTENTION_MISMATCH',
                'message': "Demande d'identifiants mais identifiants non fournis"
            })

        # 3. Vérifier que les dates sont proposées si nécessaire
        if result['data'].get('date_case') in [1, 2, 8]:  # Date vide, passée, deadline ratée
            if 'date' not in response_text.lower() and 'examen' not in response_text.lower():
                ecarts.append({
                    'type': 'MISSING_DATES',
                    'message': f"Cas date {result['data'].get('date_case')} mais pas de dates proposées"
                })
                ajustements.append("Ajouter bloc prochaines_dates_examen au template")

        # 4. Vérifier les cas Uber bloquants
        uber_case = result['data'].get('uber_case')
        if uber_case in ['A', 'B', 'D', 'E']:
            if 'uber' not in response_text.lower() and 'document' not in response_text.lower():
                ecarts.append({
                    'type': 'UBER_CASE_NOT_HANDLED',
                    'message': f"Cas Uber {uber_case} mais pas de mention dans la réponse"
                })

        # 5. Vérifier force majeure
        fm_type = result['data'].get('force_majeure_type')
        if fm_type:
            if 'cma' not in response_text.lower() and 'justificatif' not in response_text.lower():
                ecarts.append({
                    'type': 'FORCE_MAJEURE_INCOMPLETE',
                    'message': f"Force majeure {fm_type} mais procédure non expliquée"
                })

        # 6. Analyser le message client pour détecter des besoins non couverts
        msg_lower = customer_message.lower() if customer_message else ""

        keywords_to_check = [
            ('convocation', 'convocation'),
            ('formation', 'formation'),
            ('e-learning', 'e-learning'),
            ('paiement', 'paiement'),
            ('remboursement', 'remboursement'),
        ]

        for keyword, response_keyword in keywords_to_check:
            if keyword in msg_lower and response_keyword not in response_text.lower():
                analysis[f'keyword_{keyword}'] = 'mentioned_not_addressed'

        result['analysis'] = analysis

    def run_analysis(self, department: str = "DOC", limit: int = 20):
        """Lance l'analyse en masse."""
        print("=" * 80)
        print("🔍 ANALYSE EN MASSE - WORKFLOW COMPLET DRY RUN")
        print("   ✅ Workflow complet exécuté")
        print("   ❌ Pas de création de draft")
        print("   ❌ Pas de mise à jour CRM")
        print("=" * 80)

        tickets = self.get_open_tickets(department, limit)
        if not tickets:
            print("❌ Aucun ticket trouvé")
            return

        # Stats
        stats = {
            'total': len(tickets),
            'success': 0,
            'no_deal': 0,
            'routed': 0,
            'by_state': defaultdict(int),
            'by_intention': defaultdict(int),
            'by_template': defaultdict(int),
            'by_ecart_type': defaultdict(int),
            'ecarts_details': []
        }

        for i, ticket in enumerate(tickets, 1):
            ticket_id = ticket.get('id')
            subject = ticket.get('subject', '')[:40]

            print(f"\n[{i}/{len(tickets)}] {ticket_id}: {subject}...")

            result = self.run_workflow_dry_run(ticket_id)
            self.results.append(result)

            # Collecter stats
            if result['success']:
                stats['success'] += 1

            if any(e['type'] == 'NO_DEAL' for e in result.get('ecarts', [])):
                stats['no_deal'] += 1
                print(f"   ⚠️  Pas de deal CRM")
                continue

            if any(e['type'] == 'ROUTED' for e in result.get('ecarts', [])):
                stats['routed'] += 1
                route_to = result['data'].get('route_to', 'N/A')
                print(f"   ➡️  Routé vers {route_to}")
                continue

            state = result['data'].get('state_name', 'N/A')
            intention = result['data'].get('triage_intention', 'N/A')
            template = result['response'].get('template_used', 'N/A')

            stats['by_state'][state] += 1
            stats['by_intention'][intention] += 1
            stats['by_template'][template] += 1

            print(f"   État: {state} | Intention: {intention} | Template: {template}")

            # Écarts
            for ecart in result.get('ecarts', []):
                stats['by_ecart_type'][ecart['type']] += 1
                if ecart['type'] not in ['NO_DEAL', 'ROUTED', 'SPAM']:
                    print(f"   ⚠️  {ecart['type']}: {ecart['message'][:60]}")
                    stats['ecarts_details'].append({
                        'ticket_id': ticket_id,
                        'subject': subject,
                        **ecart
                    })

            # Ajustements
            for adj in result.get('ajustements', []):
                self.ajustements_suggeres[adj].append(ticket_id)

        # Rapport final
        self._print_report(stats)
        self._save_results(stats)

    def _print_report(self, stats: Dict):
        """Affiche le rapport d'analyse."""
        print("\n" + "=" * 80)
        print("📊 RAPPORT D'ANALYSE")
        print("=" * 80)

        print(f"\n📈 STATISTIQUES:")
        print(f"   Total: {stats['total']}")
        print(f"   Succès: {stats['success']}")
        print(f"   Sans deal CRM: {stats['no_deal']}")
        print(f"   Routés: {stats['routed']}")

        if stats['by_state']:
            print(f"\n🎯 PAR ÉTAT:")
            for state, count in sorted(stats['by_state'].items(), key=lambda x: -x[1]):
                print(f"   {state}: {count}")

        if stats['by_intention']:
            print(f"\n💬 PAR INTENTION:")
            for intention, count in sorted(stats['by_intention'].items(), key=lambda x: -x[1]):
                print(f"   {intention}: {count}")

        if stats['by_template']:
            print(f"\n📝 PAR TEMPLATE:")
            for template, count in sorted(stats['by_template'].items(), key=lambda x: -x[1]):
                print(f"   {template}: {count}")

        if stats['by_ecart_type']:
            print(f"\n⚠️  ÉCARTS PAR TYPE:")
            for ecart_type, count in sorted(stats['by_ecart_type'].items(), key=lambda x: -x[1]):
                print(f"   {ecart_type}: {count}")

        if self.ajustements_suggeres:
            print(f"\n🔧 AJUSTEMENTS SUGGÉRÉS:")
            for ajustement, ticket_ids in sorted(self.ajustements_suggeres.items(), key=lambda x: -len(x[1])):
                print(f"   [{len(ticket_ids)}x] {ajustement}")

        if stats['ecarts_details']:
            print(f"\n🔍 DÉTAIL DES ÉCARTS ({len(stats['ecarts_details'])}):")
            for ecart in stats['ecarts_details'][:15]:
                print(f"   • {ecart['ticket_id']}: {ecart['type']}")
                print(f"     {ecart['message'][:70]}")

        print("\n" + "=" * 80)

    def _save_results(self, stats: Dict):
        """Sauvegarde les résultats."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bulk_analysis_{timestamp}.json"

        output = {
            'timestamp': timestamp,
            'stats': {
                'total': stats['total'],
                'success': stats['success'],
                'no_deal': stats['no_deal'],
                'routed': stats['routed'],
                'by_state': dict(stats['by_state']),
                'by_intention': dict(stats['by_intention']),
                'by_template': dict(stats['by_template']),
                'by_ecart_type': dict(stats['by_ecart_type'])
            },
            'ajustements_suggeres': {k: list(v) for k, v in self.ajustements_suggeres.items()},
            'ecarts_details': stats['ecarts_details'],
            'results': self.results
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        print(f"\n💾 Résultats sauvegardés: {filename}")


def main():
    parser = argparse.ArgumentParser(description="Analyse en masse - Workflow complet DRY RUN")
    parser.add_argument('--limit', type=int, default=10, help="Nombre max de tickets")
    parser.add_argument('--department', type=str, default="DOC", help="Département")

    args = parser.parse_args()

    analyzer = BulkWorkflowAnalyzer()
    analyzer.run_analysis(department=args.department, limit=args.limit)


if __name__ == "__main__":
    main()
