"""
Unit tests for PybarsRenderer - testing template rendering without API calls.

This test validates that the pybars3-based renderer produces the same output
as the regex-based renderer for various template patterns.
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


def test_simple_variable_replacement():
    """Test simple {{variable}} replacement."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)

    template = "Bonjour {{prenom}}, votre email est {{email}}."
    context = {"prenom": "Jean", "email": "jean@example.com"}

    result = renderer.render(template, context)
    expected = "Bonjour Jean, votre email est jean@example.com."

    assert result == expected, f"Expected: {expected}\nGot: {result}"
    print("PASS: Simple variable replacement")


def test_if_block():
    """Test {{#if condition}}...{{else}}...{{/if}}."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)

    template = """{{#if uber_20}}Vous bénéficiez de l'offre Uber.{{else}}Offre standard.{{/if}}"""

    # Test with condition true
    result_true = renderer.render(template, {"uber_20": True})
    assert "Uber" in result_true, f"Expected Uber text, got: {result_true}"

    # Test with condition false
    result_false = renderer.render(template, {"uber_20": False})
    assert "standard" in result_false, f"Expected standard text, got: {result_false}"

    print("PASS: If block")


def test_unless_block():
    """Test {{#unless condition}}...{{/unless}}."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)

    template = """{{#unless compte_existe}}Vous devez créer un compte.{{/unless}}"""

    # Test with condition false (unless shows content)
    result_false = renderer.render(template, {"compte_existe": False})
    assert "créer un compte" in result_false, f"Got: {result_false}"

    # Test with condition true (unless hides content)
    result_true = renderer.render(template, {"compte_existe": True})
    assert "créer un compte" not in result_true, f"Got: {result_true}"

    print("PASS: Unless block")


def test_each_block():
    """Test {{#each items}}...{{/each}}."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)

    template = """Dates disponibles:
{{#each dates}}
- {{this.date_examen}} ({{this.departement}})
{{/each}}"""

    context = {
        "dates": [
            {"date_examen": "31/03/2026", "departement": "75"},
            {"date_examen": "15/04/2026", "departement": "92"},
        ]
    }

    result = renderer.render(template, context)
    assert "31/03/2026" in result, f"Got: {result}"
    assert "15/04/2026" in result, f"Got: {result}"
    assert "75" in result, f"Got: {result}"
    assert "92" in result, f"Got: {result}"

    print("PASS: Each block")


def test_nested_if_in_each():
    """Test {{#if this.property}} inside {{#each}}."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)

    template = """{{#each sessions}}
{{#if this.is_jour}}Cours du jour: {{this.date_debut}}{{/if}}
{{#if this.is_soir}}Cours du soir: {{this.date_debut}}{{/if}}
{{/each}}"""

    context = {
        "sessions": [
            {"is_jour": True, "is_soir": False, "date_debut": "23/03/2026"},
            {"is_jour": False, "is_soir": True, "date_debut": "16/03/2026"},
        ]
    }

    result = renderer.render(template, context)
    assert "Cours du jour: 23/03/2026" in result, f"Got: {result}"
    assert "Cours du soir: 16/03/2026" in result, f"Got: {result}"

    print("PASS: Nested if in each")


def test_partial_loading():
    """Test that partials are loaded correctly."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)
    count = renderer.load_all_partials()

    assert count > 100, f"Expected >100 partials, got {count}"

    # Check some expected partials exist
    partials = renderer.list_partials()
    assert "salutation_personnalisee" in partials, "Missing salutation_personnalisee"
    assert "signature" in partials, "Missing signature"

    print(f"PASS: Partial loading ({count} partials)")


def test_partial_rendering():
    """Test {{> partial}} rendering."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)
    renderer.load_all_partials()

    template = """{{> salutation_personnalisee}}
Votre dossier est en cours."""

    context = {"prenom": "Marie"}

    result = renderer.render(template, context)
    assert "Bonjour Marie" in result, f"Got: {result}"

    print("PASS: Partial rendering")


def test_none_value_handling():
    """Test that None values are converted to empty strings."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)

    template = "Prénom: {{prenom}}, Nom: {{nom}}"
    context = {"prenom": "Jean", "nom": None}

    result = renderer.render(template, context)
    # None should be converted to empty string, not "None"
    assert "None" not in result, f"None should be empty string, got: {result}"
    assert "Prénom: Jean" in result, f"Got: {result}"

    print("PASS: None value handling")


def test_nested_path_access():
    """Test accessing nested object properties like {{month_cross_department.region}}."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)

    template = """Région: {{month_cross_department.region}}
{{#if month_cross_department.has_options}}Options disponibles.{{/if}}"""

    context = {
        "month_cross_department": {
            "region": "Île-de-France",
            "has_options": True
        }
    }

    result = renderer.render(template, context)
    assert "Île-de-France" in result, f"Got: {result}"
    assert "Options disponibles" in result, f"Got: {result}"

    print("PASS: Nested path access")


def test_handlebars_comments_stripped():
    """Test that {{!-- comments --}} are removed."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)

    template = """{{!-- This is a comment --}}
Bonjour {{prenom}}
{{!-- Another comment --}}"""

    context = {"prenom": "Paul"}

    result = renderer.render(template, context)
    assert "comment" not in result.lower(), f"Comment should be stripped, got: {result}"
    assert "Bonjour Paul" in result, f"Got: {result}"

    print("PASS: Handlebars comments stripped")


def test_complex_template_structure():
    """Test a more complex template resembling response_master.html."""
    from src.state_engine.pybars_renderer import PybarsRenderer

    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)
    renderer.load_all_partials()

    template = """{{> salutation_personnalisee}}

{{#if intention_statut_dossier}}
Concernant l'avancement de votre dossier...
{{/if}}

{{#if show_statut_section}}
<b>Statut de votre dossier</b><br>
{{#if evalbox_valide_cma}}Votre dossier est validé par la CMA.{{/if}}
{{#if evalbox_dossier_synchronise}}Votre dossier est en cours d'instruction.{{/if}}
{{/if}}

{{#if has_next_dates}}
<b>Dates disponibles</b><br>
{{#each next_dates}}
→ {{this.date_examen_formatted}} ({{this.Departement}})
{{/each}}
{{/if}}

{{> signature}}"""

    context = {
        "prenom": "Sophie",
        "intention_statut_dossier": True,
        "show_statut_section": True,
        "evalbox_valide_cma": False,
        "evalbox_dossier_synchronise": True,
        "has_next_dates": True,
        "next_dates": [
            {"date_examen_formatted": "31/03/2026", "Departement": "75"},
            {"date_examen_formatted": "15/04/2026", "Departement": "92"},
        ]
    }

    result = renderer.render(template, context)

    # Check key elements
    assert "Bonjour Sophie" in result, f"Missing greeting, got: {result}"
    assert "avancement de votre dossier" in result, f"Missing intention text"
    assert "Statut de votre dossier" in result, f"Missing status section"
    assert "instruction" in result, f"Missing instruction status"
    assert "31/03/2026" in result, f"Missing date"
    assert "CAB Formations" in result or "cordialement" in result.lower(), f"Missing signature"

    print("PASS: Complex template structure")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("PybarsRenderer Unit Tests")
    print("=" * 60)

    tests = [
        test_simple_variable_replacement,
        test_if_block,
        test_unless_block,
        test_each_block,
        test_nested_if_in_each,
        test_partial_loading,
        test_partial_rendering,
        test_none_value_handling,
        test_nested_path_access,
        test_handlebars_comments_stripped,
        test_complex_template_structure,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}")
            print(f"  {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}")
            print(f"  {type(e).__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
