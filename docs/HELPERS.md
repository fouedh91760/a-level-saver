# Helpers Reference

## Vue d'ensemble

Les helpers encapsulent la logique métier et les opérations complexes.

| Helper | Fichier | Rôle |
|--------|---------|------|
| ExamT3P CRM Sync | `examt3p_crm_sync.py` | Synchronisation ExamT3P ↔ CRM |
| CRM Lookup | `crm_lookup_helper.py` | Enrichissement champs lookup |
| Credentials | `examt3p_credentials_helper.py` | Extraction identifiants |
| Date Examen VTC | `date_examen_vtc_helper.py` | Analyse dates examen (10 cas) |
| Session | `session_helper.py` | Sélection sessions formation |
| Uber Eligibility | `uber_eligibility_helper.py` | Cas Uber A/B/D/E |
| Alerts | `alerts_helper.py` | Alertes temporaires |
| Date Utils | `date_utils.py` | Parsing dates flexible |
| Response Humanizer | `response_humanizer.py` | Reformulation IA |
| Training Consistency | `training_exam_consistency_helper.py` | Cohérence formation/examen |

---

## 1. Synchronisation ExamT3P → CRM

**Fichier :** `src/utils/examt3p_crm_sync.py`

### Fonctions principales
```python
from src.utils.examt3p_crm_sync import (
    sync_examt3p_to_crm,              # Sync complète ExamT3P → CRM
    sync_exam_date_from_examt3p,      # Sync date d'examen
    find_exam_session_by_date_and_dept,  # Trouve l'ID session
    determine_evalbox_from_examt3p,   # Mapping statut ExamT3P → Evalbox
    can_modify_exam_date,             # Vérifie si modification autorisée
)
```

### Champs synchronisés
| Champ CRM | Source | Description |
|-----------|--------|-------------|
| `Evalbox` | statut_dossier | Statut du dossier ExamT3P |
| `IDENTIFIANT_EVALBOX` | identifiant | Email ExamT3P |
| `MDP_EVALBOX` | mot_de_passe | Mot de passe ExamT3P |
| `NUM_DOSSIER_EVALBOX` | num_dossier | Numéro de dossier CMA |
| `Date_examen_VTC` | date_examen | Date d'examen (si différente) |

### Trouver une session par date et département
```python
# CRITIQUE pour mapper date string → ID session
session = find_exam_session_by_date_and_dept(crm_client, "2026-03-31", "75")
session_id = session.get('id')  # Utiliser cet ID pour update_deal
```

### Mapping ExamT3P → Evalbox
| Statut ExamT3P | Evalbox CRM |
|----------------|-------------|
| En cours de composition | Dossier crée |
| En attente de paiement | Pret a payer |
| En cours d'instruction | Dossier Synchronisé |
| Incomplet | Refusé CMA |
| Valide | VALIDE CMA |
| En attente de convocation | Convoc CMA reçue |

---

## 2. Lookups CRM Enrichis

**Fichier :** `src/utils/crm_lookup_helper.py`

### Pourquoi ce helper est CRITIQUE

Les champs `Date_examen_VTC` et `Session` sont des **lookups** qui retournent `{name, id}`.
**Ce n'est PAS la vraie donnée !** C'est juste une référence.

```python
# PROBLÈME : deal['Date_examen_VTC'] = {'name': '34_2026-03-31', 'id': '145617...'}
# Le 'name' n'est PAS la vraie date !

# SOLUTION : utiliser ce helper
from src.utils.crm_lookup_helper import enrich_deal_lookups

lookup_cache = {}  # Cache partagé pour éviter les appels répétés
enriched = enrich_deal_lookups(crm_client, deal_data, lookup_cache)

date_examen = enriched['date_examen']        # '2026-03-31' (vraie date)
date_cloture = enriched['date_cloture']      # '2026-03-15'
departement = enriched['departement']        # '75'
session_type = enriched['session_type']      # 'jour' ou 'soir'
session_name = enriched['session_name']      # 'Cours du soir mars 2026'
```

### Fonctions disponibles
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
```

### Modules de référence
| Champ lookup | Module CRM | Champs utiles |
|--------------|------------|---------------|
| `Date_examen_VTC` | `Dates_Examens_VTC_TAXI` | `Date_Examen`, `Departement`, `Date_Cloture_Inscription` |
| `Session` | `Sessions1` | `Name`, `session_type`, `Date_d_but`, `Date_de_fin` |

**NE JAMAIS utiliser regex sur `lookup.get('name')` !** Toujours utiliser ce helper.

---

## 3. Gestion des Identifiants ExamT3P

**Fichier :** `src/utils/examt3p_credentials_helper.py`

### Fonctionnement
1. Cherche d'abord dans le CRM
2. Si pas trouvé, utilise l'IA pour extraire des threads (plus fiable que regex)
3. Teste la connexion ExamT3P
4. Gère les cas de double compte

### Usage
```python
from src.utils.examt3p_credentials_helper import get_credentials_with_validation

