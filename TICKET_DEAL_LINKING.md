## Stratégies de liaison Ticket ↔ Deal

Ce document explique comment le système lie automatiquement les tickets Zoho Desk aux opportunités Zoho CRM.

## 🎯 Le problème

Zoho Desk et Zoho CRM sont deux systèmes séparés. Pour automatiser les workflows entre eux, nous devons savoir quel ticket correspond à quelle opportunité.

## ✅ Solution : Multiples stratégies avec fallback

Le système utilise **5 stratégies** différentes, essayées dans l'ordre jusqu'à trouver un match.

---

## 📋 Les 5 stratégies

### 1️⃣ Custom Field (Lien direct) ⭐⭐⭐

**Priorité** : La plus élevée
**Comment ça marche** : Vérifie si le ticket contient déjà un champ personnalisé avec le deal_id

**Champs vérifiés** :
- `cf_deal_id`
- `cf_zoho_crm_deal_id`
- `Deal_ID`
- `dealId`
- `CRM_Deal_ID`

**Avantages** :
- ✅ 100% fiable si le lien existe
- ✅ Très rapide (pas de recherche)
- ✅ Pas d'ambiguïté

**Inconvénients** :
- ❌ Nécessite que le lien ait été créé manuellement ou automatiquement avant

**Quand l'utiliser** :
- Quand vous avez déjà lié les tickets et deals
- Après avoir utilisé `link_ticket_to_deal_bidirectional()`

**Code** :
```python
# Le ticket a un champ cf_deal_id = "123456"
deal = linker.find_deal_for_ticket(ticket_id, strategies=["custom_field"])
```

---

### 2️⃣ Contact Email ⭐⭐

**Priorité** : Élevée
**Comment ça marche** : Cherche les deals où le contact a le même email que le contact du ticket

**Recherche API** :
```python
criteria = "(Email:equals:student@example.com)"
# Ou
criteria = "(Contact_Email:equals:student@example.com)"
```

**Avantages** :
- ✅ Email généralement unique
- ✅ Très fiable dans la plupart des cas
- ✅ Fonctionne sans configuration préalable

**Inconvénients** :
- ❌ Peut retourner plusieurs deals (on prend le premier)
- ❌ Ne fonctionne pas si l'email est différent entre Desk et CRM

**Quand l'utiliser** :
- Par défaut
- Quand le contact utilise le même email partout

**Code** :
```python
deal = linker.find_deal_for_ticket(ticket_id, strategies=["contact_email"])
```

---

### 3️⃣ Contact Phone ⭐⭐

**Priorité** : Élevée
**Comment ça marche** : Cherche les deals par numéro de téléphone

**Recherche API** :
```python
criteria = "(Phone:equals:+33612345678)"
```

**Nettoyage automatique** : Le système nettoie le numéro (enlève espaces, tirets, parenthèses)

**Avantages** :
- ✅ Bon fallback si email non disponible
- ✅ Téléphone souvent unique

**Inconvénients** :
- ❌ Formats de numéros variés
- ❌ Peut manquer si formatage différent

**Quand l'utiliser** :
- Comme complément à l'email
- Pour les tickets par téléphone

**Code** :
```python
deal = linker.find_deal_for_ticket(ticket_id, strategies=["contact_phone"])
```

---

### 4️⃣ Account/Organization ⭐

**Priorité** : Moyenne
**Comment ça marche** : Cherche les deals liés à la même organisation/entreprise

**Recherche API** :
```python
criteria = "(Account_Name:equals:ABC Corp)"
```

**Avantages** :
- ✅ Utile en B2B
- ✅ Fonctionne quand le contact change

**Inconvénients** :
- ❌ Peut retourner beaucoup de deals
- ❌ Moins précis qu'email/téléphone
- ❌ Nécessite que l'account soit renseigné

**Quand l'utiliser** :
- Pour les tickets d'entreprise
- Quand plusieurs contacts de la même entreprise créent des tickets

**Code** :
```python
deal = linker.find_deal_for_ticket(ticket_id, strategies=["account"])
```

---

### 5️⃣ Recent Deal (Fallback) ⭐

**Priorité** : Faible
**Comment ça marche** : Récupère le deal le plus récemment modifié pour ce contact

