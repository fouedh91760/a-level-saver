#!/usr/bin/env python3
"""
Framework de test robuste pour l'analyse des lots de tickets.

Ce script effectue une analyse complète et systématique:
1. Extraction données (threads, CRM, ExamT3P)
2. Application des règles LEGACY (date_examen_vtc_helper, session_helper, etc.)
3. Triage + Intention (TriageAgent)
4. Détection état (StateDetector)
5. Génération template (TemplateEngine)
6. Comparaison LEGACY vs STATE ENGINE
7. Analyse de cohérence message ↔ réponse
8. Rapport détaillé avec catégorisation des bugs

Usage:
    python test_lot_analysis.py --lot 2                    # Analyse lot 2 (tickets 11-20)
    python test_lot_analysis.py --start 11 --end 20        # Même chose
    python test_lot_analysis.py --ticket 198709000448029779 # Un seul ticket
"""

import json
import sys
import os
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.agents.deal_linking_agent import DealLinkingAgent
from src.agents.triage_agent import TriageAgent
from src.agents.examt3p_agent import ExamT3PAgent
from src.state_engine.state_detector import StateDetector
from src.state_engine.template_engine import TemplateEngine
from src.utils.date_examen_vtc_helper import analyze_exam_date_situation
from src.utils.session_helper import analyze_session_situation
from src.utils.uber_eligibility_helper import analyze_uber_eligibility
from src.utils.examt3p_crm_sync import can_modify_exam_date


class CoherenceIssueType(Enum):
    """Types d'incohérences détectées."""
    TEMPLATE_PLACEHOLDER_UNRESOLVED = "template_placeholder_unresolved"
    TEMPLATE_WRONG_FOR_INTENTION = "template_wrong_for_intention"
    TEMPLATE_WRONG_FOR_STATE = "template_wrong_for_state"
    LEGACY_VS_STATE_MISMATCH = "legacy_vs_state_mismatch"
    MISSING_DATA_IN_RESPONSE = "missing_data_in_response"
    WRONG_CASE_DETECTION = "wrong_case_detection"
    SPAM_NOT_DETECTED = "spam_not_detected"
    ROUTE_INCORRECT = "route_incorrect"
    FORCE_MAJEURE_NOT_HANDLED = "force_majeure_not_handled"
    DATE_PAST_NOT_HANDLED = "date_past_not_handled"
    CRM_EVALBOX_MISMATCH = "crm_evalbox_mismatch"


@dataclass
class CoherenceIssue:
    """Une incohérence détectée."""
    issue_type: CoherenceIssueType
    severity: str  # "critical", "major", "minor"
    description: str
    expected: str
    actual: str
    fix_suggestion: str = ""


@dataclass
class TicketAnalysis:
    """Résultat complet de l'analyse d'un ticket."""
    ticket_id: str
    ticket_number: str = ""
    subject: str = ""
    status: str = ""

    # Données extraites
    customer_message: str = ""
    deal_id: Optional[str] = None
    deal_data: Dict[str, Any] = field(default_factory=dict)
    examt3p_data: Dict[str, Any] = field(default_factory=dict)
    threads_count: int = 0

    # Triage
    triage_action: str = ""
    triage_intention: Optional[str] = None
    triage_confidence: float = 0.0
    intent_context: Dict[str, Any] = field(default_factory=dict)

    # Legacy analysis
    legacy_date_case: Optional[int] = None
    legacy_date_description: str = ""
    legacy_date_response: str = ""
    legacy_session_data: Dict[str, Any] = field(default_factory=dict)
    legacy_uber_case: str = ""
    legacy_can_modify_date: bool = True
    legacy_cloture_passed: bool = False
    legacy_next_dates: List[Dict] = field(default_factory=list)

    # State Engine
    detected_state: str = ""
    template_used: str = ""
    response_generated: str = ""
    blocks_used: List[str] = field(default_factory=list)

    # Coherence
    coherence_issues: List[CoherenceIssue] = field(default_factory=list)
    coherence_score: str = "OK"

    # Errors
    errors: List[str] = field(default_factory=list)


