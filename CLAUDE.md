# CLAUDE.md - Guide du Projet A-Level Saver

## Vue d'ensemble

Système d'automatisation des tickets Zoho Desk pour CAB Formations (formation VTC Uber).
Le workflow traite les tickets DOC en utilisant plusieurs agents spécialisés et sources de données.

---

## RÈGLE D'OR : Ne Pas Réinventer la Roue

Avant de coder une nouvelle fonctionnalité, **TOUJOURS vérifier** si elle existe déjà dans :
1. Les agents (`src/agents/`)
2. Les helpers (`src/utils/`)
3. Le client Zoho (`src/zoho_client.py`)

---

## Architecture des Agents

### 1. CRMOpportunityAgent (`src/agents/crm_agent.py`)
**Agent spécialisé pour les mises à jour CRM Zoho.**

```python
from src.agents.crm_agent import CRMOpportunityAgent

agent = CRMOpportunityAgent()
result = agent.process({
    "deal_id": "123456",
    "auto_update": True,      # Applique les mises à jour automatiquement
    "auto_add_note": True     # Ajoute une note au deal
})
```

**Méthodes disponibles :**
- `process(data)` - Analyse et met à jour un deal
- `process_with_ticket(deal_id, ticket_id, ticket_analysis)` - Met à jour un deal dans le contexte d'un ticket
- `find_opportunities_needing_attention()` - Trouve les deals qui nécessitent une action

### 2. DealLinkingAgent (`src/agents/deal_linking_agent.py`)
**Lie les tickets Zoho Desk aux deals CRM.**

```python
from src.agents.deal_linking_agent import DealLinkingAgent

agent = DealLinkingAgent()
result = agent.process({"ticket_id": "123456"})
# Retourne: deal_id, deal_data, all_deals, routing info
```

### 3. ResponseGeneratorAgent (`src/agents/response_generator_agent.py`)
**Génère les réponses aux tickets avec Claude + RAG.**

```python
from src.agents.response_generator_agent import ResponseGeneratorAgent

agent = ResponseGeneratorAgent()
result = agent.generate_with_validation_loop(
    ticket_subject="...",
    customer_message="...",
    crm_data={...},
    exament3p_data={...}
)
# Retourne: response_text, crm_updates, detected_scenarios, etc.
```

**Important :** L'agent extrait automatiquement les mises à jour CRM via le bloc `[CRM_UPDATES]...[/CRM_UPDATES]`.

### 4. ExamT3PAgent (`src/agents/examt3p_agent.py`)
**Extrait les données de la plateforme ExamT3P.**

```python
from src.agents.examt3p_agent import ExamT3PAgent

agent = ExamT3PAgent()
data = agent.extract_data(identifiant, mot_de_passe)
# Retourne: documents, paiements, examens, statut_dossier, etc.
```

### 5. TicketDispatcherAgent (`src/agents/dispatcher_agent.py`)
**Route les tickets vers le bon département.**

---

## Helpers Existants (NE PAS RECODER)

### Synchronisation ExamT3P → CRM (`src/utils/examt3p_crm_sync.py`)

```python
from src.utils.examt3p_crm_sync import (
    sync_examt3p_to_crm,           # Sync complète ExamT3P → CRM
    sync_exam_date_from_examt3p,   # Sync date d'examen
    find_exam_session_by_date_and_dept,  # IMPORTANT: Trouve l'ID session par date + département
    determine_evalbox_from_examt3p,      # Mapping statut ExamT3P → Evalbox
    can_modify_exam_date,                # Vérifie si on peut modifier la date (règle VALIDE CMA)
)
```

**CRITIQUE :** Pour mapper une date string vers un ID de session CRM :
```python
session = find_exam_session_by_date_and_dept(crm_client, "2026-03-31", "75")
session_id = session.get('id')  # Utiliser cet ID pour update_deal
```

### Gestion des identifiants ExamT3P (`src/utils/examt3p_credentials_helper.py`)

```python
from src.utils.examt3p_credentials_helper import get_credentials_with_validation

result = get_credentials_with_validation(
    deal_data=deal_data,
    threads=threads_data,
    examt3p_agent=agent
)
# Retourne: identifiant, mot_de_passe, compte_existe, should_respond_to_candidate
```

### Analyse Date Examen VTC (`src/utils/date_examen_vtc_helper.py`)

```python
from src.utils.date_examen_vtc_helper import analyze_exam_date_situation

result = analyze_exam_date_situation(
    deal_data=deal_data,
    threads=threads_data,
    crm_client=crm_client,
    examt3p_data=examt3p_data
)
# Retourne: case (1-5), next_dates, should_include_in_response, response_message
```

### Sessions de Formation (`src/utils/session_helper.py`)

```python
from src.utils.session_helper import analyze_session_situation

result = analyze_session_situation(
    deal_data=deal_data,
    exam_dates=next_dates,  # Liste des dates d'examen
    threads=threads_data,
    crm_client=crm_client
)
# Retourne: session_preference (jour/soir), proposed_options avec sessions IDs
```

