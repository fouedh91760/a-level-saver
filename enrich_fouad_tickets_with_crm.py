"""
Enrich Fouad tickets with CRM data and re-analyze scenarios.

This script:
1. Loads fouad_tickets_analysis.json (100 tickets)
2. For each ticket, finds the associated CRM Deal
3. Extracts Amount, Type_formation, dates from Deal
4. Enriches tickets with CRM data
5. Re-runs scenario detection with accurate CRM-based logic
6. Generates new statistics with correct HORS_PARTENARIAT detection

Expected results:
- ~90 tickets with Amount = 20€ (Uber partnership)
- ~10 tickets with Amount != 20€ (HORS_PARTENARIAT)
- Accurate scenario distribution

Duration: ~10-15 minutes (100 API calls to CRM)
"""
import json
import logging
import time
from datetime import datetime
from collections import Counter
from src.zoho_client import ZohoCRMClient, ZohoDeskClient
from src.ticket_deal_linker import TicketDealLinker
from knowledge_base.scenarios_mapping import detect_scenario_from_text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def enrich_tickets_with_crm():
    """Enrich tickets with CRM data."""
    print("\n" + "=" * 80)
    print("ENRICHISSEMENT DES TICKETS FOUAD AVEC DONNÉES CRM")
    print("=" * 80)

    # Load existing tickets
    with open('fouad_tickets_analysis.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    tickets = data['tickets']
    print(f"\n📊 {len(tickets)} tickets à enrichir")

    # Initialize clients
    crm_client = ZohoCRMClient()
    desk_client = ZohoDeskClient()
    deal_linker = TicketDealLinker()

    enriched_tickets = []
    stats = {
        'total': len(tickets),
        'with_deal': 0,
        'without_deal': 0,
        'amount_20': 0,
        'amount_other': 0,
        'amount_zero': 0,
        'errors': 0
    }

    start_time = time.time()

    try:
        for i, ticket in enumerate(tickets, 1):
            ticket_id = ticket['ticket_id']
            email = ticket.get('contact_email', '')

            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                remaining = (len(tickets) - i) / rate if rate > 0 else 0
                print(f"\n⏳ Progression : {i}/{len(tickets)} tickets")
                print(f"   Temps restant : ~{int(remaining/60)} min {int(remaining%60)} sec")
                print(f"   Deals trouvés : {stats['with_deal']}")
                print(f"   Amount 20€ : {stats['amount_20']}")
                print(f"   Amount autre : {stats['amount_other']}")

            # Try to find deal
            try:
                logger.info(f"Ticket {i}/{len(tickets)}: {ticket_id} ({email})")

                deal_id = deal_linker.find_deal_for_ticket(ticket_id, email)

                if deal_id:
                    # Get deal data
                    deal = crm_client.get_deal(deal_id)

                    crm_data = {
                        'deal_id': deal_id,
                        'Deal_Name': deal.get('Deal_Name', ''),
                        'Amount': deal.get('Amount', 0),
                        'Stage': deal.get('Stage', ''),
                        'Type_formation': deal.get('Type_formation', ''),
                        'Date_de_depot_CMA': deal.get('Date_de_depot_CMA', ''),
                        'Date_de_cloture': deal.get('Date_de_cloture', ''),
                        'Session_choisie': deal.get('Session_choisie', ''),
                        'Owner': deal.get('Owner', {}).get('name', '')
                    }

                    ticket['crm_data'] = crm_data
                    stats['with_deal'] += 1

                    # Count amounts
                    amount = crm_data['Amount']
                    if amount == 20:
                        stats['amount_20'] += 1
                    elif amount == 0:
                        stats['amount_zero'] += 1
                    else:
                        stats['amount_other'] += 1

                    logger.info(f"  ✅ Deal trouvé: {deal_id} (Amount: {amount}€)")

                else:
                    ticket['crm_data'] = None
                    stats['without_deal'] += 1
                    logger.warning(f"  ⚠️  Pas de deal trouvé pour {email}")

                enriched_tickets.append(ticket)

                # Rate limiting: wait 0.5s between requests
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"  ❌ Erreur pour ticket {ticket_id}: {e}")
                ticket['crm_data'] = None
                ticket['enrichment_error'] = str(e)
                enriched_tickets.append(ticket)
                stats['errors'] += 1

        # Save enriched data
        enriched_data = {
            'timestamp': datetime.now().isoformat(),
            'agent': data['agent'],
            'department': data['department'],
            'total_tickets_checked': data['total_tickets_checked'],
            'tickets_with_fouad_response': data['tickets_with_fouad_response'],
            'enrichment_stats': stats,
            'tickets': enriched_tickets
        }

        output_file = 'fouad_tickets_analysis_with_crm.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enriched_data, f, indent=2, ensure_ascii=False)

        print(f"\n{'=' * 80}")
        print("ENRICHISSEMENT TERMINÉ")
        print(f"{'=' * 80}")
        print(f"\n📄 Fichier sauvegardé : {output_file}")
        print(f"\n📊 Statistiques :")
        print(f"   Total tickets : {stats['total']}")
        print(f"   Avec deal CRM : {stats['with_deal']} ({stats['with_deal']/stats['total']*100:.1f}%)")
        print(f"   Sans deal : {stats['without_deal']}")
        print(f"   Erreurs : {stats['errors']}")
        print(f"\n💰 Distribution des montants (Amount) :")
        print(f"   20€ (Uber) : {stats['amount_20']} ({stats['amount_20']/stats['with_deal']*100:.1f}% des deals)")
        print(f"   Autre montant : {stats['amount_other']} ({stats['amount_other']/stats['with_deal']*100:.1f}%)")
        print(f"   0€ (non défini) : {stats['amount_zero']}")

        return enriched_data

    finally:
        crm_client.close()
        desk_client.close()


