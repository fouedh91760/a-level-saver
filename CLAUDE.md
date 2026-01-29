# CLAUDE.md - Guide du Projet A-Level Saver

Système d'automatisation des tickets Zoho Desk pour CAB Formations (formation VTC Uber).
Le workflow traite les tickets DOC en utilisant plusieurs agents spécialisés et sources de données.

---

## ARCHITECTURE CRITIQUE : Pipeline de Réponse

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE DE RÉPONSE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. TEMPLATE ENGINE (Déterministe)                                         │
│      ├── Contient TOUTE la logique métier                                   │
│      ├── Données factuelles (dates, liens, identifiants)                    │
│      └── Structure en sections (intentions, statut, dates, actions)         │
│                               ↓                                             │
│   2. RESPONSE HUMANIZER (IA Sonnet)                                         │
│      ├── Reformule pour rendre NATUREL et EMPATHIQUE                        │
│      ├── Fusionne les sections redondantes                                  │
│      └── NE CONTIENT JAMAIS DE RÈGLES MÉTIER                                │
│                               ↓                                             │
│   3. RÉPONSE FINALE                                                         │
│      └── Humaine, structurée, pédagogique, complète                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Règle d'Or : Séparation Métier / Mise en Forme

| Composant | Responsabilité | Ce qu'il NE FAIT PAS |
|-----------|----------------|----------------------|
| **Template Engine** | Logique métier, données factuelles, explications | Mise en forme naturelle |
| **Response Humanizer** | Reformulation empathique, transitions, fluidité | Ajouter des infos métier |

**Si une info métier manque → l'ajouter dans le template, JAMAIS dans le Humanizer.**

---

## 10 RÈGLES CRITIQUES - Ne Jamais Oublier

| # | Règle | Piège à éviter | Détails |
|---|-------|----------------|---------|
| 1 | **Template/Humanizer separation** | Ajouter logique métier dans le Humanizer | `docs/TEMPLATES.md` |
| 2 | **CRM Lookups = appel API extra** | Utiliser `lookup.get('name')` directement | `docs/HELPERS.md` §2 |
| 3 | **Blocage modification date** | Modifier Date_examen_VTC si VALIDE CMA + clôture passée | `docs/BUSINESS_RULES.md` §2 |
| 4 | **Intention duality** | Ajouter intention YAML sans TriageAgent prompt | `docs/STATE_ENGINE.md` |
| 5 | **Uber 20€ one-time** | Ignorer doublon offre Uber | `docs/BUSINESS_RULES.md` §4 |
| 6 | **Multi-severity states** | Combiner états BLOCKING | `docs/STATE_ENGINE.md` |
| 7 | **Mapping ExamT3P→Evalbox** | Mauvais mapping statut | `docs/BUSINESS_RULES.md` §1 |
| 8 | **Date_test_selection READ-ONLY** | Modifier via workflow | `docs/BUSINESS_RULES.md` §5 |
| 9 | **Session preference priority** | Ignorer préférence TriageAgent | `docs/BUSINESS_RULES.md` §6 |
| 10 | **Partials = .html** | Créer partial en .md | `docs/TEMPLATES.md` |

---

## PROCESS CHECKLIST : Ajout d'un Nouveau Scénario

| # | Fichier | Action |
|---|---------|--------|
| 1 | `states/candidate_states.yaml` | Définir l'état (id, priority, severity, detection, workflow, response) |
| 2 | `src/utils/<helper>.py` | Poser le flag booléen `True` + données contexte |
| 3 | `src/state_engine/state_detector.py` | `_build_context()` + `_check_condition()` + `_collect_alerts()` |
| 4 | `states/templates/partials/<cat>/<nom>.html` | Créer le template partial (syntaxe Handlebars) |
| 5 | `src/state_engine/template_engine.py` | `_generate_alert_content()` si alerte |

**Détails complets :** `docs/STATE_ENGINE.md`

---

## PROCESS CHECKLIST : Ajout d'une Nouvelle Intention