class LotAnalyzer:
    """Analyseur de lots de tickets."""

    def __init__(self):
        print("Initialisation des composants...")
        self.desk = ZohoDeskClient()
        self.crm = ZohoCRMClient()
        self.deal_agent = DealLinkingAgent()
        self.triage_agent = TriageAgent()
        self.state_detector = StateDetector()
        self.template_engine = TemplateEngine()
        print("OK\n")

    def load_ticket_ids(self, start: int, end: int) -> List[str]:
        """Charge les IDs des tickets depuis le fichier de référence."""
        with open("data/open_doc_tickets.txt", "r") as f:
            all_ids = [line.strip() for line in f if line.strip()]
        return all_ids[start-1:end]

    def analyze_ticket(self, ticket_id: str) -> TicketAnalysis:
        """Analyse complète d'un ticket."""
        result = TicketAnalysis(ticket_id=ticket_id)

        try:
            # 1. EXTRACTION TICKET
            ticket = self.desk.get_ticket(ticket_id)
            if not ticket:
                result.errors.append("TICKET_NOT_FOUND")
                return result

            result.ticket_number = ticket.get("ticketNumber", "")
            result.subject = ticket.get("subject", "")[:100]
            result.status = ticket.get("status", "")

            # 2. EXTRACTION THREADS
            threads = self.desk.get_all_threads_with_full_content(ticket_id)
            result.threads_count = len(threads)

            # Message client (dernier thread incoming)
            for thread in threads:
                if thread.get("direction") == "in":
                    result.customer_message = thread.get("content", "")[:2000]
                    break

            # 3. LIAISON DEAL CRM
            deal_result = self.deal_agent.process({"ticket_id": ticket_id})
            result.deal_id = deal_result.get("deal_id")

            if not result.deal_id:
                # Pas de deal - vérifier si SPAM ou PROSPECT
                self._analyze_no_deal_ticket(result, ticket)
                return result

            # 4. EXTRACTION DONNÉES CRM
            deal_data = self.crm.get_deal(result.deal_id)
            if not deal_data:
                result.errors.append("DEAL_NOT_FETCHED")
                return result

            result.deal_data = deal_data

            # 5. TRIAGE + INTENTION
            triage_result = self.triage_agent.triage_ticket(
                ticket_subject=ticket.get("subject", ""),
                thread_content=result.customer_message,
                deal_data=deal_data,
                current_department="DOC"
            )
            result.triage_action = triage_result.get("action", "")
            result.triage_intention = triage_result.get("detected_intent")
            result.triage_confidence = triage_result.get("confidence", 0.0)
            result.intent_context = triage_result.get("intent_context", {})

            # 6. EXTRACTION EXAMT3P
            if deal_data.get("IDENTIFIANT_EVALBOX") and deal_data.get("MDP_EVALBOX"):
                try:
                    examt3p_agent = ExamT3PAgent()
                    result.examt3p_data = examt3p_agent.extract_data(
                        deal_data["IDENTIFIANT_EVALBOX"],
                        deal_data["MDP_EVALBOX"]
                    )
                except Exception as e:
                    result.errors.append(f"EXAMT3P_ERROR: {str(e)[:50]}")

            # 7. ANALYSE LEGACY
            self._apply_legacy_rules(result, threads)

            # 8. STATE ENGINE
            self._apply_state_engine(result, triage_result, deal_result, threads)

            # 9. ANALYSE COHÉRENCE
            self._analyze_coherence(result)

        except Exception as e:
            result.errors.append(f"ANALYSIS_ERROR: {str(e)[:100]}")

        return result

    def _analyze_no_deal_ticket(self, result: TicketAnalysis, ticket: Dict):
        """Analyse un ticket sans deal CRM."""
        spam_check = self.triage_agent.triage_ticket(
            ticket_subject=ticket.get("subject", ""),
            thread_content=result.customer_message,
            deal_data=None,
            current_department="DOC"
        )
        result.triage_action = spam_check.get("action", "")
        result.triage_intention = spam_check.get("detected_intent")
        result.triage_confidence = spam_check.get("confidence", 0.0)

        if spam_check.get("action") == "SPAM":
            result.status = "SPAM_TO_CLOSE"
            result.coherence_score = "SPAM"
        elif spam_check.get("action") == "ROUTE":
            result.status = "PROSPECT_TO_ROUTE"
        else:
            result.status = "NO_DEAL_NEEDS_REVIEW"

        result.errors.append("NO_DEAL_FOUND")

    def _apply_legacy_rules(self, result: TicketAnalysis, threads: List[Dict]):
        """Applique les règles legacy pour obtenir la réponse attendue."""
        deal_data = result.deal_data

        # 7a. Analyse date examen (LEGACY)
        next_dates = []
        try:
            date_analysis = analyze_exam_date_situation(
                deal_data=deal_data,
                threads=threads,
                crm_client=self.crm,
                examt3p_data=result.examt3p_data
            )
            result.legacy_date_case = date_analysis.get("case")
            result.legacy_date_description = date_analysis.get("case_description", "")
            result.legacy_date_response = date_analysis.get("response_message", "")
            result.legacy_can_modify_date = date_analysis.get("can_modify_exam_date", True)
            next_dates = date_analysis.get("next_dates", [])
            result.legacy_next_dates = next_dates
            # Store cloture_passed for context enrichment
            result.legacy_cloture_passed = date_analysis.get("cloture_passed", False)
        except Exception as e:
            result.errors.append(f"LEGACY_DATE_ERROR: {str(e)[:50]}")

        # 7b. Analyse session (LEGACY)
        # Use next_dates from date analysis, OR the existing Date_examen_VTC if already assigned
        try:
            exam_dates_for_session = next_dates

            # If no next_dates but Date_examen_VTC exists, use the assigned date
            if not exam_dates_for_session and deal_data.get('Date_examen_VTC'):
                date_vtc = deal_data['Date_examen_VTC']
                if isinstance(date_vtc, dict):
                    # Parse "94_2026-03-31" format from name field
                    date_name = date_vtc.get('name', '')
                    if '_' in date_name:
                        parts = date_name.split('_')
                        dept = parts[0]
                        exam_date = parts[1] if len(parts) > 1 else ''
                        exam_dates_for_session = [{
                            'Date_Examen': exam_date,
                            'Departement': dept,
                            'id': date_vtc.get('id')
                        }]

            session_analysis = analyze_session_situation(
                deal_data=deal_data,
                exam_dates=exam_dates_for_session,
                threads=threads,
                crm_client=self.crm
            )
            result.legacy_session_data = session_analysis
        except Exception as e:
            result.errors.append(f"LEGACY_SESSION_ERROR: {str(e)[:50]}")

        # 7c. Analyse Uber (LEGACY)
        try:
            uber_analysis = analyze_uber_eligibility(deal_data)
            result.legacy_uber_case = uber_analysis.get("case", "")
        except Exception as e:
            result.errors.append(f"LEGACY_UBER_ERROR: {str(e)[:50]}")

    def _apply_state_engine(self, result: TicketAnalysis, triage_result: Dict,
                            deal_result: Dict, threads: List[Dict]):
        """Applique le State Engine pour obtenir la réponse générée."""
        try:
            # Détection d'état
            state = self.state_detector.detect_state(
                deal_data=result.deal_data,
                examt3p_data=result.examt3p_data,
                triage_result=triage_result,
                linking_result=deal_result,
                threads_data=threads
            )
            result.detected_state = state.name if state else "UNKNOWN"

            # ENRICHIR le contexte avec les données LEGACY (critique!)
            # 1. Intention
            if result.triage_intention:
                state.context_data["detected_intention"] = result.triage_intention
                state.context_data["intent_context"] = result.intent_context
                # Propager les flags de force majeure
                if result.intent_context.get("mentions_force_majeure"):
                    state.context_data["mentions_force_majeure"] = True
                    state.context_data["force_majeure_type"] = result.intent_context.get("force_majeure_type")
                    state.context_data["force_majeure_details"] = result.intent_context.get("force_majeure_details")
                    state.context_data["is_force_majeure_deces"] = result.intent_context.get("force_majeure_type") == "death"
                    state.context_data["is_force_majeure_medical"] = result.intent_context.get("force_majeure_type") == "medical"
                    state.context_data["is_force_majeure_childcare"] = result.intent_context.get("force_majeure_type") == "childcare"

            # 2. Session data (du legacy)
            if result.legacy_session_data:
                state.context_data["session_data"] = result.legacy_session_data

            # 3. Date data (du legacy)
            state.context_data["legacy_date_case"] = result.legacy_date_case
            state.context_data["can_modify_exam_date"] = result.legacy_can_modify_date
            state.context_data["cloture_passed"] = result.legacy_cloture_passed

            # 4. Next dates (du legacy) - pour proposer des dates si nécessaire
            if result.legacy_next_dates:
                state.context_data["next_dates"] = result.legacy_next_dates

            # Génération template
            template_result = self.template_engine.generate_response(state=state)
            result.template_used = template_result.get("template_used", "")
            result.response_generated = template_result.get("response_text", "")[:1000]
            result.blocks_used = template_result.get("blocks_used", [])

        except Exception as e:
            result.errors.append(f"STATE_ENGINE_ERROR: {str(e)[:100]}")

    def _analyze_coherence(self, result: TicketAnalysis):
        """Analyse la cohérence entre toutes les sources."""
        issues = []

        # 1. Vérifier placeholders non résolus
        if "{{" in result.response_generated or "}}" in result.response_generated:
            issues.append(CoherenceIssue(
                issue_type=CoherenceIssueType.TEMPLATE_PLACEHOLDER_UNRESOLVED,
                severity="critical",
                description="Template contient des placeholders Handlebars non résolus",
                expected="Tous les {{...}} résolus",
                actual=self._extract_unresolved_placeholders(result.response_generated),
                fix_suggestion="Vérifier TemplateEngine._resolve_if_blocks() et le contexte passé"
            ))

        # 2. Vérifier cohérence Evalbox CRM vs ExamT3P
        if result.examt3p_data.get("statut_dossier"):
            expected_evalbox = self._get_expected_evalbox(result.examt3p_data["statut_dossier"])
            actual_evalbox = result.deal_data.get("Evalbox")
            if expected_evalbox and actual_evalbox != expected_evalbox:
                issues.append(CoherenceIssue(
                    issue_type=CoherenceIssueType.CRM_EVALBOX_MISMATCH,
                    severity="major",
                    description="Evalbox CRM ne correspond pas au statut ExamT3P",
                    expected=expected_evalbox,
                    actual=str(actual_evalbox),
                    fix_suggestion="Synchroniser CRM avec ExamT3P via examt3p_crm_sync.py"
                ))

        # 3. Vérifier si cas date passée est bien géré
        if result.legacy_date_case == 7:  # Date passée + validé
            if "no_compte" in result.template_used.lower():
                issues.append(CoherenceIssue(
                    issue_type=CoherenceIssueType.DATE_PAST_NOT_HANDLED,
                    severity="critical",
                    description="CAS 7 (date passée + validé) mal géré - template no_compte incorrect",
                    expected="Template pour examen passé avec suivi",
                    actual=result.template_used,
                    fix_suggestion="Créer état EXAM_PASSED et template correspondant"
                ))

        # 4. Vérifier si intention correspond au template
        intention_template_map = {
            "DEMANDE_IDENTIFIANTS": ["identifiants", "credentials", "login"],
            "CONFIRMATION_SESSION": ["session", "formation"],
            "REPORT_DATE": ["report", "date", "postpone"],
            "STATUT_DOSSIER": ["statut", "suivi", "dossier"],
        }
        if result.triage_intention in intention_template_map:
            expected_keywords = intention_template_map[result.triage_intention]
            if not any(kw in result.template_used.lower() for kw in expected_keywords):
                # Vérifier aussi dans la réponse
                response_lower = result.response_generated.lower()
                if not any(kw in response_lower for kw in expected_keywords):
                    issues.append(CoherenceIssue(
                        issue_type=CoherenceIssueType.TEMPLATE_WRONG_FOR_INTENTION,
                        severity="major",
                        description=f"Intention {result.triage_intention} mais template/réponse ne correspond pas",
                        expected=f"Template contenant: {expected_keywords}",
                        actual=result.template_used,
                        fix_suggestion=f"Vérifier matrice STATE:INTENTION dans state_intention_matrix.yaml"
                    ))

        # 5. Vérifier force majeure urgente
        if result.intent_context.get("mentions_force_majeure") and result.intent_context.get("is_urgent"):
            # Chercher des mots d'empathie: empathie, comprenons, comprenez, comprend, désolé, condoléances
            response_lower = result.response_generated.lower()
            empathy_words = ["empathi", "compren", "désolé", "condoléance", "courage", "soutien"]
            has_empathy = any(word in response_lower for word in empathy_words)
            if not has_empathy:
                issues.append(CoherenceIssue(
                    issue_type=CoherenceIssueType.FORCE_MAJEURE_NOT_HANDLED,
                    severity="major",
                    description="Force majeure urgente détectée mais réponse manque d'empathie",
                    expected="Réponse empathique avec mention du cas particulier",
                    actual="Réponse standard",
                    fix_suggestion="Ajouter bloc empathie_force_majeure dans le template"
                ))

        # 6. Comparer Legacy vs State Engine
        if result.legacy_date_case and result.detected_state:
            legacy_state_expected = self._map_legacy_case_to_state(result.legacy_date_case)
            if legacy_state_expected and legacy_state_expected != result.detected_state:
                issues.append(CoherenceIssue(
                    issue_type=CoherenceIssueType.LEGACY_VS_STATE_MISMATCH,
                    severity="major",
                    description=f"Legacy CAS {result.legacy_date_case} vs State Engine mismatch",
                    expected=legacy_state_expected,
                    actual=result.detected_state,
                    fix_suggestion="Aligner StateDetector avec les cas du legacy"
                ))

        result.coherence_issues = issues
        if issues:
            critical_count = sum(1 for i in issues if i.severity == "critical")
            major_count = sum(1 for i in issues if i.severity == "major")
            result.coherence_score = f"{critical_count}C/{major_count}M"
        else:
            result.coherence_score = "OK"

    def _extract_unresolved_placeholders(self, text: str) -> str:
        """Extrait les placeholders non résolus."""
        import re
        placeholders = re.findall(r'\{\{[^}]+\}\}', text)
        return ", ".join(placeholders[:5]) + ("..." if len(placeholders) > 5 else "")

    def _get_expected_evalbox(self, examt3p_status: str) -> Optional[str]:
        """Retourne l'Evalbox attendu pour un statut ExamT3P."""
        mapping = {
            "En cours de composition": "Dossier crée",
            "En attente de paiement": "Pret a payer",
            "En cours d'instruction": "Dossier Synchronisé",
            "Incomplet": "Refusé CMA",
            "Valide": "VALIDE CMA",
            "En attente de convocation": "Convoc CMA reçue"
        }
        return mapping.get(examt3p_status)

    def _map_legacy_case_to_state(self, legacy_case: int) -> Optional[str]:
        """Mappe un cas legacy vers un état State Engine."""
        mapping = {
            1: "EXAM_DATE_EMPTY",
            2: "EXAM_DATE_PAST_NOT_VALIDATED",
            3: "REFUSED_CMA",
            4: "VALIDE_CMA_WAITING_CONVOC",
            5: "DOSSIER_SYNCHRONIZED",
            6: "EXAM_DATE_ASSIGNED_WAITING",
            7: "EXAM_DATE_PAST_VALIDATED",
            8: "DEADLINE_MISSED",
            9: "CONVOCATION_RECEIVED",
            10: "READY_TO_PAY"
        }
        return mapping.get(legacy_case)

    def analyze_lot(self, start: int, end: int) -> Dict[str, Any]:
        """Analyse un lot complet de tickets."""
        ticket_ids = self.load_ticket_ids(start, end)
        lot_num = (start - 1) // 10 + 1

        print("=" * 80)
        print(f"ANALYSE LOT {lot_num} - Tickets {start}-{end}")
        print("=" * 80)
        print(f"Tickets a analyser: {len(ticket_ids)}\n")

        results = []
        for i, ticket_id in enumerate(ticket_ids):
            print(f"[{i+1}/{len(ticket_ids)}] Ticket {ticket_id}...")
            analysis = self.analyze_ticket(ticket_id)
            results.append(analysis)

            # Afficher résumé
            print(f"  Sujet: {analysis.subject[:50]}")
            print(f"  Etat: {analysis.detected_state} | Triage: {analysis.triage_action}/{analysis.triage_intention}")
            print(f"  Legacy CAS: {analysis.legacy_date_case} | Template: {analysis.template_used}")
            print(f"  Coherence: {analysis.coherence_score}")
            if analysis.coherence_issues:
                for issue in analysis.coherence_issues[:2]:
                    print(f"    [{issue.severity.upper()}] {issue.issue_type.value}: {issue.description[:60]}")
            print()

        # Générer rapport
        report = self._generate_report(results, start, end, lot_num)

        # Sauvegarder
        output_file = f"data/lot{lot_num}_full_analysis_{start}_{end}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        print(f"\nRapport sauvegarde: {output_file}")

        return report

    def _generate_report(self, results: List[TicketAnalysis], start: int, end: int, lot_num: int) -> Dict:
        """Génère un rapport détaillé."""
        # Statistiques
        states = {}
        intentions = {}
        issues_by_type = {}
        critical_issues = []
        major_issues = []

        for r in results:
            # Compter états
            state = r.detected_state or "UNKNOWN"
            states[state] = states.get(state, 0) + 1

            # Compter intentions
            intention = r.triage_intention or "N/A"
            intentions[intention] = intentions.get(intention, 0) + 1

            # Compter issues
            for issue in r.coherence_issues:
                issue_type = issue.issue_type.value
                issues_by_type[issue_type] = issues_by_type.get(issue_type, 0) + 1

                if issue.severity == "critical":
                    critical_issues.append({
                        "ticket": r.ticket_number,
                        "type": issue_type,
                        "description": issue.description,
                        "fix": issue.fix_suggestion
                    })
                elif issue.severity == "major":
                    major_issues.append({
                        "ticket": r.ticket_number,
                        "type": issue_type,
                        "description": issue.description
                    })

        return {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "lot": lot_num,
                "range": f"{start}-{end}",
                "tickets_analyzed": len(results)
            },
            "summary": {
                "states": dict(sorted(states.items(), key=lambda x: -x[1])),
                "intentions": dict(sorted(intentions.items(), key=lambda x: -x[1])),
                "issues_by_type": dict(sorted(issues_by_type.items(), key=lambda x: -x[1])),
                "total_critical": len(critical_issues),
                "total_major": len(major_issues),
                "spam_count": sum(1 for r in results if r.status == "SPAM_TO_CLOSE"),
                "route_count": sum(1 for r in results if r.triage_action == "ROUTE")
            },
            "critical_issues": critical_issues,
            "major_issues": major_issues[:20],  # Top 20
            "tickets": [asdict(r) for r in results]
        }


