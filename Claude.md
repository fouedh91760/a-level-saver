# Claude.md - A-Level Saver Project Context

---

## ⚠️ INSTRUCTIONS GIT CRITIQUES - LIRE EN PREMIER

### 🔄 Synchronisation au début de chaque session

**AVANT de commencer à travailler, TOUJOURS synchroniser avec GitHub :**

```bash
# 1. Récupérer les dernières modifications de toutes les branches
git fetch origin

# 2. Voir l'état actuel
git status
git branch -a

# 3. Si tu es sur main, merger les changements des branches claude/*
git checkout main
git merge origin/main

# 4. Vérifier s'il y a des branches claude/* avec des commits en avance
git log origin/claude/[nom-branche] --oneline -5
```

### 📤 Workflow pour pousser les modifications

**Claude pousse sur une branche `claude/*`, l'utilisateur merge sur main :**

```bash
# Claude fait ses modifications et pousse sur sa branche
git add .
git commit -m "Description du changement"
git push origin main:claude/[session-branch]

# L'utilisateur récupère et merge sur main
git fetch origin
git merge origin/claude/[session-branch]
git push origin main
```

### 🚨 ERREURS À ÉVITER

| ❌ Ne pas faire | ✅ Faire à la place |
|-----------------|---------------------|
| `git reset --hard origin/main` sans vérifier les branches | Vérifier d'abord `git log origin/claude/* --oneline -10` |
| Travailler sur une branche sans fetch | Toujours `git fetch origin` en premier |
| Ignorer les branches `claude/*` avec commits en avance | Merger ces branches avant de reset |

### 📋 Checklist de début de session

- [ ] `git fetch origin` - Récupérer les dernières modifications
- [ ] `git status` - Voir l'état actuel
- [ ] `git branch -a` - Voir toutes les branches
- [ ] Vérifier si des branches `claude/*` ont des commits non mergés
- [ ] Si oui, merger ces branches dans main avant de continuer

---

## 📝 CHANGELOG - ÉVOLUTIONS RÉCENTES (Janvier 2026)

### 25-26 Janvier 2026 - Corrections majeures

#### 🔧 Règles métier corrigées

1. **Justificatif de domicile : 3 mois (pas 6)**
   - Fichier: `src/agents/response_generator_agent.py`
   - La CMA exige un justificatif de moins de **3 mois**, pas 6

2. **Dates de formation : utiliser les données CRM**
   - Ne jamais inventer les dates de formation
   - Utiliser `Session_choisie` du CRM

3. **Identifiants E-learning ≠ ExamT3P**
   - ExamT3P : donner identifiants + lien
   - E-learning : donner **UNIQUEMENT le lien** (candidat a déjà ses identifiants)

#### 🔗 Liens officiels ajoutés

| Plateforme | URL | Texte cliquable |
|------------|-----|-----------------|
| ExamenT3P | https://www.exament3p.fr | [Mon espace ExamenT3P] |
| E-learning | https://cab-formations.fr/user | [Mon E-LEARNING] |
| Test sélection | https://cab-formations.fr/user/login?destination=/course/test-de-s%C3%A9lection | [Test de sélection] |
| Inscription Uber | https://cab-formations.fr/uberxcab_welcome | [Plateforme inscription offre Cab Uber] |

#### 💬 Communication diplomatique

- Ne pas dire "erreur de notre part" ou "manque de communication de notre côté"
- Dire : "Il est probable que cet email se soit retrouvé dans vos spams"
- Ajouter : "N'hésitez pas à nous alerter dès que vous constatez un manque d'information"

#### 🛑 Règle de blocage modifiée

- **Avant** : Bloquer les anciens dossiers (avant 01/11/2025)
- **Maintenant** : Bloquer **uniquement si échec connexion ExamT3P**

#### 📄 Détection statut "À CORRIGER"

- Fichier: `src/utils/exament3p_playwright.py`
- Le statut "À CORRIGER" est maintenant détecté et traité comme "REFUSÉ"

---

## 🎯 CONTEXTE DU PROJET

**Nom:** A-Level Saver - Automatisation Zoho Desk & CRM
**Client:** CAB Formations (France)
**Domaine:** Service de sélection de matières A-Level (éducation)
**Type:** Système d'automatisation intelligent piloté par IA
**Langage:** Python 3.9+
**IA:** Claude 3.5 Sonnet (Anthropic)

### Mission Principale
Automatiser le traitement des tickets de support Zoho Desk en utilisant Claude AI pour :
- Analyser et répondre automatiquement aux tickets clients
- Router vers le bon département (DOC, Sales, Support, etc.)
- Lier automatiquement les tickets aux opportunités CRM
- Mettre à jour les deals/opportunités selon le contexte
- Générer des réponses contextuelles et empathiques

---

## 📊 STATISTIQUES CLÉS

| Métrique | Valeur |
|----------|--------|
| **Code Python** | ~16,500+ lignes |
| **Agents IA** | 7 agents spécialisés |
| **Documentation** | 17 fichiers Markdown (~180 KB) |
| **Scénarios métier** | 26+ mappés |
| **Modèle IA** | claude-sonnet-4-5-20250929 ⭐ |
| **Base de connaissances** | 100+ tickets + 137 réponses de Fouad |
| **Dépendances** | 23 packages Python |

---

## 🏗️ ARCHITECTURE DU PROJET

```
a-level-saver/
├── src/
│   ├── agents/              # 7 agents IA spécialisés
│   │   ├── base_agent.py           # Classe abstraite commune
│   │   ├── desk_agent.py           # Analyse & réponse tickets
│   │   ├── crm_agent.py            # Gestion opportunités CRM
│   │   ├── dispatcher_agent.py     # Routage département
│   │   ├── deal_linking_agent.py   # Liaison ticket-deal
│   │   ├── response_generator_agent.py  # Génération réponses RAG
│   │   └── examt3p_agent.py        # Scraping ExamenT3P
│   ├── utils/               # Modules utilitaires
│   │   ├── logging_config.py       # Configuration logs
│   │   ├── text_utils.py           # Traitement texte
│   │   ├── response_rag.py         # Système RAG (TF-IDF)
│   │   └── response_pattern_analyzer.py  # Analyse patterns
│   ├── workflows/           # Workflows orchestrés
│   │   └── doc_ticket_workflow.py  # Workflow DOC 8 étapes
│   ├── zoho_client.py       # Client API Zoho (Desk + CRM)
│   ├── orchestrator.py      # Chef d'orchestre principal
│   └── ticket_deal_linker.py  # Système de liaison intelligent
├── knowledge_base/          # Règles métier
│   └── scenarios_mapping.py      # 26+ scénarios définis
├── examples/                # 11 scripts d'exemple
├── config.py               # Configuration Pydantic
├── main.py                 # CLI interface
├── webhook_server.py       # Serveur Flask webhooks
├── business_rules.py       # Règles métier personnalisées
└── requirements.txt        # Dépendances Python
```

---

## 🤖 LES 7 AGENTS IA

### 1. **DeskTicketAgent** (`desk_agent.py`)
**Rôle:** Analyse et génère des réponses pour tickets support

**Processus:**
1. Récupère contexte complet (ticket + threads + conversations + historique)
2. Envoie à Claude avec prompt système personnalisé
3. Analyse et génère réponse empathique et professionnelle
4. Détermine priorité, statut, escalade nécessaire
5. Optionnellement poste la réponse et met à jour le statut

**Sortie JSON:**
```json
{
  "analysis": "Analyse du ticket...",
  "suggested_response": "Réponse suggérée...",
  "priority": "High",
  "status": "In Progress",
  "escalate": false,
  "internal_notes": "Notes internes..."
}
```

---

### 2. **CRMOpportunityAgent** (`crm_agent.py`)
**Rôle:** Gère et met à jour les opportunités CRM

**Capacités:**
- Analyse état actuel de l'opportunité
- Recommande stage suivant
- Calcule probabilité de succès
- Suggère prochaines actions
- Score de priorité (1-10)
- Champs CRM à mettre à jour

---

### 3. **TicketDispatcherAgent** (`dispatcher_agent.py`)
**Rôle:** Route les tickets vers le bon département

**Départements:**
- **DOC** → Services éducatifs, programmes A-Level, deals Uber 20€
- **Sales** → Nouvelles demandes, prix, démos
- **Support** → Problèmes techniques
- **Billing** → Paiements, factures, remboursements
- **Customer Success** → Renouvellements, upgrades

**Logique:**
- Intégration règles métier
- Scoring de confiance
- Détection mots-clés
- Réaffectation automatique

---

### 4. **DealLinkingAgent** (`deal_linking_agent.py`)
**Rôle:** Lie automatiquement tickets aux deals CRM

**Stratégies (ordre):**
1. Vérification champ custom (cf_deal_id)
2. Règles métier spécifiques département
3. Recherche par email contact
4. Recherche par téléphone contact
5. Recherche par compte/organisation
6. Fallback sur deal plus récent

**Sortie:**
- Deal ID avec score de confiance
- Suggestions alternatives
- Recommandation création nouveau deal

---

### 5. **ResponseGeneratorAgent** (`response_generator_agent.py`)
**Rôle:** Génère réponses contextuelles avec RAG

**Fonctionnalités avancées:**
- **Système RAG** → Récupère réponses similaires passées (few-shot learning)
- **Analyse patterns** → Apprend de 137 vraies réponses de Fouad
- **Détection scénario** → Map vers 26+ scénarios métier
- **Validation** → Vérifie blocs obligatoires et termes interdits
- **Boucle retry** → Corrige automatiquement réponses non-conformes

**Base de données RAG:**
- 100 tickets analysés
- 137 réponses de Fouad
- 3,304 termes (vocabulaire TF-IDF)
- Similarité cosinus pour top-K retrieval

---

### 6. **ExamT3PAgent** (`examt3p_agent.py`)
**Rôle:** Scraping plateforme ExamenT3P

**Capacités:**
- Automation navigateur Playwright
- Extraction documents
- Vérification statut paiements
- Récupération infos compte
- Extraction données session

---

### 7. **BaseAgent** (`base_agent.py`)
**Classe abstraite pour tous les agents**

**Fonctionnalités communes:**
- Initialisation client Anthropic
- Gestion historique conversation
- Construction messages avec contexte
- Parsing réponses JSON
- Gestion erreurs et logging

---

## 🔄 ORCHESTRATEUR PRINCIPAL

**Fichier:** `src/orchestrator.py`
**Classe:** `ZohoAutomationOrchestrator`