result = get_credentials_with_validation(
    deal_data=deal_data,
    threads=threads_data,
    examt3p_agent=agent
)

# Structure retournée
{
    'identifiant': 'email@example.com',
    'mot_de_passe': '****',
    'compte_existe': True,
    'connection_test_success': True,
    'credentials_source': 'crm',  # ou 'threads'
    'should_respond_to_candidate': bool,
    'double_account_detected': bool
}
```

---

## 4. Analyse Date Examen VTC

**Fichier :** `src/utils/date_examen_vtc_helper.py`

### Les 10 cas gérés
| Cas | Description | Comportement |
|-----|-------------|--------------|
| 1 | Date vide | Proposer dates |
| 2 | Date passée + non validé | Proposer nouvelles dates |
| 3 | Refusé CMA | Corriger documents |
| 4 | VALIDE CMA + future | Attendre convocation |
| 5 | Dossier Synchronisé + future | Surveiller paiement |
| 6 | Autre statut + future | Compléter dossier |
| 7 | Date passée + validé | Examen passé, résultat ? |
| 8 | Deadline ratée | Proposer alternatives |
| 9 | Convoc reçue | Préparer examen |
| 10 | Prêt à payer | Surveiller paiement |

### Usage
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

# Structure retournée
{
    'case': 1,  # 1-10
    'next_dates': [...],
    'should_include_in_response': True,
    'response_message': '...',
    'alternative_department_dates': [...],
    'can_choose_other_department': True,
    'current_departement': '75'
}
```

### Dates alternatives autres départements
```python
# Si candidat n'a PAS encore de compte ExamT3P → peut choisir n'importe quel dept
alt_dates = get_earlier_dates_other_departments(
    crm_client,
    current_departement="75",
    reference_date="2026-06-30",
    limit=3
)
```

### Règles flexibilité département
- `can_choose_other_department = True` si `compte_existe == False`
- Si compte ExamT3P existe → département assigné, changement = nouveau compte

---

## 5. Filtrage Intelligent par Région

**Fichier :** `src/utils/date_examen_vtc_helper.py`

### Fonctions
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
    text="Je suis dans le Pays de la Loire",
    department="49"
)
# Retourne: "Pays de la Loire"

# Filtrer les dates intelligemment
filtered_dates = filter_dates_by_region_relevance(
    all_dates=next_dates,
    candidate_message="Je suis dans le Pays de la Loire",
    candidate_department=None
)
```

### Logique de filtrage
1. Détecte la région via : département CRM → mention région → mention ville
2. Garde TOUTES les dates de la région du candidat
3. Garde autres régions SEULEMENT si date PLUS TÔT
4. Élimine les régions éloignées avec mêmes dates

### Mappings disponibles
- `DEPT_TO_REGION` : tous les départements français → région
- `REGION_TO_DEPTS` : région → liste de départements
- `CITY_TO_REGION` : 50+ villes principales → région
- `REGION_ALIASES` : aliases ("PDL", "IDF", "alsace") → région officielle

---

## 6. Sessions de Formation

**Fichier :** `src/utils/session_helper.py`

### Usage
```python
from src.utils.session_helper import analyze_session_situation

result = analyze_session_situation(
    deal_data=deal_data,
    exam_dates=next_dates,
    threads=threads_data,
    crm_client=crm_client,
    triage_session_preference="soir"  # Préférence extraite par TriageAgent
)

# Structure retournée
{
    'session_preference': 'jour' | 'soir' | None,
    'proposed_options': [...],
    'message': '...'
}
```

### Logique de sélection
| Situation | Comportement |
|-----------|--------------|
| Date examen existe | Auto-sélection meilleure session selon préférence |
| Pas de date examen | Proposition dates + sessions, demande confirmation |

### Priorité préférence
1. `triage_session_preference` (TriageAgent)
2. `deal_data['Preference_horaire']` (CRM)
3. Analyse IA des threads

---

## 7. Éligibilité Uber 20€

**Fichier :** `src/utils/uber_eligibility_helper.py`

### Usage
```python
from src.utils.uber_eligibility_helper import analyze_uber_eligibility

result = analyze_uber_eligibility(deal_data)

