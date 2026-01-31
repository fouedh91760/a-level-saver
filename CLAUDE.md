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

## 12 RÈGLES CRITIQUES - Ne Jamais Oublier

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
| 11 | **MATRICE = Source de vérité** | Le code Python recalcule les flags de la matrice | Voir §11 ci-dessous |
| 12 | **Anti-répétition = context flags** | Ajouter logique anti-répétition dans Humanizer | Voir §12 ci-dessous |

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

#### 6.3 Sauts de ligne dans les templates HTML
```html
<!-- FAUX - Double saut de ligne (trop d'espace) -->
<b>Titre</b><br>
<br>
Contenu du paragraphe.<br>
<br>
Autre paragraphe.<br>

<!-- CORRECT - Un seul <br> entre paragraphes -->
<b>Titre</b><br>
Contenu du paragraphe.<br>
Autre paragraphe.<br>

<!-- CORRECT - <br><br> seulement pour séparer des SECTIONS distinctes -->
<b>Section 1</b><br>
Contenu section 1.<br>
<br>
<b>Section 2</b><br>
Contenu section 2.<br>
```
**Règle :** Un `<br>` = retour à la ligne. Deux `<br><br>` = nouveau paragraphe/section. Ne JAMAIS mettre `<br>` suivi d'une ligne vide dans le template.

---

## RÈGLE 11 : MATRICE = Source de Vérité pour les Context Flags

### Le Problème (Bug découvert 2026-01-31)

```
CONFLIT DE SOURCES DE VÉRITÉ :

   MATRICE (YAML)                    CODE (Python)
   ─────────────────                 ─────────────────
   context_flags:                    # _prepare_template_variables()
     show_dates_section: false  ──►  result['show_dates_section'] =
                                        not date_examen and bool(next_dates)
                                     # LE CODE ÉCRASE LA MATRICE !
```

### La Règle

**Si la matrice définit un flag → le code NE DOIT PAS le recalculer.**

```python
# ❌ FAUX - Recalcule toujours, ignore la matrice
result['show_dates_section'] = not date_examen and bool(next_dates)

# ✅ CORRECT - Respecte la matrice si définie, sinon calcul dynamique
if 'show_dates_section' in context:
    result['show_dates_section'] = context['show_dates_section']
else:
    result['show_dates_section'] = not date_examen and bool(next_dates)
```

### Flags concernés

Ces flags peuvent être overridés par la matrice :
- `show_dates_section` - Afficher section dates
- `show_sessions_section` - Afficher section sessions
- `show_statut_section` - Afficher section statut dossier
- `show_session_info` - Afficher infos générales sessions

### Ajouter une nouvelle intention

Quand tu ajoutes une intention qui doit SUPPRIMER une section :

```yaml
# Dans state_intention_matrix.yaml
"*:MA_NOUVELLE_INTENTION":
  template: "response_master.html"
  context_flags:
    intention_ma_nouvelle_intention: true
    show_dates_section: false      # ← Sera respecté par le code
    show_sessions_section: false   # ← Sera respecté par le code
```

---

## RÈGLE 12 : Anti-Répétition = Context Flags, PAS Humanizer

### Le Problème

Le Humanizer ne peut pas fiablement supprimer du contenu redondant car :
1. Il peut échouer la validation (dates manquantes)
2. Il ajoute de la latence et du coût
3. Le résultat est non-déterministe

### La Solution

Détecter la répétition EN AMONT et poser des flags dans le contexte :

```python
# Dans ticket_info_extractor.py
result['sessions_proposed_recently'] = True  # Si sessions déjà envoyées < 48h
result['dates_proposed_recently'] = True     # Si dates déjà envoyées < 48h
result['elearning_shared_recently'] = True   # Si e-learning déjà partagé < 48h

# Dans template_engine.py - respecter ces flags
if context.get('sessions_proposed_recently'):
    result['show_sessions_section'] = False
```

### Flags anti-répétition existants

| Flag | Description | Fichier source |
|------|-------------|----------------|
| `dates_proposed_recently` | Dates proposées < 48h | `ticket_info_extractor.py` |
| `sessions_proposed_recently` | Sessions proposées < 48h | `ticket_info_extractor.py` |
| `dates_already_communicated` | Dates déjà envoyées (any) | `ticket_info_extractor.py` |

### Pattern d'implémentation