### Workflow Principal: `process_ticket_complete_workflow()`

**4 étapes coordonnées:**

1. **Deal Linking**
   - Trouve le deal lié (détermine département)
   - Multi-stratégie avec fallback
   - Score de confiance

2. **Department Routing**
   - Valide/corrige département
   - Applique règles métier
   - Auto-réaffectation optionnelle

3. **Ticket Processing**
   - Analyse complète contexte
   - Génération réponse IA
   - Validation format
   - Auto-post optionnel

4. **CRM Updates**
   - Mise à jour deal si lié
   - Ajout notes CRM
   - Synchronisation bidirectionnelle

**Configuration Progressive:**
```python
auto_dispatch=True,      # Active routage auto
auto_link=True,         # Active liaison auto
auto_respond=False,     # ⚠️ Envoi réponses
auto_update_ticket=False,  # ⚠️ MAJ statut ticket
auto_update_deal=False,    # ⚠️ MAJ CRM
auto_add_note=False        # ⚠️ Ajout notes CRM
```

---

## 🔌 INTÉGRATIONS API

### Zoho Desk API

**Client:** `ZohoDeskClient` dans `src/zoho_client.py`
**Auth:** OAuth2 avec refresh automatique
**Base URL:** `https://desk.zoho.{datacenter}/api/v1`

**Méthodes principales:**
```python
get_ticket(ticket_id)                    # Récupère 1 ticket
list_all_tickets(status, limit)          # Liste avec pagination
update_ticket(ticket_id, data)           # Modifie ticket
add_ticket_comment(ticket_id, content)   # Ajoute commentaire
get_ticket_threads(ticket_id)            # Conversations email
get_ticket_complete_context(ticket_id)   # Contexte complet ⭐
```

**Données extraites:**
- ticketNumber, subject, description
- status, priority, departmentName
- contact (nom, email, téléphone)
- channel, createdTime, modifiedTime
- Custom fields (cf_deal_id, etc.)
- Threads email complets
- Historique modifications

---

### Zoho CRM API

**Client:** `ZohoCRMClient` dans `src/zoho_client.py`
**Auth:** OAuth2 séparé (optionnel) ou partagé
**Base URL:** `https://www.zohoapis.{datacenter}/crm/v3`

**Méthodes principales:**
```python
get_deal(deal_id)                        # Récupère 1 deal
update_deal(deal_id, data)               # Modifie deal
search_all_deals(criteria)               # Recherche avec pagination
search_contacts(criteria)                # Recherche contacts
get_deals_by_contact(contact_id)         # Deals d'un contact
add_deal_note(deal_id, title, content)   # Ajoute note
```

**Champs Deal:**
- Deal_Name, Stage, Amount, Probability
- Contact_Name, Account_Name
- Closing_Date, Next_Step
- Lead_Source, Description
- Custom fields (Evalbox, Uber, etc.)

---

### 📋 Schéma CRM Local (RÉFÉRENCE)

**Fichier:** `crm_schema.json` (2.4 MB)
**Date d'extraction:** 2026-01-25

> ⚠️ **IMPORTANT:** Toujours consulter ce fichier pour obtenir les noms API des modules et champs CRM. Évite d'interroger Zoho à chaque fois.

**Contenu:**
- Liste complète de tous les modules Zoho CRM
- Pour chaque module: tous les champs avec leurs métadonnées

**Structure JSON:**
```json
{
  "extraction_date": "2026-01-25T...",
  "modules": {
    "Deals": {
      "module_label": "Opportunities",
      "api_supported": true,
      "creatable": true,
      "editable": true,
      "fields_count": 127,
      "fields": [
        {
          "api_name": "Date_examen_VTC",
          "field_label": "Date examen VTC",
          "data_type": "date",
          "required": false,
          "read_only": false,
          "custom_field": true,
          "visible": true
        }
      ]
    }
  }
}
```

**Informations disponibles par champ:**
- `api_name` : Nom API à utiliser dans le code
- `field_label` : Label affiché dans l'interface Zoho
- `data_type` : Type (text, date, picklist, lookup, boolean, email, etc.)
- `required` : Champ obligatoire ou non
- `read_only` : Lecture seule ou modifiable
- `custom_field` : Champ personnalisé ou standard
- `lookup_module` : Module lié (pour les champs de type lookup)
- `pick_list_values` : Valeurs possibles (pour les picklists)

**Utilisation:**
```bash
# Rechercher un champ spécifique dans le schéma
grep -i "date_examen" crm_schema.json

# Ou utiliser le script extract_crm_schema.py
python extract_crm_schema.py --search "Date_examen"
python extract_crm_schema.py --module Deals
```

**Régénération du schéma:**
```bash
python extract_crm_schema.py
# Sauvegarde automatique dans crm_schema.json
```

---

### Anthropic Claude API

**Modèle:** `claude-3-5-sonnet-20241022`
**Configuration:**
```python
model = "claude-3-5-sonnet-20241022"
max_tokens = 4096
temperature = 0.7  # Équilibre créativité
```

**Usage:**
```python
from anthropic import Anthropic
client = Anthropic(api_key=settings.anthropic_api_key)
response = client.messages.create(
    model=settings.agent_model,
    max_tokens=settings.agent_max_tokens,
    temperature=settings.agent_temperature,
    system=system_prompt,
    messages=[...]
)
```

---

## 🎣 SERVEUR WEBHOOK

**Fichier:** `webhook_server.py`
**Framework:** Flask
**Port par défaut:** 5000

### Endpoints

| Endpoint | Méthode | Description | Auth |
|----------|---------|-------------|------|
| `/health` | GET | Health check | ❌ |
| `/webhook/zoho-desk` | POST | Webhook principal | ✅ HMAC-SHA256 |
| `/webhook/test` | POST | Test sans signature | ❌ |
| `/webhook/stats` | GET | Stats & config | ❌ |

### Sécurité HMAC-SHA256

**Vérification signature webhook:**
```python
def verify_webhook_signature(payload, signature, secret):
    computed = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)
```

**Variable env requise:** `ZOHO_WEBHOOK_SECRET`

### Événements Traités

- `ticket.created` → Nouveau ticket
- `ticket.updated` → Modification ticket
- `ticket.status_changed` → Changement statut
- `ticket.assigned` → Réaffectation

### Configuration Drapeaux

**Variables d'environnement:**
```bash
WEBHOOK_AUTO_DISPATCH=true       # ✅ Routage auto
WEBHOOK_AUTO_LINK=true          # ✅ Liaison auto
WEBHOOK_AUTO_RESPOND=false      # ⚠️ Réponses auto
WEBHOOK_AUTO_UPDATE_TICKET=false  # ⚠️ MAJ tickets
WEBHOOK_AUTO_UPDATE_DEAL=false    # ⚠️ MAJ CRM
WEBHOOK_AUTO_ADD_NOTE=false       # ⚠️ Notes CRM
```

**Recommandation:** Activer progressivement après validation manuelle

---

## ⚙️ CONFIGURATION

**Fichier:** `config.py` (Pydantic Settings)

### Variables d'environnement requises

```bash
# ===== ZOHO API =====
ZOHO_CLIENT_ID=your_client_id
ZOHO_CLIENT_SECRET=your_client_secret
ZOHO_REFRESH_TOKEN=your_refresh_token
ZOHO_DATACENTER=com              # com, eu, in, com.au
ZOHO_DESK_ORG_ID=your_org_id

# ===== ZOHO CRM (optionnel si différent de Desk) =====
ZOHO_CRM_CLIENT_ID=your_crm_client_id
ZOHO_CRM_CLIENT_SECRET=your_crm_client_secret
ZOHO_CRM_REFRESH_TOKEN=your_crm_refresh_token

# ===== ANTHROPIC =====
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx

# ===== AGENT CONFIG =====
AGENT_MODEL=claude-3-5-sonnet-20241022
AGENT_MAX_TOKENS=4096
AGENT_TEMPERATURE=0.7

# ===== LOGGING =====
LOG_LEVEL=INFO                   # DEBUG, INFO, WARNING, ERROR

# ===== WEBHOOK =====
ZOHO_WEBHOOK_SECRET=your_secret_key
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000

# ===== AUTOMATION =====
WEBHOOK_AUTO_DISPATCH=true
WEBHOOK_AUTO_LINK=true
WEBHOOK_AUTO_RESPOND=false
WEBHOOK_AUTO_UPDATE_TICKET=false
WEBHOOK_AUTO_UPDATE_DEAL=false
WEBHOOK_AUTO_ADD_NOTE=false
```

**Template:** Voir `.env.example`

---

## 🧠 RÈGLES MÉTIER (BUSINESS RULES)

**Fichier:** `business_rules.py`

### Routage Département Complexe

**Fonction:** `determine_department_from_deals_and_ticket()`

**Logique par priorité:**

1. **REFUS CMA** → Département "Refus CMA"
   - Détecté si Deal_Name contient "REFUS CMA"

2. **HORS PARTENARIAT** → Département "Contact"
   - Formation hors partenariat

3. **SPAM/Abus** → Fermeture sans note CRM

4. **Soumission Documents** → Vérification via deal 20€
   - Détection 30+ mots-clés français
   - "pièce justificative", "document", "signature", etc.

5. **VTC hors partenariat** → "DOCS CAB"

6. **Autres demandes formation** → "Contact"

7. **Cas gagnés (GAGNÉ)** → "Contact"

### Filtrage Deals Intelligent

