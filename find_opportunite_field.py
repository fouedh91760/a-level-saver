"""
Script simple pour trouver le champ personnalisé "Opportunité" dans un ticket.

Usage:
    python find_opportunite_field.py <ticket_id>

Example:
    python find_opportunite_field.py 123456789
"""
import sys
import json
from dotenv import load_dotenv
from src.zoho_client import ZohoDeskClient

load_dotenv()


def find_opportunite_field(ticket_id: str):
    """Récupère un ticket et affiche tous ses champs personnalisés."""
    print("\n" + "=" * 80)
    print(f"RECHERCHE DU CHAMP 'OPPORTUNITÉ' DANS LE TICKET {ticket_id}")
    print("=" * 80)

    desk_client = ZohoDeskClient()

    try:
        # Récupérer le ticket
        print(f"\n🔍 Récupération du ticket {ticket_id}...")
        ticket = desk_client.get_ticket(ticket_id)

        print(f"✅ Ticket récupéré : {ticket.get('subject', 'N/A')}")

        # Chercher tous les champs commençant par cf_
        print("\n📋 CHAMPS PERSONNALISÉS TROUVÉS :")

        custom_fields = {}
        for key, value in ticket.items():
            if key.startswith("cf_"):
                custom_fields[key] = value
                print(f"   {key} = {value}")

        if not custom_fields:
            print("   ⚠️  Aucun champ personnalisé trouvé dans ce ticket")
            print("   💡 Essayez avec un autre ticket ou créez d'abord le champ dans Zoho Desk")

        # Chercher spécifiquement "opportunit"
        print("\n🔍 RECHERCHE DU CHAMP 'OPPORTUNITÉ' :")
        opportunite_fields = [
            (name, value) for name, value in custom_fields.items()
            if "opportunit" in name.lower()
        ]

        if opportunite_fields:
            print(f"   ✅ TROUVÉ {len(opportunite_fields)} champ(s) !")
            for name, value in opportunite_fields:
                print(f"\n      🎯 Nom du champ : {name}")
                print(f"         Valeur actuelle : {value}")
                print(f"\n      ✅ Utilisez ce nom dans deal_linking_agent.py ligne 443:")
                print(f"         '{name}': deal_url")
        else:
            print("   ⚠️  Aucun champ contenant 'opportunit' trouvé")
            print("\n   💡 Vérifiez :")
            print("      1. Le champ a bien été créé dans Zoho Desk")
            print("      2. Le champ est activé pour ce département")
            print("      3. Essayez avec un ticket récent")

        # Sauvegarder tous les champs
        output_file = f"ticket_{ticket_id}_fields.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "ticket_id": ticket_id,
                "subject": ticket.get("subject"),
                "all_fields": ticket,
                "custom_fields_only": custom_fields
            }, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Tous les champs sauvegardés dans : {output_file}")

        return custom_fields

    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        desk_client.close()


def main():
    """Point d'entrée principal."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ Veuillez fournir un ticket ID")
        print("\nUsage: python find_opportunite_field.py <ticket_id>")
        sys.exit(1)

    ticket_id = sys.argv[1]
    result = find_opportunite_field(ticket_id)

    if result:
        print("\n" + "=" * 80)
        print("✅ SCRIPT TERMINÉ")
        print("=" * 80)
        print("\nSi le champ a été trouvé, notez son nom exact et mettez-le à jour dans :")
        print("src/agents/deal_linking_agent.py ligne 443")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
