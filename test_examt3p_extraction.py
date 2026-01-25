#!/usr/bin/env python3
"""
Script de test pour l'extraction ExamT3P via Playwright.

Usage:
    python test_examt3p_extraction.py <identifiant> <password>

Exemple:
    python test_examt3p_extraction.py candidat@email.com MonMotDePasse123
"""
import sys
import json
from datetime import datetime


def test_extraction(identifiant: str, password: str):
    """
    Teste l'extraction des données ExamT3P.

    Args:
        identifiant: Email du candidat
        password: Mot de passe ExamT3P
    """
    print("=" * 80)
    print("TEST EXTRACTION EXAMT3P")
    print("=" * 80)
    print(f"Date/Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Identifiant: {identifiant}")
    print(f"Password: {'*' * len(password)}")
    print("=" * 80)

    # Import du module
    print("\n1. Import du module exament3p_playwright...")
    try:
        from src.utils.exament3p_playwright import extract_exament3p_sync
        print("   ✅ Module importé avec succès")
    except ImportError as e:
        print(f"   ❌ Erreur d'import: {e}")
        return None

    # Extraction
    print("\n2. Lancement de l'extraction...")
    print("   (Cela peut prendre 30-60 secondes...)")
    print("-" * 40)

    try:
        data = extract_exament3p_sync(identifiant, password, max_retries=2)
        print("-" * 40)
        print("   ✅ Extraction terminée")
    except Exception as e:
        print(f"   ❌ Erreur d'extraction: {e}")
        import traceback
        traceback.print_exc()
        return None

    # Analyse du résultat
    print("\n3. Analyse du résultat:")
    print("=" * 80)

    if data.get('extraction_requise', True):
        print("   ⚠️ EXTRACTION INCOMPLÈTE")
        if data.get('error'):
            print(f"   Erreur: {data['error']}")
        if data.get('errors'):
            print("   Erreurs détaillées:")
            for err in data['errors']:
                print(f"     - {err}")
    else:
        print("   ✅ EXTRACTION RÉUSSIE")

    # Informations principales
    print("\n" + "=" * 80)
    print("DONNÉES EXTRAITES")
    print("=" * 80)

    sections = [
        ("CANDIDAT", [
            ('Nom', 'nom_candidat'),
            ('N° Dossier', 'num_dossier'),
            ('Type examen', 'type_examen'),
            ('Département', 'departement'),
        ]),
        ("DOSSIER", [
            ('Statut dossier', 'statut_dossier'),
            ('Date examen', 'date_examen'),
            ('Convocation', 'convocation'),
            ('Documents', 'statut_documents'),
            ('Documents validés', 'documents_valides'),
        ]),
        ("PROGRESSION", [
            ('Progression', 'progression'),
        ]),
        ("ACTIONS REQUISES", [
            ('Actions', 'actions_requises'),
            ('Documents refusés', 'documents_refuses'),
            ('Action candidat requise', 'action_candidat_requise'),
        ]),
    ]

    for section_name, fields in sections:
        print(f"\n📋 {section_name}:")
        for label, key in fields:
            value = data.get(key, 'N/A')
            if isinstance(value, dict):
                print(f"   {label}:")
                for k, v in value.items():
                    print(f"      - {k}: {v}")
            elif isinstance(value, list):
                print(f"   {label}:")
                if value:
                    for item in value:
                        if isinstance(item, dict):
                            print(f"      - {item}")
                        else:
                            print(f"      - {item}")
                else:
                    print("      (aucun)")
            else:
                print(f"   {label}: {value}")

    # Documents détaillés
    if data.get('documents'):
        print(f"\n📄 DÉTAIL DOCUMENTS:")
        for doc in data['documents']:
            statut = doc.get('statut', 'INCONNU')
            emoji = '✅' if statut == 'VALIDÉ' else ('❌' if statut == 'REFUSÉ' else '⏳')
            print(f"   {emoji} {doc.get('nom', 'N/A')}: {statut}")

    # Paiement
    if data.get('paiement_cma'):
        print(f"\n💳 PAIEMENT CMA:")
        paiement = data['paiement_cma']
        print(f"   Montant: {paiement.get('montant', 'N/A')}€")
        print(f"   Statut: {paiement.get('statut', 'N/A')}")
        print(f"   Date: {paiement.get('date', 'N/A')}")

    # Examens
    if data.get('examens'):
        print(f"\n📅 EXAMENS:")
        examens = data['examens']
        print(f"   Date: {examens.get('date', 'N/A')}")
        print(f"   Lieu: {examens.get('lieu', 'N/A')}")
        print(f"   Convocation dispo: {examens.get('convocation_disponible', 'N/A')}")

    # Compte
    if data.get('compte'):
        print(f"\n👤 COMPTE:")
        compte = data['compte']
        for k, v in compte.items():
            print(f"   {k}: {v}")

    # Erreurs
    if data.get('errors'):
        print(f"\n⚠️ ERREURS RENCONTRÉES:")
        for err in data['errors']:
            print(f"   - {err}")

    # Sauvegarde JSON
    print("\n" + "=" * 80)
    output_file = f"examt3p_extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"💾 Données sauvegardées dans: {output_file}")
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde JSON: {e}")

    print("=" * 80)
    print("FIN DU TEST")
    print("=" * 80)

    return data


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python test_examt3p_extraction.py <identifiant> <password>")
        print("")
        print("Exemple:")
        print("  python test_examt3p_extraction.py candidat@email.com MonMotDePasse123")
        sys.exit(1)

    identifiant = sys.argv[1]
    password = sys.argv[2]

    test_extraction(identifiant, password)
