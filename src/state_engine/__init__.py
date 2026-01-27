"""
State Engine - Architecture State-Driven pour le workflow DOC.

Ce package implémente une architecture où:
1. L'état du candidat est déterminé de manière DÉTERMINISTE (code, pas IA)
2. Les templates de réponse sont contrôlés par l'état
3. Les mises à jour CRM sont déterministes (pas d'interprétation IA)
4. La validation est stricte par état

Composants:
- StateDetector: Détecte l'état du candidat à partir des données
- TemplateEngine: Génère les réponses à partir des templates
- ResponseValidator: Valide les réponses générées
- CRMUpdater: Applique les mises à jour CRM de manière déterministe
"""

from .state_detector import StateDetector
from .template_engine import TemplateEngine
from .response_validator import ResponseValidator
from .crm_updater import CRMUpdater

__all__ = [
    'StateDetector',
    'TemplateEngine',
    'ResponseValidator',
    'CRMUpdater'
]