**Recherche API** :
```python
criteria = "(Email:equals:student@example.com)"
# Trie par Modified_Time descending, prend le 1er
```

**Avantages** :
- ✅ Dernier recours quand rien d'autre ne fonctionne
- ✅ Souvent correct pour les clients actifs

**Inconvénients** :
- ❌ Peut retourner un vieux deal fermé
- ❌ Peu fiable si le contact a plusieurs deals

**Quand l'utiliser** :
- En dernier recours uniquement
- Pour les contacts avec peu de deals

**Code** :
```python
deal = linker.find_deal_for_ticket(ticket_id, strategies=["recent_deal"])
```

---

## 🔄 Workflow automatique

### Utilisation de toutes les stratégies

```python
from src.ticket_deal_linker import TicketDealLinker

linker = TicketDealLinker()

# Essaie toutes les stratégies dans l'ordre
deal = linker.find_deal_for_ticket("ticket_123")

# Résultat :
# - Essaie custom_field → pas de champ
# - Essaie contact_email → trouve un deal! ✅
# - Retourne le deal sans essayer le reste
```

### Utilisation de stratégies spécifiques

```python
# Seulement email et téléphone
deal = linker.find_deal_for_ticket(
    "ticket_123",
    strategies=["contact_email", "contact_phone"]
)
```

---

## 🔗 Liaison bidirectionnelle

Une fois le deal trouvé, créez un lien bidirectionnel pour les prochaines fois :

```python
# Créer un lien dans les deux sens
linker.link_ticket_to_deal_bidirectional(
    ticket_id="ticket_123",
    deal_id="deal_456",
    update_ticket_field="cf_deal_id",  # Champ dans Desk
    update_deal_field="Ticket_ID"      # Champ dans CRM
)
```

**Résultat** :
- Dans Desk : Le ticket a `cf_deal_id = "deal_456"`
- Dans CRM : Le deal a `Ticket_ID = "ticket_123"`

**Avantage** : La prochaine fois, la stratégie #1 (custom_field) trouvera immédiatement le lien !

---

## ⚡ Workflow complet automatisé

La méthode recommandée qui fait tout automatiquement :

```python
from src.orchestrator import ZohoAutomationOrchestrator

orchestrator = ZohoAutomationOrchestrator()

# Traite le ticket ET trouve/met à jour le deal automatiquement
result = orchestrator.process_ticket_with_auto_crm_link(
    ticket_id="ticket_123",
    auto_respond=True,              # Répond au ticket
    auto_update_ticket=True,        # MAJ statut ticket
    auto_update_deal=True,          # MAJ le deal
    auto_add_note=True,             # Ajoute note au deal
    create_bidirectional_link=True  # Crée le lien pour la prochaine fois
)

if result['deal_found']:
    print(f"Deal trouvé et mis à jour: {result['deal_name']}")
else:
    print("Aucun deal trouvé - ticket traité seul")
```

**Ce que fait cette méthode** :
1. ✅ Analyse le ticket avec l'IA
2. ✅ Cherche le deal automatiquement (toutes stratégies)
3. ✅ Crée un lien bidirectionnel
4. ✅ Analyse l'impact sur le deal avec l'IA
5. ✅ Met à jour le deal automatiquement
6. ✅ Ajoute une note avec l'analyse

---

## 🎯 Cas d'usage

### Cas 1 : Nouveau système (pas de liens existants)

**Problème** : Aucun champ personnalisé n'existe encore

**Solution** :
```python
# Première fois : cherche par email
deal = linker.find_deal_for_ticket(ticket_id)

if deal:
    # Crée le lien pour la prochaine fois
    linker.link_ticket_to_deal_bidirectional(
        ticket_id, deal['id']
    )
```

**Résultat** : La prochaine fois, trouvera via custom_field instantanément

---

### Cas 2 : Contacts avec plusieurs deals

**Problème** : Un étudiant a plusieurs deals (différentes formations)

**Solution** :
```python
# Stratégie 1 : Utiliser un champ spécifique du ticket
# Par exemple, si le ticket a un champ "formation"
ticket = desk_client.get_ticket(ticket_id)
formation = ticket.get("cf_formation")

# Chercher le deal correspondant à cette formation
deals = crm_client.search_deals(
    criteria=f"((Email:equals:{email})and(Product:equals:{formation}))"
)
```

