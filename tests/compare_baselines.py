"""
Compare two baseline files for regression testing.

This script compares baseline outputs from before and after the pybars3 migration
to detect any differences in template rendering.

Usage:
    python tests/compare_baselines.py baselines/pre_pybars.json baselines/post_pybars.json
    python tests/compare_baselines.py file1.json file2.json --verbose
"""
import sys
import io
import json
import re
import argparse
from pathlib import Path
from difflib import unified_diff

# Fix Windows encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison.

    - Collapses multiple whitespace to single space
    - Strips leading/trailing whitespace
    - Normalizes line endings
    """
    if not text:
        return ''
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Collapse multiple whitespace (but preserve single newlines for structure)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def compare_responses(baseline: dict, current: dict, verbose: bool = False) -> list:
    """
    Compare two baseline entries and return list of differences.

    Returns list of difference descriptions, empty if identical.
    """
    differences = []
    ticket_id = baseline.get('ticket_id', 'unknown')

    # Check success status
    if baseline.get('success') != current.get('success'):
        differences.append(f"Success status changed: {baseline.get('success')} -> {current.get('success')}")

    # If both failed, don't compare further
    if not baseline.get('success') or not current.get('success'):
        return differences

    # Check state
    if baseline.get('state') != current.get('state'):
        differences.append(f"State changed: {baseline.get('state')} -> {current.get('state')}")

    # Check intent
    if baseline.get('intent') != current.get('intent'):
        differences.append(f"Intent changed: {baseline.get('intent')} -> {current.get('intent')}")

    # Check template
    if baseline.get('template') != current.get('template'):
        differences.append(f"Template changed: {baseline.get('template')} -> {current.get('template')}")

    # Compare normalized response text
    baseline_text = normalize_text(baseline.get('response_text', ''))
    current_text = normalize_text(current.get('response_text', ''))

    if baseline_text != current_text:
        len_diff = len(current_text) - len(baseline_text)
        differences.append(f"Response text differs (length: {len(baseline_text)} -> {len(current_text)}, delta: {len_diff:+d})")

        if verbose:
            # Show unified diff
            baseline_lines = baseline_text.split('\n')
            current_lines = current_text.split('\n')
            diff = list(unified_diff(
                baseline_lines,
                current_lines,
                fromfile=f'baseline/{ticket_id}',
                tofile=f'current/{ticket_id}',
                lineterm=''
            ))
            if diff:
                differences.append("Diff:\n" + '\n'.join(diff[:50]))  # Limit diff output

    return differences


def compare_baselines(file1: str, file2: str, verbose: bool = False) -> int:
    """
    Compare two baseline files and report differences.

    Returns:
        0 if identical
        1 if differences found
        2 if error
    """
    try:
        with open(file1, 'r', encoding='utf-8') as f:
            baseline_data = json.load(f)
        with open(file2, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
    except FileNotFoundError as e:
        print(f"ERROR: File not found: {e.filename}")
        return 2
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        return 2

    baseline_results = baseline_data.get('results', [])
    current_results = current_data.get('results', [])

    # Index by ticket_id
    baseline_by_id = {r['ticket_id']: r for r in baseline_results}
    current_by_id = {r['ticket_id']: r for r in current_results}

    all_ticket_ids = set(baseline_by_id.keys()) | set(current_by_id.keys())

    print(f"Comparing baselines:")
    print(f"  File 1: {file1} ({len(baseline_results)} tickets, {baseline_data.get('capture_timestamp', 'unknown')})")
    print(f"  File 2: {file2} ({len(current_results)} tickets, {current_data.get('capture_timestamp', 'unknown')})")
    print("=" * 70)

    total_differences = 0
    tickets_with_diff = []

    for ticket_id in sorted(all_ticket_ids):
        baseline = baseline_by_id.get(ticket_id)
        current = current_by_id.get(ticket_id)

        if baseline is None:
            print(f"\n[{ticket_id}] NEW in file2 (not in baseline)")
            total_differences += 1
            tickets_with_diff.append(ticket_id)
            continue

        if current is None:
            print(f"\n[{ticket_id}] MISSING in file2 (was in baseline)")
            total_differences += 1
            tickets_with_diff.append(ticket_id)
            continue

        differences = compare_responses(baseline, current, verbose)

        if differences:
            print(f"\n[{ticket_id}] DIFF:")
            for diff in differences:
                print(f"    {diff}")
            total_differences += len(differences)
            tickets_with_diff.append(ticket_id)
        else:
            if verbose:
                print(f"\n[{ticket_id}] OK")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY:")
    print(f"  Total tickets compared: {len(all_ticket_ids)}")
    print(f"  Tickets with differences: {len(tickets_with_diff)}")
    print(f"  Total differences: {total_differences}")

    if tickets_with_diff:
        print(f"\nTickets with differences:")
        for tid in tickets_with_diff:
            print(f"    - {tid}")
        print("\nRESULT: DIFFERENCES FOUND")
        return 1
    else:
        print("\nRESULT: ALL OUTPUTS MATCH!")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Compare two baseline files for regression testing'
    )
    parser.add_argument(
        'file1',
        type=str,
        help='First baseline file (reference/expected)'
    )
    parser.add_argument(
        'file2',
        type=str,
        help='Second baseline file (current/actual)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show detailed diff for each difference'
    )

    args = parser.parse_args()
    sys.exit(compare_baselines(args.file1, args.file2, args.verbose))


if __name__ == '__main__':
    main()
