"""
Test de génération de draft pour un ticket Zoho Desk.

Ce script permet de tester la génération complète d'un draft de réponse :
1. Récupération des données du ticket
2. Extraction des données CRM/ExamenT3P
3. Détection du scénario
4. Génération de la réponse avec Claude
5. Validation de la réponse

Usage:
    python test_draft_generation.py <ticket_id>

Exemple:
    python test_draft_generation.py 198709000445353417
"""
import logging
import sys
import json
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.agents.deal_linking_agent import DealLinkingAgent
from src.agents.response_generator_agent import ResponseGeneratorAgent


def extract_customer_message(threads):
    """Extraire le dernier message du client."""
    customer_messages = []
    for thread in threads.get('data', []):
        if thread.get('direction') == 'in':
            customer_messages.append({
                'content': thread.get('content', ''),
                'created_time': thread.get('createdTime', '')
            })

    if customer_messages:
        # Trier par date et prendre le dernier
        customer_messages.sort(key=lambda x: x['created_time'], reverse=True)
        return customer_messages[0]['content']

    return ""


def test_draft_generation(ticket_id: str):
    """Tester la génération de draft pour un ticket."""

    print("\n" + "=" * 80)
    print("🧪 TEST DE GÉNÉRATION DE DRAFT")
    print("=" * 80)
    print(f"Ticket ID: {ticket_id}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    desk_client = ZohoDeskClient()
    crm_client = ZohoCRMClient()
    deal_linker = DealLinkingAgent()
    response_generator = ResponseGeneratorAgent()

    try:
        # ================================================================
        # ÉTAPE 1: Récupération des données du ticket
        # ================================================================
        print("\n1️⃣  Récupération des données du ticket...")

        ticket = desk_client.get_ticket(ticket_id)
        threads = desk_client.get_ticket_threads(ticket_id)

        subject = ticket.get('subject', '')
        email = ticket.get('email', '')
        customer_message = extract_customer_message(threads)

        print(f"   ✅ Sujet: {subject}")
        print(f"   ✅ Email: {email}")
        print(f"   ✅ Message client: {customer_message[:100]}...")

        # ================================================================
        # ÉTAPE 2: Recherche du deal CRM
        # ================================================================
        print("\n2️⃣  Recherche du deal CRM...")

        deal_id = deal_linker.find_deal_for_ticket(ticket_id, email)

        deal_data = None
        if deal_id:
            print(f"   ✅ Deal trouvé: {deal_id}")
            deal = crm_client.get_deal(deal_id)
            deal_data = deal

            print(f"   📋 Deal: {deal.get('Deal_Name')}")
            print(f"   💰 Montant: {deal.get('Amount')}€")
            print(f"   📊 Stage: {deal.get('Stage')}")
            print(f"   📝 Evalbox: {deal.get('Evalbox', 'N/A')}")
        else:
            print("   ⚠️  Aucun deal trouvé")

        # ================================================================
        # ÉTAPE 3: Données ExamenT3P (simulées pour ce test)
        # ================================================================
        print("\n3️⃣  Données ExamenT3P...")
        print("   ℹ️  Données simulées (ExamT3PAgent pas encore intégré)")

        exament3p_data = {
            'compte_existe': False,  # Simulé
            'identifiant': None,
            'mot_de_passe': None,
            'documents': [],
            'documents_manquants': [],
            'paiement_cma_status': 'N/A'
        }

        # ================================================================
        # ÉTAPE 4: Données Evalbox (simulées)
        # ================================================================
        print("\n4️⃣  Données Evalbox...")
        print("   ℹ️  Données simulées (Google Sheet pas encore intégré)")

        evalbox_data = {
            'eligible_uber': None,
            'scope': None
        }

        # ================================================================
        # ÉTAPE 5: Génération de la réponse avec Claude
        # ================================================================
        print("\n5️⃣  Génération de la réponse avec Claude...")
        print("   🤖 Appel à Claude API (claude-3-5-sonnet)...")

        result = response_generator.generate_with_validation_loop(
            ticket_subject=subject,
            customer_message=customer_message,
            crm_data=deal_data,
            exament3p_data=exament3p_data,
            evalbox_data=evalbox_data,
            max_retries=2
        )

        print(f"   ✅ Réponse générée ({len(result['response_text'])} caractères)")

        # ================================================================
        # RÉSULTATS
        # ================================================================
        print("\n" + "=" * 80)
        print("📊 RÉSULTATS DE LA GÉNÉRATION")
        print("=" * 80)

        print(f"\n🎯 SCÉNARIOS DÉTECTÉS:")
        for scenario in result['detected_scenarios']:
            print(f"   - {scenario}")

        print(f"\n🔍 TICKETS SIMILAIRES UTILISÉS:")
        for i, ticket in enumerate(result['similar_tickets'], 1):
            print(f"   {i}. [Score: {ticket['similarity_score']}] {ticket['subject']}")

        print(f"\n✅ VALIDATION:")
        all_compliant = True
        for scenario_id, validation in result['validation'].items():
            status = "✅" if validation['compliant'] else "❌"
            print(f"   {status} {scenario_id}")
            if not validation['compliant']:
                all_compliant = False
                if validation['missing_blocks']:
                    print(f"      ⚠️  Blocs manquants: {validation['missing_blocks']}")
                if validation['forbidden_terms_found']:
                    print(f"      ⚠️  Termes interdits: {validation['forbidden_terms_found']}")

        if all_compliant:
            print("\n   🎉 La réponse est CONFORME à tous les scénarios")
        else:
            print("\n   ⚠️  La réponse a des problèmes de conformité")

        print(f"\n📝 UPDATE CRM REQUIS: {result['requires_crm_update']}")
        if result['requires_crm_update']:
            print(f"   Champs à mettre à jour: {result['crm_update_fields']}")

        print(f"\n🛑 STOP WORKFLOW: {result['should_stop_workflow']}")

        print(f"\n📊 MÉTADONNÉES:")
        metadata = result['metadata']
        print(f"   - Modèle: {metadata['model']}")
        print(f"   - Temperature: {metadata['temperature']}")
        print(f"   - Tokens entrée: {metadata['input_tokens']:,}")
        print(f"   - Tokens sortie: {metadata['output_tokens']:,}")
        print(f"   - Coût estimé: ${(metadata['input_tokens'] * 0.003 / 1000 + metadata['output_tokens'] * 0.015 / 1000):.4f}")

        # ================================================================
        # AFFICHAGE DU DRAFT
        # ================================================================
        print("\n" + "=" * 80)
        print("📧 DRAFT DE RÉPONSE GÉNÉRÉ")
        print("=" * 80)
        print("\n" + result['response_text'])
        print("\n" + "=" * 80)

        # ================================================================
        # SAUVEGARDE DES RÉSULTATS
        # ================================================================
        output_file = f"draft_test_result_{ticket_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'ticket_id': ticket_id,
                'timestamp': datetime.now().isoformat(),
                'subject': subject,
                'customer_message': customer_message,
                'deal_id': deal_id,
                'detected_scenarios': result['detected_scenarios'],
                'similar_tickets': [
                    {'subject': t['subject'], 'score': t['similarity_score']}
                    for t in result['similar_tickets']
                ],
                'validation': result['validation'],
                'requires_crm_update': result['requires_crm_update'],
                'crm_update_fields': result['crm_update_fields'],
                'should_stop_workflow': result['should_stop_workflow'],
                'metadata': result['metadata'],
                'response_text': result['response_text']
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Résultats sauvegardés dans: {output_file}")

        # ================================================================
        # OPTION: Créer le draft dans Zoho Desk
        # ================================================================
        print("\n" + "=" * 80)
        print("📝 CRÉER LE DRAFT DANS ZOHO DESK ?")
        print("=" * 80)
        print("\nVoulez-vous créer ce draft dans Zoho Desk ?")
        print("  (o)ui - Créer le draft")
        print("  (n)on - Ne pas créer le draft")

        choice = input("\nVotre choix (o/n): ").strip().lower()

        if choice == 'o':
            print("\n🚀 Création du draft dans Zoho Desk...")
            try:
                desk_client.create_ticket_reply_draft(
                    ticket_id=ticket_id,
                    content=result['response_text']
                )
                print("✅ Draft créé avec succès dans Zoho Desk !")
            except Exception as e:
                print(f"❌ Erreur lors de la création du draft: {e}")
        else:
            print("\n✅ Draft non créé (test uniquement)")

        print("\n" + "=" * 80)
        print("✅ TEST TERMINÉ")
        print("=" * 80)

    except Exception as e:
        logger.error(f"❌ Erreur lors du test: {e}")
        import traceback
        traceback.print_exc()

    finally:
        desk_client.close()
        crm_client.close()
        deal_linker.close()


def main():
    """Point d'entrée principal."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ Erreur: Vous devez fournir un ticket ID")
        print("\nUsage: python test_draft_generation.py <ticket_id>")
        print("Exemple: python test_draft_generation.py 198709000445353417")
        sys.exit(1)

    ticket_id = sys.argv[1]
    test_draft_generation(ticket_id)


if __name__ == "__main__":
    main()