**Priorités:**
1. Deals Uber 20€ (priorité haute)
2. Stage = GAGNÉ (opportunité gagnée)
3. Stage = ATTENTE (en attente)
4. Tri par Closing_Date (plus récent d'abord)

---

## 📚 SYSTÈME RAG (Retrieval Augmented Generation)

**Fichier:** `src/utils/response_rag.py`

### Architecture RAG

**Composants:**
1. **Index TF-IDF** → 3,304 termes de vocabulaire
2. **Base de données** → 100 tickets + 137 réponses de Fouad
3. **Similarité cosinus** → Matching top-K
4. **Few-shot prompting** → Injection exemples dans prompt Claude

### Workflow RAG

```python
# 1. Indexation
rag = ResponseRAG()
rag.add_ticket_response(ticket_text, response_text)

# 2. Recherche similarité
similar = rag.find_similar_responses(new_ticket, top_k=3)

# 3. Construction prompt few-shot
prompt = rag.build_few_shot_prompt(ticket, similar_responses)

# 4. Génération avec Claude
response = claude.generate(prompt)
```

### Patterns Analysés

**Source:** 137 vraies réponses de Fouad
**Fichier:** `src/utils/response_pattern_analyzer.py`

**Métriques:**
- Longueur moyenne: 371 mots
- Ton: Professionnel, directif, empathique
- Blocs obligatoires identifiés
- Termes interdits détectés
- Structure type extraite

---

## 🎭 WORKFLOW DOC COMPLET (8 ÉTAPES)

**Fichier:** `src/workflows/doc_ticket_workflow.py`

### Pipeline Automatisé DOC

**ÉTAPE 1: AGENT TRIEUR**
- Applique 7 règles de routage
- Décision: STOP ou CONTINUE
- Cas spéciaux: REFUS CMA, HORS PARTENARIAT, SPAM

**ÉTAPE 2: AGENT ANALYSTE**
- Extraction données de 6 sources:
  1. Zoho CRM (Contact, Deal, Sessions)
  2. ExamenT3P (Documents, Paiements, Compte)
  3. Evalbox (Éligibilité)
  4. Google Sheets (Sessions)
  5. Threads ticket
  6. Inférence email

**ÉTAPE 3: AGENT RÉDACTEUR**
- Génération réponse avec Claude + RAG
- Mapping 26+ scénarios métier
- Validation boucle de correction
- Création brouillon

**ÉTAPE 4: UPDATER**
- Écriture résultats (optionnel)
- Création note CRM
- MAJ statut ticket

---

## 📂 KNOWLEDGE BASE

**Fichier:** `knowledge_base/scenarios_mapping.py`

### 26+ Scénarios Métier Mappés

**Exemples:**
1. **Demande pièces justificatives manquantes**
2. **Non-éligibilité dossier (trop tard)**
3. **Absence de paiement Uber 20€**
4. **Problèmes techniques ExamenT3P**
5. **Questions choix matières A-Level**
6. **Demande de report session**
7. **Changement de matières**
8. **Annulation demande**
9. **Réclamation/Insatisfaction**
10. **Relance sans réponse candidat**
... (16+ autres)

**Structure scénario:**
```python
{
    "id": "scenario_01",
    "name": "Demande pièces justificatives",
    "triggers": ["pièce", "document", "justificatif"],
    "department": "DOC",
    "priority": "High",
    "template_blocks": [...]
}
```

---

## 🛠️ SCRIPTS D'EXEMPLE

**Répertoire:** `examples/` (11 scripts)

| Script | Usage |
|--------|-------|
| `basic_ticket_processing.py` | Analyse simple ticket |
| `crm_opportunity_management.py` | Gestion deals CRM |
| `full_workflow_orchestration.py` | Workflow complet ⭐ |
| `ticket_deal_linking.py` | Démonstration liaison |
| `ticket_dispatcher.py` | Exemple routage |
| `doc_ticket_automation_example.py` | Workflow DOC |
| `scheduled_automation.py` | Automation planifiée (cron) |
| `full_context_analysis.py` | Extraction contexte complet |
| `automated_deal_linking.py` | Pipeline liaison auto |
| `department_specific_linking.py` | Liaison par département |

---

## 🚀 COMMANDES CLI

**Fichier:** `main.py`

### Usage

```bash
# Traiter 1 ticket
python main.py ticket <ticket_id> [--auto-respond] [--auto-update]

# Traiter 1 deal CRM
python main.py deal <deal_id> [--auto-update] [--auto-add-note]

# Traitement batch
python main.py batch [--status Open] [--limit 10] [--auto-respond]

# Cycle complet automation
python main.py cycle [--auto-actions]
```

**Exemples:**
```bash
# Mode READ-ONLY (analyse seulement)
python main.py ticket 123456789

# Mode AUTO (actions automatiques)
python main.py ticket 123456789 --auto-respond --auto-update

# Batch 50 tickets ouverts
python main.py batch --status Open --limit 50

# Deal avec mise à jour auto
python main.py deal 987654321 --auto-update --auto-add-note
```

---

## 🧪 TESTS

### Scripts de Test

| Script | But |
|--------|-----|
| `test_webhook.py` | Test serveur webhook |
| `test_connection_quick.py` | Validation connexion API |
| `test_with_real_tickets.py` | Tests intégration données réelles |
| `test_fouad_analysis_small.py` | Analyse petit dataset |
| `test_examt3p_agent.py` | Test intégration ExamenT3P |
| `test_response_generator_structure.py` | Test génération réponses |
| `test_hors_partenariat_detection.py` | Validation règles métier |

**Lancer tests:**
```bash
pytest tests/
pytest test_webhook.py -v
```

---

## 📦 DÉPLOIEMENT

### Développement Local

```bash
# Installation
pip install -r requirements.txt
cp .env.example .env
# Éditer .env avec vos credentials

# Lancer webhook server
python webhook_server.py
# Serveur sur http://localhost:5000

# Tunnel ngrok (pour recevoir webhooks Zoho)
ngrok http 5000
# Configurer URL ngrok dans Zoho Desk webhooks
```

### Production avec Gunicorn

```bash
# Multi-worker production
gunicorn --bind 0.0.0.0:5000 \
         --workers 4 \
         --timeout 120 \
         --log-level info \
         webhook_server:app
```

### Docker

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "webhook_server:app"]
```

```bash
docker build -t a-level-saver-webhook .
docker run -d -p 5000:5000 --env-file .env a-level-saver-webhook
```

### Heroku

```bash
# Procfile
web: gunicorn --bind 0.0.0.0:$PORT --workers 4 webhook_server:app

# Déploiement
git push heroku main
heroku config:set ZOHO_CLIENT_ID=xxxxx
heroku logs --tail
```

---

## 🔍 DEBUGGING

### Logs Structurés

**Configuration:** `src/utils/logging_config.py`

**Niveaux:**
- `DEBUG` → Tous les détails (développement)
- `INFO` → Informations importantes (production)
- `WARNING` → Avertissements
- `ERROR` → Erreurs critiques

**Fichiers logs:**
```
logs/
├── app.log              # Log principal
├── webhook.log          # Logs webhook
└── errors.log           # Erreurs seulement
```

**Variable env:** `LOG_LEVEL=INFO`

### Commandes Debugging

```bash
# Vérifier connexion API
python test_connection_quick.py

# Tester webhook localement
curl -X POST http://localhost:5000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"ticketId": "123456789"}'

# Analyser 1 ticket en mode verbose
python main.py ticket 123456789 --verbose

# Voir stats webhook
curl http://localhost:5000/webhook/stats
```

---

## 🔐 SÉCURITÉ

### Bonnes Pratiques Implémentées

✅ **Vérification HMAC-SHA256** pour webhooks
✅ **OAuth2** avec refresh automatique
✅ **Secrets dans .env** (git-ignored)
✅ **Validation Pydantic** des données
✅ **Logs sans données sensibles**
✅ **Timeout configurable** sur requêtes API
✅ **Retry avec backoff exponentiel**

### Données Sensibles

**Ne JAMAIS commiter:**
- `.env` (credentials)
- `*.log` (logs peuvent contenir données clients)
- Tokens OAuth temporaires
- Clés API

**Git ignore:** Voir `.gitignore`

---

## 📈 MÉTRIQUES & MONITORING

### Health Check

```bash
# Vérifier que le serveur est up
curl http://localhost:5000/health

# Réponse:
{
  "status": "healthy",
  "timestamp": "2024-01-25T10:00:00Z",
  "version": "1.0.0"
}
```

### Stats Webhook

```bash
curl http://localhost:5000/webhook/stats

# Réponse:
{
  "webhooks_received": 1234,
  "webhooks_processed": 1200,
  "webhooks_failed": 34,
  "auto_dispatch_enabled": true,
  "auto_link_enabled": true,
  "auto_respond_enabled": false
}
```

---

## 🎓 PATTERNS D'ARCHITECTURE

### 1. Agent Pattern
- Classe abstraite `BaseAgent`
- Agents spécialisés (Desk, CRM, Dispatcher, etc.)
- Historique conversation géré
- Framework réutilisable

### 2. Orchestrator Pattern
- Coordonne plusieurs agents
- Gère l'ordre du workflow
- Passage de données entre étapes
- Recovery sur erreurs

### 3. Multi-Strategy Pattern
- Stratégie primaire (champ custom)
- Fallback strategies (email, téléphone, compte)
- Scoring de confiance
- Suggestions alternatives

### 4. Progressive Automation
- **READ-ONLY** → Analyse seulement
- **SUGGEST** → Avec recommandations
- **DISPATCH** → Routage auto
- **FULL-AUTO** → Toutes actions

### 5. RAG Pattern
- Index tickets/réponses passés
- Matching similarité TF-IDF
- Génération prompt few-shot
- Injection contexte à Claude

---

## 📖 DOCUMENTATION COMPLÈTE

**15 fichiers Markdown (~140 KB):**

| Fichier | Contenu |
|---------|---------|
| **README.md** | Vue d'ensemble projet |
| **GUIDE.md** | Guide complet usage |
| **WEBHOOK_QUICKSTART.md** | Setup webhook 5min |
| **WEBHOOK_SETUP.md** | Config détaillée webhook |
| **API_REFERENCE.md** | Référence API Zoho |
| **DOC_TICKET_AUTOMATION.md** | Workflow DOC 8 étapes |
| **TICKET_DEAL_LINKING.md** | Stratégie liaison deals |
| **ROUTING_WORKFLOW.md** | Logique routage départements |
| **THREAD_CONTENT_STRATEGY.md** | Gestion threads email |
| **PAGINATION_INFO.md** | Patterns pagination API |
| **ENRICHMENT_GUIDE.md** | Workflow enrichissement données |
| **IMPLEMENTATION_COMPLETE.md** | Statut & checklist |
| **GUIDE_TEST.md** | Guide testing |
| **DOCUMENT_KEYWORDS.md** | Mots-clés détection docs |
| **WORKFLOW.md** | Vue workflow |

---

## 🎯 DÉCISIONS TECHNIQUES

| Décision | Justification |
|----------|---------------|
| **Flask** | Léger, simple webhooks |
| **Pydantic** | Validation forte, settings management |
| **Claude 3.5 Sonnet** | Meilleur raisonnement logique complexe |
| **OAuth2** | Standard industrie sécurisé |
| **HMAC-SHA256** | Sécurité webhook vérifiée |
| **TF-IDF + Cosine** | Matching similarité efficace RAG |
| **Playwright** | Automation navigateur robuste |
| **Gunicorn** | Serveur WSGI production-grade |

---

## ⚡ QUICK START

### Installation Rapide

```bash
# 1. Cloner repo
git clone <repo-url>
cd a-level-saver

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configuration
cp .env.example .env
# Éditer .env avec vos credentials Zoho + Anthropic

