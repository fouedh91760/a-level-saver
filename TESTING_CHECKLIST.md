# Checklist de test du workflow complet

## ✅ Ce qui a été corrigé

### 1. Modèle Claude mis à jour
- ✅ `config.py` : `claude-sonnet-4-5-20250929` (Claude Sonnet 4.5)
- ✅ `.env.example` : Documentation mise à jour
- ⚠️ **ACTION REQUISE** : Mettre à jour votre `.env` local

### 2. Gestion des identifiants ExamT3P
- ✅ **Cas 1** : Identifiants absents → Ne PAS demander (création de compte)
- ✅ **Cas 2** : Identifiants invalides → Message "Mot de passe oublié ?"
- ✅ **Cas 3** : Identifiants valides → Test connexion + extraction données

### 3. Compatibilité cross-platform
- ✅ Chemin Chromium hardcodé supprimé (était `/usr/bin/chromium-browser`)
- ✅ Playwright trouve automatiquement le navigateur installé (Windows/Linux/Mac)

### 4. Scripts de test
- ✅ `list_recent_tickets.py` : Lister les tickets valides
- ✅ `test_doc_workflow_with_examt3p.py` : Test workflow DOC complet
- ✅ Bug NoneType corrigé dans `test_new_workflow.py`

## 🔧 Actions requises AVANT de tester

### 1. Mettre à jour votre fichier `.env`

```bash
# Ouvrez votre fichier .env et changez cette ligne :
AGENT_MODEL=claude-sonnet-4-5-20250929
```

### 2. Installer/mettre à jour les dépendances

```bash
# Installer les packages Python
pip install -r requirements.txt

# Installer les navigateurs Playwright (IMPORTANT !)
playwright install chromium
```

**Note** : Si vous n'avez pas Playwright installé, le test de connexion ExamT3P échouera, MAIS le workflow continuera quand même grâce à la nouvelle logique.

### 3. Pull les derniers changements

```bash
git pull origin claude/zoho-ticket-automation-wb1xw
```

## 🧪 Commandes de test

### Test 1 : Lister les tickets valides

```bash
python list_recent_tickets.py
```

Résultat attendu : Liste des tickets récents avec ID, sujet, contact.

### Test 2 : Workflow DOC complet (RECOMMANDÉ)

```bash
python test_doc_workflow_with_examt3p.py <TICKET_ID>
```

**Ce test valide :**
- ✅ AGENT TRIEUR (triage)
- ✅ AGENT ANALYSTE (extraction données + **validation ExamT3P**)
- ✅ AGENT RÉDACTEUR (génération réponse)
- ✅ CRM Note
- ✅ Ticket/Deal Update

### Test 3 : Workflow basique (linking + routing)

```bash
python test_new_workflow.py <TICKET_ID> --full-workflow
```

**Ce test valide :**
- ✅ DealLinkingAgent (email → contacts → deals)
- ✅ DispatcherAgent (routing)
- ⚠️ Ne teste PAS la validation ExamT3P

## 📊 Comportement attendu

### Avec identifiants absents (ni Zoho ni threads)

```
🌐 ExamT3P:
   Identifiants trouvés: False

   ✅ IDENTIFIANTS ABSENTS - Pas de demande au candidat
      → Création de compte nécessaire (par nous)
```

### Avec identifiants présents mais invalides

```
🌐 ExamT3P:
   Identifiants trouvés: True
   Source: crm (ou email_threads)
   Connexion testée: False

   ⚠️ DEMANDE DE RÉINITIALISATION AU CANDIDAT
   Message:
      Bonjour,

      Nous avons tenté d'accéder à votre dossier...

      Pour accéder à votre compte, veuillez suivre la procédure de réinitialisation :
      1. Rendez-vous sur la plateforme ExamenT3P : https://www.exament3p.fr
      2. Cliquez sur "Me connecter"
      3. Utilisez la fonction "Mot de passe oublié ?"
      ...
```

### Avec identifiants valides

```
🌐 ExamT3P:
   Identifiants trouvés: True
   Source: crm (ou email_threads)
   Connexion testée: True

   ✅ IDENTIFIANTS VALIDÉS
   Compte existe: True
   Documents: 5
   Paiement CMA: EN ATTENTE
```

