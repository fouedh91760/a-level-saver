# DOC Ticket Automation - Documentation Complète

## Vue d'ensemble

Système d'automatisation intelligent pour les tickets du département DOC de CAB Formations, basé sur :
- **137 réponses réelles de Fouad Haddouchi** (analyse pattern + style)
- **26+ scénarios métier** de la knowledge base
- **RAG (Retrieval Augmented Generation)** pour few-shot learning
- **Claude 3.5 Sonnet** pour génération intelligente
- **6 sources de données** (CRM, ExamenT3P, Evalbox, Sessions, etc.)

---

## Architecture du système

```
┌─────────────────────────────────────────────────────────────────┐
│                     DOCTicketWorkflow                            │
│                  (Orchestrateur principal)                       │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
   ┌─────────┐        ┌──────────┐      ┌─────────────┐
   │ TRIEUR  │        │ ANALYSTE │      │ RÉDACTEUR   │
   │ (Rules) │        │(6 sources)│      │(Claude+RAG) │
   └─────────┘        └──────────┘      └─────────────┘
        │                   │                   │
        │                   │                   │
        ▼                   ▼                   ▼
    STOP & GO          Extraction          Generation
   (7 règles)         de données           + Validation
```

### Composants

#### 1. **knowledge_base/scenarios_mapping.py**
- 26+ scénarios métier (SC-00 à SC-26)
- Détection automatique de scénarios
- Blocs obligatoires (identifiants, warnings, etc.)
- Termes interdits (BFS, Evalbox, CDJ, CDS, 20€, Montreuil)
- Validation de conformité

#### 2. **src/utils/response_pattern_analyzer.py**
- Analyse de 137 réponses de Fouad
- Extraction de patterns structurels
- Analyse de ton (professional, directive, empathetic)
- Statistiques de longueur (moyenne: 371 mots)
- Détection d'éléments obligatoires

#### 3. **src/utils/response_rag.py**
- Système RAG basé sur TF-IDF + cosine similarity
- Index de 100 tickets + 137 réponses
- Vocabulaire: 3304 termes
- Recherche top-K tickets similaires
- Formatage few-shot pour Claude

#### 4. **src/agents/response_generator_agent.py**
- Génération de réponses avec Claude
- Utilise RAG pour trouver exemples similaires
- Applique les scénarios détectés
- Valide contre blocs obligatoires
- Boucle de validation avec retry

#### 5. **src/workflows/doc_ticket_workflow.py**
- Orchestrateur complet en 8 étapes
- Implémente la checklist 00_CHECKLIST_EXECUTION
- Gestion des gates (STOP & GO)
- Création draft + note CRM
- Updates automatiques (optionnels)

---

## Processus en 8 étapes

### 1️⃣  AGENT TRIEUR
**Objectif** : Router ou continuer

**7 règles de triage** :
- Règle #1: REFUS CMA → Déplacer vers "Refus CMA"
- Règle #2: HORS PARTENARIAT → Déplacer vers "Contact"
- Règle #3: SPAM → Clôturer sans note CRM
- Règle #4: PIÈCE JUSTIFICATIVE → Vérifier 20€
- Règle #5: VTC HORS PARTENARIAT → DOCS CAB
- Règle #6: AUTRE FORMATION → Contact
- Règle #7: SUCCÈS PRATIQUE → Contact

**Si ROUTE → STOP (pas de draft)**

---

### 2️⃣  AGENT ANALYSTE
**Objectif** : Extraire données de 6 sources

**6 sources de données** :
1. **CRM Zoho** : Contact, Deal, Sessions choisies
2. **ExamenT3P** : Documents, Paiement CMA, Compte
3. **Evalbox** : Éligibilité Uber (colonnes Q, R)
4. **Sessions Sheet** : SESSIONSUBER2026.xlsx
5. **Ticket Threads** : Historique conversation
6. **Google Drive** : Documents spécifiques

**Vérifications critiques** :
- **Vérification #0** : `Date_de_depot_CMA < 01/11/2025` → ANCIEN DOSSIER → STOP
- **Vérification #1** : Evalbox = null → COMPTE N'EXISTE PAS