| # | Fichier | Action |
|---|---------|--------|
| 1 | `states/state_intention_matrix.yaml` | Définir l'intention (section `intentions:`) |
| 2 | **`src/agents/triage_agent.py`** | **OBLIGATOIRE** - Ajouter dans `SYSTEM_PROMPT` |
| 3 | `states/state_intention_matrix.yaml` | Ajouter entrées matrice `"*:NOM_INTENTION"` |
| 4 | `states/templates/partials/intentions/<nom>.html` | Template partial |
| 5 | `states/templates/response_master.html` | Ajouter `{{#if intention_xxx}}` |

**CRITIQUE : Si l'intention n'est pas dans YAML ET TriageAgent → jamais détectée !**

```bash
# Vérification obligatoire
grep "NOM_INTENTION" states/state_intention_matrix.yaml
grep "NOM_INTENTION" src/agents/triage_agent.py
```

**Détails complets :** `docs/STATE_ENGINE.md`

---

## RÈGLE D'OR : Vérification Avant Codage

Avant de coder une fonctionnalité, **TOUJOURS vérifier** si elle existe :

```bash
# Lister états existants (38+)
grep -E "^  [A-Z_]+:" states/candidate_states.yaml | head -50

# Lister intentions existantes (37+)
grep -E "^  [A-Z_]+:" states/state_intention_matrix.yaml | head -50

# Chercher si similaire existe
grep -i "mot_clé" states/candidate_states.yaml
grep -i "mot_clé" states/state_intention_matrix.yaml

# Vérifier helpers existants
ls src/utils/
```

**Si l'intent/état existe (même sous un nom différent) → l'utiliser, NE PAS en créer un nouveau.**

---

## Workflow Principal (8 étapes)

```
1. TRIAGE AGENT     → GO/ROUTE/SPAM + intention + session_preference
2. ANALYSIS         → 6 sources (ticket, deal, ExamT3P, dates, sessions, uber)
3. STATE DETECTION  → Déterministe, multi-severity (BLOCKING/WARNING/INFO)
4. TEMPLATE ENGINE  → STATE×INTENTION → Template + partials
5. HUMANIZER        → Reformulation naturelle (optionnel)
6. CRM UPDATES      → Via CRMUpdateAgent (mapping auto, règles blocage)
7. DRAFT CREATION   → Brouillon Zoho Desk
8. VALIDATION       → Vérification finale
```

**Détails complets :** `docs/ARCHITECTURE.md`

---

## Sources de Vérité

| Fichier | Contenu |
|---------|---------|
| `states/candidate_states.yaml` | **38 ÉTATS** - severity, detection, workflow |
| `states/state_intention_matrix.yaml` | **37 INTENTIONS** + matrice État×Intention |
| `states/templates/response_master.html` | Template master modulaire (v2.0) |
| `states/templates/partials/**/*.html` | Partials modulaires (intentions, statuts, actions) |
| `states/VARIABLES.md` | Variables Handlebars disponibles |
| `alerts/active_alerts.yaml` | Alertes temporaires (éditable) |

---

## Pièges Courants (Gotchas)

### 1. Extraction lookups CRM
```python
# FAUX - lookup retourne {name, id}, pas la vraie donnée !
date = deal_data['Date_examen_VTC']['name']  # '34_2026-03-31' ≠ vraie date

# CORRECT - utiliser le helper
from src.utils.crm_lookup_helper import enrich_deal_lookups
enriched = enrich_deal_lookups(crm_client, deal_data, {})
date = enriched['date_examen']  # '2026-03-31' (vraie date)
```

### 2. Extraction intention TriageAgent
```python
# CORRECT
intention = result.get("detected_intent")
session_pref = result.get("intent_context", {}).get("session_preference")

# FAUX (n'existe pas !)
intention = result.get("intent_context", {}).get("intention")
```

### 3. Parsing dates
```python
# FAUX - formats multiples possibles
date = datetime.strptime(date_str, "%Y-%m-%d")

# CORRECT - gère tous les formats
from src.utils.date_utils import parse_date_flexible
date = parse_date_flexible(date_str)
```

### 4. Mise à jour CRM
```python
# FAUX - Date_examen_VTC attend un ID, pas une date string
crm_client.update_deal(deal_id, {'Date_examen_VTC': '2026-03-31'})

# CORRECT - utiliser CRMUpdateAgent qui fait le mapping
from src.agents.crm_update_agent import CRMUpdateAgent
agent = CRMUpdateAgent()
agent.update_from_ticket_response(deal_id, {'Date_examen_VTC': '2026-03-31'}, deal_data)
```

