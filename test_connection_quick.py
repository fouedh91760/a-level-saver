"""
Test rapide de connexion Zoho Desk et CRM.
"""
import logging
from dotenv import load_dotenv
from src.zoho_client import ZohoDeskClient, ZohoCRMClient

# Charger .env
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_desk_connection():
    """Test connexion Zoho Desk."""
    print("\n" + "=" * 60)
    print("TEST CONNEXION ZOHO DESK")
    print("=" * 60)

    try:
        desk_client = ZohoDeskClient()
        tickets = desk_client.list_tickets(limit=3)

        if tickets.get("data"):
            print("\n✅ CONNEXION ZOHO DESK : OK")
            print(f"   Tickets récupérés : {len(tickets['data'])}")
            for ticket in tickets["data"][:3]:
                print(f"   - Ticket {ticket.get('id')}: {ticket.get('subject')[:50]}...")
            return True
        else:
            print("\n❌ CONNEXION ZOHO DESK : Aucun ticket trouvé")
            return False

    except Exception as e:
        print(f"\n❌ ERREUR ZOHO DESK : {e}")
        return False
    finally:
        desk_client.close()


def test_crm_connection():
    """Test connexion Zoho CRM."""
    print("\n" + "=" * 60)
    print("TEST CONNEXION ZOHO CRM")
    print("=" * 60)

    try:
        crm_client = ZohoCRMClient()

        # Essayer de chercher des deals
        # Utiliser un critère générique qui devrait retourner quelque chose
        result = crm_client.search_deals(
            criteria="(Stage:equals:Qualification)",
            per_page=3
        )

        if result.get("data"):
            print("\n✅ CONNEXION ZOHO CRM : OK")
            print(f"   Deals trouvés : {len(result['data'])}")
            for deal in result["data"][:3]:
                print(f"   - Deal {deal.get('id')}: {deal.get('Deal_Name', 'N/A')}")
            return True
        else:
            # Peut-être qu'il n'y a pas de deals en Qualification
            # Essayons juste de vérifier que l'API répond
            print("\n✅ CONNEXION ZOHO CRM : OK (API répond)")
            print("   Note : Aucun deal trouvé avec le critère de test")
            return True

    except Exception as e:
        print(f"\n❌ ERREUR ZOHO CRM : {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        crm_client.close()


def main():
    """Test principal."""
    print("\n" + "=" * 60)
    print("TEST RAPIDE DE CONNEXION ZOHO")
    print("=" * 60)

    desk_ok = test_desk_connection()
    crm_ok = test_crm_connection()

    print("\n" + "=" * 60)
    print("RÉSUMÉ")
    print("=" * 60)

    if desk_ok and crm_ok:
        print("\n🎉 Tous les tests sont passés !")
        print("\nVous pouvez maintenant exécuter :")
        print("  python test_with_real_tickets.py")
    elif desk_ok:
        print("\n⚠️  Zoho Desk : OK")
        print("❌ Zoho CRM : ERREUR")
        print("\nVérifiez vos credentials CRM dans .env :")
        print("  - ZOHO_CRM_CLIENT_ID")
        print("  - ZOHO_CRM_CLIENT_SECRET")
        print("  - ZOHO_CRM_REFRESH_TOKEN")
    elif crm_ok:
        print("\n⚠️  Zoho CRM : OK")
        print("❌ Zoho Desk : ERREUR")
        print("\nVérifiez vos credentials Desk dans .env :")
        print("  - ZOHO_CLIENT_ID")
        print("  - ZOHO_CLIENT_SECRET")
        print("  - ZOHO_REFRESH_TOKEN")
        print("  - ZOHO_DESK_ORG_ID")
    else:
        print("\n❌ Les deux connexions ont échoué")
        print("\nVérifiez :")
        print("  1. Que le fichier .env existe")
        print("  2. Que toutes les credentials sont correctes")
        print("  3. Que ZOHO_DATACENTER est correct (com, eu, in, ou com.au)")
        print("  4. Que les refresh tokens sont valides")


if __name__ == "__main__":
    main()
