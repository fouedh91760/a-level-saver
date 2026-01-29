"""
Capture baseline outputs for regression testing of TemplateEngine pybars3 migration.

This script captures the response outputs from a set of regression tickets
to enable comparison before and after the pybars3 refactoring.

Usage:
    python tests/baseline_capture.py                    # Capture to baselines/pre_pybars.json
    python tests/baseline_capture.py --output FILE     # Capture to custom file
"""
import sys
import io
import json
import argparse
from pathlib import Path
from datetime import datetime

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# Regression tickets covering various scenarios
REGRESSION_TICKETS = [
    # Cross-department + unless + each (complex template parsing)
    '198709000448774407',
    # STATUT_DOSSIER intention
    '198709000448019181',
    # CONFIRMATION_SESSION intention
    '198709000448043841',
    # DEMANDE_IDENTIFIANTS intention
    '198709000448028627',
    # Sessions proposees (each loops)
    '198709000448028260',
]


def run_single_ticket(ticket_id: str, dry_run: bool = True) -> dict:
    """Run workflow for a single ticket and return results."""
    from src.workflows.doc_ticket_workflow import DOCTicketWorkflow

    workflow = DOCTicketWorkflow()
    try:
        result = workflow.process_ticket(
            ticket_id=ticket_id,
            auto_create_draft=False,
            auto_update_crm=False,
            auto_update_ticket=False
        )
        return result
    finally:
        try:
            workflow.close()
        except Exception:
            pass


def capture_baseline(output_file: str = None):
    """Capture baseline outputs for all regression tickets."""
    if output_file is None:
        output_file = str(project_root / 'baselines' / 'pre_pybars.json')

    # Ensure output directory exists
    Path(output_file).parent.mkdir(exist_ok=True)

    results = []
    errors = []

    print(f"Capturing baselines for {len(REGRESSION_TICKETS)} tickets...")
    print("=" * 60)

    for i, ticket_id in enumerate(REGRESSION_TICKETS, 1):
        print(f"\n[{i}/{len(REGRESSION_TICKETS)}] Processing ticket {ticket_id}...")

        try:
            result = run_single_ticket(ticket_id, dry_run=True)

            if result and result.get('success'):
                response_result = result.get('response_result', {})
                state_engine = response_result.get('state_engine', {})
                context = state_engine.get('context', {})

                baseline_entry = {
                    'ticket_id': ticket_id,
                    'success': True,
                    'state': state_engine.get('state_id'),
                    'state_name': state_engine.get('state_name'),
                    'intent': context.get('detected_intent') or context.get('primary_intent'),
                    'template': response_result.get('template_used'),
                    'template_file': response_result.get('template_file'),
                    'blocks_included': response_result.get('blocks_included', []),
                    'response_text': response_result.get('response_text', ''),
                    'response_length': len(response_result.get('response_text', '')),
                }

                print(f"    State: {baseline_entry['state']}")
                print(f"    Intent: {baseline_entry['intent']}")
                print(f"    Template: {baseline_entry['template']}")
                print(f"    Response length: {baseline_entry['response_length']} chars")

                results.append(baseline_entry)
            else:
                error_entry = {
                    'ticket_id': ticket_id,
                    'success': False,
                    'error': result.get('errors', ['Unknown error']) if result else ['Workflow returned None'],
                    'workflow_stage': result.get('workflow_stage') if result else 'unknown',
                }
                results.append(error_entry)
                errors.append(ticket_id)
                print(f"    ERROR: {error_entry.get('error')}")

        except Exception as e:
            error_entry = {
                'ticket_id': ticket_id,
                'success': False,
                'error': str(e),
            }
            results.append(error_entry)
            errors.append(ticket_id)
            print(f"    EXCEPTION: {e}")

    # Write results
    output_data = {
        'capture_timestamp': datetime.now().isoformat(),
        'total_tickets': len(REGRESSION_TICKETS),
        'successful': len(REGRESSION_TICKETS) - len(errors),
        'errors': errors,
        'results': results
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"Captured {len(results)} baselines")
    print(f"  Successful: {len(REGRESSION_TICKETS) - len(errors)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Output: {output_file}")

    if errors:
        print(f"\nFailed tickets: {errors}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Capture baseline outputs for pybars3 migration regression testing'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output file path (default: baselines/pre_pybars.json)'
    )

    args = parser.parse_args()
    capture_baseline(args.output)


if __name__ == '__main__':
    main()
