#!/usr/bin/env python3
"""
Test du State Engine - Vérification des 3 sections (intention + statut + action).

Ce script teste que chaque réponse générée contient bien:
1. Section INTENTION: Réponse à la question du candidat
2. Section STATUT: État actuel du dossier
3. Section ACTION: Prochaine étape pour avancer
"""

import json
import sys
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.agents.deal_linking_agent import DealLinkingAgent
from src.agents.triage_agent import TriageAgent
from src.state_engine.state_detector import StateDetector
from src.state_engine.template_engine import TemplateEngine

# Initialiser les composants
desk_client = ZohoDeskClient()
crm_client = ZohoCRMClient()
linking_agent = DealLinkingAgent()
triage_agent = TriageAgent()
state_detector = StateDetector()
template_engine = TemplateEngine()

# 5 tickets variés à tester (avec deals CRM confirmés)
TEST_TICKETS = [
    '198709000448019181',  # STATUT_DOSSIER
    '198709000448043841',  # CONFIRMATION_SESSION
    '198709000448028627',  # DEMANDE_IDENTIFIANTS
    '198709000448028260',  # Autre ticket
    '198709000448029779',  # Autre ticket
]


def check_response_sections(response_text):
    """Vérifie que la réponse contient les 3 sections."""
    sections = {
        'intention': False,
        'statut': False,
        'action': False
    }

    # Détecter section intention (différentes formulations)
    intention_markers = [
        'Concernant', 'Vos identifiants', 'votre dossier', 'votre demande',
        'les dates', 'votre choix', 'votre session', 'l\'avancement',
        'date d\'examen', 'convocation'
    ]
    for marker in intention_markers:
        if marker.lower() in response_text.lower():
            sections['intention'] = True
            break

    # Détecter section statut
    statut_markers = [
        'Statut de votre dossier', 'en attente', 'instruction', 'validé',
        'synchronisé', 'traitement', 'validation', 'dossier est',
        'paiement', 'CMA', 'convocation'
    ]
    for marker in statut_markers:
        if marker.lower() in response_text.lower():
            sections['statut'] = True
            break

    # Détecter section action
    action_markers = [
        'Prochaine', 'Action requise', 'étape', 'Pour avancer',
        'passer le test', 'surveiller', 'choisir', 'Passez le test',
        'envoyer', 'télécharger', 'corriger', 'attendre'
    ]
    for marker in action_markers:
        if marker.lower() in response_text.lower():
            sections['action'] = True
            break

    return sections


def main():
    print('=' * 70)
    print('TEST STATE ENGINE - 5 TICKETS VARIÉS')
    print('Vérification: intention + statut + action dans chaque réponse')
    print('=' * 70)
    print()

    results = []

    for i, ticket_id in enumerate(TEST_TICKETS, 1):
        print(f'[{i}/5] Ticket {ticket_id}...')

        try:
            # 1. Récupérer le ticket
            ticket = desk_client.get_ticket(ticket_id)
            threads = desk_client.get_all_threads_with_full_content(ticket_id)

            # 2. Extraire le deal_id depuis cf_opportunite
            cf = ticket.get('cf', {})
            cf_opportunite = cf.get('cf_opportunite', '')

            # Extraire l'ID du deal depuis l'URL
            deal_id = None
            if cf_opportunite and 'Potentials/' in cf_opportunite:
                deal_id = cf_opportunite.split('Potentials/')[-1].split('?')[0].split('/')[0]

            if not deal_id:
                print(f'  [!] Pas de deal CRM trouvé')
                results.append({'ticket_id': ticket_id, 'error': 'NO_DEAL'})
                print()
                continue

            # Récupérer les données du deal
            deal_data = crm_client.get_deal(deal_id)
            if not deal_data:
                print(f'  [!] Deal {deal_id} non trouvé dans CRM')
                results.append({'ticket_id': ticket_id, 'error': 'DEAL_NOT_FOUND'})
                print()
                continue

            # 3. Triage
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

            # 4. Détecter l'état
            examt3p_data = {}
            linking_result = {
                'deal_id': deal_id,
                'deal_data': deal_data,
            }

            state = state_detector.detect_state(
                deal_data=deal_data,
                examt3p_data=examt3p_data,
                triage_result=triage_result,
                linking_result=linking_result,
            )

            # 5. Générer la réponse
            response_result = template_engine.generate_response(state)
            response_text = response_result.get('response_text', '')
            template_used = response_result.get('template_used', 'N/A')

            # 6. Vérifier les sections
            sections = check_response_sections(response_text)

            # Afficher résultat
            intention = triage_result.get('detected_intent', 'N/A')
            print(f'  État: {state.name}')
            print(f'  Intention: {intention}')
            print(f'  Template: {template_used}')
            print(f'  Sections:')
            print(f'    - Intention: {"OK" if sections["intention"] else "MANQUANTE"}')
            print(f'    - Statut: {"OK" if sections["statut"] else "MANQUANTE"}')
            print(f'    - Action: {"OK" if sections["action"] else "MANQUANTE"}')

            all_ok = all(sections.values())
            results.append({
                'ticket_id': ticket_id,
                'state': state.name,
                'intention': intention,
                'template': template_used,
                'sections': sections,
                'all_ok': all_ok,
                'response_preview': response_text[:300]
            })

            if not all_ok:
                print(f'  [!] Sections manquantes détectées')

            print()

        except Exception as e:
            print(f'  ERREUR: {str(e)[:80]}')
            results.append({
                'ticket_id': ticket_id,
                'error': str(e)
            })
            print()

    # Résumé
    print('=' * 70)
    print('RÉSUMÉ')
    print('=' * 70)

    valid_results = [r for r in results if not r.get('error')]
    ok_count = sum(1 for r in valid_results if r.get('all_ok'))

    print(f'Tickets analysés: {len(valid_results)}/5')
    print(f'Tickets OK (3 sections): {ok_count}/{len(valid_results)}')
    print()

    # Détails des problèmes
    for r in results:
        if r.get('error'):
            print(f"[X] {r['ticket_id']}: ERREUR - {r['error'][:50]}")
        elif not r.get('all_ok'):
            sections = r.get('sections', {})
            missing = [k for k, v in sections.items() if not v]
            print(f"[!] {r['ticket_id']}: {r['state']} - Manque: {missing}")
        else:
            print(f"[OK] {r['ticket_id']}: {r['state']}")

    # Sauvegarder les résultats
    with open('data/test_sections_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print()
    print(f'Résultats sauvegardés: data/test_sections_results.json')


if __name__ == '__main__':
    main()