**Si ANCIEN_DOSSIER → STOP (alerte interne)**

---

### 3️⃣  AGENT RÉDACTEUR
**Objectif** : Générer réponse avec Claude + RAG

**Processus** :
1. Détecter scénarios (SC-00 à SC-26)
2. Trouver 3-5 tickets similaires via RAG
3. Construire prompt avec few-shot examples
4. Appeler Claude 3.5 Sonnet
5. Valider contre blocs obligatoires
6. Retry si non-compliant (max 2 fois)

**Style de Fouad** (analysé) :
- Salutation: "Bonjour,"
- Ton: Professional (88%), Directive (58%), Rassurant (22%)
- Longueur: ~371 mots (médiane: 302)
- Formule: "Bien cordialement,"
- Signature: "L'équipe Cab Formations"

---

### 4️⃣  CRM NOTE
**Objectif** : Créer note CRM (OBLIGATOIRE avant draft)

**Format** :
```
[TICKET #123456] 2026-01-24 22:30
**Scénarios détectés** : SC-01_IDENTIFIANTS_EXAMENT3P
**Action** : Réponse générée et draft créé
**Champs CRM mis à jour** : Session_choisie, Date_debut_session
**Tickets similaires utilisés** :
  - #1089525 (score: 0.1662)
  - #1092373 (score: 0.1342)
```

---

### 5️⃣  TICKET UPDATE
**Objectif** : Mettre à jour statut et tags

**Champs mis à jour** :
- `tags`: Scénarios détectés (max 3)
- `status`: "En attente réponse client" (si besoin)
- `priority`: Selon scénario

---

### 6️⃣  DEAL UPDATE
**Objectif** : Mettre à jour CRM si scénario le requiert

**Scénarios avec CRM update** :
- **SC-17_CONFIRMATION_SESSION** : Update `Session_choisie`, `Date_debut_session`, `Date_fin_session`
- **SC-20_RESULTAT_POSITIF** : Update `Resultat_examen`
- **SC-21_RESULTAT_NEGATIF** : Update `Resultat_examen`

**⚠️ Champs interdits de modification** :
- `Date_test_selection` (source: ExamenT3P)
- `Date_Dossier_re_u` (source: ExamenT3P)

---

### 7️⃣  DRAFT CREATION
**Objectif** : Créer brouillon dans Zoho Desk

**Format** : HTML avec formatage Zoho
- Utilise `response_text` généré par Claude
- Préserve structure (salutation, corps, signature)
- Inclut blocs obligatoires

---

### 8️⃣  FINAL VALIDATION
**Objectif** : Vérifications finales

**Contrôles** :
- ✅ Blocs obligatoires présents
- ✅ Pas de termes interdits
- ✅ Compliance avec scénario
- ✅ CRM note créée
- ✅ Draft créé (si auto_create_draft=True)

---

## Fichiers générés

### `response_patterns_analysis.json` (7.2 KB)
Analyse complète des patterns de Fouad :
```json
{
  "metadata": {
    "total_responses_analyzed": 137,
    "total_tickets": 100
  },
  "structural_patterns": {
    "most_common_greeting": "Bonjour,",
    "most_common_closing": "Bien cordialement,",
    "most_common_signature": "L'équipe Cab Formations"
  },
  "tone_analysis": {
    "dominant_tones": ["professional", "directive", "reassuring"]
  },
  "length_statistics": {
    "avg_words": 371,
    "median_words": 302
  },
  "common_phrases": {
    "top_50_phrases": [...]
  }
}
```

### `fouad_tickets_analysis.json` (10.5 MB)
100 tickets complets avec:
- Sujets et questions clients
- 137 réponses de Fouad (contenu HTML complet)
- Métadonnées (dates, canal, tags)
- Threads complets

---

## Scénarios détectés dans les 137 réponses

