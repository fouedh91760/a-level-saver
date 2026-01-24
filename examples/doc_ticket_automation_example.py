"""
Example: Complete DOC Ticket Automation

This example demonstrates the full workflow for automating DOC ticket responses:
1. Process a single ticket through the complete workflow
2. Use RAG to find similar tickets
3. Generate response with Claude
4. Validate compliance
5. Create CRM note and draft

Based on:
- 137 Fouad responses analyzed
- 26+ scenarios from knowledge base
- RAG system with 100 tickets
"""
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.workflows.doc_ticket_workflow import DOCTicketWorkflow
from src.agents.response_generator_agent import ResponseGeneratorAgent
from src.utils.response_rag import ResponseRAG
from knowledge_base.scenarios_mapping import (
    detect_scenario_from_text,
    SCENARIOS,
    validate_response_compliance
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def example_1_full_workflow():
    """Example 1: Process a complete DOC ticket through workflow."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: FULL WORKFLOW")
    print("=" * 80)

    workflow = DOCTicketWorkflow()

    try:
        # Process a real ticket
        # Note: Replace with actual ticket ID from Zoho Desk
        ticket_id = "198709000445353417"

        print(f"\n🎯 Processing ticket: {ticket_id}")
        print("   Mode: Manual review (auto_* = False)")

        result = workflow.process_ticket(
            ticket_id=ticket_id,
            auto_create_draft=False,    # Review before creating
            auto_update_crm=False,       # Review before updating
            auto_update_ticket=False     # Review before updating
        )

        print(f"\n{'=' * 80}")
        print("WORKFLOW RESULT")
        print(f"{'=' * 80}")

        print(f"\n✅ Success: {result['success']}")
        print(f"📍 Stopped at: {result['workflow_stage']}")

        if result.get('triage_result'):
            print(f"\n1️⃣  TRIAGE:")
            print(f"   Action: {result['triage_result'].get('action', 'GO')}")

        if result.get('analysis_result'):
            print(f"\n2️⃣  ANALYSIS:")
            print(f"   Deal ID: {result['analysis_result'].get('deal_id', 'N/A')}")
            print(f"   Ancien dossier: {result['analysis_result'].get('ancien_dossier', False)}")

        if result.get('response_result'):
            print(f"\n3️⃣  RESPONSE:")
            print(f"   Scénarios: {result['response_result'].get('detected_scenarios', [])}")
            print(f"   Similar tickets: {len(result['response_result'].get('similar_tickets', []))}")
            print(f"   Requires CRM update: {result['response_result'].get('requires_crm_update', False)}")

            print(f"\n   📝 GENERATED RESPONSE:")
            print(f"   {'-' * 76}")
            response_text = result['response_result'].get('response_text', '')
            # Show first 500 chars
            preview = response_text[:500] + "..." if len(response_text) > 500 else response_text
            print(f"   {preview}")
            print(f"   {'-' * 76}")

        if result.get('crm_note'):
            print(f"\n4️⃣  CRM NOTE:")
            print(f"   {result['crm_note'][:200]}...")

        if result.get('errors'):
            print(f"\n⚠️  ERRORS:")
            for error in result['errors']:
                print(f"   - {error}")

    except Exception as e:
        logger.error(f"Error in example 1: {e}")
        import traceback
        traceback.print_exc()
    finally:
        workflow.close()


def example_2_rag_search():
    """Example 2: Use RAG to find similar tickets."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: RAG SIMILARITY SEARCH")
    print("=" * 80)

    rag = ResponseRAG("fouad_tickets_analysis.json")

    # Sample queries
    queries = [
        {
            "subject": "Demande d'identifiants ExamenT3P",
            "message": "Bonjour, je n'arrive pas à me connecter. Pouvez-vous me renvoyer mes identifiants ?"
        },
        {
            "subject": "Report de ma session de février",
            "message": "J'ai décalé mon examen théorique, je voudrais reporter ma formation."
        },
        {
            "subject": "Statut de mon dossier",
            "message": "Où en est mon dossier ? Ai-je été inscrit à l'examen ?"
        }
    ]

    for i, query in enumerate(queries, 1):
        print(f"\n{'=' * 80}")
        print(f"QUERY {i}: {query['subject']}")
        print(f"{'=' * 80}")

        similar_tickets = rag.find_similar_tickets(
            subject=query['subject'],
            customer_message=query['message'],
            top_k=3
        )

        print(f"\n🔍 Top 3 tickets similaires:")
        for j, ticket in enumerate(similar_tickets, 1):
            print(f"\n  {j}. [Score: {ticket['similarity_score']}]")
            print(f"     Sujet: {ticket['subject']}")
            print(f"     Ticket: #{ticket['ticket_number']}")
            print(f"     Réponses: {len(ticket['fouad_responses'])}")

            if ticket['fouad_responses']:
                first_resp = ticket['fouad_responses'][0]['content']
                preview = first_resp[:150].replace('\n', ' ')
                print(f"     Aperçu: {preview}...")


