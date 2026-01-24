"""
Script pour lister tous les départements Zoho Desk.

Ce script récupère la liste complète des départements avec leurs IDs et noms
pour configurer correctement business_rules.py.
"""
import logging
from dotenv import load_dotenv
from src.zoho_client import ZohoDeskClient

# Charger .env
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def list_departments():
    """Liste tous les départements Zoho Desk."""
    print("\n" + "=" * 80)
    print("LISTE DES DÉPARTEMENTS ZOHO DESK")
    print("=" * 80)

    desk_client = ZohoDeskClient()

    try:
        # Récupérer TOUS les départements avec pagination automatique
        from config import settings
        url = f"{settings.zoho_desk_api_url}/departments"

        print("\n🔍 Récupération de TOUS les départements (avec pagination)...")

        # Utiliser la pagination automatique
        dept_list = desk_client._get_all_pages(
            url=url,
            params={"orgId": settings.zoho_desk_org_id},
            limit_per_page=100
        )

        if dept_list:
            print(f"\n✅ {len(dept_list)} département(s) trouvé(s) :\n")

            # Afficher sous forme de tableau
            print(f"{'ID':<20} | {'Nom':<30} | {'Description':<40}")
            print("-" * 95)

            for dept in dept_list:
                dept_id = dept.get("id", "N/A")
                dept_name = dept.get("name", "N/A")
                dept_desc = dept.get("description", "")[:37] + "..." if len(dept.get("description", "")) > 40 else dept.get("description", "")

                print(f"{dept_id:<20} | {dept_name:<30} | {dept_desc:<40}")

            # Générer un template pour business_rules.py
            print("\n" + "=" * 80)
            print("TEMPLATE POUR business_rules.py")
            print("=" * 80)
            print("\nCopiez-collez ce code dans get_department_routing_rules() :\n")

            print("return {")
            for dept in dept_list:
                dept_name = dept.get("name", "Unknown")
                print(f'    "{dept_name}": {{')
                print(f'        "keywords": [')
                print(f'            # Ajoutez ici les mots-clés pour {dept_name}')
                print(f'            # Exemple: "mot1", "mot2", "mot3"')
                print(f'        ],')
                print(f'        "contact_domains": []  # Domaines email si nécessaire')
                print(f'    }},')
            print("}")

            # Générer template pour deal linking
            print("\n" + "=" * 80)
            print("TEMPLATE POUR DEAL LINKING (get_deal_search_criteria_for_department)")
            print("=" * 80)
            print("\nExemple de structure :\n")

            for dept in dept_list[:3]:  # Montrer 3 exemples
                dept_name = dept.get("name", "Unknown")
                print(f'if department == "{dept_name}":')
                print(f'    return [')
                print(f'        {{')
                print(f'            "criteria": f"((Email:equals:{{contact_email}})and(...))",')
                print(f'            "description": "Description du critère",')
                print(f'            "max_results": 1,')
                print(f'            "sort_by": "Modified_Time",')
                print(f'            "sort_order": "desc"')
                print(f'        }}')
                print(f'    ]')
                print()

            return dept_list

        else:
            print("\n⚠️  Aucun département trouvé")
            print("Vérifiez vos permissions API")
            return []

    except Exception as e:
        print(f"\n❌ Erreur lors de la récupération : {e}")
        import traceback
        traceback.print_exc()
        return []

    finally:
        desk_client.close()


def main():
    """Point d'entrée principal."""
    departments = list_departments()

    if departments:
        print("\n" + "=" * 80)
        print("PROCHAINES ÉTAPES")
        print("=" * 80)
        print("\n1. Notez les noms de départements ci-dessus")
        print("2. Ouvrez business_rules.py")
        print("3. Modifiez get_department_routing_rules() avec vos départements")
        print("4. Ajoutez les mots-clés appropriés pour chaque département")
        print("5. Configurez get_deal_search_criteria_for_department() selon vos besoins")
        print("\n💡 Conseil : Commencez par configurer 1-2 départements principaux,")
        print("   puis ajoutez les autres progressivement.")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
