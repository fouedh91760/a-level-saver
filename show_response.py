#!/usr/bin/env python3
"""Génère et affiche une réponse complète pour un ticket."""

import sys
sys.path.insert(0, 'C:/Users/fouad/Documents/a-level-saver')

from dotenv import load_dotenv
load_dotenv()

from src.zoho_client import ZohoDeskClient, ZohoCRMClient
from src.agents.triage_agent import TriageAgent
from src.state_engine.state_detector import StateDetector
from src.state_engine.template_engine import TemplateEngine

desk_client = ZohoDeskClient()
crm_client = ZohoCRMClient()
triage_agent = TriageAgent()
state_detector = StateDetector()
template_engine = TemplateEngine()

# Ticket 1: EXAM_DATE_EMPTY + STATUT_DOSSIER
ticket_id = '198709000448019181'
ticket = desk_client.get_ticket(ticket_id)
threads = desk_client.get_all_threads_with_full_content(ticket_id)

# Get deal
cf = ticket.get('cf', {})
cf_opportunite = cf.get('cf_opportunite', '')
deal_id = cf_opportunite.split('Potentials/')[-1].split('?')[0].split('/')[0]
deal_data = crm_client.get_deal(deal_id)

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

# Save to file
with open('data/sample_response.html', 'w', encoding='utf-8') as f:
    f.write(f"<!-- TICKET: {ticket_id} -->\n")
    f.write(f"<!-- ETAT: {state.name} -->\n")
    f.write(f"<!-- INTENTION: {triage_result.get('detected_intent')} -->\n")
    f.write(f"<!-- TEMPLATE: {response_result.get('template_used')} -->\n\n")
    f.write(response_text)

print(f"Response saved to data/sample_response.html")
print(f"TICKET: {ticket_id}")
print(f"ETAT: {state.name}")
print(f"INTENTION: {triage_result.get('detected_intent')}")
print(f"TEMPLATE: {response_result.get('template_used')}")