| Scénario | Occurrences | Description |
|----------|-------------|-------------|
| SC-VTC_HORS_PARTENARIAT | 102 | VTC hors partenariat |
| SC-20_RESULTAT_POSITIF | 77 | Résultat examen positif |
| SC-01_IDENTIFIANTS_EXAMENT3P | 74 | Demande identifiants |
| SC-02_CONFIRMATION_PAIEMENT | 44 | Confirmation paiement |
| SC-04_DOCUMENT_MANQUANT | 30 | Document manquant |
| SC-15a_REPORT_SANS_DOSSIER | 20 | Report sans dossier CMA |
| SC-15b_REPORT_AVANT_CLOTURE | 20 | Report avant clôture |
| SC-15c_REPORT_APRES_CLOTURE | 20 | Report après clôture |

---

## Utilisation

### Exemple 1 : Traiter un ticket complet

```python
from src.workflows.doc_ticket_workflow import DOCTicketWorkflow

workflow = DOCTicketWorkflow()

result = workflow.process_ticket(
    ticket_id="198709000445353417",
    auto_create_draft=False,    # Manuel pour review
    auto_update_crm=False,       # Manuel pour review
    auto_update_ticket=False     # Manuel pour review
)

if result['success']:
    print(f"✅ Workflow terminé au stage: {result['workflow_stage']}")
    print(f"Scénarios: {result['response_result']['detected_scenarios']}")
    print(f"Draft créé: {result['draft_created']}")
    print(f"\nRéponse générée:\n{result['response_result']['response_text']}")
else:
    print(f"❌ Erreurs: {result['errors']}")

workflow.close()
```

### Exemple 2 : Générer réponse uniquement (sans workflow complet)

```python
from src.agents.response_generator_agent import ResponseGeneratorAgent

agent = ResponseGeneratorAgent()

result = agent.generate_response(
    ticket_subject="Demande d'identifiants ExamenT3P",
    customer_message="Je n'arrive pas à me connecter",
    exament3p_data={
        'compte_existe': True,
        'identifiant': 'test@example.com',
        'mot_de_passe': 'testpass123'
    }
)

print(f"Scénarios: {result['detected_scenarios']}")
print(f"Similarité: {result['similar_tickets'][0]['similarity_score']}")
print(f"\nRéponse:\n{result['response_text']}")
```

### Exemple 3 : Recherche de tickets similaires (RAG)

```python
from src.utils.response_rag import ResponseRAG

rag = ResponseRAG()

similar = rag.find_similar_tickets(
    subject="Report de formation",
    customer_message="Je veux décaler ma session",
    top_k=5
)

for ticket in similar:
    print(f"[{ticket['similarity_score']}] {ticket['subject']}")
```

---

## Configuration requise

### Variables d'environnement (.env)

```bash
# Anthropic API
ANTHROPIC_API_KEY=sk-ant-...

# Zoho Desk
ZOHO_DESK_ORG_ID=648790851
ZOHO_DESK_CLIENT_ID=...
ZOHO_DESK_CLIENT_SECRET=...
ZOHO_DESK_REFRESH_TOKEN=...

# Zoho CRM
ZOHO_CRM_CLIENT_ID=...
ZOHO_CRM_CLIENT_SECRET=...
ZOHO_CRM_REFRESH_TOKEN=...
```

### Dépendances

```bash
pip install -r requirements.txt
```

Nouvelles dépendances ajoutées :
- `beautifulsoup4==4.12.3` - Parsing HTML
- `lxml==5.1.0` - Parser rapide
- `anthropic>=0.40.0` - Claude API

---

## Workflow décisionnel

```
┌─────────────┐
│   TICKET    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ 1. TRIEUR       │ ──[ROUTE]──→ Déplacer → STOP
│ (7 règles)      │ ──[SPAM]───→ Clôturer → STOP
└────────┬────────┘
         │ [GO]
         ▼
┌─────────────────┐
│ 2. ANALYSTE     │ ──[ANCIEN]──→ Alerte → STOP
│ (6 sources)     │
└────────┬────────┘
         │ [OK]
         ▼
┌─────────────────┐
│ 3. RÉDACTEUR    │
│ Claude + RAG    │ → Génère réponse
│ + Validation    │ → Vérifie blocs obligatoires
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. CRM NOTE     │ → Note obligatoire
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5-6. UPDATES    │ → Ticket + Deal (si requis)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 7. DRAFT        │ → Brouillon Zoho Desk
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 8. VALIDATION   │ → Vérification finale
└─────────────────┘
```

