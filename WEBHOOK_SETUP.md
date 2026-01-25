# Configuration du Webhook Zoho Desk

Ce guide explique comment configurer et déployer le serveur webhook pour automatiser le traitement des tickets Zoho Desk.

## Architecture

```
Zoho Desk (Événement ticket)
    ↓
Webhook HTTP POST
    ↓
Serveur Flask (webhook_server.py)
    ↓
Vérification signature HMAC
    ↓
Orchestrateur (process_ticket_complete_workflow)
    ↓
8 étapes d'automatisation
    ↓
Réponse JSON (succès/échec)
```

## 1. Configuration locale

### Installation des dépendances

```bash
pip install -r requirements.txt
```

Cela installera Flask et Gunicorn nécessaires pour le serveur webhook.

### Configuration des variables d'environnement

Ajoutez ces variables dans votre fichier `.env` :

```bash
# Webhook Configuration
ZOHO_WEBHOOK_SECRET=votre_secret_hmac_ici
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000

# Automation Flags (contrôle progressif)
WEBHOOK_AUTO_DISPATCH=true          # Réaffectation auto au bon département
WEBHOOK_AUTO_LINK=true              # Liaison auto ticket ↔ deal
WEBHOOK_AUTO_RESPOND=false          # ⚠️ Génère ET envoie la réponse
WEBHOOK_AUTO_UPDATE_TICKET=false    # ⚠️ Change le statut du ticket
WEBHOOK_AUTO_UPDATE_DEAL=false      # ⚠️ Met à jour le CRM
WEBHOOK_AUTO_ADD_NOTE=false         # ⚠️ Ajoute des notes au CRM

# Flask
FLASK_DEBUG=false                   # true pour dev, false pour prod
```

### Démarrage du serveur (développement)

```bash
python webhook_server.py
```

Le serveur démarre sur `http://0.0.0.0:5000` avec les endpoints suivants :

- `GET /health` - Health check
- `POST /webhook/zoho-desk` - Endpoint principal pour les webhooks Zoho
- `POST /webhook/test` - Endpoint de test sans vérification de signature
- `GET /webhook/stats` - Statistiques et configuration actuelle

### Vérification

```bash
# Health check
curl http://localhost:5000/health

# Stats
curl http://localhost:5000/webhook/stats
```

## 2. Test en local avec ngrok

Pour tester le webhook avec Zoho Desk en développement, exposez votre serveur local :

### Installation de ngrok

```bash
# macOS
brew install ngrok

# Linux
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar xvzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/
```

### Démarrage

```bash
# Terminal 1 : Démarrer le serveur webhook
python webhook_server.py

# Terminal 2 : Exposer via ngrok
ngrok http 5000
```

Ngrok vous donnera une URL publique comme :
```
https://abc123.ngrok.io
```

Utilisez cette URL pour configurer le webhook dans Zoho Desk :
```
https://abc123.ngrok.io/webhook/zoho-desk
```

## 3. Configuration du webhook dans Zoho Desk

### Étape 1 : Accéder aux webhooks

1. Connectez-vous à Zoho Desk
2. Allez dans **Setup** → **Automation** → **Webhooks**
3. Cliquez sur **Add Webhook**

### Étape 2 : Configuration

**Nom du webhook :**
```
A-Level Saver Automation
```

**URL du webhook :**
```
https://votre-domaine.com/webhook/zoho-desk
```
(Utilisez ngrok pour les tests : `https://abc123.ngrok.io/webhook/zoho-desk`)

**Méthode HTTP :**
```
POST
```

**Format de données :**
```
JSON
```

**Événements déclencheurs :**

Cochez les événements suivants :
- ☑️ **Ticket Created** - Nouveau ticket créé
- ☑️ **Ticket Updated** - Ticket mis à jour
- ☑️ **Ticket Status Changed** - Changement de statut
- ☐ Ticket Assigned (optionnel)
- ☐ Ticket Comment Added (optionnel)

**Départements :**

Sélectionnez les départements concernés :
- ☑️ DOC
- ☑️ Contact
- ☑️ FACTURATION
- ☐ Autres (selon besoin)

**En-têtes HTTP personnalisés :**

Ajoutez cet en-tête pour la vérification de signature :
```
X-Zoho-Signature: {signature}
```

(Zoho génèrera automatiquement la signature si vous configurez le secret)

### Étape 3 : Configuration du secret HMAC

**Dans Zoho Desk :**
1. Dans la configuration du webhook, cherchez "Webhook Secret"
2. Générez un secret aléatoire fort :
   ```bash
   # Générez un secret sécurisé
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. Copiez ce secret dans Zoho Desk
4. Ajoutez-le aussi dans votre `.env` :
   ```bash
   ZOHO_WEBHOOK_SECRET=le_secret_généré
   ```

**⚠️ Important :** Le secret doit être identique dans Zoho Desk et dans votre `.env` !

### Étape 4 : Tester le webhook

Dans Zoho Desk, cliquez sur **Test Webhook** pour envoyer un événement de test.

Vérifiez les logs du serveur Flask :
```bash
# Logs en temps réel
tail -f logs/app.log

