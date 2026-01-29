# Agents Reference

## Vue d'ensemble

Les agents sont des composants IA spécialisés utilisant Claude (Anthropic).

| Agent | Modèle | Rôle |
|-------|--------|------|
| TriageAgent | Haiku | Triage tickets (GO/ROUTE/SPAM) + détection intention |
| CRMUpdateAgent | - | Mises à jour CRM avec validation |
| DealLinkingAgent | - | Liaison ticket↔deal |
| ExamT3PAgent | - | Extraction données ExamT3P |
| TicketDispatcherAgent | - | Routage vers départements |

---

## 1. TriageAgent

**Fichier :** `src/agents/triage_agent.py`
**Premier dans le workflow** - Agent IA pour triage intelligent des tickets.

### Signature
```python
from src.agents.triage_agent import TriageAgent

agent = TriageAgent()

# SIGNATURE CORRECTE (NE PAS passer ticket_id seul!)
result = agent.triage_ticket(
    ticket_subject="Re: Test de sélection réussi",
    thread_content="Je souhaiterais la session du matin...",
    deal_data=deal_data,  # Optionnel, dict CRM
    current_department="DOC"
)
```

### Structure retournée
```python
{
    'action': 'GO' | 'ROUTE' | 'SPAM' | 'DUPLICATE_UBER' | 'NEEDS_CLARIFICATION',
    'target_department': 'DOC' | 'Contact' | 'Comptabilité' | etc,
    'detected_intent': 'DEMANDE_DATES_FUTURES',     # Intention principale
    'primary_intent': 'DEMANDE_DATES_FUTURES',      # Alias
    'secondary_intents': ['QUESTION_SESSION'],       # Intentions secondaires
    'reason': 'Explication du choix',
    'confidence': 0.95,
    'intent_context': {
        'is_urgent': bool,
        'mentions_force_majeure': bool,
        'force_majeure_type': 'medical' | 'death' | 'accident' | 'childcare' | 'other' | None,
        'force_majeure_details': 'description courte' | None,
        'wants_earlier_date': bool,
        'session_preference': 'jour' | 'soir' | None
    }
}
```

### Actions possibles
| Action | Comportement |
|--------|--------------|
| `GO` | Ticket DOC valide, continuer le workflow |
| `ROUTE` | Transférer vers autre département |
| `SPAM` | Spam/pub, clôturer automatiquement |
| `DUPLICATE_UBER` | Doublon offre Uber 20€ |
| `NEEDS_CLARIFICATION` | Besoin de clarification |

### Extraction automatique de contexte
- `session_preference` : Extrait "jour" ou "soir" si le candidat le mentionne
- `force_majeure_type` : Détecte "medical", "death", "accident", "childcare"
- `wants_earlier_date` : Détecte si le candidat veut une date plus tôt

### ATTENTION - Extraction de l'intention
```python
# CORRECT
intention = result.get("detected_intent")
session_pref = result.get("intent_context", {}).get("session_preference")

# FAUX (ne pas utiliser)
# intention = result.get("intent_context", {}).get("intention")  # N'EXISTE PAS!
```

---

## 2. CRMUpdateAgent

**Fichier :** `src/agents/crm_update_agent.py`
**Recommandé** - Agent spécialisé pour TOUTES les mises à jour CRM.

### Fonctionnalités
- Mapping automatique string → ID pour les champs lookup
- Respect des règles de blocage (VALIDE CMA + clôture passée)
- Note CRM optionnelle

### Signature
```python
from src.agents.crm_update_agent import CRMUpdateAgent

agent = CRMUpdateAgent()

result = agent.update_from_ticket_response(
    deal_id="123456",
    ai_updates={
        'Date_examen_VTC': '2026-03-31',
        'Session_choisie': 'Cours du soir'
    },
    deal_data=deal_data,
    session_data=session_data,  # Sessions proposées par session_helper
    ticket_id="789012",
    auto_add_note=False  # Note consolidée gérée par le workflow
)
```

### Mappings automatiques
| Champ | Entrée | Transformation |
|-------|--------|----------------|
| `Date_examen_VTC` | Date string ("2026-03-31") | ID session via `find_exam_session_by_date_and_dept()` |
| `Session_choisie` | Nom ("Cours du soir") | ID en cherchant dans sessions proposées |
| `Preference_horaire` | Texte ("soir") | Pas de mapping |

