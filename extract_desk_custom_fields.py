"""
Script pour extraire les champs personnalisés des tickets Zoho Desk.

Ce script récupère tous les champs disponibles sur les tickets pour identifier
le nom exact du champ "Opportunité" que vous venez de créer.

Usage:
    python extract_desk_custom_fields.py
"""
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from src.zoho_client import ZohoDeskClient
from config import settings

# Charger .env
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

OUTPUT_FILE = "desk_custom_fields_reference.json"


def extract_ticket_fields():
    """Extrait tous les champs personnalisés disponibles pour les tickets Desk."""
    print("\n" + "=" * 80)
    print("EXTRACTION DES CHAMPS PERSONNALISÉS - ZOHO DESK")
    print("=" * 80)

    desk_client = ZohoDeskClient()

    try:
        # Récupérer les départements
        print("\n🔍 Récupération des départements...")
        departments_url = f"{settings.zoho_desk_api_url}/departments"
        departments_params = {"orgId": settings.zoho_desk_org_id}
        departments_response = desk_client._make_request("GET", departments_url, params=departments_params)
        departments = departments_response.get("data", [])
        print(f"✅ {len(departments)} départements trouvés")

        all_fields = {}

        # Pour chaque département, récupérer les champs
        for dept in departments:
            dept_id = dept.get("id")
            dept_name = dept.get("name")

            print(f"\n📋 Département: {dept_name} (ID: {dept_id})")

            # Récupérer les champs du département
            layouts_url = f"{settings.zoho_desk_api_url}/departments/{dept_id}/layouts"
            layouts_params = {"orgId": settings.zoho_desk_org_id}

            try:
                layouts_response = desk_client._make_request("GET", layouts_url, params=layouts_params)
                layouts = layouts_response.get("data", [])

                for layout in layouts:
                    layout_id = layout.get("id")
                    layout_name = layout.get("name", "Default")

                    print(f"   Layout: {layout_name}")

                    # Récupérer les champs du layout
                    fields_url = f"{settings.zoho_desk_api_url}/departments/{dept_id}/layouts/{layout_id}/fields"
                    fields_params = {"orgId": settings.zoho_desk_org_id}

                    fields_response = desk_client._make_request("GET", fields_url, params=fields_params)
                    fields = fields_response.get("data", [])

                    # Filtrer les champs personnalisés (cf_)
                    custom_fields = [f for f in fields if f.get("apiName", "").startswith("cf_")]

                    if custom_fields:
                        print(f"      Champs personnalisés trouvés: {len(custom_fields)}")

                        for field in custom_fields:
                            api_name = field.get("apiName")
                            field_label = field.get("displayLabel")
                            field_type = field.get("type")

                            if api_name not in all_fields:
                                all_fields[api_name] = {
                                    "apiName": api_name,
                                    "displayLabel": field_label,
                                    "type": field_type,
                                    "required": field.get("required", False),
                                    "maxLength": field.get("maxLength"),
                                    "departments": []
                                }

                            all_fields[api_name]["departments"].append({
                                "dept_id": dept_id,
                                "dept_name": dept_name,
                                "layout_id": layout_id,
                                "layout_name": layout_name
                            })

            except Exception as e:
                logger.error(f"Erreur lors de la récupération des champs pour {dept_name}: {e}")

        # Résumé
        print(f"\n📊 Résumé :")
        print(f"   - Total départements : {len(departments)}")
        print(f"   - Champs personnalisés uniques : {len(all_fields)}")

        # Afficher les champs personnalisés
        print(f"\n🔑 CHAMPS PERSONNALISÉS TROUVÉS :")
        for api_name, field_info in sorted(all_fields.items()):
            print(f"\n   📌 {api_name}")
            print(f"      Label: {field_info['displayLabel']}")
            print(f"      Type: {field_info['type']}")
            print(f"      Requis: {field_info['required']}")
            if field_info.get('maxLength'):
                print(f"      Max Length: {field_info['maxLength']}")
            print(f"      Départements: {', '.join([d['dept_name'] for d in field_info['departments']])}")

        # Rechercher spécifiquement "opportunite" ou "opportunité"
        print(f"\n🔍 Recherche du champ 'Opportunité'...")
        opportunite_fields = [
            (name, info) for name, info in all_fields.items()
            if "opportunit" in name.lower() or "opportunit" in info['displayLabel'].lower()
        ]

        if opportunite_fields:
            print(f"   ✅ Trouvé {len(opportunite_fields)} champ(s) correspondant:")
            for api_name, info in opportunite_fields:
                print(f"\n      🎯 {api_name}")
                print(f"         Label: {info['displayLabel']}")
                print(f"         Type: {info['type']}")
        else:
            print(f"   ⚠️  Aucun champ contenant 'opportunit' trouvé")
            print(f"   💡 Vérifiez que le champ a bien été créé dans Zoho Desk")

        # Sauvegarder le résultat complet
        output = {
            "timestamp": datetime.now().isoformat(),
            "org_id": settings.zoho_desk_org_id,
            "api_url": settings.zoho_desk_api_url,
            "summary": {
                "total_departments": len(departments),
                "custom_fields_count": len(all_fields)
            },
            "departments": [{"id": d.get("id"), "name": d.get("name")} for d in departments],
            "custom_fields": all_fields
        }

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Référence complète sauvegardée dans : {OUTPUT_FILE}")

        return output

    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        desk_client.close()


def main():
    """Point d'entrée principal."""
    result = extract_ticket_fields()

    if result:
        print("\n" + "=" * 80)
        print("PROCHAINES ÉTAPES")
        print("=" * 80)
        print("\n1. Vérifiez desk_custom_fields_reference.json")
        print("\n2. Identifiez le nom exact du champ 'Opportunité':")
        print("   - Cherchez dans la sortie ci-dessus")
        print("   - Le nom sera du type 'cf_opportunite' ou 'cf_opportunité'")
        print("\n3. Si le champ est trouvé, il sera automatiquement utilisé par DealLinkingAgent")
        print("\n4. Si le nom est différent de 'cf_opportunite', modifiez:")
        print("   src/agents/deal_linking_agent.py ligne ~440")
        print("   Changez: 'cf_opportunite' → '<nom_exact_du_champ>'")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
