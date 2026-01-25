"""
Script pour extraire tous les modules Zoho CRM et leurs champs API.

Ce script récupère:
- La liste de tous les modules CRM
- Pour chaque module: tous les champs avec leurs noms API, types, labels, etc.
- Sauvegarde le schéma dans crm_schema.json

Usage:
    python extract_crm_schema.py
    python extract_crm_schema.py --output custom_schema.json
"""
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Ajouter le projet au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def extract_crm_schema(output_file: str = "crm_schema.json") -> Dict[str, Any]:
    """
    Extrait tous les modules CRM et leurs champs.

    Args:
        output_file: Nom du fichier JSON de sortie

    Returns:
        Dict contenant tous les modules et leurs champs
    """
    from src.zoho_client import ZohoCRMClient
    from config import settings

    print("\n" + "=" * 80)
    print("📦 EXTRACTION DU SCHÉMA ZOHO CRM")
    print("=" * 80)

    crm_client = ZohoCRMClient()
    schema = {
        "extraction_date": None,
        "modules": {}
    }

    try:
        # 1. Récupérer la liste de tous les modules
        print("\n🔍 Récupération de la liste des modules...")
        url = f"{settings.zoho_crm_api_url}/settings/modules"
        modules_response = crm_client._make_request(
            method="GET",
            url=url
        )

        if not modules_response or "modules" not in modules_response:
            logger.error("❌ Impossible de récupérer la liste des modules")
            return schema

        modules_list = modules_response["modules"]
        print(f"✅ {len(modules_list)} modules trouvés\n")

        # 2. Pour chaque module, récupérer les champs
        for idx, module in enumerate(modules_list, 1):
            module_name = module.get("api_name")
            module_label = module.get("plural_label")

            # Ignorer les modules système non pertinents
            if module.get("generated_type") == "default" and not module.get("api_supported"):
                continue

            print(f"[{idx}/{len(modules_list)}] 📋 {module_label} ({module_name})...")

            try:
                # Récupérer les champs du module
                url = f"{settings.zoho_crm_api_url}/settings/fields"
                fields_response = crm_client._make_request(
                    method="GET",
                    url=url,
                    params={"module": module_name}
                )

                if not fields_response or "fields" not in fields_response:
                    logger.warning(f"   ⚠️  Pas de champs pour {module_name}")
                    continue

                fields_list = fields_response["fields"]

                # Extraire les informations pertinentes de chaque champ
                module_fields = []
                for field in fields_list:
                    field_info = {
                        "api_name": field.get("api_name"),
                        "field_label": field.get("field_label"),
                        "data_type": field.get("data_type"),
                        "length": field.get("length"),
                        "required": field.get("required", False),
                        "read_only": field.get("read_only", False),
                        "custom_field": field.get("custom_field", False),
                        "visible": field.get("visible", True),
                    }

                    # Ajouter les options pour les picklists
                    if field.get("data_type") in ["picklist", "multiselectpicklist"]:
                        pick_list_values = field.get("pick_list_values", [])
                        field_info["pick_list_values"] = [
                            {
                                "display_value": v.get("display_value"),
                                "actual_value": v.get("actual_value")
                            }
                            for v in pick_list_values
                        ]

                    # Ajouter les infos de lookup
                    if field.get("data_type") == "lookup":
                        field_info["lookup_module"] = field.get("lookup", {}).get("module", {}).get("api_name")

                    module_fields.append(field_info)

                # Stocker les informations du module
                schema["modules"][module_name] = {
                    "module_label": module_label,
                    "singular_label": module.get("singular_label"),
                    "api_supported": module.get("api_supported", True),
                    "creatable": module.get("creatable", False),
                    "editable": module.get("editable", False),
                    "deletable": module.get("deletable", False),
                    "viewable": module.get("viewable", True),
                    "fields_count": len(module_fields),
                    "fields": module_fields
                }

                print(f"   ✅ {len(module_fields)} champs extraits")

            except Exception as e:
                logger.error(f"   ❌ Erreur pour {module_name}: {e}")
                continue

        # 3. Ajouter la date d'extraction
        from datetime import datetime
        schema["extraction_date"] = datetime.now().isoformat()

        # 4. Sauvegarder le schéma
        output_path = project_root / output_file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 80)
        print("✅ EXTRACTION TERMINÉE")
        print("=" * 80)
        print(f"📁 Fichier sauvegardé: {output_path}")
        print(f"📊 Modules extraits: {len(schema['modules'])}")

        total_fields = sum(m["fields_count"] for m in schema["modules"].values())
        print(f"📋 Champs totaux: {total_fields}")

        # Afficher un résumé des modules principaux
        print("\n📦 Modules principaux:")
        main_modules = ["Deals", "Contacts", "Accounts", "Leads", "Products"]
        for mod_name in main_modules:
            if mod_name in schema["modules"]:
                mod = schema["modules"][mod_name]
                print(f"   - {mod['module_label']}: {mod['fields_count']} champs")

        print("\n" + "=" * 80)

        return schema

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'extraction: {e}")
        import traceback
        traceback.print_exc()
        return schema

    finally:
        try:
            crm_client.close()
        except:
            pass


