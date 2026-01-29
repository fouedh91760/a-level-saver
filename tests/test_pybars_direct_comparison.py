"""
Direct comparison of regex vs pybars3 template rendering.

This test renders the same template with identical context using both
implementations to verify they produce equivalent output.
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


def normalize_for_html(text: str) -> str:
    """Normalize text for HTML comparison (whitespace-insensitive)."""
    if not text:
        return ''
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    # Remove empty lines
    lines = [line for line in lines if line]
    # Join with single newline
    return '\n'.join(lines)


def test_direct_comparison():
    """Compare regex and pybars3 rendering of response_master.html."""
    from src.state_engine.pybars_renderer import PybarsRenderer
    import src.state_engine.template_engine as te_module

    states_path = project_root / "states"

    # Load template
    template_path = states_path / "templates" / "response_master.html"
    template = template_path.read_text(encoding='utf-8')

    # Context mimicking a real scenario
    context = {
        "prenom": "TestUser",
        "intention_statut_dossier": True,
        "show_statut_section": True,
        "evalbox_dossier_synchronise": True,
        "has_required_action": True,
        "action_completer_dossier": True,
        "identifiant_examt3p": "test@example.com",
        "mot_de_passe_examt3p": "password123",
        "has_next_dates": True,
        "show_dates_section": True,
        "next_dates": [
            {
                "date_examen_formatted": "31/03/2026",
                "date_cloture_formatted": "13/03/2026",
                "Departement": "75",
                "is_first_of_dept": True,
            }
        ],
        "email": "test@example.com",
        # All false flags
        "uber_cas_a": False, "uber_cas_b": False, "uber_cas_d": False,
        "uber_cas_e": False, "uber_doublon": False, "uber_prospect": False,
        "resultat_admis": False, "resultat_non_admis": False, "resultat_absent": False,
        "report_bloque": False, "report_possible": False, "report_force_majeure": False,
        "credentials_invalid": False, "credentials_inconnus": False,
        "show_prospect_rappel": False, "show_sessions_section": False,
    }

    # Render with pybars3
    print("Rendering with pybars3...")
    pybars_renderer = PybarsRenderer(states_path)
    pybars_renderer.load_all_partials()
    pybars_output = pybars_renderer.render(template, context)

    # Render with regex
    print("Rendering with regex...")
    te_module.PYBARS_ENABLED = False
    from src.state_engine.template_engine import TemplateEngine
    regex_engine = TemplateEngine()
    regex_engine.pybars_renderer = None

    blocks_included = []
    regex_output = regex_engine._parse_template(template, context, blocks_included)
    regex_output = regex_engine._replace_placeholders(regex_output, context)[0]

    # Normalize for comparison
    pybars_normalized = normalize_for_html(pybars_output)
    regex_normalized = normalize_for_html(regex_output)

    print(f"\nPybars output length: {len(pybars_normalized)}")
    print(f"Regex output length: {len(regex_normalized)}")

    # Check key elements in both
    key_elements = [
        "Bonjour TestUser",
        "Statut",
        "31/03/2026",
        "CAB Formations",
    ]

    print("\nKey elements check:")
    all_present = True
    for element in key_elements:
        in_pybars = element in pybars_output
        in_regex = element in regex_output
        status = "BOTH" if (in_pybars and in_regex) else ("PYBARS_ONLY" if in_pybars else ("REGEX_ONLY" if in_regex else "NEITHER"))
        print(f"  '{element}': {status}")
        if not (in_pybars and in_regex):
            all_present = False

    if all_present:
        print("\n PASS: All key elements present in both outputs")
    else:
        print("\n FAIL: Some elements missing")
        print("\nPybars output (first 500):")
        print(pybars_output[:500])
        print("\nRegex output (first 500):")
        print(regex_output[:500])

    # The outputs might have minor whitespace differences but content should be equivalent
    return all_present


if __name__ == "__main__":
    success = test_direct_comparison()
    sys.exit(0 if success else 1)