# Structure retournée
{
    'is_uber_20_deal': True,
    'case': 'A' | 'B' | 'D' | 'E' | 'PROSPECT' | 'ELIGIBLE',
    'is_eligible': True,
    'response_message': '...'
}
```

### Ordre de vérification
```
PROSPECT → NOT_UBER → CAS A → CAS D → CAS E → CAS B → ÉLIGIBLE
```

### Timing vérification D/E
La vérification `Compte_Uber` et `ELIGIBLE` se fait à `Date_Dossier_recu + 1 jour`.
Avant ce délai, on ne bloque pas le candidat.

---

## 8. Alertes Temporaires

**Fichier :** `src/utils/alerts_helper.py`

### Usage
```python
from src.utils.alerts_helper import get_alerts_for_response, get_active_alerts

# Récupérer les alertes formatées pour le prompt
alerts_text = get_alerts_for_response(deal_data=deal_data, examt3p_data=examt3p_data)

# Ou récupérer la liste des alertes actives
alerts = get_active_alerts(evalbox_status="Convoc CMA reçue", department="75")
```

### Configuration (alerts/active_alerts.yaml)
```yaml
alerts:
  - id: "double_convocation_jan2026"
    active: true
    start_date: "2026-01-25"
    end_date: "2026-01-31"
    title: "Double convocation CMA"
    context: "La CMA a envoyé deux convocations par erreur"
    instruction: "Dire au candidat de prendre la seconde"
    applies_to:
      evalbox: ["Convoc CMA reçue", "VALIDE CMA"]
```

---

## 9. Parsing de Dates

**Fichier :** `src/utils/date_utils.py`

### Pourquoi utiliser ce module
Les dates viennent de sources multiples (CRM, ExamT3P, API) avec formats différents.
Ce module gère tous les formats de manière robuste.

### Usage
```python
from src.utils.date_utils import (
    parse_date_flexible,       # Parse date → datetime.date
    parse_datetime_flexible,   # Parse datetime → datetime.datetime
    format_date_for_display,   # Formate pour affichage (DD/MM/YYYY)
    is_date_before,            # Compare date1 < date2
    is_date_after,             # Compare date1 > date2
    days_between,              # Nombre de jours entre dates
    add_days,                  # Ajoute des jours
)

# Exemples
date = parse_date_flexible("2026-03-31")           # datetime.date(2026, 3, 31)
date = parse_date_flexible("2026-03-31T10:30:00Z") # datetime.date(2026, 3, 31)
date = parse_date_flexible("31/03/2026")           # datetime.date(2026, 3, 31)
```

### Formats supportés (ordre de priorité)
```python
DATE_FORMATS = [
    "%Y-%m-%d",                    # 2026-03-31
    "%Y-%m-%dT%H:%M:%S",           # 2026-03-31T10:30:00
    "%Y-%m-%dT%H:%M:%S.%f",        # 2026-03-31T10:30:00.000
    "%Y-%m-%dT%H:%M:%SZ",          # 2026-03-31T10:30:00Z
    "%d/%m/%Y",                    # 31/03/2026
    "%d-%m-%Y",                    # 31-03-2026
]
```

**TOUJOURS utiliser `parse_date_flexible()` au lieu de parsers inline.**

---

## 10. Response Humanizer

**Fichier :** `src/utils/response_humanizer.py`

### Usage
```python
from src.utils.response_humanizer import humanize_response

result = humanize_response(
    template_response=response_html,    # Sortie du TemplateEngine
    candidate_message=customer_message, # Message du candidat
    candidate_name="Aziz",              # Prénom pour personnalisation
    use_ai=True                         # Activer l'humanisation
)

humanized_email = result['humanized_response']
```

### Ce que fait le Humanizer
- Fusionne "Concernant X" + "Concernant Y" en paragraphes fluides
- Ajoute transitions naturelles
- Rend le ton chaleureux et professionnel
- Préserve 100% des données factuelles

### Ce que le Humanizer NE FAIT JAMAIS
- Ajouter des explications métier
- Inventer des informations
- Modifier dates, liens, identifiants
- Faire des promesses non présentes dans le template

### Validation automatique
Le Humanizer vérifie que toutes les dates, URLs et emails sont préservés.
Si la validation échoue → retourne la réponse template originale.

---

## 11. Cohérence Formation/Examen

**Fichier :** `src/utils/training_exam_consistency_helper.py`

### Usage
```python
from src.utils.training_exam_consistency_helper import analyze_training_exam_consistency

result = analyze_training_exam_consistency(
    deal_data=deal_data,
    threads=threads,
    session_data=session_data,
    crm_client=crm_client
)
```

### Cas détectés
- Formation manquée + examen imminent
- Incohérence dates formation/examen
- Session non commencée
