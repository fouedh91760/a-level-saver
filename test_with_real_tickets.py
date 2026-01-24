"""
Script de test pour tester le système avec de vrais tickets Zoho.

Ce script permet de tester progressivement chaque étape du workflow.
"""
import logging
import sys
from dotenv import load_dotenv
from src.agents import TicketDispatcherAgent, DealLinkingAgent, DeskTicketAgent
from src.orchestrator import ZohoAutomationOrchestrator
from src.zoho_client import ZohoDeskClient

# Charger les variables d'environnement
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_connection():
    """Test 0 : Vérifier la connexion Zoho."""
    print("\n" + "=" * 80)
    print("TEST 0 : VÉRIFICATION DE LA CONNEXION ZOHO")
    print("=" * 80)

    try:
        desk_client = ZohoDeskClient()

        # Essayer de lister quelques tickets
        print("\n📡 Test de connexion à Zoho Desk...")
        tickets = desk_client.list_tickets(limit=5)

        if tickets.get("data"):
            print(f"✅ Connexion réussie!")
            print(f"   Nombre de tickets récupérés : {len(tickets['data'])}")
            print("\n   Premiers tickets trouvés :")
            for ticket in tickets["data"][:3]:
                print(f"     - ID: {ticket.get('id')} | Sujet: {ticket.get('subject')[:50]}...")
            return True
        else:
            print("❌ Aucun ticket trouvé. Vérifiez votre configuration.")
            return False

    except Exception as e:
        print(f"❌ Erreur de connexion : {e}")
        print("\n💡 Vérifiez votre fichier .env :")
        print("   - ZOHO_CLIENT_ID")
        print("   - ZOHO_CLIENT_SECRET")
        print("   - ZOHO_REFRESH_TOKEN")
        print("   - ZOHO_DESK_ORG_ID")
        print("   - ANTHROPIC_API_KEY")
        return False
    finally:
        desk_client.close()


def test_1_dispatcher_single_ticket(ticket_id: str):
    """Test 1 : Tester le dispatcher sur un ticket unique."""
    print("\n" + "=" * 80)
    print("TEST 1 : DISPATCHER - VALIDATION DU DÉPARTEMENT")
    print("=" * 80)

    dispatcher = TicketDispatcherAgent()

    try:
        print(f"\n🎯 Analyse du ticket {ticket_id}...")

        # Mode READ-ONLY - pas de réaffectation
        result = dispatcher.process({
            "ticket_id": ticket_id,
            "auto_reassign": False  # Juste analyser, ne pas réaffecter
        })

        print("\n📊 Résultat de l'analyse :")
        print(f"   Département actuel : {result['current_department']}")
        print(f"   Département recommandé : {result['recommended_department']}")
        print(f"   Méthode : {result['method']}")
        print(f"   Confiance : {result['confidence']}%")

        if result['should_reassign']:
            print(f"\n⚠️  RECOMMANDATION : Réaffecter vers {result['recommended_department']}")
            print(f"   Raison : {result['reasoning']}")
            print(f"   Signaux détectés : {', '.join(result.get('signals', []))}")
        else:
            print(f"\n✅ Département correct - Pas de réaffectation nécessaire")

        return result

    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None
    finally:
        dispatcher.close()


def test_2_dispatcher_batch():
    """Test 2 : Analyser plusieurs tickets en batch."""
    print("\n" + "=" * 80)
    print("TEST 2 : DISPATCHER - ANALYSE BATCH")
    print("=" * 80)

    dispatcher = TicketDispatcherAgent()

    try:
        print("\n📊 Analyse des tickets ouverts (limit 20)...")

        result = dispatcher.batch_validate_departments(
            status="Open",
            limit=20
        )

        print(f"\n📈 Résumé :")
        print(f"   Total analysé : {result['total_checked']}")
        print(f"   Département correct : {result['correct_department']}")
        print(f"   À réaffecter : {result['should_reassign']}")

        if result['should_reassign'] > 0:
            print(f"\n⚠️  Tickets à réaffecter :")
            for ticket_result in result['results']:
                if ticket_result.get('should_reassign'):
                    print(f"\n   📌 Ticket {ticket_result['ticket_id']}")
                    print(f"      De : {ticket_result['current_department']}")
                    print(f"      Vers : {ticket_result['recommended_department']}")
                    print(f"      Confiance : {ticket_result['confidence']}%")
                    print(f"      Raison : {ticket_result['reasoning']}")
        else:
            print(f"\n✅ Tous les tickets sont dans le bon département")

        return result

    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None
    finally:
        dispatcher.close()


def test_3_deal_linking(ticket_id: str):
    """Test 3 : Tester le linking ticket-deal."""
    print("\n" + "=" * 80)
    print("TEST 3 : DEAL LINKING - RECHERCHE DU DEAL")
    print("=" * 80)

    linking_agent = DealLinkingAgent()

    try:
        print(f"\n🔗 Recherche de deal pour le ticket {ticket_id}...")

        # Mode READ-ONLY - pas de modification
        result = linking_agent.process({
            "ticket_id": ticket_id
        })

        if result.get('deal_found'):
            print(f"\n✅ Deal trouvé !")
            print(f"   Deal ID : {result['deal_id']}")
            print(f"   Deal Name : {result['deal_name']}")
            print(f"   Stratégie utilisée : {result['strategy_used']}")
            print(f"   Lien créé : {result.get('link_created', False)}")
        else:
            print(f"\n❌ Aucun deal trouvé")
            print(f"   Raison : {result.get('reason', 'N/A')}")

        return result

    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None
    finally:
        linking_agent.close()


