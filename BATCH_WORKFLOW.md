# BATCH WORKFLOW - Traitement des Tickets DOC

## Script Principal
```
run_workflow_batch.py
```

## Fichiers de Données
| Fichier | Description |
|---------|-------------|
| `doc_tickets_pending.json` | Liste des tickets à traiter (859 au 03/02/2026) |
| `doc_tickets_processed.json` | Historique des tickets traités |
| `data/batch_results_<timestamp>.json` | Résultats détaillés de chaque batch |

## Process Standard

### 1. Vérifier le statut
```bash
python run_workflow_batch.py --status
```

### 2. Demander à l'utilisateur combien de tickets traiter
**IMPORTANT**: Toujours demander avant de lancer un batch.

### 3. Lancer le batch
```bash
# Production (crée les drafts, met à jour CRM)
python run_workflow_batch.py --count <N>

# Test dry-run (pas de modification)
python run_workflow_batch.py --count <N> --dry-run
```

### 4. Les tickets traités sont automatiquement retirés de `doc_tickets_pending.json`

## Commandes Disponibles

| Commande | Description |
|----------|-------------|
| `--status` ou `-s` | Affiche le nombre de tickets en attente et traités |
| `--count N` ou `-n N` | Traite N tickets (défaut: 10) |
| `--dry-run` ou `-d` | Mode test sans création de draft/CRM |
| `--ticket ID` ou `-t ID` | Traite un ticket spécifique |
| `--delay X` | Délai entre tickets en secondes (défaut: 2.0) |

## Exemples

```bash
# Statut actuel
python run_workflow_batch.py --status

# Traiter 5 tickets en production
python run_workflow_batch.py --count 5

# Traiter 20 tickets avec délai de 3s
python run_workflow_batch.py --count 20 --delay 3

# Test sur 10 tickets sans modification
python run_workflow_batch.py --count 10 --dry-run

# Retraiter un ticket spécifique
python run_workflow_batch.py --ticket 198709000449714052
```

## Ordre de Traitement
- Les tickets sont traités du **plus récent au plus ancien** (tri par `createdTime` desc)
- Chaque ticket traité est retiré de `doc_tickets_pending.json`
- Les résultats sont sauvegardés dans `doc_tickets_processed.json`

## Structure des Fichiers

### doc_tickets_pending.json
```json
[
  {
    "id": "198709000449749722",
    "ticketNumber": "12345",
    "subject": "Inscription",
    "createdTime": "2026-02-02T..."
  }
]
```

### doc_tickets_processed.json
```json
[
  {
    "id": "198709000449714052",
    "processed_at": "2026-02-03T00:12:36",
    "success": true,
    "workflow_stage": "COMPLETED",
    "triage_action": "GO",
    "primary_intent": "DEMANDE_CHANGEMENT_SESSION",
    "draft_created": true
  }
]
```

## Régénérer la Liste des Tickets

Si besoin de recharger la liste depuis Zoho Desk :
```bash
python -c "
from src.zoho_client import ZohoDeskClient
import json, time

desk = ZohoDeskClient()
doc_dept_id = '198709000025523146'
all_tickets = []
from_index = 0

while True:
    result = desk._make_request('GET', 'https://desk.zoho.com/api/v1/tickets', params={
        'departmentId': doc_dept_id,
        'status': 'Open',
        'limit': 100,
        'from': from_index,
        'sortBy': '-createdTime'
    })
    data = result.get('data', [])
    if not data:
        break
    all_tickets.extend(data)
    print(f'Page {from_index//100 + 1}: {len(all_tickets)} tickets')
    from_index += len(data)
    if len(data) < 100:
        break
    time.sleep(0.2)

ticket_list = [{
    'id': t.get('id'),
    'ticketNumber': t.get('ticketNumber'),
    'subject': t.get('subject', '')[:80],
    'createdTime': t.get('createdTime')
} for t in all_tickets]

with open('doc_tickets_pending.json', 'w', encoding='utf-8') as f:
    json.dump(ticket_list, f, ensure_ascii=False, indent=2)

print(f'Sauvegardé {len(ticket_list)} tickets')
"
```

## Notes
- Délai de 2s entre tickets pour respecter le rate limit Zoho
- Chaque ticket prend environ 1min30 à traiter (workflow complet)
- Estimation: 10 tickets = ~17 minutes

---

## Session du 03/02/2026

### Progression
| Métrique | Valeur |
|----------|--------|
| Tickets initiaux | 859 |
| Traités | 155 |
| Restants | 704 |
| Taux de succès | 100% |
| Drafts créés | 111 |

### Répartition par Action
| Action | Count | Description |
|--------|-------|-------------|
| GO | 97 | Workflow complet, draft créé |
| ROUTE | 43 | Routé vers autre département (Refus CMA, Contact, etc.) |
| NEEDS_CLARIFICATION | 13 | Candidat non trouvé, demande de clarification |
| DUPLICATE_UBER | 2 | Doublon offre Uber 20€ |

### Fichiers de Logs
```
data/batch_results_20260203_004229.json   (5 tickets)
data/batch_results_20260203_010732.json   (10 tickets)
data/batch_results_20260203_012331.json   (20 tickets)
data/batch_results_20260203_020453.json   (50 tickets)
data/batch_results_20260203_044706.json   (20 tickets)
data/batch_results_20260203_055437.json   (50 tickets)
```

### Fix Appliqué : Date d'Examen Passée

