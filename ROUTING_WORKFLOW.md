# 🔄 Workflow de Routing Correct

## ❌ Ancien Workflow (INCORRECT)

```
Ticket → Routing (keywords) → Deal Linking → Traitement
```

**Problème** : Le routing ne peut pas utiliser le deal pour déterminer le département, donc il se base uniquement sur les keywords du ticket, ce qui peut être imprécis.

---

## ✅ Nouveau Workflow (CORRECT)

```
Ticket → Deal Linking → Routing (deal + keywords) → Traitement → Update CRM
```

### Étape 1 : Deal Linking Agent
- Cherche le deal CRM associé au ticket
- Critères : email, téléphone, account, custom fields
- **Résultat** : Deal trouvé avec toutes ses données (Deal_Name, Stage, Amount, etc.)

### Étape 2 : Routing Agent (Dispatcher)
**Priorité 1 - Deal-based routing** (`BusinessRules.get_department_from_deal()`) :
- Si deal trouvé → Détermine département selon le deal
  - Uber €20 → DOC
  - CAB/Capacité → DOCS CAB
  - CMA Closed Lost → Refus CMA
  - CMA autres stages → Inscription CMA
  - Deal sans règle spécifique → Contact

**Priorité 2 - Keyword-based routing** (fallback) :
- Si pas de deal OU deal sans règle → Utilise `get_department_routing_rules()`
- Analyse mots-clés du sujet/description
- Exemple : "examen", "convocation" → DOC

**Priorité 3 - AI analysis** :
- Si aucune règle ne matche → Analyse AI

### Étape 3 : Process Ticket
- Traite le ticket dans le bon département
- Génère réponse automatique si configuré

### Étape 4 : Update CRM
- Met à jour le deal avec contexte du ticket
- Ajoute des notes automatiques

---

## 📋 Implémentation

### 1. BusinessRules.py

Nouvelle méthode ajoutée :

```python
@staticmethod
def get_department_from_deal(deal: Dict[str, Any]) -> Optional[str]:
    """
    Détermine le département basé sur le deal CRM (PRIORITAIRE).

    Retourne le nom du département ou None (fallback sur keywords).
    """
    deal_name = deal.get("Deal_Name", "").lower()
    stage = deal.get("Stage", "")
    amount = deal.get("Amount", 0)

    # Uber €20 deals → DOC
    if "uber" in deal_name and amount == 20:
        return "DOC"

    # CAB / Capacité deals → DOCS CAB
    if "cab" in deal_name or "capacité" in deal_name:
        return "DOCS CAB"

    # CMA deals selon stage
    if "cma" in deal_name:
        if stage == "Closed Lost":
            return "Refus CMA"
        else:
            return "Inscription CMA"

    # Deal trouvé sans règle → Contact
    return "Contact"
```

### 2. Dispatcher Agent (src/agents/dispatcher_agent.py)

Mise à jour de la méthode `process()` :

```python
def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
    ticket_id = data.get("ticket_id")
    deal = data.get("deal")  # NEW: Deal from DealLinkingAgent

    # Step 1: Check deal first (PRIORITY)
    if deal:
        deal_based_department = BusinessRules.get_department_from_deal(deal)
        if deal_based_department:
            return {
                "recommended_department": deal_based_department,
                "routing_method": "deal",
                "confidence": 98,
                ...
            }

    # Step 2: Fallback to keywords
    rule_based_department = self._check_routing_rules(ticket, routing_rules)
    if rule_based_department:
        return {
            "recommended_department": rule_based_department,
            "routing_method": "business_rules",
            "confidence": 95,
            ...
        }

    # Step 3: AI analysis
    ai_result = self._analyze_with_ai(ticket)
    return {
        "recommended_department": ai_result["department"],
        "routing_method": "ai_analysis",
        ...
    }
```

### 3. Orchestrator (src/orchestrator.py)

Mise à jour de `process_ticket_complete_workflow()` :

```python
def process_ticket_complete_workflow(self, ticket_id, ...):
    # Step 1: Deal linking FIRST
    linking_result = self.deal_linking_agent.process({
        "ticket_id": ticket_id
    })

    deal = linking_result.get("deal")  # Get full deal data

    # Step 2: Routing with deal context
    dispatch_result = self.dispatcher_agent.process({
        "ticket_id": ticket_id,
        "deal": deal,  # Pass deal to dispatcher
        "auto_reassign": auto_dispatch
    })

    # Step 3: Process ticket
    ticket_result = self.desk_agent.process(...)

    # Step 4: Update CRM
    if deal_id:
        crm_result = self.crm_agent.process_with_ticket(...)
```

