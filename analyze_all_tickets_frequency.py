#!/usr/bin/env python3
"""
Analyse rapide de TOUS les tickets DOC pour statistiques de fréquence.

Ce script:
1. Récupère les sujets et statuts des 356 tickets
2. Estime les intentions à partir des sujets (sans appel IA)
3. Récupère les états CRM (Evalbox) quand possible
4. Génère des statistiques de fréquence pour priorisation des partials
"""

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.zoho_client import ZohoDeskClient, ZohoCRMClient


def estimate_intention_from_subject(subject: str, message: str = "") -> str:
    """Estime l'intention à partir du sujet du ticket."""
    text = f"{subject} {message}".lower()

    # Patterns pour chaque intention
    patterns = {
        'DEMANDE_IDENTIFIANTS': [
            r'identifiant', r'mot de passe', r'mdp', r'connexion', r'connecter',
            r'code', r'login', r'acc[eè]s', r'plateforme', r'evalbox', r'examt3p'
        ],
        'STATUT_DOSSIER': [
            r'statut', r'avancement', r'o[uù] en est', r'suivi', r'dossier',
            r'transmis', r'valid[eé]', r'instruction', r'nouvelles'
        ],
        'DEMANDE_DATE_EXAMEN': [
            r'date.{0,10}examen', r'prochaine.{0,10}session', r'quand.{0,10}passer',
            r'inscription.{0,10}examen', r'dates disponibles'
        ],
        'REPORT_DATE': [
            r'report', r'changer.{0,10}date', r'modifier.{0,10}date', r'autre date',
            r'annul', r'd[eé]caler', r'pas disponible', r'emp[eê]ch'
        ],
        'CONFIRMATION_SESSION': [
            r'session', r'formation', r'cours', r'horaire', r'jour', r'soir',
            r'pr[eé]sentiel', r'visio', r'confirm'
        ],
        'QUESTION_UBER': [
            r'uber', r'20\s*[€e]', r'offre', r'partenariat', r'eligib'
        ],
        'CONVOCATION': [
            r'convocation', r'lieu', r'adresse', r'cma', r'heure.{0,10}passage'
        ],
        'RESULTAT_EXAMEN': [
            r'r[eé]sultat', r'not[eé]', r'pass[eé]', r'rat[eé]', r'r[eé]ussi',
            r'[eé]chou[eé]', r'admis'
        ],
        'DOCUMENTS': [
            r'document', r'pi[eè]ce', r'justificatif', r'photo', r'permis',
            r't[eé]l[eé]charger', r'envoyer'
        ],
        'PAIEMENT': [
            r'paiement', r'pay[eé]', r'241', r'facture', r'r[eé]glement'
        ],
    }

    for intention, regex_list in patterns.items():
        for pattern in regex_list:
            if re.search(pattern, text):
                return intention

    return 'QUESTION_GENERALE'


def estimate_state_from_evalbox(evalbox: str, date_examen: str = None) -> str:
    """Estime l'état à partir du statut Evalbox."""
    if not evalbox:
        if date_examen:
            return 'EXAM_DATE_ASSIGNED_WAITING'
        return 'EXAM_DATE_EMPTY'

    evalbox_lower = evalbox.lower()

    if 'valide cma' in evalbox_lower:
        return 'VALIDE_CMA_WAITING_CONVOC'
    elif 'convoc' in evalbox_lower:
        return 'CONVOCATION_RECEIVED'
    elif 'synchronis' in evalbox_lower or 'instruction' in evalbox_lower:
        return 'DOSSIER_SYNCHRONIZED'
    elif 'pret a payer' in evalbox_lower or 'prêt' in evalbox_lower:
        return 'READY_TO_PAY'
    elif 'refus' in evalbox_lower or 'incomplet' in evalbox_lower:
        return 'DOSSIER_REFUSED'
    elif 'cr' in evalbox_lower or 'composition' in evalbox_lower:
        return 'DOSSIER_CREATED'
    elif 'examen pass' in evalbox_lower:
        return 'EXAM_PASSED'

    return 'UNKNOWN'


