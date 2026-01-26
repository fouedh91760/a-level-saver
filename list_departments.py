#!/usr/bin/env python3
"""
Script pour lister tous les départements Zoho Desk (avec pagination).

Usage:
    python list_departments.py
"""

from config import settings
import requests


def get_access_token():
    """Get a fresh access token."""
    url = f"https://accounts.zoho.{settings.zoho_datacenter}/oauth/v2/token"
    data = {
        "refresh_token": settings.zoho_refresh_token,
        "client_id": settings.zoho_client_id,
        "client_secret": settings.zoho_client_secret,
        "grant_type": "refresh_token"
    }
    response = requests.post(url, data=data)
    response.raise_for_status()
    return response.json()["access_token"]


def list_all_departments():
    """List all departments with pagination."""
    access_token = get_access_token()

    all_departments = []
    from_index = 0
    limit = 100  # Max per page

    while True:
        url = f"{settings.zoho_desk_api_url}/departments"
        params = {
            "orgId": settings.zoho_desk_org_id,
            "from": from_index,
            "limit": limit
        }
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "orgId": str(settings.zoho_desk_org_id)
        }

        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        departments = data.get("data", [])
        if not departments:
            break

        all_departments.extend(departments)

        # Check if there are more pages
        if len(departments) < limit:
            break

        from_index += limit

    return all_departments


def main():
    print("=" * 60)
    print("LISTE DES DÉPARTEMENTS ZOHO DESK")
    print("=" * 60)

    departments = list_all_departments()

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


if __name__ == "__main__":
    main()
