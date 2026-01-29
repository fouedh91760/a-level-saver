# Architecture Système A-Level Saver

## Vue d'Ensemble

Système d'automatisation des tickets Zoho Desk pour CAB Formations (formation VTC Uber).
Le workflow traite les tickets DOC en utilisant plusieurs agents spécialisés et sources de données.

**Stack technique :**
- Python 3.11+
- Anthropic Claude (Sonnet pour agents, Haiku pour tâches légères)
- Zoho Desk & CRM APIs (OAuth2)
- Playwright/Selenium (scraping ExamT3P)
- YAML (configuration états/intentions)
- Handlebars (templates)

---

## Structure du Projet

```
a-level-saver/
├── src/                              # Code applicatif principal
│   ├── agents/                       # Agents IA spécialisés
│   │   ├── triage_agent.py           # Triage tickets (GO/ROUTE/SPAM)
│   │   ├── crm_update_agent.py       # Mises à jour CRM
│   │   ├── deal_linking_agent.py     # Liaison ticket↔deal
│   │   ├── examt3p_agent.py          # Extraction données ExamT3P
│   │   ├── dispatcher_agent.py       # Routage départements
│   │   └── base_agent.py             # Classe abstraite agents
│   │
│   ├── state_engine/                 # Moteur d'états déterministe
│   │   ├── state_detector.py         # Détection multi-états
│   │   └── template_engine.py        # Sélection et rendu templates
│   │
│   ├── utils/                        # Helpers métier
│   │   ├── date_examen_vtc_helper.py # Analyse dates examen (10 cas)
│   │   ├── examt3p_crm_sync.py       # Sync ExamT3P↔CRM
│   │   ├── session_helper.py         # Sélection sessions
│   │   ├── uber_eligibility_helper.py# Cas Uber A/B/D/E
│   │   ├── crm_lookup_helper.py      # Enrichissement lookups
│   │   ├── examt3p_credentials_helper.py # Extraction identifiants
│   │   ├── response_humanizer.py     # Reformulation IA
│   │   ├── alerts_helper.py          # Alertes temporaires
│   │   ├── date_utils.py             # Parsing dates flexible
│   │   └── training_exam_consistency_helper.py # Cohérence formation/examen
│   │
│   ├── workflows/                    # Orchestration
│   │   └── doc_ticket_workflow.py    # Workflow principal 8 étapes
│   │
│   ├── zoho_client.py                # Clients API Zoho (Desk + CRM)
│   ├── ticket_deal_linker.py         # Liaison tickets↔deals
│   └── orchestrator.py               # Coordination agents
│
├── states/                           # Configuration State Engine
│   ├── candidate_states.yaml         # Source vérité états (38+)
│   ├── state_intention_matrix.yaml   # Intentions (37+) + matrice
│   ├── blocks/                       # Blocs réutilisables (.md)
│   ├── VARIABLES.md                  # Documentation variables Handlebars
│   └── templates/
│       ├── response_master.html      # Template master universel
│       ├── base_legacy/              # 62 templates legacy (fallback)
│       └── partials/                 # Fragments modulaires
│           ├── intentions/           # Réponses intentions (14)
│           ├── statuts/              # Affichage statuts (7)
│           ├── actions/              # Actions requises (10)
│           ├── uber/                 # Conditions Uber (5)
│           ├── resultats/            # Résultats examen (3)
│           ├── report/               # Report date (3)
│           ├── credentials/          # Problèmes identifiants (2)
│           └── dates/                # Proposition dates (1)
│
├── alerts/                           # Alertes temporaires
│   └── active_alerts.yaml            # Alertes actives (éditable)
│
├── examples/                         # Scripts d'exemple
├── tests/                            # Tests unitaires
├── docs/                             # Documentation détaillée
├── config.py                         # Configuration Pydantic
├── main.py                           # Point d'entrée CLI
└── CLAUDE.md                         # Guide projet (règles critiques)
```

---

## Workflow Principal (8 Étapes)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DOC TICKET WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  STEP 1: TRIAGE AGENT                                               │
│  ├─→ Input: ticket content, deal data                               │
│  ├─→ Output: action (GO/ROUTE/SPAM), intent, session_preference     │
│  └─→ GATES: ROUTE→transfer, SPAM→close, DUPLICATE_UBER→special      │
│                                                                     │
│  STEP 2: ANALYSIS (6 sources)                                       │
│  ├─→ Ticket data extraction                                         │
│  ├─→ Deal linking (DealLinkingAgent)                                │
│  ├─→ ExamT3P credentials + data                                     │
│  ├─→ Date exam analysis (10 cas)                                    │
│  ├─→ Session selection                                              │
│  └─→ Uber eligibility check (A/B/D/E)                               │
│                                                                     │
│  STEP 3: STATE DETECTION (déterministe)                             │
│  ├─→ Évalue candidate_states.yaml par priorité                      │
│  └─→ Retourne: blocking/warning/info states                         │
│                                                                     │
│  STEP 4: TEMPLATE RENDERING                                         │
│  ├─→ Lookup STATE:INTENTION dans matrice                            │
│  ├─→ Charge template + partials                                     │
│  └─→ Remplace variables Handlebars                                  │
│                                                                     │
│  STEP 5: HUMANIZATION (optionnel)                                   │
│  ├─→ Claude Sonnet reformule                                        │
│  ├─→ Valide préservation données                                    │
│  └─→ Retourne original si validation échoue                         │
│                                                                     │
│  STEP 6: CRM UPDATES                                                │
│  ├─→ Extrait mises à jour suggérées                                 │
│  ├─→ Applique règles métier (blocage VALIDE CMA)                    │
│  └─→ Crée note consolidée                                           │
│                                                                     │
│  STEP 7: DRAFT CREATION                                             │
│  └─→ Crée brouillon Zoho Desk (attente validation humaine)          │
│                                                                     │
│  STEP 8: VALIDATION                                                 │
│  └─→ Vérifie tous les champs requis présents                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Sources de Données (6 sources)

