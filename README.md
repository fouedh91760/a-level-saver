# A-Level Saver - Automatisation Zoho Desk & CRM

Système d'agents IA pour automatiser la gestion des tickets Zoho Desk et la mise à jour des opportunités Zoho CRM pour un service d'orientation A-Level.

## 🎯 Fonctionnalités

### Agent Zoho Desk
- ✅ Analyse automatique des tickets de support
- ✅ Génération de réponses personnalisées et empathiques
- ✅ Détection automatique des cas nécessitant une escalade
- ✅ Mise à jour automatique des statuts de tickets
- ✅ Traitement par lots de multiples tickets

### Agent Zoho CRM
- ✅ Analyse de la santé des opportunités
- ✅ Recommandations de prochaines étapes
- ✅ Mise à jour automatique des champs d'opportunité
- ✅ Détection des opportunités nécessitant attention
- ✅ Scoring automatique de priorité

### Orchestrateur
- ✅ Coordination entre tickets et opportunités CRM
- ✅ Workflows automatisés complexes
- ✅ Traitement planifié (cron-ready)
- ✅ Reporting et monitoring

## 🚀 Démarrage rapide

### Installation

```bash
# Cloner le repository
git clone <repository-url>
cd a-level-saver

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditez .env avec vos credentials Zoho et Anthropic
```

### Configuration

1. **Obtenir les credentials Zoho** (voir [GUIDE.md](GUIDE.md#configuration))
2. **Obtenir une clé API Anthropic** sur https://console.anthropic.com
3. **Remplir le fichier .env** avec vos credentials

### Premier test

```bash
# Test de l'agent Desk
python examples/basic_ticket_processing.py

# Test de l'agent CRM
python examples/crm_opportunity_management.py

# Test du workflow complet
python examples/full_workflow_orchestration.py
```

## 📖 Documentation

- **[GUIDE.md](GUIDE.md)** - Guide complet d'utilisation
- **[WEBHOOK_QUICKSTART.md](WEBHOOK_QUICKSTART.md)** - 🚀 Démarrer le webhook en 5 minutes
- **[WEBHOOK_SETUP.md](WEBHOOK_SETUP.md)** - Configuration complète du webhook
- **[examples/](examples/)** - Exemples de code

## 🔔 Webhook Automation (Nouveau !)

Le système peut maintenant être déclenché automatiquement via webhook Zoho Desk :

```bash
# 1. Démarrer le serveur webhook
python webhook_server.py

# 2. Tester localement
python test_webhook.py --test simple

# 3. Exposer avec ngrok (pour tests)
ngrok http 5000
```

**Configuration Zoho Desk :**
1. Setup → Automation → Webhooks → Add Webhook
2. URL : `https://votre-domaine.com/webhook/zoho-desk`
3. Events : "Ticket Created", "Ticket Updated"
4. Configurer le secret HMAC dans `.env`

**Guide rapide :** [WEBHOOK_QUICKSTART.md](WEBHOOK_QUICKSTART.md)

## 🏗️ Architecture

```
a-level-saver/
├── src/
│   ├── agents/
│   │   ├── base_agent.py        # Classe de base pour les agents IA
│   │   ├── desk_agent.py        # Agent Zoho Desk
│   │   └── crm_agent.py         # Agent Zoho CRM
│   ├── zoho_client.py           # Clients API Zoho (Desk & CRM)
│   └── orchestrator.py          # Orchestrateur de workflows
├── examples/
│   ├── basic_ticket_processing.py
│   ├── crm_opportunity_management.py
│   ├── full_workflow_orchestration.py
│   └── scheduled_automation.py
├── config.py                    # Configuration centralisée
├── requirements.txt             # Dépendances Python
└── GUIDE.md                    # Documentation complète
```

## 💡 Cas d'usage

### 1. Support client automatisé
```python
from src.agents import DeskTicketAgent

agent = DeskTicketAgent()
result = agent.process({
    "ticket_id": "123456789",
    "auto_respond": True,
    "auto_update": True
})
```

### 2. Gestion des opportunités
```python
from src.agents import CRMOpportunityAgent

agent = CRMOpportunityAgent()
result = agent.process({
    "deal_id": "987654321",
    "auto_update": True,
    "auto_add_note": True
})
```

### 3. Workflow intégré
```python
from src.orchestrator import ZohoAutomationOrchestrator

orchestrator = ZohoAutomationOrchestrator()
result = orchestrator.process_ticket_with_crm_update(
    ticket_id="123456789",
    deal_id="987654321",
    auto_respond=True,
    auto_update_deal=True
)
```

## 🔧 Technologies utilisées

- **Python 3.9+**
- **Anthropic Claude** - Agent IA pour l'analyse et les recommandations
- **Zoho Desk API** - Gestion des tickets de support
- **Zoho CRM API** - Gestion des opportunités
- **OAuth2** - Authentification sécurisée

## 📊 Fonctionnalités avancées

- **Retry automatique** avec backoff exponentiel
- **Gestion du cache de tokens** OAuth2
- **Logs structurés** pour monitoring
- **Historique de conversation** pour contexte IA
- **Traitement par lots** optimisé
- **Workflows personnalisables**

## 🔒 Sécurité

- Authentification OAuth2 avec refresh tokens
- Variables d'environnement pour les secrets
- Validation des entrées
- Gestion sécurisée des erreurs

## 🤝 Contribution

Les contributions sont les bienvenues ! Consultez le guide de contribution pour plus d'informations.

## 📄 Licence

[À définir]

## 📞 Support

Pour plus d'informations, consultez le [GUIDE.md](GUIDE.md) ou ouvrez une issue.
