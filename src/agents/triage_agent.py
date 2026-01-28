"""
TriageAgent - Agent IA pour le triage intelligent des tickets.

Remplace le système de keywords par une analyse contextuelle avec Claude.
Comprend le SENS du message, pas juste les mots-clés.
Détecte également l'INTENTION du candidat pour un traitement approprié.

UTILISATION:
    agent = TriageAgent()
    result = agent.triage_ticket(
        ticket_subject="Form submission from: Assistance",
        thread_content="J'ai téléchargé tous les documents...",
        deal_data=deal_data  # Optionnel
    )
    # Retourne: action, target_department, reason, confidence, detected_intent, intent_context
"""
import logging
from typing import Dict, Any, Optional
import json
from pathlib import Path

# Load environment variables for Anthropic API key
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TriageAgent(BaseAgent):
    """Agent IA pour le triage intelligent des tickets CAB Formations."""

    SYSTEM_PROMPT = """Tu es un expert du triage de tickets pour CAB Formations, un centre de formation VTC.

CONTEXTE MÉTIER:
- CAB Formations prépare les candidats à l'examen VTC (théorique)
- Partenariat Uber: offre à 20€ pour les chauffeurs Uber
- Processus: Inscription → Formation → Examen CMA → Obtention carte VTC

DÉPARTEMENTS DISPONIBLES:
- DOC: Questions sur formation, examen, dates, sessions, identifiants ExamT3P (département par défaut pour candidats Uber 20€)
- Refus CMA: UNIQUEMENT si la CMA a REFUSÉ un document (statut Evalbox = "Refusé CMA" ou "Documents manquants")
- Contact: Demandes commerciales, autres formations, questions générales non liées à un dossier en cours
- Comptabilité: Factures, remboursements, paiements

RÈGLES DE TRIAGE:

1. **SPAM** → Messages publicitaires, phishing, sans rapport avec la formation

2. **GO (rester dans DOC)** pour:
   - Candidat qui CONFIRME avoir envoyé ses documents (même s'il dit "document")
   - Candidat qui fournit ses identifiants ExamT3P
   - Questions sur dates d'examen, sessions de formation
   - Demandes de changement de date / report
   - Questions sur le dossier en cours

3. **ROUTE vers Refus CMA** SEULEMENT si:
   - Le candidat signale que la CMA a REFUSÉ son dossier
   - OU deal_data.Evalbox == "Refusé CMA" ou "Documents manquants"
   - NE PAS router si le candidat dit juste "j'ai envoyé mes documents"

4. **ROUTE vers Contact** si:
   - Demande d'information sur une NOUVELLE formation
   - Questions sur le prix, les modalités d'inscription
   - Pas de dossier en cours (pas de deal)
   - Demande de suppression de données (RGPD, droit à l'oubli, destruction données)

IMPORTANT:
- Le mot "document" ne signifie PAS automatiquement Refus CMA
- "J'ai téléchargé mes documents" = GO (confirmation d'envoi)
- "Mon document a été refusé" = ROUTE vers Refus CMA
- Comprends le CONTEXTE, pas juste les mots-clés

---

DÉTECTION D'INTENTIONS (TOUTES, pas seulement la principale):

Quand l'action est GO, tu dois identifier TOUTES les intentions exprimées par le candidat.
Un candidat peut avoir PLUSIEURS intentions dans un même message - c'est très fréquent !

INTENTIONS POSSIBLES (par ordre de spécificité - préfère les intentions spécifiques):

**Intentions liées aux DATES D'EXAMEN:**
- DEMANDE_DATES_FUTURES: Demande de dates d'examen disponibles
  Exemples: "Quelles sont les prochaines dates ?", "dates disponibles", "dates pour juillet", "dates à Montpellier"
- REPORT_DATE: Veut CHANGER sa date d'examen actuelle
  Exemples: "Je voudrais reporter", "changer ma date", "décaler mon examen"
- DEMANDE_AUTRES_DEPARTEMENTS: Veut voir des dates dans d'autres villes/départements
  Exemples: "dates ailleurs", "autre département", "dates à Lyon", "d'autres options"

**Intentions liées à la FORMATION:**
- QUESTION_SESSION: Question sur les sessions de formation (cours du soir/jour)
  Exemples: "cours du soir", "formation du jour", "horaires de formation", "infos sur les cours"
- CONFIRMATION_SESSION: CONFIRME son choix de session
  Exemples: "je choisis cours du soir", "je prends l'option 2", "je confirme la formation du jour"

**Intentions liées au DOSSIER:**
- STATUT_DOSSIER: Question sur l'avancement
  Exemples: "où en est mon dossier", "mon inscription", "avancement", "statut"
- DOCUMENT_QUESTION: Question sur les documents
  Exemples: "quels documents", "pièces à fournir", "document manquant"
- CONFIRMATION_PAIEMENT: Question sur le paiement
  Exemples: "j'ai payé", "confirmation de paiement", "facture"

**Intentions liées aux IDENTIFIANTS:**
- DEMANDE_IDENTIFIANTS: Demande d'identifiants ExamT3P
  Exemples: "mot de passe oublié", "mes identifiants", "connexion ExamT3P"
- REFUS_PARTAGE_CREDENTIALS: Refuse de partager ses identifiants (sécurité)
  Exemples: "je ne veux pas donner mon mot de passe", "données personnelles", "RGPD"

**Autres intentions:**
- RESULTAT_EXAMEN: Question sur le résultat
  Exemples: "résultat de l'examen", "ai-je réussi", "admis ou pas"
- QUESTION_PROCESSUS: Question sur le processus
  Exemples: "comment ça marche", "prochaines étapes", "c'est quoi la suite"
- DEMANDE_SUPPRESSION_DONNEES: Demande RGPD de suppression
  Exemples: "supprimer mes données", "droit à l'oubli"
- QUESTION_GENERALE: UNIQUEMENT si aucune intention spécifique ne correspond
  ⚠️ N'utilise QUESTION_GENERALE que si tu ne peux vraiment pas classifier autrement !

**EXEMPLES DE MULTI-INTENTIONS (très fréquent):**
- "Je voudrais les dates de Montpellier pour juillet et des infos sur les cours du soir"
  → primary_intent: DEMANDE_DATES_FUTURES, secondary_intents: ["QUESTION_SESSION"]
- "Où en est mon dossier ? Et quand est mon examen ?"
  → primary_intent: STATUT_DOSSIER, secondary_intents: ["DEMANDE_DATES_FUTURES"]
- "Je confirme le cours du soir. C'est quoi les prochaines étapes ?"
  → primary_intent: CONFIRMATION_SESSION, secondary_intents: ["QUESTION_PROCESSUS"]
- "Y a-t-il des dates plus tôt dans d'autres départements ?"
  → primary_intent: DEMANDE_DATES_FUTURES, secondary_intents: ["DEMANDE_AUTRES_DEPARTEMENTS"]

Pour REPORT_DATE, ajoute un contexte supplémentaire:
- is_urgent: true si examen imminent (< 7 jours) ou mention d'urgence
- mentions_force_majeure: true si le candidat mentionne un motif de force majeure
- force_majeure_type: "medical" (maladie, hospitalisation, santé), "death" (décès, deuil), "accident", "other", ou null

MOTIFS DE FORCE MAJEURE:
IMPORTANT: La force majeure doit affecter DIRECTEMENT le candidat ou un membre de sa famille proche.
Si c'est un problème indirect (ex: l'assistante maternelle qui a un décès dans SA famille), ce n'est PAS
une force majeure du candidat mais une contrainte de garde d'enfant → force_majeure_type = "childcare" ou "other"

- Medical: maladie DU CANDIDAT, hospitalisation, problème de santé, opération, certificat médical, douleurs, enceinte, accouchement
- Death: décès d'un PROCHE DU CANDIDAT (parent, conjoint, enfant, frère/sœur) - PAS décès chez la nounou/voisin/etc.
- Accident: accident DU CANDIDAT (voiture, travail, etc.)
- Childcare: problème de garde d'enfant (nounou absente, assistante maternelle indisponible, etc.)
- Other: convocation judiciaire, catastrophe naturelle, autre contrainte personnelle

Pour force_majeure_details, préciser QUI est affecté (le candidat directement ou quelqu'un d'autre).

CONTEXTE SUPPLÉMENTAIRE (pour toutes les intentions):
- wants_earlier_date: true si le candidat demande une date plus tôt, plus proche, plus rapide,
  ou s'il mentionne vouloir un autre département, d'autres options, toutes les dates disponibles,
  ou une urgence particulière (pressé, au plus vite, rapidement, etc.)

---

Réponds UNIQUEMENT en JSON valide:
{
    "action": "GO" | "ROUTE" | "SPAM",
    "target_department": "DOC" | "Refus CMA" | "Contact" | "Comptabilité" | null,
    "reason": "explication courte",
    "confidence": 0.0-1.0,
    "primary_intent": "REPORT_DATE" | "DEMANDE_IDENTIFIANTS" | "STATUT_DOSSIER" | "CONFIRMATION_SESSION" | "DEMANDE_DATES_FUTURES" | "QUESTION_SESSION" | "QUESTION_GENERALE" | ... | null,
    "secondary_intents": ["QUESTION_SESSION", "DEMANDE_DATES_FUTURES", ...],
    "intent_context": {
        "is_urgent": true | false,
        "mentions_force_majeure": true | false,
        "force_majeure_type": "medical" | "death" | "accident" | "childcare" | "other" | null,
        "force_majeure_details": "description courte si force majeure détectée" | null,
        "wants_earlier_date": true | false,
        "session_preference": "jour" | "soir" | null
    }
}

IMPORTANT: Si le candidat exprime plusieurs intentions, liste l'intention principale dans primary_intent
et les autres dans secondary_intents (array, peut être vide).

Pour CONFIRMATION_SESSION, extraire la préférence:
- "jour" si le candidat mentionne: cours du jour, formation du jour, journée, matin
- "soir" si le candidat mentionne: cours du soir, formation du soir, soirée, après le travail
"""

    def __init__(self):
        super().__init__(
            name="TriageAgent",
            system_prompt=self.SYSTEM_PROMPT
        )

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Interface standard pour le traitement (requis par BaseAgent).

        Args:
            data: {
                'ticket_subject': str,
                'thread_content': str,
                'deal_data': Dict (optionnel),
                'current_department': str (optionnel)
            }

        Returns:
            Résultat du triage
        """
        return self.triage_ticket(
            ticket_subject=data.get('ticket_subject', ''),
            thread_content=data.get('thread_content', ''),
            deal_data=data.get('deal_data'),
            current_department=data.get('current_department', 'DOC')
        )

    def triage_ticket(
        self,
        ticket_subject: str,
        thread_content: str,
        deal_data: Optional[Dict[str, Any]] = None,
        current_department: str = "DOC"
    ) -> Dict[str, Any]:
        """
        Analyse un ticket et détermine l'action de triage + intention du candidat.

        Args:
            ticket_subject: Sujet du ticket
            thread_content: Contenu du dernier message du client
            deal_data: Données du deal CRM (optionnel)
            current_department: Département actuel du ticket

        Returns:
            {
                'action': 'GO' | 'ROUTE' | 'SPAM',
                'target_department': str ou None,
                'reason': str,
                'confidence': float,
                'method': 'ai',
                'detected_intent': str ou None (REPORT_DATE, DEMANDE_IDENTIFIANTS, etc.),
                'intent_context': {
                    'is_urgent': bool,
                    'mentions_force_majeure': bool,
                    'force_majeure_type': str ou None,
                    'force_majeure_details': str ou None
                }
            }
        """
        # Construire le contexte pour l'IA
        context_parts = [
            f"**Sujet du ticket:** {ticket_subject}",
            f"**Message du client:**\n{thread_content[:2000]}",  # Limiter la taille
            f"**Département actuel:** {current_department}"
        ]

        # Ajouter les infos du deal si disponibles
        if deal_data:
            deal_info = [
                f"**Deal trouvé:** {deal_data.get('Deal_Name', 'N/A')}",
                f"**Montant:** {deal_data.get('Amount', 'N/A')}€",
                f"**Stage:** {deal_data.get('Stage', 'N/A')}",
                f"**Evalbox:** {deal_data.get('Evalbox', 'N/A')}"
            ]
            context_parts.append("\n".join(deal_info))

            # Règle automatique: Si Evalbox indique un refus → Refus CMA
            evalbox = deal_data.get('Evalbox', '')
            if evalbox in ['Refusé CMA', 'Documents manquants', 'Documents refusés']:
                logger.info(f"  🔍 Evalbox = '{evalbox}' → Route automatique vers Refus CMA")
                return {
                    'action': 'ROUTE',
                    'target_department': 'Refus CMA',
                    'reason': f"Evalbox indique: {evalbox}",
                    'confidence': 1.0,
                    'method': 'rule_evalbox',
                    'primary_intent': None,
                    'secondary_intents': [],
                    'detected_intent': None,
                    'intent_context': {}
                }

        context = "\n\n".join(context_parts)

        # Appeler Claude pour l'analyse
        try:
            from anthropic import Anthropic

            client = Anthropic()
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",  # Modèle rapide pour le triage
                max_tokens=500,
                system=self.SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": f"Analyse ce ticket et détermine l'action de triage:\n\n{context}"}
                ]
            )

            response_text = response.content[0].text.strip()
            logger.info(f"  🤖 TriageAgent response: {response_text[:200]}...")

            # Parser la réponse JSON
            # Nettoyer le JSON si nécessaire
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            # Extraire uniquement le JSON (ignorer le texte après)
            # Chercher le premier { et le dernier } correspondant
            start_idx = response_text.find('{')
            if start_idx != -1:
                brace_count = 0
                end_idx = start_idx
                for i, char in enumerate(response_text[start_idx:], start_idx):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i + 1
                            break
                response_text = response_text[start_idx:end_idx]

            result = json.loads(response_text)

            # Valider et normaliser
            action = result.get('action', 'GO').upper()
            if action not in ['GO', 'ROUTE', 'SPAM']:
                action = 'GO'

            target_dept = result.get('target_department')
            if action == 'GO':
                target_dept = current_department

            # Extraire les intentions (support multi-intentions)
            primary_intent = result.get('primary_intent') or result.get('detected_intent')
            secondary_intents = result.get('secondary_intents', [])
            intent_context = result.get('intent_context', {})

            # Normaliser intent_context et secondary_intents
            if not isinstance(intent_context, dict):
                intent_context = {}
            if not isinstance(secondary_intents, list):
                secondary_intents = []

            # Log les intentions détectées
            if primary_intent:
                logger.info(f"  🎯 Intention principale: {primary_intent}")
            if secondary_intents:
                logger.info(f"  🎯 Intentions secondaires: {secondary_intents}")
            if intent_context.get('mentions_force_majeure'):
                logger.info(f"  ⚠️ Force majeure mentionnée: {intent_context.get('force_majeure_type')} - {intent_context.get('force_majeure_details', 'N/A')}")
            if intent_context.get('is_urgent'):
                logger.info(f"  🚨 Situation urgente détectée")

            return {
                'action': action,
                'target_department': target_dept,
                'reason': result.get('reason', 'Analyse IA'),
                'confidence': float(result.get('confidence', 0.8)),
                'method': 'ai',
                # Multi-intentions
                'primary_intent': primary_intent,
                'secondary_intents': secondary_intents,
                # Rétrocompatibilité
                'detected_intent': primary_intent,
                'intent_context': intent_context
            }

        except json.JSONDecodeError as e:
            logger.warning(f"  ⚠️ TriageAgent JSON error: {e}")
            # Fallback: rester dans le département actuel
            return {
                'action': 'GO',
                'target_department': current_department,
                'reason': 'Erreur parsing IA - fallback GO',
                'confidence': 0.5,
                'method': 'fallback',
                'primary_intent': None,
                'secondary_intents': [],
                'detected_intent': None,
                'intent_context': {}
            }

        except Exception as e:
            logger.error(f"  ❌ TriageAgent error: {e}")
            # Fallback: rester dans le département actuel
            return {
                'action': 'GO',
                'target_department': current_department,
                'reason': f'Erreur IA: {str(e)[:50]} - fallback GO',
                'confidence': 0.3,
                'method': 'fallback',
                'primary_intent': None,
                'secondary_intents': [],
                'detected_intent': None,
                'intent_context': {}
            }

    def should_use_ai_triage(
        self,
        ticket_subject: str,
        thread_content: str
    ) -> bool:
        """
        Détermine si on doit utiliser le triage IA ou les règles simples.

        Pour économiser les appels API, on utilise l'IA seulement si:
        - Le contenu contient des mots ambigus (document, etc.)
        - Le sujet n'est pas clairement identifiable

        Returns:
            True si triage IA recommandé
        """
        combined = (ticket_subject + " " + thread_content).lower()

        # Mots ambigus qui nécessitent une analyse contextuelle
        ambiguous_words = [
            'document', 'pièce', 'justificatif', 'fichier',
            'envoyé', 'téléchargé', 'uploadé', 'joint'
        ]

        # Si mots ambigus présents → IA
        if any(word in combined for word in ambiguous_words):
            return True

        # Sinon, les règles simples suffisent
        return False