# Ou dans le terminal si FLASK_DEBUG=true
```

## 4. Test manuel avec curl

### Test simple (sans signature)

Utilisez l'endpoint `/webhook/test` qui ne vérifie pas la signature :

```bash
curl -X POST http://localhost:5000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "ticket_id": "198709000438366101",
    "auto_dispatch": true,
    "auto_link": true,
    "auto_respond": false
  }'
```

### Test avec signature HMAC

Pour tester l'endpoint principal avec signature :

```bash
# 1. Créez le payload
PAYLOAD='{"ticket":{"id":"198709000438366101"},"event_type":"ticket.created"}'

# 2. Calculez la signature HMAC
SECRET="votre_secret_hmac"
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | cut -d' ' -f2)

# 3. Envoyez la requête
curl -X POST http://localhost:5000/webhook/zoho-desk \
  -H "Content-Type: application/json" \
  -H "X-Zoho-Signature: $SIGNATURE" \
  -d "$PAYLOAD"
```

### Test avec les fichiers JSON pushés

Vous pouvez tester avec les vraies données que vous avez pushées :

```bash
# Testez avec le ticket 198709000438366101
curl -X POST http://localhost:5000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"ticket_id": "198709000438366101"}'
```

## 5. Déploiement en production

### Option A : Déploiement avec Gunicorn

Pour la production, utilisez Gunicorn au lieu du serveur Flask de développement :

```bash
# Démarrage avec Gunicorn (4 workers)
gunicorn --bind 0.0.0.0:5000 \
         --workers 4 \
         --timeout 120 \
         --access-logfile logs/access.log \
         --error-logfile logs/error.log \
         webhook_server:app
```

### Option B : Déploiement avec Supervisor

Créez un fichier `/etc/supervisor/conf.d/webhook.conf` :

```ini
[program:webhook]
command=/chemin/vers/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 webhook_server:app
directory=/chemin/vers/a-level-saver
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/webhook/access.log
stderr_logfile=/var/log/webhook/error.log
environment=PATH="/chemin/vers/venv/bin"
```

Démarrez :
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start webhook
```

### Option C : Déploiement avec systemd

Créez un fichier `/etc/systemd/system/webhook.service` :

```ini
[Unit]
Description=A-Level Saver Webhook Service
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/chemin/vers/a-level-saver
Environment="PATH=/chemin/vers/venv/bin"
ExecStart=/chemin/vers/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 webhook_server:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Démarrez :
```bash
sudo systemctl daemon-reload
sudo systemctl enable webhook
sudo systemctl start webhook
sudo systemctl status webhook
```

### Option D : Déploiement Docker

Créez un `Dockerfile` :

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 5000

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "webhook_server:app"]
```

Build et run :
```bash
docker build -t a-level-saver-webhook .
docker run -d -p 5000:5000 --env-file .env --name webhook a-level-saver-webhook
```

### Option E : Déploiement Heroku

```bash
# 1. Créez un Procfile
echo "web: gunicorn --bind 0.0.0.0:\$PORT --workers 4 --timeout 120 webhook_server:app" > Procfile

# 2. Créez l'app Heroku
heroku create a-level-saver-webhook

# 3. Configurez les variables d'environnement
heroku config:set ZOHO_CLIENT_ID=...
heroku config:set ZOHO_CLIENT_SECRET=...
heroku config:set ZOHO_WEBHOOK_SECRET=...
# ... toutes les autres variables

# 4. Déployez
git push heroku main

# 5. Vérifiez
heroku logs --tail
```

### Option F : Déploiement Render.com