# 4. Tester connexion
python test_connection_quick.py

# 5. Analyser un ticket (read-only)
python main.py ticket <ticket_id>

# 6. Lancer webhook server
python webhook_server.py
# Ou en production:
gunicorn --bind 0.0.0.0:5000 --workers 4 webhook_server:app

# 7. Configurer tunnel ngrok (dev)
ngrok http 5000
# Copier URL publique vers Zoho Desk webhook settings
```

---

## 🚨 POINTS D'ATTENTION

### ⚠️ Mode Full-Auto

**Attention:** Les flags `auto_respond`, `auto_update_ticket`, `auto_update_deal` modifient les données réelles.

**Recommandation:**
1. ✅ Commencer en READ-ONLY
2. ✅ Activer `auto_dispatch` + `auto_link` (lecture CRM seulement)
3. ⚠️ Tester manuellement quelques tickets
4. ⚠️ Activer progressivement autres flags
5. ⚠️ Monitorer logs attentivement

### 🔍 Rate Limiting Zoho

**Limites API Zoho:**
- Desk: ~10,000 requêtes/jour
- CRM: ~5,000 requêtes/jour (varie selon plan)

**Mitigation:**
- Retry avec backoff exponentiel (3 tentatives)
- Pagination intelligente
- Caching tokens OAuth
- Éviter appels redondants

### 🧠 Token Limits Claude

**Limites:**
- Max tokens par requête: 4,096 (config)
- Context window: 200K tokens

**Optimisation:**
- Résumé threads longs
- Extraction contenu pertinent seulement
- Éviter inclure historique complet si > 50 messages

---

## 📞 SUPPORT & RESSOURCES

### Documentation Externe

- **Zoho Desk API:** https://desk.zoho.com/DeskAPIDocument
- **Zoho CRM API:** https://www.zoho.com/crm/developer/docs/api/v3/
- **Anthropic Claude:** https://docs.anthropic.com/
- **Flask Webhooks:** https://flask.palletsprojects.com/

### Contact Technique

**Développeur:** Fouad (CAB Formations)
**Projet:** A-Level Saver Automation
**Version:** 1.0.0 (Production-ready)

---

## 📊 CHANGELOG RÉCENT (Git Commits)

```
760f012 - Implement Zoho Desk webhook automation server
d13bc15 - Add webhook payload and test data for testing
1278813 - Fix email extraction from Zoho Desk tickets
1deb642 - Implement 2-step deal search: Contact → Deal
6f1627f - Add debug script to investigate why deals are not found
```

---

## ✅ STATUT IMPLÉMENTATION

| Fonctionnalité | Statut | Notes |
|----------------|--------|-------|
| **API Zoho Desk** | ✅ Complet | CRUD + threads complets |
| **API Zoho CRM** | ✅ Complet | Deals + Contacts + Notes |
| **Agents IA (7)** | ✅ Complet | Tous opérationnels |
| **Orchestrateur** | ✅ Complet | Workflow 4 étapes |
| **Webhook Server** | ✅ Complet | Flask + HMAC security |
| **Système RAG** | ✅ Complet | 100 tickets + 137 réponses |
| **Business Rules** | ✅ Complet | Routage + Liaison |
| **Workflow DOC** | ✅ Complet | 8 étapes automatisées |
| **CLI Interface** | ✅ Complet | 4 commandes |
| **Tests** | ✅ Complet | 7+ scripts test |
| **Documentation** | ✅ Complet | 15 fichiers MD |
| **Déploiement** | ✅ Ready | Docker + Heroku ready |

**État:** ✅ **PRODUCTION-READY**

---

## 🎉 FONCTIONNALITÉS CLÉS

✅ **Automation Temps Réel** → Webhook-triggered
✅ **Routage Intelligent** → Multi-critères + business rules
✅ **IA Contextuelle** → Claude 3.5 Sonnet
✅ **Liaison Bi-directionnelle** → Desk ↔ CRM sync
✅ **RAG Few-Shot** → Apprentissage de 137 réponses Fouad
✅ **Automation Progressive** → READ → SUGGEST → DISPATCH → FULL-AUTO
✅ **Logs Structurés** → Debugging facilité
✅ **Multi-Worker** → Scalable avec Gunicorn
✅ **Sécurité HMAC** → Webhooks vérifiés
✅ **26+ Scénarios** → Couverture métier complète

---

## 🆕 MISES À JOUR MAJEURES - JANVIER 2026

### 🔄 Migration Claude Sonnet 4.5 (25 janvier 2026)

**Changement modèle IA:**
- Ancien: `claude-3-5-sonnet-20241022`
- Nouveau: `claude-sonnet-4-5-20250929` ✅

**Fichiers modifiés:**
- `config.py`: agent_model mis à jour
- `.env.example`: Documentation mise à jour

**Impact:** Amélioration qualité génération + performance

---

### 🔐 Nouvelle Logique de Gestion des Identifiants ExamT3P

**Fichier:** `src/utils/examt3p_credentials_helper.py`

#### Workflow de Validation (3 étapes)

**Étape 1:** Recherche identifiants dans Zoho CRM
- Champs: `IDENTIFIANT_EVALBOX`, `MDP_EVALBOX`

**Étape 2:** Si absents → Recherche dans threads email
- Patterns détectés: `identifiant:`, `login:`, `email:`, `mot de passe:`, `mdp:`, `password:`
- Extraction intelligente avec regex

**Étape 3:** Test de connexion OBLIGATOIRE (si identifiants trouvés)
- Utilise Playwright pour tester login ExamT3P
- Validation réelle de la connexion

#### 3 Cas de Gestion

**CAS 1: Identifiants absents (ni Zoho ni threads)**
```python
{
    'credentials_found': False,
    'should_respond_to_candidate': False,  # ⚠️ NE PAS demander
    'candidate_response_message': None
}
```
**Raison:** C'est nous qui allons créer le compte → Pas de demande au candidat

**CAS 2: Identifiants présents mais INVALIDES (connexion échouée)**
```python
{
    'credentials_found': True,
    'connection_test_success': False,
    'should_respond_to_candidate': True,
    'candidate_response_message': "Procédure 'Mot de passe oublié ?'..."
}
```
**Raison:** Candidat a probablement modifié son mot de passe

**Message généré:**
- Explication de l'échec de connexion
- Procédure détaillée de réinitialisation:
  1. Aller sur https://www.exament3p.fr
  2. Cliquer "Me connecter"
  3. Utiliser "Mot de passe oublié ?"
  4. Suivre les instructions
  5. Retransmettre les nouveaux identifiants

**CAS 3: Identifiants valides (connexion OK)**
```python
{
    'credentials_found': True,
    'connection_test_success': True,
    'compte_existe': True,
    # + données extraites (documents, paiement, etc.)
}
```
**Action:** Extraction complète des données ExamT3P

#### Mise à Jour Automatique CRM

Si identifiants trouvés dans threads email ET connexion OK:
- ✅ Mise à jour automatique de `IDENTIFIANT_EVALBOX` et `MDP_EVALBOX` dans Zoho CRM
- Log: "CRM mis à jour avec les nouveaux identifiants"

---

### 📅 Nouvelle Logique de Gestion des Dates d'Examen VTC

**Fichier:** `src/utils/date_examen_vtc_helper.py`

#### Objectif

Inscrire le candidat à son examen VTC en s'assurant que la date d'examen est renseignée et valide. Si des informations manquent, les ajouter automatiquement à la réponse.

#### Champs CRM Utilisés

**Module Deals:**
- `Date_examen_VTC` (lookup) → Module `Dates_Examens_VTC_TAXI`
- `Evalbox` (picklist) → Statut du dossier
- `CMA_de_depot` (text) → CMA/Département du candidat

**Module Dates_Examens_VTC_TAXI:**
- `Date_Examen` (date) → Date de l'examen
- `Date_Cloture_Inscription` (datetime) → Date limite inscription
- `Departement` (integer) → Numéro département (75, 93, etc.)
- `Statut` (picklist) → Actif, Complet, Cloturé, Annulé
- `Libelle_Affichage` (text) → Libellé pour affichage candidat

#### Les 8 Cas de Gestion

| CAS | Condition | Action dans la réponse |
|-----|-----------|------------------------|
| **1** | `Date_examen_VTC` = vide | Proposer 2 prochaines dates (CMA du candidat, clôture future) |
| **2** | Date passée + `Evalbox` ≠ "VALIDE CMA" / "Dossier Synchronisé" | Proposer 2 prochaines dates |
| **3** | `Evalbox` = "Refusé CMA" | Informer du refus + lister pièces refusées (ExamT3P) + date clôture + prochaine date |
| **4** | Date future + `Evalbox` = "VALIDE CMA" | Rassurer : dossier validé, convocation ~10j avant examen |
| **5** | Date future + `Evalbox` = "Dossier Synchronisé" | Prévenir : instruction en cours, surveiller mails, corriger avant clôture sinon décalé |
| **6** | Date future + `Evalbox` = autre + clôture future | En attente (pas d'action spéciale) |
| **7** | Date passée + `Evalbox` ∈ {VALIDE CMA, Dossier Synchronisé} | Examen passé, SAUF indices thread → demander clarification |
| **8** | Date future + **clôture passée** + `Evalbox` ≠ VALIDE CMA/Dossier Synchronisé | Deadline ratée → Informer du report + proposer 2 prochaines dates |

#### Valeurs Evalbox

- `Dossier crée` → Compte créé
- `Documents manquants` / `Documents refusés` → Problème documents
- `Pret a payer` / `Pret a payer par cheque` → En attente paiement
- `Dossier Synchronisé` → En cours d'instruction CMA
- `VALIDE CMA` → Dossier validé par CMA
- `Refusé CMA` → Pièces refusées par CMA
- `Convoc CMA reçue` → Convocation reçue

#### Fonctions Principales

```python
from src.utils.date_examen_vtc_helper import analyze_exam_date_situation, get_next_exam_dates

# Analyser la situation du candidat
result = analyze_exam_date_situation(
    deal_data=deal_data,
    threads=threads_data,
    crm_client=crm_client,
    examt3p_data=examt3p_data
)