def main():
    print("=" * 70)
    print("ANALYSE DE FREQUENCE - TOUS LES TICKETS DOC")
    print("=" * 70)
    print()

    # Charger la liste des tickets
    with open('data/open_doc_tickets.txt', 'r') as f:
        ticket_ids = [line.strip() for line in f if line.strip()]

    print(f"Tickets a analyser: {len(ticket_ids)}")
    print()

    desk_client = ZohoDeskClient()
    crm_client = ZohoCRMClient()

    # Compteurs
    intention_counter = Counter()
    state_counter = Counter()
    evalbox_counter = Counter()
    amount_counter = Counter()
    errors = []
    analyzed = 0

    results = []

    # Analyser chaque ticket
    for i, ticket_id in enumerate(ticket_ids, 1):
        if i % 20 == 0 or i == 1:
            print(f"[{i}/{len(ticket_ids)}] En cours...")

        try:
            # Récupérer le ticket (juste le sujet, pas les threads)
            ticket = desk_client.get_ticket(ticket_id)
            subject = ticket.get('subject', '')

            # Récupérer le premier message client (s'il existe dans la description)
            description = ticket.get('description', '') or ''

            # Estimer l'intention
            intention = estimate_intention_from_subject(subject, description[:500])
            intention_counter[intention] += 1

            # Récupérer le deal CRM si lié
            cf = ticket.get('cf', {})
            cf_opportunite = cf.get('cf_opportunite', '')

            deal_id = None
            evalbox = None
            date_examen = None
            amount = None

            if cf_opportunite and 'Potentials/' in cf_opportunite:
                deal_id = cf_opportunite.split('Potentials/')[-1].split('?')[0].split('/')[0]

                try:
                    deal = crm_client.get_deal(deal_id)
                    if deal:
                        evalbox = deal.get('Evalbox') or ''
                        date_examen = deal.get('Date_examen_VTC')
                        amount = deal.get('Amount')

                        evalbox_counter[evalbox or 'N/A'] += 1
                        amount_counter[amount or 'N/A'] += 1
                except Exception:
                    pass

            # Estimer l'état
            state = estimate_state_from_evalbox(evalbox, date_examen)
            state_counter[state] += 1

            results.append({
                'ticket_id': ticket_id,
                'subject': subject[:100],
                'intention': intention,
                'state': state,
                'evalbox': evalbox,
                'amount': amount,
                'has_deal': deal_id is not None
            })

            analyzed += 1

        except Exception as e:
            errors.append({'ticket_id': ticket_id, 'error': str(e)[:50]})

    print()
    print("=" * 70)
    print("RESULTATS")
    print("=" * 70)
    print()

    print(f"Tickets analyses: {analyzed}/{len(ticket_ids)}")
    print(f"Erreurs: {len(errors)}")
    print()

    # Statistiques Intentions
    print("INTENTIONS (frequence):")
    print("-" * 40)
    for intention, count in intention_counter.most_common():
        pct = count / analyzed * 100
        print(f"  {intention:30} {count:4} ({pct:5.1f}%)")
    print()

    # Statistiques États
    print("ETATS (frequence):")
    print("-" * 40)
    for state, count in state_counter.most_common():
        pct = count / analyzed * 100
        print(f"  {state:30} {count:4} ({pct:5.1f}%)")
    print()

    # Statistiques Evalbox
    print("EVALBOX (frequence):")
    print("-" * 40)
    for evalbox, count in evalbox_counter.most_common(10):
        pct = count / analyzed * 100
        print(f"  {str(evalbox)[:30]:30} {count:4} ({pct:5.1f}%)")
    print()

    # Statistiques Amount (Uber 20 vs autres)
    print("AMOUNT (Uber 20 vs autres):")
    print("-" * 40)
    for amount, count in amount_counter.most_common():
        pct = count / analyzed * 100
        label = f"{amount}" if amount else "N/A"
        print(f"  {label:30} {count:4} ({pct:5.1f}%)")
    print()

    # Sauvegarder les résultats
    output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'total_tickets': len(ticket_ids),
            'analyzed': analyzed,
            'errors': len(errors)
        },
        'frequency': {
            'intentions': dict(intention_counter.most_common()),
            'states': dict(state_counter.most_common()),
            'evalbox': dict(evalbox_counter.most_common()),
            'amount': {str(k): v for k, v in amount_counter.most_common()}
        },
        'tickets': results[:50],  # Garder les 50 premiers comme échantillon
        'errors': errors[:10]  # Garder les 10 premières erreurs
    }

    with open('data/frequency_analysis_all_tickets.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Resultats sauvegardes: data/frequency_analysis_all_tickets.json")

    # Recommandations de priorité
    print()
    print("=" * 70)
    print("RECOMMANDATIONS PARTIALS PAR PRIORITE")
    print("=" * 70)
    print()

    # Mapper intentions aux partials manquants
    intention_to_partial = {
        'STATUT_DOSSIER': 'partials/intentions/statut_dossier.html',
        'DEMANDE_IDENTIFIANTS': 'partials/intentions/demande_identifiants.html',
        'CONFIRMATION_SESSION': 'partials/intentions/confirmation_session.html',
        'DEMANDE_DATE_EXAMEN': 'partials/intentions/demande_date.html',
        'REPORT_DATE': 'partials/intentions/report_date.html',
        'QUESTION_UBER': 'partials/intentions/question_uber.html',
        'CONVOCATION': 'partials/intentions/convocation.html',
        'RESULTAT_EXAMEN': 'partials/intentions/resultat_examen.html',
        'DOCUMENTS': 'partials/intentions/documents.html',
        'PAIEMENT': 'partials/intentions/paiement.html',
        'QUESTION_GENERALE': 'partials/intentions/question_generale.html',
    }

    state_to_partial = {
        'EXAM_DATE_EMPTY': 'partials/statuts/exam_date_empty.html',
        'EXAM_DATE_ASSIGNED_WAITING': 'partials/statuts/exam_date_assigned.html',
        'VALIDE_CMA_WAITING_CONVOC': 'partials/statuts/valide_cma.html',
        'CONVOCATION_RECEIVED': 'partials/statuts/convocation_received.html',
        'DOSSIER_SYNCHRONIZED': 'partials/statuts/dossier_synchronized.html',
        'READY_TO_PAY': 'partials/statuts/ready_to_pay.html',
        'DOSSIER_REFUSED': 'partials/statuts/dossier_refused.html',
        'DOSSIER_CREATED': 'partials/statuts/dossier_created.html',
        'EXAM_PASSED': 'partials/statuts/exam_passed.html',
    }

    print("P1 - INTENTIONS (>10% des tickets):")
    for intention, count in intention_counter.most_common():
        pct = count / analyzed * 100
        if pct >= 10:
            partial = intention_to_partial.get(intention, f'A CREER: {intention}')
            print(f"  [{count:3}] {intention} -> {partial}")

    print()
    print("P2 - INTENTIONS (5-10% des tickets):")
    for intention, count in intention_counter.most_common():
        pct = count / analyzed * 100
        if 5 <= pct < 10:
            partial = intention_to_partial.get(intention, f'A CREER: {intention}')
            print(f"  [{count:3}] {intention} -> {partial}")

    print()
    print("P1 - ETATS (>10% des tickets):")
    for state, count in state_counter.most_common():
        pct = count / analyzed * 100
        if pct >= 10:
            partial = state_to_partial.get(state, f'A CREER: {state}')
            print(f"  [{count:3}] {state} -> {partial}")


if __name__ == '__main__':
    main()
