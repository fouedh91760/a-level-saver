# Gestion Avancée des Doublons BFS

## Vue d'ensemble

Ce document décrit le système de détection et gestion des doublons pour les candidats BFS (offre Uber 20€). Le système permet d'identifier les candidats qui tentent de se réinscrire et de gérer intelligemment la reprise de leur dossier existant.

---

## Problématique

Un candidat peut se réinscrire avec :
- Le **même email** → Doublon facilement détectable
- Un **email différent** mais même nom/prénom/code postal → Homonyme ou même personne ?

### Cas d'usage

| Scénario | Email | Téléphone | Nom+CP | Action |
|----------|-------|-----------|--------|--------|
| Même personne, même email | ✅ Match | - | - | Doublon confirmé |
| Même personne, nouvel email | ❌ Différent | ❌ Différent | ✅ Match | **Clarification requise** |
| Homonyme | ❌ Différent | ❌ Différent | ✅ Match | **Clarification requise** |

---

## Architecture de la Solution

### ⚠️ RÈGLE CRITIQUE : Demandes Non-Uber

**AVANT** d'appliquer la logique doublon, le système vérifie si la demande est liée à une formation **non-Uber**.

| Type de demande | Keywords détectés | Action |
|-----------------|-------------------|--------|
| CPF | cpf, compte cpf, compte formation, moncompteformation | → Contact |
| France Travail | france travail, kairos, pole emploi, conseiller | → Contact |
| Financement personnel | 720€, tarif complet, payer moi-même | → Contact |
| Devis | devis, facture pro forma | → Contact |
| Autres financements | opco, fafcea, agefice, fifpl, fif pl | → Contact |

**Si une demande non-Uber est détectée** (même si le candidat a un dossier Uber existant), le ticket est **routé vers Contact** pour traitement manuel. La logique doublon Uber n'est **PAS appliquée**.

```
Ticket → Détection keywords non-Uber →
   ├── OUI (CPF/France Travail/etc.) → ROUTE vers Contact (ignorer doublon)
   └── NON → Continuer avec logique doublon Uber (voir ci-dessous)
```

### Flux Global (Demandes Uber uniquement)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ÉTAPE 1 : DÉTECTION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Ticket arrive → DealLinkingAgent analyse                                  │
│                                                                             │
│   1. Recherche par EMAIL (prioritaire)                                      │
│      └── Si match → Doublon HIGH_CONFIDENCE                                 │
│                                                                             │
│   2. Si pas de match email → Recherche par NOM + CODE POSTAL                │
│      ├── Si match + même email OU même téléphone → HIGH_CONFIDENCE          │
│      └── Si match + email ET téléphone différents → NEEDS_CONFIRMATION      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ÉTAPE 2 : CLARIFICATION (si nécessaire)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Action = DUPLICATE_CLARIFICATION                                          │
│                                                                             │
│   1. Générer brouillon adapté à l'intention du candidat                     │
│      - STATUT_DOSSIER → "Pour vérifier l'état de votre dossier..."         │
│      - DEMANDE_REINSCRIPTION → "Pour reprendre votre inscription..."        │
│      - DEMANDE_IDENTIFIANTS → "Pour vous transmettre vos identifiants..."   │
│                                                                             │
│   2. Créer note interne avec marker et données de vérification              │
│      [DUPLICATE_PENDING:deal_id]                                            │
│      + Email doublon + Téléphone doublon + Intention originale              │
│                                                                             │
│   3. cf_opportunite reste INCHANGÉ (lié au nouveau deal)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
                    ┌───────────────────────────────┐
                    │   Candidat répond au ticket   │
                    │   avec son email ou téléphone │
                    └───────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ÉTAPE 3 : VÉRIFICATION AUTOMATIQUE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. Détecter la note [DUPLICATE_PENDING:deal_id]                           │
│   2. Extraire email/téléphone du message candidat (regex)                   │
│   3. Comparer avec valeurs stockées dans la note                            │
│                                                                             │
│   Normalisation téléphone :                                                 │
│   - "06 95 36 90 68" → "0695369068"                                        │
│   - "+33 6 95 36 90 68" → "0695369068"                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
           ┌────────────────────────┴────────────────────────┐
           │                                                  │
    ✅ MATCH                                          ❌ NO MATCH
    (email OU téléphone)                              (rien ne correspond)
           │                                                  │
           ↓                                                  ↓
