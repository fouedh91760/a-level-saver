# Zia Agent - CAB Formations Ticket Handler

## Vue d'ensemble

Ce dossier contient la configuration complète pour déployer un agent Zia qui reproduit la logique du système a-level-saver pour le traitement automatique des tickets Zoho Desk.

L'agent est capable de :
- **Analyser** le contenu des tickets entrants
- **Identifier** le contact et ses formations dans Zoho CRM
- **Détecter** l'état du candidat (38 états possibles)
- **Comprendre** l'intention du candidat (37 intentions)
- **Générer** des réponses appropriées selon la matrice ÉTAT × INTENTION
- **Mettre à jour** le CRM (contact et deal)
- **Router** les tickets vers le bon département

---

## Structure du dossier

```
zia-agent/
├── README.md                      # Ce fichier
├── agent_instructions_cab.md      # Instructions complètes de l'agent (prompt)
├── tools/                         # Configurations des outils API
│   ├── getLatestThread.yaml       # Lire le dernier message du ticket
│   ├── searchContactByEmail.yaml  # Rechercher un contact dans le CRM
│   ├── getRelatedDeals.yaml       # Récupérer les deals d'un contact
│   ├── getExamT3PData.yaml        # Récupérer les données ExamT3P
│   ├── getAvailableSessions.yaml  # Récupérer les sessions disponibles
│   ├── sendEmailReply.yaml        # Envoyer une réponse email
│   ├── updateContact.yaml         # Mettre à jour un contact CRM
│   ├── updateDeal.yaml            # Mettre à jour un deal CRM
│   └── moveTicket.yaml            # Déplacer un ticket
└── deluge/                        # Scripts Deluge pour l'intégration
    ├── workflow_trigger.ds        # Script principal du workflow
    └── custom_function_simple.ds  # Version simplifiée
```

---

## Guide de Configuration

### Étape 1 : Créer les Connexions API

Dans **Zoho Desk > Setup > Developer Space > Connections**, créez :

| Connexion | Service | Scopes |
|-----------|---------|--------|
| `zohodesk` | Zoho Desk | Desk.tickets.READ, Desk.tickets.UPDATE |
| `zohocrm` | Zoho CRM | ZohoCRM.modules.contacts.READ/UPDATE, ZohoCRM.modules.deals.READ/UPDATE |
| `ziaagents` | Zoho OAuth (Self-Client) | Zia.Agents.EXECUTE |

### Étape 2 : Créer l'Agent dans Zia Agents

1. Connectez-vous à [https://ziaagents.zoho.eu](https://ziaagents.zoho.eu)
2. Créez un nouvel agent :
   - **Nom** : `CAB Ticket Handler`
   - **Modèle IA** : OpenAI GPT-4o-mini
   - **Instructions** : Copiez le contenu de `agent_instructions_cab.md`

### Étape 3 : Configurer les Outils

Dans l'interface de l'agent, créez un **Tool Group** nommé `CAB Tools` et importez chaque fichier `.yaml` du dossier `tools/`.

**Liste des outils** :
1. `getLatestThread` - Lire le dernier thread du ticket
2. `searchContactByEmail` - Rechercher un contact par email
3. `getRelatedDeals` - Récupérer les deals d'un contact
4. `getExamT3PData` - Récupérer les données ExamT3P
5. `getAvailableSessions` - Récupérer les sessions disponibles
6. `sendEmailReply` - Envoyer une réponse email
7. `updateContact` - Mettre à jour un contact
8. `updateDeal` - Mettre à jour un deal
9. `moveTicket` - Déplacer un ticket

### Étape 4 : Déployer l'Agent

Cliquez sur **Deploy** et notez les IDs :
- `Organization ID`
- `Agent ID`
- `Agent Version ID`

### Étape 5 : Configurer le Workflow Zoho Desk

1. Allez dans **Zoho Desk > Setup > Automation > Workflow Rules**
2. Créez une règle sur le module **Tickets**
3. Ajoutez une **Custom Function** avec le code de `deluge/workflow_trigger.ds`
4. Remplacez les IDs par ceux obtenus à l'étape 4

---

## Logique Métier Intégrée

### États Uber (Offre 20€)

| État | Condition | Action |
|------|-----------|--------|
| UBER_CAS_A | Documents non envoyés | Demander les documents |
| UBER_CAS_B | Test de sélection non passé | Demander de passer le test |
| UBER_CAS_D | Compte Uber non vérifié | Contacter Uber |
| UBER_CAS_E | Non éligible Uber | Contacter Uber |
| DUPLICATE_UBER | 2+ offres 20€ utilisées | Proposer alternatives |

### Règles Critiques

1. **Blocage modification date** : Ne jamais modifier `Date_examen_VTC` si Evalbox = "VALIDE CMA" ou "Convoc CMA reçue" et date de clôture passée.

2. **Offre Uber unique** : L'offre 20€ n'est valable qu'une seule fois par candidat.

3. **Date_test_selection READ-ONLY** : Ce champ est mis à jour uniquement par webhook.

### Mapping des Départements

| Département | ID | Usage |
|-------------|-----|-------|
| Contact | 799478000000006907 | Nouvelles inscriptions |
| Pédagogie | 799478000001601380 | Questions e-learning |
| DOC | 799478000004394715 | Documents administratifs |
| Back-Office | 799478000001594039 | Questions admin |

---

## Tests

Pour tester l'agent :

1. Envoyez un email de test à votre adresse de support
2. Vérifiez les logs dans **Zoho Desk > Setup > History > Workflow History**
3. Consultez les logs de la fonction Deluge pour le débogage

### Scénarios de test recommandés

- [ ] Nouveau candidat (contact non trouvé)
- [ ] Candidat Uber CAS A (documents manquants)
- [ ] Candidat Uber CAS B (test non passé)
- [ ] Demande d'identifiants ExamT3P
- [ ] Demande de dates d'examen
- [ ] Confirmation de session
- [ ] Demande de report
- [ ] Doublon offre Uber

---

## Maintenance

### Mise à jour des instructions

Si vous modifiez les règles métier dans le projet a-level-saver, mettez à jour le fichier `agent_instructions_cab.md` en conséquence.

### Ajout de nouveaux scénarios

1. Ajoutez le scénario dans `agent_instructions_cab.md`
2. Créez le template de réponse correspondant
3. Redéployez l'agent

---

## Support

Pour toute question, consultez :
- Documentation Zia Agents : [help.zoho.com](https://help.zoho.com)
- Documentation a-level-saver : `docs/` dans ce repository
