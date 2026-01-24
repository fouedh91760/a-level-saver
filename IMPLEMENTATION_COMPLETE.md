# ✅ Implementation Complete: New Workflow

## 🎯 What Was Implemented

Complete redesign of the ticket routing workflow to use CRM deal data as the primary routing mechanism.

### Previous Workflow (INCORRECT)
```
Ticket → Routing (keywords only) → Deal Linking → Processing
```
**Problem**: Routing couldn't access deal information, leading to imprecise department assignment.

### New Workflow (CORRECT)
```
Ticket → Deal Linking (email from thread) → Routing (deal-based) → Processing → CRM Update
```
**Advantage**: Department is determined by customer's CRM deal context, not just ticket keywords.

---

## 📦 Components Modified

### 1. `src/agents/deal_linking_agent.py` (MAJOR REWRITE)

#### New Workflow Implementation:
1. **Extract email from THREAD** (not ticket contact)
   - More accurate: uses customer's actual email from conversation
   - Prioritizes incoming customer emails
   - Fallback to ticket contact if no thread email found

2. **Search ALL contacts in CRM** with that email
   - Multiple contacts may share the same email
   - We need ALL of them to find ALL deals

3. **Retrieve ALL deals** for those contacts
   - One contact may have multiple deals
   - Different amounts: €20, €500, etc.
   - Different stages: GAGNÉ, EN ATTENTE, PERDU

4. **Determine department** using `BusinessRules.determine_department_from_deals_and_ticket()`
   - Priority 1: 20€ deals GAGNÉ (most recent by Closing_Date)
   - Priority 2: 20€ deals EN ATTENTE
   - Check EVALBOX field (Refusé CMA, Documents refusés, Documents manquants)
   - Check last thread for document submission (30+ keywords)
   - Priority 3: Other amounts GAGNÉ/EN ATTENTE → Contact
   - Fallback: Keywords or AI

5. **Return comprehensive result**:
   - `email`: Email extracted from threads
   - `contacts_found`: Number of CRM contacts
   - `deals_found`: Total deals retrieved
   - `all_deals`: List of ALL deals
   - `selected_deal`: The deal chosen by routing logic
   - `recommended_department`: Department from BusinessRules
   - `routing_explanation`: Detailed explanation

#### New Helper Methods:
- `_get_crm_client()`: Lazy CRM client initialization
- `_extract_email_from_thread()`: Extract from single thread
- `_extract_email_from_threads()`: Get from most recent customer thread
- `_search_contacts_by_email()`: CRM contacts search
- `_get_deals_for_contacts()`: Retrieve all deals for contact IDs

---

### 2. `src/agents/dispatcher_agent.py` (UPDATED)

#### New Priority Order:
1. **HIGHEST PRIORITY**: Use `recommended_department` from DealLinkingAgent
   - Already calculated using complete business logic
   - Considers ALL deals, not just one
   - Includes document detection from thread content
   - Confidence: 98%

2. **Fallback**: Old deal-based routing (backward compatibility)
   - For code that still passes `deal` parameter directly
   - Uses `BusinessRules.get_department_from_deal()`

3. **Fallback**: Business rules keywords
   - When no deal found or deal doesn't match routing rules

4. **Fallback**: AI analysis
   - Last resort when nothing else matches

#### New Parameters:
- `linking_result`: Full result from DealLinkingAgent (RECOMMENDED)
- `deal`: Single deal object (DEPRECATED, for backward compatibility)

---

### 3. `src/orchestrator.py` (UPDATED)

#### Changes:
- Now passes `linking_result` (full object) to dispatcher instead of just `deal`
- Dispatcher can access `recommended_department` directly
- No need to recalculate routing logic

---

## 🧪 Testing

### Test Script: `test_new_workflow.py`

Run comprehensive tests:

```bash
# Test deal linking only
python test_new_workflow.py <ticket_id>

# Test complete workflow
python test_new_workflow.py <ticket_id> --full-workflow
```

### Test Scenarios:

1. **20€ GAGNÉ deal** → Should route to **DOC**
   ```bash
   python test_new_workflow.py 123456789
   ```

2. **CMA Closed Lost** → Should route to **Refus CMA**
   ```bash
   python test_new_workflow.py 123456790
   ```