# Résultat
{
    'case': 1,  # Numéro du cas (1-8)
    'case_description': 'Date examen VTC vide - Proposer 2 prochaines dates',
    'should_include_in_response': True,  # Doit-on ajouter info à la réponse?
    'response_message': '...',  # Message à intégrer
    'next_dates': [...],  # Prochaines dates disponibles
    'pieces_refusees': [...],  # Pour cas 3
    'date_cloture': '2026-02-15'
}

# Récupérer les prochaines dates d'examen
next_dates = get_next_exam_dates(
    crm_client=crm_client,
    departement='75',
    limit=2
)
```

#### Intégration Workflow DOC

Le helper est automatiquement appelé dans l'étape ANALYSE du workflow DOC:

1. **Analyse** → `analyze_exam_date_situation()` est appelé
2. **Log** → Affiche le cas détecté
3. **Génération réponse** → Les données sont passées à l'agent rédacteur
4. **Réponse** → Le message date examen est intégré si `should_include_in_response=True`

---

### 🔧 Corrections Workflow DOC

**Fichier:** `src/workflows/doc_ticket_workflow.py`

**Problèmes corrigés:**

1. **Lecture contenu threads** ✅
   - Avant: `get_ticket_threads()` → Contenu partiel
   - Après: `get_all_threads_with_full_content()` → Contenu complet
   - Utilise: `get_clean_thread_content()` pour extraction propre

2. **Utilisation DealLinkingAgent** ✅
   - Avant: `find_deal_for_ticket()` (n'existe pas)
   - Après: `process()` (méthode correcte)

3. **Méthode close()** ✅
   - Ajout vérification `hasattr()` avant appel
   - Gestion ExamT3PAgent sans méthode close()

**Impact:** Workflow DOC 100% fonctionnel avec contenu complet

---

### 🧪 Nouveaux Scripts de Test

**1. `list_recent_tickets.py`** - Liste tickets valides
```bash
python list_recent_tickets.py [--status Open] [--limit 20]
```
**Sortie:**
- Liste tickets avec ID, sujet, contact, département
- Commande de test prête à copier-coller

**2. `test_doc_workflow_with_examt3p.py`** - Test workflow DOC complet
```bash
python test_doc_workflow_with_examt3p.py <TICKET_ID>
```
**Teste les 8 étapes:**
1. TRIAGE
2. ANALYSE (incluant validation ExamT3P)
3. GÉNÉRATION réponse
4. CRM Note
5. Ticket Update
6. Deal Update
7. Draft Creation
8. Final Validation

**Affichage détaillé:**
- Deal trouvé (ID, nom, stage)
- Validation ExamT3P (cas 1, 2 ou 3)
- Scénarios détectés
- Message généré (preview)
- CRM note créée

**3. `test_missing_credentials_behavior.py`** - Test cas ExamT3P
- Valide le cas "identifiants absents"
- Valide le cas "identifiants invalides"

**4. `extract_crm_schema.py`** - Extraction schéma CRM ⭐ NOUVEAU
```bash
# Extraire tous les modules et champs CRM
python extract_crm_schema.py

# Rechercher un champ spécifique
python extract_crm_schema.py --search "Date_examen"

# Lister tous les champs d'un module
python extract_crm_schema.py --module Deals
```

**Fonctionnalités:**
- ✅ Extraction automatique de TOUS les modules Zoho CRM
- ✅ Pour chaque module: tous les champs avec nom API, type, label, options
- ✅ Sauvegarde dans `crm_schema.json`
- ✅ Recherche de champs par nom
- ✅ Liste détaillée des champs d'un module
- ✅ Informations sur picklists et lookups

**Utilité:**
- Évite de devoir demander les noms de champs API à chaque fois
- Documentation automatique du schéma CRM
- Référence rapide pour développement

**Sortie JSON:**
```json
{
  "extraction_date": "2026-01-25T...",
  "modules": {
    "Deals": {
      "module_label": "Opportunities",
      "fields_count": 127,
      "fields": [
        {
          "api_name": "Date_examen_VTC",
          "field_label": "Date examen VTC",
          "data_type": "date",
          "required": false,
          "custom_field": true
        },
        ...
      ]
    },
    ...
  }
}
```

---

### 📋 Documentation Technique

**Nouveau fichier:** `TESTING_CHECKLIST.md`

**Contenu:**
- ✅ Checklist complète des corrections
- ✅ Actions requises avant test
- ✅ Commandes de test détaillées
- ✅ Comportements attendus (3 cas)
- ✅ Diagnostic problèmes potentiels
- ✅ Solutions aux erreurs courantes

**Utilité:** Guide complet pour tester et diagnostiquer

---

### 🐛 Bugs Corrigés

| Bug | Fichier | Fix |
|-----|---------|-----|
| Chromium path hardcodé `/usr/bin/...` | `examt3p_credentials_helper.py` | Supprimé (Playwright auto-detect) |
| `NoneType.get()` crash | `test_new_workflow.py` | Ajout vérification `if crm_result:` |
| Message "vide" dans réponse | `doc_ticket_workflow.py` | Utilise `get_all_threads_with_full_content()` |
| `find_deal_for_ticket()` n'existe pas | `doc_ticket_workflow.py` | Remplacé par `process()` |
| `ExamT3PAgent.close()` n'existe pas | `doc_ticket_workflow.py` | Supprimé l'appel |

---

### 📊 État Actuel (25 janvier 2026)

**Workflow DOC:** ✅ 100% fonctionnel
- Toutes les 8 étapes opérationnelles
- Validation ExamT3P intégrée (3 cas)
- Lecture contenu complet threads
- Génération réponse avec contexte complet

**Tests:** ✅ Tous les tests passent
- `test_credentials_workflow.py`: 4/4 ✅
- `test_missing_credentials_behavior.py`: 2/2 ✅
- `test_doc_workflow_with_examt3p.py`: Fonctionnel ✅

**Compatibilité:** ✅ Cross-platform
- Windows, Linux, macOS
- Playwright auto-détecte navigateur

**Modèle IA:** ✅ Claude Sonnet 4.5 (latest)

---

## 📅 LOGIQUE DATES D'EXAMEN ET SESSIONS DE FORMATION (CRUCIAL)

### Architecture des Dépendances

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WORKFLOW DOC - ÉTAPE ANALYSE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. DEAL CRM                                                                │
│     ├── Date_examen_VTC (lookup) ──────► Dates_Examens_VTC_TAXI            │
│     ├── Evalbox (picklist) ────────────► Statut du dossier                 │
│     ├── CMA_de_depot (text) ───────────► Département candidat              │
│     └── Session (lookup) ──────────────► Sessions1                         │
│                                                                             │
│  2. ANALYSE DATE EXAMEN (date_examen_vtc_helper.py)                         │
│     └── Détermine CAS 1-8 selon Date_examen_VTC + Evalbox                  │
│         └── Récupère next_dates si nécessaire                              │
│                                                                             │
│  3. ANALYSE SESSIONS (session_helper.py)                                    │
│     └── SI next_dates disponibles:                                         │
│         ├── Cherche sessions AVANT Date_Examen                             │
│         ├── Filtre: Lieu_de_formation = VISIO Zoom VTC (Uber)              │
│         ├── Détecte préférence (jour/soir) depuis deal + threads           │
│         └── Propose sessions CDJ et/ou CDS                                 │
│                                                                             │
│  4. GÉNÉRATION RÉPONSE                                                      │
│     └── Inclut dates examen + sessions associées + règles métier           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 📊 Modules CRM Impliqués

#### Module `Deals` (Opportunities)

| Champ API | Type | Description |
|-----------|------|-------------|
| `Date_examen_VTC` | lookup | Lien vers `Dates_Examens_VTC_TAXI` |
| `Evalbox` | picklist | Statut du dossier ExamT3P |
| `CMA_de_depot` | text | CMA/Département du candidat (ex: "CMA 75", "93") |
| `Session` | lookup | Session de formation actuelle |
| `Session_souhait_e` | text | Préférence jour/soir du candidat |

**Valeurs Evalbox:**
- `Dossier crée` → Compte créé sur ExamT3P
- `Documents manquants` → Pièces à fournir
- `Documents refusés` → Pièces à corriger
- `Pret a payer` / `Pret a payer par cheque` → En attente paiement
- `Dossier Synchronisé` → Transmis à la CMA, en instruction
- `VALIDE CMA` → Dossier validé par la CMA ✅
- `Refusé CMA` → Pièces refusées par la CMA ❌
- `Convoc CMA reçue` → Convocation reçue

#### Module `Dates_Examens_VTC_TAXI`

| Champ API | Type | Description |
|-----------|------|-------------|
| `Date_Examen` | date | Date de l'examen (YYYY-MM-DD) |
| `Date_Cloture_Inscription` | datetime | Date limite d'inscription |
| `Departement` | integer | Numéro département (75, 93, etc.) |
| `Statut` | picklist | Actif, Complet, Cloturé, Annulé |
| `Libelle_Affichage` | text | Libellé pour affichage candidat |
| `Adresse_Centre` | text | Adresse du centre d'examen |

#### Module `Sessions1` (Sessions de Formation)

| Champ API | Type | Description |
|-----------|------|-------------|
| `Name` | text | Nom de la session (cdj-*, cds-*) |
| `Date_d_but` | date | Date de début |
| `Date_fin` | date | Date de fin |
| `Lieu_de_formation` | lookup | Lieu (VISIO Zoom VTC pour Uber) |
| `Statut` | picklist | PLANIFIÉ, EN COURS, TERMINÉ |
| `Type_de_cours` | text | Type de formation |

---

### 🎯 Les 8 Cas de Gestion Date d'Examen

**Fichier:** `src/utils/date_examen_vtc_helper.py`

| CAS | Condition | Action | Message |
|-----|-----------|--------|---------|
| **1** | `Date_examen_VTC` = vide | Proposer 2 prochaines dates | "Nous n'avons pas de date d'examen enregistrée..." |
| **2** | Date passée + Evalbox ≠ VALIDE CMA/Dossier Sync | Proposer 2 prochaines dates | "La date d'examen est passée..." |
| **3** | Evalbox = `Refusé CMA` | Informer refus + pièces + prochaine date | "La CMA a refusé certaines pièces..." |
| **4** | Date future + Evalbox = `VALIDE CMA` | Rassurer | "Bonne nouvelle ! Dossier validé, convocation ~10j avant" |
| **5** | Date future + Evalbox = `Dossier Synchronisé` | Prévenir instruction en cours | "Surveiller emails, corriger si demandé..." |
| **6** | Date future + Evalbox autre + clôture future | Pas d'action spéciale | Ne rien ajouter (en attente) |
| **7** | Date passée + Evalbox ∈ {VALIDE CMA, Dossier Sync} | Examen probablement passé | Demander clarification si indices contraires |
| **8** | Date future + **clôture passée** + Evalbox ≠ VALIDE/Sync | Deadline ratée → report | "Inscriptions clôturées, report automatique..." |
| **9** | Evalbox = `Convoc CMA reçue` | Transmettre identifiants + instructions | Lien ExamT3P, identifiants, télécharger/imprimer, pièce d'identité, bonne chance |
| **10** | Evalbox = `Pret a payer` / `Pret a payer par cheque` | Informer du paiement en cours | Paiement imminent, surveiller emails, corriger si refus avant clôture |

---

### 🚗 Éligibilité Uber 20€ (PRÉREQUIS OBLIGATOIRES)

**Fichier:** `src/utils/uber_eligibility_helper.py`

#### Contexte de l'Offre Uber 20€

L'offre en partenariat avec Uber à 20€ inclut:
- **Inscription à l'examen VTC** (frais de 241€ payés par CAB Formations)
- **Accès à la plateforme e-learning**
- **Formation en visio** avec formateur (cours du jour OU cours du soir)

#### Étapes Obligatoires pour Être Éligible

```
Paiement 20€ (Opp gagnée)
        ↓
