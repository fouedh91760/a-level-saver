#!/usr/bin/env python3
"""Extrait et sauvegarde tous les IDs des tickets DOC ouverts."""

import json
from src.zoho_client import ZohoDeskClient

desk = ZohoDeskClient()

# Récupérer TOUS les tickets ouverts avec pagination
print("Récupération de tous les tickets ouverts...")
all_tickets = desk.list_all_tickets(status="Open")
print(f"Total tickets ouverts: {len(all_tickets)}")

# Filtrer par département DOC
doc_dept_id = "198709000025523146"
doc_tickets = [t for t in all_tickets if t.get("departmentId") == doc_dept_id]
print(f"Tickets DOC: {len(doc_tickets)}")

# Sauvegarder les IDs et infos minimales
ticket_list = []
for t in doc_tickets:
    ticket_list.append({
        "id": t.get("id"),
        "ticketNumber": t.get("ticketNumber"),
        "subject": t.get("subject", "")[:80],
        "createdTime": t.get("createdTime"),
        "status": t.get("status")
    })

# Sauvegarder
with open("doc_tickets_open_list.json", "w", encoding="utf-8") as f:
    json.dump(ticket_list, f, ensure_ascii=False, indent=2)

print(f"\nSauvegardé dans doc_tickets_open_list.json")
print(f"Tickets par lot de 10:")
for i in range(0, len(ticket_list), 10):
    lot = i // 10 + 1
    print(f"  Lot {lot}: tickets {i+1}-{min(i+10, len(ticket_list))}")