3. **Document submission detected** → Should route to **Refus CMA**
   - Customer sends "ci-joint mon passeport"
   - Last thread contains document keywords

4. **No deals found** → Should fallback to **keywords**
   - New customer without CRM history

5. **Multiple deals** → Should select **correct one**
   - Customer has €20 GAGNÉ + €500 EN ATTENTE
   - Should prioritize €20 GAGNÉ

---

## 📋 Business Rules Used

The implementation uses the complete logic from `business_rules.py`:

### `determine_department_from_deals_and_ticket()`

```python
Priority 1: 20€ deals GAGNÉ (most recent closing_date)
Priority 2: 20€ deals EN ATTENTE
Condition checks:
  - EVALBOX = "Refusé CMA" → Refus CMA
  - EVALBOX = "Documents refusés" → Refus CMA
  - EVALBOX = "Documents manquants" → Refus CMA
  - Last thread contains document keywords → Refus CMA
  - Else → DOC
Priority 3: Other amounts (GAGNÉ or EN ATTENTE) → Contact
Fallback: None (keywords or AI will handle)
```

### Document Keywords (30+)

Detected in last thread content:
- **Générique**: ci-joint, pièce jointe, document, fichier, attachment
- **Identité**: CNI, passeport, carte d'identité, titre de séjour, récépissé
- **Domicile**: justificatif de domicile, attestation d'hébergement
- **Signature**: signature, signé

Full list: See `DOCUMENT_KEYWORDS.md`

---

## 🔍 How to Debug

### Enable Detailed Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Test Output

After running `test_new_workflow.py`, check:
- `test_results_<ticket_id>.json` - Full results in JSON format

### Key Logging Points

1. **DealLinkingAgent**:
   - Email extraction: `"Extracted email from thread: <email>"`
   - Contacts found: `"Found X contacts with email <email>"`
   - Deals found: `"Total deals found: X"`
   - Routing result: `"Routing result: <explanation>"`

2. **DispatcherAgent**:
   - Priority used: `"Using department from DealLinkingAgent: <dept>"`
   - Fallback: `"Deal-based routing determined: <dept>"`
   - Keywords: `"Rule-based routing determined: <dept>"`
   - AI: `"Using AI analysis for department routing"`

---

## 📊 Expected Results

### Example 1: Uber €20 Customer

**Scenario**: Customer with "Uber €20 - Mohammed Talbi" deal (GAGNÉ)

**Input**: Ticket with subject "Question sur ma formation"

**Expected Flow**:
1. Email extracted from thread: `mohammed.talbi@gmail.com`
2. Contacts found: 1
3. Deals found: 1 (Uber €20 - GAGNÉ)
4. Selected deal: Uber €20 - GAGNÉ
5. **Department: DOC** (20€ GAGNÉ → DOC)
6. Confidence: 98%
7. Method: deal_linking_agent

### Example 2: CMA Refusé

**Scenario**: Customer with "CMA - Registration - Ahmed Benali" deal (Closed Lost)

**Input**: Ticket with subject "Pourquoi mon dossier a été refusé ?"

**Expected Flow**:
1. Email extracted from thread: `ahmed.benali@outlook.fr`
2. Contacts found: 1
3. Deals found: 1 (CMA - PERDU)
4. Selected deal: CMA - PERDU
5. **Department: Refus CMA** (CMA + Closed Lost → Refus CMA)
6. Confidence: 98%
7. Method: deal_linking_agent

### Example 3: Document Submission

**Scenario**: Customer with "Uber €20" (GAGNÉ) + thread contains "ci-joint mon passeport"

**Expected Flow**:
1. Email extracted from thread
2. Deals found: Uber €20 - GAGNÉ
3. Last thread content: "Bonjour, ci-joint mon passeport et ma CNI..."
4. Document keywords detected: ✅ (ci-joint, passeport, CNI)
5. **Department: Refus CMA** (document submission detected)
6. Confidence: 98%
7. Method: deal_linking_agent

### Example 4: No Deals (Fallback)

**Scenario**: New customer without CRM history

**Input**: Ticket with subject "Je veux m'inscrire pour l'examen VTC"

**Expected Flow**:
1. Email extracted from thread: `nouveau.client@gmail.com`
2. Contacts found: 0
3. Deals found: 0
4. **Fallback to keywords**: "examen", "vtc" → DOC
5. **Department: DOC** (keyword-based)
6. Confidence: 95%
7. Method: business_rules

