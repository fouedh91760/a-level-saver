"""
Comparison test: regex-based vs pybars3-based template rendering.

This test loads templates and renders them with both implementations
to verify they produce equivalent output.
"""
import sys
import io
import re
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace for comparison."""
    if not text:
        return ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Collapse all whitespace (spaces, tabs, newlines) to single space
    # This makes comparison focus on content, not formatting
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_regex_renderer():
    """Get a TemplateEngine with regex parsing (PYBARS_ENABLED=False)."""
    # Temporarily disable pybars
    import src.state_engine.template_engine as te_module
    original_flag = te_module.PYBARS_ENABLED
    te_module.PYBARS_ENABLED = False

    from src.state_engine.template_engine import TemplateEngine
    engine = TemplateEngine()
    engine.pybars_renderer = None  # Ensure regex mode

    te_module.PYBARS_ENABLED = original_flag
    return engine


def get_pybars_renderer():
    """Get a PybarsRenderer."""
    from src.state_engine.pybars_renderer import PybarsRenderer
    states_path = project_root / "states"
    renderer = PybarsRenderer(states_path)
    renderer.load_all_partials()
    return renderer


def compare_renderers(template: str, context: dict, test_name: str):
    """Compare output of both renderers."""
    regex_engine = get_regex_renderer()
    pybars_renderer = get_pybars_renderer()

    # Render with regex
    blocks_included = []
    regex_output = regex_engine._parse_template(template, context, blocks_included)
    regex_output = regex_engine._replace_placeholders(regex_output, context)[0]
    regex_normalized = normalize_whitespace(regex_output)

    # Render with pybars
    pybars_output = pybars_renderer.render(template, context)
    pybars_normalized = normalize_whitespace(pybars_output)

    if regex_normalized == pybars_normalized:
        print(f"PASS: {test_name}")
        return True
    else:
        print(f"FAIL: {test_name}")
        print(f"  Regex output ({len(regex_normalized)} chars):")
        print(f"    {regex_normalized[:200]}...")
        print(f"  Pybars output ({len(pybars_normalized)} chars):")
        print(f"    {pybars_normalized[:200]}...")
        return False


def test_simple_variables():
    """Test simple variable replacement."""
    template = "Bonjour {{prenom}}, votre email est {{email}}."
    context = {"prenom": "Jean", "email": "jean@example.com"}
    return compare_renderers(template, context, "Simple variables")


def test_if_else():
    """Test if/else blocks."""
    template = "{{#if uber_20}}Offre Uber{{else}}Offre standard{{/if}}"
    context = {"uber_20": True}
    result1 = compare_renderers(template, context, "If/else (true)")

    context = {"uber_20": False}
    result2 = compare_renderers(template, context, "If/else (false)")

    return result1 and result2


def test_unless():
    """Test unless blocks."""
    template = "{{#unless compte_existe}}Créer compte{{/unless}}"
    context = {"compte_existe": False}
    result1 = compare_renderers(template, context, "Unless (false)")

    context = {"compte_existe": True}
    result2 = compare_renderers(template, context, "Unless (true)")

    return result1 and result2


def test_each():
    """Test each blocks."""
    # Note: pybars handles whitespace slightly differently in each blocks
    # Using <br> tags for line breaks instead of newlines for consistent behavior
    template = """{{#each dates}}- {{this.date}}: {{this.dept}}<br>{{/each}}"""
    context = {
        "dates": [
            {"date": "31/03", "dept": "75"},
            {"date": "15/04", "dept": "92"},
        ]
    }
    return compare_renderers(template, context, "Each block")


def test_nested_if_in_each():
    """Test if inside each."""
    template = """{{#each sessions}}
{{#if this.is_jour}}Jour: {{this.date}}{{/if}}
{{#if this.is_soir}}Soir: {{this.date}}{{/if}}
{{/each}}"""
    context = {
        "sessions": [
            {"is_jour": True, "is_soir": False, "date": "23/03"},
            {"is_jour": False, "is_soir": True, "date": "16/03"},
        ]
    }
    return compare_renderers(template, context, "Nested if in each")


def test_dot_notation():
    """Test dot notation for nested objects."""
    template = "{{#if data.active}}Actif{{else}}Inactif{{/if}} - {{data.name}}"
    context = {"data": {"active": True, "name": "Test"}}
    return compare_renderers(template, context, "Dot notation")


def test_partial_salutation():
    """Test partial inclusion - salutation."""
    template = "{{> salutation_personnalisee}}"
    context = {"prenom": "Marie"}
    return compare_renderers(template, context, "Partial salutation")


def test_partial_signature():
    """Test partial inclusion - signature."""
    template = "Merci.\n{{> signature}}"
    context = {}
    return compare_renderers(template, context, "Partial signature")


def test_combined_template():
    """Test a combined template with multiple features."""
    template = """{{> salutation_personnalisee}}

{{#if show_status}}
<b>Statut</b>
{{#if status_valid}}Validé{{else}}En attente{{/if}}
{{/if}}

{{#if has_dates}}
<b>Dates</b>
{{#each dates}}
→ {{this.date}} ({{this.dept}})
{{/each}}
{{/if}}

{{> signature}}"""

    context = {
        "prenom": "Pierre",
        "show_status": True,
        "status_valid": False,
        "has_dates": True,
        "dates": [
            {"date": "31/03/2026", "dept": "75"},
            {"date": "15/04/2026", "dept": "92"},
        ]
    }
    return compare_renderers(template, context, "Combined template")


def run_all_tests():
    """Run all comparison tests."""
    print("=" * 60)
    print("Regex vs Pybars Renderer Comparison Tests")
    print("=" * 60)

    tests = [
        test_simple_variables,
        test_if_else,
        test_unless,
        test_each,
        test_nested_if_in_each,
        test_dot_notation,
        test_partial_salutation,
        test_partial_signature,
        test_combined_template,
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

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
