"""
Script de test pour le workflow DOC complet avec validation ExamT3P et Date Examen VTC.

Ce script teste le workflow complet incluant :
1. AGENT TRIEUR
2. AGENT ANALYSTE (incluant validation ExamT3P + Date Examen VTC)
3. AGENT RÉDACTEUR
4. CRM Note
5. Ticket Update
6. Deal Update
7. Draft Creation
8. Final Validation

Usage:
    python test_doc_workflow_with_examt3p.py <ticket_id>

Exemple:
    python test_doc_workflow_with_examt3p.py 198709000447309732
"""
import sys
import logging
from pathlib import Path
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


def test_doc_workflow(ticket_id: str):
    """Test le workflow DOC complet avec validation ExamT3P."""
    print("\n" + "=" * 80)
    print("🧪 TEST WORKFLOW DOC COMPLET (avec validation ExamT3P)")
    print("=" * 80)
    print(f"Ticket ID: {ticket_id}")
    print()

    from src.workflows.doc_ticket_workflow import DOCTicketWorkflow

    workflow = DOCTicketWorkflow()

    try:
        print("\n🚀 Lancement du workflow complet...\n")

        # Exécuter le workflow complet
        result = workflow.process_ticket(
            ticket_id=ticket_id,
            auto_create_draft=True,    # Créer le draft dans Zoho Desk
            auto_update_crm=True,      # Mettre à jour le CRM automatiquement
            auto_update_ticket=False   # Ne pas mettre à jour le ticket automatiquement
        )

        # Afficher les résultats
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
            print(f"   Scénarios détectés: {', '.join(response.get('detected_scenarios', []))}")
            print(f"   Mise à jour CRM requise: {response.get('requires_crm_update', False)}")
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
        if analysis.get('exament3p_data'):
            examt3p = analysis['exament3p_data']
            print(f"\n   🌐 ExamT3P:")
            if examt3p.get('should_respond_to_candidate'):
                print(f"      → Demande réinitialisation au candidat")
            elif not examt3p.get('identifiant'):
                print(f"      → Identifiants absents (création de compte)")
            else:
                print(f"      → Identifiants validés et données extraites")

        # Information importante sur Date Examen VTC
        if analysis.get('date_examen_vtc_result'):
            date_vtc = analysis['date_examen_vtc_result']
            print(f"\n   📅 Date Examen VTC:")
            print(f"      → CAS {date_vtc.get('case', 'N/A')}: {date_vtc.get('case_description', '')}")
            if date_vtc.get('should_include_in_response'):
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


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ Erreur: Ticket ID manquant")
        print("\n💡 Pour obtenir un ticket ID valide:")
        print("   python list_recent_tickets.py")
        sys.exit(1)

    ticket_id = sys.argv[1]

    result = test_doc_workflow(ticket_id)

    if result:
        print("\n✅ Test terminé avec succès")
        sys.exit(0)
    else:
        print("\n❌ Test échoué")
        sys.exit(1)


if __name__ == "__main__":
    main()