def search_field(schema_file: str, search_term: str):
    """
    Recherche un champ dans le schéma.

    Args:
        schema_file: Chemin du fichier schéma
        search_term: Terme à rechercher (insensible à la casse)
    """
    schema_path = Path(schema_file)

    if not schema_path.exists():
        print(f"❌ Fichier {schema_file} introuvable")
        print("💡 Exécutez d'abord: python extract_crm_schema.py")
        return

    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)

    print(f"\n🔍 Recherche de '{search_term}' dans le schéma CRM...")
    print("=" * 80)

    search_lower = search_term.lower()
    results = []

    for module_name, module_data in schema["modules"].items():
        for field in module_data["fields"]:
            api_name = field.get("api_name", "")
            field_label = field.get("field_label", "")

            if search_lower in api_name.lower() or search_lower in field_label.lower():
                results.append({
                    "module": module_name,
                    "module_label": module_data["module_label"],
                    "field": field
                })

    if not results:
        print(f"❌ Aucun champ trouvé pour '{search_term}'")
        return

    print(f"✅ {len(results)} résultat(s) trouvé(s):\n")

    for result in results:
        field = result["field"]
        print(f"📦 Module: {result['module_label']} ({result['module']})")
        print(f"   API Name: {field['api_name']}")
        print(f"   Label: {field['field_label']}")
        print(f"   Type: {field['data_type']}")
        print(f"   Required: {field['required']}")
        print(f"   Custom: {field['custom_field']}")
        if field.get("pick_list_values"):
            print(f"   Options: {len(field['pick_list_values'])} valeurs")
        print()


def list_module_fields(schema_file: str, module_name: str):
    """
    Liste tous les champs d'un module.

    Args:
        schema_file: Chemin du fichier schéma
        module_name: Nom API du module
    """
    schema_path = Path(schema_file)

    if not schema_path.exists():
        print(f"❌ Fichier {schema_file} introuvable")
        print("💡 Exécutez d'abord: python extract_crm_schema.py")
        return

    with open(schema_path, 'r', encoding='utf-8') as f:
        schema = json.load(f)

    if module_name not in schema["modules"]:
        print(f"❌ Module '{module_name}' introuvable")
        print(f"💡 Modules disponibles: {', '.join(schema['modules'].keys())}")
        return

    module_data = schema["modules"][module_name]

    print(f"\n📦 Module: {module_data['module_label']} ({module_name})")
    print("=" * 80)
    print(f"Champs: {module_data['fields_count']}")
    print(f"Creatable: {module_data['creatable']}")
    print(f"Editable: {module_data['editable']}")
    print("\n📋 Champs:\n")

    for field in module_data["fields"]:
        required = "⚠️ " if field["required"] else "   "
        custom = "🔧" if field["custom_field"] else "  "
        print(f"{required}{custom} {field['api_name']:<40} ({field['data_type']:<15}) - {field['field_label']}")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Extraction du schéma Zoho CRM")
    parser.add_argument(
        "--output",
        default="crm_schema.json",
        help="Fichier de sortie (default: crm_schema.json)"
    )
    parser.add_argument(
        "--search",
        help="Rechercher un champ dans le schéma existant"
    )
    parser.add_argument(
        "--module",
        help="Lister tous les champs d'un module"
    )

    args = parser.parse_args()

    # Mode recherche
    if args.search:
        search_field(args.output, args.search)
        return

    # Mode liste module
    if args.module:
        list_module_fields(args.output, args.module)
        return

    # Mode extraction
    schema = extract_crm_schema(args.output)

    if schema and schema["modules"]:
        print("\n💡 Exemples d'utilisation:")
        print(f"   # Rechercher un champ:")
        print(f"   python extract_crm_schema.py --search 'Date_examen'")
        print(f"   # Lister les champs d'un module:")
        print(f"   python extract_crm_schema.py --module Deals")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
