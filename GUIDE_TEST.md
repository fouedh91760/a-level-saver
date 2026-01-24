# Guide de test avec de vrais tickets Zoho

Ce guide vous explique comment tester le système d'automatisation avec vos vrais tickets Zoho.

## Prérequis

### 1. Configuration Zoho

Vous avez besoin de :

1. **Client ID et Client Secret Zoho**
   - Allez sur https://api-console.zoho.com/
   - Créez une "Self Client"
   - Notez le Client ID et Client Secret

2. **Refresh Token**
   - Générez un refresh token avec les scopes suivants :
     - `Desk.tickets.ALL`
     - `Desk.contacts.READ`
     - `ZohoCRM.modules.ALL`
   - URL de génération : https://accounts.zoho.com/oauth/v2/auth
   - Paramètres :
     ```
     scope=Desk.tickets.ALL,Desk.contacts.READ,ZohoCRM.modules.ALL
     client_id=VOTRE_CLIENT_ID
     response_type=code
     access_type=offline
     redirect_uri=https://www.zoho.com
     ```

3. **Organization ID (Desk)**
   - Trouvez votre Org ID dans Zoho Desk → Setup → Developer Space → API

4. **Clé API Anthropic**
   - Créez un compte sur https://console.anthropic.com/
   - Générez une API key dans Settings → API Keys
   - Le modèle utilisé : `claude-3-5-sonnet-20241022`

### 2. Fichier .env

Créez un fichier `.env` à la racine du projet :

```bash
cp .env.example .env
```

Puis éditez `.env` avec vos vraies credentials :

```bash
# Zoho API Configuration
ZOHO_CLIENT_ID=1000.XXXXXXXXXXXXXXXXXXXXX
ZOHO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ZOHO_REFRESH_TOKEN=1000.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ZOHO_DATACENTER=com  # ou eu, in, com.au selon votre région

# Zoho Desk Configuration
ZOHO_DESK_ORG_ID=12345678

# Anthropic API
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Configuration des agents (optionnel - valeurs par défaut)
AGENT_MODEL=claude-3-5-sonnet-20241022
AGENT_MAX_TOKENS=4096
AGENT_TEMPERATURE=0.7

# Logging
LOG_LEVEL=INFO
```

### 3. Installation des dépendances

```bash
pip install -r requirements.txt
```

## Tests progressifs

### Étape 1 : Test de connexion

Vérifiez que la connexion Zoho fonctionne :

```bash
python test_with_real_tickets.py
```

Choisissez l'option "0" pour démarrer le test de connexion automatique.

Si ça échoue :
- Vérifiez vos credentials dans `.env`
- Vérifiez que le refresh token est valide
- Vérifiez le datacenter (com, eu, in, etc.)

### Étape 2 : Test du Dispatcher (1 ticket)

**Mode READ-ONLY** - Ne modifie rien, analyse seulement.

```bash
python test_with_real_tickets.py
```

Choisissez l'option **1** et entrez un ID de ticket.

**Ce que ça fait :**
- Récupère le ticket
- Analyse le département actuel vs recommandé
- Affiche la confiance et le raisonnement
- **N'effectue AUCUNE modification**

**Exemple de résultat :**
```
Département actuel : Sales
Département recommandé : DOC
Confiance : 95%
Raison : Keywords "uber", "student" found

⚠️ RECOMMANDATION : Réaffecter vers DOC
```

### Étape 3 : Test du Dispatcher (batch)

**Mode READ-ONLY** - Analyse 20 tickets ouverts.

```bash
python test_with_real_tickets.py
```

Choisissez l'option **2**.

**Ce que ça fait :**
- Récupère les 20 premiers tickets ouverts
- Analyse chacun
- Affiche un résumé des tickets mal affectés

**Intérêt :**
- Voir combien de tickets sont mal affectés
- Identifier les patterns
- Ajuster les règles de routing dans `business_rules.py` si nécessaire

### Étape 4 : Test du Deal Linking (1 ticket)

**Mode READ-ONLY** - Cherche le deal sans créer de lien.