def main():
    parser = argparse.ArgumentParser(description="Analyse complete des lots de tickets")
    parser.add_argument("--lot", type=int, help="Numero du lot (1-36)")
    parser.add_argument("--start", type=int, help="Ticket de debut")
    parser.add_argument("--end", type=int, help="Ticket de fin")
    parser.add_argument("--ticket", help="Analyser un seul ticket par ID")
    args = parser.parse_args()

    analyzer = LotAnalyzer()

    if args.ticket:
        result = analyzer.analyze_ticket(args.ticket)
        # Sauvegarder dans un fichier pour éviter problèmes d'encodage Windows
        output = asdict(result)
        output_file = f"data/ticket_analysis_{args.ticket[-8:]}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)
        print(f"Resultat sauvegarde: {output_file}")
        print(f"Etat: {result.detected_state}")
        print(f"Template: {result.template_used}")
        print(f"Coherence: {result.coherence_score}")
        if result.coherence_issues:
            for issue in result.coherence_issues:
                print(f"  [{issue.severity}] {issue.issue_type.value}")
    elif args.lot:
        start = (args.lot - 1) * 10 + 1
        end = args.lot * 10
        analyzer.analyze_lot(start, end)
    elif args.start and args.end:
        analyzer.analyze_lot(args.start, args.end)
    else:
        print("Usage:")
        print("  python test_lot_analysis.py --lot 2")
        print("  python test_lot_analysis.py --start 11 --end 20")
        print("  python test_lot_analysis.py --ticket 198709000448029779")


if __name__ == "__main__":
    main()