def test_4_complete_workflow(ticket_id: str, auto_dispatch: bool = False):
    """Test 4 : Workflow complet (READ-ONLY)."""
    print("\n" + "=" * 80)
    print("TEST 4 : WORKFLOW COMPLET")
    print("=" * 80)

    orchestrator = ZohoAutomationOrchestrator()

    try:
        print(f"\n🚀 Exécution du workflow complet pour ticket {ticket_id}...")
        print(f"   Mode : {'AUTO-DISPATCH' if auto_dispatch else 'READ-ONLY'}")

        result = orchestrator.process_ticket_complete_workflow(
            ticket_id=ticket_id,
            auto_dispatch=auto_dispatch,  # Configurable
            auto_link=False,        # READ-ONLY - ne pas créer de lien
            auto_respond=False,     # READ-ONLY - ne pas répondre
            auto_update_ticket=False,
            auto_update_deal=False,
            auto_add_note=False
        )

        print("\n" + "=" * 80)
        print("RÉSULTATS DU WORKFLOW")
        print("=" * 80)

        # Étape 1 : Dispatch
        dispatch = result.get('dispatch_result', {})
        print(f"\n1️⃣ DISPATCH :")
        print(f"   Département actuel : {dispatch.get('current_department')}")
        print(f"   Département recommandé : {dispatch.get('recommended_department')}")
        if dispatch.get('reassigned'):
            print(f"   ✅ Réaffecté automatiquement")
        elif dispatch.get('should_reassign'):
            print(f"   ⚠️  Devrait être réaffecté (auto_dispatch=False)")
        else:
            print(f"   ✅ Département correct")

        # Étape 2 : Linking
        linking = result.get('linking_result', {})
        print(f"\n2️⃣ DEAL LINKING :")
        if linking.get('deal_found'):
            print(f"   ✅ Deal trouvé : {linking.get('deal_id')}")
            print(f"   Nom : {linking.get('deal_name')}")
            print(f"   Stratégie : {linking.get('strategy_used')}")
        else:
            print(f"   ❌ Aucun deal trouvé")

        # Étape 3 : Ticket processing
        ticket_result = result.get('ticket_result', {})
        print(f"\n3️⃣ TICKET PROCESSING :")
        if ticket_result:
            analysis = ticket_result.get('agent_analysis', {})
            print(f"   Sentiment : {analysis.get('sentiment', 'N/A')}")
            print(f"   Urgence : {analysis.get('urgency', 'N/A')}")
            print(f"   Escalation nécessaire : {analysis.get('should_escalate', False)}")
            print(f"   Réponse suggérée : {ticket_result.get('suggested_response', 'N/A')[:100]}...")
        else:
            print(f"   ⚠️  Pas de résultat")

        # Étape 4 : CRM update
        crm = result.get('crm_result', {})
        print(f"\n4️⃣ CRM UPDATE :")
        if crm.get('skipped'):
            print(f"   ⏭️  Ignoré (raison : {crm.get('reason')})")
        elif crm:
            print(f"   ✅ Analyse CRM effectuée")
        else:
            print(f"   ⚠️  Pas de résultat")

        print("\n" + "=" * 80)
        return result

    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        orchestrator.close()


def main():
    """Menu principal pour les tests."""
    print("\n" + "=" * 80)
    print("🧪 SCRIPT DE TEST - SYSTÈME D'AUTOMATISATION ZOHO")
    print("=" * 80)

    # Test de connexion
    if not test_connection():
        print("\n❌ Échec de la connexion. Arrêt du script.")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("CHOISISSEZ UN TEST")
    print("=" * 80)
    print("\n1. Test dispatcher sur un ticket unique")
    print("2. Test dispatcher en batch (20 tickets)")
    print("3. Test deal linking sur un ticket unique")
    print("4. Test workflow complet (READ-ONLY)")
    print("5. Test workflow complet (AUTO-DISPATCH)")
    print("6. Tout tester avec un ticket ID")
    print("\n0. Quitter")

    choice = input("\nVotre choix : ").strip()

    if choice == "0":
        print("\n👋 Au revoir!")
        return

    # Pour les tests nécessitant un ticket_id
    if choice in ["1", "3", "4", "5", "6"]:
        ticket_id = input("\nEntrez l'ID du ticket à tester : ").strip()

        if not ticket_id:
            print("❌ ID de ticket requis")
            return

    # Exécuter le test choisi
    if choice == "1":
        test_1_dispatcher_single_ticket(ticket_id)

    elif choice == "2":
        test_2_dispatcher_batch()

    elif choice == "3":
        test_3_deal_linking(ticket_id)

    elif choice == "4":
        test_4_complete_workflow(ticket_id, auto_dispatch=False)

    elif choice == "5":
        confirm = input("\n⚠️  ATTENTION : Auto-dispatch modifiera le département si nécessaire. Continuer ? (oui/non) : ")
        if confirm.lower() in ["oui", "yes", "y"]:
            test_4_complete_workflow(ticket_id, auto_dispatch=True)
        else:
            print("❌ Test annulé")

    elif choice == "6":
        print("\n🔄 Exécution de tous les tests...")
        test_1_dispatcher_single_ticket(ticket_id)
        test_3_deal_linking(ticket_id)
        test_4_complete_workflow(ticket_id, auto_dispatch=False)

    else:
        print("❌ Choix invalide")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interruption par l'utilisateur")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur inattendue : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
