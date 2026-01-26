#!/usr/bin/env python3
"""
Script pour lister tous les départements Zoho Desk.

Usage:
    python list_departments.py
"""

from src.zoho_client import ZohoDeskClient


def main():
    print("=" * 60)
    print("LISTE DES DÉPARTEMENTS ZOHO DESK")
    print("=" * 60)

    client = ZohoDeskClient()
    departments = client.list_departments()

    if not departments:
        print("❌ Aucun département trouvé")
        return

    print(f"\n✅ {len(departments)} département(s) trouvé(s):\n")

    # Trier par nom
    departments_sorted = sorted(departments, key=lambda d: d.get('name', ''))

    for dept in departments_sorted:
        dept_id = dept.get('id', 'N/A')
        dept_name = dept.get('name', 'N/A')
        dept_description = dept.get('description', '')
        is_enabled = dept.get('isEnabled', True)

        status = "✅" if is_enabled else "❌"
        print(f"  {status} ID: {dept_id}")
        print(f"     Name: '{dept_name}'")
        if dept_description:
            print(f"     Desc: {dept_description}")
        print()

    print("=" * 60)
    print("NOMS À UTILISER DANS LE CODE:")
    print("=" * 60)
    for dept in departments_sorted:
        if dept.get('isEnabled', True):
            print(f"  - '{dept.get('name')}'")

    client.close()


if __name__ == "__main__":
    main()
