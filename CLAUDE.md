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
result = agent.triage_ticket(ticket_id)
# Retourne:
#   action (GO/ROUTE/SPAM)
#   target_department
#   reason, confidence
#   detected_intent (ex: "CONFIRMATION_SESSION", "REPORT_DATE")
#   intent_context: {
#       is_urgent, mentions_force_majeure, force_majeure_type,
#       wants_earlier_date, session_preference ("jour"|"soir"|null)
#   }
```

**Actions possibles :**
- `GO` : Ticket DOC valide, continuer le workflow
- `ROUTE` : Transférer vers autre département (Contact, Partenariat, etc.)
- `SPAM` : Spam/pub, clôturer sans réponse

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

### 4. ResponseGeneratorAgent (`src/agents/response_generator_agent.py`)
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

**Important :**
- L'agent extrait automatiquement les mises à jour CRM via le bloc `[CRM_UPDATES]...[/CRM_UPDATES]`
- Les alertes temporaires sont automatiquement injectées dans le prompt

### 5. ExamT3PAgent (`src/agents/examt3p_agent.py`)
**Extrait les données de la plateforme ExamT3P.**

```python
from src.agents.examt3p_agent import ExamT3PAgent

agent = ExamT3PAgent()
data = agent.extract_data(identifiant, mot_de_passe)
# Retourne: documents, paiements, examens, statut_dossier, num_dossier, etc.
```

### 6. TicketDispatcherAgent (`src/agents/dispatcher_agent.py`)
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
Le filtrage est appliqué automatiquement dans `ResponseGeneratorAgent._format_data_sources()`.
L'IA reçoit uniquement les dates pertinentes, pas besoin de règles manuelles dans le prompt.

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
- `Session` → Attend un **ID** (bigint), pas un nom de session (⚠️ PAS `Session_choisie`)
- Utiliser `find_exam_session_by_date_and_dept()` pour obtenir l'ID

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

**Le Legacy fournit la LOGIQUE et les DONNÉES, le State Engine fournit le ROUTING et le RENDU.**

Le système génère les réponses de manière **déterministe** :
1. **ÉTAT** = situation factuelle du candidat (détecté depuis CRM/ExamT3P)
2. **INTENTION** = ce que le candidat demande (détecté par TriageAgent via IA)
3. **TEMPLATE** = réponse adaptée à la combinaison ÉTAT × INTENTION

### Fichiers Source de Vérité

| Fichier | Contenu |
|---------|---------|
| `states/candidate_states.yaml` | **~25 ÉTATS** (T1-T4, A0-A3, U01-U06, E01-E13, etc.) |
| `states/state_intention_matrix.yaml` | **37 INTENTIONS** (I01-I37) + MATRICE État×Intention |
| `states/templates/base/*.html` | **62 Templates** HTML (tous en .html, pas .md) |
| `states/blocks/*.md` | Blocs réutilisables (salutation, signature, etc.) |
| `states/VARIABLES.md` | Documentation des variables Handlebars |

### Détection d'Intent et Contexte par TriageAgent

```python
triage_result = triage_agent.triage_ticket(ticket_id)
# Retourne: action, detected_intent, intent_context

# Structure de intent_context:
{
    "is_urgent": True | False,
    "mentions_force_majeure": True | False,
    "force_majeure_type": "medical" | "death" | "accident" | "childcare" | "other" | None,
    "force_majeure_details": "description courte" | None,
    "wants_earlier_date": True | False,
    "session_preference": "jour" | "soir" | None  # NOUVEAU - extrait automatiquement
}
```

**Le TriageAgent extrait automatiquement `session_preference`** quand le candidat mentionne "cours du jour", "cours du soir", etc.

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
{{session_message}}             <!-- Message pré-formaté du legacy -->
{{#each sessions_proposees}}    <!-- Liste aplatie des sessions -->
  {{this.nom}}                  <!-- Nom de la session -->
  {{this.debut}}                <!-- Date début formatée -->
  {{this.fin}}                  <!-- Date fin formatée -->
  {{this.date_examen}}          <!-- Date examen associée -->
  {{this.departement}}          <!-- Département -->
  {{this.type}}                 <!-- "jour" ou "soir" -->
  {{this.is_jour}}              <!-- true/false -->
  {{this.is_soir}}              <!-- true/false -->
{{/each}}
```

### Logique de Sélection Template (TemplateEngine)

L'ordre de priorité dans `_select_base_template()` :

1. **PASS 0** : Matrice `STATE:INTENTION` (priorité maximale)
   ```python
   # Cherche "DATE_EXAMEN_VIDE:CONFIRMATION_SESSION" dans state_intention_matrix
   matrix_key = f"{state.name}:{intention}"
   if matrix_key in self.state_intention_matrix:
       return config['template']  # ex: "confirmation_session.html"
   ```

2. **PASS 1** : Templates avec intention (`for_intention` + `for_condition`)
3. **PASS 2** : Templates avec condition seule
4. **PASS 3** : Cas Uber (A, B, D, E)
5. **PASS 4** : Résultat examen
6. **PASS 5** : Evalbox (statut dossier)
7. **Fallback** : Par nom d'état normalisé

### Transformation des Données Legacy → Template

Le `TemplateEngine` utilise `_flatten_session_options()` pour transformer les données du legacy `session_helper` en format utilisable par les templates :

```python
# Input (legacy session_helper format):
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

### Ajout d'un Nouvel Intent ou État

**⚠️ TOUJOURS vérifier d'abord avec les commandes de la section "Règle d'Or" ci-dessus !**

1. Vérifier qu'il n'existe pas (grep dans les YAML)
2. Ajouter dans le fichier YAML approprié
3. Créer/modifier le template si nécessaire (en `.html`, pas `.md`)
4. Tester avec un ticket réel

### Vérification de la Couverture Templates

```bash
# Vérifier qu'aucun template ne manque
python -c "
import re, os
with open('states/state_intention_matrix.yaml') as f:
    templates = set(re.findall(r'template:\s*[\"']?([\\w_-]+\\.html)', f.read()))
existing = set(os.listdir('states/templates/base'))
missing = templates - existing
print(f'Manquants: {len(missing)}')
for t in sorted(missing): print(f'  - {t}')
"
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

# Tester la génération de réponse seule
python -c "from src.agents.response_generator_agent import ResponseGeneratorAgent; ..."
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
5. **Vérifier les templates existants** : `ls states/templates/base/`
6. **Lire ce fichier** : Les fonctions sont documentées ici
7. **Ne pas dupliquer** : Si une fonction existe, l'utiliser !
