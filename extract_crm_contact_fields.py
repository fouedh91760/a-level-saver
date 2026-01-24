"""
Script pour extraire TOUS les champs disponibles sur les contacts CRM Zoho.

Ce script récupère :
1. Liste complète des champs disponibles
2. Valeurs possibles pour les champs picklist
3. Types de champs
4. Métadonnées complètes

Résultat sauvegardé dans : crm_contact_fields_reference.json

Usage:
    python extract_crm_contact_fields.py
"""
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from src.zoho_client import ZohoCRMClient
from config import settings

# Charger .env
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

OUTPUT_FILE = "crm_contact_fields_reference.json"


def extract_contact_fields():
    """Extrait tous les champs disponibles pour les contacts CRM."""
    print("\n" + "=" * 80)
    print("EXTRACTION DES CHAMPS CRM - CONTACTS")
    print("=" * 80)

    crm_client = ZohoCRMClient()

    try:
        # Récupérer les métadonnées des champs
        print("\n🔍 Récupération des champs via API metadata...")
        url = f"{settings.zoho_crm_api_url}/settings/fields?module=Contacts"

        response = crm_client._make_request("GET", url, params={})
        fields_data = response.get("fields", [])

        print(f"✅ {len(fields_data)} champs récupérés")

        # Organiser les champs
        all_fields = {}
        picklist_fields = {}
        custom_fields = {}
        system_fields = {}

        for field in fields_data:
            field_name = field.get("api_name")
            field_label = field.get("field_label")
            field_type = field.get("data_type")
            is_custom = field.get("custom_field", False)

            field_info = {
                "label": field_label,
                "api_name": field_name,
                "data_type": field_type,
                "is_custom": is_custom,
                "is_required": field.get("required", False),
                "read_only": field.get("read_only", False),
                "length": field.get("length"),
                "decimal_place": field.get("decimal_place")
            }

            # Si c'est un picklist, récupérer les valeurs
            if field_type in ["picklist", "multiselectpicklist"]:
                pick_list_values = field.get("pick_list_values", [])
                values = [v.get("display_value") for v in pick_list_values]
                field_info["picklist_values"] = values
                picklist_fields[field_name] = {
                    "label": field_label,
                    "values": values
                }

            all_fields[field_name] = field_info

            # Séparer custom vs system
            if is_custom:
                custom_fields[field_name] = field_info
            else:
                system_fields[field_name] = field_info

        # Résumé
        print(f"\n📊 Résumé :")
        print(f"   - Total champs : {len(all_fields)}")
        print(f"   - Champs système : {len(system_fields)}")
        print(f"   - Champs custom : {len(custom_fields)}")
        print(f"   - Champs picklist : {len(picklist_fields)}")

        # Afficher les champs importants pour les candidats
        print(f"\n🔑 Champs importants pour les candidats :")
        important_fields = [
            "First_Name", "Last_Name", "Full_Name", "Email",
            "Phone", "Mobile", "Date_of_Birth", "Mailing_Street",
            "Mailing_City", "Mailing_Zip", "Mailing_State"
        ]

        for field_name in important_fields:
            if field_name in all_fields:
                info = all_fields[field_name]
                print(f"   ✅ {field_name} ({info['label']}) : {info['data_type']}")
            else:
                print(f"   ⚠️  {field_name} : Non trouvé")

        # Chercher les champs custom importants
        print(f"\n🔍 Champs custom contenant 'candidat', 'exam', 'formation'...")
        for fname, finfo in custom_fields.items():
            fname_lower = fname.lower()
            label_lower = finfo['label'].lower() if finfo['label'] else ''
            if any(keyword in fname_lower or keyword in label_lower
                   for keyword in ['candidat', 'exam', 'formation', 'inscription', 'convoc']):
                print(f"   📋 {fname} ({finfo['label']}) : {finfo['data_type']}")
                if finfo.get('picklist_values'):
                    for val in finfo['picklist_values'][:5]:  # Show first 5 values
                        print(f"      - {val}")
                    if len(finfo['picklist_values']) > 5:
                        print(f"      ... et {len(finfo['picklist_values']) - 5} autres valeurs")

        # Sauvegarder le résultat complet
        output = {
            "timestamp": datetime.now().isoformat(),
            "module": "Contacts",
            "api_url": settings.zoho_crm_api_url,
            "summary": {
                "total_fields": len(all_fields),
                "system_fields": len(system_fields),
                "custom_fields": len(custom_fields),
                "picklist_fields": len(picklist_fields)
            },
            "all_fields": all_fields,
            "picklist_fields_only": picklist_fields,
            "custom_fields_only": custom_fields,
            "system_fields_only": system_fields
        }

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Référence complète sauvegardée dans : {OUTPUT_FILE}")

        # Liste des champs custom pour référence rapide
        print(f"\n📝 Liste des champs CUSTOM (pour référence) :")
        for fname in sorted(custom_fields.keys())[:20]:  # Show first 20
            finfo = custom_fields[fname]
            print(f"   - {fname} ({finfo['label']}) : {finfo['data_type']}")

        if len(custom_fields) > 20:
            print(f"   ... et {len(custom_fields) - 20} autres champs custom")

        return output

    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        crm_client.close()


def main():
    """Point d'entrée principal."""
    result = extract_contact_fields()

    if result:
        print("\n" + "=" * 80)
        print("PROCHAINES ÉTAPES")
        print("=" * 80)
        print("\n1. Examinez crm_contact_fields_reference.json")
        print("\n2. Identifiez les champs nécessaires pour répondre aux tickets :")
        print("   - Informations candidat (nom, prénom, email, téléphone)")
        print("   - Date de naissance")
        print("   - Adresse")
        print("   - Informations formation/examen")
        print("\n3. Commitez le fichier :")
        print("   git add crm_contact_fields_reference.json")
        print("   git commit -m 'Add CRM contact fields reference'")
        print("   git push")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
