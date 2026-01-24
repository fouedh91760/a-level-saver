"""
Script pour extraire TOUS les champs disponibles sur les deals CRM Zoho.

Ce script récupère :
1. Liste complète des champs disponibles
2. Valeurs possibles pour les champs picklist (Stage, EVALBOX, etc.)
3. Types de champs
4. Métadonnées complètes

Résultat sauvegardé dans : crm_deal_fields_reference.json

Usage:
    python extract_crm_deal_fields.py
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

OUTPUT_FILE = "crm_deal_fields_reference.json"


def extract_deal_fields():
    """Extrait tous les champs disponibles pour les deals CRM."""
    print("\n" + "=" * 80)
    print("EXTRACTION DES CHAMPS CRM - DEALS")
    print("=" * 80)

    crm_client = ZohoCRMClient()

    try:
        # Récupérer les métadonnées des champs
        print("\n🔍 Récupération des champs via API metadata...")
        url = f"{settings.zoho_crm_api_url}/settings/fields?module=Deals"

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

        # Afficher les champs picklist importants
        print(f"\n🔑 Champs PICKLIST importants :")
        important_picklists = ["Stage", "EVALBOX", "Lead_Source", "Type"]

        for field_name in important_picklists:
            if field_name in picklist_fields:
                info = picklist_fields[field_name]
                print(f"\n   📋 {field_name} ({info['label']}) :")
                for value in info['values']:
                    print(f"      - {value}")
            else:
                # Chercher dans les custom fields avec pattern
                found = False
                for fname, finfo in all_fields.items():
                    if field_name.lower() in fname.lower() and finfo.get("picklist_values"):
                        print(f"\n   📋 {fname} ({finfo['label']}) :")
                        for value in finfo['picklist_values']:
                            print(f"      - {value}")
                        found = True
                        break

                if not found:
                    print(f"\n   ⚠️  {field_name} : Non trouvé (peut être un champ custom)")

        # Chercher spécifiquement EVALBOX
        print(f"\n🔍 Recherche du champ EVALBOX dans tous les champs...")
        evalbox_found = False
        for fname, finfo in all_fields.items():
            if "evalbox" in fname.lower() or "eval" in fname.lower():
                print(f"   ✅ Trouvé : {fname} ({finfo['label']})")
                print(f"      Type : {finfo['data_type']}")
                if finfo.get("picklist_values"):
                    print(f"      Valeurs :")
                    for val in finfo['picklist_values']:
                        print(f"         - {val}")
                evalbox_found = True

        if not evalbox_found:
            print(f"   ⚠️  Aucun champ contenant 'evalbox' ou 'eval' trouvé")

        # Sauvegarder le résultat complet
        output = {
            "timestamp": datetime.now().isoformat(),
            "module": "Deals",
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
        for fname in sorted(custom_fields.keys()):
            finfo = custom_fields[fname]
            print(f"   - {fname} ({finfo['label']}) : {finfo['data_type']}")

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
    result = extract_deal_fields()

    if result:
        print("\n" + "=" * 80)
        print("PROCHAINES ÉTAPES")
        print("=" * 80)
        print("\n1. Examinez crm_deal_fields_reference.json")
        print("\n2. Identifiez les valeurs exactes pour :")
        print("   - Stage (Closed Won, Pending, etc.)")
        print("   - EVALBOX (REFUS CMA, Documents refusés, etc.)")
        print("\n3. Commitez le fichier :")
        print("   git add crm_deal_fields_reference.json")
        print("   git commit -m 'Add CRM deal fields reference'")
        print("   git push")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
