"""
Script de test pour ExamT3PAgent.

Usage:
    python test_examt3p_agent.py <username> <password> <dossier_number>

Exemple:
    python test_examt3p_agent.py "identifiant123" "motdepasse" "DOS123456"
"""
import sys
import json
from dotenv import load_dotenv
from src.agents.examt3p_agent import ExamT3PAgent

load_dotenv()


def test_examt3p_login(username: str, password: str, dossier_number: str, headless: bool = False):
    """
    Test de connexion et extraction de données.

    Args:
        username: IDENTIFIANT_EVALBOX
        password: MDP_EVALBOX
        dossier_number: NUM_DOSSIER_EVALBOX
        headless: Run in headless mode (False = voir le navigateur)
    """
    print("\n" + "=" * 80)
    print("TEST EXAMT3P AGENT")
    print("=" * 80)
    print(f"\nUsername: {username}")
    print(f"Dossier: {dossier_number}")
    print(f"Headless: {headless}")

    agent = ExamT3PAgent(headless=headless)

    try:
        # Test 1: Login
        print("\n" + "-" * 80)
        print("TEST 1: LOGIN")
        print("-" * 80)

        result = agent.process({
            "username": username,
            "password": password,
            "dossier_number": dossier_number
        })

        print("\n📊 RÉSULTAT:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result.get("success"):
            print("\n✅ LOGIN ET EXTRACTION RÉUSSIS")

            # Afficher les données extraites
            data = result.get("data", {})
            print("\n📋 DONNÉES EXTRAITES:")
            print(f"   - Convocations: {len(data.get('convocations', []))}")
            print(f"   - Résultats: {len(data.get('resultats', []))}")
            print(f"   - Statut: {data.get('statut_inscription', 'N/A')}")
            print(f"   - Documents: {len(data.get('documents', []))}")

        else:
            print("\n❌ ÉCHEC")
            print(f"   Erreur: {result.get('error')}")

        return result

    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Point d'entrée principal."""
    if len(sys.argv) < 4:
        print(__doc__)
        print("\n❌ Veuillez fournir username, password et dossier_number")
        print("\nExemple:")
        print('   python test_examt3p_agent.py "mon_identifiant" "mon_password" "DOS123"')
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    dossier_number = sys.argv[3]

    # Mode headless par défaut, ajouter --no-headless pour voir le navigateur
    headless = "--no-headless" not in sys.argv

    result = test_examt3p_login(username, password, dossier_number, headless)

    if result and result.get("success"):
        print("\n" + "=" * 80)
        print("PROCHAINES ÉTAPES")
        print("=" * 80)
        print("\n1. Les sélecteurs HTML dans examt3p_agent.py sont des PLACEHOLDERS")
        print("\n2. Vous devez les remplacer par les vrais sélecteurs:")
        print("   - Inspectez la page avec Chrome DevTools (F12)")
        print("   - Identifiez les input fields, buttons, etc.")
        print("   - Mettez à jour les méthodes login(), _get_convocations(), etc.")
        print("\n3. Relancez ce test jusqu'à ce que tout fonctionne")
        print("\n4. Une fois OK, intégrez dans le workflow de réponse aux tickets")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