┌─────────────────────────────────┐          ┌─────────────────────────────┐
│  ÉTAPE 4A : CONFIRMATION        │          │  ÉTAPE 4B : NOUVEAU DOSSIER │
├─────────────────────────────────┤          ├─────────────────────────────┤
│                                 │          │                             │
│  • cf_opportunite → deal doublon│          │  • cf_opportunite = INCHANGÉ│
│  • Action = DUPLICATE_RECOVERABLE│         │  • Action = GO              │
│  • Intention originale restaurée│          │  • Traitement normal        │
│  • Note: [DUPLICATE_RESOLVED:   │          │  • Note: [DUPLICATE_        │
│          VERIFIED]              │          │          VERIFICATION_FAILED]│
│                                 │          │                             │
└─────────────────────────────────┘          └─────────────────────────────┘
```

---

## Classification des Doublons

### Types de Doublons Récupérables

| Type | Evalbox | Signification | Action possible |
|------|---------|---------------|-----------------|
| `RECOVERABLE_REFUS_CMA` | Refusé CMA | CMA a refusé le dossier | Réinscription avec même offre 20€ |
| `RECOVERABLE_NOT_PAID` | Dossier créé, Pret a payer | Inscription non finalisée | Reprise du dossier existant |
| `RECOVERABLE_PAID` | Dossier Synchronisé | Payé, en attente validation | Reprise sans repayer |

### Types de Doublons Non-Récupérables

| Type | Evalbox | Signification | Action |
|------|---------|---------------|--------|
| `TRUE_DUPLICATE` | VALIDE CMA, Convoc CMA | Candidat déjà validé | Offre 20€ épuisée |

---

## Implémentation Technique

### Fichiers Impliqués

| Fichier | Rôle |
|---------|------|
| `src/agents/deal_linking_agent.py` | Détection doublon par nom+CP, classification |
| `src/workflows/doc_ticket_workflow.py` | Orchestration, vérification, mise à jour CRM |
| `src/zoho_client.py` | API Zoho (get_ticket_comments, add_ticket_comment) |
| `states/templates/partials/uber/doublon_clarification.html` | Template message clarification |

### Méthodes Clés

#### 1. Détection du doublon (`deal_linking_agent.py`)

```python
def _search_duplicate_by_name_and_postal(self, name, postal_code, current_email, current_phone):
    """
    Recherche les deals avec même nom + code postal.

    Returns:
        {
            'duplicates': List[Deal],
            'confidence': 'HIGH_CONFIDENCE' | 'NEEDS_CONFIRMATION',
            'match_details': {...}
        }
    """
```

**Logique de confiance :**
- `HIGH_CONFIDENCE` : Nom+CP match ET (email match OU téléphone match)
- `NEEDS_CONFIRMATION` : Nom+CP match MAIS email ET téléphone différents

#### 2. Vérification des credentials (`doc_ticket_workflow.py`)

```python
def _verify_duplicate_clarification_response(self, ticket_id, pending_clarification, latest_message):
    """
    Vérifie si l'email/téléphone fourni par le candidat correspond au doublon.

    Returns:
        {
            'verified': bool,
            'match_type': 'email' | 'phone' | 'both' | 'none',
            'extracted_email': str | None,
            'extracted_phone': str | None,
            'reason': str
        }
    """
```

**Patterns d'extraction :**
```python
# Email
email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Téléphone français
phone_pattern = r'(?:(?:\+33|0033|33)|0)[67][\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}'
```

#### 3. Détection clarification en attente (`doc_ticket_workflow.py`)

```python
def _check_pending_duplicate_clarification(self, ticket_id):
    """
    Vérifie si une clarification doublon est en attente via les notes internes.

    Cherche le marker [DUPLICATE_PENDING:deal_id] dans les commentaires privés.

    Returns:
        {
            'pending_deal_id': str,
            'duplicate_type': str,
            'duplicate_email': str,
            'duplicate_phone': str,
            'original_intent': str,
            'comment_id': str
        } | None
    """
```

---

## Format des Notes Internes

### Note de Clarification en Attente

```
⚠️ DOUBLON POTENTIEL DÉTECTÉ - EN ATTENTE CLARIFICATION

Dossier doublon trouvé par NOM + CODE POSTAL (email/téléphone différents)
• Deal ID: 1456177001270922601
• Deal Name: BFS NP Jean Dupont
• Type: RECOVERABLE_REFUS_CMA
• Email doublon: ancien@email.com
• Téléphone doublon: 0612345678
• Intention originale: STATUT_DOSSIER

