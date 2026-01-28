"""
Script de test pour le workflow DOC complet avec validation ExamT3P et Date Examen VTC.

Ce script teste le workflow complet incluant :
1. AGENT TRIEUR
2. AGENT ANALYSTE (incluant validation ExamT3P + Date Examen VTC)
3. AGENT RÉDACTEUR (State Engine ou Legacy mode)
4. CRM Note
5. Ticket Update
6. Deal Update
7. Draft Creation
8. Final Validation

Usage:
    python test_doc_workflow_with_examt3p.py <ticket_id> [options]
    python test_doc_workflow_with_examt3p.py --bulk [options]

Options:
    --legacy          Utiliser l'ancien mode IA (ResponseGeneratorAgent)
    --dry-run         Ne pas mettre à jour le CRM ni créer de draft
    --no-crm-update   Ne pas mettre à jour le CRM
    --no-draft        Ne pas créer de draft dans Zoho Desk
    --bulk            Traiter tous les tickets ouverts du département DOC
    --output FILE     Sauvegarder les résultats dans un fichier JSON (mode bulk)

Exemples:
    # Mode State Engine (défaut - déterministe)
    python test_doc_workflow_with_examt3p.py 198709000447309732

    # Mode Legacy (IA avec ResponseGeneratorAgent)
    python test_doc_workflow_with_examt3p.py 198709000447309732 --legacy

    # Mode dry run (analyse sans modification)
    python test_doc_workflow_with_examt3p.py 198709000447309732 --dry-run

    # Bulk analysis - tous les tickets DOC ouverts
    python test_doc_workflow_with_examt3p.py --bulk --dry-run --output results.json
"""
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Ajouter le projet au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_doc_workflow(ticket_id: str, use_state_engine: bool = True,
                       auto_create_draft: bool = True, auto_update_crm: bool = True,
                       quiet: bool = False):
    """Test le workflow DOC complet avec validation ExamT3P.

    Args:
        ticket_id: ID du ticket à traiter
        use_state_engine: Ignoré (toujours State Engine maintenant)
        auto_create_draft: Créer le draft dans Zoho Desk
        auto_update_crm: Mettre à jour le CRM
        quiet: Mode silencieux (moins de logs)

    Returns:
        dict: Résultat du workflow
    """
    if not quiet:
        print("\n" + "=" * 80)
        print("TEST WORKFLOW DOC COMPLET (avec validation ExamT3P)")
        print("=" * 80)
        print(f"Ticket ID: {ticket_id}")
        print(f"Mode: STATE ENGINE (deterministe)")
        if not auto_create_draft or not auto_update_crm:
            print(f"DRY RUN: CRM update={auto_update_crm}, Draft={auto_create_draft}")
        print()

    from src.workflows.doc_ticket_workflow import DOCTicketWorkflow

    workflow = DOCTicketWorkflow()

    try:
        if not quiet:
            print("\n🚀 Lancement du workflow complet...\n")

        # Exécuter le workflow complet
        result = workflow.process_ticket(
            ticket_id=ticket_id,
            auto_create_draft=auto_create_draft,    # Créer le draft dans Zoho Desk
            auto_update_crm=auto_update_crm,        # Mettre à jour le CRM automatiquement
            auto_update_ticket=auto_update_crm      # Mettre à jour le ticket (routing, tags) si pas dry-run
        )

        # Afficher les résultats (seulement si pas quiet)
        if not quiet:
            print("\n" + "=" * 80)
            print("📊 RÉSULTATS DU WORKFLOW")
            print("=" * 80)

            print(f"\n✅ Success: {result['success']}")
            print(f"📍 Workflow Stage: {result['workflow_stage']}")

            # Triage
            print("\n" + "-" * 80)
            print("1️⃣  TRIAGE")
            print("-" * 80)
            triage = result.get('triage_result', {})
            print(f"   Action: {triage.get('action')}")
            print(f"   Raison: {triage.get('reason')}")
            if triage.get('target_department'):
                print(f"   Département cible: {triage.get('target_department')}")

            # Analyse (y compris ExamT3P)
            print("\n" + "-" * 80)
            print("2️⃣  ANALYSE (incluant ExamT3P)")
            print("-" * 80)
            analysis = result.get('analysis_result', {})

            print(f"\n   📊 CRM:")
            print(f"      Deal ID: {analysis.get('deal_id') or 'Non trouvé'}")
            if analysis.get('deal_data'):
                deal = analysis['deal_data']
                print(f"      Deal Name: {deal.get('Deal_Name')}")
                print(f"      Stage: {deal.get('Stage')}")

            print(f"\n   🌐 ExamT3P:")
            examt3p = analysis.get('exament3p_data', {})

            # Afficher les informations de validation des identifiants
            print(f"      Identifiants trouvés: {examt3p.get('identifiant') is not None}")
            if examt3p.get('identifiant'):
                print(f"      Identifiant: {examt3p.get('identifiant')}")
                print(f"      Source: {examt3p.get('credentials_source')}")
                print(f"      Connexion testée: {examt3p.get('connection_test_success')}")

            # ALERTE DOUBLON DE PAIEMENT
            if examt3p.get('duplicate_payment_alert'):
                print(f"\n      🚨🚨🚨 ALERTE CRITIQUE: DOUBLE PAIEMENT DÉTECTÉ! 🚨🚨🚨")
                dup_accounts = examt3p.get('duplicate_accounts', {})
                print(f"      Compte CRM: {dup_accounts.get('crm', {}).get('identifiant')}")
                print(f"      Compte Candidat: {dup_accounts.get('thread', {}).get('identifiant')}")
                print(f"      → INTERVENTION MANUELLE REQUISE!")

            # Info si basculement vers compte payé
            if examt3p.get('switched_to_paid_account'):
                print(f"\n      🔄 BASCULEMENT: Utilisation du compte candidat (déjà payé)")

            # NOUVEAU: Afficher le comportement selon nos règles
            if examt3p.get('should_respond_to_candidate'):
                print(f"\n      ⚠️  DEMANDE DE RÉINITIALISATION AU CANDIDAT")
                print(f"      Message:")
                if examt3p.get('candidate_response_message'):
                    msg = examt3p['candidate_response_message']
                    # Afficher les 3 premières lignes
                    lines = msg.split('\n')[:3]
                    for line in lines:
                        print(f"         {line}")
                    print(f"         ... (voir message complet dans les résultats)")
            elif not examt3p.get('identifiant'):
                print(f"\n      ✅ IDENTIFIANTS ABSENTS - Pas de demande au candidat")
                print(f"         → Création de compte nécessaire (par nous)")
            else:
                print(f"\n      ✅ IDENTIFIANTS VALIDÉS")
                print(f"      Compte existe: {examt3p.get('compte_existe', False)}")
                if examt3p.get('compte_existe'):
                    print(f"      Documents: {len(examt3p.get('documents', []))}")
                    print(f"      Paiement CMA: {examt3p.get('paiement_cma_status')}")

            # Date Examen VTC
            print(f"\n   📅 Date Examen VTC:")
            date_vtc = analysis.get('date_examen_vtc_result', {})
            if date_vtc:
                case_num = date_vtc.get('case', 0)
                case_desc = date_vtc.get('case_description', 'N/A')
                evalbox = date_vtc.get('evalbox_status', 'N/A')
                should_include = date_vtc.get('should_include_in_response', False)

                print(f"      CAS détecté: {case_num}")
                print(f"      Description: {case_desc}")
                print(f"      Statut Evalbox: {evalbox}")
                print(f"      Inclure dans réponse: {'Oui' if should_include else 'Non'}")

                if should_include:
                    print(f"\n      ⚠️  ACTION REQUISE - Message à intégrer:")
                    if date_vtc.get('response_message'):
                        msg = date_vtc['response_message']
                        lines = msg.split('\n')[:5]
                        for line in lines:
                            print(f"         {line}")
                        if len(msg.split('\n')) > 5:
                            print(f"         ... (message tronqué)")

                if date_vtc.get('next_dates'):
                    print(f"\n      📆 Prochaines dates proposées:")
                    for i, date_info in enumerate(date_vtc['next_dates'][:2], 1):
                        date_examen = date_info.get('Date_Examen', 'N/A')
                        libelle = date_info.get('Libelle_Affichage', '')
                        print(f"         {i}. {date_examen} - {libelle}")

                if date_vtc.get('pieces_refusees'):
                    print(f"\n      ❌ Pièces refusées (CAS 3):")
                    for piece in date_vtc['pieces_refusees']:
                        print(f"         - {piece}")
            else:
                print(f"      Pas d'analyse date examen VTC")

            # Génération de réponse
            print("\n" + "-" * 80)
            print("3️⃣  GÉNÉRATION DE RÉPONSE")
            print("-" * 80)
            response = result.get('response_result', {})
            if response:
                # State Engine metadata
                state_engine_info = response.get('state_engine', {})
                if state_engine_info:
                    print(f"   🎯 STATE ENGINE:")
                    print(f"      État détecté: {state_engine_info.get('state_id')} - {state_engine_info.get('state_name')}")
                    print(f"      Priorité: {state_engine_info.get('priority')}")
                    ctx = state_engine_info.get('context', {})
                    if ctx.get('evalbox'):
                        print(f"      Evalbox: {ctx.get('evalbox')}")
                    if ctx.get('uber_case'):
                        print(f"      Cas Uber: {ctx.get('uber_case')}")
                    if ctx.get('date_case'):
                        print(f"      Cas Date: {ctx.get('date_case')}")
                    if ctx.get('detected_intent'):
                        print(f"      Intention: {ctx.get('detected_intent')}")
                    if state_engine_info.get('crm_updates_blocked'):
                        print(f"      🔒 Mises à jour bloquées: {list(state_engine_info['crm_updates_blocked'].keys())}")
                else:
                    print(f"   🤖 LEGACY MODE (ResponseGeneratorAgent)")

                print(f"\n   Scénarios détectés: {', '.join(response.get('detected_scenarios', []))}")
                print(f"   Mise à jour CRM requise: {response.get('requires_crm_update', False)}")
                if response.get('crm_updates'):
                    print(f"   Mises à jour CRM: {response.get('crm_updates')}")

                # Validation info
                validation = response.get('validation', {})
                if validation:
                    for scenario_id, val_info in validation.items():
                        if not val_info.get('compliant', True):
                            print(f"\n   ⚠️ VALIDATION ÉCHOUÉE pour {scenario_id}:")
                            for error in val_info.get('errors', []):
                                print(f"      - {error}")
                        if val_info.get('forbidden_terms_found'):
                            print(f"   🚫 Termes interdits trouvés: {val_info['forbidden_terms_found']}")

                if response.get('response_text'):
                    print(f"\n   📧 RÉPONSE COMPLÈTE:")
                    print("   " + "=" * 76)
                    # Afficher la réponse complète avec indentation
                    for line in response['response_text'].split('\n'):
                        print(f"   {line}")
                    print("   " + "=" * 76)
            else:
                print("   Pas de réponse générée (workflow arrêté avant)")

            # CRM Note
            print("\n" + "-" * 80)
            print("4️⃣  CRM NOTE")
            print("-" * 80)
            if result.get('crm_note'):
                note_lines = result['crm_note'].split('\n')[:5]
                for line in note_lines:
                    print(f"   {line}")
                print("   ...")
            else:
                print("   Pas de note CRM (workflow arrêté avant)")

            # Erreurs
            if result.get('errors'):
                print("\n" + "-" * 80)
                print("⚠️  ERREURS / AVERTISSEMENTS")
                print("-" * 80)
                for error in result['errors']:
                    print(f"   - {error}")

            # Résumé final
            print("\n" + "=" * 80)
            print("📋 RÉSUMÉ")
            print("=" * 80)
            print(f"   Workflow complété: {result['success']}")
            print(f"   Arrêté à l'étape: {result['workflow_stage']}")
            print(f"   Draft créé: {result['draft_created']}")
            print(f"   CRM mis à jour: {result['crm_updated']}")
            print(f"   Ticket mis à jour: {result['ticket_updated']}")

            # Information importante sur ExamT3P
            if result.get('analysis_result', {}).get('exament3p_data'):
                examt3p_summary = result['analysis_result']['exament3p_data']
                print(f"\n   🌐 ExamT3P:")
                if examt3p_summary.get('duplicate_payment_alert'):
                    print(f"      → 🚨 ALERTE: DOUBLE PAIEMENT DÉTECTÉ!")
                elif examt3p_summary.get('switched_to_paid_account'):
                    print(f"      → 🔄 Basculé vers compte candidat (déjà payé)")
                elif examt3p_summary.get('should_respond_to_candidate'):
                    print(f"      → Demande réinitialisation au candidat")
                elif not examt3p_summary.get('identifiant'):
                    print(f"      → Identifiants absents (création de compte)")
                else:
                    print(f"      → Identifiants validés et données extraites")

            # Information importante sur Date Examen VTC
            if result.get('analysis_result', {}).get('date_examen_vtc_result'):
                date_vtc_summary = result['analysis_result']['date_examen_vtc_result']
                print(f"\n   📅 Date Examen VTC:")
                print(f"      → CAS {date_vtc_summary.get('case', 'N/A')}: {date_vtc_summary.get('case_description', '')}")
                if date_vtc_summary.get('should_include_in_response'):
                    print(f"      → ⚠️ Message à intégrer dans la réponse")
                else:
                    print(f"      → ✅ Pas d'action spéciale requise")

            print("\n" + "=" * 80)

        return result

    except Exception as e:
        logger.error(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        try:
            workflow.close()
        except Exception as e:
            logger.warning(f"Error closing workflow: {e}")


def get_open_doc_tickets():
    """Récupère tous les tickets ouverts du département DOC."""
    from src.zoho_client import ZohoDeskClient

    client = ZohoDeskClient()
    try:
        # Get DOC department ID
        DOC_DEPARTMENT_ID = "198709000025523146"

        # List all open tickets (includes all departments)
        all_tickets = client.list_all_tickets(status="Open")

        # Filter to DOC department only
        tickets = [t for t in all_tickets if t.get("departmentId") == DOC_DEPARTMENT_ID]

        print(f"📋 Trouvé {len(tickets)} tickets ouverts dans DOC (sur {len(all_tickets)} tickets ouverts total)")
        return tickets
    finally:
        client.close()


def run_bulk_analysis(use_state_engine: bool = True,
                      auto_create_draft: bool = False,
                      auto_update_crm: bool = False,
                      output_file: str = None):
    """Execute le workflow sur tous les tickets DOC ouverts.

    Args:
        use_state_engine: Utiliser le State Engine
        auto_create_draft: Créer les drafts
        auto_update_crm: Mettre à jour le CRM
        output_file: Fichier JSON pour sauvegarder les résultats
    """
    tickets = get_open_doc_tickets()

    if not tickets:
        print("❌ Aucun ticket ouvert trouvé")
        return

    results = []
    stats = {
        "total": len(tickets),
        "success": 0,
        "no_deal": 0,
        "routed": 0,
        "errors": 0,
        "by_state": {},
        "by_intention": {}
    }

    print("\n" + "=" * 80)
    print(f"🔄 ANALYSE EN MASSE - {len(tickets)} tickets")
    print(f"   Mode: {'DRY RUN' if not auto_update_crm and not auto_create_draft else 'PRODUCTION'}")
    print("=" * 80)

    for i, ticket in enumerate(tickets, 1):
        ticket_id = ticket.get("id")
        subject = ticket.get("subject", "N/A")[:50]
        contact_email = ticket.get("contact", {}).get("email", "N/A")

        print(f"\n[{i}/{len(tickets)}] 📧 {ticket_id}")
        print(f"   Subject: {subject}...")
        print(f"   Email: {contact_email}")

        try:
            result = test_doc_workflow(
                ticket_id=ticket_id,
                use_state_engine=use_state_engine,
                auto_create_draft=auto_create_draft,
                auto_update_crm=auto_update_crm,
                quiet=True  # Mode silencieux pour bulk
            )

            if result:
                # Analyser le résultat
                ticket_result = {
                    "ticket_id": ticket_id,
                    "subject": ticket.get("subject"),
                    "contact_email": contact_email,
                    "success": result.get("success", False),
                    "workflow_stage": result.get("workflow_stage"),
                    "triage_action": result.get("triage_result", {}).get("action"),
                    "deal_found": bool(result.get("analysis_result", {}).get("deal_id")),
                    "deal_id": result.get("analysis_result", {}).get("deal_id"),
                    "state_detected": result.get("response_result", {}).get("state_engine", {}).get("state_id"),
                    "state_name": result.get("response_result", {}).get("state_engine", {}).get("state_name"),
                    "detected_intent": result.get("response_result", {}).get("state_engine", {}).get("context", {}).get("detected_intent"),
                    "response_preview": (result.get("response_result", {}).get("response_text") or "")[:200]
                }

                # Vérifier si deal trouvé
                if not ticket_result["deal_found"]:
                    stats["no_deal"] += 1
                    ticket_result["ecart"] = "NO_DEAL"
                    print(f"   ⚠️ Pas de deal CRM trouvé")
                elif result.get("triage_result", {}).get("action") == "ROUTE":
                    stats["routed"] += 1
                    ticket_result["ecart"] = "ROUTED"
                    print(f"   ➡️ Routé vers: {result.get('triage_result', {}).get('target_department')}")
                elif result.get("success"):
                    stats["success"] += 1
                    print(f"   ✅ État: {ticket_result['state_detected']} - {ticket_result['state_name']}")
                    # Track by state
                    state = ticket_result['state_detected'] or "unknown"
                    stats["by_state"][state] = stats["by_state"].get(state, 0) + 1
                    # Track by intention
                    intent = ticket_result['detected_intent'] or "unknown"
                    stats["by_intention"][intent] = stats["by_intention"].get(intent, 0) + 1
                else:
                    stats["errors"] += 1
                    ticket_result["ecart"] = "ERROR"
                    print(f"   ❌ Erreur workflow")

                results.append(ticket_result)
            else:
                stats["errors"] += 1
                results.append({
                    "ticket_id": ticket_id,
                    "success": False,
                    "ecart": "WORKFLOW_FAILED"
                })
                print(f"   ❌ Workflow échoué")

        except Exception as e:
            stats["errors"] += 1
            results.append({
                "ticket_id": ticket_id,
                "success": False,
                "error": str(e)
            })
            print(f"   ❌ Exception: {e}")

    # Résumé
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DE L'ANALYSE")
    print("=" * 80)
    print(f"   Total tickets: {stats['total']}")
    print(f"   ✅ Succès: {stats['success']}")
    print(f"   ⚠️ Pas de deal: {stats['no_deal']}")
    print(f"   ➡️ Routés: {stats['routed']}")
    print(f"   ❌ Erreurs: {stats['errors']}")

    if stats["by_state"]:
        print(f"\n   Par état détecté:")
        for state, count in sorted(stats["by_state"].items(), key=lambda x: -x[1]):
            print(f"      {state}: {count}")

    if stats["by_intention"]:
        print(f"\n   Par intention:")
        for intent, count in sorted(stats["by_intention"].items(), key=lambda x: -x[1]):
            print(f"      {intent}: {count}")

    # Sauvegarder les résultats si output_file spécifié
    if output_file:
        output_data = {
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "stats": stats,
            "results": results
        }
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Résultats sauvegardés dans: {output_file}")

    return stats, results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Test du workflow DOC avec ExamT3P",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
    # Test un ticket spécifique
    python test_doc_workflow_with_examt3p.py 198709000447309732

    # Test en mode dry run (pas de modification)
    python test_doc_workflow_with_examt3p.py 198709000447309732 --dry-run

    # Analyse en masse de tous les tickets DOC ouverts
    python test_doc_workflow_with_examt3p.py --bulk --dry-run

    # Analyse en masse avec sauvegarde JSON
    python test_doc_workflow_with_examt3p.py --bulk --dry-run --output results.json
        """
    )

    parser.add_argument("ticket_id", nargs="?", help="ID du ticket à tester")
    parser.add_argument("--legacy", action="store_true",
                        help="Utiliser le mode Legacy (IA)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Ne pas modifier le CRM ni créer de draft")
    parser.add_argument("--no-crm-update", action="store_true",
                        help="Ne pas mettre à jour le CRM")
    parser.add_argument("--no-draft", action="store_true",
                        help="Ne pas créer de draft")
    parser.add_argument("--bulk", action="store_true",
                        help="Traiter tous les tickets DOC ouverts")
    parser.add_argument("--output", "-o", type=str,
                        help="Fichier JSON pour les résultats (mode bulk)")

    args = parser.parse_args()

    # Déterminer les options
    use_state_engine = not args.legacy
    auto_create_draft = not (args.dry_run or args.no_draft)
    auto_update_crm = not (args.dry_run or args.no_crm_update)

    if args.bulk:
        # Mode bulk
        print("🔄 Mode BULK - Analyse de tous les tickets DOC ouverts")
        if args.dry_run:
            print("⚠️  DRY RUN activé - Aucune modification ne sera effectuée")

        stats, results = run_bulk_analysis(
            use_state_engine=use_state_engine,
            auto_create_draft=auto_create_draft,
            auto_update_crm=auto_update_crm,
            output_file=args.output
        )

        if stats["success"] > 0 or stats["no_deal"] > 0:
            print("\n✅ Analyse bulk terminée")
            sys.exit(0)
        else:
            print("\n❌ Analyse bulk échouée")
            sys.exit(1)

    elif args.ticket_id:
        # Mode single ticket
        if args.legacy:
            print("⚠️  Mode LEGACY activé (ResponseGeneratorAgent avec IA)")

        result = test_doc_workflow(
            args.ticket_id,
            use_state_engine=use_state_engine,
            auto_create_draft=auto_create_draft,
            auto_update_crm=auto_update_crm
        )

        if result:
            print("\n✅ Test terminé avec succès")
            sys.exit(0)
        else:
            print("\n❌ Test échoué")
            sys.exit(1)

    else:
        parser.print_help()
        print("\n❌ Erreur: Ticket ID manquant ou --bulk requis")
        print("\n💡 Pour obtenir un ticket ID valide:")
        print("   python list_recent_tickets.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
