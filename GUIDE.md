# Guide d'utilisation - Automatisation Zoho Desk & CRM

Ce guide vous explique comment utiliser le système d'agents IA pour automatiser vos tickets Zoho Desk et la mise à jour de vos opportunités Zoho CRM.

## 📋 Table des matières

- [Installation](#installation)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Utilisation](#utilisation)
- [Exemples](#exemples)
- [Automatisation planifiée](#automatisation-planifiée)

## 🚀 Installation

### Prérequis

- Python 3.9 ou supérieur
- Compte Zoho Desk avec accès API
- Compte Zoho CRM avec accès API
- Clé API Anthropic (Claude)

### Installation des dépendances

```bash
# Installer les dépendances Python
pip install -r requirements.txt

# Copier le fichier de configuration exemple
cp .env.example .env
```

## ⚙️ Configuration

### 1. Obtenir les credentials Zoho

#### OAuth2 pour Zoho

1. Allez sur https://api-console.zoho.com/
2. Créez une application "Self Client"
3. Notez votre `Client ID` et `Client Secret`
4. Générez un code d'autorisation avec les scopes suivants :
   - `Desk.tickets.ALL`
   - `Desk.contacts.READ`
   - `ZohoCRM.modules.ALL`
5. Échangez le code contre un refresh token :

```bash
curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
  -d "code=YOUR_AUTH_CODE" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "grant_type=authorization_code"
```

6. Notez le `refresh_token` retourné

### 2. Configuration du fichier .env

Éditez le fichier `.env` avec vos credentials :

```env
# Zoho API Configuration
ZOHO_CLIENT_ID=votre_client_id
ZOHO_CLIENT_SECRET=votre_client_secret
ZOHO_REFRESH_TOKEN=votre_refresh_token
ZOHO_DATACENTER=com  # ou eu, in, com.au selon votre région

# Zoho Desk Configuration
ZOHO_DESK_ORG_ID=votre_org_id

# Anthropic API
ANTHROPIC_API_KEY=votre_cle_anthropic

# Configuration des agents (optionnel)
AGENT_MODEL=claude-3-5-sonnet-20241022
AGENT_MAX_TOKENS=4096
AGENT_TEMPERATURE=0.7

# Logging
LOG_LEVEL=INFO
```

## 🏗️ Architecture

Le système est composé de plusieurs couches :

### 1. Clients API (`src/zoho_client.py`)

- **ZohoAPIClient** : Gestion de l'authentification OAuth2
- **ZohoDeskClient** : Opérations sur les tickets Zoho Desk
- **ZohoCRMClient** : Opérations sur les opportunités Zoho CRM

### 2. Agents IA (`src/agents/`)

- **BaseAgent** : Classe de base pour tous les agents
- **DeskTicketAgent** : Agent spécialisé pour les tickets
  - Analyse automatique des tickets
  - Génération de réponses personnalisées
  - Détection des cas nécessitant une escalade
- **CRMOpportunityAgent** : Agent spécialisé pour les opportunités
  - Analyse de la santé des opportunités
  - Recommandations de prochaines étapes
  - Détection des opportunités nécessitant attention

### 3. Orchestrateur (`src/orchestrator.py`)

Coordonne les agents pour des workflows complexes :
- Traitement de tickets avec mise à jour CRM
- Traitement par lots
- Détection d'opportunités en attente
- Cycles d'automatisation complets

## 📖 Utilisation

### Utilisation de base - Agent Desk

```python
from src.agents import DeskTicketAgent

# Initialiser l'agent
agent = DeskTicketAgent()

# Analyser un ticket
result = agent.process({
    "ticket_id": "123456789",
    "auto_respond": False,  # True pour répondre automatiquement
    "auto_update": False    # True pour mettre à jour le statut
})

# Afficher l'analyse
print(f"Priorité: {result['agent_analysis']['priority']}")
print(f"Réponse suggérée: {result['agent_analysis']['suggested_response']}")
```

### Utilisation de base - Agent CRM

```python
from src.agents import CRMOpportunityAgent

# Initialiser l'agent
agent = CRMOpportunityAgent()

# Analyser une opportunité
result = agent.process({
    "deal_id": "987654321",
    "auto_update": False,   # True pour appliquer les mises à jour
    "auto_add_note": False  # True pour ajouter des notes
})

# Afficher l'analyse
print(f"Score de priorité: {result['agent_analysis']['priority_score']}/10")
print(f"Prochaines étapes: {result['agent_analysis']['suggested_next_steps']}")
```

### Utilisation avancée - Orchestrateur

```python
from src.orchestrator import ZohoAutomationOrchestrator

# Initialiser l'orchestrateur
orchestrator = ZohoAutomationOrchestrator()

# Traiter un ticket et mettre à jour l'opportunité associée
result = orchestrator.process_ticket_with_crm_update(
    ticket_id="123456789",
    deal_id="987654321",
    auto_respond=True,
    auto_update_ticket=True,
    auto_update_deal=True,
    auto_add_note=True
)
```

## 💡 Exemples

Plusieurs exemples sont disponibles dans le dossier `examples/` :

### 1. Traitement basique de tickets
```bash
python examples/basic_ticket_processing.py
```

Montre comment :
- Analyser un ticket individuel
- Répondre automatiquement
- Traiter plusieurs tickets en lot

### 2. Gestion des opportunités CRM
```bash
python examples/crm_opportunity_management.py
```

Montre comment :
- Analyser une opportunité
- Appliquer les recommandations automatiquement
- Trouver les opportunités nécessitant attention
- Traiter une opportunité avec contexte de ticket

### 3. Orchestration complète
```bash
python examples/full_workflow_orchestration.py
```

Montre comment :
- Coordonner ticket et CRM
- Exécuter un cycle complet
- Lier tickets et opportunités

### 4. Automatisation planifiée
```bash
python examples/scheduled_automation.py
```

Script prêt pour cron/planification qui :
- Traite automatiquement les nouveaux tickets
- Met à jour les opportunités en attente
- Génère des rapports

## ⏰ Automatisation planifiée

### Configuration avec cron (Linux/Mac)

Ajoutez cette ligne à votre crontab (`crontab -e`) :

```bash
# Exécuter toutes les heures
0 * * * * cd /path/to/a-level-saver && /usr/bin/python3 examples/scheduled_automation.py >> logs/automation.log 2>&1

# Exécuter toutes les 30 minutes
*/30 * * * * cd /path/to/a-level-saver && /usr/bin/python3 examples/scheduled_automation.py >> logs/automation.log 2>&1
```

### Configuration avec Task Scheduler (Windows)

1. Ouvrir Task Scheduler
2. Créer une tâche de base
3. Déclencher : Quotidien, toutes les heures
4. Action : Démarrer un programme
   - Programme : `python.exe`
   - Arguments : `examples/scheduled_automation.py`
   - Répertoire : `C:\path\to\a-level-saver`

### Logs et monitoring

Les logs sont écrits dans `automation.log`. Pour surveiller en temps réel :

```bash
tail -f automation.log
```

## 🎯 Cas d'usage courants

### 1. Support client automatisé

Traiter automatiquement les tickets de support simples :

```python
agent = DeskTicketAgent()
result = agent.process({
    "ticket_id": "123",
    "auto_respond": True,  # Répond automatiquement
    "auto_update": True    # Ferme le ticket si résolu
})
```

### 2. Suivi des ventes

Maintenir à jour vos opportunités :

```python
orchestrator = ZohoAutomationOrchestrator()
result = orchestrator.find_and_update_stale_opportunities(
    days_stale=7,
    auto_update=True,
    auto_add_note=True
)
```

### 3. Intégration support-ventes

Mettre à jour les opportunités quand un client contacte le support :

```python
orchestrator = ZohoAutomationOrchestrator()
result = orchestrator.process_ticket_with_crm_update(
    ticket_id="123",
    deal_id="456",
    auto_respond=True,
    auto_update_deal=True
)
```

## 🔧 Personnalisation

### Modifier le comportement des agents

Les prompts système des agents peuvent être personnalisés dans :
- `src/agents/desk_agent.py` : SYSTEM_PROMPT
- `src/agents/crm_agent.py` : SYSTEM_PROMPT

### Ajouter des champs personnalisés

Modifiez les méthodes `process()` pour inclure vos champs personnalisés Zoho.

### Créer de nouveaux agents

Héritez de `BaseAgent` et implémentez la méthode `process()` :

```python
from src.agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="MyAgent",
            system_prompt="Votre prompt personnalisé"
        )

    def process(self, data):
        # Votre logique ici
        pass
```

## 📊 Monitoring et reporting

### Logs structurés

Les logs incluent :
- Timestamp
- Nom de l'agent
- Niveau (INFO, WARNING, ERROR)
- Message détaillé

### Métriques clés

- Nombre de tickets traités
- Taux d'escalade
- Nombre d'opportunités mises à jour
- Score de priorité moyen

## ❓ Dépannage

### Erreur d'authentification

Vérifiez :
- Que votre `refresh_token` est valide
- Que les scopes OAuth sont corrects
- Que le datacenter est correct (com, eu, etc.)

### Timeout API

Augmentez le timeout dans `src/zoho_client.py` si nécessaire.

### Erreurs de parsing JSON

Les agents doivent retourner du JSON valide. Si ce n'est pas le cas, ajustez le prompt système.

## 🔒 Sécurité

- Ne commitez JAMAIS votre fichier `.env`
- Utilisez des tokens avec les permissions minimales nécessaires
- Revoyez régulièrement les logs pour détecter les anomalies
- Limitez l'auto-action sur les environnements de production

## 📚 Ressources

- [Documentation API Zoho Desk](https://desk.zoho.com/support/APIDocument.do)
- [Documentation API Zoho CRM](https://www.zoho.com/crm/developer/docs/api/v3/)
- [Documentation Anthropic Claude](https://docs.anthropic.com/)
- [OAuth2 Zoho](https://www.zoho.com/accounts/protocol/oauth.html)
