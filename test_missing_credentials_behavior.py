"""
Test pour vérifier le nouveau comportement : ne pas demander les identifiants quand ils sont absents.
"""
import sys
from pathlib import Path

# Ajouter le projet au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.examt3p_credentials_helper import get_credentials_with_validation


def test_missing_credentials_no_request():
    """
    Test que quand les identifiants sont absents (ni CRM ni threads),
    on ne demande PAS au candidat de les fournir.
    """
    print("\n" + "=" * 80)
    print("TEST: IDENTIFIANTS ABSENTS - NE PAS DEMANDER AU CANDIDAT")
    print("=" * 80)

    # CRM sans identifiants
    deal_data = {
        'Deal_Name': 'Test Deal - Sans identifiants',
        # Pas de IDENTIFIANT_EVALBOX ni MDP_EVALBOX
    }

    # Threads sans identifiants
    threads = [
        {
            'direction': 'in',
            'plainText': 'Bonjour, je voudrais savoir où en est mon dossier.'
        },
        {
            'direction': 'out',
            'plainText': 'Merci pour votre message'
        }
    ]

    print("\n📋 Configuration du test:")
    print("   - CRM: Pas d'identifiants")
    print("   - Threads: Pas d'identifiants")
    print("\n🎯 Comportement attendu:")
    print("   - credentials_found = False")
    print("   - should_respond_to_candidate = False (NE PAS demander)")
    print("   - candidate_response_message = None")

    result = get_credentials_with_validation(
        deal_data=deal_data,
        threads=threads,
        crm_client=None,
        deal_id=None,
        auto_update_crm=False
    )

    print("\n📊 Résultat obtenu:")
    print(f"   - credentials_found: {result['credentials_found']}")
    print(f"   - should_respond_to_candidate: {result['should_respond_to_candidate']}")
    print(f"   - candidate_response_message: {result['candidate_response_message']}")

    # Vérifications
    success = True

    if result['credentials_found']:
        print("\n❌ ERREUR: credentials_found devrait être False")
        success = False

    if result['should_respond_to_candidate']:
        print("\n❌ ERREUR: should_respond_to_candidate devrait être False")
        print("   (On ne doit PAS demander les identifiants au candidat)")
        success = False

    if result['candidate_response_message'] is not None:
        print("\n❌ ERREUR: candidate_response_message devrait être None")
        success = False

    if success:
        print("\n✅ TEST RÉUSSI !")
        print("   Le système ne demande pas les identifiants au candidat")
        print("   (C'est nous qui allons créer le compte)")
        return True
    else:
        print("\n❌ TEST ÉCHOUÉ")
        return False


def test_invalid_credentials_with_reset_procedure():
    """
    Test que quand les identifiants sont présents mais invalides,
    on demande au candidat de réinitialiser via "Mot de passe oublié ?".
    """
    print("\n" + "=" * 80)
    print("TEST: IDENTIFIANTS INVALIDES - DEMANDER RÉINITIALISATION")
    print("=" * 80)

    # CRM avec identifiants
    deal_data = {
        'Deal_Name': 'Test Deal - Identifiants invalides',
        'IDENTIFIANT_EVALBOX': 'test@example.com',
        'MDP_EVALBOX': 'ancien_mot_de_passe'
    }

    # Threads vides
    threads = []

    print("\n📋 Configuration du test:")
    print("   - CRM: Identifiants présents")
    print("   - Connexion: Va échouer (identifiants invalides)")
    print("\n🎯 Comportement attendu:")
    print("   - credentials_found = True")
    print("   - connection_test_success = False")
    print("   - should_respond_to_candidate = True")
    print("   - candidate_response_message contient 'Mot de passe oublié ?'")

    result = get_credentials_with_validation(
        deal_data=deal_data,
        threads=threads,
        crm_client=None,
        deal_id=None,
        auto_update_crm=False
    )

    print("\n📊 Résultat obtenu:")
    print(f"   - credentials_found: {result['credentials_found']}")
    print(f"   - connection_test_success: {result['connection_test_success']}")
    print(f"   - should_respond_to_candidate: {result['should_respond_to_candidate']}")

    # Vérifications
    success = True

    if not result['credentials_found']:
        print("\n❌ ERREUR: credentials_found devrait être True")
        success = False

    if result['connection_test_success']:
        print("\n❌ ERREUR: connection_test_success devrait être False")
        success = False

    if not result['should_respond_to_candidate']:
        print("\n❌ ERREUR: should_respond_to_candidate devrait être True")
        success = False

    if result['candidate_response_message']:
        if 'Mot de passe oublié ?' in result['candidate_response_message']:
            print("\n✅ Message contient bien la procédure 'Mot de passe oublié ?'")
        else:
            print("\n❌ ERREUR: Message ne contient pas la procédure 'Mot de passe oublié ?'")
            success = False
    else:
        print("\n❌ ERREUR: candidate_response_message ne devrait pas être None")
        success = False

    if success:
        print("\n✅ TEST RÉUSSI !")
        print("   Le système demande au candidat de réinitialiser via 'Mot de passe oublié ?'")
        return True
    else:
        print("\n❌ TEST ÉCHOUÉ")
        return False


def main():
    """Exécuter tous les tests."""
    print("\n" + "=" * 80)
    print("TESTS DU NOUVEAU COMPORTEMENT DE GESTION DES IDENTIFIANTS")
    print("=" * 80)

    tests = [
        ("Identifiants absents - Ne pas demander", test_missing_credentials_no_request),
        ("Identifiants invalides - Procédure réinitialisation", test_invalid_credentials_with_reset_procedure)
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