def example_3_response_generation():
    """Example 3: Generate response with Claude + RAG."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: RESPONSE GENERATION (Structure test)")
    print("=" * 80)

    agent = ResponseGeneratorAgent()

    # Sample ticket data
    ticket_data = {
        "subject": "Demande d'identifiants ExamenT3P",
        "customer_message": "Bonjour, je n'arrive pas à me connecter sur ExamenT3P. Pouvez-vous me renvoyer mes identifiants ? Merci",
        "exament3p_data": {
            "compte_existe": True,
            "identifiant": "jean.dupont@gmail.com",
            "mot_de_passe": "Pass123!",
            "paiement_cma_status": "Payé",
            "documents_manquants": []
        },
        "crm_data": {
            "email": "jean.dupont@gmail.com",
            "Session_choisie": "Session CDJ Février 2026",
            "Date_de_depot_CMA": "2025-12-15"
        }
    }

    print(f"\n📋 Ticket: {ticket_data['subject']}")
    print(f"💬 Message: {ticket_data['customer_message']}")

    # Detect scenarios
    scenarios = detect_scenario_from_text(
        subject=ticket_data['subject'],
        customer_message=ticket_data['customer_message'],
        crm_data=ticket_data['crm_data']
    )

    print(f"\n🎯 Scénarios détectés: {scenarios}")

    for scenario_id in scenarios:
        if scenario_id in SCENARIOS:
            scenario = SCENARIOS[scenario_id]
            print(f"\n  {scenario_id}:")
            print(f"    Nom: {scenario['name']}")
            if scenario.get('template_notes'):
                print(f"    Notes: {scenario['template_notes']}")
            if scenario.get('mandatory_blocks'):
                print(f"    Blocs obligatoires: {scenario['mandatory_blocks']}")

    # Find similar tickets
    similar = agent.rag.find_similar_tickets(
        subject=ticket_data['subject'],
        customer_message=ticket_data['customer_message'],
        top_k=3
    )

    print(f"\n🔍 Tickets similaires trouvés: {len(similar)}")
    for i, ticket in enumerate(similar, 1):
        print(f"  {i}. [{ticket['similarity_score']}] {ticket['subject']}")

    # Note: Actual Claude API call would happen here
    print("\n⚠️  Note: Appel Claude API désactivé dans cet exemple")
    print("    Pour générer réellement, configurez ANTHROPIC_API_KEY")

    # Show what the prompt would look like
    system_prompt = agent._build_system_prompt()
    print(f"\n📝 System prompt: {len(system_prompt)} caractères")
    print(f"   Extrait: {system_prompt[:200]}...")


def example_4_scenario_validation():
    """Example 4: Validate response compliance."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: RESPONSE VALIDATION")
    print("=" * 80)

    # Sample response
    sample_response = """Bonjour,

Voici vos identifiants ExamenT3P :

🔐 **Identifiants** :
• **Identifiant** : jean.dupont@gmail.com
• **Mot de passe** : Pass123!

⚠️ Ces identifiants sont personnels et confidentiels. Ne les communiquez jamais à qui que ce soit.

Vous pouvez maintenant accéder à votre espace sur exament3p.fr pour suivre votre dossier.

📧 Vérifiez vos spams si vous ne recevez pas nos emails.

Bien cordialement,
L'équipe Cab Formations"""

    # Validate for SC-01_IDENTIFIANTS_EXAMENT3P
    scenario_id = "SC-01_IDENTIFIANTS_EXAMENT3P"
    validation = validate_response_compliance(sample_response, scenario_id)

    print(f"\n📋 Scénario: {scenario_id}")
    print(f"✅ Compliant: {validation['compliant']}")

    if validation['missing_blocks']:
        print(f"\n⚠️  Blocs manquants:")
        for block in validation['missing_blocks']:
            print(f"   - {block}")

    if validation['forbidden_terms_found']:
        print(f"\n❌ Termes interdits trouvés:")
        for term in validation['forbidden_terms_found']:
            print(f"   - {term}")

    if validation['compliant']:
        print(f"\n✅ La réponse est conforme au scénario {scenario_id}")


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("DOC TICKET AUTOMATION - EXAMPLES")
    print("=" * 80)

    # Example 2: RAG search (no API calls)
    example_2_rag_search()

    # Example 3: Response generation structure
    example_3_response_generation()

    # Example 4: Validation
    example_4_scenario_validation()

    # Example 1: Full workflow (would need real ticket + API)
    # Uncomment when ready to test with real tickets:
    # example_1_full_workflow()

    print("\n" + "=" * 80)
    print("✅ All examples completed")
    print("=" * 80)
    print("\n📚 See DOC_TICKET_AUTOMATION.md for full documentation")


if __name__ == "__main__":
    main()
