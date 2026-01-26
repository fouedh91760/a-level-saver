"""
TriageAgent - Agent IA pour le triage intelligent des tickets.

Remplace le système de keywords par une analyse contextuelle avec Claude.
Comprend le SENS du message, pas juste les mots-clés.

UTILISATION:
    agent = TriageAgent()
    result = agent.triage_ticket(
        ticket_subject="Form submission from: Assistance",
        thread_content="J'ai téléchargé tous les documents...",
        deal_data=deal_data  # Optionnel
    )
    # Retourne: action (GO/ROUTE/SPAM), target_department, reason, confidence
"""
import logging
from typing import Dict, Any, Optional
import json

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
   - Demandes de changement de date
   - Questions sur le dossier en cours

3. **ROUTE vers Refus CMA** SEULEMENT si:
   - Le candidat signale que la CMA a REFUSÉ son dossier
   - OU deal_data.Evalbox == "Refusé CMA" ou "Documents manquants"
   - NE PAS router si le candidat dit juste "j'ai envoyé mes documents"

4. **ROUTE vers Contact** si:
   - Demande d'information sur une NOUVELLE formation
   - Questions sur le prix, les modalités d'inscription
   - Pas de dossier en cours (pas de deal)

IMPORTANT:
- Le mot "document" ne signifie PAS automatiquement Refus CMA
- "J'ai téléchargé mes documents" = GO (confirmation d'envoi)
- "Mon document a été refusé" = ROUTE vers Refus CMA
- Comprends le CONTEXTE, pas juste les mots-clés

Réponds UNIQUEMENT en JSON valide:
{
    "action": "GO" | "ROUTE" | "SPAM",
    "target_department": "DOC" | "Refus CMA" | "Contact" | "Comptabilité" | null,
    "reason": "explication courte",
    "confidence": 0.0-1.0
}
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
        Analyse un ticket et détermine l'action de triage.

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
                'method': 'ai'
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
                    'method': 'rule_evalbox'
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

            result = json.loads(response_text)

            # Valider et normaliser
            action = result.get('action', 'GO').upper()
            if action not in ['GO', 'ROUTE', 'SPAM']:
                action = 'GO'

            target_dept = result.get('target_department')
            if action == 'GO':
                target_dept = current_department

            return {
                'action': action,
                'target_department': target_dept,
                'reason': result.get('reason', 'Analyse IA'),
                'confidence': float(result.get('confidence', 0.8)),
                'method': 'ai'
            }

        except json.JSONDecodeError as e:
            logger.warning(f"  ⚠️ TriageAgent JSON error: {e}")
            # Fallback: rester dans le département actuel
            return {
                'action': 'GO',
                'target_department': current_department,
                'reason': 'Erreur parsing IA - fallback GO',
                'confidence': 0.5,
                'method': 'fallback'
            }

        except Exception as e:
            logger.error(f"  ❌ TriageAgent error: {e}")
            # Fallback: rester dans le département actuel
            return {
                'action': 'GO',
                'target_department': current_department,
                'reason': f'Erreur IA: {str(e)[:50]} - fallback GO',
                'confidence': 0.3,
                'method': 'fallback'
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
