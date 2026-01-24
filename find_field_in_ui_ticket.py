"""
Script pour trouver le nom API exact du champ "Opportunité".

INSTRUCTIONS:
1. Va dans Zoho Desk UI
2. Ouvre un ticket
3. Remplis manuellement le champ "Opportunité" avec n'importe quelle valeur (ex: "test")
4. Note l'ID du ticket
5. Lance ce script avec cet ID

Usage:
    python find_field_in_ui_ticket.py <ticket_id>

Example:
    python find_field_in_ui_ticket.py 198709000438366101
"""
import sys
import json
from dotenv import load_dotenv
from src.zoho_client import ZohoDeskClient

load_dotenv()


def find_custom_fields(ticket_id: str):
    """Récupère tous les champs d'un ticket pour trouver le champ Opportunité."""
    print("\n" + "=" * 80)
    print(f"RECHERCHE DES CHAMPS PERSONNALISÉS - TICKET {ticket_id}")
    print("=" * 80)

    desk_client = ZohoDeskClient()

    try:
        print(f"\n🔍 Récupération du ticket {ticket_id}...")
        ticket = desk_client.get_ticket(ticket_id)

        print(f"\n✅ Ticket récupéré")
        print(f"   Sujet: {ticket.get('subject', 'N/A')}")
        print(f"   Département: {ticket.get('departmentId', 'N/A')}")

        # Tous les champs
        print(f"\n📋 TOUS LES CHAMPS DU TICKET :")
        print("-" * 80)

        all_fields = {}
        custom_fields = {}

        for key, value in sorted(ticket.items()):
            all_fields[key] = value

            # Afficher tous les champs
            value_str = str(value)[:100] if value else "None"
            print(f"   {key:30} = {value_str}")

            # Identifier les champs personnalisés
            if key.startswith("cf_"):
                custom_fields[key] = value
                print(f"      ⭐ CHAMP PERSONNALISÉ TROUVÉ!")

        # Résumé
        print(f"\n" + "=" * 80)
        print(f"📊 RÉSUMÉ:")
        print(f"   Total champs: {len(all_fields)}")
        print(f"   Champs personnalisés (cf_*): {len(custom_fields)}")

        if custom_fields:
            print(f"\n✅ CHAMPS PERSONNALISÉS TROUVÉS:")
            for field_name, value in custom_fields.items():
                print(f"\n   🎯 {field_name}")
                print(f"      Valeur actuelle: {value}")
                print(f"\n   💡 Utilise ce nom dans deal_linking_agent.py:")
                print(f"      update_data = {{'{field_name}': deal_url}}")
        else:
            print(f"\n⚠️  AUCUN CHAMP PERSONNALISÉ TROUVÉ")
            print(f"\n   Cela signifie que:")
            print(f"   1. Le champ 'Opportunité' n'est PAS encore rempli dans ce ticket")
            print(f"   2. Ou le champ n'existe pas pour ce département")
            print(f"\n   💡 SOLUTION:")
            print(f"   1. Va dans Zoho Desk UI")
            print(f"   2. Ouvre ce ticket: {ticket_id}")
            print(f"   3. Remplis manuellement le champ 'Opportunité' avec 'test'")
            print(f"   4. Sauvegarde le ticket")
            print(f"   5. Relance ce script")

        # Sauvegarder tout
        output_file = f"ticket_{ticket_id}_all_fields.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "ticket_id": ticket_id,
                "subject": ticket.get("subject"),
                "departmentId": ticket.get("departmentId"),
                "all_fields": all_fields,
                "custom_fields": custom_fields
            }, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Tous les champs sauvegardés dans: {output_file}")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

    finally:
        desk_client.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ Veuillez fournir un ticket ID")
        sys.exit(1)

    ticket_id = sys.argv[1]
    find_custom_fields(ticket_id)


if __name__ == "__main__":
    main()