### Éligibilité Uber 20€ (`src/utils/uber_eligibility_helper.py`)

```python
from src.utils.uber_eligibility_helper import analyze_uber_eligibility

result = analyze_uber_eligibility(deal_data)
# Retourne: is_uber_20_deal, case (A/B/C/PROSPECT), is_eligible
```

### Notes CRM (`src/utils/crm_note_logger.py`)

```python
from src.utils.crm_note_logger import (
    log_examt3p_sync,
    log_ticket_update,
    log_uber_eligibility_check,
    log_response_sent
)
```

### Cohérence Formation/Examen (`src/utils/training_exam_consistency_helper.py`)

```python
from src.utils.training_exam_consistency_helper import analyze_training_exam_consistency

result = analyze_training_exam_consistency(deal_data, threads, session_data, crm_client)
# Détecte les cas: formation manquée + examen imminent
```

---

## Client Zoho (`src/zoho_client.py`)

### ZohoDeskClient

```python
from src.zoho_client import ZohoDeskClient

client = ZohoDeskClient()
ticket = client.get_ticket(ticket_id)
threads = client.get_all_threads_with_full_content(ticket_id)  # TOUJOURS utiliser cette méthode
client.create_ticket_reply_draft(ticket_id, content, content_type="html")
client.update_ticket(ticket_id, {"cf": {"cf_opportunite": "..."}})
client.move_ticket_to_department(ticket_id, "Contact")
```

### ZohoCRMClient

```python
from src.zoho_client import ZohoCRMClient

client = ZohoCRMClient()
deal = client.get_deal(deal_id)
client.update_deal(deal_id, {"Field_Name": value})  # ATTENTION: certains champs attendent des IDs
client.add_deal_note(deal_id, note_title, note_content)
client.search_deals(criteria="(Email:equals:test@example.com)")
```

**ATTENTION - Champs Lookup :**
- `Date_examen_VTC` → Attend un **ID** (bigint), pas une date string
- `Session_choisie` → Attend un **ID** (bigint), pas un nom de session
- Utiliser `find_exam_session_by_date_and_dept()` pour obtenir l'ID

---

## Workflow Principal (`src/workflows/doc_ticket_workflow.py`)

```
1. AGENT TRIEUR    → Triage (GO/ROUTE/SPAM)
2. AGENT ANALYSTE  → Extraction données 6 sources
3. AGENT RÉDACTEUR → Génération réponse Claude + RAG
4. CRM NOTE        → Note dans le deal
5. TICKET UPDATE   → Tags, statut
6. DEAL UPDATE     → Mise à jour champs CRM (Date_examen_VTC, Session_choisie)
7. DRAFT CREATION  → Brouillon Zoho Desk
8. FINAL VALIDATION
```

---

## Règles Métier Critiques

### Mapping ExamT3P → Evalbox
| ExamT3P | Evalbox CRM |
|---------|-------------|
| En cours de composition | Dossier crée |
| En attente de paiement | Pret a payer |
| En cours d'instruction | Dossier Synchronisé |
| Incomplet | Refusé CMA |
| Valide | VALIDE CMA |
| En attente de convocation | Convoc CMA reçue |

### Blocage Modification Date Examen
**NE JAMAIS modifier `Date_examen_VTC` automatiquement si :**
- Evalbox ∈ {"VALIDE CMA", "Convoc CMA reçue"}
- ET `Date_Cloture_Inscription` < aujourd'hui

→ Seule solution : justificatif de force majeure (action humaine)

### Cas Uber 20€
- **CAS A** : Payé 20€ mais dossier non envoyé → Demander les documents
- **CAS B** : Dossier envoyé mais test non passé → Demander de passer le test
- **CAS C** : Éligible → Peut être inscrit à l'examen

---

## Structure des Données

### crm_updates (extrait par IA)
```python
{
    'Date_examen_VTC': '2026-03-31',      # Date string → À MAPPER vers ID
    'Session_choisie': 'Formation soir...', # Nom → À MAPPER vers ID
    'Preference_horaire': 'soir'           # Texte simple, pas de mapping
}
```

### examt3p_data
```python
{
    'compte_existe': True,
    'identifiant': 'email@example.com',
    'mot_de_passe': '****',
    'statut_dossier': 'En cours de composition',
    'documents': [...],
    'paiements': [...],
    'departement': '75'
}
```

---

## Commandes Utiles

```bash
# Lister les tickets récents
python list_recent_tickets.py

# Tester le workflow complet
python test_doc_workflow_with_examt3p.py <ticket_id>

# Tester la génération de réponse seule
python -c "from src.agents.response_generator_agent import ResponseGeneratorAgent; ..."
```

---

## À Faire Avant de Coder

1. **Chercher dans les helpers** : `grep -r "fonction_recherchée" src/utils/`
2. **Vérifier les agents** : `ls src/agents/`
3. **Lire ce fichier** : Les fonctions sont documentées ici
4. **Ne pas dupliquer** : Si une fonction existe, l'utiliser !