---

## 🚀 Next Steps

### 1. Test with Real Tickets

Run the test script with actual ticket IDs from your Zoho Desk:

```bash
# Find a ticket with a 20€ deal
python test_new_workflow.py <ticket_id>
```

### 2. Review Test Results

Check the generated `test_results_<ticket_id>.json` file:
- Verify email extraction is correct
- Confirm deals are found
- Check department recommendation matches expectations

### 3. Validate Edge Cases

Test these scenarios:
- [ ] Customer with NO CRM contact
- [ ] Customer with multiple contacts (same email)
- [ ] Customer with multiple deals (different amounts)
- [ ] Customer with EVALBOX = "Refusé CMA"
- [ ] Thread with document keywords
- [ ] Thread without customer email (agent reply only)

### 4. Enable in Production

Once tests pass, enable auto-reassignment:

```python
orchestrator.process_ticket_complete_workflow(
    ticket_id=ticket_id,
    auto_dispatch=True,  # Enable auto-reassignment
    auto_link=True,      # Enable auto-linking
    auto_respond=False,  # Keep manual for now
    auto_update_ticket=False,
    auto_update_deal=True,     # Enable CRM updates
    auto_add_note=True         # Enable automatic notes
)
```

### 5. Monitor and Adjust

- Track routing accuracy
- Monitor reassignment frequency
- Adjust business rules if needed
- Add new document keywords as discovered

---

## 📚 Related Documentation

- `business_rules.py` - Complete business logic
- `ROUTING_WORKFLOW.md` - Workflow architecture
- `DOCUMENT_KEYWORDS.md` - Document detection keywords
- `crm_deal_fields_reference.json` - CRM field definitions
- `fouad_tickets_analysis.json` - Analysis of 100 real tickets

---

## ⚠️ Important Notes

1. **Email Source**: We use THREAD email, not ticket contact email
   - Threads are more accurate (actual conversation)
   - Ticket contact can be outdated

2. **ALL Deals**: We retrieve ALL deals for a contact
   - One contact may have multiple deals
   - We select the most relevant based on priority

3. **EVALBOX Field**: Critical for Refus CMA routing
   - Values: "Refusé CMA", "Documents refusés", "Documents manquants"
   - Must match exactly (case-sensitive)

4. **Document Detection**: 30+ keywords in French
   - Checked in LAST thread only (most recent)
   - Case-insensitive matching

5. **Backward Compatibility**: Old workflow still supported
   - `deal` parameter still works in dispatcher
   - Use `linking_result` for new code

---

## 🐛 Troubleshooting

### Issue: No email found

**Symptom**: `email_found: false`

**Causes**:
1. Ticket has no threads yet
2. Thread doesn't contain email (system message)
3. Email format not recognized

**Solution**: Will fallback to ticket contact email automatically

### Issue: No contacts found

**Symptom**: `contacts_found: 0`

**Causes**:
1. Email not in CRM
2. Email typo in CRM
3. Different email address used

**Solution**: Will fallback to keyword routing

### Issue: No deals found

**Symptom**: `deals_found: 0` but `contacts_found: 1`

**Causes**:
1. Contact exists but has no deals
2. Contact has deals but wrong Contact_Name field

**Solution**: Will fallback to keyword routing

### Issue: Wrong department recommended

**Symptom**: Department doesn't match expectations

**Debug**:
1. Check `routing_explanation` in result
2. Verify deal Stage and Amount
3. Check EVALBOX field value
4. Review last thread content
5. Confirm business rules in `business_rules.py`

---

## ✅ Validation Checklist

- [x] DealLinkingAgent extracts email from threads
- [x] Searches ALL contacts by email
- [x] Retrieves ALL deals for contacts
- [x] Calls BusinessRules with complete data
- [x] Returns comprehensive result with explanation
- [x] DispatcherAgent uses recommended_department
- [x] Orchestrator passes linking_result to dispatcher
- [x] Backward compatibility maintained
- [x] Test script created
- [x] Documentation complete
- [ ] Tested with real tickets (YOUR TURN!)
- [ ] Validated in production

---

**Status**: ✅ Implementation complete. Ready for testing.

**Last Updated**: 2026-01-24

**Developer**: Claude (Anthropic)
