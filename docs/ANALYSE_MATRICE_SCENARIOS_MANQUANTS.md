# Analyse Matrice État×Intention - Scénarios Manquants

**Date**: 2026-02-06
**Fichiers analysés**:
- `states/candidate_states.yaml` (38 états)
- `states/state_intention_matrix.yaml` (50 intentions, ~120 entrées matrice)
- `states/templates/response_master.html` (template master)
- `states/templates/partials/**/*.html` (82 partials)
- `src/state_engine/template_engine.py` (INTENTION_FLAG_MAP + _auto_map_intention_flags)
- `src/agents/triage_agent.py` (détection d'intentions)

---

## Résumé Exécutif

| Catégorie | Nombre | Sévérité |
|-----------|--------|----------|
| Intentions sans wildcard ni partial | 4 | **CRITIQUE** |
| Intentions avec flag mais sans wildcard | 6 | **HAUTE** |
| Intentions avec entrées spécifiques uniquement | 5 | **MOYENNE** |
| Entrées matrice avec noms d'états obsolètes (dead code) | ~20 | **HAUTE** |
| Partial/flag existant mais jamais rendu | 1 | **BASSE** |
| États sans entrées spécifiques (wildcards only) | 5 | **INFO** |

---

## CATÉGORIE 1 — CRITIQUE : Intentions Totalement Absentes

Ces intentions sont détectées par le TriageAgent mais n'ont **ni wildcard `*:INTENTION`**, **ni entrée `INTENTION_FLAG_MAP`**, **ni partial dans `response_master.html`**. Résultat : **template fallback minimal** (juste salutation + personnalisation IA).

### 1.1 ANNONCE_RESULTAT_POSITIF (I21)

- **Trigger**: "j'ai réussi mon examen", "je suis admis"
- **Détecté par TriageAgent**: Oui (`triage_agent.py:247`)
- **Wildcard `*:ANNONCE_RESULTAT_POSITIF`**: **ABSENT**
- **INTENTION_FLAG_MAP**: **ABSENT**
- **Partial**: **ABSENT**
- **Impact**: Le candidat annonce sa réussite → réponse générique sans félicitations ni prochaines étapes carte VTC

**Fix**: Ajouter `*:ANNONCE_RESULTAT_POSITIF` → `response_master.html` avec flags `resultat_admis: true` + utiliser le partial existant `partials/resultats/admis.html`

### 1.2 ANNONCE_RESULTAT_NEGATIF (I22)

- **Trigger**: "j'ai raté", "j'ai échoué", "recalé"
- **Détecté par TriageAgent**: Oui (`triage_agent.py:249`)
- **Wildcard `*:ANNONCE_RESULTAT_NEGATIF`**: **ABSENT**
- **INTENTION_FLAG_MAP**: **ABSENT**
- **Partial**: **ABSENT**
- **Impact**: Le candidat annonce son échec → réponse générique sans empathie ni proposition de réinscription

**Fix**: Ajouter `*:ANNONCE_RESULTAT_NEGATIF` → `response_master.html` avec flags `resultat_non_admis: true` + utiliser le partial existant `partials/resultats/non_admis.html`

### 1.3 DEMANDE_CERTIFICAT_FORMATION (I32)

- **Trigger**: "certificat de formation", "attestation", "France Travail me demande"
- **Détecté par TriageAgent**: Oui (`triage_agent.py:187`, rule `triage_agent.py:744`)
- **Wildcard `*:DEMANDE_CERTIFICAT_FORMATION`**: **ABSENT**
- **INTENTION_FLAG_MAP**: **ABSENT**
- **Partial**: **ABSENT** (pas de `partials/intentions/demande_certificat.html`)
- **Impact**: Demande fréquente (France Travail) → réponse vide

**Fix**: Créer partial `partials/intentions/demande_certificat.html` + ajouter wildcard `*:DEMANDE_CERTIFICAT_FORMATION` + ajouter dans `INTENTION_FLAG_MAP` + ajouter `{{#if}}` dans `response_master.html`

### 1.4 DEMANDE_SUPPRESSION_DONNEES (I37)

- **Trigger**: "supprimer mes données", "droit à l'oubli", "RGPD"
- **Détecté par TriageAgent**: Oui (`triage_agent.py:82`)
- **Routing prévu**: Contact (jc@cab-formations.fr)
- **Wildcard `*:DEMANDE_SUPPRESSION_DONNEES`**: **ABSENT**
- **INTENTION_FLAG_MAP**: **ABSENT**
- **Partial**: **ABSENT**
- **Impact**: Demande RGPD légalement obligatoire → réponse vide, pas de routing

**Fix**: Ajouter wildcard `*:DEMANDE_SUPPRESSION_DONNEES` avec routing vers Contact, ou ajouter dans triage comme ROUTE

---

## CATÉGORIE 2 — HAUTE : Intentions avec Flag Auto-Mappé mais Sans Wildcard

Ces intentions ont une entrée dans `INTENTION_FLAG_MAP` (le flag est posé) **mais pas de wildcard `*:INTENTION`**. Le flag est posé mais inutile car le template sélectionné est le **fallback minimal** (pas `response_master.html`).

### 2.1 QUESTION_EXAMEN_PRATIQUE (I31)

- **INTENTION_FLAG_MAP**: `intention_question_examen_pratique` ✓
- **Partial**: `partials/intentions/question_examen_pratique.html` ✓
- **`response_master.html`**: `{{#if intention_question_examen_pratique}}` ligne 197 ✓
- **Wildcard**: **ABSENT** ❌
- **Impact**: Flag posé + partial prêt + reference dans master MAIS jamais rendu car template fallback utilisé

**Fix**: Ajouter `*:QUESTION_EXAMEN_PRATIQUE` dans la matrice :
```yaml
"*:QUESTION_EXAMEN_PRATIQUE":
  template: "response_master.html"
  context_flags:
    intention_question_examen_pratique: true
    show_statut_section: true
```

### 2.2 DEMANDE_AUTRES_DATES (I09)

- **INTENTION_FLAG_MAP**: `intention_demande_date` ✓
- **Entrées spécifiques**: EXAM_DATE_EMPTY, UBER_DOCS_MISSING, UBER_TEST_MISSING, PROSPECT_UBER_20
- **Wildcard**: **ABSENT** ❌
- **Impact**: Pour les états non couverts (DOSSIER_SYNCHRONIZED, READY_TO_PAY, etc.) → fallback

**Fix**: Ajouter `*:DEMANDE_AUTRES_DATES` :
```yaml
"*:DEMANDE_AUTRES_DATES":
  template: "response_master.html"
  context_flags:
    intention_demande_date: true
    show_dates_section: true
    include_other_departments: true
```

### 2.3 FORCE_MAJEURE_REPORT (I11)

- **INTENTION_FLAG_MAP**: `intention_report_date` ✓
- **Entrée spécifique**: BLOCAGE_MODIFICATION_DATE:FORCE_MAJEURE_REPORT uniquement
- **Wildcard**: **ABSENT** ❌
- **Impact**: Candidat mentionne "certificat médical" avec un état non-BLOCAGE → fallback

**Fix**: Ajouter `*:FORCE_MAJEURE_REPORT` :
```yaml
"*:FORCE_MAJEURE_REPORT":
  template: "response_master.html"
  context_flags:
    intention_report_date: true
    report_force_majeure: true
    show_statut_section: true
```

### 2.4 ENVOIE_DOCUMENTS (I14)

- **INTENTION_FLAG_MAP**: `intention_probleme_documents` ✓
- **Wildcard**: **ABSENT** ❌
- **Impact**: Candidat confirme avoir uploadé ses documents → réponse fallback au lieu d'accusé réception

**Fix**: Ajouter `*:ENVOIE_DOCUMENTS` :
```yaml
"*:ENVOIE_DOCUMENTS":
  template: "response_master.html"
  context_flags:
    intention_probleme_documents: true
    show_statut_section: true
```
Note: Le mapping vers `intention_probleme_documents` est discutable — un flag dédié `intention_envoie_documents` serait plus approprié.

### 2.5 TRANSMET_DOCUMENTS (I14b) — Cas GO (Date_Dossier_reçu vide)

- **INTENTION_FLAG_MAP**: **ABSENT**
- **Wildcard**: **ABSENT** ❌
- **Routing**: Normalement ROUTE vers "Refus CMA", SAUF si Date_Dossier_reçu est vide → GO
- **Impact**: Envoi initial de documents en pièce jointe → aucune réponse structurée

**Fix**: Ajouter dans INTENTION_FLAG_MAP + créer wildcard ou gérer dans le routing

### 2.6 ENVOIE_IDENTIFIANTS (I15)

- **INTENTION_FLAG_MAP**: `intention_demande_identifiants` ✓
- **Wildcard**: **ABSENT** ❌
- **Impact**: Candidat partage ses identifiants → devrait accusé-réceptionner et enregistrer

**Fix**: Ajouter `*:ENVOIE_IDENTIFIANTS` :
```yaml
"*:ENVOIE_IDENTIFIANTS":
  template: "response_master.html"
  context_flags:
    intention_demande_identifiants: true
    show_statut_section: true
```

---

## CATÉGORIE 3 — MOYENNE : Intentions avec Entrées Spécifiques Uniquement

Ces intentions ont des entrées pour certains états mais pas de wildcard. Les états non couverts tombent en fallback.

### 3.1 DEMANDE_REINSCRIPTION (I23)

- **Entrées**: `EXAM_DATE_PAST_VALIDATED:DEMANDE_REINSCRIPTION`, `RESULTAT_NON_ADMIS:DEMANDE_REINSCRIPTION`
- **Pas de wildcard**
- **Pas dans INTENTION_FLAG_MAP**
- **Pas de partial dans response_master.html**
- **Impact**: Si état = EXAM_PASSED_AWAITING_RESULTS ou DEADLINE_MISSED → fallback

**Fix**: Ajouter wildcard `*:DEMANDE_REINSCRIPTION` + créer partial + ajouter dans INTENTION_FLAG_MAP

### 3.2 QUESTION_CARTE_VTC (I30)

- **Entrée**: `RESULTAT_ADMIS:QUESTION_CARTE_VTC` uniquement
- **Pas de wildcard** (note: RESULTAT_ADMIS n'est pas un état dans `candidate_states.yaml`)
- **Pas dans INTENTION_FLAG_MAP**
- **Impact**: Candidat non-ADMIS qui demande la carte VTC → fallback

**Fix**: Ajouter wildcard `*:QUESTION_CARTE_VTC` + créer partial

### 3.3 DEMANDE_INFOS_OFFRE (I08)

- **Entrée**: `PROSPECT_UBER_20:DEMANDE_INFOS_OFFRE` (NOM OBSOLÈTE — voir Catégorie 4)
- **Pas de wildcard**
- **Impact**: L'entrée spécifique NE MATCHERA JAMAIS (nom état obsolète). Aucun état ne gère cette intention.

**Fix**: Ajouter wildcard `*:DEMANDE_INFOS_OFFRE` ou renommer l'entrée en `UBER_PROSPECT:DEMANDE_INFOS_OFFRE`

### 3.4 DEMANDE_APPEL_TEL (I24)

- **Wildcard**: `*:DEMANDE_APPEL_TEL` → `demande_appel.html` ✓
- **Mais**: `demande_appel.html` n'est PAS dans le dossier templates vérifié
- **Impact**: Si le fichier template n'existe pas → erreur silencieuse

*À vérifier: existence de `demande_appel.html`*

### 3.5 DEMANDE_REMBOURSEMENT (I26)

- **Wildcard**: `*:DEMANDE_REMBOURSEMENT` → `demande_remboursement.html` ✓
- **Routing**: Comptabilité
- **Même question**: vérifier l'existence du fichier template

---

## CATÉGORIE 4 — HAUTE : Entrées avec Noms d'États Obsolètes (Dead Code)

Le `state_detector.py` crée les états avec `name=state_name` directement depuis les clés de `candidate_states.yaml` (ligne 1073). Les entrées suivantes utilisent des noms de la section `states:` (DEPRECATED) de `state_intention_matrix.yaml` et **NE MATCHERONT JAMAIS** au PASS 0a.

### 4.1 PROSPECT_UBER_20 → devrait être UBER_PROSPECT

| Entrée matrice (DEAD CODE) | Devrait être |
|---------------------------|-------------|
| `PROSPECT_UBER_20:DEMANDE_INFOS_OFFRE` | `UBER_PROSPECT:DEMANDE_INFOS_OFFRE` |
| `PROSPECT_UBER_20:DEMANDE_DATE_EXAMEN` | `UBER_PROSPECT:DEMANDE_DATE_EXAMEN` |
| `PROSPECT_UBER_20:CONFIRMATION_PAIEMENT` | `UBER_PROSPECT:CONFIRMATION_PAIEMENT` |
| `PROSPECT_UBER_20:STATUT_DOSSIER` | `UBER_PROSPECT:STATUT_DOSSIER` |
| `PROSPECT_UBER_20:DEMANDE_CONVOCATION` | `UBER_PROSPECT:DEMANDE_CONVOCATION` |
| `PROSPECT_UBER_20:DEMANDE_IDENTIFIANTS` | `UBER_PROSPECT:DEMANDE_IDENTIFIANTS` |
| `PROSPECT_UBER_20:DEMANDE_AUTRES_DATES` | `UBER_PROSPECT:DEMANDE_AUTRES_DATES` |

**Impact**: 7 entrées prospect-spécifiques (avec flag `is_prospect`) ne matchent jamais. Le wildcard prend le relais SANS le flag `is_prospect`.

### 4.2 DATE_FUTURE_VALIDE_CMA → devrait être VALIDE_CMA_WAITING_CONVOC

| Entrée matrice (DEAD CODE) | Devrait être |
|---------------------------|-------------|
| `DATE_FUTURE_VALIDE_CMA:DEMANDE_CONVOCATION` | `VALIDE_CMA_WAITING_CONVOC:DEMANDE_CONVOCATION` |
| `DATE_FUTURE_VALIDE_CMA:CONFIRMATION_SESSION` | `VALIDE_CMA_WAITING_CONVOC:CONFIRMATION_SESSION` |

**Note**: Les entrées `VALIDE_CMA_WAITING_CONVOC:REPORT_DATE` et `VALIDE_CMA_WAITING_CONVOC:DEMANDE_CONVOCATION` existent AUSSI (noms corrects). Donc doublon partiel.

### 4.3 DATE_FUTURE_DOSSIER_SYNC → devrait être DOSSIER_SYNCHRONIZED

| Entrée matrice (DEAD CODE) | Entrée correcte existante ? |
|---------------------------|---------------------------|
| `DATE_FUTURE_DOSSIER_SYNC:CONFIRMATION_SESSION` | Non — à créer comme `DOSSIER_SYNCHRONIZED:CONFIRMATION_SESSION` |

**Note**: `DOSSIER_SYNCHRONIZED:STATUT_DOSSIER`, `DOSSIER_SYNCHRONIZED:CONFIRMATION_SESSION` et `DOSSIER_SYNCHRONIZED:DEMANDE_CONVOCATION` existent déjà avec le nom correct. Donc `DATE_FUTURE_DOSSIER_SYNC:CONFIRMATION_SESSION` est bien du dead code redondant.

### 4.4 EVALBOX_REFUSE_CMA → devrait être REFUSED_CMA

| Entrée matrice (DEAD CODE) | Devrait être |
|---------------------------|-------------|
| `EVALBOX_REFUSE_CMA:DEMANDE_CONVOCATION` | `REFUSED_CMA:DEMANDE_CONVOCATION` |
| `EVALBOX_REFUSE_CMA:REPORT_DATE` | `REFUSED_CMA:REPORT_DATE` |
| `EVALBOX_REFUSE_CMA:STATUT_DOSSIER` | `REFUSED_CMA:STATUT_DOSSIER` |
| `EVALBOX_REFUSE_CMA:DOCUMENT_QUESTION` | `REFUSED_CMA:DOCUMENT_QUESTION` |

**Impact**: 4 entrées avec flags spécifiques (evalbox_refus_cma, report_deja_effectue, show_documents_refuses) ne matchent jamais.

### 4.5 DEADLINE_RATEE → devrait être DEADLINE_MISSED

| Entrée matrice (DEAD CODE) | Devrait être |
|---------------------------|-------------|
| `DEADLINE_RATEE:DEMANDE_CONVOCATION` | `DEADLINE_MISSED:DEMANDE_CONVOCATION` |
| `DEADLINE_RATEE:STATUT_DOSSIER` | `DEADLINE_MISSED:STATUT_DOSSIER` |
| `DEADLINE_RATEE:REPORT_DATE` | `DEADLINE_MISSED:REPORT_DATE` |

### 4.6 EXAMT3P_CREDENTIALS_INVALIDES → devrait être CREDENTIALS_INVALID

| Entrée matrice (DEAD CODE) | Devrait être |
|---------------------------|-------------|
| `EXAMT3P_CREDENTIALS_INVALIDES:DEMANDE_IDENTIFIANTS` | `CREDENTIALS_INVALID:DEMANDE_IDENTIFIANTS` |
| `EXAMT3P_CREDENTIALS_INVALIDES:PROBLEME_CONNEXION_EXAMT3P` | `CREDENTIALS_INVALID:PROBLEME_CONNEXION_EXAMT3P` |

### 4.7 EXAMT3P_PAS_DE_COMPTE → pas d'état correspondant

| Entrée matrice (DEAD CODE) | Note |
|---------------------------|------|
| `EXAMT3P_PAS_DE_COMPTE:STATUT_DOSSIER` | Pas d'état "EXAMT3P_PAS_DE_COMPTE" dans `candidate_states.yaml`. L'état le plus proche est `CREDENTIALS_INVALID` (A1). |

### 4.8 BLOCAGE_MODIFICATION_DATE → devrait être DATE_MODIFICATION_BLOCKED

| Entrée matrice (DEAD CODE) | Devrait être |
|---------------------------|-------------|
| `BLOCAGE_MODIFICATION_DATE:REPORT_DATE` | `DATE_MODIFICATION_BLOCKED:REPORT_DATE` |
| `BLOCAGE_MODIFICATION_DATE:FORCE_MAJEURE_REPORT` | `DATE_MODIFICATION_BLOCKED:FORCE_MAJEURE_REPORT` |

### 4.9 PRET_A_PAYER vs READY_TO_PAY

| Entrée matrice | État réel |
|----------------|-----------|
| `PRET_A_PAYER:CONFIRMATION_SESSION` | DEAD CODE (état = READY_TO_PAY) |
| `READY_TO_PAY:CONFIRMATION_SESSION` | ✓ MATCH |

**Note**: Les deux existent, seule READY_TO_PAY matche.

### 4.10 RESULTAT_ADMIS / RESULTAT_NON_ADMIS / SESSION_NON_ASSIGNEE / SESSION_ASSIGNEE_PASSEE

Ces noms d'états n'existent pas dans `candidate_states.yaml`. Toutes les entrées utilisant ces noms sont du dead code :

| Entrée | Note |
|--------|------|
| `RESULTAT_ADMIS:RESULTAT_EXAMEN` | Pas d'état RESULTAT_ADMIS |
| `RESULTAT_ADMIS:QUESTION_CARTE_VTC` | Pas d'état RESULTAT_ADMIS |
| `RESULTAT_NON_ADMIS:RESULTAT_EXAMEN` | Pas d'état RESULTAT_NON_ADMIS |
| `RESULTAT_NON_ADMIS:DEMANDE_REINSCRIPTION` | Pas d'état RESULTAT_NON_ADMIS |
| `SESSION_NON_ASSIGNEE:CONFIRMATION_SESSION` | Pas d'état SESSION_NON_ASSIGNEE |
| `SESSION_ASSIGNEE_PASSEE:DEMANDE_DATE_VISIO` | Pas d'état SESSION_ASSIGNEE_PASSEE |

---

## CATÉGORIE 5 — BASSE : Partial/Flag Non Rendu

### 5.1 `report_deja_effectue` — Flag posé mais pas dans response_master

- **Posé par**: `EVALBOX_REFUSE_CMA:REPORT_DATE` (ligne 1545, mais cette entrée est dead code)
- **Partial**: `partials/report/deja_effectue.html` existe ✓
- **response_master.html**: **Aucun `{{#if report_deja_effectue}}`** ❌
- **Impact**: Même si le flag était posé, le partial ne serait jamais rendu

**Fix**: Ajouter `{{#if report_deja_effectue}}{{> partials/report/deja_effectue}}{{/if}}` dans la Section 0 de `response_master.html`

### 5.2 `DOCUMENT_QUESTION` double-mappé dans INTENTION_FLAG_MAP

- Ligne 1225: `'DOCUMENT_QUESTION': 'intention_probleme_documents'`
- Ligne 1233: `'DOCUMENT_QUESTION': 'intention_document_question'`
- **La deuxième valeur écrase la première** (dict Python)
- **Résultat**: DOCUMENT_QUESTION → `intention_document_question` (correct)
- **Impact**: Mineur, mais code trompeur

---

## CATÉGORIE 6 — INFO : États Sans Entrées Spécifiques

Ces états n'ont aucune entrée spécifique dans la matrice. Ils fonctionnent via les wildcards, mais pourraient bénéficier d'entrées spécifiques avec des `context_flags` adaptés.

| État | Description | Risque |
|------|-------------|--------|
| `EXAM_DATE_PAST_NOT_VALIDATED` (D-2) | Date passée + non validé | Wildcard OK mais pas de flag `report_auto` |
| `UBER_NOT_ELIGIBLE` (U-E) | Non éligible Uber | Wildcard OK mais pas de flag `uber_cas_e` |
| `PERSONAL_ACCOUNT_WARNING` (A4) | Compte perso détecté | Wildcard OK |
| `TRAINING_MISSED_EXAM_IMMINENT` (C1) | Formation manquée | Wildcard OK mais pas de flags spécifiques |
| `GENERAL` (DEFAULT) | État par défaut | Wildcard OK |

---

## Plan d'Action Prioritaire

### Phase 1 — Critique (Intentions sans template)

1. Ajouter wildcards pour : `ANNONCE_RESULTAT_POSITIF`, `ANNONCE_RESULTAT_NEGATIF`, `DEMANDE_CERTIFICAT_FORMATION`, `DEMANDE_SUPPRESSION_DONNEES`
2. Créer les partials manquants pour `DEMANDE_CERTIFICAT_FORMATION` et `DEMANDE_SUPPRESSION_DONNEES`
3. Ajouter les entrées dans `INTENTION_FLAG_MAP`
4. Ajouter les `{{#if}}` dans `response_master.html`

### Phase 2 — Haute (Wildcards manquants)

5. Ajouter wildcards pour : `QUESTION_EXAMEN_PRATIQUE`, `DEMANDE_AUTRES_DATES`, `FORCE_MAJEURE_REPORT`, `ENVOIE_DOCUMENTS`, `ENVOIE_IDENTIFIANTS`, `DEMANDE_REINSCRIPTION`, `QUESTION_CARTE_VTC`, `DEMANDE_INFOS_OFFRE`
6. Renommer les ~20 entrées dead code (Catégorie 4) vers les noms corrects de `candidate_states.yaml`

### Phase 3 — Nettoyage

7. Supprimer les entrées doublons (ex: `PRET_A_PAYER:CONFIRMATION_SESSION`)
8. Ajouter `{{#if report_deja_effectue}}` dans `response_master.html`
9. Supprimer le double-mapping de `DOCUMENT_QUESTION` dans `INTENTION_FLAG_MAP`
10. Ajouter entrées spécifiques pour les états de Catégorie 6 si nécessaire
