"""
Test rendering the response_master.html template with pybars3.

This verifies that the full production template can be rendered correctly.
"""
import sys
import io
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_response_master_statut_dossier():
    """Test response_master with STATUT_DOSSIER intention."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)
    renderer.load_all_partials()

    # Load response_master.html
    template_path = states_path / "templates" / "response_master.html"
    template = template_path.read_text(encoding='utf-8')

    # Context for a typical STATUT_DOSSIER scenario
    context = {
        "prenom": "Jean",
        "intention_statut_dossier": True,
        "show_statut_section": True,
        "evalbox_dossier_synchronise": True,
        "has_required_action": True,
        "action_completer_dossier": True,
        "identifiant_examt3p": "candidat.test@cab-formations.fr",
        "mot_de_passe_examt3p": "testpassword123",
        "has_next_dates": True,
        "show_dates_section": True,
        "next_dates": [
            {
                "date_examen_formatted": "31/03/2026",
                "date_cloture_formatted": "13/03/2026",
                "Departement": "75",
                "is_first_of_dept": True,
                "session_name": "Cours du jour",
                "session_debut": "23/03/2026",
                "session_fin": "27/03/2026",
            }
        ],
        "email": "jean@example.com",
        # Disable sections we don't want
        "uber_cas_a": False,
        "uber_cas_b": False,
        "uber_cas_d": False,
        "uber_cas_e": False,
        "uber_doublon": False,
        "uber_prospect": False,
        "resultat_admis": False,
        "resultat_non_admis": False,
        "resultat_absent": False,
        "report_bloque": False,
        "report_possible": False,
        "report_force_majeure": False,
        "credentials_invalid": False,
        "credentials_inconnus": False,
        "show_prospect_rappel": False,
    }

    result = renderer.render(template, context)

    # Verify key elements are present
    checks = [
        ("Greeting", "Bonjour Jean" in result),
        ("Status section", "Statut" in result or "dossier" in result.lower()),
        ("Action section", "étape" in result.lower() or "action" in result.lower()),
        ("Dates section", "31/03/2026" in result),
        ("Signature", "CAB Formations" in result or "cordialement" in result.lower()),
    ]

    print("Test: response_master with STATUT_DOSSIER")
    print("-" * 50)

    all_passed = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\nRendered output (first 500 chars):")
        print(result[:500])
        print("...")

    return all_passed


def test_response_master_confirmation_session():
    """Test response_master with CONFIRMATION_SESSION intention."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)
    renderer.load_all_partials()

    template_path = states_path / "templates" / "response_master.html"
    template = template_path.read_text(encoding='utf-8')

    context = {
        "prenom": "Marie",
        "intention_confirmation_session": True,
        "show_statut_section": True,
        "evalbox_dossier_cree": True,
        "has_sessions_proposees": True,
        "show_sessions_section": True,
        "session_preference": "jour",
        "preference_horaire_text": "cours du jour",
        "sessions_proposees": [
            {
                "date_examen_formatted": "31/03/2026",
                "is_first_of_exam": True,
                "is_jour": True,
                "is_soir": False,
                "date_debut": "23/03/2026",
                "date_fin": "27/03/2026",
            },
            {
                "date_examen_formatted": "31/03/2026",
                "is_first_of_exam": False,
                "is_jour": False,
                "is_soir": True,
                "date_debut": "16/03/2026",
                "date_fin": "27/03/2026",
            }
        ],
        # Disable other sections
        "uber_cas_a": False,
        "uber_cas_b": False,
        "uber_cas_d": False,
        "uber_cas_e": False,
        "uber_doublon": False,
        "uber_prospect": False,
        "resultat_admis": False,
        "resultat_non_admis": False,
        "resultat_absent": False,
        "report_bloque": False,
        "report_possible": False,
        "report_force_majeure": False,
        "credentials_invalid": False,
        "credentials_inconnus": False,
        "show_prospect_rappel": False,
        "has_required_action": False,
        "show_dates_section": False,
    }

    result = renderer.render(template, context)

    checks = [
        ("Greeting", "Bonjour Marie" in result),
        ("Sessions section", "Sessions" in result or "session" in result.lower()),
        ("Cours du jour", "Cours du jour" in result),
        ("Cours du soir", "Cours du soir" in result),
        ("Session dates", "23/03/2026" in result and "27/03/2026" in result),
        ("Signature", "CAB Formations" in result or "cordialement" in result.lower()),
    ]

    print("\nTest: response_master with CONFIRMATION_SESSION")
    print("-" * 50)

    all_passed = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\nRendered output (first 800 chars):")
        print(result[:800])
        print("...")

    return all_passed


def test_response_master_uber_case():
    """Test response_master with Uber case."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)
    renderer.load_all_partials()

    template_path = states_path / "templates" / "response_master.html"
    template = template_path.read_text(encoding='utf-8')

    context = {
        "prenom": "Pierre",
        "uber_cas_b": True,  # Test manquant
        "intention_question_uber": True,
        "show_statut_section": False,
        # Disable other sections
        "uber_cas_a": False,
        "uber_cas_d": False,
        "uber_cas_e": False,
        "uber_doublon": False,
        "uber_prospect": False,
        "resultat_admis": False,
        "resultat_non_admis": False,
        "resultat_absent": False,
        "report_bloque": False,
        "report_possible": False,
        "report_force_majeure": False,
        "credentials_invalid": False,
        "credentials_inconnus": False,
        "show_prospect_rappel": False,
        "has_required_action": False,
        "show_dates_section": False,
        "show_sessions_section": False,
    }

    result = renderer.render(template, context)

    # The uber cas_b partial should be included
    checks = [
        ("Greeting", "Bonjour Pierre" in result),
        ("Uber content included", len(result) > 100),  # Should have substantial content
        ("Signature", "CAB Formations" in result or "cordialement" in result.lower()),
    ]

    print("\nTest: response_master with Uber case B")
    print("-" * 50)

    all_passed = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\nRendered output:")
        print(result[:500])

    return all_passed


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Response Master Template Tests (pybars3)")
    print("=" * 60)

    tests = [
        test_response_master_statut_dossier,
        test_response_master_confirmation_session,
        test_response_master_uber_case,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}")
            print(f"  {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