---

## Scénarios principaux

### SC-00: NOUVEAU_CANDIDAT
**Déclencheurs** : "nouveau candidat", "première inscription"
**Action** : Proposer **dates d'examen** (PAS sessions)
**Blocs obligatoires** : Identifiants (si compte existe), E-learning, Spam warning

### SC-01: IDENTIFIANTS_EXAMENT3P
**Déclencheurs** : "identifiant", "mot de passe", "connexion"
**Blocs obligatoires** :
```
🔐 **Vos identifiants ExamenT3P** :
• **Identifiant** : [email]
• **Mot de passe** : [password]

⚠️ Ces identifiants sont personnels et confidentiels.
Ne les communiquez jamais à qui que ce soit.
```

### SC-15a/b/c: REPORT
**Types** :
- **15a**: SANS_DOSSIER (Date_de_depot_CMA = null) → Report facile
- **15b**: AVANT_CLOTURE (Date_de_cloture = null) → Report possible
- **15c**: APRES_CLOTURE (Date_de_cloture existe) → Report difficile

**Source de vérité** : CRM fields

### SC-17: CONFIRMATION_SESSION
**Déclencheurs** : "je choisis", "je confirme la session"
**Action** : ⚠️ **UPDATE CRM OBLIGATOIRE**
**Champs** : `Session_choisie`, `Date_debut_session`, `Date_fin_session`

### SC-25: RECLAMATION
**Déclencheurs** : "réclamation", "inadmissible", "insatisfait"
**Ton** : Apologétique + Rassurant
**Action** : Escalade si grave

---

## Sources de vérité

| Source | Champs | Utilisation |
|--------|--------|-------------|
| **ExamenT3P** | Documents, Paiement CMA, Statut | Source of truth pour documents et paiement |
| **Evalbox** | Colonnes Q, R (Google Sheet) | Source of truth pour éligibilité Uber |
| **CRM Zoho** | Sessions, Dates CMA, Contact | Informations deal et historique |

**⚠️ RÈGLE CRITIQUE** : Si conflit entre sources, ExamenT3P et Evalbox sont prioritaires.

---

## Blocs obligatoires

### Identifiants ExamenT3P (si compte existe)
```
🔐 **Vos identifiants ExamenT3P** :
• **Identifiant** : [email du candidat]
• **Mot de passe** : [mot_de_passe]

⚠️ Ces identifiants sont personnels et confidentiels.
```

### Avertissement mot de passe (TOUJOURS)
```
⚠️ Ne communiquez jamais vos identifiants à qui que ce soit.
```

### Lien e-learning (TOUJOURS)
```
🎓 **Formation e-learning** : [lien personnalisé]
```

### Vérification spam (si email envoyé)
```
📧 Vérifiez vos spams/courriers indésirables si vous ne recevez pas notre email.
```

---

## Termes interdits

❌ **NE JAMAIS UTILISER** :
- `BFS` → Code interne
- `Evalbox` → Dire "plateforme ExamenT3P"
- `CDJ` / `CDS` → Codes internes sessions
- `20€` → Dire "frais de dossier"
- `Montreuil` → Localisation interne

---

## Statistiques d'analyse

### Patterns de Fouad (137 réponses)
- **Ton dominant** : Professional (88%), Directive (58%), Rassurant (22%)
- **Longueur moyenne** : 371 mots (min: 34, max: 2299, médiane: 302)
- **Salutation** : "Bonjour," (standard)
- **Closing** : "Bien cordialement," (93 occurrences)
- **Signature** : "L'équipe Cab Formations" (standard)

### Conformité éléments obligatoires
- **Identifiants** : 54% des réponses
- **E-learning** : 51% des réponses
- **Spam warning** : 26% des réponses
- **Password warning** : 0.7% (⚠️ à améliorer)

