"""
Script de test pour le workflow complet de gestion des identifiants ExamT3P.

Tests :
1. Extraction des identifiants depuis les threads
2. Test de connexion
3. Workflow complet avec mise à jour CRM

Usage:
    python test_credentials_workflow.py
"""
import sys
from pathlib import Path

# Ajouter le projet au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.examt3p_credentials_helper import (
    extract_credentials_from_threads,
    test_examt3p_connection,
    get_credentials_with_validation
)


def test_extract_credentials_from_threads():
    """Test d'extraction des identifiants depuis les threads."""
    print("\n" + "=" * 80)
    print("TEST 1: EXTRACTION DES IDENTIFIANTS DEPUIS LES THREADS")
    print("=" * 80)

    # Simuler des threads avec identifiants
    test_threads = [
        {
            'direction': 'in',
            'plainText': """Bonjour,

Voici mes identifiants pour ExamenT3P :
Identifiant: test@example.com
Mot de passe: MonMotDePasse123

Merci de vérifier mon dossier.
"""
        },
        {
            'direction': 'out',
            'plainText': 'Merci pour votre message'
        }
    ]

    result = extract_credentials_from_threads(test_threads)

    if result:
        print(f"\n✅ Identifiants extraits avec succès:")
        print(f"   - Identifiant: {result['identifiant']}")
        print(f"   - Mot de passe: {'*' * len(result['mot_de_passe'])}")
        print(f"   - Source: {result['source']}")
        return True
    else:
        print("\n❌ Échec de l'extraction des identifiants")
        return False


def test_extract_credentials_various_formats():
    """Test avec différents formats d'identifiants."""
    print("\n" + "=" * 80)
    print("TEST 2: EXTRACTION AVEC DIFFÉRENTS FORMATS")
    print("=" * 80)

    test_cases = [
        {
            'name': 'Format avec "login" et "pass"',
            'thread': {
                'direction': 'in',
                'plainText': 'Login : user@test.fr\nPass : password123'
            },
            'expected': True
        },
        {
            'name': 'Format avec "email" et "mdp"',
            'thread': {
                'direction': 'in',
                'plainText': 'Email: contact@example.com\nMDP: mdp456'
            },
            'expected': True
        },
        {
            'name': 'Format incomplet (seulement email)',
            'thread': {
                'direction': 'in',
                'plainText': 'Mon email est: user@test.com'
            },
            'expected': False
        }
    ]

    success_count = 0
    for test_case in test_cases:
        print(f"\n📝 {test_case['name']}...")
        result = extract_credentials_from_threads([test_case['thread']])

        if (result is not None) == test_case['expected']:
            print(f"   ✅ Résultat attendu")
            success_count += 1
        else:
            print(f"   ❌ Résultat inattendu")

    print(f"\n📊 Résultat: {success_count}/{len(test_cases)} tests réussis")
    return success_count == len(test_cases)


def test_connection_mock():
    """Test du système de test de connexion (sans vraie connexion)."""
    print("\n" + "=" * 80)
    print("TEST 3: SYSTÈME DE TEST DE CONNEXION")
    print("=" * 80)

    print("\n⚠️  Note: Le test de connexion réel nécessite:")
    print("   - Un navigateur Chromium installé")
    print("   - Des identifiants valides ExamenT3P")
    print("   - Une connexion internet")
    print("\nCe test valide seulement que la fonction existe et peut être appelée.")

    # Vérifier que la fonction existe
    try:
        # Test avec des identifiants fictifs (va échouer mais c'est normal)
        success, error = test_examt3p_connection("test@example.com", "fakepassword")

        print(f"\n✅ Fonction de test de connexion opérationnelle")
        print(f"   - Résultat attendu: échec de connexion")
        print(f"   - Success: {success}")
        print(f"   - Error: {error}")

        # On s'attend à ce que ça échoue avec des faux identifiants
        if not success:
            print(f"\n✅ Comportement correct (échec avec faux identifiants)")
            return True
        else:
            print(f"\n⚠️  Résultat inattendu (succès avec faux identifiants)")
            return False

    except Exception as e:
        print(f"\n❌ Erreur lors de l'appel de la fonction: {e}")
        return False


def test_workflow_integration():
    """Test d'intégration du workflow complet."""
    print("\n" + "=" * 80)
    print("TEST 4: WORKFLOW COMPLET D'INTÉGRATION")
    print("=" * 80)

    # Simuler des données CRM et threads
    deal_data = {
        'Deal_Name': 'Test Deal',
        # Pas d'identifiants dans le CRM
    }

    threads = [
        {
            'direction': 'in',
            'plainText': """Bonjour,

Je vous envoie mes identifiants :
Identifiant: test@example.com
Mot de passe: TestPassword123

Cordialement
"""
        }
    ]

    print("\n📋 Configuration du test:")
    print("   - CRM: Pas d'identifiants")
    print("   - Threads: Identifiants présents")

    result = get_credentials_with_validation(
        deal_data=deal_data,
        threads=threads,
        crm_client=None,  # Pas de client CRM pour le test
        deal_id=None,
        auto_update_crm=False
    )

    print("\n📊 Résultat du workflow:")
    print(f"   - Identifiants trouvés: {result['credentials_found']}")
    print(f"   - Source: {result['credentials_source']}")
    print(f"   - Test de connexion: {result['connection_test_success']}")
    print(f"   - Réponse au candidat requise: {result['should_respond_to_candidate']}")

    if result['credentials_found'] and result['credentials_source'] == 'email_threads':
        print("\n✅ Workflow fonctionne correctement")
        print("   - Identifiants extraits des threads ✓")
        return True
    else:
        print("\n❌ Workflow ne fonctionne pas comme attendu")
        return False


def main():
    """Exécuter tous les tests."""
    print("\n" + "=" * 80)
    print("TEST COMPLET DU WORKFLOW DE GESTION DES IDENTIFIANTS EXAMT3P")
    print("=" * 80)

    tests = [
        ("Extraction depuis threads", test_extract_credentials_from_threads),
        ("Formats variés", test_extract_credentials_various_formats),
        ("Test de connexion", test_connection_mock),
        ("Workflow complet", test_workflow_integration)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Erreur lors de l'exécution du test '{name}': {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Résumé
    print("\n" + "=" * 80)
    print("RÉSUMÉ DES TESTS")
    print("=" * 80)

    success_count = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if result:
            success_count += 1

    print(f"\n📊 Total: {success_count}/{len(results)} tests réussis")

    if success_count == len(results):
        print("\n🎉 Tous les tests sont passés !")
        return 0
    else:
        print(f"\n⚠️  {len(results) - success_count} test(s) échoué(s)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
