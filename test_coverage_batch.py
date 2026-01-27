#!/usr/bin/env python3
"""
Test de couverture sur un échantillon de tickets.
Vérifie que les réponses générées ont les 3 sections.
"""

import sys
import os
import json
import random
from collections import Counter
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, 'C:/Users/fouad/Documents/a-level-saver')

from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.agents.triage_agent import TriageAgent
from src.state_engine.state_detector import StateDetector
from src.state_engine.template_engine import TemplateEngine


def check_response_sections(response_text):
    """Verifie que la reponse contient les 3 sections."""
    sections = {
        'intention': False,
        'statut': False,
        'action': False
    }

    # Detecter section intention
    intention_markers = [
        'Concernant', 'Vos identifiants', 'votre dossier', 'votre demande',
        'les dates', 'votre choix', 'votre session', "l'avancement",
        'date d\'examen', 'convocation', 'offre Uber', 'resultat'
    ]
    for marker in intention_markers:
        if marker.lower() in response_text.lower():
            sections['intention'] = True
            break

    # Detecter section statut
    statut_markers = [
        'Statut de votre dossier', 'en attente', 'instruction', 'valide',
        'synchronise', 'traitement', 'validation', 'dossier est',
        'paiement', 'CMA', 'convocation'
    ]
    for marker in statut_markers:
        if marker.lower() in response_text.lower():
            sections['statut'] = True
            break

    # Detecter section action
    action_markers = [
        'Prochaine', 'Action requise', 'etape', 'Pour avancer',
        'passer le test', 'surveiller', 'choisir', 'Passez le test',
        'envoyer', 'telecharger', 'corriger', 'attendre'
    ]
    for marker in action_markers:
        if marker.lower() in response_text.lower():
            sections['action'] = True
            break

    return sections


def main():
    # Charger les tickets
    with open('data/open_doc_tickets.txt', 'r') as f:
        all_tickets = [line.strip() for line in f if line.strip()]

    # Echantillon aleatoire de 50 tickets
    sample_size = min(50, len(all_tickets))
    sample_tickets = random.sample(all_tickets, sample_size)

    print(f"Test de couverture sur {sample_size} tickets")
    print("=" * 60)

    desk_client = ZohoDeskClient()
    crm_client = ZohoCRMClient()
    triage_agent = TriageAgent()
    state_detector = StateDetector()
    template_engine = TemplateEngine()

    results = {
        'total': 0,
        'ok': 0,
        'missing_sections': [],
        'errors': [],
        'states': Counter(),
        'intentions': Counter(),
        'templates': Counter(),
    }

    for i, ticket_id in enumerate(sample_tickets, 1):
        if i % 10 == 0:
            print(f"[{i}/{sample_size}] En cours...")

        try:
            ticket = desk_client.get_ticket(ticket_id)
            threads = desk_client.get_all_threads_with_full_content(ticket_id)

            # Get deal
            cf = ticket.get('cf', {})
            cf_opportunite = cf.get('cf_opportunite', '')

            if not cf_opportunite or 'Potentials/' not in cf_opportunite:
                continue

            deal_id = cf_opportunite.split('Potentials/')[-1].split('?')[0].split('/')[0]
            deal_data = crm_client.get_deal(deal_id)

            if not deal_data:
                continue

            # Triage
            customer_message = ''
            for thread in threads:
                if thread.get('direction') == 'in':
                    customer_message = thread.get('content', '')[:1000]
                    break

            triage_result = triage_agent.triage_ticket(
                ticket_subject=ticket.get('subject', ''),
                thread_content=customer_message,
                deal_data=deal_data
            )

            # Detect state
            state = state_detector.detect_state(
                deal_data=deal_data,
                examt3p_data={},
                triage_result=triage_result,
                linking_result={'deal_id': deal_id, 'deal_data': deal_data},
            )

            # Generate response
            response_result = template_engine.generate_response(state)
            response_text = response_result.get('response_text', '')
            template_used = response_result.get('template_used', 'N/A')
            intention = triage_result.get('detected_intent', 'N/A')

            # Check sections
            sections = check_response_sections(response_text)
            all_ok = all(sections.values())

            results['total'] += 1
            results['states'][state.name] += 1
            results['intentions'][intention] += 1
            results['templates'][template_used] += 1

            if all_ok:
                results['ok'] += 1
            else:
                missing = [k for k, v in sections.items() if not v]
                results['missing_sections'].append({
                    'ticket_id': ticket_id,
                    'state': state.name,
                    'intention': intention,
                    'template': template_used,
                    'missing': missing
                })

        except Exception as e:
            results['errors'].append({'ticket_id': ticket_id, 'error': str(e)[:50]})

    # Resultats
    print()
    print("=" * 60)
    print("RESULTATS")
    print("=" * 60)
    print(f"Tickets analyses: {results['total']}")
    print(f"Tickets OK (3 sections): {results['ok']} ({results['ok']/max(results['total'],1)*100:.1f}%)")
    print(f"Erreurs: {len(results['errors'])}")
    print()

    print("ETATS les plus frequents:")
    for state, count in results['states'].most_common(5):
        print(f"  {state}: {count}")
    print()

    print("INTENTIONS les plus frequentes:")
    for intention, count in results['intentions'].most_common(5):
        print(f"  {intention}: {count}")
    print()

    print("TEMPLATES utilises:")
    for template, count in results['templates'].most_common(5):
        print(f"  {template}: {count}")
    print()

    if results['missing_sections']:
        print("SECTIONS MANQUANTES:")
        for item in results['missing_sections'][:10]:
            print(f"  {item['ticket_id']}: {item['state']} / {item['intention']} -> manque {item['missing']}")

    # Sauvegarder
    with open('data/coverage_test_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print()
    print("Resultats sauvegardes: data/coverage_test_results.json")


if __name__ == '__main__':
    main()