[CAS A si manquant]
        ↓
1. Envoyer documents + finaliser inscription CAB Formations
   → Champ: Date_Dossier_re_u non vide
        ↓
[CAS B si manquant]
        ↓
2. Passer le test de sélection (mail envoyé après étape 1)
   → Champ: Date_test_selection non vide
        ↓
✅ ÉLIGIBLE → Peut être inscrit à l'examen
```

#### Les 2 Cas de Blocage

| CAS | Condition | Action |
|-----|-----------|--------|
| **A** | Opp 20€ gagnée + `Date_Dossier_re_u` vide | Expliquer offre + demander de finaliser inscription |
| **B** | `Date_Dossier_re_u` OK + `Date_test_selection` vide | Demander de passer le test de sélection |

**Important:** Si CAS A ou B, on ne peut PAS parler de dates d'examen ou de formation !

#### Champs CRM Utilisés

| Champ API | Description |
|-----------|-------------|
| `Stage` | Doit être "GAGNÉ" pour identifier une opp gagnée |
| `Amount` | Doit être ~20€ pour identifier l'offre Uber |
| `Date_Dossier_re_u` | Date de réception du dossier complet |
| `Date_test_selection` | Date de passage du test de sélection |

#### Message CAS A (Documents non envoyés)

```
Nous avons bien reçu votre paiement de 20€ pour l'offre VTC en partenariat avec Uber.

**Ce que comprend votre offre :**
- Inscription à l'examen VTC incluant les frais de 241€ (pris en charge)
- Accès à notre plateforme e-learning
- Formation en visio avec formateur (jour OU soir)

**Pour en bénéficier, il vous reste à :**
1. Finaliser votre inscription sur la plateforme CAB Formations
2. Nous transmettre tous vos documents
3. Passer un test de sélection simple (lien envoyé après finalisation)
```

#### Message CAS B (Test non passé)

```
Nous avons bien reçu votre dossier.

**Pour finaliser votre inscription, il vous reste une dernière étape :**

Vous devez passer le **test de sélection**. Un email avec le lien vous a été envoyé.

**À propos du test :**
- Simple et rapide
- Ne nécessite pas de consulter les cours
- Nous permet de déclencher votre inscription à l'examen

Nous ne pouvons pas procéder à votre inscription tant que vous n'avez pas réussi ce test.
```

---

### 🗺️ Vision Globale: Parcours Candidat VTC (Evalbox)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PARCOURS CANDIDAT VTC - ÉTATS EVALBOX                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. CRÉATION COMPTE                                                         │
│     └── Evalbox = "Dossier crée"                                           │
│         → Compte créé sur ExamT3P, en attente des documents                │
│                     ↓                                                       │
│  2. DOCUMENTS                                                               │
│     ├── Evalbox = "Documents manquants"                                    │
│     │   → Pièces à fournir par le candidat                                 │
│     └── Evalbox = "Documents refusés"                                      │
│         → Pièces à corriger (rejetées par CAB)                             │
│                     ↓                                                       │
│  3. PAIEMENT (CAS 10)                                                       │
│     └── Evalbox = "Pret a payer" / "Pret a payer par cheque"               │
│         → CAB va payer les frais d'examen → Instruction CMA                │
│         → Surveiller emails pour demandes CMA                              │
│                     ↓                                                       │
│  4. INSTRUCTION CMA (CAS 5)                                                 │
│     └── Evalbox = "Dossier Synchronisé"                                    │
│         → Dossier transmis à la CMA, en cours d'examen                     │
│         → Peut être accepté ou refusé                                      │
│                     ↓                                                       │
│  5a. VALIDATION (CAS 4)              5b. REFUS (CAS 3)                      │
│      └── Evalbox = "VALIDE CMA"          └── Evalbox = "Refusé CMA"        │
│          → Dossier OK !                      → Pièces refusées par CMA     │
│          → Convocation ~10j avant            → Corriger avant clôture      │
│                     ↓                                    ↓                  │
│  6. CONVOCATION (CAS 9)                      Retour étape 2 ou 3           │
│     └── Evalbox = "Convoc CMA reçue"                                       │
│         → Télécharger sur ExamT3P                                          │
│         → Imprimer + pièce d'identité                                      │
│         → BONNE CHANCE !                                                   │
│                     ↓                                                       │
│  7. EXAMEN (CAS 7)                                                          │
│     └── Date passée + Evalbox validé                                       │
│         → Examen probablement passé                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Cas d'erreur/exception:**
- **CAS 1**: Pas de date d'examen → Proposer dates
- **CAS 2**: Date passée + non validé → Proposer nouvelles dates
- **CAS 8**: Deadline clôture passée + non validé → Report automatique

---

## 🚨 RÈGLES CRITIQUES DE MODIFICATION (OBLIGATOIRES)

### Architecture de Synchronisation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WORKFLOW DOC - ORDRE D'EXÉCUTION                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. RÉCUPÉRATION DEAL CRM                                                   │
│     └── Données actuelles du deal                                          │
│                     ↓                                                       │
│  2. SYNC EXAMT3P → CRM (examt3p_crm_sync.py) ⚡ PRIORITAIRE                │
│     ├── ExamT3P est la SOURCE DE VÉRITÉ                                   │
│     ├── Mapping statuts → Evalbox                                          │
│     ├── Mise à jour identifiants si vides                                  │
│     └── LOG dans note CRM                                                  │
│                     ↓                                                       │
│  3. EXTRACTION CONFIRMATIONS TICKET (ticket_info_extractor.py)             │
│     ├── Détection: confirmations date, préférence session, report          │
│     ├── VALIDATION règles critiques AVANT modification                     │
│     └── LOG dans note CRM                                                  │
│                     ↓                                                       │
│  4. ANALYSE DATE EXAMEN + SESSIONS                                          │
│     └── Analyse normale avec données à jour                                │
│                     ↓                                                       │
│  5. GÉNÉRATION RÉPONSE                                                      │
│     └── LOG réponse dans note CRM                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 🔒 Règle Critique #1: JAMAIS Modifier Date_examen_VTC SI...

**Condition de blocage:**
```
SI Evalbox ∈ {"VALIDE CMA", "Convoc CMA reçue"}
ET Date_Cloture_Inscription < aujourd'hui (passée)
→ JAMAIS MODIFIER Date_examen_VTC automatiquement
```

**Raison:** Le candidat est inscrit auprès de la CMA. Un report nécessite:
1. Un justificatif de force majeure (certificat médical, etc.)
2. OU des frais de réinscription de 241€

**Fichiers concernés:**
- `src/utils/examt3p_crm_sync.py` → `can_modify_exam_date()`
- `src/utils/ticket_info_extractor.py` → Validation avant mise à jour

### 🔒 Règle Critique #2: Communication par EMAIL Uniquement

**NE JAMAIS:**
- Dire "nous contacter" ou "nous appeler"
- Suggérer de téléphoner

**TOUJOURS:**
- Demander de transmettre le justificatif **par email**
- Indiquer la procédure par email

**Message type (demande de report bloquée):**
```
Votre dossier a été validé par la CMA et les inscriptions sont clôturées.

**Un report de date d'examen n'est possible qu'avec un justificatif de force majeure.**

Pour demander un report, merci de nous transmettre **par email** :
1. Votre justificatif de force majeure (certificat médical ou autre document officiel)
2. Une brève explication de votre situation

Nous soumettrons votre demande à la CMA pour validation du report.

**Sans justificatif valide**, des frais de réinscription de 241€ seront nécessaires.
```

### 📊 Mapping ExamT3P → Evalbox CRM

**Fichier:** `src/utils/examt3p_crm_sync.py`

Le champ **"Statut du Dossier"** de ExamT3P détermine la valeur Evalbox dans CRM:

| ExamT3P (Statut du Dossier) | → Evalbox CRM |
|-----------------------------|---------------|
| En cours de composition | Dossier crée |
| En attente de paiement | Pret a payer |
| En cours d'instruction | Dossier Synchronisé |
| Incomplet | Refusé CMA |
| Valide | VALIDE CMA |
| En attente de convocation | Convoc CMA reçue |

**Note importante:** Les valeurs "Documents manquants" et "Documents refusés" sont utilisées
**AVANT** la création du compte ExamT3P (gestion interne CAB Formations)

### 📥 Extraction des Confirmations (Tickets)

**Fichier:** `src/utils/ticket_info_extractor.py`

**Patterns détectés:**
| Type | Exemples |
|------|----------|
| Confirmation date examen | "je confirme pour le 15/03", "ok pour le 15 mars" |
| Préférence session | "cours du soir", "en journée", "après le travail" |
| Confirmation session | "ok pour la session du 24/02" |
| Demande de report | "je souhaite décaler", "reporter mon examen" |

**Workflow:**
```python
confirmations = extract_confirmations_from_threads(threads, deal_data)

