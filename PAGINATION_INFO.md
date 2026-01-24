# ⚠️ IMPORTANT : Gestion de la pagination Zoho

## Pourquoi la pagination est critique

**ATTENTION** : Les API Zoho utilisent la pagination PARTOUT. Si vous ne gérez pas correctement la pagination, vous ne verrez qu'une **partie** de vos données !

### Exemple concret :
- Vous avez 250 tickets "Open"
- Sans pagination : Vous ne verrez que les 100 premiers ❌
- Avec pagination : Vous verrez les 250 ✅

---

## 🔧 Méthodes avec pagination automatique

### Zoho Desk

#### ✅ Récupérer TOUS les tickets

```python
from src.zoho_client import ZohoDeskClient

desk_client = ZohoDeskClient()

# ❌ ANCIEN (UNE SEULE PAGE - MAX 100 tickets)
response = desk_client.list_tickets(status="Open", limit=100)
tickets = response.get("data", [])  # Seulement 100 tickets max

# ✅ NOUVEAU (TOUTES LES PAGES - TOUS LES TICKETS)
all_tickets = desk_client.list_all_tickets(status="Open")
# Retourne TOUS les tickets, peu importe le nombre
```

#### ✅ Récupérer TOUS les départements

```python
# Utilise automatiquement _get_all_pages() pour tout récupérer
dept_list = desk_client._get_all_pages(
    url=f"{settings.zoho_desk_api_url}/departments",
    params={"orgId": settings.zoho_desk_org_id},
    limit_per_page=100
)
```

---

### Zoho CRM

#### ✅ Rechercher TOUS les deals

```python
from src.zoho_client import ZohoCRMClient

crm_client = ZohoCRMClient()

# ❌ ANCIEN (UNE SEULE PAGE - MAX 200 deals)
response = crm_client.search_deals(
    criteria="(Stage:equals:Qualification)",
    per_page=200
)
deals = response.get("data", [])  # Seulement 200 deals max

# ✅ NOUVEAU (TOUTES LES PAGES - TOUS LES DEALS)
all_deals = crm_client.search_all_deals(
    criteria="(Stage:equals:Qualification)"
)
# Retourne TOUS les deals correspondants
```

---

## 🎯 Quand utiliser quelle méthode ?

### Utilisez les méthodes SANS pagination (`list_tickets`, `search_deals`) :

✅ Pour les **tests** où vous voulez juste quelques exemples
✅ Pour l'**UI** où vous affichez page par page
✅ Quand vous savez qu'il y a **peu de résultats**

### Utilisez les méthodes AVEC pagination automatique (`list_all_tickets`, `search_all_deals`) :

✅ Pour les **workflows automatiques** qui doivent traiter TOUS les éléments
✅ Pour les **rapports** et **statistiques**
✅ Pour l'**audit** (vérifier tous les départements, tous les liens, etc.)
✅ **Par défaut**, sauf si vous avez une bonne raison de limiter

---

## 📊 Limites par API Zoho

| API | Endpoint | Limite par page | Paramètre |
|-----|----------|-----------------|-----------|
| **Desk** | `/tickets` | 100 | `limit` + `from` |
| **Desk** | `/departments` | 100 | `limit` + `from` |
| **Desk** | `/threads` | 100 | `limit` + `from` |
| **CRM** | `/Deals/search` | 200 | `per_page` + `page` |
| **CRM** | `/Deals` | 200 | `per_page` + `page` |

---

## 🔍 Comment fonctionne la pagination automatique ?

### Pour Desk (utilise `from` index)

```python
# La méthode _get_all_pages() fait automatiquement :
all_items = []
from_index = 0

while True:
    response = api.request(from=from_index, limit=100)
    items = response["data"]

    if not items:
        break  # Plus de données

    all_items.extend(items)

    if len(items) < 100:
        break  # Dernière page (moins de 100 items)

    from_index += len(items)  # Page suivante
```

### Pour CRM (utilise `page` number)

```python
# La méthode search_all_deals() fait automatiquement :
all_deals = []
page = 1

while True:
    response = api.search(page=page, per_page=200)
    deals = response["data"]

    if not deals:
        break  # Plus de deals

    all_deals.extend(deals)

    # CRM retourne info.more_records
    if not response["info"]["more_records"]:
        break  # Dernière page

    page += 1  # Page suivante
```

---

## ⚠️ Points d'attention

### 1. Performance
- Récupérer TOUTES les pages peut prendre du temps si vous avez beaucoup de données
- Utilisez des filtres (status, date, etc.) pour limiter les résultats

### 2. Rate Limiting
- Zoho limite le nombre d'appels API par minute
- La pagination automatique respecte les limites mais peut prendre du temps

### 3. Memory
- Charger 10,000 tickets en mémoire peut être lourd
- Pour de très gros volumes, traitez par batch :

```python
# Traiter par batch de 100
from_index = 0
batch_size = 100

while True:
    response = desk_client.list_tickets(
        status="Open",
        from_index=from_index,
        limit=batch_size
    )
    tickets = response.get("data", [])

    if not tickets:
        break

    # Traiter ce batch
    for ticket in tickets:
        process_ticket(ticket)

    if len(tickets) < batch_size:
        break

    from_index += batch_size
```

---

## ✅ Checklist : Ai-je bien géré la pagination ?

Avant de lancer un script en production, vérifiez :

- [ ] J'utilise `list_all_tickets()` au lieu de `list_tickets()` ?
- [ ] J'utilise `search_all_deals()` au lieu de `search_deals()` ?
- [ ] J'utilise `_get_all_pages()` pour les endpoints custom ?
- [ ] Je log le nombre total d'éléments récupérés ?
- [ ] J'ai testé avec plus de 100/200 éléments ?

---

## 🚀 Exemples pratiques

### Valider TOUS les tickets ouverts

```python
from src.agents import TicketDispatcherAgent

dispatcher = TicketDispatcherAgent()

# ✅ Avec pagination automatique
result = dispatcher.batch_validate_departments(
    status="Open",
    use_pagination=True  # Récupère TOUS les tickets
)

print(f"Total vérifié : {result['total_checked']}")
print(f"À réaffecter : {result['should_reassign']}")
```

### Lier TOUS les tickets non liés à des deals

```python
from src.agents import DealLinkingAgent

linking_agent = DealLinkingAgent()

# ✅ Process ALL unlinked tickets
result = linking_agent.process_unlinked_tickets(
    status="Open",
    use_pagination=True,  # Important !
    create_bidirectional_link=True
)
```

---

## 📝 Résumé

**Règle d'or** : Par défaut, utilisez TOUJOURS les méthodes avec pagination automatique (`list_all_*`, `search_all_*`) sauf si vous avez une raison spécifique de ne pas le faire.

**Les méthodes avec pagination automatique sont disponibles dans :**
- ✅ `ZohoDeskClient.list_all_tickets()`
- ✅ `ZohoDeskClient._get_all_pages()` (helper générique)
- ✅ `ZohoCRMClient.search_all_deals()`
- ✅ `TicketDispatcherAgent.batch_validate_departments(use_pagination=True)`
- ✅ `DealLinkingAgent.process_unlinked_tickets(use_pagination=True)`

**Prochaine étape** : Vérifiez tous vos scripts et remplacez les appels simples par les versions avec pagination !