### Règles de blocage
**Refuse de modifier `Date_examen_VTC` si :**
- Evalbox ∈ {"VALIDE CMA", "Convoc CMA reçue"}
- ET `Date_Cloture_Inscription` < aujourd'hui

---

## 3. DealLinkingAgent

**Fichier :** `src/agents/deal_linking_agent.py`
Lie les tickets Zoho Desk aux deals CRM.

### Signature
```python
from src.agents.deal_linking_agent import DealLinkingAgent

agent = DealLinkingAgent()
result = agent.process({"ticket_id": "123456"})
```

### Structure retournée
```python
{
    'deal_id': '123456789',
    'deal_data': { ... },           # Données complètes du deal
    'all_deals': [ ... ],           # Tous les deals du contact
    'has_duplicate_uber_offer': bool,  # Doublon détecté
    'duplicate_deals': [ ... ],     # Deals en doublon si applicable
    'routing_info': {
        'should_route': bool,
        'target_department': 'Contact' | None,
        'reason': '...'
    }
}
```

### Détection de doublon Uber 20€
```python
# L'agent détecte automatiquement les doublons
deals_20_won = [d for d in all_deals if d.get("Amount") == 20 and d.get("Stage") == "GAGNÉ"]
if len(deals_20_won) > 1:
    result["has_duplicate_uber_offer"] = True
    result["duplicate_deals"] = deals_20_won
```

---

## 4. ExamT3PAgent

**Fichier :** `src/agents/examt3p_agent.py`
Extrait les données de la plateforme ExamT3P.

### Signature
```python
from src.agents.examt3p_agent import ExamT3PAgent

agent = ExamT3PAgent()
data = agent.extract_data(identifiant, mot_de_passe)
```

### Structure retournée
```python
{
    'compte_existe': True,
    'connection_test_success': True,
    'statut_dossier': 'En cours de composition',
    'num_dossier': '00038886',
    'documents': [
        {'name': 'CNI', 'status': 'validé'},
        {'name': 'Photo', 'status': 'en attente'}
    ],
    'paiements': [
        {'date': '2026-01-15', 'montant': 241, 'status': 'payé'}
    ],
    'examens': [ ... ],
    'departement': '75'
}
```

### Gestion des erreurs
- Si connexion échoue → `connection_test_success = False`
- Si compte n'existe pas → `compte_existe = False`
- Workflow continue même si ExamT3P indisponible

---

## 5. TicketDispatcherAgent

**Fichier :** `src/agents/dispatcher_agent.py`
Route les tickets vers le bon département.

### Signature
```python
from src.agents.dispatcher_agent import TicketDispatcherAgent

agent = TicketDispatcherAgent()
result = agent.dispatch(ticket_id, target_department="Contact")
```

### Départements disponibles
Voir `desk_departments.json` pour la liste complète :
- DOC, DOCS CAB, Contact, Comptabilité, Refus CMA, etc.

---

## 6. BaseAgent (Classe abstraite)

**Fichier :** `src/agents/base_agent.py`
Classe de base pour tous les agents.

### Méthode principale
```python
class BaseAgent:
    def ask(self, prompt: str, system_prompt: str = None) -> str:
        """Appelle Claude avec le prompt donné."""
        pass
```

### Modèle utilisé
Défini dans `config.py` : `claude-sonnet-4-5-20250929`
(Haiku pour les tâches légères comme le triage)

---

## Bonnes Pratiques

### 1. Ne pas passer ticket_id seul au TriageAgent
```python
# FAUX
result = agent.triage_ticket(ticket_id)

# CORRECT
result = agent.triage_ticket(
    ticket_subject=ticket['subject'],
    thread_content=threads_content,
    deal_data=deal_data
)
```

### 2. Toujours utiliser CRMUpdateAgent pour les mises à jour
```python
# FAUX - mapping manuel
crm_client.update_deal(deal_id, {'Date_examen_VTC': '2026-03-31'})

# CORRECT - mapping automatique + validation
agent.update_from_ticket_response(
    deal_id=deal_id,
    ai_updates={'Date_examen_VTC': '2026-03-31'},
    deal_data=deal_data
)
```

### 3. Vérifier le résultat du DealLinkingAgent
```python
result = agent.process({"ticket_id": ticket_id})

if result.get('has_duplicate_uber_offer'):
    # Traitement spécial doublon Uber
    pass

if result.get('routing_info', {}).get('should_route'):
    # Router vers autre département
    pass
```