# Résultat:
{
    'date_examen_confirmed': '2026-03-15',  # ou None
    'session_preference': 'soir',  # ou 'jour', ou None
    'report_requested': True,  # ou False
    'blocked_updates': [...],  # Mises à jour bloquées par règle critique
    'changes_to_apply': [...]  # Changements autorisés
}
```

### 📝 Logging Systématique (Notes CRM)

**Fichier:** `src/utils/crm_note_logger.py`

**Types de notes:**
| Type | Emoji | Description |
|------|-------|-------------|
| `SYNC_EXAMT3P` | 🔄 | Synchronisation ExamT3P → CRM |
| `TICKET_UPDATE` | 📥 | Mise à jour depuis ticket |
| `RESPONSE_SENT` | 📤 | Réponse envoyée au candidat |
| `EXAM_DATE_BLOCKED` | 🔒 | Tentative de modification bloquée |
| `UBER_ELIGIBILITY` | 🚗 | Vérification éligibilité Uber |
| `SESSION_LINKED` | 📚 | Session de formation liée |

**Format des notes:**
```
🔄 SYNC_EXAMT3P - 25/01/2026 14:30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ CHANGEMENTS APPLIQUÉS:
  • Evalbox: 'Dossier Synchronisé' → 'VALIDE CMA'
  • IDENTIFIANT_EVALBOX: '' → 'candidat@email.com'

🔒 CHANGEMENTS BLOQUÉS:
  • Date_examen_VTC: Clôture passée + VALIDE CMA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Fonctions principales:**
```python
from src.utils.crm_note_logger import (
    log_examt3p_sync,
    log_ticket_update,
    log_response_sent,
    log_exam_date_blocked,
    log_uber_eligibility_check
)

# Log sync ExamT3P
log_examt3p_sync(deal_id, crm_client, sync_result)

# Log update depuis ticket
log_ticket_update(deal_id, crm_client, ticket_id, confirmations)

# Log réponse envoyée
log_response_sent(deal_id, crm_client, ticket_id, response_summary, case_handled)

# Log blocage modification date
log_exam_date_blocked(deal_id, crm_client, evalbox, date_cloture, action)
```

---

#### Détail CAS 9: Convocation CMA Reçue

**Condition:** `Evalbox = "Convoc CMA reçue"`

**Données utilisées:**
- `IDENTIFIANT_EVALBOX` (Deal) → Identifiant ExamT3P du candidat
- `MDP_EVALBOX` (Deal) → Mot de passe ExamT3P du candidat
- `Date_Examen` → Date de l'examen

**Message généré:**
```
Excellente nouvelle ! Votre convocation pour l'examen VTC du **15/03/2026** est maintenant disponible !

**Pour récupérer votre convocation :**

1. Connectez-vous sur la plateforme ExamT3P : **https://www.exament3p.fr**

**Vos identifiants de connexion :**
- Identifiant : **candidat@email.com**
- Mot de passe : **MotDePasse123**

2. Une fois connecté, téléchargez votre convocation officielle

3. **Imprimez votre convocation** - elle est obligatoire le jour de l'examen

**Le jour de l'examen, présentez-vous avec :**
- Votre convocation imprimée
- Une pièce d'identité en cours de validité (carte d'identité ou passeport)

Nous vous souhaitons bonne chance pour votre examen ! Nous restons à votre disposition si vous avez des questions.
```

#### Détail CAS 10: Prêt à Payer

**Condition:** `Evalbox = "Pret a payer"` ou `"Pret a payer par cheque"`

**Données utilisées:**
- `Date_Examen` → Date de l'examen prévue
- `Date_Cloture_Inscription` → Date limite pour corrections

**Message généré:**
```
Votre dossier est complet et prêt pour le paiement des frais d'examen !

Nous allons procéder au règlement des frais d'inscription dans les **prochaines heures/jours**.

**Ce qui va se passer ensuite :**

1. Une fois le paiement effectué, votre dossier sera transmis à la **CMA** pour instruction

2. La CMA va examiner vos pièces justificatives

3. **Important - Surveillez vos emails (et vos spams !)** : Si la CMA refuse certaines pièces, vous recevrez une notification par email

4. En cas de demande de correction, vous devrez nous transmettre les documents corrigés **avant le 01/03/2026**

**Attention :** Si les corrections ne sont pas apportées avant la date de clôture, votre inscription sera automatiquement reportée sur la prochaine session d'examen.
```

---

**Fonction principale:**
```python
from src.utils.date_examen_vtc_helper import analyze_exam_date_situation

result = analyze_exam_date_situation(
    deal_data=deal_data,
    threads=threads_data,
    crm_client=crm_client,
    examt3p_data=examt3p_data
)

# Résultat:
{
    'case': 1,  # Numéro du cas (1-8)
    'case_description': '...',
    'should_include_in_response': True,  # Ajouter à la réponse?
    'response_message': '...',  # Message à intégrer
    'next_dates': [...],  # Prochaines dates disponibles
    'date_cloture': '2026-02-15'
}
```

---

### 📚 Logique Sessions de Formation

**Fichier:** `src/utils/session_helper.py`

#### Règles Métier Essentielles

1. **Timing:** La session de formation doit se terminer **AVANT** la date d'examen
   - Minimum: 3 jours avant (MIN_DAYS_BEFORE_EXAM)
   - Maximum: 60 jours avant (MAX_DAYS_BEFORE_EXAM)

2. **Convention de nommage:**
   - `cdj-*` → **Cours Du Jour** (ex: "cdj-janvier-2026")
   - `cds-*` → **Cours Du Soir** (ex: "cds-janvier-2026")

3. **Filtrage Uber:** Seules les sessions avec `Lieu_de_formation` contenant "VISIO" ET "VTC" sont proposées (sessions partenariat Uber)

4. **Détection préférence jour/soir:**
   - Depuis le Deal: champs `Session` et `Session_souhait_e`
   - Depuis les threads: patterns comme "cours du soir", "en journée", "après travail"
   - Si préférence détectée → proposer uniquement ce type
   - Si aucune préférence → proposer les deux options

#### Fonction Principale

```python
from src.utils.session_helper import analyze_session_situation

session_data = analyze_session_situation(
    deal_data=deal_data,
    exam_dates=next_dates,  # Issues de date_examen_vtc_helper
    threads=threads_data,
    crm_client=crm_client
)

# Résultat:
{
    'session_preference': 'soir',  # ou 'jour', ou None
    'current_session': {...},  # Session actuelle du deal
    'current_session_is_past': False,  # Session terminée?
    'refresh_session_available': True,  # Rafraîchissement proposé?
    'refresh_session': {...},  # Détails session de rafraîchissement
    'proposed_options': [
        {
            'exam_info': {...},  # Date d'examen
            'sessions': [...]    # Sessions associées
        }
    ],
    'message': '...'  # Message formaté pour le candidat
}
```

#### Critères de Recherche Sessions

```python
# Critère API Zoho CRM (Sessions1/search):
criteria = (
    f"(((Statut:equals:PLANIFIÉ)or(Statut:equals:null))"
    f"and(Date_fin:greater_equal:{min_end_date})"  # Fin >= exam - 60j
    f"and(Date_fin:less_equal:{max_end_date})"      # Fin <= exam - 3j
    f"and(Date_d_but:greater_equal:{today}))"        # Début >= aujourd'hui
)

# Filtrage Python (après récupération):
if 'VISIO' in lieu_name.upper() and 'VTC' in lieu_name.upper():
    # C'est une session Uber → garder
```

---

### 🔄 Cas Spécial: Session de Rafraîchissement

**Condition:**
- Le candidat a DÉJÀ suivi une formation (session passée/terminée)
- Son examen est dans le FUTUR
- Une nouvelle session est disponible AVANT l'examen

**Action:** Proposer GRATUITEMENT de rejoindre la prochaine session pour rafraîchir ses connaissances

**Message type:**
```
📚 **PROPOSITION DE RAFRAÎCHISSEMENT (sans frais supplémentaires)**

Nous avons constaté que vous avez déjà suivi votre formation, mais votre examen est prévu pour le [DATE].

**Pour nous, votre réussite est notre priorité.** Plus vos connaissances sont fraîches au moment de l'examen, plus vos chances de succès sont élevées.

C'est pourquoi nous vous proposons, **sans aucun coût additionnel**, de rejoindre la prochaine session de formation pour rafraîchir vos acquis.
```

**Détection:**
```python
# Dans analyze_session_situation():
if result['current_session_is_past'] and result['proposed_options']:
    # Session passée + examen futur avec options disponibles
    result['refresh_session_available'] = True
    result['refresh_session'] = {...}  # Meilleure session trouvée
```

---

### ⚠️ Règle Critique: Lien Visio

**NE JAMAIS** dire "nous venons de vous envoyer un lien d'invitation" ou similaire SI:
- On propose **plusieurs dates d'examen** au choix
- On propose **plusieurs sessions de formation** au choix

**Le lien visio n'est envoyé QUE** quand:
- La date d'examen est **confirmée** (une seule date)
- ET la session de formation est **confirmée** (une seule session)

**Implémentation:** Règle ajoutée dans le system prompt de `response_generator_agent.py`

---

### 🔗 Chaîne de Dépendances Complète

```
1. Ticket DOC reçu
        ↓
2. Récupération Deal CRM
   ├── Date_examen_VTC
   ├── Evalbox
   ├── CMA_de_depot
   └── Session
        ↓
3. analyze_exam_date_situation()
   ├── Détermine le CAS (1-8)
   ├── Récupère next_dates (si besoin)
   └── Génère response_message (date examen)
        ↓
4. SI next_dates disponibles:
   └── analyze_session_situation()
       ├── Détecte préférence (deal + threads)
       ├── Cherche sessions AVANT chaque date d'examen
       ├── Filtre: VISIO Zoom VTC uniquement
       ├── Détecte si rafraîchissement possible
       └── Génère message complet (dates + sessions)
        ↓
5. ResponseGeneratorAgent
   ├── Reçoit date_examen_result
   ├── Reçoit session_data
   └── Intègre dans la réponse
        ↓
6. Réponse finale au candidat
   ├── Dates d'examen proposées
   ├── Sessions de formation associées
   ├── Message rafraîchissement (si applicable)
   └── Demande de confirmation préférence
```

---

### 📝 Exemple de Réponse Générée

