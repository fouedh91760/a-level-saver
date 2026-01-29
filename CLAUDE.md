# CLAUDE.md - Guide du Projet A-Level Saver

## Vue d'ensemble

Système d'automatisation des tickets Zoho Desk pour CAB Formations (formation VTC Uber).
Le workflow traite les tickets DOC en utilisant plusieurs agents spécialisés et sources de données.

---

## PROCESS OBLIGATOIRE : Ajout d'un Nouveau Scénario

Quand un nouveau cas métier est identifié (bug, comportement inattendu, nouveau workflow), **suivre ces étapes dans l'ordre** pour respecter l'architecture du State Engine :

### Étape 1 : Analyser et nommer le scénario
- Identifier clairement la **condition de déclenchement** (quelles données, quel contexte)
- Vérifier que le scénario n'existe pas déjà dans `states/candidate_states.yaml`
- Choisir un ID unique (ex: A4, U-D, R3) et un nom en UPPER_SNAKE_CASE

### Étape 2 : Définir l'état dans `states/candidate_states.yaml`
```yaml
NOM_DU_SCENARIO:
  id: "XX"
  priority: NNN
  description: "Description claire"
  category: "analysis|credentials|uber|report|result"
  detection:
    method: "helper_source"
    condition: "flag_name == true"
  workflow:
    action: "RESPOND_WITH_ALERT|RESPOND|BLOCK|ROUTE"
    alert_internal: true|false
  response:
    generate: true
    alert_template: "partials/category/template_name.html"  # si alerte client
    alert_position: "before_signature"
```

### Étape 3 : Ajouter le flag dans la source de données
- Le flag doit être posé **dans le helper qui détecte la condition** (ex: `examt3p_credentials_helper.py`, `uber_eligibility_helper.py`, `date_examen_vtc_helper.py`)
- Le flag doit être un **booléen `True`** (pas une string)
- Ajouter aussi les données de contexte nécessaires au template (emails, dates, etc.)

### Étape 4 : Propager dans le State Detector (`src/state_engine/state_detector.py`)
1. **Contexte** : Ajouter le flag + données dans `_build_context()` (section examt3p_data ou deal_data)
2. **Détection** : Ajouter la condition dans `_check_condition()` avec `is True` (pas truthy)
3. **Alertes** : Si alerte client → ajouter dans `_collect_alerts()` avec type, id, position, et données de contexte

### Étape 5 : Créer le template partial (si réponse/alerte client)
- Chemin : `states/templates/partials/<category>/<nom>.html`
- Utiliser les variables Handlebars : `{{variable}}`, `{{#if condition}}...{{/if}}`
- Suivre le format HTML des partials existants (pas de `<html>`, `<body>`, etc.)

### Étape 6 : Ajouter le rendu dans le Template Engine (`src/state_engine/template_engine.py`)
- Ajouter le cas dans `_generate_alert_content()` pour les alertes
- Utiliser `_load_partial_path()` + `_resolve_if_blocks()` + `_replace_placeholders()` pour rendre le template

### Étape 7 : Tester
- Tester sur un ticket réel qui déclenche le scénario
- Vérifier : détection correcte de l'état, alerte collectée, template rendu, réponse cohérente

