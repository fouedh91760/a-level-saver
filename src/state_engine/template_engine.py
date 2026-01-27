"""
TemplateEngine - Génération contrôlée des réponses à partir de templates.

Ce module génère les réponses en combinant:
1. Des templates structurés (blocs fixes) depuis states/templates/base/
2. Des blocs réutilisables depuis states/blocks/
3. Des placeholders remplacés par des données réelles
4. Des sections IA contraintes (personnalisation uniquement)

Syntaxe Handlebars supportée:
- {{variable}} : Remplacement de variable
- {{> bloc_name}} : Inclusion de bloc (partial)
- {{#if condition}}...{{else}}...{{/if}} : Conditionnel
- {{#unless condition}}...{{/unless}} : Conditionnel inverse
- {{#each items}}...{{/each}} : Boucle

L'IA n'intervient QUE pour la personnalisation, pas pour le contenu factuel.
"""

import logging
import re
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .state_detector import DetectedState

logger = logging.getLogger(__name__)

# Chemins vers les ressources
STATES_PATH = Path(__file__).parent.parent.parent / "states"
TEMPLATES_BASE_PATH = STATES_PATH / "templates" / "base"
BLOCKS_PATH = STATES_PATH / "blocks"
MATRIX_PATH = STATES_PATH / "state_intention_matrix.yaml"


