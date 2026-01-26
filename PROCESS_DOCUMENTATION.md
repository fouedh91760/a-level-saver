# Documentation du Processus d'Inscription VTC - CAB Formations

## Vue d'Ensemble

Ce document décrit le processus métier d'inscription à l'examen VTC via le partenariat Uber/CAB Formations, identifie tous les points de divergence possibles, et documente les solutions implémentées pour ramener chaque exception vers le flux nominal.

---

## 1. LE PROCESSUS STANDARD (Happy Path)

### 1.1 Parcours Candidat Nominal

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         PROCESSUS D'INSCRIPTION VTC                              │
│                              (Offre Uber 20€)                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

ÉTAPE 1: PROSPECT
    │
    │  Le candidat découvre l'offre via Uber Driver
    │  → Paiement des 20€ sur la plateforme CAB Formations
    │
    ▼
ÉTAPE 2: CANDIDAT INSCRIT (Deal 20€ GAGNÉ)
    │
    │  Le candidat doit:
    │  ├── Envoyer ses documents (pièce d'identité, justificatif domicile, etc.)
    │  │   → CRM: Date_Dossier_reçu est renseigné
    │  │
    │  └── Passer le test de sélection (depuis 19/05/2025)
    │      → CRM: Date_test_selection est renseigné
    │
    ▼
ÉTAPE 3: CRÉATION COMPTE EXAMT3P
    │
    │  CAB Formations crée le compte ExamT3P du candidat
    │  → CRM: IDENTIFIANT_EVALBOX + MDP_EVALBOX renseignés
    │  → Email envoyé au candidat avec ses identifiants
    │
    ▼
ÉTAPE 4: CHOIX DATE D'EXAMEN
    │
    │  Le candidat choisit une date parmi les sessions disponibles
    │  → CRM: Date_examen_VTC (lookup vers module Dates_Examens_VTC_TAXI)
    │  → CRM: CMA_de_depot (département: 75, 93, etc.)
    │
    ▼
ÉTAPE 5: CHOIX SESSION DE FORMATION
    │
    │  Le candidat choisit sa session de formation:
    │  ├── Cours du jour (8h30-16h30, 1 semaine)
    │  └── Cours du soir (18h-22h, 2 semaines)
    │  → CRM: Session (lookup vers module Sessions1)
    │  → CRM: Preference_horaire (jour/soir)
    │
    ▼
ÉTAPE 6: DOSSIER SYNCHRONISÉ AVEC CMA
    │
    │  CAB paie les 241€ de frais d'examen
    │  Le dossier est envoyé à la CMA pour instruction
    │  → CRM: Evalbox = "Pret a payer" puis "Dossier Synchronisé"
    │  → ExamT3P: statut = "En cours d'instruction"
    │
    ▼
ÉTAPE 7: VALIDATION CMA
    │
    │  La CMA valide le dossier
    │  → CRM: Evalbox = "VALIDE CMA"
    │  → ExamT3P: statut = "Valide"
    │
    ▼
ÉTAPE 8: CONVOCATION
    │
    │  La CMA envoie la convocation (~10j avant examen)
    │  → CRM: Evalbox = "Convoc CMA reçue"
    │  → ExamT3P: statut = "En attente de convocation" → convocation disponible
    │
    ▼
ÉTAPE 9: PASSAGE EXAMEN
    │
    │  Le candidat passe son examen VTC
    │
    ▼
ÉTAPE 10: RÉSULTAT
    │
    ├── ADMIS → Carte VTC
    └── ÉCHEC → Possibilité de réinscription (mais 241€ à la charge du candidat)
```

### 1.2 États du Dossier (Source de Vérité: ExamT3P)

| Statut ExamT3P | Evalbox CRM | Signification |
|----------------|-------------|---------------|
| En cours de composition | Dossier crée | Documents en cours de téléchargement |
| En attente de paiement | Pret a payer | Dossier complet, prêt pour paiement CMA |
| En cours d'instruction | Dossier Synchronisé | CMA examine les documents |
| Incomplet | Refusé CMA | Documents refusés par la CMA |
| Valide | VALIDE CMA | Dossier validé, convocation à venir |
| En attente de convocation | Convoc CMA reçue | Convocation disponible sur ExamT3P |

---

## 2. ARCHITECTURE DU SYSTÈME D'AUTOMATISATION

### 2.1 Flux du Workflow (8 étapes)

```
TICKET ENTRANT (Zoho Desk - Département DOC)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: AGENT TRIEUR (TriageAgent - Claude Haiku)               │
│                                                                  │
│ Décision: GO | ROUTE | SPAM | DUPLICATE_UBER | NEEDS_CLARIFICATION│
│ + Détection d'intention: REPORT_DATE, CONFIRMATION_SESSION, etc. │
└─────────────────────────────────────────────────────────────────┘
    │
    │ Si GO →
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: AGENT ANALYSTE (6 sources de données)                   │
│                                                                  │
│ Sources:                                                         │
│ 1. CRM Zoho (deal, contact)                                     │
│ 2. ExamT3P (compte, documents, paiements)                       │
│ 3. Credentials validation (CRM ou extraction IA depuis threads) │
│ 4. Date examen VTC (10 cas possibles)                           │
│ 5. Sessions de formation                                         │
│ 6. Éligibilité Uber (CAS A/B/D/E)                               │
│                                                                  │
│ + Sync ExamT3P → CRM automatique                                │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: AGENT RÉDACTEUR (ResponseGeneratorAgent - Claude Sonnet)│
│                                                                  │
│ - RAG sur 100 réponses de référence (style Fouad)               │
│ - Injection alertes temporaires                                  │
│ - Extraction automatique des mises à jour CRM [CRM_UPDATES]     │
│ - Validation compliance (blocs obligatoires, termes interdits)  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4-8: POST-PROCESSING                                       │
│                                                                  │
│ 4. CRM Note consolidée (lien ticket, updates, next steps IA)    │
│ 5. Ticket Update (tags, statut)                                 │
│ 6. Deal Update via CRMUpdateAgent (mapping IDs, règles blocage) │
│ 7. Draft Creation (HTML dans Zoho Desk)                         │
│ 8. Validation finale + transfert DOCS CAB si VTC classique      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. EXCEPTIONS ET SOLUTIONS

### 3.1 Exceptions au Niveau TRIAGE (Step 1)

#### EXCEPTION T1: SPAM
**Point de détection:** `TriageAgent.triage_ticket()` ou keywords simples
**Condition:** Message contient viagra, casino, lottery, etc.
**Solution implémentée:**
- Action: `SPAM`
- Workflow: STOP
- Ticket: Clôturé sans réponse
- CRM: Aucune note

#### EXCEPTION T2: ROUTE vers autre département
**Point de détection:** `TriageAgent` (IA contextuelle)
**Conditions:**
- `Evalbox = "Refusé CMA"` → Refus CMA
- Demande commerciale/nouvelle formation → Contact
- Question facturation → Comptabilité
**Solution implémentée:**
- Action: `ROUTE`
- Workflow: STOP (transfert automatique)
- Ticket: Transféré vers le département cible

#### EXCEPTION T3: DOUBLON UBER 20€
**Point de détection:** `DealLinkingAgent.process()`
**Condition:** Contact a plusieurs deals avec `Amount=20` ET `Stage=GAGNÉ`
**Solution implémentée:**
- Action: `DUPLICATE_UBER`
- Workflow: Génère réponse spécifique
- Réponse: Explique que l'offre est valable une seule fois
- Options proposées: Inscription autonome (241€) ou formation payante

```python
# Détection dans deal_linking_agent.py
deals_20_won = [d for d in all_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]
if len(deals_20_won) > 1:
    result["has_duplicate_uber_offer"] = True
```

#### EXCEPTION T4: CANDIDAT NON TROUVÉ
**Point de détection:** `DealLinkingAgent.process()`
**Condition:** Aucun deal trouvé pour l'email du ticket
**Solution implémentée:**
- Action: `NEEDS_CLARIFICATION`
- Workflow: Génère réponse de clarification
- Réponse: Demande nom, prénom, email d'inscription, téléphone

---

### 3.2 Exceptions au Niveau ANALYSE (Step 2)

#### EXCEPTION A1: Identifiants ExamT3P invalides ou manquants
**Point de détection:** `get_credentials_with_validation()`
**Conditions:**
- Identifiants non trouvés dans CRM ni dans threads
- Connexion échouée (mot de passe incorrect)
**Solution implémentée:**
- Flag: `credentials_only_response = True`
- Skip: Analyse dates/sessions SKIP
- Réponse: UNIQUEMENT sur les identifiants
- Action: Demander réinitialisation mot de passe ou fournir identifiants

```python
# Dans doc_ticket_workflow.py:1005-1016
if exament3p_data.get('should_respond_to_candidate') and not exament3p_data.get('compte_existe'):
    skip_date_session_analysis = True
    skip_reason = 'credentials_invalid'
```

#### EXCEPTION A2: Connexion ExamT3P échouée (technique)
**Point de détection:** `ExamT3PAgent.process()`
**Condition:** Erreur technique lors de l'extraction (site down, timeout)
**Solution implémentée:**
- Workflow: STOP (`STOPPED_EXAMT3P_FAILED`)
- Note: Alerte interne pour intervention manuelle

#### EXCEPTION A3: Double compte ExamT3P payé
**Point de détection:** `get_credentials_with_validation()`
**Condition:** Compte CRM + compte personnel, les deux ont été payés
**Solution implémentée:**
- Flag: `duplicate_payment_alert = True`
- Action: Note CRM d'alerte urgente
- Intervention: Manuelle requise pour vérifier les paiements

---

### 3.3 Exceptions au Niveau ÉLIGIBILITÉ UBER (Step 2)

#### EXCEPTION U-PROSPECT: Candidat en attente de paiement
**Point de détection:** `analyze_uber_eligibility()`
**Condition:** `Stage = "EN ATTENTE"` + `Amount = 20`
**Solution implémentée:**
- Case: `PROSPECT`
- Réponse: Information sur l'offre + encouragement à finaliser le paiement

#### EXCEPTION U-CAS A: Documents non envoyés
**Point de détection:** `analyze_uber_eligibility()`
**Condition:** Deal 20€ GAGNÉ + `Date_Dossier_reçu = null`
**Solution implémentée:**
- Case: `A`
- Flag: `uber_case_blocks_dates = True`
- Skip: Dates/sessions SKIP
- Réponse: Expliquer l'offre + demander de finaliser inscription
- Message généré par: `generate_documents_missing_message()`

#### EXCEPTION U-CAS B: Test sélection non passé
**Point de détection:** `analyze_uber_eligibility()`
**Condition:**
- `Date_Dossier_reçu > 19/05/2025`
- `Date_test_selection = null`
**Solution implémentée:**
- Case: `B`
- Flag: `uber_case_blocks_dates = True`
- Skip: Dates/sessions SKIP
- Réponse: Demander de passer le test de sélection
- Message généré par: `generate_test_selection_missing_message()`

#### EXCEPTION U-CAS D: Compte Uber non vérifié
**Point de détection:** `analyze_uber_eligibility()`
**Condition:**
- `Date_Dossier_reçu + 1 jour < aujourd'hui`
- `Compte_Uber = false`
**Solution implémentée:**
- Case: `D`
- Flag: `uber_case_alert` (alerte dans réponse normale, pas blocage)
- Réponse: Inclut message demandant de vérifier email ou contacter Uber
- Message généré par: `generate_compte_uber_missing_message()`

#### EXCEPTION U-CAS E: Non éligible selon Uber
**Point de détection:** `analyze_uber_eligibility()`
**Condition:**
- `Date_Dossier_reçu + 1 jour < aujourd'hui`
- `ELIGIBLE = false`
**Solution implémentée:**
- Case: `E`
- Flag: `uber_case_alert` (alerte dans réponse normale, pas blocage)
- Réponse: Inclut message demandant de contacter le support Uber
- Message généré par: `generate_not_eligible_message()`

---

### 3.4 Exceptions au Niveau DATE EXAMEN (Step 2)

#### EXCEPTION D-CAS 1: Date examen vide
**Point de détection:** `analyze_exam_date_situation()`
**Condition:** `Date_examen_VTC = null`
**Solution implémentée:**
- Case: `1`
- Action: Proposer 2 prochaines dates du département
- Si pas de compte ExamT3P: Proposer aussi dates plus tôt d'autres départements
- Message: `generate_propose_dates_message()`

#### EXCEPTION D-CAS 2: Date passée + dossier non validé
**Point de détection:** `analyze_exam_date_situation()`
**Condition:**
- `Date_examen_VTC < aujourd'hui`
- `Evalbox ∉ {VALIDE CMA, Dossier Synchronisé}`
**Solution implémentée:**
- Case: `2`
- Action: Proposer 2 prochaines dates
- Message: `generate_propose_dates_past_message()`

#### EXCEPTION D-CAS 3: Refusé CMA
**Point de détection:** `analyze_exam_date_situation()`
**Condition:** `Evalbox = "Refusé CMA"`
**Solution implémentée:**
- Case: `3`
- Action:
  1. Informer du refus avec détails des pièces refusées (motif + solution)
  2. Indiquer repositionnement automatique sur prochaine date
  3. Donner la date limite de correction (clôture prochaine session)
- Message: `generate_refus_cma_message()`
- Données: `pieces_refusees_details` depuis ExamT3P

#### EXCEPTION D-CAS 4: VALIDE CMA + date future
**Point de détection:** `analyze_exam_date_situation()`
**Condition:**
- `Date_examen_VTC > aujourd'hui`
- `Evalbox = "VALIDE CMA"`
**Solution implémentée:**
- Case: `4`
- Sous-cas selon jours restants:
  - `> 10 jours`: Rassurer, convocation à venir
  - `7-10 jours`: Convocation devrait être arrivée, vérifier spams
  - `≤ 7 jours sans convocation`: Report automatique CMA, proposer prochaine date
- Message: `generate_valide_cma_message()`

#### EXCEPTION D-CAS 5: Dossier Synchronisé
**Point de détection:** `analyze_exam_date_situation()`
**Condition:**
- `Date_examen_VTC > aujourd'hui`
- `Evalbox = "Dossier Synchronisé"`
**Solution implémentée:**
- Case: `5`
- Action: Informer que CMA examine le dossier
- Avertissement: Surveiller emails, corriger si refus avant clôture
- Message: `generate_dossier_synchronise_message()`

#### EXCEPTION D-CAS 6: Date future + autre statut
**Point de détection:** `analyze_exam_date_situation()`
**Condition:**
- `Date_examen_VTC > aujourd'hui`
- `Date_Cloture > aujourd'hui`
- `Evalbox ∉ {VALIDE CMA, Dossier Synchronisé, Convoc reçue, Pret a payer}`
**Solution implémentée:**
- Case: `6`
- Flag: `should_include_in_response = False` (date déjà assignée)
- Action: Réponse normale, pas de proposition de dates

#### EXCEPTION D-CAS 7: Date passée + dossier validé
**Point de détection:** `analyze_exam_date_situation()`
**Condition:**
- `Date_examen_VTC < aujourd'hui`
- `Evalbox ∈ {VALIDE CMA, Dossier Synchronisé}`
**Solution implémentée:**
- Case: `7`
- Vérification: Indices dans threads que examen non passé
- Si indices → Demander clarification
- Sinon → Considérer examen passé
- Message: `generate_clarification_exam_message()`

#### EXCEPTION D-CAS 8: Deadline ratée
**Point de détection:** `analyze_exam_date_situation()`
**Condition:**
- `Date_examen_VTC > aujourd'hui`
- `Date_Cloture < aujourd'hui`
- `Evalbox ∉ {VALIDE CMA, Dossier Synchronisé}`
**Solution implémentée:**
- Case: `8`
- Action: Informer que deadline passée, report automatique
- Proposer prochaines dates
- Message: `generate_deadline_missed_message()`

#### EXCEPTION D-CAS 9: Convocation reçue
**Point de détection:** `analyze_exam_date_situation()`
**Condition:** `Evalbox = "Convoc CMA reçue"`
**Solution implémentée:**
- Case: `9`
- Action:
  1. Transmettre identifiants ExamT3P
  2. Lien vers plateforme
  3. Instructions: télécharger, imprimer convocation
  4. Rappel: pièce d'identité le jour J
  5. Souhaiter bonne chance
- Message: `generate_convocation_message()`

#### EXCEPTION D-CAS 10: Prêt à payer
**Point de détection:** `analyze_exam_date_situation()`
**Condition:** `Evalbox ∈ {"Pret a payer", "Pret a payer par cheque"}`
**Solution implémentée:**
- Case: `10`
- Action: Informer que paiement en cours
- Avertissement: Surveiller emails pour instruction CMA
- Message: `generate_pret_a_payer_message()`

---

### 3.5 Exceptions au Niveau INTENTION CANDIDAT (Triage → Response)

#### EXCEPTION I1: REPORT_DATE (Demande de changement de date)
**Point de détection:** `TriageAgent` → `intent_context`
**Solution implémentée:**
- Détection force majeure: médical, décès, accident
- Si force majeure → Procédure spéciale (justificatif requis)
- Si date antérieure demandée + pas de compte ExamT3P → Proposer dates autres départements

```python
# Dans triage_agent.py
intent_context = {
    'is_urgent': bool,
    'mentions_force_majeure': bool,
    'force_majeure_type': "medical" | "death" | "accident" | "other",
    'wants_earlier_date': bool
}
```

#### EXCEPTION I2: CONFIRMATION_SESSION
**Point de détection:** `TriageAgent` → `detected_intent`
**Solution implémentée:**
- Si date déjà assignée → Utiliser UNIQUEMENT cette date pour sessions
- Ne pas proposer d'alternatives
- Extraire le choix du candidat → Mise à jour CRM

```python
# Dans doc_ticket_workflow.py:1149-1153
if has_assigned_date and detected_intent == 'CONFIRMATION_SESSION':
    exam_dates_for_session = [date_examen_info]  # Pas d'alternatives
```

---

### 3.6 Exceptions au Niveau COHÉRENCE FORMATION/EXAMEN

#### EXCEPTION C1: Formation manquée + Examen imminent
**Point de détection:** `analyze_training_exam_consistency()`
**Condition:**
- Formation (Session) dans le passé ou manquée
- Examen dans < 14 jours
**Solution implémentée:**
- Proposer 2 options:
  - **Option A**: Maintenir examen (e-learning suffit)
  - **Option B**: Reporter (force majeure requise si dossier clôturé)

---

### 3.7 Règles de Blocage Critiques

#### RÈGLE B1: Modification Date_examen_VTC bloquée
**Condition:**
```
Evalbox ∈ {"VALIDE CMA", "Convoc CMA reçue"}
ET Date_Cloture_Inscription < aujourd'hui
```
**Raison:** Dossier validé + clôture passée = modification impossible sans force majeure
**Implémentation:** `can_modify_exam_date()` dans `examt3p_crm_sync.py`
**Solution:** Seule la force majeure avec justificatif permet le report (action manuelle)

```python
# Dans examt3p_crm_sync.py
def can_modify_exam_date(deal_data, exam_session_data):
    evalbox = deal_data.get('Evalbox', '')
    if evalbox in ['VALIDE CMA', 'Convoc CMA reçue']:
        date_cloture = exam_session_data.get('Date_Cloture_Inscription')
        if date_cloture and is_date_in_past(date_cloture):
            return False, "Dossier validé + clôture passée"
    return True, None
```

---

## 4. SYNCHRONISATION DES DONNÉES

### 4.1 ExamT3P → CRM (Source de Vérité)

**Fichier:** `src/utils/examt3p_crm_sync.py`

**Champs synchronisés automatiquement:**
| Champ CRM | Source ExamT3P | Notes |
|-----------|----------------|-------|
| Evalbox | statut_dossier | Mapping via `determine_evalbox_from_examt3p()` |
| IDENTIFIANT_EVALBOX | identifiant | Email du compte |
| MDP_EVALBOX | mot_de_passe | Mot de passe |
| NUM_DOSSIER_EVALBOX | num_dossier | Numéro CMA |
| Date_examen_VTC | date_examen | Via `find_exam_session_by_date_and_dept()` |

### 4.2 Extraction Identifiants (Fallback IA)

**Fichier:** `src/utils/examt3p_credentials_helper.py`

**Ordre de recherche:**
1. CRM (IDENTIFIANT_EVALBOX, MDP_EVALBOX)
2. Si vide → Extraction IA depuis threads (Claude Haiku)
3. Test de connexion ExamT3P
4. Si OK → Mise à jour CRM automatique

---

## 5. ALERTES TEMPORAIRES

**Fichier de config:** `alerts/active_alerts.yaml`

**Système:** Permet d'injecter des informations contextuelles dans les réponses IA sans modifier le code.

**Exemple:**
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

---

## 6. SCÉNARIOS DE RÉPONSE (26+)

**Fichier:** `knowledge_base/scenarios_mapping.py`

### Scénarios principaux:

| ID | Nom | Trigger | Action |
|----|-----|---------|--------|
| SC-00 | Nouveau candidat | Jamais inscrit | Proposer dates examen |
| SC-01 | Identifiants ExamT3P | Mot de passe oublié | Fournir + warning spam |
| SC-02 | Confirmation paiement | Payé, facture | Vérifier ExamT3P |
| SC-03 | Paiement en attente | Pas encore payé | Infos paiement |
| SC-04 | Document manquant | Pièce à fournir | Liste depuis ExamT3P |
| SC-05 | Document refusé | Pièce refusée | Motif + solution |
| SC-06 | Statut dossier | Où en est mon dossier | Status complet |
| SC-15a/b/c | Report | Reporter/décaler | Selon statut CMA |
| SC-17 | Confirmation session | Je choisis, option 1 | Update CRM |
| SC-20/21 | Résultat examen | Admis/échoué | Félicitations ou réinscription |
| SC-25 | Réclamation | Insatisfait | Ton apologétique |

### Termes interdits:
- `BFS`, `Evalbox`, `CDJ`, `CDS`, `20€`, `Montreuil`

### Blocs obligatoires:
- Identifiants: warning mot de passe + check spams
- E-learning: lien personnalisé

---

## 7. RÉSUMÉ: MATRICE EXCEPTION → SOLUTION

| # | Exception | Point Détection | Solution | Retour au Nominal |
|---|-----------|-----------------|----------|-------------------|
| T1 | Spam | Triage | Clôturer | N/A |
| T2 | Autre département | Triage | Transférer | Traité ailleurs |
| T3 | Doublon Uber | Deal Linking | Réponse spéciale | Inscription autonome |
| T4 | Candidat inconnu | Deal Linking | Clarification | Identification |
| A1 | Identifiants invalides | Credentials | Réponse credentials-only | Récupérer identifiants |
| A2 | ExamT3P down | ExamT3P Agent | Stop + alerte | Intervention manuelle |
| A3 | Double compte payé | Credentials | Alerte CRM | Intervention manuelle |
| U-A | Documents non envoyés | Uber Eligibility | Demander documents | Étape 2 du process |
| U-B | Test non passé | Uber Eligibility | Demander test | Étape 2 du process |
| U-D | Compte Uber NOK | Uber Eligibility | Contacter Uber | Vérification Uber |
| U-E | Non éligible | Uber Eligibility | Contacter Uber | Vérification Uber |
| D-1 | Date vide | Date Helper | Proposer dates | Étape 4 du process |
| D-2 | Date passée | Date Helper | Proposer dates | Étape 4 du process |
| D-3 | Refusé CMA | Date Helper | Corriger pièces | Revalidation CMA |
| D-4 | VALIDE CMA | Date Helper | Attendre convoc | Étape 8 du process |
| D-8 | Deadline ratée | Date Helper | Prochaine session | Report automatique |
| D-9 | Convoc reçue | Date Helper | Identifiants + instructions | Étape 9 du process |
| I1 | Report demandé | Triage Intent | Force majeure si bloqué | Nouvelle date |
| I2 | Confirmation session | Triage Intent | Update CRM | Étape 5 du process |
| C1 | Formation manquée | Consistency | Options A/B | Maintien ou report |
| B1 | Date bloquée | CRM Update | Refuser modif | Force majeure manuelle |

---

## 8. CONCLUSION

Ce système gère **40+ exceptions** pour ramener le candidat vers le processus nominal d'inscription VTC. Les principes clés sont:

1. **ExamT3P = Source de vérité** → Sync automatique vers CRM
2. **Détection contextuelle** → IA comprend le sens, pas les mots-clés
3. **Règles de blocage** → Protection contre les modifications impossibles
4. **Réponses spécialisées** → Chaque exception a sa solution documentée
5. **Alertes temporaires** → Flexibilité sans modification de code

Le but ultime: **Chaque candidat doit pouvoir avancer vers son examen VTC**, même si son parcours diverge du chemin nominal.