**Résumé des fichiers touchés (dans l'ordre) :**
| # | Fichier | Action |
|---|---------|--------|
| 1 | `states/candidate_states.yaml` | Définir l'état |
| 2 | `src/utils/<helper>.py` | Poser le flag booléen + données contexte |
| 3 | `src/state_engine/state_detector.py` | Contexte + détection + collecte alerte |
| 4 | `states/templates/partials/<cat>/<nom>.html` | Template partial |
| 5 | `src/state_engine/template_engine.py` | Rendu de l'alerte |

---

## PROCESS OBLIGATOIRE : Ajout d'une Nouvelle Intention

**⚠️ RÈGLE STRICTE : Toute intention ajoutée dans le YAML DOIT être ajoutée dans le prompt du TriageAgent !**

Le TriageAgent (Claude Sonnet) ne peut détecter que les intentions qu'il connaît. Si une intention existe dans `state_intention_matrix.yaml` mais pas dans le prompt du TriageAgent, elle ne sera **JAMAIS détectée**.

### Étape 1 : Définir l'intention dans `states/state_intention_matrix.yaml`
```yaml
intentions:
  NOM_INTENTION:
    id: "IXX"
    description: "Description claire"
    triggers:
      - "phrase déclencheuse 1"
      - "phrase déclencheuse 2"
    priority: XX
```

### Étape 2 : Ajouter l'intention dans le prompt du TriageAgent

**OBLIGATOIRE** - Modifier `src/agents/triage_agent.py` dans la variable `SYSTEM_PROMPT` :

```python
**Catégorie appropriée:**
- NOM_INTENTION: Description claire de quand utiliser cette intention
  Exemples: "exemple 1", "exemple 2"
  ⚠️ Notes importantes si nécessaire (différence avec autre intention, etc.)
```

### Étape 3 : Ajouter les entrées dans la matrice État×Intention

Dans `states/state_intention_matrix.yaml`, ajouter les combinaisons pertinentes :
```yaml
"*:NOM_INTENTION":
  template: "response_master.html"
  context_flags:
    intention_xxx: true
```

### Étape 4 : Créer le partial si nécessaire

Si l'intention nécessite une réponse spécifique :
- Créer `states/templates/partials/intentions/nom_intention.html`
- Ajouter le flag dans `response_master.html`

**Résumé des fichiers touchés (dans l'ordre) :**
| # | Fichier | Action |
|---|---------|--------|
| 1 | `states/state_intention_matrix.yaml` | Définir l'intention (section `intentions:`) |
| 2 | **`src/agents/triage_agent.py`** | **OBLIGATOIRE** - Ajouter dans SYSTEM_PROMPT |
| 3 | `states/state_intention_matrix.yaml` | Ajouter entrées matrice État×Intention |
| 4 | `states/templates/partials/intentions/<nom>.html` | Template partial (si nécessaire) |
| 5 | `states/templates/response_master.html` | Ajouter section {{#if intention_xxx}} |

### Vérification de cohérence

Avant de considérer l'ajout terminé, vérifier que l'intention existe dans les DEUX fichiers :
```bash
# Vérifier dans le YAML
grep "NOM_INTENTION" states/state_intention_matrix.yaml

# Vérifier dans le TriageAgent
grep "NOM_INTENTION" src/agents/triage_agent.py
```

**Si l'intention n'est pas dans les DEUX fichiers, elle ne fonctionnera PAS.**

---

## RÈGLE D'OR : Ne Pas Réinventer la Roue

Avant de coder une nouvelle fonctionnalité, **TOUJOURS vérifier** si elle existe déjà dans :
1. Les agents (`src/agents/`)
2. Les helpers (`src/utils/`)
3. Le client Zoho (`src/zoho_client.py`)
4. Les alertes temporaires (`alerts/active_alerts.yaml`)
5. Les fichiers de référence (`crm_schema.json`, `desk_departments.json`)
6. **Le State Engine** (`states/candidate_states.yaml`, `states/state_intention_matrix.yaml`)

### Vérification OBLIGATOIRE avant d'ajouter un Intent ou État

```bash
# Lister tous les intents existants (36 définis)
grep -E "^  [A-Z_]+:" states/state_intention_matrix.yaml | head -50

# Chercher si un intent similaire existe déjà
grep -i "mot_clé" states/state_intention_matrix.yaml

# Lister tous les états existants
grep -E "^  [A-Z_]+:" states/candidate_states.yaml | head -30
```

**Si l'intent/état existe (même sous un nom différent) → l'utiliser, NE PAS en créer un nouveau.**

---

## Architecture des Agents

### 1. TriageAgent (`src/agents/triage_agent.py`) - PREMIER DANS LE WORKFLOW
**Agent IA pour triage intelligent des tickets (GO/ROUTE/SPAM) + détection d'intention.**

```python
from src.agents.triage_agent import TriageAgent

agent = TriageAgent()

# SIGNATURE CORRECTE (NE PAS passer ticket_id seul!)
result = agent.triage_ticket(
    ticket_subject="Re: Test de sélection réussi",
    thread_content="Je souhaiterais la session du matin...",
    deal_data=deal_data,  # Optionnel, dict CRM
    current_department="DOC"
)

# Retourne:
#   action (GO/ROUTE/SPAM)
#   target_department
#   reason, confidence
#   detected_intent (IMPORTANT: extraire avec result.get("detected_intent"))
#   intent_context: {
#       is_urgent, mentions_force_majeure, force_majeure_type,
#       wants_earlier_date, session_preference ("jour"|"soir"|null)
#   }
```

**ATTENTION - Extraction de l'intention :**
```python
# CORRECT
intention = result.get("detected_intent")  # "CONFIRMATION_SESSION", "REPORT_DATE", etc.
session_pref = result.get("intent_context", {}).get("session_preference")  # "jour" ou "soir"

# FAUX (ne pas utiliser)
# intention = result.get("intent_context", {}).get("intention")  # N'EXISTE PAS!
```

**Actions possibles :**
- `GO` : Ticket DOC valide, continuer le workflow
- `ROUTE` : Transférer vers autre département (Contact, Partenariat, etc.)
- `SPAM` : Spam/pub, clôturer automatiquement

**Extraction automatique de contexte :**
- `session_preference` : Extrait "jour" ou "soir" si le candidat mentionne sa préférence
- `force_majeure_type` : Détecte "medical", "death", "accident", "childcare"
- `wants_earlier_date` : Détecte si le candidat veut une date plus tôt

### 2. CRMUpdateAgent (`src/agents/crm_update_agent.py`) - RECOMMANDÉ
**Agent spécialisé pour TOUTES les mises à jour CRM CAB Formations.**

Centralise toute la logique de mise à jour CRM :
- Mapping automatique string → ID pour les champs lookup
- Respect des règles de blocage (VALIDE CMA + clôture passée)
- Note CRM optionnelle (désactivée par défaut dans le workflow)

```python
from src.agents.crm_update_agent import CRMUpdateAgent

agent = CRMUpdateAgent()

# Méthode recommandée pour les réponses tickets
result = agent.update_from_ticket_response(
    deal_id="123456",
    ai_updates={'Date_examen_VTC': '2026-03-31', 'Session_choisie': 'Cours du soir'},
    deal_data=deal_data,
    session_data=session_data,  # Sessions proposées par session_helper
    ticket_id="789012",
    auto_add_note=False  # Note consolidée gérée par le workflow
)
```

**IMPORTANT :** Cet agent gère automatiquement :
- `Date_examen_VTC` : convertit date string → ID session via `find_exam_session_by_date_and_dept()`
- `Session_choisie` : convertit nom → ID en cherchant dans les sessions proposées
- Règles de blocage : refuse de modifier `Date_examen_VTC` si VALIDE CMA + clôture passée

### 3. DealLinkingAgent (`src/agents/deal_linking_agent.py`)
**Lie les tickets Zoho Desk aux deals CRM.**

```python
from src.agents.deal_linking_agent import DealLinkingAgent

agent = DealLinkingAgent()
result = agent.process({"ticket_id": "123456"})
# Retourne: deal_id, deal_data, all_deals, routing info
```

### 4. ExamT3PAgent (`src/agents/examt3p_agent.py`)
**Extrait les données de la plateforme ExamT3P.**

```python
from src.agents.examt3p_agent import ExamT3PAgent

agent = ExamT3PAgent()
data = agent.extract_data(identifiant, mot_de_passe)
# Retourne: documents, paiements, examens, statut_dossier, num_dossier, etc.
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

**Champs synchronisés :**
- `Evalbox` : statut du dossier
- `IDENTIFIANT_EVALBOX` / `MDP_EVALBOX` : identifiants ExamT3P
- `NUM_DOSSIER_EVALBOX` : numéro de dossier CMA
- `Date_examen_VTC` : date d'examen (si différente)

**CRITIQUE :** Pour mapper une date string vers un ID de session CRM :
```python
session = find_exam_session_by_date_and_dept(crm_client, "2026-03-31", "75")
session_id = session.get('id')  # Utiliser cet ID pour update_deal
```

### Lookups CRM Enrichis (`src/utils/crm_lookup_helper.py`) - NOUVEAU v2.2

**Helper centralisé pour lire les champs lookup CRM (Date_examen_VTC, Session).**

Les champs `Date_examen_VTC` et `Session` sont des lookups qui retournent `{name, id}`.
Ce helper appelle les modules Zoho CRM pour récupérer les vraies données via `get_record()`.

```python
from src.utils.crm_lookup_helper import (
    enrich_deal_lookups,       # Enrichit tous les lookups d'un deal
    enrich_lookup_field,       # Enrichit un champ lookup spécifique
    get_real_exam_date,        # Date d'examen (YYYY-MM-DD)
    get_real_cloture_date,     # Date de clôture
    get_real_departement,      # Département de l'examen
    get_session_type,          # 'jour' ou 'soir'
    get_session_details,       # Détails complets de la session
)

# Utilisation recommandée dans le workflow
lookup_cache = {}  # Cache partagé pour éviter les appels répétés
enriched_lookups = enrich_deal_lookups(crm_client, deal_data, lookup_cache)

# Accéder aux données
date_examen = enriched_lookups['date_examen']        # '2026-03-31'
date_cloture = enriched_lookups['date_cloture']      # '2026-03-15'
departement = enriched_lookups['departement']        # '75'
session_type = enriched_lookups['session_type']      # 'jour' ou 'soir'
session_name = enriched_lookups['session_name']      # 'Cours du soir mars 2026'
```

**Modules de référence :**
| Champ lookup | Module CRM | Champs utiles |
|--------------|------------|---------------|
| `Date_examen_VTC` | `Dates_Examens_VTC_TAXI` | `Date_Examen`, `Departement`, `Date_Cloture_Inscription` |
| `Session` | `Sessions1` | `Name`, `session_type`, `Date_d_but`, `Date_de_fin` |

**⚠️ NE JAMAIS utiliser regex sur `lookup.get('name')` !** Toujours utiliser ce helper.

### Gestion des identifiants ExamT3P (`src/utils/examt3p_credentials_helper.py`)

**Utilise l'IA (Haiku) pour extraire les identifiants des emails.**

```python
from src.utils.examt3p_credentials_helper import get_credentials_with_validation

result = get_credentials_with_validation(
    deal_data=deal_data,
    threads=threads_data,
    examt3p_agent=agent
)
# Retourne: identifiant, mot_de_passe, compte_existe, connection_test_success,
#           credentials_source, should_respond_to_candidate
```

**Fonctionnement :**
1. Cherche d'abord dans le CRM
2. Si pas trouvé, utilise l'IA pour extraire des threads (plus fiable que regex)
3. Teste la connexion ExamT3P
4. Gère les cas de double compte (alerte si deux comptes payés)

### Alertes Temporaires (`src/utils/alerts_helper.py`) - NOUVEAU

**Système pour informer l'agent rédacteur de bugs/situations temporaires.**

```python
from src.utils.alerts_helper import get_alerts_for_response, get_active_alerts

# Récupérer les alertes formatées pour le prompt
alerts_text = get_alerts_for_response(deal_data=deal_data, examt3p_data=examt3p_data)

# Ou récupérer la liste des alertes actives
alerts = get_active_alerts(evalbox_status="Convoc CMA reçue", department="75")
```

**Fichier de configuration :** `alerts/active_alerts.yaml`

```yaml
alerts:
  - id: "double_convocation_jan2026"
    active: true
    start_date: "2026-01-25"
    end_date: "2026-01-31"
    title: "Double convocation CMA"
    context: "La CMA a envoyé deux convocations par erreur"
    instruction: "Dire au candidat de prendre la seconde (annule et remplace)"
    applies_to:
      evalbox: ["Convoc CMA reçue", "VALIDE CMA"]
```

### Analyse Date Examen VTC (`src/utils/date_examen_vtc_helper.py`)

```python
from src.utils.date_examen_vtc_helper import (
    analyze_exam_date_situation,
    get_earlier_dates_other_departments,
    get_next_exam_dates
)

result = analyze_exam_date_situation(
    deal_data=deal_data,
    threads=threads_data,
    crm_client=crm_client,
    examt3p_data=examt3p_data
)
# Retourne:
#   case (1-10), next_dates, should_include_in_response, response_message,
#   alternative_department_dates, can_choose_other_department, current_departement
```

**CAS gérés :** 1-Date vide, 2-Date passée, 3-Refusé CMA, 4-VALIDE CMA, 5-Dossier Synchronisé,
6-Autre statut, 7-Examen passé, 8-Deadline ratée, 9-Convoc reçue, 10-Prêt à payer

**Dates alternatives dans d'autres départements :**
```python
# Rechercher des dates plus tôt dans d'autres départements
# Utile si candidat n'a PAS encore de compte ExamT3P (peut choisir n'importe quel dept)
alt_dates = get_earlier_dates_other_departments(
    crm_client,
    current_departement="75",
    reference_date="2026-06-30",  # Première date du dept actuel
    limit=3
)
# Retourne: Liste de sessions avec Date_Examen < reference_date
```

**Règles de flexibilité département :**
- `can_choose_other_department = True` si `compte_existe == False` (pas de compte ExamT3P)
- Le candidat peut alors s'inscrire dans N'IMPORTE QUEL département
- Si compte ExamT3P existe → département assigné, changement = nouveau compte avec identifiants différents

### Filtrage Intelligent par Région (`src/utils/date_examen_vtc_helper.py`)

**Filtre automatiquement les dates d'examen selon la région du candidat.**

```python
from src.utils.date_examen_vtc_helper import (
    detect_candidate_region,
    filter_dates_by_region_relevance,
    DEPT_TO_REGION,
    REGION_TO_DEPTS,
    CITY_TO_REGION,
    REGION_ALIASES
)

# Détecter la région du candidat
region = detect_candidate_region(
    text="Je suis dans le Pays de la Loire",  # Message du candidat
    department="49"  # Ou département CRM (optionnel)
)
# Retourne: "Pays de la Loire"

# Filtrer les dates intelligemment
filtered_dates = filter_dates_by_region_relevance(
    all_dates=next_dates,  # 15 dates de tous départements
    candidate_message="Je suis dans le Pays de la Loire",
    candidate_department=None
)
# Retourne: dates Pays de la Loire + dates antérieures d'autres régions
```

**Logique de filtrage :**
1. Détecte la région via : département CRM → mention région dans texte → mention ville
2. Garde TOUTES les dates de la région du candidat
3. Garde les autres régions SEULEMENT si date PLUS TÔT que la 1ère date de la région du candidat
4. Élimine les régions éloignées avec mêmes dates (évite de noyer le candidat)

**Mappings disponibles :**
- `DEPT_TO_REGION` : tous les départements français → région
- `REGION_TO_DEPTS` : région → liste de départements
- `CITY_TO_REGION` : 50+ villes principales → région (Nantes, Lyon, etc.)
- `REGION_ALIASES` : aliases ("PDL", "IDF", "alsace") → région officielle

**Intégration automatique :**
Le filtrage est appliqué automatiquement dans le workflow d'analyse.
Les templates reçoivent uniquement les dates pertinentes pour la région du candidat.

### Sessions de Formation (`src/utils/session_helper.py`)

```python
from src.utils.session_helper import analyze_session_situation

result = analyze_session_situation(
    deal_data=deal_data,
    exam_dates=next_dates,  # Liste des dates d'examen
    threads=threads_data,
    crm_client=crm_client,
    triage_session_preference="soir"  # NOUVEAU - préférence extraite par TriageAgent
)
# Retourne: session_preference (jour/soir), proposed_options avec sessions IDs, message
```

**Logique de sélection de session :**
- **Si date d'examen existe** → Auto-sélection de la meilleure session correspondant à la préférence
- **Si pas de date d'examen** → Proposition des dates + sessions associées, demande de confirmation

**Priorité pour la préférence :**
1. `triage_session_preference` (TriageAgent)
2. `deal_data['Preference_horaire']` (CRM)
3. Analyse IA des threads

**Note :** Les sessions sont proposées même si la date d'examen est déjà assignée mais que `Session` est vide.

### Éligibilité Uber 20€ (`src/utils/uber_eligibility_helper.py`)

```python
from src.utils.uber_eligibility_helper import analyze_uber_eligibility

result = analyze_uber_eligibility(deal_data)
# Retourne: is_uber_20_deal, case (A/B/C/D/E/PROSPECT), is_eligible, response_message
```

**Ordre de vérification :** PROSPECT → NOT_UBER → CAS A → CAS D → CAS E → CAS B → ÉLIGIBLE

### Cohérence Formation/Examen (`src/utils/training_exam_consistency_helper.py`)

```python
from src.utils.training_exam_consistency_helper import analyze_training_exam_consistency

result = analyze_training_exam_consistency(deal_data, threads, session_data, crm_client)
# Détecte les cas: formation manquée + examen imminent
```

### Parsing de Dates (`src/utils/date_utils.py`) - NOUVEAU

**Module centralisé pour le parsing robuste de dates depuis diverses sources (CRM, ExamT3P, API).**

```python
from src.utils.date_utils import (
    parse_date_flexible,       # Parse date avec multiples formats → date
    parse_datetime_flexible,   # Parse datetime avec multiples formats → datetime
    format_date_for_display,   # Formate date pour affichage (DD/MM/YYYY)
    is_date_before,            # Compare deux dates (date1 < date2)
    is_date_after,             # Compare deux dates (date1 > date2)
    days_between,              # Nombre de jours entre deux dates
    add_days,                  # Ajoute des jours à une date
)

# Exemples d'utilisation
date = parse_date_flexible("2026-03-31")           # → datetime.date(2026, 3, 31)
date = parse_date_flexible("2026-03-31T10:30:00Z") # → datetime.date(2026, 3, 31)
date = parse_date_flexible("31/03/2026")           # → datetime.date(2026, 3, 31)

# Formats supportés (ordre de priorité)
DATE_FORMATS = [
    "%Y-%m-%d",                    # 2026-03-31
    "%Y-%m-%dT%H:%M:%S",           # 2026-03-31T10:30:00
    "%Y-%m-%dT%H:%M:%S.%f",        # 2026-03-31T10:30:00.000
    "%Y-%m-%dT%H:%M:%SZ",          # 2026-03-31T10:30:00Z
    "%d/%m/%Y",                    # 31/03/2026
    "%d-%m-%Y",                    # 31-03-2026
]
```

**IMPORTANT :** Toujours utiliser `parse_date_flexible()` au lieu de parsers inline pour éviter les bugs de formats. Ce module est utilisé par `uber_eligibility_helper.py` et d'autres helpers.

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

**ATTENTION - Champs Lookup (CRITIQUE) :**

Les champs `Date_examen_VTC` et `Session` sont des **lookups** vers d'autres modules CRM.

**En LECTURE (get_deal) :**
```python
deal = crm_client.get_deal(deal_id)
deal['Date_examen_VTC']  # → {'name': '34_2026-03-31', 'id': '1456177001550147229'}
deal['Session']          # → {'name': 'cds-mars-2026', 'id': '1456177001234567890'}
```
⚠️ **Ce n'est PAS la vraie date/session !** C'est juste une référence (name + id).

**Pour obtenir les vraies données, TOUJOURS faire un appel API supplémentaire :**
```python
# Pour Date_examen_VTC → module "Dates_Examens_VTC_TAXI"
exam_session_id = deal['Date_examen_VTC']['id']
exam_session = crm_client.get_record('Dates_Examens_VTC_TAXI', exam_session_id)
real_date = exam_session['Date_Examen']  # → '2026-03-31' (vraie date)
departement = exam_session['Departement']  # → '34'

# Pour Session → module "Sessions"
session_id = deal['Session']['id']
session = crm_client.get_record('Sessions', session_id)
session_name = session['Name']  # → 'Cours du soir mars 2026'
session_type = session['session_type']  # → 'soir'
```

**En ÉCRITURE (update_deal) :**
- `Date_examen_VTC` → Attend un **ID** (bigint), pas une date string
- `Session` → Attend un **ID** (bigint), pas un nom de session
- Utiliser `find_exam_session_by_date_and_dept()` pour obtenir l'ID depuis une date

**Modules de référence :**
| Champ CRM | Module associé | Champs utiles |
|-----------|----------------|---------------|
| `Date_examen_VTC` | `Dates_Examens_VTC_TAXI` | `Date_Examen`, `Departement`, `Date_Cloture_Inscription` |
| `Session` | `Sessions1` | `Name`, `session_type`, `Date_d_but`, `Date_de_fin` |

---

## Workflow Principal (`src/workflows/doc_ticket_workflow.py`)

```
1. AGENT TRIEUR     → Triage IA (GO/ROUTE/SPAM)
2. AGENT ANALYSTE   → Extraction données 6 sources + sync ExamT3P
3. AGENT RÉDACTEUR  → Génération réponse Claude + RAG + alertes temporaires
4. CRM NOTE         → Note unique consolidée (next steps générés par IA)
5. TICKET UPDATE    → Tags, statut
6. DEAL UPDATE      → Via CRMUpdateAgent (mapping auto, règles de blocage)
7. DRAFT CREATION   → Brouillon HTML dans Zoho Desk
8. FINAL VALIDATION
```

### Note CRM Consolidée (STEP 4)

Le workflow crée **UNE SEULE note** avec :
- Lien vers le ticket Desk
- Mises à jour CRM effectuées
- Next steps candidat (générés par IA Haiku)
- Next steps CAB (générés par IA Haiku)
- Alertes si nécessaire

**Format :**
```
Ticket #198709000445735836
https://desk.zoho.com/agent/cabformations/cab-formations/tickets/198709000445735836

Mises à jour CRM:
• NUM_DOSSIER_EVALBOX: — → 00038886
• Date_examen_VTC: — → 31/03/2026

Next steps candidat:
• Surveiller emails paiement CMA
• Choisir session de formation

Next steps CAB:
• Vérifier paiement CMA sous 48h

✓ Aucune alerte
```

---

## State Engine - Architecture État × Intention → Template

### Principe Fondamental

**Le State Engine génère les réponses de manière déterministe** :
1. **ÉTAT** = situation factuelle du candidat (détecté depuis CRM/ExamT3P)
2. **INTENTION** = ce que le candidat demande (détecté par TriageAgent via IA)
3. **TEMPLATE** = réponse adaptée à la combinaison ÉTAT × INTENTION

### Multi-États (Architecture v2.1)

Le State Engine détecte **plusieurs états simultanément** grâce à la classification par sévérité :

| Severity | Comportement | Exemples |
|----------|--------------|----------|
| **BLOCKING** | Stoppe le workflow, réponse unique | SPAM, DUPLICATE_UBER, UBER_CAS_A |
| **WARNING** | Continue + ajoute alerte | UBER_ACCOUNT_NOT_VERIFIED, UBER_NOT_ELIGIBLE |
| **INFO** | Combinables entre eux | EXAM_DATE_EMPTY, CREDENTIALS_INVALID, GENERAL |

```python
# Dans state_detector.py
detected_states = state_detector.detect_all_states(
    deal_data=deal_data,
    examt3p_data=examt3p_data,
    triage_result=triage_result,
    linking_result=linking_result,
    session_data=session_data,                         # NOUVEAU v2.2
    training_exam_consistency_data=consistency_data    # NOUVEAU v2.2
)

# Structure DetectedStates:
{
    "blocking_state": None,                    # Si présent, stoppe tout
    "warning_states": [DetectedState, ...],   # Alertes à inclure
    "info_states": [DetectedState, ...],      # États combinables
    "primary_state": DetectedState,            # État principal (rétrocompat)
    "all_states": [DetectedState, ...]         # Tous les états détectés
}

# Contexte enrichi automatiquement (v2.2):
# - uber_case: calculé automatiquement depuis deal_data (A/B/D/E/ELIGIBLE)
# - extraction_failed: True si ExamT3P indisponible
# - error_type: type d'erreur (connection_failed, etc.)
```

**Comportement :**
- Si `blocking_state` présent → réponse unique, workflow stoppé
- Sinon → combine tous les `warning_states` et `info_states` dans la réponse

```yaml
# Exemple dans candidate_states.yaml
CREDENTIALS_INVALID:
  id: "A1"
  priority: 100
  severity: "INFO"  # Pas BLOCKING car CAB crée le compte pour Uber

UBER_ACCOUNT_NOT_VERIFIED:
  id: "U-D"
  priority: 203
  severity: "WARNING"  # Ajoute alerte mais continue le workflow
```

### Fichiers Source de Vérité

| Fichier | Contenu |
|---------|---------|
| `states/candidate_states.yaml` | **38 ÉTATS** avec severity (BLOCKING/WARNING/INFO) - **SOURCE DE VÉRITÉ UNIQUE** |
| `states/state_intention_matrix.yaml` | **37 INTENTIONS** (I01-I37) + MATRICE État×Intention (section `states:` DÉPRÉCIÉE) |
| `states/templates/response_master.html` | **Template master modulaire** (architecture v2.0) |
| `states/templates/partials/**/*.html` | **Partials modulaires** - tous en `.html` (pas `.md`) |
| `states/templates/base_legacy/*.html` | **62 Templates legacy** (archivés, utilisés en fallback) |
| `states/blocks/*.md` | Blocs réutilisables (salutation, signature, etc.) |
| `states/VARIABLES.md` | Documentation des variables Handlebars |

**⚠️ IMPORTANT (v2.2) :** La section `states:` dans `state_intention_matrix.yaml` est **DÉPRÉCIÉE**. La source de vérité unique pour les états est `candidate_states.yaml`.

### Détection d'Intent et Contexte par TriageAgent

```python
triage_result = triage_agent.triage_ticket(ticket_id)
# Retourne: action, primary_intent, secondary_intents, intent_context

# Structure complète:
{
    "action": "GO" | "ROUTE" | "SPAM",
    "primary_intent": "DEMANDE_DATES_FUTURES",       # Intention principale
    "secondary_intents": ["QUESTION_SESSION"],       # Intentions secondaires
    "detected_intent": "DEMANDE_DATES_FUTURES",      # Alias rétrocompat
    "intent_context": {
        "is_urgent": True | False,
        "mentions_force_majeure": True | False,
        "force_majeure_type": "medical" | "death" | "accident" | "childcare" | "other" | None,
        "force_majeure_details": "description courte" | None,
        "wants_earlier_date": True | False,
        "session_preference": "jour" | "soir" | None
    }
}
```

**Le TriageAgent extrait automatiquement `session_preference`** quand le candidat mentionne "cours du jour", "cours du soir", etc.

### Multi-Intentions (Architecture v2.1)

Le TriageAgent détecte **plusieurs intentions simultanément** :

```python
# Exemple: "Je voudrais les dates de Montpellier et des infos sur les cours du soir"
result = triage_agent.triage_ticket(...)
# → primary_intent: "DEMANDE_DATES_FUTURES"
# → secondary_intents: ["QUESTION_SESSION"]
```

**Intentions disponibles pour multi-détection :**
- `DEMANDE_DATES_FUTURES` - Demande de dates d'examen futures
- `QUESTION_SESSION` - Question sur les sessions jour/soir
- `QUESTION_PROCESSUS` - Question sur le processus global
- `DEMANDE_AUTRES_DEPARTEMENTS` - Veut voir d'autres départements
- `STATUT_DOSSIER`, `REPORT_DATE`, `CONFIRMATION_SESSION`, etc.

### Intégration TriageAgent → session_helper

```python
# Le workflow passe la préférence du TriageAgent au session_helper
session_data = analyze_session_situation(
    deal_data=deal_data,
    exam_dates=exam_dates,
    threads=threads_data,
    crm_client=crm_client,
    triage_session_preference=triage_result.get('intent_context', {}).get('session_preference')
)
```

**Priorité de détection de préférence :**
1. TriageAgent (`session_preference` dans `intent_context`)
2. Deal CRM (`Preference_horaire`)
3. Threads (analyse IA du message)

### Syntaxe Templates (Handlebars)

```html
{{variable}}                          <!-- Variable simple -->
{{{variable}}}                        <!-- Variable HTML (non échappée) -->
{{> bloc_name}}                       <!-- Inclusion de bloc -->
{{#if condition}}...{{else}}...{{/if}} <!-- Conditionnel -->
{{#unless condition}}...{{/unless}}   <!-- Conditionnel inverse -->
{{#each items}}{{this.field}}{{/each}} <!-- Boucle -->
```

**Variables de session disponibles dans les templates :**
```
{{session_preference}}          <!-- "jour" ou "soir" -->
{{session_preference_jour}}     <!-- true/false -->
{{session_preference_soir}}     <!-- true/false -->
{{session_message}}             <!-- Message pré-formaté -->
{{#each sessions_proposees}}    <!-- Liste aplatie des sessions -->
  {{this.nom}}                  <!-- Nom de la session -->
  {{this.debut}}                <!-- Date début formatée -->
  {{this.fin}}                  <!-- Date fin formatée -->
  {{this.date_examen}}          <!-- Date examen associée -->
  {{this.date_examen_formatted}} <!-- Alias -->
  {{this.date_cloture_formatted}} <!-- Date clôture formatée -->
  {{this.departement}}          <!-- Département -->
  {{this.type}}                 <!-- "jour" ou "soir" -->
  {{this.is_jour}}              <!-- true/false -->
  {{this.is_soir}}              <!-- true/false -->
  {{this.is_first_of_exam}}     <!-- true si première session de cette date (pour grouper) -->
{{/each}}

<!-- Booléens pour proposer dates/sessions automatiquement -->
{{date_examen_vide}}            <!-- true si Date_examen_VTC est vide -->
{{session_vide}}                <!-- true si Session est vide -->
{{has_sessions_proposees}}      <!-- true si sessions_proposees non vide -->
```

### Logique de Sélection Template (TemplateEngine)

L'ordre de priorité dans `_select_base_template()` :

1. **PASS 0** : Matrice `STATE:INTENTION` (priorité maximale) + **WILDCARDS** (v2.2)
   ```python
   # 0a. D'abord essayer match exact STATE:INTENTION
   matrix_key = f"{state.name}:{intention}"
   config = self.state_intention_matrix.get(matrix_key)

   # 0b. Si pas de match exact, essayer wildcard *:INTENTION (NOUVEAU v2.2)
   if not config:
       wildcard_key = f"*:{intention}"
       if wildcard_key in self.state_intention_matrix:
           config = self.state_intention_matrix[wildcard_key]
   ```

   **Exemple wildcard :**
   ```yaml
   # Dans state_intention_matrix.yaml
   "*:REPORT_DATE":
     template: "report_possible.html"
     context_flags:
       intention_report_date: true
   ```

2. **PASS 1** : Templates avec intention (`for_intention` + `for_condition`)
3. **PASS 1.5** : Templates avec `for_state` (état spécifique, indépendant de l'intention)
   ```yaml
   # Dans state_intention_matrix.yaml
   examen_passe:
     file: "templates/base/examen_passe.html"
     for_state: "EXAM_DATE_PAST_VALIDATED"  # Priorité sur for_condition
   ```
4. **PASS 2** : Templates avec condition seule
5. **PASS 3** : Cas Uber (A, B, D, E)
6. **PASS 4** : Résultat examen
7. **PASS 5** : Evalbox (statut dossier)
8. **Fallback** : Par nom d'état normalisé

### Transformation des Données session_helper → Template

Le `TemplateEngine` utilise `_flatten_session_options()` pour transformer les données de `session_helper` en format utilisable par les templates :

```python
# Input (session_helper format):
{
    'proposed_options': [
        {
            'exam_info': {'Date_Examen': '2026-03-31', 'Departement': '75'},
            'sessions': [
                {'Name': 'cds-janvier', 'Date_d_but': '...', 'session_type': 'soir'}
            ]
        }
    ]
}

# Output (template format - aplati):
[
    {
        'date_examen': '31/03/2026',
        'departement': '75',
        'nom': 'Cours du soir',
        'debut': '15/01/2026',
        'fin': '25/01/2026',
        'type': 'soir',
        'is_soir': True
    }
]
```

### Template STATUT_DOSSIER avec Next Steps Automatiques

Le template `statut_dossier_reponse.html` gère automatiquement la proposition de dates et sessions :

```html
<!-- Si date_examen_vide ET sessions disponibles → proposer dates + sessions -->
{{#if date_examen_vide}}
{{#if has_sessions_proposees}}
<b>Prochaines étapes : choisir votre date d'examen</b>
{{#each sessions_proposees}}
{{#if this.is_first_of_exam}}
<b>Examen du {{this.date_examen_formatted}}</b>
{{/if}}
{{#if this.is_jour}}→ Cours du jour : {{this.date_debut}} - {{this.date_fin}}{{/if}}
{{#if this.is_soir}}→ Cours du soir : {{this.date_debut}} - {{this.date_fin}}{{/if}}
{{/each}}
{{/if}}
{{/if}}

<!-- Si date assignée MAIS session vide → proposer sessions uniquement -->
{{#if date_examen}}
{{#if session_vide}}
{{#if has_sessions_proposees}}
<b>Prochaine étape : choisir votre session de formation</b>
...
{{/if}}
{{/if}}
{{/if}}
```

**Important** : Les patterns `{{#if this.*}}` à l'intérieur des `{{#each}}` sont préservés par `_resolve_if_blocks` et traités ensuite par `_resolve_if_blocks_in_each_item`.

### Empathie Force Majeure

Dans les templates de report (ex: `report_possible.html`), ajouter l'empathie automatique :

```html
{{#if mentions_force_majeure}}
{{> empathie_force_majeure}}
{{/if}}
```

Le bloc `empathie_force_majeure.md` adapte le message selon `force_majeure_type` :
- `death` → Condoléances sincères
- `medical` → Prompt rétablissement
- `accident` → Soutien et compréhension
- `childcare` → Compréhension de la situation familiale

---

## Architecture Modulaire des Templates (v2.0)

### Principe Fondamental

**Objectif : Chaque réponse fait AVANCER le candidat vers l'inscription finale à l'examen.**

L'architecture modulaire garantit que TOUTE réponse :
1. **Répond à la question** (intention du candidat)
2. **Affiche le statut actuel** (où en est le dossier)
3. **Pousse vers l'action suivante** (ce que le candidat doit faire maintenant)

### Structure des Dossiers (Architecture v2.0)

```
states/templates/
├── response_master.html          # Template master universel
├── base_legacy/                  # Templates legacy (archivés, utilisés en fallback)
│   ├── uber_cas_a.html
│   ├── dossier_synchronise.html
│   └── ... (62 templates)
└── partials/                     # Blocs modulaires réutilisables
    ├── intentions/               # Réponses aux intentions (14 fichiers)
    │   ├── statut_dossier.html
    │   ├── demande_date.html
    │   ├── demande_identifiants.html
    │   ├── confirmation_session.html
    │   ├── demande_convocation.html
    │   ├── demande_elearning.html
    │   ├── report_date.html
    │   ├── probleme_documents.html
    │   ├── question_generale.html
    │   ├── resultat_examen.html
    │   ├── question_uber.html
    │   ├── question_session.html      # Multi-intentions v2.1
    │   ├── question_processus.html    # Multi-intentions v2.1
    │   └── autres_departements.html   # Multi-intentions v2.1
    ├── statuts/                  # Affichage du statut Evalbox (7 fichiers)
    │   ├── dossier_cree.html
    │   ├── dossier_synchronise.html
    │   ├── pret_a_payer.html
    │   ├── valide_cma.html
    │   ├── refus_cma.html
    │   ├── convoc_recue.html
    │   └── en_attente.html
    ├── actions/                  # Actions requises pour avancer (10 fichiers)
    │   ├── passer_test.html
    │   ├── envoyer_documents.html
    │   ├── completer_dossier.html
    │   ├── choisir_date.html
    │   ├── choisir_session.html
    │   ├── surveiller_paiement.html
    │   ├── attendre_convocation.html
    │   ├── preparer_examen.html
    │   ├── corriger_documents.html
    │   └── contacter_uber.html
    ├── uber/                     # Conditions bloquantes Uber (5 fichiers)
    │   ├── cas_a_docs_manquants.html
    │   ├── cas_b_test_manquant.html
    │   ├── cas_d_compte_non_verifie.html
    │   ├── cas_e_non_eligible.html
    │   └── doublon_offre.html
    ├── resultats/                # Résultats d'examen (3 fichiers)
    │   ├── admis.html
    │   ├── non_admis.html
    │   └── absent.html
    ├── report/                   # Report de date (3 fichiers)
    │   ├── bloque.html
    │   ├── possible.html
    │   └── force_majeure.html
    ├── credentials/              # Problèmes d'identifiants (2 fichiers)
    │   ├── invalid.html
    │   └── inconnus.html
    └── dates/                    # Proposition de dates (1 fichier)
        └── proposition.html
```

### Template Master (`response_master.html`)

Le template master combine dynamiquement les partials selon le contexte :

```html
{{> salutation_personnalisee}}

<!-- SECTION 1: RÉPONDRE À L'INTENTION -->
{{#if intention_statut_dossier}}
{{> partials/intentions/statut_dossier}}
{{/if}}
{{#if intention_demande_date}}
{{> partials/intentions/demande_date}}
{{/if}}
<!-- ... autres intentions ... -->

<!-- SECTION 2: STATUT ACTUEL DU DOSSIER -->
{{#if show_statut_section}}
<b>Statut de votre dossier</b><br>
{{#if evalbox_dossier_synchronise}}
{{> partials/statuts/dossier_synchronise}}
{{/if}}
<!-- ... autres statuts ... -->
{{/if}}

<!-- SECTION 3: ACTION REQUISE POUR AVANCER -->
{{#if has_required_action}}
<b style="color: #d35400;">Prochaine étape pour avancer</b><br>
{{#if action_passer_test}}
{{> partials/actions/passer_test}}
{{/if}}
<!-- ... autres actions ... -->
{{/if}}

<!-- SECTION 4: DATES/SESSIONS SI PERTINENT -->
{{#if show_dates_section}}
{{#each next_dates}}
...
{{/each}}
{{/if}}

{{> acces_elearning_rappel}}
{{> verifier_spams}}
{{> signature}}
```

### Context Flags pour Intentions

Les context flags sont injectés par la matrice État×Intention et activent les sections appropriées :

```yaml
# Dans state_intention_matrix.yaml
"UBER_TEST_MISSING:STATUT_DOSSIER":
  template: "response_master.html"  # ou template hybride
  context_flags:
    intention_statut_dossier: true

"UBER_TEST_MISSING:DEMANDE_DATE_EXAMEN":
  template: "response_master.html"
  context_flags:
    intention_demande_date: true
```

**Flags d'intention disponibles :**
- `intention_statut_dossier` - Question sur l'avancement
- `intention_demande_date` - Demande de dates d'examen
- `intention_demande_identifiants` - Demande d'identifiants ExamT3P
- `intention_confirmation_session` - Choix de session jour/soir
- `intention_demande_convocation` - Où est ma convocation ?
- `intention_demande_elearning` - Accès e-learning
- `intention_report_date` - Demande de report
- `intention_probleme_documents` - Problème avec les documents
- `intention_question_generale` - Question générale
- `intention_resultat_examen` - Question sur résultat d'examen
- `intention_question_uber` - Question sur l'offre Uber
- `intention_question_session` - Question sur les sessions jour/soir (v2.1)
- `intention_question_processus` - Question sur le processus global (v2.1)
- `intention_autres_departements` - Demande d'autres départements (v2.1)

**Flags de conditions bloquantes (Section 0 du response_master) :**
- `uber_cas_a` - Documents non envoyés (CAS A)
- `uber_cas_b` - Test de sélection non passé (CAS B)
- `uber_cas_d` - Compte Uber non vérifié (CAS D)
- `uber_cas_e` - Non éligible selon Uber (CAS E)
- `uber_doublon` - Doublon offre Uber 20€
- `resultat_admis` - Résultat d'examen admis
- `resultat_non_admis` - Résultat d'examen non admis
- `resultat_absent` - Candidat absent à l'examen
- `report_bloque` - Report impossible (VALIDE CMA + clôture passée)
- `report_possible` - Report encore possible
- `report_force_majeure` - Demande de report avec force majeure
- `credentials_invalid` - Identifiants invalides
- `credentials_inconnus` - Identifiants inconnus

**STATE_FLAG_MAP (v2.2)** - Mapping complet État → Flags template :
```python
# Dans template_engine.py
STATE_FLAG_MAP = {
    # Uber states
    'UBER_DOCS_MISSING': ['uber_cas_a'],
    'UBER_TEST_MISSING': ['uber_cas_b'],
    'UBER_ACCOUNT_NOT_VERIFIED': ['uber_cas_d'],
    'UBER_NOT_ELIGIBLE': ['uber_cas_e'],
    'DUPLICATE_UBER': ['uber_doublon'],
    # Credentials states
    'CREDENTIALS_INVALID': ['credentials_invalid'],
    'CREDENTIALS_UNKNOWN': ['credentials_inconnus'],
    # Report states
    'DATE_MODIFICATION_BLOCKED': ['report_bloque'],
    'REPORT_DATE_REQUEST': ['report_possible'],
    'FORCE_MAJEURE_REPORT': ['report_force_majeure'],
    # Exam result states
    'EXAM_PASSED': ['resultat_admis'],
    'EXAM_FAILED': ['resultat_non_admis'],
    'EXAM_ABSENT': ['resultat_absent'],
    # ... (20+ états au total)
}
```

### Détermination Automatique des Actions

Le `TemplateEngine._determine_required_actions()` calcule automatiquement les actions requises :

```python
def _determine_required_actions(self, context, evalbox) -> Dict[str, bool]:
    """Détermine les actions requises selon l'état du candidat."""
    actions = {
        'has_required_action': False,
        'action_passer_test': False,
        'action_envoyer_documents': False,
        'action_completer_dossier': False,
        'action_choisir_date': False,
        'action_choisir_session': False,
        'action_surveiller_paiement': False,
        'action_attendre_convocation': False,
        'action_preparer_examen': False,
        'action_corriger_documents': False,
        'action_contacter_uber': False,
    }

    # Logique Uber (prioritaire)
    if is_uber_20:
        if not date_dossier_recu:
            actions['action_envoyer_documents'] = True  # CAS A
        elif not date_test_selection:
            actions['action_passer_test'] = True        # CAS B
        elif not compte_uber:
            actions['action_contacter_uber'] = True     # CAS D
        elif not eligible_uber:
            actions['action_contacter_uber'] = True     # CAS E

    # Logique Evalbox
    if evalbox == 'Dossier crée':
        actions['action_completer_dossier'] = True
    elif evalbox == 'Dossier Synchronisé':
        actions['action_surveiller_paiement'] = True
    elif evalbox == 'VALIDE CMA':
        actions['action_attendre_convocation'] = True
    elif evalbox == 'Refusé CMA':
        actions['action_corriger_documents'] = True
    elif evalbox == 'Convoc CMA reçue':
        actions['action_preparer_examen'] = True
    # ...

    return actions
```

### Chargement des Partials avec Chemin

Le `TemplateEngine` supporte les chemins dans les partials :

```html
{{> partials/intentions/statut_dossier}}  <!-- Chemin relatif à states/templates/ -->
{{> signature}}                            <!-- Bloc classique depuis states/blocks/ -->
```

**Méthode `_load_partial_path()` :**
```python
def _load_partial_path(self, partial_path: str) -> str:
    """Charge un partial depuis un chemin relatif au dossier templates."""
    templates_root = self.states_path / "templates"
    full_path = templates_root / partial_path
    # Essaie .html puis .md puis sans extension
    for ext in ['.html', '.md', '']:
        file_path = full_path.parent / (full_path.name + ext)
        if file_path.exists():
            return self._clean_block_content(file_path.read_text())
    return ''
```

### Exemple de Rendu Complet

Pour un candidat Uber CAS B qui demande son statut :
- État : `UBER_TEST_MISSING`
- Intention : `STATUT_DOSSIER`
- Context flags : `intention_statut_dossier: true`

**Résultat généré :**
```html
Bonjour Thomas,

<b>Concernant l'avancement de votre dossier</b>
Votre dossier est en attente de traitement...

<b>Statut de votre dossier</b>
Votre dossier est en attente de traitement...

<b style="color: #d35400;">Prochaine étape pour avancer</b>
Pour finaliser votre inscription, vous devez <b>passer le test de sélection</b>.
→ <a href="...">Passez le test maintenant</a>
Ce test est rapide (environ 10 minutes)...

<b>Prochaines dates d'examen disponibles</b>
CMA 75
  → 31/03/2026 (clôture : 15/03/2026)

Accès à votre formation e-learning...
Pensez à vérifier vos spams...

Bien cordialement,
L'équipe CAB Formations
```

### Architecture Modulaire

L'architecture supporte deux types de templates :
1. **Templates spécifiques** (`states/templates/base/*.html`) pour des cas particuliers
2. **Template master** (`response_master.html`) avec context flags pour les cas généraux
3. **Templates hybrides** (comme `uber_test_missing_hybrid.html`) pour combiner les approches

### Ajout d'une Nouvelle Intention

1. Créer le partial `states/templates/partials/intentions/nouvelle_intention.html`
2. Ajouter le flag dans `_prepare_placeholder_data()` :
   ```python
   'intention_nouvelle_intention': context.get('intention_nouvelle_intention', False),
   ```
3. Ajouter la section dans `response_master.html` :
   ```html
   {{#if intention_nouvelle_intention}}
   {{> partials/intentions/nouvelle_intention}}
   {{/if}}
   ```
4. Ajouter les entrées dans la matrice pour chaque état concerné

### Ajout d'une Nouvelle Action

1. Créer le partial `states/templates/partials/actions/nouvelle_action.html`
2. Ajouter le flag dans `_determine_required_actions()` :
   ```python
   'action_nouvelle_action': False,
   # ... logique de détection
   if condition_specifique:
       actions['action_nouvelle_action'] = True
   ```
3. Ajouter la section dans `response_master.html` :
   ```html
   {{#if action_nouvelle_action}}
   {{> partials/actions/nouvelle_action}}
   {{/if}}
   ```

---

### Test de Sélection Uber (CAS B → ELIGIBLE)

**`Date_test_selection` est un champ interdit de modification** : mis à jour par webhook e-learning, pas par le workflow.

**Flow automatique :**
```
1. Candidat passe le test sur e-learning CAB Formations
2. Webhook externe → Date_test_selection rempli dans Zoho CRM
3. Candidat contacte "j'ai passé le test"
4. Workflow vérifie CRM → Date_test_selection non vide
5. État: CAS B → ELIGIBLE (plus de blocage)
6. Si Date_examen_VTC vide → template propose dates + sessions automatiquement
```

**Pas besoin d'intention spéciale** : L'état est basé sur les données CRM, pas sur ce que le candidat dit. Une fois `Date_test_selection` rempli, le candidat sort automatiquement de CAS B.

### Ajout d'un Nouvel Intent ou État

**⚠️ TOUJOURS vérifier d'abord avec les commandes de la section "Règle d'Or" ci-dessus !**

1. Vérifier qu'il n'existe pas (grep dans les YAML)
2. Ajouter dans le fichier YAML approprié
3. Créer/modifier le template si nécessaire (en `.html`, pas `.md`)
4. Tester avec un ticket réel

### Vérification de la Couverture Templates

```bash
# Vérifier qu'aucun template ne manque (avec base_legacy)
python -c "
import re, os
with open('states/state_intention_matrix.yaml') as f:
    templates = set(re.findall(r'template:\s*[\"']?([\\w_-]+\\.html)', f.read()))
existing = set(os.listdir('states/templates/base_legacy'))
missing = templates - existing - {'response_master.html'}  # response_master est à la racine
print(f'Manquants: {len(missing)}')
for t in sorted(missing): print(f'  - {t}')
"

# Vérifier que tous les partials existent
ls states/templates/partials/*/
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
- **CAS D** : Compte_Uber = false (après vérif J+1) → Email ≠ compte Uber Driver → Contacter Uber
- **CAS E** : ELIGIBLE = false (après vérif J+1) → Non éligible selon Uber → Contacter Uber
- **CAS B** : Dossier envoyé mais test non passé (si > 19/05/2025) → Demander de passer le test
- **ÉLIGIBLE** : Toutes vérifications OK → Peut être inscrit à l'examen

**Timing vérification Uber :** La vérification Compte_Uber et ELIGIBLE se fait à `Date_Dossier_recu + 1 jour`.
Avant ce délai, on ne bloque pas le candidat (vérification en attente).

### Doublon Uber 20€ (IMPORTANT)
**L'offre Uber 20€ n'est valable qu'UNE SEULE FOIS par candidat.**

**Détection :** Si un contact a plusieurs opportunités avec `Amount = 20` ET `Stage = GAGNÉ` → DOUBLON

**Comportement du workflow :**
1. Le `DealLinkingAgent` détecte automatiquement les doublons (`has_duplicate_uber_offer = True`)
2. Le workflow s'arrête à l'étape TRIAGE avec l'action `DUPLICATE_UBER`
3. Une réponse spécifique est générée expliquant que l'offre a déjà été utilisée

**Options proposées au candidat :**
- **Inscription autonome** : S'inscrire sur ExamT3P et payer les 241€ lui-même
- **Formation avec nous** : Formation VISIO ou présentiel (à ses frais)

**Code de détection :**
```python
# Dans DealLinkingAgent.process()
deals_20_won = [d for d in all_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]
if len(deals_20_won) > 1:
    result["has_duplicate_uber_offer"] = True
    result["duplicate_deals"] = deals_20_won
```

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

---

## Fichiers de Référence

### `crm_schema.json`
Schéma complet des modules et champs Zoho CRM (extrait automatiquement).
Utile pour connaître les noms API exacts des champs.

### `desk_departments.json`
Liste de tous les départements Zoho Desk avec leurs IDs.
```python
# Structure
{
    "departments": {
        "DOC": {"id": "198709000025523146", "is_enabled": true},
        "DOCS CAB": {"id": "198709000102030275", "is_enabled": true},
        "Refus CMA": {"id": "198709000092515473", "is_enabled": true},
        "Contact": {"id": "198709000025227670", "is_enabled": true},
        ...
    },
    "active_department_names": ["DOC", "DOCS CAB", "Refus CMA", ...]
}
```

**Scripts de mise à jour :**
- `python extract_crm_schema.py` → Met à jour `crm_schema.json`
- `python list_departments.py` → Affiche les départements (màj manuelle du JSON)

---

## Commandes Utiles

```bash
# Lister les tickets récents
python list_recent_tickets.py

# Tester le workflow complet
python test_doc_workflow_with_examt3p.py <ticket_id>

# Tester le State Engine sur 5 tickets
python test_state_engine_sections.py

# Analyser un lot de tickets (utilise data/open_doc_tickets.txt)
python analyze_lot.py 11 20  # Lot 2: tickets 11-20
python analyze_lot.py 21 30  # Lot 3: tickets 21-30

# Clôturer les tickets SPAM identifiés
python close_spam_tickets.py data/lot2_analysis_11_20.json --dry-run  # Prévisualisation
python close_spam_tickets.py data/lot2_analysis_11_20.json            # Clôture réelle
```

### Liste des 356 tickets DOC ouverts

Fichier de référence : `data/open_doc_tickets.txt` (1 ID par ligne)

Les lots sont analysés par tranches de 10 tickets.

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

## Intentions Spéciales (Routing Automatique)

### DEMANDE_SUPPRESSION_DONNEES (I37) - RGPD
**Demande de suppression de données personnelles → Route automatiquement vers département "Contact"**

```yaml
# Dans state_intention_matrix.yaml
DEMANDE_SUPPRESSION_DONNEES:
  id: "I37"
  triggers:
    - "suppression"
    - "supprimer mes données"
    - "droit à l'oubli"
  routing: "Contact"
  priority: 90
```

Le TriageAgent détecte automatiquement cette intention et retourne `action: ROUTE, target: Contact`.

---

## À Faire Avant de Coder

1. **Chercher dans les helpers** : `grep -r "fonction_recherchée" src/utils/`
2. **Vérifier les agents** : `ls src/agents/`
3. **Vérifier les alertes** : `cat alerts/active_alerts.yaml`
4. **Vérifier les intents existants** : `grep -E "^  [A-Z_]+:" states/state_intention_matrix.yaml`
5. **Vérifier les templates existants** : `ls states/templates/base_legacy/` et `ls states/templates/partials/*/`
6. **Vérifier les partials** : `ls states/templates/partials/*/`
7. **Lire ce fichier** : Les fonctions sont documentées ici
8. **Ne pas dupliquer** : Si une fonction existe, l'utiliser !
