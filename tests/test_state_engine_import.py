"""
Test d'import et de configuration du State Engine.

Ce script vérifie que:
1. Tous les modules s'importent correctement
2. Le fichier YAML se charge correctement
3. Les états sont bien configurés
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test que tous les modules s'importent."""
    print("=" * 60)
    print("TEST 1: Imports des modules")
    print("=" * 60)

    try:
        from src.state_engine import StateDetector, TemplateEngine, ResponseValidator, CRMUpdater
        print("✅ Import src.state_engine OK")
    except Exception as e:
        print(f"❌ Import src.state_engine FAILED: {e}")
        return False

    try:
        from src.state_engine.state_detector import DetectedState
        print("✅ Import DetectedState OK")
    except Exception as e:
        print(f"❌ Import DetectedState FAILED: {e}")
        return False

    return True


def test_yaml_loading():
    """Test le chargement du fichier YAML."""
    print("\n" + "=" * 60)
    print("TEST 2: Chargement du YAML")
    print("=" * 60)

    try:
        from src.state_engine import StateDetector
        detector = StateDetector()
        print(f"✅ YAML chargé: {len(detector.states)} états trouvés")

        # Afficher les catégories d'états
        categories = {}
        for name, config in detector.states.items():
            cat = config.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1

        print("\n📊 États par catégorie:")
        for cat, count in sorted(categories.items()):
            print(f"   • {cat}: {count}")

        return True

    except Exception as e:
        print(f"❌ Chargement YAML FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_state_detection():
    """Test la détection d'état avec des données simulées."""
    print("\n" + "=" * 60)
    print("TEST 3: Détection d'état")
    print("=" * 60)

    try:
        from src.state_engine import StateDetector

        detector = StateDetector()

        # Test 1: Deal Uber 20€ sans documents
        print("\n🧪 Test: Uber 20€ GAGNÉ sans Date_Dossier_reçu")
        deal_data = {
            'Amount': 20,
            'Stage': 'GAGNÉ',
            'Date_Dossier_re_u': None,
            'Evalbox': '',
        }
        examt3p_data = {'compte_existe': False}
        triage_result = {'action': 'GO', 'detected_intent': None}
        linking_result = {'deal_id': '123', 'has_duplicate_uber_offer': False}

        state = detector.detect_state(
            deal_data=deal_data,
            examt3p_data=examt3p_data,
            triage_result=triage_result,
            linking_result=linking_result
        )
        print(f"   → État détecté: {state.name} ({state.id})")
        print(f"   → Catégorie: {state.category}")
        print(f"   → Action workflow: {state.workflow_action}")

        # Test 2: Deal avec convocation reçue
        print("\n🧪 Test: Convocation reçue")
        deal_data = {
            'Amount': 20,
            'Stage': 'GAGNÉ',
            'Date_Dossier_re_u': '2025-01-01',
            'Evalbox': 'Convoc CMA reçue',
            'Date_examen_VTC': '2026-02-15',
        }
        examt3p_data = {
            'compte_existe': True,
            'identifiant': 'test@email.com',
            'mot_de_passe': 'test123',
        }

        state = detector.detect_state(
            deal_data=deal_data,
            examt3p_data=examt3p_data,
            triage_result=triage_result,
            linking_result=linking_result
        )
        print(f"   → État détecté: {state.name} ({state.id})")
        print(f"   → Catégorie: {state.category}")

        # Test 3: Doublon Uber
        print("\n🧪 Test: Doublon Uber 20€")
        linking_result_duplicate = {
            'deal_id': '123',
            'has_duplicate_uber_offer': True,
            'duplicate_deals': [{'id': '1'}, {'id': '2'}]
        }

        state = detector.detect_state(
            deal_data=deal_data,
            examt3p_data=examt3p_data,
            triage_result=triage_result,
            linking_result=linking_result_duplicate
        )
        print(f"   → État détecté: {state.name} ({state.id})")

        # Test 4: Intention CONFIRMATION_SESSION
        print("\n🧪 Test: Intention CONFIRMATION_SESSION")
        triage_result_session = {
            'action': 'GO',
            'detected_intent': 'CONFIRMATION_SESSION',
            'intent_context': {}
        }
        deal_data_session = {
            'Amount': 20,
            'Stage': 'GAGNÉ',
            'Date_Dossier_re_u': '2025-01-01',
            'Evalbox': 'Dossier Synchronisé',
            'Date_examen_VTC': '2026-02-15',
        }

        state = detector.detect_state(
            deal_data=deal_data_session,
            examt3p_data=examt3p_data,
            triage_result=triage_result_session,
            linking_result=linking_result
        )
        print(f"   → État détecté: {state.name} ({state.id})")
        print(f"   → Intention: {state.detected_intent}")

        return True

    except Exception as e:
        print(f"❌ Détection d'état FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_template_engine():
    """Test le TemplateEngine."""
    print("\n" + "=" * 60)
    print("TEST 4: Template Engine")
    print("=" * 60)

    try:
        from src.state_engine import TemplateEngine, StateDetector
        from src.state_engine.state_detector import DetectedState

        engine = TemplateEngine()
        detector = StateDetector()

        # Créer un état de test
        deal_data = {
            'Deal_Name': 'JEAN DUPONT',
            'Amount': 20,
            'Stage': 'GAGNÉ',
            'Evalbox': 'Convoc CMA reçue',
        }
        examt3p_data = {
            'compte_existe': True,
            'identifiant': 'jean.dupont@email.com',
            'mot_de_passe': 'secret123',
        }
        triage_result = {'action': 'GO'}
        linking_result = {'deal_id': '123'}

        state = detector.detect_state(
            deal_data=deal_data,
            examt3p_data=examt3p_data,
            triage_result=triage_result,
            linking_result=linking_result
        )

        # Générer la réponse (sans IA pour le test)
        result = engine.generate_response(state, ai_generator=None)

        print(f"✅ Template utilisé: {result['template_used']}")
        print(f"✅ Placeholders remplacés: {result['placeholders_replaced']}")
        print(f"✅ Longueur réponse: {len(result['response_text'])} caractères")

        print("\n📝 Aperçu de la réponse:")
        print("-" * 40)
        print(result['response_text'][:500])
        if len(result['response_text']) > 500:
            print("...")
        print("-" * 40)

        return True

    except Exception as e:
        print(f"❌ Template Engine FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_response_validator():
    """Test le ResponseValidator."""
    print("\n" + "=" * 60)
    print("TEST 5: Response Validator")
    print("=" * 60)

    try:
        from src.state_engine import ResponseValidator, StateDetector
        from src.state_engine.state_detector import DetectedState

        validator = ResponseValidator()
        detector = StateDetector()

        # Créer un état de test
        deal_data = {'Evalbox': 'VALIDE CMA'}
        examt3p_data = {}
        triage_result = {'action': 'GO'}
        linking_result = {'deal_id': '123'}

        state = detector.detect_state(
            deal_data=deal_data,
            examt3p_data=examt3p_data,
            triage_result=triage_result,
            linking_result=linking_result
        )

        # Test avec une bonne réponse
        good_response = """Bonjour Jean,

Votre dossier a bien été validé par la CMA. Vous recevrez votre convocation environ 10 jours avant l'examen.

Bien cordialement,
L'équipe CAB Formations"""

        result = validator.validate(good_response, state)
        print(f"✅ Réponse valide: {result.valid}")
        print(f"   Erreurs: {len(result.errors)}")
        print(f"   Warnings: {len(result.warnings)}")
        print(f"   Checks passés: {result.checks_passed}")

        # Test avec une mauvaise réponse (terme interdit)
        bad_response = """Bonjour,

J'ai mis à jour votre Evalbox dans le CRM. Le deal BFS montre que tout est OK.

Votre inscription à 20€ est confirmée.

Cordialement"""

        result_bad = validator.validate(bad_response, state)
        print(f"\n❌ Réponse avec erreurs: valid={result_bad.valid}")
        print(f"   Erreurs trouvées:")
        for err in result_bad.errors:
            print(f"      • {err.error_type}: {err.message}")

        return True

    except Exception as e:
        print(f"❌ Response Validator FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crm_updater():
    """Test le CRMUpdater."""
    print("\n" + "=" * 60)
    print("TEST 6: CRM Updater")
    print("=" * 60)

    try:
        from src.state_engine import CRMUpdater, StateDetector

        updater = CRMUpdater()
        detector = StateDetector()

        # Créer un état CONFIRMATION_SESSION
        deal_data = {
            'Amount': 20,
            'Stage': 'GAGNÉ',
            'Date_Dossier_re_u': '2025-01-01',
            'Evalbox': 'Dossier Synchronisé',
        }
        examt3p_data = {'compte_existe': True}
        triage_result = {
            'action': 'GO',
            'detected_intent': 'CONFIRMATION_SESSION'
        }
        linking_result = {'deal_id': '123'}

        state = detector.detect_state(
            deal_data=deal_data,
            examt3p_data=examt3p_data,
            triage_result=triage_result,
            linking_result=linking_result
        )

        # Test extraction session
        message = "Bonjour, je choisis le cours du soir s'il vous plaît."
        proposed_sessions = [
            {'id': '1001', 'Name': 'cdj-01', 'session_type': 'jour'},
            {'id': '1002', 'Name': 'cds-01', 'session_type': 'soir'},
        ]

        result = updater.determine_updates(
            state=state,
            candidate_message=message,
            proposed_sessions=proposed_sessions
        )

        print(f"✅ Mises à jour déterminées:")
        print(f"   Applied: {result.updates_applied}")
        print(f"   Blocked: {result.updates_blocked}")
        print(f"   Skipped: {result.updates_skipped}")

        # Test avec message ambigu
        message_ambigu = "Je veux le cours du jour, enfin non le soir, je sais pas."
        result_ambigu = updater.determine_updates(
            state=state,
            candidate_message=message_ambigu,
            proposed_sessions=proposed_sessions
        )
        print(f"\n⚠️ Message ambigu:")
        print(f"   Skipped: {result_ambigu.updates_skipped}")

        return True

    except Exception as e:
        print(f"❌ CRM Updater FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Exécute tous les tests."""
    print("\n" + "🚀 " * 20)
    print("STATE ENGINE - TESTS D'IMPORT ET DE CONFIGURATION")
    print("🚀 " * 20 + "\n")

    results = []

    results.append(("Imports", test_imports()))
    results.append(("YAML Loading", test_yaml_loading()))
    results.append(("State Detection", test_state_detection()))
    results.append(("Template Engine", test_template_engine()))
    results.append(("Response Validator", test_response_validator()))
    results.append(("CRM Updater", test_crm_updater()))

    print("\n" + "=" * 60)
    print("RÉSUMÉ DES TESTS")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {name}: {status}")
        if not passed:
            all_passed = False

    print("\n" + ("🎉 TOUS LES TESTS PASSENT!" if all_passed else "⚠️ CERTAINS TESTS ONT ÉCHOUÉ"))

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
