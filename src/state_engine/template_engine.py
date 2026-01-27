"""
TemplateEngine - Génération contrôlée des réponses à partir de templates.

Ce module génère les réponses en combinant:
1. Des templates structurés (blocs fixes)
2. Des placeholders remplacés par des données réelles
3. Des sections IA contraintes (personnalisation uniquement)

L'IA n'intervient QUE pour la personnalisation, pas pour le contenu factuel.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .state_detector import DetectedState

logger = logging.getLogger(__name__)

# Chemin vers les templates
TEMPLATES_PATH = Path(__file__).parent.parent.parent / "states" / "templates"


class TemplateEngine:
    """
    Génère les réponses à partir des templates et de l'état détecté.

    Principes:
    1. Les données factuelles (dates, identifiants, etc.) viennent des placeholders
    2. L'IA génère UNIQUEMENT les sections de personnalisation
    3. La structure de la réponse est définie par le template
    """

    def __init__(self, templates_path: Optional[Path] = None):
        """
        Initialise le TemplateEngine.

        Args:
            templates_path: Chemin vers le dossier des templates (optionnel)
        """
        self.templates_path = templates_path or TEMPLATES_PATH
        self.templates_cache: Dict[str, str] = {}

        # S'assurer que le dossier existe
        self.templates_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"TemplateEngine initialisé avec templates_path={self.templates_path}")

    def generate_response(
        self,
        state: DetectedState,
        ai_generator: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Génère la réponse complète pour un état donné.

        Args:
            state: État détecté du candidat
            ai_generator: Fonction pour générer les sections IA (optionnel)

        Returns:
            {
                'response_text': str,
                'template_used': str,
                'placeholders_replaced': List[str],
                'ai_sections_generated': List[str],
                'alerts_included': List[str]
            }
        """
        response_config = state.response_config
        context = state.context_data

        # Déterminer le template à utiliser
        template_name = self._select_template(response_config, context)

        if not template_name:
            logger.warning(f"Pas de template pour l'état {state.name}")
            return self._generate_fallback_response(state, ai_generator)

        # Charger le template
        template_content = self._load_template(template_name)

        if not template_content:
            logger.warning(f"Template {template_name} non trouvé")
            return self._generate_fallback_response(state, ai_generator)

        # Préparer les données pour les placeholders
        placeholder_data = self._prepare_placeholder_data(state)

        # Remplacer les placeholders
        response_text, replaced = self._replace_placeholders(
            template_content, placeholder_data
        )

        # Générer les sections IA si nécessaire
        ai_sections = []
        ai_section_name = response_config.get('ai_section')
        if ai_section_name and ai_generator:
            ai_content = self._generate_ai_section(
                state, ai_section_name, ai_generator
            )
            if ai_content:
                response_text = response_text.replace(
                    f"{{{{{ai_section_name}}}}}", ai_content
                )
                ai_sections.append(ai_section_name)

        # Ajouter les alertes
        alerts_included = []
        for alert in state.alerts:
            alert_content = self._generate_alert_content(alert, context)
            if alert_content:
                response_text = self._insert_alert(
                    response_text, alert_content, alert.get('position', 'after_main')
                )
                alerts_included.append(alert.get('id', alert.get('type')))

        # Nettoyer les placeholders non remplacés
        response_text = self._cleanup_unresolved_placeholders(response_text)

        return {
            'response_text': response_text.strip(),
            'template_used': template_name,
            'placeholders_replaced': replaced,
            'ai_sections_generated': ai_sections,
            'alerts_included': alerts_included
        }

    def _select_template(
        self,
        response_config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[str]:
        """Sélectionne le template approprié selon les conditions."""
        # Vérifier les variantes conditionnelles
        variants = response_config.get('template_variants', [])
        for variant in variants:
            condition = variant.get('condition', '')
            if self._evaluate_template_condition(condition, context):
                return variant.get('template')

        # Template par défaut
        return response_config.get('template')

    def _evaluate_template_condition(
        self,
        condition: str,
        context: Dict[str, Any]
    ) -> bool:
        """Évalue une condition de sélection de template."""
        if not condition or condition == 'default':
            return True

        # Conditions simples
        if 'days_until_exam' in condition:
            days = context.get('days_until_exam')
            if days is None:
                return False

            if '>' in condition:
                threshold = int(re.search(r'>\s*(\d+)', condition).group(1))
                if '<=' in condition:
                    return days <= threshold
                return days > threshold
            elif '<' in condition:
                threshold = int(re.search(r'<\s*(\d+)', condition).group(1))
                if '>=' in condition:
                    return days >= threshold
                return days < threshold

        if 'can_modify_exam_date' in condition:
            can_modify = context.get('can_modify_exam_date', True)
            if '== true' in condition:
                return can_modify
            if '== false' in condition:
                return not can_modify

        if 'mentions_force_majeure' in condition:
            intent_context = context.get('intent_context', {})
            mentions = intent_context.get('mentions_force_majeure', False)
            if '== true' in condition:
                return mentions
            if '== false' in condition:
                return not mentions

        if 'evalbox' in condition:
            evalbox = context.get('evalbox', '')
            if '==' in condition:
                expected = condition.split('==')[1].strip().strip("'\"")
                return evalbox == expected

        return False

    def _load_template(self, template_name: str) -> Optional[str]:
        """Charge un template depuis le cache ou le fichier."""
        if template_name in self.templates_cache:
            return self.templates_cache[template_name]

        template_path = self.templates_path / template_name

        if not template_path.exists():
            # Essayer de créer un template par défaut
            default_content = self._create_default_template(template_name)
            if default_content:
                self.templates_cache[template_name] = default_content
                return default_content
            return None

        try:
            content = template_path.read_text(encoding='utf-8')
            self.templates_cache[template_name] = content
            return content
        except Exception as e:
            logger.error(f"Erreur lecture template {template_name}: {e}")
            return None

    def _create_default_template(self, template_name: str) -> Optional[str]:
        """Crée un template par défaut basé sur le nom."""
        # Templates par défaut pour les états courants
        default_templates = {
            'general_response.md': """Bonjour {{prenom}},

{{personnalisation}}

Bien cordialement,
L'équipe CAB Formations""",

            'propose_dates.md': """Bonjour {{prenom}},

{{personnalisation}}

Voici les prochaines dates d'examen disponibles :

{{dates_proposees}}

Merci de nous indiquer la date qui vous convient.

Bien cordialement,
L'équipe CAB Formations""",

            'identifiants_examt3p.md': """Bonjour {{prenom}},

{{personnalisation}}

Voici vos identifiants pour accéder à la plateforme ExamT3P :

**Identifiant :** {{identifiant_examt3p}}
**Mot de passe :** {{mot_de_passe_examt3p}}

🔗 Lien de connexion : https://www.intras.fr

⚠️ **Important** : Si vous ne trouvez pas l'email, vérifiez vos spams/courriers indésirables.

Bien cordialement,
L'équipe CAB Formations""",

            'convocation_received.md': """Bonjour {{prenom}},

{{personnalisation}}

Votre convocation pour l'examen du **{{date_examen_formatted}}** est disponible !

**Pour la télécharger :**
1. Connectez-vous sur https://www.intras.fr
2. Identifiant : {{identifiant_examt3p}}
3. Mot de passe : {{mot_de_passe_examt3p}}
4. Téléchargez et imprimez votre convocation

**Le jour de l'examen, n'oubliez pas :**
- Votre convocation imprimée
- Une pièce d'identité en cours de validité

Bonne chance ! 🍀

Bien cordialement,
L'équipe CAB Formations""",

            'confirmation_session.md': """Bonjour {{prenom}},

{{personnalisation}}

Votre choix de session a bien été enregistré :

**{{session_choisie}}**
Du {{date_debut_formation}} au {{date_fin_formation}}

Vous recevrez un email de rappel avant le début de la formation.

Bien cordialement,
L'équipe CAB Formations""",

            'statut_dossier.md': """Bonjour {{prenom}},

{{personnalisation}}

**Statut actuel de votre dossier :**

{{statut_actuel}}

{{prochaines_etapes}}

Bien cordialement,
L'équipe CAB Formations""",
        }

        return default_templates.get(template_name)

    def _prepare_placeholder_data(self, state: DetectedState) -> Dict[str, Any]:
        """Prépare les données pour remplacer les placeholders."""
        context = state.context_data
        deal_data = context.get('deal_data', {})
        examt3p_data = context.get('examt3p_data', {})

        # Extraire le prénom
        prenom = self._extract_prenom(deal_data)

        # Formater les dates
        date_examen = context.get('date_examen')
        date_examen_formatted = self._format_date(date_examen) if date_examen else ''

        # Préparer les dates proposées
        dates_proposees = self._format_dates_list(context.get('next_dates', []))

        # Préparer le statut actuel
        statut_actuel = self._format_statut(context.get('evalbox', ''))

        return {
            # Infos candidat
            'prenom': prenom or 'Bonjour',
            'nom': deal_data.get('Last_Name', ''),
            'email': deal_data.get('Email', ''),

            # Identifiants ExamT3P
            'identifiant_examt3p': examt3p_data.get('identifiant', ''),
            'mot_de_passe_examt3p': examt3p_data.get('mot_de_passe', ''),

            # Dates
            'date_examen': date_examen or '',
            'date_examen_formatted': date_examen_formatted,
            'date_cloture': context.get('date_cloture', ''),
            'dates_proposees': dates_proposees,

            # Session
            'session_choisie': self._format_session(deal_data.get('Session')),
            'date_debut_formation': '',
            'date_fin_formation': '',

            # Statut
            'statut_actuel': statut_actuel,
            'evalbox_status': context.get('evalbox', ''),
            'num_dossier_cma': examt3p_data.get('num_dossier', ''),

            # Prochaines étapes (à personnaliser selon l'état)
            'prochaines_etapes': self._get_prochaines_etapes(state),
        }

    def _extract_prenom(self, deal_data: Dict[str, Any]) -> str:
        """Extrait le prénom du candidat."""
        # Essayer Deal_Name qui contient souvent "PRÉNOM NOM"
        deal_name = deal_data.get('Deal_Name', '')
        if deal_name:
            parts = deal_name.split()
            if parts:
                return parts[0].capitalize()

        # Fallback sur First_Name
        return deal_data.get('First_Name', '')

    def _format_date(self, date_str: str) -> str:
        """Formate une date en DD/MM/YYYY."""
        if not date_str:
            return ''
        try:
            date_obj = datetime.strptime(str(date_str)[:10], '%Y-%m-%d')
            return date_obj.strftime('%d/%m/%Y')
        except:
            return str(date_str)

    def _format_dates_list(self, dates: List[Dict]) -> str:
        """Formate une liste de dates d'examen."""
        if not dates:
            return "Aucune date disponible pour le moment."

        lines = []
        for i, date_info in enumerate(dates[:5], 1):  # Max 5 dates
            date_str = date_info.get('Date_Examen', '')
            formatted = self._format_date(date_str)
            cloture = date_info.get('Date_Cloture_Inscription', '')
            cloture_formatted = self._format_date(cloture) if cloture else ''

            line = f"📅 **{formatted}**"
            if cloture_formatted:
                line += f" (clôture : {cloture_formatted})"

            lines.append(line)

        return "\n".join(lines)

    def _format_session(self, session: Any) -> str:
        """Formate les infos de session."""
        if not session:
            return ''
        if isinstance(session, dict):
            return session.get('name', '')
        return str(session)

    def _format_statut(self, evalbox: str) -> str:
        """Formate le statut Evalbox pour affichage."""
        statut_mapping = {
            'Dossier crée': '📝 Dossier en cours de création',
            'Pret a payer': '💳 Dossier prêt pour paiement CMA',
            'Dossier Synchronisé': '🔄 Dossier transmis à la CMA (instruction en cours)',
            'VALIDE CMA': '✅ Dossier validé par la CMA',
            'Convoc CMA reçue': '📨 Convocation disponible',
            'Refusé CMA': '❌ Document(s) refusé(s) par la CMA',
        }
        return statut_mapping.get(evalbox, f"📋 {evalbox}" if evalbox else "Statut inconnu")

    def _get_prochaines_etapes(self, state: DetectedState) -> str:
        """Génère les prochaines étapes selon l'état."""
        state_steps = {
            'EXAM_DATE_EMPTY': "Choisissez une date d'examen parmi celles proposées.",
            'DOSSIER_SYNCHRONIZED': "Surveillez vos emails pour la validation CMA.",
            'VALIDE_CMA_WAITING_CONVOC': "Votre convocation arrivera environ 10 jours avant l'examen.",
            'CONVOCATION_RECEIVED': "Téléchargez et imprimez votre convocation.",
            'READY_TO_PAY': "Le paiement CMA est en cours de traitement.",
        }
        return state_steps.get(state.name, "")

    def _replace_placeholders(
        self,
        template: str,
        data: Dict[str, Any]
    ) -> tuple:
        """Remplace les placeholders dans le template."""
        replaced = []
        result = template

        # Pattern pour les placeholders: {{placeholder_name}}
        pattern = r'\{\{(\w+)\}\}'

        for match in re.finditer(pattern, template):
            placeholder = match.group(1)
            if placeholder in data and data[placeholder]:
                result = result.replace(f"{{{{{placeholder}}}}}", str(data[placeholder]))
                replaced.append(placeholder)

        return result, replaced

    def _generate_ai_section(
        self,
        state: DetectedState,
        section_name: str,
        ai_generator: callable
    ) -> str:
        """Génère une section via l'IA."""
        response_config = state.response_config
        ai_instructions = response_config.get('ai_instructions', '')

        # Si c'est une section full_response, utiliser l'IA pour tout
        if section_name == 'full_response':
            return ai_generator(
                state=state,
                instructions=ai_instructions,
                max_length=500
            )

        # Sinon, générer juste la personnalisation
        return ai_generator(
            state=state,
            instructions=ai_instructions,
            max_length=100  # 2-3 phrases max
        )

    def _generate_alert_content(
        self,
        alert: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[str]:
        """Génère le contenu d'une alerte."""
        alert_type = alert.get('type', '')

        if alert_type == 'uber_case_d':
            return """
---
⚠️ **Information importante concernant votre compte Uber**

Nous avons constaté que l'adresse email utilisée pour votre inscription n'est pas reconnue par Uber comme un compte chauffeur actif.

Veuillez vérifier que vous utilisez la même adresse email que votre compte **Uber Driver** (pas Uber client). Si le problème persiste, contactez le support Uber via l'application.
---"""

        if alert_type == 'uber_case_e':
            return """
---
⚠️ **Information importante concernant votre éligibilité Uber**

Selon les informations d'Uber, votre profil n'est pas éligible à l'offre partenariat. Nous n'avons pas de visibilité sur les raisons de cette décision.

Nous vous invitons à contacter le support Uber via l'application **Uber Driver** (Compte → Aide) pour comprendre votre situation.
---"""

        return None

    def _insert_alert(
        self,
        response: str,
        alert_content: str,
        position: str = 'after_main'
    ) -> str:
        """Insère une alerte dans la réponse."""
        if position == 'before_signature':
            # Insérer avant "Bien cordialement"
            if 'Bien cordialement' in response:
                return response.replace(
                    'Bien cordialement',
                    f"{alert_content}\n\nBien cordialement"
                )

        # Par défaut, ajouter à la fin avant la signature
        return response.rstrip() + "\n" + alert_content

    def _cleanup_unresolved_placeholders(self, response: str) -> str:
        """Nettoie les placeholders non remplacés."""
        # Remplacer les placeholders vides par une chaîne vide
        cleaned = re.sub(r'\{\{\w+\}\}', '', response)
        # Nettoyer les lignes vides multiples
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned

    def _generate_fallback_response(
        self,
        state: DetectedState,
        ai_generator: Optional[callable]
    ) -> Dict[str, Any]:
        """Génère une réponse de fallback quand pas de template."""
        # Utiliser le template général
        general_template = self._create_default_template('general_response.md')
        placeholder_data = self._prepare_placeholder_data(state)

        response_text, replaced = self._replace_placeholders(
            general_template or "Bonjour,\n\n{{personnalisation}}\n\nBien cordialement,\nL'équipe CAB Formations",
            placeholder_data
        )

        # Générer la personnalisation via IA
        ai_sections = []
        if ai_generator:
            ai_content = ai_generator(
                state=state,
                instructions="Répondre de manière contextuelle au candidat.",
                max_length=300
            )
            if ai_content:
                response_text = response_text.replace("{{personnalisation}}", ai_content)
                ai_sections.append('personnalisation')

        return {
            'response_text': self._cleanup_unresolved_placeholders(response_text),
            'template_used': 'fallback',
            'placeholders_replaced': replaced,
            'ai_sections_generated': ai_sections,
            'alerts_included': []
        }