ACTION REQUISE: Attendre réponse candidat pour confirmer s'il s'agit bien du même dossier.
[DUPLICATE_PENDING:1456177001270922601]
```

### Note de Résolution - Vérifié

```
✅ CLARIFICATION DOUBLON RÉSOLUE - IDENTITÉ VÉRIFIÉE

Le candidat a fourni des informations qui CORRESPONDENT au dossier doublon.
→ Méthode de vérification: email
→ Email correspond
→ Email fourni: ancien@email.com
→ Téléphone fourni: N/A
→ Deal ID confirmé: 1456177001270922601
→ cf_opportunite mis à jour vers ce deal
→ Intention originale restaurée: STATUT_DOSSIER

[DUPLICATE_RESOLVED:VERIFIED]
```

### Note de Résolution - Échec

```
⚠️ CLARIFICATION DOUBLON - VÉRIFICATION ÉCHOUÉE

Le candidat a répondu mais les informations NE CORRESPONDENT PAS.
→ Email fourni: autre@email.com
→ Téléphone fourni: Aucun
→ Raison: Email/téléphone ne correspondent pas au dossier doublon

ACTION: Traitement comme nouveau dossier (homonyme probable)

[DUPLICATE_VERIFICATION_FAILED]
```

---

## Messages de Clarification Adaptés

Le message de clarification s'adapte à l'intention originale du candidat :

| Intention | Introduction du message |
|-----------|------------------------|
| `STATUT_DOSSIER` | "Pour vérifier l'état de votre dossier..." |
| `DEMANDE_REINSCRIPTION` | "Bonne nouvelle ! Pour reprendre votre inscription..." |
| `DEMANDE_IDENTIFIANTS` | "Pour vous transmettre vos identifiants en toute sécurité..." |
| `DEMANDE_DATES_FUTURES` | "Avant de vous communiquer les dates disponibles..." |
| `DEMANDE_ELEARNING_ACCESS` | "Pour vous donner accès à votre formation..." |
| Autre | "Afin de nous assurer qu'il s'agit bien de vous..." |

---

## Gestion de cf_opportunite

| Étape | État de cf_opportunite |
|-------|------------------------|
| Ticket arrive | Peut être lié au nouveau deal (par Zoho) ou vide |
| Clarification envoyée | **INCHANGÉ** |
| Vérification réussie | → **Mis à jour vers le deal doublon** |
| Vérification échouée | **INCHANGÉ** (reste sur nouveau deal) |

---

## Cas Particuliers

### 1. Deux deals GAGNÉ pour le même contact

Si un candidat a 2 deals à 20€ GAGNÉ, on sélectionne celui avec un compte ExamT3P :

```python
def _select_deal_for_duplicate_recovery(self, current_deal, duplicate_deal):
    """
    Sélectionne le deal à utiliser quand 2 deals GAGNÉ existent.

    Priorité : Deal avec compte ExamT3P (Evalbox = Synchronisé ou Refusé CMA)
    """
```

Le deal non sélectionné a son champ `EXAM_INCLUS` mis à `Non`.

### 2. Frais CMA déjà payés

Si le doublon a `Evalbox = Dossier Synchronisé` ou `VALIDE CMA`, les frais CMA ont déjà été payés. Une alerte est ajoutée pour éviter un double paiement.

### 3. Candidat ne fournit pas d'email/téléphone

Si le candidat répond sans fournir d'email ou téléphone vérifiable, le système considère que la vérification a échoué et traite comme un nouveau dossier.

---

## Tests

### Tester la détection

```python
from src.workflows.doc_ticket_workflow import DOCTicketWorkflow

workflow = DOCTicketWorkflow()
result = workflow.process_ticket('TICKET_ID', auto_create_draft=False)

print(result.get('workflow_stage'))  # DUPLICATE_CLARIFICATION si doublon détecté
print(result.get('triage_result', {}).get('duplicate_contact_info'))
```

### Tester la vérification

```python
pending = {
    'pending_deal_id': '123456',
    'duplicate_email': 'test@email.com',
    'duplicate_phone': '0612345678'
}

verification = workflow._verify_duplicate_clarification_response(
    ticket_id='test',
    pending_clarification=pending,
    latest_message='Mon email était test@email.com'
)

print(verification['verified'])  # True
print(verification['match_type'])  # 'email'
```

---

## Évolutions Futures

- [ ] Support des numéros de téléphone internationaux
- [ ] Détection de similarité phonétique pour les noms (Levenshtein)
- [ ] Interface admin pour résolution manuelle des cas ambigus
- [ ] Historique des vérifications dans le CRM