### 5. Blocage modification date
```python
# CRITIQUE - vérifier AVANT de modifier
from src.utils.examt3p_crm_sync import can_modify_exam_date
if not can_modify_exam_date(deal_data, exam_session):
    # BLOQUÉ : Evalbox = VALIDE CMA + clôture passée
    # Nécessite force majeure
```

### 6. Template Engine - pybars3

**Le Template Engine utilise maintenant pybars3** (bibliothèque Handlebars pour Python).

#### Architecture
- `src/state_engine/pybars_renderer.py` - Renderer pybars3 avec cache de partials
- `src/state_engine/template_engine.py` - Orchestration (sélection template, préparation contexte)

#### Syntaxe Handlebars supportée
```html
{{variable}}                    <!-- Remplacement de variable -->
{{> partial_name}}              <!-- Inclusion de partial -->
{{#if condition}}...{{/if}}     <!-- Conditionnel -->
{{#unless condition}}...{{/unless}}  <!-- Conditionnel inversé -->
{{#each items}}{{this.prop}}{{/each}}  <!-- Boucle -->
```

#### 6.1 Comparaison int vs string (départements)
```python
# FAUX - CRM retourne int, mapping utilise string
dept = date_info.get('Departement', '')  # Retourne 11 (int)
DEPT_TO_REGION['11']  # KeyError ou comparaison False

# CORRECT - toujours convertir en string
dept = str(date_info.get('Departement', ''))
```
**Fichiers concernés :** `cross_department_helper.py`

#### 6.2 `next_dates` écrasé à plusieurs endroits
```python
# Le workflow écrit next_dates à 4+ endroits différents !
# Lignes ~2040, ~2121, ~2153 dans doc_ticket_workflow.py

# SOLUTION : Ajouter filtre FINAL juste avant generate_response_multi()
# Voir ligne ~2191 "FILTRE FINAL"
```

**Note :** Les anciens gotchas regex (6.2-6.5) ne s'appliquent plus avec pybars3.

---

## Fichiers de Référence

| Fichier | Description | Mise à jour |
|---------|-------------|-------------|
| `crm_schema.json` | Schéma modules/champs Zoho CRM | `python extract_crm_schema.py` |
| `desk_departments.json` | Départements Zoho Desk avec IDs | `python list_departments.py` |

---

## Commandes Utiles

```bash
# Lister tickets récents
python list_recent_tickets.py

# Tester workflow complet
python test_doc_workflow_with_examt3p.py <ticket_id>

# Analyser un lot de tickets
python analyze_lot.py 11 20  # Tickets 11-20

# Clôturer tickets SPAM
python close_spam_tickets.py data/lot2_analysis.json --dry-run
python close_spam_tickets.py data/lot2_analysis.json

# Afficher réponse workflow
python show_response.py <ticket_id>
```

---

## Coûts API (estimation par ticket)

| Composant | Modèle | Coût |
|-----------|--------|------|
| Extraction identifiants | Haiku 3.5 | ~$0.001 |
| Agent Trieur | Haiku 3.5 | ~$0.001 |
| Agent Rédacteur | Sonnet 4.5 | ~$0.036 |
| Next steps note CRM | Haiku 3.5 | ~$0.001 |
| **Total** | | **~$0.04** |

---

## Documentation Détaillée

| Document | Contenu |
|----------|---------|
| `docs/ARCHITECTURE.md` | Structure projet, workflow 8 étapes, data structures |
| `docs/STATE_ENGINE.md` | États, intentions, détection, processes détaillés |
| `docs/AGENTS.md` | Signatures agents, usage, return structures |
| `docs/HELPERS.md` | Tous les helpers avec exemples de code |
| `docs/BUSINESS_RULES.md` | Règles métier complètes (Uber, dates, mappings) |
| `docs/TEMPLATES.md` | Système template, Handlebars, partials, flags |
| `docs/architecture-diagrams.md` | Diagrammes Mermaid |
| `states/VARIABLES.md` | Variables Handlebars disponibles |