1. Créez un compte sur https://render.com
2. Créez un nouveau "Web Service"
3. Connectez votre repo GitHub
4. Configuration :
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 webhook_server:app`
5. Ajoutez les variables d'environnement dans l'interface
6. Déployez

### Configuration Nginx (reverse proxy)

Si vous déployez sur un VPS, configurez Nginx :

```nginx
server {
    listen 80;
    server_name votre-domaine.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

Pour HTTPS avec Let's Encrypt :
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d votre-domaine.com
```

## 6. Activation progressive de l'automatisation

**Recommandation :** Activez progressivement les fonctionnalités pour valider chaque étape.

### Niveau 1 : Dispatch + Linking uniquement

```bash
WEBHOOK_AUTO_DISPATCH=true
WEBHOOK_AUTO_LINK=true
WEBHOOK_AUTO_RESPOND=false
WEBHOOK_AUTO_UPDATE_TICKET=false
WEBHOOK_AUTO_UPDATE_DEAL=false
WEBHOOK_AUTO_ADD_NOTE=false
```

**Ce qui se passe :**
- ✅ Les tickets sont automatiquement réaffectés au bon département
- ✅ Le lien ticket ↔ deal est créé automatiquement
- ❌ Aucune réponse envoyée (reste en mode suggestion)
- ❌ Aucune modification du ticket/CRM

**Surveillez pendant 2-3 jours** pour vérifier que le routing est correct.

### Niveau 2 : + Réponses automatiques

```bash
WEBHOOK_AUTO_RESPOND=true
WEBHOOK_AUTO_UPDATE_TICKET=true
```

**Ce qui se passe :**
- ✅ Génère ET envoie les réponses aux clients
- ✅ Change le statut du ticket (ex: Open → Pending)

**⚠️ ATTENTION :** Les clients recevront des emails automatiques !

**Surveillez attentivement** pour vérifier que les réponses sont appropriées.

### Niveau 3 : Automatisation complète

```bash
WEBHOOK_AUTO_UPDATE_DEAL=true
WEBHOOK_AUTO_ADD_NOTE=true
```

**Ce qui se passe :**
- ✅ Met à jour les opportunités CRM automatiquement
- ✅ Ajoute des notes dans le CRM

## 7. Monitoring et logs

### Vérifier les logs

```bash
# Logs temps réel
tail -f logs/app.log

# Logs d'erreurs uniquement
grep ERROR logs/app.log

# Logs webhook
grep "Received webhook" logs/app.log
```

### Statistiques

```bash
# Vérifier la configuration actuelle
curl http://localhost:5000/webhook/stats
```

Exemple de réponse :
```json
{
  "service": "a-level-saver-webhook",
  "status": "running",
  "configuration": {
    "auto_dispatch": true,
    "auto_link": true,
    "auto_respond": false,
    "auto_update_ticket": false,
    "auto_update_deal": false,
    "auto_add_note": false,
    "signature_verification": true
  },
  "timestamp": "2026-01-25T02:00:00.000Z"
}
```

### Alertes recommandées

Configurez des alertes pour :
- ❌ Webhook signature verification failed
- ❌ Error processing webhook
- ❌ Failed to parse JSON payload
- ⚠️ No ticket ID found in payload

## 8. Dépannage

### Erreur : "Invalid signature"

**Cause :** Le secret HMAC ne correspond pas entre Zoho et votre serveur.

**Solution :**
1. Vérifiez que `ZOHO_WEBHOOK_SECRET` dans `.env` correspond au secret dans Zoho Desk
2. Vérifiez qu'il n'y a pas d'espaces ou caractères invisibles
3. Régénérez un nouveau secret si nécessaire

### Erreur : "No ticket ID found in payload"

**Cause :** Le format du payload Zoho a changé ou est inattendu.

**Solution :**
1. Loggez le payload complet : ajoutez `logger.debug(f"Payload: {json.dumps(data, indent=2)}")`
2. Vérifiez la structure dans les logs
3. Ajustez `extract_ticket_id_from_payload()` si nécessaire

### Erreur : "Orchestrator failed"

**Cause :** Problème dans le workflow d'automatisation.

**Solution :**
1. Vérifiez les credentials Zoho dans `.env`
2. Testez manuellement avec `test_with_real_tickets.py`
3. Vérifiez les logs détaillés de l'orchestrateur

### Webhook ne se déclenche pas

**Vérifiez :**
1. Le webhook est bien activé dans Zoho Desk
2. L'URL est accessible publiquement (testez avec ngrok)
3. Les événements déclencheurs sont cochés
4. Le département du ticket correspond aux départements configurés

### Performance lente

**Si le traitement prend > 30 secondes :**

1. Augmentez le timeout dans Gunicorn :
   ```bash
   gunicorn --timeout 180 ...
   ```

2. Utilisez une queue asynchrone (Celery + Redis) :
   - Le webhook accepte immédiatement la requête
   - Le traitement se fait en arrière-plan
   - Permet de gérer des pics de charge

## 9. Sécurité

### Checklist de sécurité

- ✅ **Signature HMAC activée** : `ZOHO_WEBHOOK_SECRET` configuré
- ✅ **HTTPS uniquement** : Utilisez un certificat SSL (Let's Encrypt)
- ✅ **Rate limiting** : Limitez le nombre de requêtes par IP
- ✅ **Validation des données** : Vérifiez ticket_id, event_type, etc.
- ✅ **Logs sécurisés** : Ne loggez jamais les secrets ou tokens
- ✅ **Firewall** : Limitez l'accès au webhook aux IPs de Zoho uniquement

### IPs Zoho à whitelist

Ajoutez ces IPs dans votre firewall :
```
# Zoho Desk webhook IPs (vérifiez la doc officielle)
# https://www.zoho.com/desk/help/api/webhook-ips.html
```

## 10. Prochaines étapes

Une fois le webhook configuré et testé :

1. ✅ **Surveillez les logs** pendant 1 semaine en mode READ-ONLY
2. ✅ **Activez progressivement** les fonctionnalités (dispatch → link → respond)
3. ✅ **Affinez les règles** dans `business_rules.py` selon les résultats
4. ✅ **Configurez les alertes** pour les erreurs critiques
5. ✅ **Documentez** les cas particuliers et exceptions

## Support

Pour toute question :
1. Vérifiez les logs (`logs/app.log`)
2. Testez manuellement avec `/webhook/test`
3. Consultez la documentation Zoho : https://www.zoho.com/desk/help/api/webhooks.html

---

**Bon déploiement ! 🚀**
