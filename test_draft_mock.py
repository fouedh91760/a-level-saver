"""
Test de génération de draft avec données SIMULÉES (MOCK).

Ce script permet de tester la génération complète d'un draft sans connexion API :
1. Utilise des données de test depuis fouad_tickets_analysis.json
2. Génère la réponse avec Claude (nécessite ANTHROPIC_API_KEY)
3. Affiche le draft complet avec validation

Usage:
    python test_draft_mock.py <ticket_id>
    ou
    python test_draft_mock.py  (utilisera un ticket d'exemple)

Exemple:
    python test_draft_mock.py 198709000445353417
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
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

from src.agents.response_generator_agent import ResponseGeneratorAgent
from src.utils.text_utils import clean_html


def load_ticket_from_fouad_data(ticket_id: str = None):
    """Charger un ticket depuis fouad_tickets_analysis.json."""
    with open('fouad_tickets_analysis.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    tickets = data.get('tickets', [])

    if ticket_id:
        # Chercher le ticket spécifique
        for ticket in tickets:
            if ticket['ticket_id'] == ticket_id:
                return ticket
        raise ValueError(f"Ticket {ticket_id} non trouvé dans fouad_tickets_analysis.json")
    else:
        # Prendre le premier ticket avec un message client
        for ticket in tickets:
            if ticket.get('customer_questions'):
                return ticket
        raise ValueError("Aucun ticket avec message client trouvé")


def load_deal_mock_data(ticket_id: str = None):
    """Charger des données CRM mockées depuis test_results si disponibles."""
    # Essayer de trouver des test_results pour ce ticket
    try:
        with open(f'test_results_{ticket_id}.json', 'r', encoding='utf-8') as f:
            test_data = json.load(f)

        # Extraire le deal depuis linking_result
        linking = test_data.get('linking_result', {})
        selected_deal = linking.get('selected_deal')

        if selected_deal:
            return selected_deal
    except FileNotFoundError:
        pass

    # Sinon, retourner des données mockées génériques
    return {
        'id': '123456789',
        'Deal_Name': 'VTC Uber - Candidat Test',
        'Amount': 20,
        'Stage': 'GAGNÉ',
        'Evalbox': 'En attente documents',
        'Session_choisie': None,
        'Date_de_depot_CMA': None,
        'Date_de_cloture': None,
        'email': 'test@example.com'
    }


def test_draft_with_mock_data(ticket_id: str = None):
    """Tester la génération de draft avec données mockées."""

    print("\n" + "=" * 80)
    print("🧪 TEST DE GÉNÉRATION DE DRAFT (MODE SIMULÉ)")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # ================================================================
    # ÉTAPE 1: Chargement des données mockées
    # ================================================================
    print("\n1️⃣  Chargement des données mockées...")

    try:
        ticket_data = load_ticket_from_fouad_data(ticket_id)
        actual_ticket_id = ticket_data['ticket_id']
        print(f"   ✅ Ticket chargé: {actual_ticket_id}")
    except Exception as e:
        logger.error(f"Erreur lors du chargement du ticket: {e}")
        return

    subject = ticket_data.get('subject', '')
    print(f"   📋 Sujet: {subject}")

    # Extraire le premier message client
    customer_questions = ticket_data.get('customer_questions', [])
    if customer_questions:
        customer_message = clean_html(customer_questions[0].get('content', ''))
        print(f"   💬 Message client: {customer_message[:150]}...")
    else:
        customer_message = "Message client non disponible"
        print(f"   ⚠️  Aucun message client trouvé")

    # Charger les données CRM mockées
    deal_data = load_deal_mock_data(actual_ticket_id)
    print(f"\n   💼 Données CRM (mockées):")
    print(f"      - Deal: {deal_data.get('Deal_Name', 'N/A')}")
    print(f"      - Montant: {deal_data.get('Amount', 0)}€")
    print(f"      - Stage: {deal_data.get('Stage', 'N/A')}")
    print(f"      - Evalbox: {deal_data.get('Evalbox', 'N/A')}")

    # Données ExamenT3P mockées
    exament3p_data = {
        'compte_existe': False,
        'identifiant': None,
        'mot_de_passe': None,
        'documents': [],
        'documents_manquants': ['Carte d\'identité', 'Justificatif de domicile'],
        'paiement_cma_status': 'En attente'
    }
    print(f"\n   🌐 Données ExamenT3P (mockées):")
    print(f"      - Compte existe: {exament3p_data['compte_existe']}")
    print(f"      - Paiement CMA: {exament3p_data['paiement_cma_status']}")

    # Données Evalbox mockées
    evalbox_data = {
        'eligible_uber': True,
        'scope': 'uber_gagne'
    }
    print(f"\n   📊 Données Evalbox (mockées):")
    print(f"      - Éligible Uber: {evalbox_data['eligible_uber']}")

    # ================================================================
    # ÉTAPE 2: Initialisation de l'agent
    # ================================================================
    print("\n2️⃣  Initialisation du Response Generator Agent...")

    try:
        response_generator = ResponseGeneratorAgent()
        print("   ✅ Agent initialisé")
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation: {e}")
        return

    # ================================================================
    # ÉTAPE 3: Génération de la réponse avec Claude
    # ================================================================
    print("\n3️⃣  Génération de la réponse avec Claude...")
    print("   🤖 Appel à Claude API (claude-3-5-sonnet)...")
    print("   ⏳ Cela peut prendre 10-30 secondes...")

    try:
        result = response_generator.generate_with_validation_loop(
            ticket_subject=subject,
            customer_message=customer_message,
            crm_data=deal_data,
            exament3p_data=exament3p_data,
            evalbox_data=evalbox_data,
            max_retries=2
        )

        print(f"\n   ✅ Réponse générée ({len(result['response_text'])} caractères)")

    except Exception as e:
        logger.error(f"❌ Erreur lors de la génération: {e}")
        import traceback
        traceback.print_exc()
        return

    # ================================================================
    # ÉTAPE 4: Affichage des résultats
    # ================================================================
    print("\n" + "=" * 80)
    print("📊 RÉSULTATS DE LA GÉNÉRATION")
    print("=" * 80)

    print(f"\n🎯 SCÉNARIOS DÉTECTÉS ({len(result['detected_scenarios'])}):")
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

    if all_compliant and result['validation']:
        print("\n   🎉 La réponse est CONFORME à tous les scénarios")
    elif result['validation']:
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

    # Calcul du coût (prix Claude 3.5 Sonnet)
    input_cost = metadata['input_tokens'] * 0.003 / 1000
    output_cost = metadata['output_tokens'] * 0.015 / 1000
    total_cost = input_cost + output_cost
    print(f"   - Coût estimé: ${total_cost:.4f}")

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
    output_file = f"draft_mock_result_{actual_ticket_id}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'ticket_id': actual_ticket_id,
            'timestamp': datetime.now().isoformat(),
            'subject': subject,
            'customer_message': customer_message,
            'mock_data': {
                'deal_data': deal_data,
                'exament3p_data': exament3p_data,
                'evalbox_data': evalbox_data
            },
            'detected_scenarios': result['detected_scenarios'],
            'similar_tickets': [
                {
                    'ticket_number': t.get('ticket_number'),
                    'subject': t['subject'],
                    'score': t['similarity_score']
                }
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
    # STATISTIQUES FINALES
    # ================================================================
    print("\n" + "=" * 80)
    print("📈 STATISTIQUES DU TEST")
    print("=" * 80)
    print(f"✅ Ticket analysé: {actual_ticket_id}")
    print(f"✅ Scénarios détectés: {len(result['detected_scenarios'])}")
    print(f"✅ Tickets similaires: {len(result['similar_tickets'])}")
    print(f"✅ Longueur draft: {len(result['response_text'])} caractères")
    print(f"✅ Nombre de mots: {len(result['response_text'].split())}")
    print(f"✅ Conforme: {'Oui' if all_compliant and result['validation'] else 'Non'}")
    print(f"✅ Coût API: ${total_cost:.4f}")

    print("\n" + "=" * 80)
    print("✅ TEST TERMINÉ")
    print("=" * 80)


def main():
    """Point d'entrée principal."""

    # Vérifier si ANTHROPIC_API_KEY est définie
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n❌ ERREUR: ANTHROPIC_API_KEY non définie dans .env")
        print("\nPour utiliser ce script, vous devez :")
        print("1. Créer un fichier .env à la racine du projet")
        print("2. Ajouter: ANTHROPIC_API_KEY=votre_clé_api")
        print("\nOu exporter la variable d'environnement:")
        print("export ANTHROPIC_API_KEY=votre_clé_api")
        sys.exit(1)

    # Récupérer le ticket_id si fourni
    ticket_id = sys.argv[1] if len(sys.argv) > 1 else None

    if ticket_id:
        print(f"\n🎫 Test avec le ticket: {ticket_id}")
    else:
        print("\n🎫 Aucun ticket spécifié, utilisation d'un ticket d'exemple")

    test_draft_with_mock_data(ticket_id)


if __name__ == "__main__":
    main()