| # | Source | Agent/Helper | Données extraites |
|---|--------|--------------|-------------------|
| 1 | Ticket Zoho Desk | `ZohoDeskClient` | Sujet, contenu, threads, pièces jointes |
| 2 | Deal CRM | `DealLinkingAgent` | Champs deal, statut Evalbox, dates, montant |
| 3 | ExamT3P | `ExamT3PAgent` | Statut dossier, documents, paiements, num_dossier |
| 4 | Sessions CRM | `session_helper` | Sessions disponibles (jour/soir) |
| 5 | Dates examen CRM | `date_examen_vtc_helper` | Prochaines dates, départements |
| 6 | Alertes temporaires | `alerts_helper` | Bugs en cours, situations spéciales |

---

## Structures de Données Principales

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
    'connection_test_success': True,
    'identifiant': 'email@example.com',
    'mot_de_passe': '****',
    'credentials_source': 'crm',  # ou 'threads'
    'statut_dossier': 'En cours de composition',
    'num_dossier': '00038886',
    'documents': [...],
    'paiements': [...],
    'departement': '75'
}
```

### TriageAgent result
```python
{
    'action': 'GO' | 'ROUTE' | 'SPAM' | 'DUPLICATE_UBER',
    'target_department': 'DOC' | 'Contact' | etc,
    'detected_intent': 'DEMANDE_DATES_FUTURES',     # Intention principale
    'primary_intent': 'DEMANDE_DATES_FUTURES',      # Alias
    'secondary_intents': ['QUESTION_SESSION'],       # Intentions secondaires
    'intent_context': {
        'is_urgent': bool,
        'mentions_force_majeure': bool,
        'force_majeure_type': 'medical' | 'death' | 'accident' | 'childcare',
        'wants_earlier_date': bool,
        'session_preference': 'jour' | 'soir' | None
    }
}
```

### DetectedStates (multi-états)
```python
{
    'blocking_state': DetectedState | None,   # Si présent, stoppe workflow
    'warning_states': [DetectedState, ...],   # Alertes à inclure
    'info_states': [DetectedState, ...],      # États combinables
    'primary_state': DetectedState,           # Rétrocompatibilité
    'all_states': [DetectedState, ...]        # Tous les états détectés
}
```

---

## Points d'Entrée

### CLI (main.py)
```bash
python main.py ticket <ticket_id> [--auto-respond] [--auto-update]
python main.py deal <deal_id> [--auto-update] [--auto-add-note]
python main.py batch [--status Open] [--limit 10] [--auto-respond]
python main.py cycle [--auto-actions]
```

### Programmatique
```python
from src.workflows.doc_ticket_workflow import DOCTicketWorkflow

workflow = DOCTicketWorkflow()
result = workflow.process_ticket(ticket_id, auto_create_draft=False)
```

### Scripts d'analyse
```bash
python analyze_lot.py 11 20           # Analyser tickets 11-20
python list_recent_tickets.py         # Lister tickets DOC ouverts
python close_spam_tickets.py data.json # Clôturer SPAM
```

---

## Clients API Zoho

### ZohoDeskClient
```python
from src.zoho_client import ZohoDeskClient

client = ZohoDeskClient()
ticket = client.get_ticket(ticket_id)
threads = client.get_all_threads_with_full_content(ticket_id)
client.create_ticket_reply_draft(ticket_id, content, content_type="html")
client.update_ticket(ticket_id, {"cf": {"cf_opportunite": "..."}})
client.move_ticket_to_department(ticket_id, "Contact")
```

### ZohoCRMClient
```python
from src.zoho_client import ZohoCRMClient

client = ZohoCRMClient()
deal = client.get_deal(deal_id)
client.update_deal(deal_id, {"Field_Name": value})
client.add_deal_note(deal_id, note_title, note_content)
client.search_deals(criteria="(Email:equals:test@example.com)")
client.get_record('Dates_Examens_VTC_TAXI', record_id)  # Enrichir lookup
```

---

## Configuration

### Variables d'environnement (.env)
```
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REFRESH_TOKEN=...
ANTHROPIC_API_KEY=...
```

### config.py (Pydantic Settings)
```python
from config import settings

settings.zoho_client_id
settings.anthropic_api_key
settings.agent_model  # claude-sonnet-4-5-20250929
```

---

## Diagrammes

Voir `docs/architecture-diagrams.md` pour les diagrammes Mermaid détaillés :
- Workflow complet
- State Engine flow
- Template selection
- Data flow

---

## Coûts API (estimation par ticket)

| Composant | Modèle | Coût |
|-----------|--------|------|
| Extraction identifiants | Haiku 3.5 | ~$0.001 |
| Agent Trieur | Haiku 3.5 | ~$0.001 |
| Agent Rédacteur | Sonnet 4.5 | ~$0.036 |
| Next steps note CRM | Haiku 3.5 | ~$0.001 |
| **Total** | | **~$0.04** |
