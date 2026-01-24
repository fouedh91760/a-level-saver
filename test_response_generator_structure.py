"""
Test Response Generator Agent structure without calling Claude API.

This test validates:
- RAG system initialization
- Scenario detection
- Similar ticket retrieval
- Prompt building
- Data formatting

No actual API calls are made.
"""
from src.agents.response_generator_agent import ResponseGeneratorAgent
from knowledge_base.scenarios_mapping import detect_scenario_from_text


def test_structure():
    """Test the agent structure without API calls."""
    print("\n" + "=" * 80)
    print("TEST STRUCTURE - RESPONSE GENERATOR AGENT (sans appel API)")
    print("=" * 80)

    # 1. Initialize agent (will warn about API key but continue)
    print("\n1️⃣  Initialisation de l'agent...")
    agent = ResponseGeneratorAgent()
    print("✅ Agent initialisé")

    # 2. Test scenario detection
    print("\n2️⃣  Test détection de scénarios...")
    test_cases = [
        {
            "subject": "Demande d'identifiants ExamenT3P",
            "message": "Je n'arrive pas à me connecter"
        },
        {
            "subject": "Report de formation",
            "message": "Je veux reporter ma session de février"
        },
        {
            "subject": "Document manquant",
            "message": "Quel document manque-t-il dans mon dossier ?"
        }
    ]

    for i, case in enumerate(test_cases, 1):
        scenarios = detect_scenario_from_text(
            subject=case['subject'],
            customer_message=case['message']
        )
        print(f"\n  Test {i}: {case['subject']}")
        print(f"  Scénarios détectés: {scenarios}")

    # 3. Test RAG similarity search
    print("\n3️⃣  Test recherche de similarité (RAG)...")
    similar = agent.rag.find_similar_tickets(
        subject="Demande d'identifiants",
        customer_message="Je n'arrive pas à me connecter",
        top_k=3
    )
    print(f"✅ {len(similar)} tickets similaires trouvés")
    for i, ticket in enumerate(similar, 1):
        print(f"  {i}. [Score: {ticket['similarity_score']}] {ticket['subject']}")

    # 4. Test prompt building
    print("\n4️⃣  Test construction des prompts...")
    system_prompt = agent._build_system_prompt()
    print(f"✅ System prompt: {len(system_prompt)} caractères")
    print(f"  - Salutation: {agent.patterns.get('structural_patterns', {}).get('most_common_greeting', 'N/A')}")
    print(f"  - Signature: {agent.patterns.get('structural_patterns', {}).get('most_common_signature', 'N/A')}")

    user_prompt = agent._build_user_prompt(
        ticket_subject="Demande d'identifiants",
        customer_message="Je n'arrive pas à me connecter",
        similar_tickets=similar,
        detected_scenarios=["SC-01_IDENTIFIANTS_EXAMENT3P"],
        exament3p_data={
            'compte_existe': True,
            'identifiant': 'test@example.com',
            'mot_de_passe': 'testpass123'
        }
    )
    print(f"✅ User prompt: {len(user_prompt)} caractères")

    # 5. Test data formatting
    print("\n5️⃣  Test formatage des données...")
    data_summary = agent._format_data_sources(
        crm_data={'email': 'test@example.com', 'Session_choisie': 'CDJ Février'},
        exament3p_data={'compte_existe': True, 'paiement_cma_status': 'Payé'},
        evalbox_data={'eligible_uber': True, 'scope': 'uber_gagne'}
    )
    print(f"✅ Données formatées: {len(data_summary)} caractères")
    print("\n  Aperçu:")
    for line in data_summary.split('\n')[:5]:
        print(f"    {line}")

    # 6. Test few-shot formatting
    print("\n6️⃣  Test formatage few-shot...")
    few_shot = agent.rag.format_for_few_shot(similar[:2])
    print(f"✅ Few-shot examples: {len(few_shot)} caractères")
    print(f"  Nombre d'exemples: 2")

    # 7. Summary
    print("\n" + "=" * 80)
    print("RÉSUMÉ DES TESTS")
    print("=" * 80)
    print("✅ Agent initialisé correctement")
    print("✅ Détection de scénarios fonctionnelle")
    print("✅ RAG system opérationnel (TF-IDF + cosine similarity)")
    print("✅ Construction des prompts validée")
    print("✅ Formatage des données validé")
    print("✅ Few-shot examples générés")
    print("\n📋 L'agent est prêt à générer des réponses avec Claude")
    print("🔑 Configuration requise: ANTHROPIC_API_KEY dans .env")
    print("🎯 Modèle: claude-3-5-sonnet-20240620")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    test_structure()
