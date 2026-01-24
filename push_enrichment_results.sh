#!/bin/bash
# Script to push CRM enrichment results after local execution

set -e  # Exit on error

echo "================================================================================"
echo "PUSH CRM ENRICHMENT RESULTS"
echo "================================================================================"

# Check if results files exist
echo ""
echo "🔍 Checking for result files..."

if [ ! -f "fouad_tickets_analysis_with_crm.json" ]; then
    echo "❌ Error: fouad_tickets_analysis_with_crm.json not found"
    echo "   Did you run 'python enrich_fouad_tickets_with_crm.py' first?"
    exit 1
fi

if [ ! -f "scenario_analysis_with_crm.json" ]; then
    echo "❌ Error: scenario_analysis_with_crm.json not found"
    echo "   The enrichment script may not have completed successfully"
    exit 1
fi

echo "✅ Found fouad_tickets_analysis_with_crm.json ($(du -h fouad_tickets_analysis_with_crm.json | cut -f1))"
echo "✅ Found scenario_analysis_with_crm.json ($(du -h scenario_analysis_with_crm.json | cut -f1))"

# Show preview of results
echo ""
echo "📊 Preview of enrichment stats:"
python3 -c "
import json
with open('fouad_tickets_analysis_with_crm.json', 'r') as f:
    data = json.load(f)
    stats = data.get('enrichment_stats', {})
    print(f\"  Total tickets: {stats.get('total', 0)}\")
    print(f\"  With CRM deal: {stats.get('with_deal', 0)}\")
    print(f\"  Amount = 20€ (Uber): {stats.get('amount_20', 0)}\")
    print(f\"  Amount ≠ 20€ (HORS): {stats.get('amount_other', 0)}\")
"

echo ""
echo "📊 Preview of scenario comparison:"
python3 -c "
import json
with open('scenario_analysis_with_crm.json', 'r') as f:
    data = json.load(f)
    comp = data.get('comparison', {})
    print(f\"  Before (false positives): {comp.get('before', 0)}\")
    print(f\"  After (real HORS_PARTENARIAT): {comp.get('after', 0)}\")
    print(f\"  Reduction: {comp.get('reduction', 0)} ({comp.get('reduction', 0) / max(comp.get('before', 1), 1) * 100:.1f}%)\")
"

# Confirm before pushing
echo ""
read -p "🚀 Push these results to git? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 0
fi

# Git operations
echo ""
echo "📤 Pushing to git..."

git add fouad_tickets_analysis_with_crm.json scenario_analysis_with_crm.json

git commit -m "Add CRM enrichment results for 100 Fouad tickets

- Enriched tickets with CRM Deal data (Amount field)
- Re-analyzed scenarios with correct HORS_PARTENARIAT logic
- Results: $(python3 -c "import json; data=json.load(open('scenario_analysis_with_crm.json')); print(f\"{data['comparison']['after']} real HORS_PARTENARIAT vs {data['comparison']['before']} false positives before\")")"

git push origin claude/zoho-ticket-automation-wb1xw

echo ""
echo "================================================================================"
echo "✅ RESULTS PUSHED SUCCESSFULLY"
echo "================================================================================"
echo ""
echo "Claude can now analyze the enriched data and validate the results."