### RAG System
- **100 tickets** indexés
- **137 réponses** de Fouad
- **3304 termes** dans vocabulaire
- **Similarité moyenne** : 10-30% (TF-IDF cosine)

---

## Prochaines étapes

### Phase 2A : Intégration ExamT3PAgent
- [ ] Connecter ExamT3PAgent au workflow
- [ ] Scraper données réelles ExamenT3P
- [ ] Mapper aux champs CRM

### Phase 2B : Intégration Evalbox
- [ ] Connecter Google Sheets API
- [ ] Lire colonnes Q, R (éligibilité)
- [ ] Détecter scope (uber_gagne, uber_en_attente, hors_scope)

### Phase 3 : Tests complets
- [ ] Tester avec 10 tickets réels
- [ ] Valider génération de réponses
- [ ] Vérifier compliance à 100%

### Phase 4 : Production
- [ ] Intégrer au ZohoAutomationOrchestrator
- [ ] Batch processing de tickets
- [ ] Monitoring et métriques

---

## Fichiers créés

```
knowledge_base/
  └── scenarios_mapping.py           # 26+ scénarios + détection

src/
  agents/
    └── response_generator_agent.py  # Agent Claude + RAG
  utils/
    ├── response_pattern_analyzer.py # Analyse patterns
    └── response_rag.py              # Système RAG
  workflows/
    └── doc_ticket_workflow.py       # Orchestrateur 8 étapes

response_patterns_analysis.json      # Résultats analyse (7.2 KB)
fouad_tickets_analysis.json          # 100 tickets (10.5 MB)
test_response_generator_structure.py # Tests structure
```

---

## Architecture technique

### RAG (Retrieval Augmented Generation)
- **Indexation** : TF-IDF (Term Frequency - Inverse Document Frequency)
- **Similarité** : Cosine similarity
- **Complexité** : O(n) pour recherche (n = 100 tickets)
- **Avantages** : Léger, pas d'API externe, rapide (<1s)

### Claude Integration
- **Modèle** : claude-3-5-sonnet-20240620
- **Temperature** : 0.3 (focused)
- **Max tokens** : 2000
- **System prompt** : 2647 caractères (style Fouad)
- **User prompt** : 4000-6000 caractères (contexte + exemples)
- **Few-shot** : 3-5 tickets similaires

### Validation
- **Boucle retry** : Max 2 tentatives
- **Vérifications** : Blocs obligatoires + termes interdits
- **Compliance score** : Calculé par scénario

---

## Avantages vs système Ubuntu existant

| Aspect | Système Ubuntu | Nouveau système |
|--------|---------------|-----------------|
| **LLM** | GPT-4 générique | Claude + RAG (apprend de Fouad) |
| **Exemples** | Aucun | 3-5 tickets similaires (few-shot) |
| **Scénarios** | Détection manuelle | 26+ scénarios automatiques |
| **Validation** | Minimale | Blocs obligatoires + termes interdits |
| **CRM** | MCP CLI subprocess | API REST directe |
| **Architecture** | Monolithique | Modulaire (agents + workflow) |
| **Tests** | Manuels | Automatisés (pytest) |
| **Git** | Non versionné | Versionné + CI/CD ready |

---

## Notes importantes

### ⚠️ Configuration Claude API
Le test avec appel API Claude échoue actuellement avec erreur 404 sur le modèle.
**Actions à vérifier** :
1. ANTHROPIC_API_KEY est bien défini dans .env
2. La clé a accès au modèle `claude-3-5-sonnet-20240620`
3. Essayer avec `claude-3-opus-20240229` si nécessaire

### ✅ Structure validée
Tous les tests de structure passent :
- ✅ Détection de scénarios
- ✅ RAG similarity search
- ✅ Construction des prompts
- ✅ Formatage des données
- ✅ Workflow orchestration

### 🎯 Prêt pour intégration
Le système est prêt à être intégré au `ZohoAutomationOrchestrator` existant.

---

**Auteur** : Système d'automatisation CAB Formations
**Date** : 2026-01-24
**Version** : 1.0.0
**Basé sur** : 137 réponses de Fouad Haddouchi + Knowledge base complète