```bash
python test_with_real_tickets.py
```

Choisissez l'option **3** et entrez un ID de ticket.

**Ce que ça fait :**
- Essaie de trouver un deal avec les stratégies configurées :
  1. `custom_field` (si cf_deal_id existe déjà)
  2. `department_specific` (logique DOC : Uber €20, Won → Pending → Lost)
  3. `contact_email`
  4. `contact_phone`
  5. `account`
  6. `recent_deal`
- Affiche le deal trouvé (si trouvé)
- Affiche la stratégie qui a fonctionné
- **Ne crée PAS le lien bidirectionnel**

**Exemple de résultat :**
```
✅ Deal trouvé !
Deal ID : 5844913000001234567
Deal Name : Uber A-Level Programme - €20
Stratégie utilisée : department_specific
```

### Étape 5 : Workflow complet (READ-ONLY)

**Mode READ-ONLY** - Teste les 4 étapes sans modification.

```bash
python test_with_real_tickets.py
```

Choisissez l'option **4** et entrez un ID de ticket.

**Ce que ça fait :**
1. **Dispatcher** : Analyse le département (pas de réaffectation)
2. **Deal Linking** : Cherche le deal (pas de lien créé)
3. **Desk Agent** : Génère une réponse suggérée (pas d'envoi)
4. **CRM Agent** : Analyse le deal (pas de mise à jour)

**Intérêt :**
- Voir tout le workflow end-to-end
- Vérifier que chaque étape fonctionne
- Examiner les suggestions avant d'activer l'automatisation

### Étape 6 : Workflow complet (AUTO-DISPATCH)

**⚠️ ATTENTION : MODIFIE LES TICKETS**

Ce mode réaffecte automatiquement les tickets au bon département.

```bash
python test_with_real_tickets.py
```

Choisissez l'option **5** et confirmez.

**Ce que ça fait :**
- Même chose que l'étape 5, MAIS :
- **Réaffecte le ticket** si le département est incorrect
- Les autres étapes restent en READ-ONLY

**Utilisez cette option uniquement si :**
- Les tests READ-ONLY donnent de bons résultats
- Vous avez validé les règles de routing
- Vous êtes prêt à automatiser le dispatching

## Affiner les règles de routing

Après les tests batch (étape 3), vous verrez peut-être des tickets mal classés.

### Ajuster les mots-clés

Éditez `business_rules.py` :

```python
@staticmethod
def get_department_routing_rules() -> Dict[str, Any]:
    return {
        "DOC": {
            "keywords": [
                "uber",
                "a-level",
                "student",
                "education",
                # Ajoutez vos propres mots-clés
                "programme",
                "cours",
                "étudiant"
            ],
            "contact_domains": [
                # Filtrer par domaine email si nécessaire
                "@university.edu",
                "@school.ac.uk"
            ]
        },
        "Sales": {
            "keywords": [
                "pricing",
                "quote",
                "demo",
                # Ajoutez les vôtres
                "tarif",
                "devis"
            ]
        }
    }
```

### Re-tester après modifications

1. Modifiez `business_rules.py`
2. Relancez le test batch (option 2)
3. Vérifiez que les suggestions sont meilleures
4. Itérez jusqu'à satisfaction

## Ajuster les règles de deal linking

Si le deal linking ne trouve pas les bons deals, ajustez la logique département par département.

### Pour le département DOC

Éditez `business_rules.py`, méthode `get_deal_search_criteria_for_department()` :

```python
if department == "DOC":
    return [
        {
            "criteria": f"((Email:equals:{contact_email})and(Deal_Name:contains:Uber)and(Amount:equals:20)and(Stage:equals:Closed Won))",
            "description": "Uber €20 deals - WON",
            "max_results": 1,
            "sort_by": "Modified_Time",
            "sort_order": "desc"
        },
        # Ajoutez d'autres critères de fallback
    ]
```

**Paramètres modifiables :**
- `Deal_Name:contains:Uber` → Changez "Uber" selon vos deals
- `Amount:equals:20` → Changez le montant
- `Stage:equals:Closed Won` → Changez le statut

### Ajouter d'autres départements

```python
if department == "Sales":
    return [
        {
            "criteria": f"((Email:equals:{contact_email})and(Stage:equals:Qualification))",
            "description": "Open Sales deals",
            "max_results": 1,
            "sort_by": "Modified_Time",
            "sort_order": "desc"
        }
    ]
```

## Activation progressive de l'automatisation

Une fois les tests satisfaisants :

### Niveau 1 : Dispatcher auto + Reste READ-ONLY

```python
result = orchestrator.process_ticket_complete_workflow(
    ticket_id=ticket_id,
    auto_dispatch=True,     # ✅ Active
    auto_link=False,        # ❌ READ-ONLY
    auto_respond=False,     # ❌ READ-ONLY
    auto_update_deal=False  # ❌ READ-ONLY
)
```

### Niveau 2 : Dispatcher + Deal linking auto

```python
result = orchestrator.process_ticket_complete_workflow(
    ticket_id=ticket_id,
    auto_dispatch=True,     # ✅ Active
    auto_link=True,         # ✅ Active (crée le lien cf_deal_id)
    auto_respond=False,     # ❌ READ-ONLY
    auto_update_deal=False  # ❌ READ-ONLY
)
```

### Niveau 3 : Automatisation complète

```python
result = orchestrator.process_ticket_complete_workflow(
    ticket_id=ticket_id,
    auto_dispatch=True,       # ✅ Active
    auto_link=True,           # ✅ Active
    auto_respond=True,        # ✅ Active (envoie la réponse)
    auto_update_ticket=True,  # ✅ Active (change le statut)
    auto_update_deal=True,    # ✅ Active (met à jour le CRM)
    auto_add_note=True        # ✅ Active (ajoute des notes)
)
```

**⚠️ Recommandation :** Activez progressivement et surveillez les résultats pendant quelques jours à chaque niveau.

## Intégration avec un webhook Zoho

Pour automatiser complètement :

1. **Créez un webhook dans Zoho Desk**
   - Setup → Automation → Webhooks
   - Trigger : "On ticket creation" ou "On ticket update"
   - URL : Votre endpoint (ex: `https://votre-serveur.com/webhook`)

2. **Créez un endpoint Flask/FastAPI**

```python
from flask import Flask, request
from src.orchestrator import ZohoAutomationOrchestrator

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def handle_ticket():
    data = request.json
    ticket_id = data.get('ticket_id')

    orchestrator = ZohoAutomationOrchestrator()
    try:
        result = orchestrator.process_ticket_complete_workflow(
            ticket_id=ticket_id,
            auto_dispatch=True,
            auto_link=True,
            auto_respond=True,
            auto_update_deal=True
        )
        return {"success": True, "result": result}
    finally:
        orchestrator.close()
```

3. **Déployez sur Heroku/AWS/GCP/Render**

## Dépannage

### Erreur : "Invalid refresh token"
- Regénérez un nouveau refresh token
- Vérifiez les scopes
- Vérifiez le datacenter (com vs eu vs in)

### Erreur : "Department not found"
- Dans `dispatcher_agent.py`, ligne ~230, il utilise `departmentId`
- Zoho peut nécessiter l'ID numérique du département, pas le nom
- Solution : Créez un mapping dans `business_rules.py`

### Aucun deal trouvé
- Vérifiez les critères de recherche dans `get_deal_search_criteria_for_department()`
- Testez manuellement la recherche dans Zoho CRM
- Vérifiez que le champ `Email` existe dans vos deals CRM

### IA génère des mauvaises réponses
- Ajustez le `system_prompt` dans `desk_agent.py`
- Ajustez la température dans `.env` (0.7 → 0.5 pour plus de cohérence)
- Donnez plus de contexte métier dans les prompts

## Support

Pour toute question :
1. Vérifiez les logs (niveau INFO ou DEBUG)
2. Testez chaque étape séparément
3. Vérifiez la documentation Zoho API

Bon test ! 🚀
