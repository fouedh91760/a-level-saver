#!/usr/bin/env python3
"""Debug script to investigate department transfer issues."""
import sys
sys.path.insert(0, '.')

from src.zoho_client import ZohoDeskClient

def main():
    client = ZohoDeskClient()

    print("\n" + "=" * 60)
    print("🔍 DIAGNOSTIC DES DÉPARTEMENTS ZOHO DESK")
    print("=" * 60)

    # 1. List all departments
    print("\n📋 Liste des départements:")
    print("-" * 60)
    departments = client.list_departments()
    for dept in departments:
        print(f"  ID: {dept.get('id')}")
        print(f"  Name: {dept.get('name')}")
        print(f"  isEnabled: {dept.get('isEnabled')}")
        print(f"  layoutId: {dept.get('layoutId', 'N/A')}")
        print(f"  associatedAgentIds: {dept.get('associatedAgentIds', [])}")
        print()

    # 2. Get ticket details
    ticket_id = sys.argv[1] if len(sys.argv) > 1 else None
    if ticket_id:
        print(f"\n🎫 Détails du ticket {ticket_id}:")
        print("-" * 60)
        ticket = client.get_ticket(ticket_id)
        print(f"  Subject: {ticket.get('subject')}")
        print(f"  Status: {ticket.get('status')}")
        print(f"  Current departmentId: {ticket.get('departmentId')}")
        print(f"  Current layoutId: {ticket.get('layoutId')}")
        print(f"  layoutDetails: {ticket.get('layoutDetails')}")

        # Find current department name
        current_dept_id = ticket.get('departmentId')
        current_dept_name = "Unknown"
        for dept in departments:
            if str(dept.get('id')) == str(current_dept_id):
                current_dept_name = dept.get('name')
                break
        print(f"  Current department name: {current_dept_name}")

        # 3. Try to get more info about what fields are required
        print("\n🔧 Test de mise à jour minimale:")
        print("-" * 60)

        # Try just updating status to see if basic updates work
        try:
            result = client.update_ticket(ticket_id, {"priority": ticket.get('priority', 'Medium')})
            print("  ✅ Mise à jour basique fonctionne")
        except Exception as e:
            print(f"  ❌ Échec mise à jour basique: {e}")

        # Try getting department layouts
        print("\n📐 Layouts par département:")
        print("-" * 60)
        for dept in departments:
            dept_name = dept.get('name')
            dept_id = dept.get('id')
            layout_id = dept.get('layoutId', 'N/A')
            is_enabled = dept.get('isEnabled', False)
            print(f"  {dept_name}: ID={dept_id}, layoutId={layout_id}, enabled={is_enabled}")

    client.close()

if __name__ == "__main__":
    main()