```
📅 **Examen du 15/03/2026** (clôture inscriptions: 01/03/2026)
   Sessions de formation disponibles :
   • **Cours du jour** : du 24/02/2026 au 28/02/2026
   • **Cours du soir** : du 17/02/2026 au 07/03/2026

📅 **Examen du 29/03/2026** (clôture inscriptions: 15/03/2026)
   Sessions de formation disponibles :
   • **Cours du jour** : du 10/03/2026 au 14/03/2026
   • **Cours du soir** : du 03/03/2026 au 21/03/2026

Merci de nous indiquer votre préférence (cours du jour ou cours du soir) ainsi que la date d'examen qui vous convient.
```

---

### 🧪 Tests et Validation

**Scripts de test:**
- `test_doc_workflow_with_examt3p.py` → Test complet workflow DOC avec dates
- `list_recent_tickets.py` → Trouver des tickets de test

**Logs à vérifier:**
```
🔍 Analyse de la situation date d'examen VTC...
  Date_examen_VTC: {...}
  Evalbox: VALIDE CMA
  CMA_de_depot: CMA 75 (département: 75)
  ➡️ CAS 4: Date future + VALIDE CMA

🔍 Analyse de la situation session de formation...
  Session actuelle: cds-janvier-2026
  Préférence détectée: soir
  ✅ 2 session(s) sélectionnée(s) pour l'examen du 2026-03-15
```

---

## 🧵 ANALYSE DE L'HISTORIQUE DES THREADS (SESSION JAN 2026)

### Contexte

Le système doit analyser **TOUT l'historique de conversation**, pas seulement le dernier message du candidat. Cela permet de:
- Ne pas répéter des informations déjà communiquées
- Détecter si on a déjà demandé les identifiants/la création de compte
- Adapter le ton selon le nombre d'échanges précédents
- Tenir compte des préférences déjà exprimées

### Implémentation

**Fichier:** `src/agents/response_generator_agent.py`

**Méthode:** `_format_thread_history(threads)`

```python
def _format_thread_history(self, threads: Optional[List]) -> str:
    """
    Formate l'historique complet des échanges pour le prompt.
    Affiche chronologiquement tous les messages (entrants et sortants).
    """
    # Format:
    # ### Échange #1 (25/01/2026 10:30)
    # **📩 CANDIDAT** :
    # [contenu du message]
    #
    # ### Échange #2 (25/01/2026 14:45)
    # **📤 NOUS (Cab Formations)** :
    # [contenu de notre réponse]
```

**Passage dans le workflow:**
- `doc_ticket_workflow.py` → `analysis_result['threads']`
- `response_generator_agent.py` → Paramètre `threads` dans toutes les méthodes de génération

---

## 🔐 DÉTECTION DEMANDES D'IDENTIFIANTS/COMPTE DANS L'HISTORIQUE

### Objectif

Détecter si nous avons déjà demandé:
1. Les **identifiants ExamT3P** au candidat
2. De **créer un compte** ExamT3P

Et adapter la réponse en conséquence (ne pas re-demander de la même façon, être plus direct).

### Fichier: `src/utils/examt3p_credentials_helper.py`

**Fonctions:**

| Fonction | Description |
|----------|-------------|
| `detect_credentials_request_in_history(threads)` | Détecte si on a déjà demandé les identifiants |
| `detect_account_creation_request_in_history(threads)` | Détecte si on a demandé de créer un compte |
| `detect_session_preference_in_threads(threads)` | Détecte préférence cours jour/soir |

### Patterns Détectés

**Messages SORTANTS (de nous vers le candidat):**
```python
outgoing_patterns = [
    r'transmettre\s+vos\s+identifiants',
    r'communiquer\s+vos\s+identifiants',
    r'envoyer\s+vos\s+identifiants',
    r'identifiants\s+de\s+connexion',
    r'créer\s+(?:votre\s+)?compte',
    r's[\'']inscrire\s+sur\s+exament3p',
]
```

**Messages ENTRANTS (du candidat):**
```python
incoming_patterns = [
    r're[çc]u\s+un\s+mail.*demande.*identifiants',
    r'vous\s+(?:m\'avez|avez)\s+demandé\s+mes\s+identifiants',
    r'est-ce\s+(?:que\s+c\'est\s+)?normal.*identifiants',
]
```

### Adaptation de la Réponse

| Nombre de demandes | Ton de la réponse |
|--------------------|-------------------|
| 0 (première fois) | Expliquer pourquoi + demander poliment |
| 1 (2ème demande) | Reconnaître la situation + recommander réinitialisation |
| ≥2 (3ème+ demande) | Ton plus direct + insister sur vérification avant envoi |

---

## ⚠️ COHÉRENCE FORMATION / EXAMEN (CRITIQUE)

### Le Problème

Le système proposait parfois des dates de **formation APRÈS la date d'examen**, ce qui est illogique.

**Exemple bugué:**
- Examen: 27/01/2026
- Formation proposée: 09/02/2026 au 20/02/2026 ❌

### Solution: Helper de Cohérence

**Fichier:** `src/utils/training_exam_consistency_helper.py`

#### Détection du Cas Critique

**Conditions:**
1. Candidat mentionne avoir **manqué sa formation** (patterns détectés)
2. Date d'examen est **imminente** (≤ 14 jours)

#### Les 2 Options à Proposer

| Option | Description | Condition |
|--------|-------------|-----------|
| **A** | Maintenir l'examen | E-learning considéré suffisant |
| **B** | Reporter l'examen | **Justificatif de force majeure OBLIGATOIRE** |

### Règles Métier Cruciales

#### 🔒 Force Majeure = Seul Motif de Report

**CE QUI EST UN MOTIF VALABLE:**
- Certificat médical **couvrant le jour de l'examen**
- Décès d'un proche
- Accident
- Convocation judiciaire

**CE QUI N'EST PAS UN MOTIF VALABLE:**
- Ne pas avoir suivi la formation ❌
- Certificat médical couvrant uniquement la période de formation ❌
- "Pas prêt" / "Pas eu le temps de réviser" ❌

#### 🏛️ CMA vs Formation

| Entité | Gère | Ne gère PAS |
|--------|------|-------------|
| **CMA** (Chambre des Métiers) | Examens, inscriptions, reports | Formation |
| **CAB Formations** | Formation (visio, e-learning) | Décision de report |

**Conséquence:** Le justificatif de force majeure doit couvrir **le jour de l'EXAMEN**, pas la période de formation.

#### 📚 E-learning = Suffisant

La formation en visioconférence est un **complément**, pas une obligation. Le candidat peut passer l'examen s'il a suivi le e-learning uniquement.

### Message Type Généré

```
Bonjour,

Nous avons bien pris connaissance de votre message concernant la formation.

**⚠️ Information importante : Vous êtes inscrit(e) à l'examen VTC du 27/01/2026.**

La formation en visioconférence et le e-learning sont des outils de préparation,
mais votre inscription à l'examen est déjà validée auprès de la CMA.

Vous avez deux possibilités :

---

## Option A : Maintenir votre examen au 27/01/2026

Si le e-learning vous a permis d'acquérir les connaissances nécessaires,
vous pouvez passer l'examen à la date prévue.

La formation en visioconférence est un complément, mais n'est pas obligatoire.

---

## Option B : Reporter votre examen

**Un justificatif de force majeure couvrant la date du 27/01/2026 est obligatoire.**

⚠️ Le certificat médical doit couvrir **le jour de l'examen** (27/01/2026),
pas seulement la période de la formation.

En cas de report accepté, vous serez repositionné(e) sur le 15/03/2026.

⚠️ **Important** : Le simple fait de ne pas avoir suivi la formation
n'est **pas** un motif valable de report auprès de la CMA.

---

**Merci de nous indiquer votre choix.**

Cordialement,
L'équipe Cab Formations
```

### Fonctions Principales

```python
from src.utils.training_exam_consistency_helper import (
    analyze_training_exam_consistency,
    detect_missed_training_in_threads,
    detect_force_majeure_in_threads,
    get_next_exam_date_after,
    generate_training_exam_options_message,
    check_session_dates_consistency
)

# Analyse complète
result = analyze_training_exam_consistency(
    deal_data=deal_data,
    threads=threads_data,
    session_data=session_data,
    crm_client=crm_client
)

# Résultat:
{
    'has_consistency_issue': True,
    'issue_type': 'MISSED_TRAINING_IMMINENT_EXAM',
    'exam_date': '2026-01-27',
    'exam_date_formatted': '27/01/2026',
    'next_exam_date': '2026-03-15',
    'next_exam_date_formatted': '15/03/2026',
    'force_majeure_detected': True,
    'force_majeure_type': 'medical',
    'should_present_options': True,
    'response_message': '...',
    'options': [
        {'id': 'A', 'title': "Maintenir l'examen", ...},
        {'id': 'B', 'title': "Reporter l'examen", ...}
    ]
}
```

### Intégration Workflow

**Fichier:** `src/workflows/doc_ticket_workflow.py`

L'analyse est effectuée **APRÈS** l'analyse de la date d'examen et **AVANT** la génération de réponse:

```
1. Validation identifiants ExamT3P
2. Analyse date examen VTC (date_examen_vtc_helper)
3. ⭐ Vérification cohérence formation/examen (training_exam_consistency_helper)
4. Analyse sessions de formation (session_helper)
5. Génération de la réponse
```

**Si `has_consistency_issue = True`:**
- Le système utilise **directement le message pré-généré** avec les options A/B
- Pas d'appel à Claude pour cette partie (message déterministe)
- Évite de proposer des dates de formation incohérentes

---

## 📝 RÉCAPITULATIF DES HELPERS CRÉÉS (SESSION JAN 2026)

| Helper | Fichier | Rôle |
|--------|---------|------|
| **Credentials** | `examt3p_credentials_helper.py` | Validation identifiants, détection historique |
| **Date Examen** | `date_examen_vtc_helper.py` | 10 cas de gestion date examen |
| **Sessions** | `session_helper.py` | Proposition sessions, rafraîchissement |
| **Uber Eligibility** | `uber_eligibility_helper.py` | Vérification prérequis Uber 20€ |
| **Training/Exam Consistency** | `training_exam_consistency_helper.py` | Cohérence formation/examen, options A/B |
| **CRM Sync** | `examt3p_crm_sync.py` | Sync ExamT3P → CRM |
| **CRM Note Logger** | `crm_note_logger.py` | Logging notes CRM |
| **Ticket Info Extractor** | `ticket_info_extractor.py` | Extraction confirmations ticket |

---

**Dernière mise à jour:** 2026-01-25
**Version Claude.md:** 1.3
**Généré par:** Claude Opus 4.5 (Anthropic)