**Ou créer une stratégie personnalisée** :
```python
# Dans ticket_deal_linker.py, ajouter une nouvelle stratégie
def _find_by_formation(self, ticket):
    email = ticket.get("contact", {}).get("email")
    formation = ticket.get("cf_formation")

    if email and formation:
        criteria = f"((Email:equals:{email})and(Product:equals:{formation}))"
        result = self.crm_client.search_deals(criteria=criteria)
        deals = result.get("data", [])
        return deals[0] if deals else None

    return None
```

---

### Cas 3 : B2B avec plusieurs contacts

**Problème** : Une entreprise a plusieurs contacts créant des tickets

**Solution** : Utiliser la stratégie "account"
```python
# Cherche par organisation
deal = linker.find_deal_for_ticket(
    ticket_id,
    strategies=["account", "contact_email"]
)
```

---

## 🔧 Configuration requise

### Dans Zoho Desk

Créez un champ personnalisé pour stocker le deal_id :

1. Allez dans **Setup > Ticket Fields**
2. Créez un nouveau champ :
   - **Name** : Deal ID
   - **API Name** : cf_deal_id
   - **Type** : Single Line

### Dans Zoho CRM

Créez un champ personnalisé pour stocker le ticket_id :

1. Allez dans **Setup > Modules and Fields > Deals**
2. Créez un nouveau champ :
   - **Field Label** : Ticket ID
   - **Field Name** : Ticket_ID
   - **Type** : Single Line

---

## 📊 Performance

| Stratégie | Appels API | Vitesse | Fiabilité |
|-----------|-----------|---------|-----------|
| Custom Field | 1 (get deal) | ⚡⚡⚡ Très rapide | ⭐⭐⭐ 100% |
| Contact Email | 1-3 (search) | ⚡⚡ Rapide | ⭐⭐⭐ Élevée |
| Contact Phone | 1 (search) | ⚡⚡ Rapide | ⭐⭐ Moyenne |
| Account | 1 (search) | ⚡⚡ Rapide | ⭐ Faible |
| Recent Deal | 1 (search) | ⚡⚡ Rapide | ⭐ Très faible |

**Recommandation** : Utilisez la liaison bidirectionnelle pour qu'après la première fois, ce soit toujours "Custom Field" (le plus rapide et fiable).

---

## 🐛 Dépannage

### Problème : Aucun deal trouvé

**Solutions** :
1. Vérifier que le contact a bien un email dans le ticket
2. Vérifier que le deal existe dans le CRM
3. Vérifier l'orthographe de l'email (même casse)
4. Activer les logs pour voir quelle stratégie échoue :
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Problème : Mauvais deal trouvé

**Solutions** :
1. Créer une liaison bidirectionnelle pour fixer le lien
2. Utiliser des stratégies plus spécifiques
3. Fermer les vieux deals pour qu'ils ne soient plus retournés

### Problème : Plusieurs deals trouvés

**Solutions** :
1. Le système prend toujours le premier - trier par date pour avoir le plus récent
2. Filtrer sur le statut (deals ouverts uniquement)
3. Ajouter des critères supplémentaires (produit, montant, etc.)

---

## 📚 API Reference

Voir `src/ticket_deal_linker.py` pour :
- `find_deal_for_ticket()` - Trouve un deal
- `link_ticket_to_deal_bidirectional()` - Crée un lien bidirectionnel
- `auto_link_ticket()` - Trouve ET lie automatiquement

Voir `src/orchestrator.py` pour :
- `process_ticket_with_crm_update()` - Workflow avec deal_id connu
- `process_ticket_with_auto_crm_link()` - Workflow avec recherche auto

---

## ✅ Best Practices

1. **Toujours créer des liens bidirectionnels** quand un match est trouvé
2. **Privilégier l'email** comme méthode de recherche principale
3. **Nettoyer les vieux deals** pour éviter les faux positifs
4. **Utiliser des champs personnalisés** pour stocker les liens
5. **Logger les résultats** pour comprendre quelle stratégie fonctionne le mieux
6. **Tester avec de vraies données** avant d'activer les auto-actions