class TemplateEngine:
    """
    Génère les réponses à partir des templates et de l'état détecté.

    Architecture:
    1. Charge state_intention_matrix.yaml pour blocks_registry et base_templates
    2. Sélectionne le template de base selon l'état (via for_evalbox, for_uber_case, etc.)
    3. Charge les blocs depuis states/blocks/
    4. Parse la syntaxe Handlebars ({{> partial}}, {{#if}}, etc.)
    5. Remplace les placeholders par les données réelles
    """

    def __init__(self, states_path: Optional[Path] = None):
        """
        Initialise le TemplateEngine.

        Args:
            states_path: Chemin vers le dossier states (optionnel)
        """
        self.states_path = states_path or STATES_PATH
        self.templates_base_path = self.states_path / "templates" / "base"
        self.blocks_path = self.states_path / "blocks"
        self.matrix_path = self.states_path / "state_intention_matrix.yaml"

        # Caches
        self.templates_cache: Dict[str, str] = {}
        self.blocks_cache: Dict[str, str] = {}

        # Charger la matrice état×intention
        self.matrix = self._load_matrix()
        self.blocks_registry = self.matrix.get('blocks_registry', {})
        self.base_templates = self.matrix.get('base_templates', {})

        logger.info(f"TemplateEngine initialisé: {len(self.blocks_registry)} blocs, {len(self.base_templates)} templates")

    def _load_matrix(self) -> Dict[str, Any]:
        """Charge state_intention_matrix.yaml."""
        try:
            if self.matrix_path.exists():
                with open(self.matrix_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            else:
                logger.warning(f"Matrice non trouvée: {self.matrix_path}")
                return {}
        except Exception as e:
            logger.error(f"Erreur chargement matrice: {e}")
            return {}

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
                'alerts_included': List[str],
                'blocks_included': List[str]
            }
        """
        context = state.context_data

        # 1. Sélectionner le template de base approprié
        template_key, template_config = self._select_base_template(state, context)

        if not template_key:
            logger.warning(f"Pas de template pour l'état {state.name}, utilisation fallback")
            return self._generate_fallback_response(state, ai_generator)

        # 2. Charger le template
        template_file = template_config.get('file', f'templates/base/{template_key}.html')
        template_content = self._load_template(template_file)

        if not template_content:
            logger.warning(f"Template {template_file} non trouvé, utilisation fallback")
            return self._generate_fallback_response(state, ai_generator)

        # 3. Préparer les données pour les placeholders et conditions
        placeholder_data = self._prepare_placeholder_data(state)

        # 4. Parser et résoudre le template (partials, conditionnels, boucles)
        blocks_included = []
        response_text = self._parse_template(template_content, placeholder_data, blocks_included)

        # 5. Remplacer les placeholders simples restants
        response_text, replaced = self._replace_placeholders(response_text, placeholder_data)

        # 6. Générer les sections IA si nécessaire
        ai_sections = []
        response_config = state.response_config
        ai_section_name = response_config.get('ai_section')
        if ai_section_name and ai_generator and f"{{{{{ai_section_name}}}}}" in response_text:
            ai_content = self._generate_ai_section(state, ai_section_name, ai_generator)
            if ai_content:
                response_text = response_text.replace(f"{{{{{ai_section_name}}}}}", ai_content)
                ai_sections.append(ai_section_name)

        # 7. Ajouter les alertes
        alerts_included = []
        for alert in state.alerts:
            alert_content = self._generate_alert_content(alert, context)
            if alert_content:
                response_text = self._insert_alert(
                    response_text, alert_content, alert.get('position', 'before_signature')
                )
                alerts_included.append(alert.get('id', alert.get('type')))

        # 8. Nettoyer
        response_text = self._cleanup_unresolved_placeholders(response_text)
        response_text = self._strip_comments(response_text)

        return {
            'response_text': response_text.strip(),
            'template_used': template_key,
            'template_file': template_file,
            'placeholders_replaced': replaced,
            'ai_sections_generated': ai_sections,
            'alerts_included': alerts_included,
            'blocks_included': blocks_included
        }

    def _select_base_template(
        self,
        state: DetectedState,
        context: Dict[str, Any]
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Sélectionne le template de base approprié selon l'état et le contexte.

        Ordre de priorité:
        1. Intention + condition (ex: DEMANDE_IDENTIFIANTS + compte_existe)
        2. Condition seule (ex: has_duplicate_uber_offer)
        3. Cas Uber (A, B, D, E)
        4. Résultat examen (Admis, Non admis)
        5. Evalbox (statut du dossier)
        6. Fallback par nom d'état
        """
        evalbox = context.get('evalbox', '')
        uber_case = self._determine_uber_case(context)
        resultat = context.get('deal_data', {}).get('Resultat', '')
        intention = context.get('detected_intent', '')

        # PASS 1: Templates avec intention (priorité haute)
        for template_key, config in self.base_templates.items():
            if 'for_intention' in config:
                if intention == config['for_intention']:
                    # Vérifier aussi la condition si elle existe
                    if 'for_condition' in config:
                        if not self._evaluate_condition(config['for_condition'], context):
                            continue  # Condition non satisfaite, passer au suivant
                    return template_key, config

        # PASS 2: Templates avec condition seule (sans intention)
        for template_key, config in self.base_templates.items():
            if 'for_condition' in config and 'for_intention' not in config:
                if self._evaluate_condition(config['for_condition'], context):
                    return template_key, config

        # PASS 3: Cas Uber
        for template_key, config in self.base_templates.items():
            if 'for_uber_case' in config:
                if uber_case == config['for_uber_case']:
                    return template_key, config

        # PASS 4: Résultat examen
        for template_key, config in self.base_templates.items():
            if 'for_resultat' in config:
                if resultat == config['for_resultat']:
                    return template_key, config

        # PASS 5: Evalbox (le plus courant)
        for template_key, config in self.base_templates.items():
            if 'for_evalbox' in config:
                if evalbox == config['for_evalbox']:
                    return template_key, config

        # Fallback: chercher par nom d'état normalisé
        state_name_normalized = state.name.lower().replace('_', '-')
        for template_key, config in self.base_templates.items():
            if template_key.lower() == state_name_normalized:
                return template_key, config

        return None, {}

    def _determine_uber_case(self, context: Dict[str, Any]) -> str:
        """Détermine le cas Uber (A, B, D, E, ELIGIBLE, NOT_UBER)."""
        if not context.get('is_uber_20_deal'):
            return 'NOT_UBER'

        if not context.get('date_dossier_recu'):
            return 'A'

        if not context.get('compte_uber', True):
            return 'D'

        if not context.get('eligible_uber', True):
            return 'E'

        if not context.get('date_test_selection'):
            return 'B'

        return 'ELIGIBLE'

    def _load_template(self, template_path: str) -> Optional[str]:
        """Charge un template depuis le cache ou le fichier."""
        if template_path in self.templates_cache:
            return self.templates_cache[template_path]

        # Construire le chemin complet
        full_path = self.states_path / template_path

        if not full_path.exists():
            # Essayer avec le path direct
            full_path = self.templates_base_path / Path(template_path).name
            if not full_path.exists():
                logger.warning(f"Template non trouvé: {template_path}")
                return None

        try:
            content = full_path.read_text(encoding='utf-8')
            # Nettoyer le contenu: supprimer commentaires HTML et espaces inutiles
            content = self._clean_block_content(content)
            self.templates_cache[template_path] = content
            return content
        except Exception as e:
            logger.error(f"Erreur lecture template {template_path}: {e}")
            return None

    def _load_block(self, block_name: str) -> Optional[str]:
        """Charge un bloc depuis le cache ou le fichier."""
        if block_name in self.blocks_cache:
            return self.blocks_cache[block_name]

        # Chercher dans le registry
        block_config = self.blocks_registry.get(block_name, {})
        block_file = block_config.get('file', f'blocks/{block_name}.md')

        # Construire le chemin
        full_path = self.states_path / block_file

        if not full_path.exists():
            # Essayer avec le path direct dans blocks/
            full_path = self.blocks_path / f"{block_name}.md"
            if not full_path.exists():
                logger.warning(f"Bloc non trouvé: {block_name}")
                return None

        try:
            content = full_path.read_text(encoding='utf-8')
            # Nettoyer le contenu: supprimer commentaires HTML et espaces inutiles
            content = self._clean_block_content(content)
            self.blocks_cache[block_name] = content
            return content
        except Exception as e:
            logger.error(f"Erreur lecture bloc {block_name}: {e}")
            return None

    def _clean_block_content(self, content: str) -> str:
        """Nettoie le contenu d'un bloc en supprimant commentaires et espaces inutiles."""
        import re
        # Supprimer les commentaires HTML (<!-- ... -->)
        content = re.sub(r'<!--.*?-->\s*', '', content, flags=re.DOTALL)
        # Supprimer les lignes vides multiples
        content = re.sub(r'\n\s*\n', '\n', content)
        # Supprimer les espaces en début et fin
        content = content.strip()
        return content

    def _parse_template(
        self,
        template: str,
        context: Dict[str, Any],
        blocks_included: List[str]
    ) -> str:
        """
        Parse le template et résout les partials, conditionnels, boucles.

        Ordre de traitement:
        1. {{> partial}} - Inclusion de blocs
        2. {{#if}}...{{else}}...{{/if}} - Conditionnels
        3. {{#unless}}...{{/unless}} - Conditionnels inverses
        4. {{#each}}...{{/each}} - Boucles
        """
        result = template

        # 1. Résoudre les partials ({{> bloc_name}})
        result = self._resolve_partials(result, context, blocks_included)

        # 2. Résoudre les conditionnels {{#if}}
        result = self._resolve_if_blocks(result, context)

        # 3. Résoudre les conditionnels inverses {{#unless}}
        result = self._resolve_unless_blocks(result, context)

        # 4. Résoudre les boucles {{#each}}
        result = self._resolve_each_blocks(result, context)

        return result

    def _resolve_partials(
        self,
        template: str,
        context: Dict[str, Any],
        blocks_included: List[str]
    ) -> str:
        """Résout les {{> bloc_name}} en chargeant et injectant les blocs."""
        result = template

        # Pattern pour {{> bloc_name}}
        pattern = r'\{\{>\s*(\w+)\s*\}\}'

        while True:
            match = re.search(pattern, result)
            if not match:
                break

            block_name = match.group(1)
            block_content = self._load_block(block_name)

            if block_content:
                # Résoudre récursivement les partials dans le bloc
                block_content = self._resolve_partials(block_content, context, blocks_included)
                # Résoudre les conditionnels dans le bloc
                block_content = self._resolve_if_blocks(block_content, context)
                block_content = self._resolve_unless_blocks(block_content, context)

                result = result[:match.start()] + block_content + result[match.end():]
                blocks_included.append(block_name)
            else:
                # Bloc non trouvé, supprimer le placeholder
                logger.warning(f"Bloc {block_name} non trouvé, suppression du placeholder")
                result = result[:match.start()] + result[match.end():]

        return result

    def _resolve_if_blocks(self, template: str, context: Dict[str, Any]) -> str:
        """Résout les {{#if condition}}...{{else}}...{{/if}} avec support des blocs imbriqués."""
        result = template

        # Traiter les blocs de l'intérieur vers l'extérieur
        # en cherchant les blocs {{#if}} qui ne contiennent pas d'autres {{#if}}
        max_iterations = 100  # Sécurité contre les boucles infinies

        for _ in range(max_iterations):
            # Chercher un {{#if}} dont le contenu ne contient pas d'autres {{#if}}
            # Pattern: {{#if var}} (contenu sans {{#if}}) {{/if}} ou avec {{else}}
            pattern = r'\{\{#if\s+(\w+)\s*\}\}((?:(?!\{\{#if)(?!\{\{#unless).)*?)(?:\{\{else\}\}((?:(?!\{\{#if)(?!\{\{#unless).)*?))?\{\{/if\}\}'

            match = re.search(pattern, result, re.DOTALL)
            if not match:
                break

            condition_var = match.group(1)
            if_content = match.group(2) or ''
            else_content = match.group(3) or ''

            # Évaluer la condition
            condition_value = self._get_context_value(condition_var, context)

            if condition_value:
                replacement = if_content
            else:
                replacement = else_content

            result = result[:match.start()] + replacement + result[match.end():]

        return result

    def _resolve_unless_blocks(self, template: str, context: Dict[str, Any]) -> str:
        """Résout les {{#unless condition}}...{{else}}...{{/unless}}."""
        result = template

        pattern = r'\{\{#unless\s+(\w+)\s*\}\}(.*?)(?:\{\{else\}\}(.*?))?\{\{/unless\}\}'

        while True:
            match = re.search(pattern, result, re.DOTALL)
            if not match:
                break

            condition_var = match.group(1)
            unless_content = match.group(2) or ''
            else_content = match.group(3) or ''

            # Évaluer la condition (inversée pour unless)
            condition_value = self._get_context_value(condition_var, context)

            if not condition_value:
                replacement = unless_content
            else:
                replacement = else_content

            result = result[:match.start()] + replacement + result[match.end():]

        return result

    def _resolve_each_blocks(self, template: str, context: Dict[str, Any]) -> str:
        """Résout les {{#each items}}...{{/each}}."""
        result = template

        pattern = r'\{\{#each\s+(\w+)\s*\}\}(.*?)\{\{/each\}\}'

        while True:
            match = re.search(pattern, result, re.DOTALL)
            if not match:
                break

            items_var = match.group(1)
            item_template = match.group(2)

            items = self._get_context_value(items_var, context)

            if items and isinstance(items, list):
                rendered_items = []
                for item in items:
                    rendered_item = item_template
                    # Remplacer {{this.property}} ou {{this}}
                    if isinstance(item, dict):
                        for key, value in item.items():
                            rendered_item = rendered_item.replace(f"{{{{this.{key}}}}}", str(value))
                    else:
                        rendered_item = rendered_item.replace("{{this}}", str(item))
                    rendered_items.append(rendered_item)
                replacement = ''.join(rendered_items)
            else:
                replacement = ''

            result = result[:match.start()] + replacement + result[match.end():]

        return result

    def _get_context_value(self, key: str, context: Dict[str, Any]) -> Any:
        """Récupère une valeur du contexte, avec support des clés imbriquées."""
        # Mapping des variables de template vers le contexte
        # Variables booléennes courantes
        if key == 'uber_20':
            return context.get('is_uber_20_deal', False)
        if key == 'can_choose_other_department':
            return not context.get('compte_existe', True)
        if key == 'session_choisie':
            return context.get('session_assigned', False)
        if key == 'compte_existe':
            return context.get('compte_existe', False)
        if key == 'identifiant_examt3p':
            return context.get('examt3p_data', {}).get('identifiant', '')
        if key == 'mot_de_passe_examt3p':
            return context.get('examt3p_data', {}).get('mot_de_passe', '')

        # Mapping prochaines_dates depuis next_dates
        if key == 'prochaines_dates':
            next_dates = context.get('next_dates', [])
            if next_dates:
                formatted_dates = []
                for d in next_dates[:5]:  # Limiter à 5 dates
                    date_str = d.get('Date_Examen', '')
                    date_formatted = self._format_date(date_str) if date_str else ''
                    cloture_str = d.get('Date_Cloture_Inscription', '')
                    cloture_formatted = self._format_date(cloture_str) if cloture_str else ''
                    formatted_dates.append({
                        'date': date_formatted,
                        'departement': d.get('Departement', ''),
                        'cloture': cloture_formatted
                    })
                return formatted_dates
            return []

        # Chercher directement dans le contexte
        if key in context:
            return context[key]

        # Chercher dans deal_data
        deal_data = context.get('deal_data', {})
        if key in deal_data:
            return deal_data[key]

        # Chercher dans examt3p_data
        examt3p_data = context.get('examt3p_data', {})
        if key in examt3p_data:
            return examt3p_data[key]

        return None

    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Évalue une condition de type 'variable == value'."""
        if '==' in condition:
            parts = condition.split('==')
            if len(parts) == 2:
                var_name = parts[0].strip()
                expected = parts[1].strip().strip("'\"")
                actual = self._get_context_value(var_name, context)

                if expected.lower() == 'true':
                    return actual == True
                if expected.lower() == 'false':
                    return actual == False
                return str(actual) == expected

        return False

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

        # Département
        departement = context.get('departement', '')

        # Préparer les dates proposées
        dates_proposees = self._format_dates_list(context.get('next_dates', []))

        # Préparer le statut actuel
        statut_actuel = self._format_statut(context.get('evalbox', ''))

        # Calculer la date de convocation (environ 10 jours avant l'examen)
        date_convocation = ''
        if date_examen:
            try:
                from datetime import timedelta
                exam_date = datetime.strptime(date_examen, '%Y-%m-%d')
                convoc_date = exam_date - timedelta(days=10)
                date_convocation = convoc_date.strftime('%d/%m/%Y')
            except:
                pass

        return {
            # Infos candidat
            'prenom': prenom or 'Bonjour',
            'nom': deal_data.get('Last_Name', ''),
            'email': deal_data.get('Email', ''),

            # Identifiants ExamT3P
            'identifiant_examt3p': examt3p_data.get('identifiant', ''),
            'mot_de_passe_examt3p': examt3p_data.get('mot_de_passe', ''),

            # Dates
            'date_examen': date_examen_formatted or '',
            'date_examen_raw': date_examen or '',
            'date_examen_formatted': date_examen_formatted,
            'date_cloture': self._format_date(context.get('date_cloture', '')) if context.get('date_cloture') else '',
            'date_convocation': date_convocation,
            'dates_proposees': dates_proposees,

            # Département
            'departement': departement,

            # Session - utilise les données du legacy session_helper
            # Le legacy fournit la logique (quelles sessions proposer), le State Engine formate l'affichage
            'session_choisie': self._format_session(deal_data.get('Session')),
            'session_message': context.get('session_data', {}).get('message', ''),
            'session_preference': context.get('session_data', {}).get('session_preference', ''),
            'session_preference_soir': context.get('session_data', {}).get('session_preference') == 'soir',
            'session_preference_jour': context.get('session_data', {}).get('session_preference') == 'jour',
            # Données aplaties pour itération facile dans les templates
            'sessions_proposees': self._flatten_session_options(context.get('session_data', {})),
            'date_debut_formation': '',
            'date_fin_formation': '',

            # Statut
            'statut_actuel': statut_actuel,
            'evalbox_status': context.get('evalbox', ''),
            'num_dossier_cma': examt3p_data.get('num_dossier', ''),

            # Numéro de dossier
            'num_dossier': examt3p_data.get('num_dossier', '') or context.get('num_dossier', ''),

            # Prochaines étapes
            'prochaines_etapes': self._get_prochaines_etapes(state),

            # Booléens pour les conditions (aussi disponibles comme placeholders)
            'uber_20': context.get('is_uber_20_deal', False),
            'can_choose_other_department': context.get('can_choose_other_department', False) or not context.get('compte_existe', True),
            'session_assigned': context.get('session_assigned', False),
            'compte_existe': context.get('compte_existe', False),
            'can_modify_exam_date': context.get('can_modify_exam_date', True),
            'cloture_passed': context.get('cloture_passed', False),

            # Force majeure (pour les templates empathiques)
            'mentions_force_majeure': context.get('mentions_force_majeure', False),
            'force_majeure_type': context.get('force_majeure_type'),
            'force_majeure_details': context.get('force_majeure_details', ''),
            'is_force_majeure_deces': context.get('is_force_majeure_deces', False),
            'is_force_majeure_medical': context.get('is_force_majeure_medical', False),
            'is_force_majeure_accident': context.get('is_force_majeure_accident', False),
            'is_force_majeure_childcare': context.get('is_force_majeure_childcare', False),
            'is_force_majeure_other': context.get('is_force_majeure_other', False),
        }

    def _extract_prenom(self, deal_data: Dict[str, Any]) -> str:
        """Extrait le prénom du candidat."""
        first_name = deal_data.get('First_Name', '')
        if first_name and first_name.strip():
            return first_name.strip().capitalize()

        deal_name = deal_data.get('Deal_Name', '')
        if deal_name:
            internal_codes = {'BFS', 'NP', 'CPF', 'UBER', 'VISIO', 'PRES', 'TEST', 'VIP'}
            parts = deal_name.split()
            for part in parts:
                if part.upper() in internal_codes:
                    continue
                if len(part) <= 3 and part.isupper():
                    continue
                return part.capitalize()

        return ''

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
        """Formate une liste de dates d'examen en HTML."""
        if not dates:
            return "<p>Aucune date disponible pour le moment.</p>"

        lines = []
        for i, date_info in enumerate(dates[:5], 1):
            date_str = date_info.get('Date_Examen', '')
            formatted = self._format_date(date_str)
            dept = date_info.get('Departement', '')
            cloture = date_info.get('Date_Cloture_Inscription', '')
            cloture_formatted = self._format_date(cloture) if cloture else ''

            line = f"<li><b>{formatted}</b> (département {dept})"
            if cloture_formatted:
                line += f" - clôture : {cloture_formatted}"
            line += "</li>"
            lines.append(line)

        return f"<ul>{''.join(lines)}</ul>"

    def _format_session(self, session: Any) -> str:
        """Formate les infos de session."""
        if not session:
            return ''
        if isinstance(session, dict):
            return session.get('name', '')
        return str(session)

    def _flatten_session_options(self, session_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transforme les proposed_options du legacy session_helper en format plat
        utilisable facilement par les templates Handlebars.

        Input (legacy format):
            proposed_options: [
                {
                    'exam_info': {'Date_Examen': '2026-03-31', 'Departement': '75', ...},
                    'sessions': [
                        {'Name': 'cds-janvier', 'Date_d_but': '...', 'Date_fin': '...', 'session_type': 'soir', ...}
                    ]
                }
            ]

        Output (template format):
            [
                {
                    'date_examen': '31/03/2026',
                    'departement': '75',
                    'cloture': '15/03/2026',
                    'nom': 'Cours du soir - Janvier 2026',
                    'debut': '15/01/2026',
                    'fin': '25/01/2026',
                    'type': 'soir',
                    'horaires': '18h-22h'
                }
            ]
        """
        flattened = []
        proposed_options = session_data.get('proposed_options', [])

        for option in proposed_options:
            exam_info = option.get('exam_info', {})
            sessions = option.get('sessions', [])

            # Formater les dates d'examen
            date_examen = exam_info.get('Date_Examen', '')
            date_examen_formatted = self._format_date(date_examen) if date_examen else ''
            cloture = exam_info.get('Date_Cloture_Inscription', '')
            cloture_formatted = self._format_date(cloture) if cloture else ''
            departement = exam_info.get('Departement', '')

            for session in sessions:
                session_type = session.get('session_type', '')
                session_type_label = session.get('session_type_label', '')

                # Extraire les dates de la session
                date_debut = session.get('Date_d_but', '')
                date_fin = session.get('Date_fin', '')
                date_debut_formatted = self._format_date(date_debut) if date_debut else ''
                date_fin_formatted = self._format_date(date_fin) if date_fin else ''

                # Extraire les horaires si disponibles
                horaires = session.get('Type_de_cours', '')
                if isinstance(horaires, dict):
                    horaires = horaires.get('name', '')

                flattened.append({
                    'date_examen': date_examen_formatted,
                    'date_examen_raw': date_examen,
                    'departement': departement,
                    'cloture': cloture_formatted,
                    'nom': session_type_label or session.get('Name', ''),
                    'session_name': session.get('Name', ''),
                    'session_id': session.get('id', ''),
                    'debut': date_debut_formatted,
                    'fin': date_fin_formatted,
                    'type': session_type,
                    'horaires': horaires,
                    'is_jour': session_type == 'jour',
                    'is_soir': session_type == 'soir',
                })

        return flattened

    def _format_statut(self, evalbox: str) -> str:
        """Formate le statut Evalbox pour affichage."""
        statut_mapping = {
            'Dossier crée': 'Dossier en cours de création',
            'Pret a payer': 'Dossier prêt pour paiement CMA',
            'Dossier Synchronisé': 'Dossier transmis à la CMA (instruction en cours)',
            'VALIDE CMA': 'Dossier validé par la CMA',
            'Convoc CMA reçue': 'Convocation disponible',
            'Refusé CMA': 'Document(s) refusé(s) par la CMA',
        }
        return statut_mapping.get(evalbox, evalbox or "Statut inconnu")

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
    ) -> Tuple[str, List[str]]:
        """Remplace les placeholders simples {{variable}} dans le template."""
        replaced = []
        result = template

        # Pattern pour les placeholders: {{placeholder_name}}
        pattern = r'\{\{(\w+)\}\}'

        for match in re.finditer(pattern, template):
            placeholder = match.group(1)
            # Ignorer les blocs spéciaux (personnalisation, etc.)
            if placeholder in ['personnalisation', 'full_response']:
                continue
            if placeholder in data and data[placeholder]:
                value = data[placeholder]
                # Ne pas convertir les booléens en string ici (déjà gérés par conditionnels)
                if not isinstance(value, bool):
                    result = result.replace(f"{{{{{placeholder}}}}}", str(value))
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

        if section_name == 'full_response':
            return ai_generator(
                state=state,
                instructions=ai_instructions,
                max_length=500
            )

        return ai_generator(
            state=state,
            instructions=ai_instructions,
            max_length=100
        )

    def _generate_alert_content(
        self,
        alert: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[str]:
        """Génère le contenu HTML d'une alerte."""
        alert_type = alert.get('type', '')

        if alert_type == 'uber_case_d':
            return """
<hr>
<p><b>Information importante concernant votre compte Uber</b></p>
<p>Nous avons constaté que l'adresse email utilisée pour votre inscription n'est pas reconnue par Uber comme un compte chauffeur actif.</p>
<p>Veuillez vérifier que vous utilisez la même adresse email que votre compte <b>Uber Driver</b> (pas Uber client). Si le problème persiste, contactez le support Uber via l'application.</p>
<hr>"""

        if alert_type == 'uber_case_e':
            return """
<hr>
<p><b>Information importante concernant votre éligibilité Uber</b></p>
<p>Selon les informations d'Uber, votre profil n'est pas éligible à l'offre partenariat. Nous n'avons pas de visibilité sur les raisons de cette décision.</p>
<p>Nous vous invitons à contacter le support Uber via l'application <b>Uber Driver</b> (Compte → Aide) pour comprendre votre situation.</p>
<hr>"""

        return None

    def _insert_alert(
        self,
        response: str,
        alert_content: str,
        position: str = 'before_signature'
    ) -> str:
        """Insère une alerte dans la réponse HTML."""
        if position == 'before_signature':
            # Chercher la signature (bloc signature ou "Bien cordialement")
            signature_patterns = [
                r'(<p[^>]*>.*?(?:cordialement|équipe cab).*?</p>)',
                r'(Bien cordialement)',
                r'(L\'équipe CAB)',
            ]
            for pattern in signature_patterns:
                match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
                if match:
                    return response[:match.start()] + alert_content + "\n" + response[match.start():]

        # Fallback: ajouter à la fin
        return response.rstrip() + "\n" + alert_content

    def _cleanup_unresolved_placeholders(self, response: str) -> str:
        """Nettoie les placeholders non remplacés."""
        # Supprimer les placeholders vides (sauf personnalisation qu'on garde pour debug)
        cleaned = re.sub(r'\{\{(?!personnalisation)\w+\}\}', '', response)
        # Nettoyer les lignes vides multiples
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        # Nettoyer les paragraphes vides
        cleaned = re.sub(r'<p>\s*</p>', '', cleaned)
        return cleaned

    def _strip_comments(self, response: str) -> str:
        """Supprime les commentaires HTML du texte final."""
        # Supprimer les commentaires <!-- ... -->
        cleaned = re.sub(r'<!--.*?-->', '', response, flags=re.DOTALL)
        # Nettoyer les lignes vides multiples
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        return cleaned.strip()

    def _generate_fallback_response(
        self,
        state: DetectedState,
        ai_generator: Optional[callable]
    ) -> Dict[str, Any]:
        """Génère une réponse de fallback quand pas de template."""
        placeholder_data = self._prepare_placeholder_data(state)
        prenom = placeholder_data.get('prenom', 'Bonjour')

        fallback_template = f"""<p>Bonjour {prenom},</p>

<p>{{{{personnalisation}}}}</p>

<p>Bien cordialement,<br>
L'équipe CAB Formations</p>"""

        response_text = fallback_template
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
            'template_file': None,
            'placeholders_replaced': ['prenom'],
            'ai_sections_generated': ai_sections,
            'alerts_included': [],
            'blocks_included': []
        }
