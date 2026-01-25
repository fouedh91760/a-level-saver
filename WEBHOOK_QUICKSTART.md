# 🚀 Webhook - Guide de démarrage rapide (5 minutes)

Guide minimal pour démarrer le webhook en local et le tester.

## 1. Installation (1 minute)

```bash
# Installer les dépendances (Flask + Gunicorn)
pip install -r requirements.txt
```

## 2. Configuration (2 minutes)

### Générer un secret HMAC

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copiez le résultat (ex: `xK7pQ2mN9vR8sT4uW6yZ1aB3cD5eF7gH`)

### Ajouter au fichier `.env`

Ajoutez ces lignes à votre `.env` :

```bash
# Webhook
ZOHO_WEBHOOK_SECRET=xK7pQ2mN9vR8sT4uW6yZ1aB3cD5eF7gH
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000

# Automation (mode READ-ONLY au début)
WEBHOOK_AUTO_DISPATCH=true
WEBHOOK_AUTO_LINK=true
WEBHOOK_AUTO_RESPOND=false
WEBHOOK_AUTO_UPDATE_TICKET=false
WEBHOOK_AUTO_UPDATE_DEAL=false
WEBHOOK_AUTO_ADD_NOTE=false

# Flask
FLASK_DEBUG=false
```

## 3. Démarrer le serveur (30 secondes)

```bash
python webhook_server.py
```

Vous devriez voir :
```
🚀 A-Level Saver Webhook Server Starting
Host: 0.0.0.0
Port: 5000
Auto Dispatch: True
Auto Link: True
Auto Respond: False
...
```

## 4. Tester (1 minute)

### Terminal 1 : Serveur (déjà lancé)

```bash
python webhook_server.py
```

### Terminal 2 : Tests

```bash
# Test 1 : Health check
curl http://localhost:5000/health

# Test 2 : Stats
curl http://localhost:5000/webhook/stats

# Test 3 : Traiter un ticket réel
python test_webhook.py --test simple --ticket-id 198709000438366101
```

## 5. Configuration Zoho Desk (optionnel - pour production)

### Option A : Test local avec ngrok

```bash
# Terminal 3 : Exposer le serveur local
ngrok http 5000
```

Copiez l'URL ngrok (ex: `https://abc123.ngrok.io`)

### Option B : Configuration Zoho

1. Allez dans **Zoho Desk** → **Setup** → **Automation** → **Webhooks**
2. Cliquez **Add Webhook**
3. Configuration :
   - **URL** : `https://abc123.ngrok.io/webhook/zoho-desk` (remplacez par votre URL)
   - **Méthode** : POST
   - **Format** : JSON
   - **Événements** : Cochez "Ticket Created" et "Ticket Updated"
   - **Secret** : Collez le secret généré à l'étape 2
4. Cliquez **Save**
5. Cliquez **Test Webhook** pour envoyer un événement test

## 6. Vérifier les logs

```bash
# Logs en temps réel
tail -f logs/app.log

# Ou voir directement dans le terminal si FLASK_DEBUG=true
```

## Résultats attendus

Après un test réussi, vous devriez voir :

```json
{
  "success": true,
  "ticket_id": "198709000438366101",
  "processing_time_seconds": 3.45,
  "result": {
    "dispatcher": true,
    "deal_linking": true,
    "desk_agent": true,
    "crm_agent": true,
    "summary": {
      "current_department": "Contact",
      "recommended_department": "DOC",
      "deal_found": true,
      "deal_name": "BFS NP Samir Mezoulfi"
    }
  }
}
```

## Commandes utiles

```bash
# Démarrer le serveur
python webhook_server.py

# Tests complets
python test_webhook.py --test all

# Test avec un ticket spécifique
python test_webhook.py --test simple --ticket-id VOTRE_TICKET_ID

# Test avec signature HMAC
python test_webhook.py --test signature --ticket-id VOTRE_TICKET_ID

# Vérifier la configuration
curl http://localhost:5000/webhook/stats

# Logs en temps réel
tail -f logs/app.log
```

## Activation progressive

### Niveau 1 : Dispatch + Link (recommandé au début)

```bash
WEBHOOK_AUTO_DISPATCH=true
WEBHOOK_AUTO_LINK=true
WEBHOOK_AUTO_RESPOND=false
WEBHOOK_AUTO_UPDATE_TICKET=false
WEBHOOK_AUTO_UPDATE_DEAL=false
WEBHOOK_AUTO_ADD_NOTE=false
```

**Ce qui se passe :**
- ✅ Les tickets sont réaffectés au bon département
- ✅ Le lien ticket ↔ deal est créé
- ❌ Aucune réponse envoyée (mode suggestion)
- ❌ Aucune modification du CRM

### Niveau 2 : + Réponses (après validation)

```bash
WEBHOOK_AUTO_RESPOND=true
WEBHOOK_AUTO_UPDATE_TICKET=true
```

**⚠️ ATTENTION :** Les clients recevront des emails automatiques !

### Niveau 3 : Tout automatique (après tests approfondis)

```bash
WEBHOOK_AUTO_UPDATE_DEAL=true
WEBHOOK_AUTO_ADD_NOTE=true
```

## Dépannage rapide

### "Connection refused"

Le serveur n'est pas démarré. Lancez :
```bash
python webhook_server.py
```

### "Invalid signature"

Le secret dans `.env` ne correspond pas au secret dans Zoho Desk.

Solution :
1. Vérifiez `ZOHO_WEBHOOK_SECRET` dans `.env`
2. Vérifiez le secret dans Zoho Desk
3. Régénérez un nouveau secret si nécessaire

### "No ticket ID found"

Le format du payload est inattendu.

Solution :
1. Utilisez `/webhook/test` qui est plus tolérant
2. Vérifiez les logs pour voir la structure du payload

### Le webhook ne se déclenche pas depuis Zoho

1. Vérifiez que l'URL est accessible publiquement (utilisez ngrok)
2. Testez l'URL manuellement : `curl https://votre-url/health`
3. Vérifiez les événements déclencheurs dans Zoho Desk
4. Vérifiez les logs Zoho Desk → Webhooks → View Logs

## Déploiement production (bonus)

### Avec Gunicorn

```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 webhook_server:app
```

### Avec Docker

```bash
docker build -t webhook .
docker run -d -p 5000:5000 --env-file .env webhook
```

### Avec Heroku

```bash
echo "web: gunicorn --bind 0.0.0.0:\$PORT --workers 4 webhook_server:app" > Procfile
heroku create a-level-saver-webhook
git push heroku main
```

## Documentation complète

Pour plus de détails :
- **Guide complet** : [WEBHOOK_SETUP.md](./WEBHOOK_SETUP.md)
- **Architecture** : [DOC_TICKET_AUTOMATION.md](./DOC_TICKET_AUTOMATION.md)
- **API Reference** : [API_REFERENCE.md](./API_REFERENCE.md)

---

**C'est tout ! Votre webhook est prêt. 🎉**
