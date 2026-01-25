# Claude.md - A-Level Saver Project Context

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

**Dernière mise à jour:** 2026-01-25
**Version Claude.md:** 1.1
**Généré par:** Claude 3.5 Sonnet (Anthropic)