## ⚠️ Problèmes potentiels et solutions

### Erreur : "Module playwright non installé"

**Cause** : Playwright n'est pas installé ou les navigateurs ne sont pas installés.

**Solution** :
```bash
pip install playwright
playwright install chromium
```

**Impact** : Le test de connexion ExamT3P échouera, mais le workflow continuera (identifiants marqués comme "non testés").

### Erreur : "404 Not Found" sur le modèle Claude

**Cause** : Votre `.env` utilise encore l'ancien modèle.

**Solution** :
```bash
# Éditez .env et changez :
AGENT_MODEL=claude-sonnet-4-5-20250929
```

### Erreur : "Ticket not found (404)"

**Cause** : Le ticket ID n'existe pas ou n'est plus accessible.

**Solution** : Utilisez `list_recent_tickets.py` pour obtenir un ticket ID valide.

### Avertissement : "Could not fetch history for ticket"

**Cause** : Problème avec l'API Zoho Desk pour récupérer l'historique.

**Impact** : Workflow continue, mais historique incomplet. Ce n'est pas bloquant.

## 🎯 Workflow complet : Ce qui VA fonctionner

### 1. ✅ DealLinkingAgent
- Extraction email depuis threads
- Recherche contacts dans Zoho CRM
- Récupération de tous les deals
- Sélection du deal le plus pertinent
- Recommandation de département

### 2. ✅ Validation ExamT3P (NOUVELLE LOGIQUE)

**Scénario A : Identifiants absents**
- Recherche dans Zoho CRM : ❌ Non trouvés
- Recherche dans threads email : ❌ Non trouvés
- **Résultat** : `should_respond_to_candidate = False`
- **Action** : Aucune demande au candidat (on va créer le compte)

**Scénario B : Identifiants trouvés mais invalides**
- Recherche dans Zoho/threads : ✅ Trouvés
- Test de connexion : ❌ Échec
- **Résultat** : `should_respond_to_candidate = True`
- **Message** : Procédure "Mot de passe oublié ?" sur ExamenT3P

**Scénario C : Identifiants valides**
- Recherche dans Zoho/threads : ✅ Trouvés
- Test de connexion : ✅ Succès
- Extraction données : ✅ Documents, paiement, statut
- **Résultat** : Données ExamT3P disponibles pour la réponse

### 3. ✅ DispatcherAgent
- Utilise le département recommandé par DealLinkingAgent
- Vérifie si réaffectation nécessaire
- Confiance élevée (98%) basée sur les données CRM

### 4. ⚠️ ResponseGeneratorAgent (si appelé)
- Génère la réponse avec Claude Sonnet 4.5
- Utilise les données ExamT3P si disponibles
- Intègre le message "Mot de passe oublié ?" si nécessaire
- **Dépend de** : Modèle configuré correctement dans `.env`

### 5. ✅ CRM Update
- Mise à jour des identifiants si trouvés dans emails
- Ajout de notes au deal
- **Mode test** : Pas de mise à jour réelle (auto_update_crm=False)

## 📝 Résumé

**Le workflow VA fonctionner** si :
- ✅ Vous avez mis à jour `.env` avec le bon modèle
- ✅ Vous utilisez un ticket ID valide
- ⚠️ Playwright installé (recommandé mais pas obligatoire)

**Le workflow continuera même si** :
- ❌ Playwright n'est pas installé (test connexion échoué)
- ❌ Identifiants ExamT3P absents (nouvelle logique)
- ❌ Identifiants ExamT3P invalides (message généré)

## 🚀 Lancer le test maintenant

```bash
# 1. Pull
git pull origin claude/zoho-ticket-automation-wb1xw

# 2. Mettre à jour .env
# AGENT_MODEL=claude-sonnet-4-5-20250929

# 3. Installer Playwright (optionnel mais recommandé)
playwright install chromium

# 4. Lister tickets
python list_recent_tickets.py

# 5. Tester workflow complet
python test_doc_workflow_with_examt3p.py <TICKET_ID>
```

**C'est parti !** 🎉