```python
# 1. Détection dans ticket_info_extractor.py
session_markers = ["cours du jour", "cours du soir", "session de formation"]
if any(marker in content for marker in session_markers):
    if thread_date > recent_threshold:  # < 48h
        result['sessions_proposed_recently'] = True

# 2. Passage au contexte template dans doc_ticket_workflow.py
'sessions_proposed_recently': analysis_result.get('sessions_proposed_recently', False),

# 3. Utilisation dans template_engine.py
if context.get('sessions_proposed_recently') and is_follow_up_intent:
    result['show_sessions_section'] = False
```

---

## DEBUGGING : Pistes d'Investigation

### 7. Template non affiché / Partial manquant

**Symptôme:** Une section (ex: confirmation_session) n'apparaît pas dans la réponse.

**Ordre de priorité de sélection du template:**
```
1. MATRICE STATE:INTENTION (state_intention_matrix.yaml)
   Ex: "READY_TO_PAY:CONFIRMATION_SESSION" → response_master.html
   ✅ Architecture moderne avec intentions

2. TEMPLATE_STATE_MAP (template_engine.py ligne ~1007)
   Ex: 'READY_TO_PAY': 'pret_a_payer'
   ❌ Legacy (base_legacy/) - PAS d'intentions !

3. candidate_states.yaml → response.template
   Ex: template: "ready_to_pay.html"

4. Fallback générique
```

**Investigation:**
```bash
# 1. Vérifier si entrée STATE:INTENTION existe
grep "READY_TO_PAY:CONFIRMATION_SESSION" states/state_intention_matrix.yaml

# 2. Vérifier le log "Template sélectionné via matrice"
# Si absent → fallback sur legacy

# 3. Vérifier TEMPLATE_STATE_MAP dans template_engine.py
grep "READY_TO_PAY" src/state_engine/template_engine.py
```

**Solution:** Ajouter l'entrée dans `state_intention_matrix.yaml`:
```yaml
"ETAT:INTENTION":
  template: "response_master.html"
  context_flags:
    intention_xxx: true
```

### 8. Noms d'états incohérents

**Piège:** Le nom d'état diffère entre les fichiers.

| Fichier | Peut utiliser |
|---------|---------------|
| `candidate_states.yaml` | `READY_TO_PAY` |
| `state_intention_matrix.yaml` | `PRET_A_PAYER` (ancien) |
| `TEMPLATE_STATE_MAP` | `'READY_TO_PAY': 'pret_a_payer'` |

**Vérification:**
```bash
# Trouver le vrai nom de l'état
grep -E "^  [A-Z_]+:" states/candidate_states.yaml | grep -i "pay"
```

### 9. Champs CRM Sessions1

**Module Sessions1 - Noms de champs corrects:**
```python
# CORRECT
session_record.get('Date_d_but')   # Date début
session_record.get('Date_fin')      # Date fin (PAS Date_de_fin !)
session_record.get('session_type')  # 'jour' ou 'soir'
session_record.get('Name')          # Nom complet
```

**Fichier:** `src/utils/crm_lookup_helper.py`

### 10. Variables session dans le contexte

**Priorité des données session (fallback chain):**
```python
# 1. Matching nouveau (si CONFIRMATION_SESSION + proposed_options)
matched_session_start = context.get('matched_session_start')
matched_session_end = context.get('matched_session_end')

# 2. Session déjà assignée dans CRM (fallback)
enriched_lookups.get('session_date_debut')
enriched_lookups.get('session_date_fin')
```

**Template Engine (ligne ~725):**
```python
'matched_session_start': context.get('matched_session_start') or enriched_lookups.get('session_date_debut')
```

### 11. Session déjà assignée - Changement bloqué

**Symptôme:** Le candidat veut changer de session (jour→soir) mais le système ne propose rien.

**Cause:** `session_helper.py` retourne immédiatement si session assignée.

**Solution:** Paramètre `allow_change=True` pour bypasser:
```python
session_data = analyze_session_situation(
    ...,
    allow_change=(detected_intent == 'CONFIRMATION_SESSION'),
    enriched_lookups=enriched_lookups
)
```

**Condition de bypass:**
- `allow_change=True` ET
- Préférence exprimée (jour/soir) ET
- Préférence ≠ session actuelle

### 12. Statut "validé" vs "complet"

**Attention au vocabulaire métier:**

| Evalbox | Signification | Terme correct |
|---------|---------------|---------------|
| `Pret a payer` | Documents transmis, en attente paiement | "complet" |
| `Dossier Synchronisé` | CMA a reçu, vérifie | "en cours de vérification" |
| `VALIDE CMA` | CMA a validé après paiement | "validé" |

**Fichier:** `states/templates/partials/statuts/pret_a_payer.html`

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