def reanalyze_scenarios_with_crm():
    """Re-analyze scenarios with CRM data."""
    print("\n" + "=" * 80)
    print("RÉ-ANALYSE DES SCÉNARIOS AVEC DONNÉES CRM")
    print("=" * 80)

    # Load enriched tickets
    try:
        with open('fouad_tickets_analysis_with_crm.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("\n❌ Fichier fouad_tickets_analysis_with_crm.json non trouvé")
        print("   Exécutez d'abord l'enrichissement CRM")
        return None

    tickets = data['tickets']
    print(f"\n📊 Analyse de {len(tickets)} tickets enrichis...")

    scenario_counter = Counter()
    hors_partenariat_details = []

    for ticket in tickets:
        subject = ticket.get('subject', '')

        # Get first customer question
        customer_message = ""
        customer_questions = ticket.get('customer_questions', [])
        if customer_questions:
            customer_message = customer_questions[0].get('content', '')

        # Get CRM data
        crm_data = ticket.get('crm_data')

        # Detect scenarios with CRM data
        scenarios = detect_scenario_from_text(
            subject=subject,
            customer_message=customer_message,
            crm_data=crm_data
        )

        # Count scenarios
        for scenario in scenarios:
            scenario_counter[scenario] += 1

        # Track HORS_PARTENARIAT cases
        if any('HORS_PARTENARIAT' in s for s in scenarios):
            hors_partenariat_details.append({
                'ticket_id': ticket['ticket_id'],
                'ticket_number': ticket.get('ticket_number', ''),
                'subject': subject,
                'amount': crm_data.get('Amount', 0) if crm_data else None,
                'scenarios': scenarios
            })

    # Display results
    print(f"\n{'=' * 80}")
    print("RÉSULTATS DE LA RÉ-ANALYSE")
    print(f"{'=' * 80}")

    print(f"\n🎯 Top 10 scénarios détectés :")
    for scenario, count in scenario_counter.most_common(10):
        print(f"   {scenario}: {count} ({count/len(tickets)*100:.1f}%)")

    print(f"\n🚨 Cas HORS_PARTENARIAT détectés : {len(hors_partenariat_details)}")
    if hors_partenariat_details:
        print(f"\n   Détails :")
        for i, case in enumerate(hors_partenariat_details[:10], 1):
            print(f"\n   {i}. Ticket #{case['ticket_number']}")
            print(f"      Sujet : {case['subject'][:60]}...")
            print(f"      Amount : {case['amount']}€")
            print(f"      Scénarios : {', '.join(case['scenarios'])}")

        if len(hors_partenariat_details) > 10:
            print(f"\n   ... et {len(hors_partenariat_details) - 10} autres cas")

    # Compare with old detection
    print(f"\n📊 Comparaison avant/après :")
    print(f"   Avant (faux positifs) : 102 SC-VTC_HORS_PARTENARIAT")
    print(f"   Après (logique CRM) : {scenario_counter.get('SC-VTC_HORS_PARTENARIAT', 0)} SC-VTC_HORS_PARTENARIAT")
    print(f"   Après (tous HORS) : {len(hors_partenariat_details)} total HORS_PARTENARIAT")

    reduction = 102 - len(hors_partenariat_details)
    print(f"\n   ✅ Réduction de {reduction} faux positifs ({reduction/102*100:.1f}%)")

    # Save analysis
    analysis_output = {
        'timestamp': datetime.now().isoformat(),
        'total_tickets': len(tickets),
        'scenario_distribution': dict(scenario_counter),
        'hors_partenariat_cases': hors_partenariat_details,
        'comparison': {
            'before': 102,
            'after': len(hors_partenariat_details),
            'reduction': reduction
        }
    }

    with open('scenario_analysis_with_crm.json', 'w', encoding='utf-8') as f:
        json.dump(analysis_output, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Analyse sauvegardée : scenario_analysis_with_crm.json")

    return analysis_output


def main():
    """Main execution."""
    print("\n🚀 Démarrage de l'enrichissement et ré-analyse...")

    # Step 1: Enrich with CRM data
    print("\n" + "=" * 80)
    print("ÉTAPE 1/2 : ENRICHISSEMENT CRM")
    print("=" * 80)

    enriched_data = enrich_tickets_with_crm()

    if not enriched_data:
        print("\n❌ Échec de l'enrichissement")
        return

    # Step 2: Re-analyze scenarios
    print("\n" + "=" * 80)
    print("ÉTAPE 2/2 : RÉ-ANALYSE DES SCÉNARIOS")
    print("=" * 80)

    analysis = reanalyze_scenarios_with_crm()

    if analysis:
        print("\n" + "=" * 80)
        print("✅ ENRICHISSEMENT ET RÉ-ANALYSE TERMINÉS")
        print("=" * 80)
        print("\n📂 Fichiers générés :")
        print("   1. fouad_tickets_analysis_with_crm.json (tickets enrichis)")
        print("   2. scenario_analysis_with_crm.json (nouvelle analyse)")
        print("\n🎯 Prochaine étape : Mettre à jour response_patterns_analysis.json")
        print("   avec les vrais scénarios détectés")


if __name__ == "__main__":
    main()