### 4. Deal Linking Agent (src/agents/deal_linking_agent.py)

Mise à jour pour retourner le deal complet :

```python
return {
    "success": True,
    "deal_found": True,
    "deal_id": deal_id,
    "deal": deal,  # NEW: Return full deal for routing
    ...
}
```

---

## 🎯 Avantages du Nouveau Workflow

1. **Routing basé sur le deal = Plus précis**
   - Un client avec deal Uber €20 → toujours DOC
   - Un client avec CMA refusé → toujours Refus CMA
   - Pas besoin de mots-clés dans le sujet

2. **Fallback intelligent**
   - Si pas de deal → keywords
   - Si keywords ne matchent pas → AI
   - Toujours une solution

3. **Traçabilité**
   - Le champ `routing_method` indique comment le routing a été fait
   - "deal" = basé sur le deal CRM
   - "business_rules" = basé sur keywords
   - "ai_analysis" = basé sur AI

4. **Cohérence métier**
   - Le département est déterminé par le contexte commercial
   - Un même client sera toujours routé au même département pour un même type de deal

---

## 📝 Exemples Réels

### Exemple 1 : Client avec deal Uber €20

**Ticket** : "Question sur ma formation"

**Sans deal-based routing** :
- Keywords : "formation" → peut matcher plusieurs départements (DOC, Pédagogie)
- Résultat : Incertain

**Avec deal-based routing** :
1. Deal trouvé : "Uber €20 - Mohammed Talbi"
2. Deal_Name contient "Uber" + Amount = 20
3. **Routing : DOC** (confiance 98%)
4. Résultat : Précis et cohérent

### Exemple 2 : Client avec CMA refusé

**Ticket** : "Pourquoi mon dossier a été refusé ?"

**Sans deal-based routing** :
- Keywords : "dossier", "refusé" → peut matcher Contact ou Inscription CMA
- Résultat : Peut aller dans le mauvais département

**Avec deal-based routing** :
1. Deal trouvé : "CMA - Registration - Ahmed Benali"
2. Stage = "Closed Lost"
3. Deal_Name contient "CMA" + Stage = "Closed Lost"
4. **Routing : Refus CMA** (confiance 98%)
5. Résultat : Va directement au département qui gère les refus

### Exemple 3 : Nouveau client sans deal

**Ticket** : "Je veux m'inscrire pour l'examen VTC"

**Workflow** :
1. Deal linking : Aucun deal trouvé
2. **Fallback sur keywords** : "examen", "vtc" → DOC
3. **Routing : DOC** (confiance 95%)
4. Résultat : Keywords fonctionnent bien pour nouveaux clients

---

## ⚙️ Configuration Actuelle

### Départements configurés avec deal-based routing :

- **DOC** : Uber €20, A-Level, VTC, Formation
- **DOCS CAB** : CAB, Capacité
- **Inscription CMA** : CMA (stages actifs)
- **Refus CMA** : CMA (Closed Lost)
- **Contact** : Deal trouvé sans règle spécifique

### Mots-clés configurés (fallback) :

**DOC** : examen, inscription, formation, convocation, test, dossier, rappel, demande, sélection, admissibilité, épreuve, vtc, passage, réussi, théorique, pratique

(Basés sur l'analyse de 100 tickets réels de Fouad depuis 01/11/2025)

---

## 🧪 Tests Recommandés

1. **Test avec deal Uber €20** → Doit router vers DOC
2. **Test avec deal CMA Closed Lost** → Doit router vers Refus CMA
3. **Test sans deal avec keywords** → Doit utiliser keywords
4. **Test sans deal sans keywords** → Doit utiliser AI

Voir : `test_routing_workflow.py` (à créer)

---

## 📚 Références

- `business_rules.py` : Configuration des règles métier
- `src/agents/dispatcher_agent.py` : Agent de routing
- `src/agents/deal_linking_agent.py` : Agent de linking
- `src/orchestrator.py` : Orchestration du workflow complet
- `fouad_tickets_analysis.json` : Analyse de 100 tickets pour définir les keywords