**Problème détecté :** 6 tickets avec incohérences de dates (examen passé mais workflow continuait)

**Solution implémentée :** `src/workflows/doc_ticket_workflow.py`
- Si date d'examen passée (CAS 2, 7, 8) → STOP workflow
- Stage: `STOPPED_EXAM_DATE_PASSED`
- Pas de mise à jour CRM
- Création d'une note explicative pour traitement humain

**Note créée automatiquement :**
```
⚠️ À TRAITER MANUELLEMENT - DATE D'EXAMEN PASSÉE

La date d'examen dans Zoho CRM est dans le passé...

📋 INFORMATIONS CANDIDAT (nom, date examen, evalbox, intention)
💬 RÉSUMÉ DES ÉCHANGES (généré par IA)
🌐 ÉTAT EXAMT3P (statut dossier, documents, examens)
🔧 ACTIONS POSSIBLES
```

### Fix Appliqué : Clôture Passée (CAS 8) - Redirect Automatique

**Problème détecté :** Ticket 198709000449429351 - Le candidat demandait une session pour l'examen du 24/02, mais la clôture d'inscription était passée. Le système confirmait la session au lieu de rediriger vers la prochaine date d'examen.

**Analyse :**
- CAS 8 = clôture passée mais examen encore futur (≠ CAS 2/7 où l'examen lui-même est passé)
- Le code vérifiait `evalbox IN PRE_PAYMENT_STATUSES` qui n'incluait pas "Documents manquants"
- CAS 8 était dans `date_passee_cases = [2, 7, 8]` ce qui stoppait le workflow à tort

**Solution implémentée :**

1. **`src/utils/date_examen_vtc_helper.py`** - Inversion de la logique :
   ```python
   # Avant: evalbox IN PRE_PAYMENT_STATUSES (whitelist)
   # Après: evalbox NOT IN BLOCKED_STATUSES (blacklist)
   BLOCKED_STATUSES_FOR_RESCHEDULE = ['VALIDE CMA', 'Convoc CMA reçue', 'Refusé CMA']
   ```

2. **`src/workflows/doc_ticket_workflow.py`** :
   - CAS 8 retiré de `date_passee_cases` (ligne 319): `date_passee_cases = [2, 7]`
   - Sessions filtrées pour nouvelle date d'examen (lignes 1989-2008)
   - Extraction sessions de `proposed_options` vers `sessions_proposees` (lignes 2777-2789)

3. **`states/templates/partials/intentions/confirmation_session.html`** - Template CAS 8 :
   ```html
   {{#if deadline_passed_reschedule}}
   ⚠️ Important : La date limite d'inscription pour l'examen du {{original_exam_date}} est dépassée.
   Vous êtes automatiquement repositionné(e) sur l'examen du {{new_exam_date}} (clôture: {{new_exam_date_cloture}}).
   {{/if}}
   ```

**Flux CAS 8 complet :**
1. Détection clôture passée pour date actuelle
2. Identification prochaine date d'examen disponible
3. Message au candidat : ancienne date fermée → nouvelle date + clôture
4. Proposition sessions pour nouvelle date (selon préférence jour/soir)
5. Mise à jour CRM avec nouvelle date d'examen
6. Attente confirmation candidat pour Session1

**Condition d'application :** `evalbox NOT IN (VALIDE CMA, Convoc CMA reçue, Refusé CMA)`

---

### Structure des Résultats (mise à jour v3)
```json
{
  "ticket_id": "198709000449...",
  "deal_id": "1456177001...",
  "success": true,
  "stage": "COMPLETED",
  "triage_action": "GO",
  "draft_created": true,

  "triage": {
    "detected_intent": "DEMANDE_CHANGEMENT_SESSION",
    "secondary_intents": ["DEMANDE_DATES_FUTURES"],
    "intent_context": {
      "session_preference": "jour",
      "is_complaint": false,
      "claimed_session": null
    }
  },

  "input": {
    "crm": {
      "deal_name": "BFS NP John DOE",
      "stage": "GAGNÉ",
      "evalbox": "Dossier Synchronisé",
      "date_examen_vtc": "34_2026-03-31",
      "session1": "1456177000...",
      "email": "john@example.com"
    },
    "examt3p": {
      "statut_dossier": "Dossier synchronisé",
      "num_dossier": "00012345",
      "documents_count": 5,
      "examens": [],
      "credentials_valid": true
    },
    "lookups": {
      "date_examen": "2026-03-31",
      "session_type": "jour",
      "session_date_debut": "2026-02-10",
      "session_date_fin": "2026-02-14"
    }
  },

  "template_vars": {
    "state_id": "DOSSIER_SYNCHRONIZED",
    "state_name": "D-5",
    "primary_intent": "DEMANDE_CHANGEMENT_SESSION",
    "secondary_intents": ["DEMANDE_DATES_FUTURES"],
    "intents_handled": ["DEMANDE_CHANGEMENT_SESSION"],
    "date_case": 5,
    "uber_case": "ELIGIBLE",
    "session_preference": "jour",
    "is_complaint": false,
    "is_cab_error": false,
    "can_modify_exam_date": true,
    "has_sessions_proposees": true,
    "report_possible": false,
    "report_bloque": false,
    "evalbox": "Dossier Synchronisé"
  },

  "output": {
    "crm_updated": true,
    "crm_updates": {"Session1": "...", "Date_examen_VTC": "..."},
    "draft_content": "<html>Bonjour John,..."
  },

  "error": null
}
```
