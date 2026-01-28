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

from .state_detector import DetectedState, DetectedStates

logger = logging.getLogger(__name__)

# Chemins vers les ressources
STATES_PATH = Path(__file__).parent.parent.parent / "states"
TEMPLATES_BASE_PATH = STATES_PATH / "templates" / "base_legacy"  # Migrated to partials
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
        self.templates_base_path = self.states_path / "templates" / "base_legacy"  # Migrated to partials
        self.blocks_path = self.states_path / "blocks"
        self.matrix_path = self.states_path / "state_intention_matrix.yaml"

        # Caches
        self.templates_cache: Dict[str, str] = {}
        self.blocks_cache: Dict[str, str] = {}

        # Charger la matrice état×intention
        self.matrix = self._load_matrix()
        self.blocks_registry = self.matrix.get('blocks_registry', {})
        self.base_templates = self.matrix.get('base_templates', {})
        self.state_intention_matrix = self.matrix.get('matrix', {})

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

    def generate_response_multi(
        self,
        detected_states: DetectedStates,
        triage_result: Dict[str, Any],
        ai_generator: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Génère une réponse composite gérant multi-intentions et multi-états.

        Args:
            detected_states: Tous les états détectés (blocking, warning, info)
            triage_result: Résultat du triage avec primary_intent et secondary_intents
            ai_generator: Fonction pour générer les sections IA (optionnel)

        Returns:
            {
                'response_text': str,
                'template_used': str,
                'states_used': List[str],
                'intents_handled': List[str],
                ...
            }
        """
        # 1. Si état BLOCKING → réponse unique (comportement actuel)
        if detected_states.blocking_state:
            logger.info(f"🚫 État BLOCKING détecté - réponse unique pour {detected_states.blocking_state.name}")
            result = self.generate_response(detected_states.blocking_state, ai_generator)
            result['states_used'] = [detected_states.blocking_state.name]
            result['is_blocking'] = True
            return result

        # 2. Sinon, combiner les flags de tous les états et intentions
        primary_state = detected_states.primary_state
        if not primary_state:
            logger.warning("Aucun état primaire - utilisation de GENERAL")
            primary_state = self._create_default_state()

        # Copier le contexte du primary_state
        combined_context = primary_state.context_data.copy()

        # Ajouter les flags des états WARNING
        warning_flags = self._map_warning_state_flags(detected_states.warning_states)
        combined_context.update(warning_flags)

        # Ajouter les intentions du triage (primary + secondary)
        combined_context['primary_intent'] = triage_result.get('primary_intent')
        combined_context['secondary_intents'] = triage_result.get('secondary_intents', [])

        # Enrichir le primary_state avec le contexte combiné
        primary_state.context_data = combined_context

        # Collecter les alertes de tous les WARNING states
        all_alerts = list(primary_state.alerts)
        for warning_state in detected_states.warning_states:
            all_alerts.extend(warning_state.alerts)
        primary_state.alerts = all_alerts

        # 3. Générer la réponse avec le contexte combiné
        result = self.generate_response(primary_state, ai_generator)

        # 4. Ajouter les métadonnées multi-états
        result['states_used'] = [s.name for s in detected_states.all_states]
        result['warning_states'] = [s.name for s in detected_states.warning_states]
        result['info_states'] = [s.name for s in detected_states.info_states]
        result['primary_intent'] = triage_result.get('primary_intent')
        result['secondary_intents'] = triage_result.get('secondary_intents', [])
        result['is_blocking'] = False

        intents_handled = []
        if triage_result.get('primary_intent'):
            intents_handled.append(triage_result['primary_intent'])
        intents_handled.extend(triage_result.get('secondary_intents', []))
        result['intents_handled'] = intents_handled

        logger.info(f"📝 Réponse multi-états générée: states={result['states_used']}, intents={intents_handled}")

        return result

    def _create_default_state(self) -> DetectedState:
        """Crée un état GENERAL par défaut."""
        return DetectedState(
            id='DEFAULT',
            name='GENERAL',
            priority=999,
            category='default',
            description='État par défaut',
            workflow_action='RESPOND',
            response_config={},
            crm_updates_config=None,
            detection_reason='Fallback vers état GENERAL',
            severity='INFO',
            context_data={},
            alerts=[]
        )

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
        0. Matrice STATE:INTENTION (ex: "DATE_EXAMEN_VIDE:CONFIRMATION_SESSION")
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
        # Standardiser sur primary_intent avec fallback sur detected_intent (rétrocompat)
        intention = context.get('primary_intent') or context.get('detected_intent', '')

        # PASS 0: Chercher dans la matrice STATE:INTENTION (priorité maximale)
        # Format: "STATE_NAME:INTENTION" -> configuration spécifique
        if intention:
            matrix_key = f"{state.name}:{intention}"
            if matrix_key in self.state_intention_matrix:
                config = self.state_intention_matrix[matrix_key]
                template_file = config.get('template', '')
                # Extraire le nom du template sans extension
                template_key = template_file.replace('.html', '').replace('.md', '')
                logger.info(f"✅ Template sélectionné via matrice: {matrix_key} -> {template_file}")

                # Injecter les context_flags dans le contexte global ET dans state.context_data
                # Ces flags permettent aux templates hybrides de savoir quelle intention traiter
                context_flags = config.get('context_flags', {})
                if context_flags:
                    context.update(context_flags)
                    # IMPORTANT: Aussi mettre à jour state.context_data pour _prepare_placeholder_data
                    state.context_data.update(context_flags)
                    logger.info(f"📌 Context flags injectés: {list(context_flags.keys())}")

                # Construire la config au format attendu
                # response_master.html est dans templates/, pas templates/base/
                if template_file == 'response_master.html':
                    file_path = 'templates/response_master.html'
                else:
                    file_path = f'templates/base/{template_file}'

                return template_key, {
                    'file': file_path,
                    'blocks': config.get('blocks', []),
                    'crm_update': config.get('crm_update', []),
                    'context_flags': context_flags,
                }

        # PASS 1: Templates avec intention (priorité haute)
        for template_key, config in self.base_templates.items():
            if 'for_intention' in config:
                if intention == config['for_intention']:
                    # Vérifier aussi la condition si elle existe
                    if 'for_condition' in config:
                        if not self._evaluate_condition(config['for_condition'], context):
                            continue  # Condition non satisfaite, passer au suivant
                    # Injecter les context_flags (FIX: manquait dans PASS 1)
                    context_flags = config.get('context_flags', {})
                    if context_flags:
                        context.update(context_flags)
                        state.context_data.update(context_flags)
                    return template_key, config

        # PASS 1.5: Templates avec for_state (état spécifique)
        # Priorité sur les conditions génériques pour éviter que no_compte_examt3p
        # ne match pour des états comme EXAM_DATE_PAST_VALIDATED
        for template_key, config in self.base_templates.items():
            if 'for_state' in config:
                if state.name == config['for_state']:
                    logger.info(f"✅ Template sélectionné via for_state: {state.name} -> {template_key}")
                    self._inject_context_flags(config, context, state, "PASS 1.5")
                    return template_key, config

        # PASS 2: Templates avec condition seule (sans intention et sans for_state)
        for template_key, config in self.base_templates.items():
            if 'for_condition' in config and 'for_intention' not in config and 'for_state' not in config:
                if self._evaluate_condition(config['for_condition'], context):
                    self._inject_context_flags(config, context, state, "PASS 2")
                    return template_key, config

        # PASS 3: Cas Uber
        for template_key, config in self.base_templates.items():
            if 'for_uber_case' in config:
                if uber_case == config['for_uber_case']:
                    self._inject_context_flags(config, context, state, "PASS 3")
                    return template_key, config

        # PASS 4: Résultat examen
        for template_key, config in self.base_templates.items():
            if 'for_resultat' in config:
                if resultat == config['for_resultat']:
                    self._inject_context_flags(config, context, state, "PASS 4")
                    return template_key, config

        # PASS 5: Evalbox (le plus courant)
        for template_key, config in self.base_templates.items():
            if 'for_evalbox' in config:
                if evalbox == config['for_evalbox']:
                    self._inject_context_flags(config, context, state, "PASS 5")
                    return template_key, config

        # Fallback: chercher par nom d'état normalisé
        state_name_normalized = state.name.lower().replace('_', '-')
        for template_key, config in self.base_templates.items():
            if template_key.lower() == state_name_normalized:
                self._inject_context_flags(config, context, state, "Fallback by name")
                return template_key, config

        # FALLBACK FINAL: Utiliser response_master.html avec auto-mapping des intentions
        # Cela permet de gérer TOUS les états sans créer ~200 entrées manuelles
        logger.info(f"📝 Fallback vers response_master.html pour {state.name}")
        return 'response_master', {
            'file': 'templates/response_master.html',
            'description': f'Template master générique pour {state.name}',
        }

    def _inject_context_flags(
        self,
        config: Dict[str, Any],
        context: Dict[str, Any],
        state: DetectedState,
        pass_name: str
    ) -> None:
        """
        Injecte les context_flags d'un template dans le contexte et state.context_data.

        Args:
            config: Configuration du template (peut contenir 'context_flags')
            context: Contexte global à modifier
            state: État détecté (state.context_data sera aussi modifié)
            pass_name: Nom du PASS pour le logging (ex: "PASS 1.5")
        """
        context_flags = config.get('context_flags', {})
        if context_flags:
            context.update(context_flags)
            state.context_data.update(context_flags)
            logger.info(f"📌 Context flags injectés ({pass_name}): {list(context_flags.keys())}")

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

        # Construire le chemin complet - ordre de recherche:
        # 1. Chemin relatif depuis states_path (ex: templates/base/xxx.html)
        # 2. Directement dans templates/ (ex: response_master.html)
        # 3. Dans templates/base/ (fallback)
        full_path = self.states_path / template_path

        if not full_path.exists():
            # Essayer dans states/templates/ directement
            templates_root = self.states_path / "templates"
            full_path = templates_root / Path(template_path).name
            if not full_path.exists():
                # Essayer dans templates/base/
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

        # Pattern pour {{> bloc_name}} ou {{> path/to/partial}}
        # Supporte les chemins avec / comme partials/intentions/statut_dossier
        pattern = r'\{\{>\s*([\w/]+)\s*\}\}'

        while True:
            match = re.search(pattern, result)
            if not match:
                break

            block_name = match.group(1)

            # Si c'est un chemin (contient /), charger directement depuis templates/
            if '/' in block_name:
                block_content = self._load_partial_path(block_name)
            else:
                block_content = self._load_block(block_name)

            if block_content:
                # Résoudre récursivement les partials dans le bloc
                block_content = self._resolve_partials(block_content, context, blocks_included)
                # Résoudre les conditionnels dans le bloc
                block_content = self._resolve_if_blocks(block_content, context)
                block_content = self._resolve_unless_blocks(block_content, context)

                result = result[:match.start()] + block_content + result[match.end():]
                blocks_included.append(block_name.split('/')[-1])  # Juste le nom pour le log
            else:
                # Bloc non trouvé, supprimer le placeholder
                logger.warning(f"Bloc {block_name} non trouvé, suppression du placeholder")
                result = result[:match.start()] + result[match.end():]

        return result

    def _load_partial_path(self, partial_path: str) -> str:
        """Charge un partial depuis un chemin relatif au dossier templates."""
        # Construire le chemin complet - utiliser states_path / templates
        templates_root = self.states_path / "templates"
        full_path = templates_root / partial_path
        extensions = ['.html', '.md', '']

        for ext in extensions:
            file_path = full_path.parent / (full_path.name + ext)
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Nettoyer le contenu comme pour les autres blocs
                        return self._clean_block_content(content)
                except Exception as e:
                    logger.warning(f"Erreur lecture partial {file_path}: {e}")
                    return ''

        logger.warning(f"Partial non trouvé: {partial_path} (cherché dans {templates_root})")
        return ''

    def _resolve_if_blocks(self, template: str, context: Dict[str, Any]) -> str:
        """Résout les {{#if condition}}...{{else}}...{{/if}} avec support des blocs imbriqués."""
        result = template

        # Traiter les blocs de l'intérieur vers l'extérieur
        # en cherchant les blocs {{#if}} qui ne contiennent pas d'autres {{#if}}
        max_iterations = 100  # Sécurité contre les boucles infinies

        # Stocker les blocs "this.*" pour les restaurer après
        this_blocks = {}
        this_counter = 0

        for _ in range(max_iterations):
            # Chercher un {{#if}} dont le contenu ne contient pas d'autres {{#if}}
            # Pattern: {{#if var}} (contenu sans {{#if}}) {{/if}} ou avec {{else}}
            # Support des chemins pointés: sessions_proposees, this.is_soir, etc.
            pattern = r'\{\{#if\s+([\w.]+)\s*\}\}((?:(?!\{\{#if)(?!\{\{#unless).)*?)(?:\{\{else\}\}((?:(?!\{\{#if)(?!\{\{#unless).)*?))?\{\{/if\}\}'

            match = re.search(pattern, result, re.DOTALL)
            if not match:
                break

            condition_var = match.group(1)
            if_content = match.group(2) or ''
            else_content = match.group(3) or ''

            # SKIP: Les conditions "this.*" sont réservées pour le traitement {{#each}}
            # Elles seront résolues par _resolve_if_blocks_in_each_item
            if condition_var.startswith('this.'):
                # Remplacer par un placeholder unique
                placeholder = f"__THIS_IF_{this_counter}__"
                this_blocks[placeholder] = match.group(0)
                this_counter += 1
                result = result[:match.start()] + placeholder + result[match.end():]
                continue

            # Évaluer la condition - support des chemins pointés (a.b.c)
            condition_value = self._get_context_value_with_path(condition_var, context)

            if condition_value:
                replacement = if_content
            else:
                replacement = else_content

            result = result[:match.start()] + replacement + result[match.end():]

        # Restaurer les blocs "this.*"
        for placeholder, original in this_blocks.items():
            result = result.replace(placeholder, original)

        return result

    def _get_context_value_with_path(self, path: str, context: Dict[str, Any]) -> Any:
        """Récupère une valeur du contexte avec support des chemins pointés (a.b.c)."""
        # D'abord essayer comme variable simple via _get_context_value
        simple_value = self._get_context_value(path, context)
        if simple_value is not None:
            return simple_value

        # Ensuite traiter comme chemin pointé
        if '.' in path:
            parts = path.split('.')
            value = context
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value

        return context.get(path)

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
                        # Résoudre les {{#if this.property}} conditionnels DANS chaque item
                        rendered_item = self._resolve_if_blocks_in_each_item(rendered_item, item)
                    else:
                        rendered_item = rendered_item.replace("{{this}}", str(item))
                    rendered_items.append(rendered_item)
                replacement = ''.join(rendered_items)
            else:
                replacement = ''

            result = result[:match.start()] + replacement + result[match.end():]

        return result

    def _resolve_if_blocks_in_each_item(self, template: str, item: Dict[str, Any]) -> str:
        """Résout les {{#if this.property}} conditionnels à l'intérieur d'un item {{#each}}."""
        result = template

        # Pattern pour {{#if this.property}} avec contenu qui ne contient pas d'autres {{#if}}
        pattern = r'\{\{#if\s+this\.(\w+)\s*\}\}((?:(?!\{\{#if).)*?)(?:\{\{else\}\}((?:(?!\{\{#if).)*?))?\{\{/if\}\}'

        max_iterations = 50
        for _ in range(max_iterations):
            match = re.search(pattern, result, re.DOTALL)
            if not match:
                break

            property_name = match.group(1)
            if_content = match.group(2) or ''
            else_content = match.group(3) or ''

            # Évaluer la condition sur l'item
            condition_value = item.get(property_name)

            if condition_value:
                replacement = if_content
            else:
                replacement = else_content

            result = result[:match.start()] + replacement + result[match.end():]

        return result

    def _get_context_value(self, key: str, context: Dict[str, Any]) -> Any:
        """Récupère une valeur du contexte, avec support des clés imbriquées."""
        # PRIORITÉ 1: Vérifier si la clé existe directement dans le contexte
        # Ceci permet à placeholder_data de surcharger les mappings legacy
        if key in context:
            return context[key]

        # PRIORITÉ 2: Mappings legacy pour rétrocompatibilité
        # (utilisés uniquement si la clé n'existe pas directement)
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

        # Chercher dans deal_data (fallback pour clés non mappées)
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
        contact_data = context.get('contact_data', {})  # Données du Contact lié (First_Name, Last_Name)
        examt3p_data = context.get('examt3p_data', {})

        # Extraire le prénom et nom depuis Contact (pas Deal)
        prenom = self._extract_prenom_from_contact(contact_data, deal_data)
        nom = contact_data.get('Last_Name', '') or ''

        # Formater les dates - utiliser date_examen_vtc_value si disponible (extraite du lookup)
        date_examen = context.get('date_examen_vtc_value') or context.get('date_examen')
        date_examen_formatted = self._format_date(date_examen) if date_examen else ''

        # Département
        departement = context.get('departement', '')

        # Préparer les dates proposées
        dates_proposees = self._format_dates_list(context.get('next_dates', []))

        # Préparer le statut actuel
        evalbox = context.get('evalbox', '')
        statut_actuel = self._format_statut(evalbox)

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

        result = {
            # Infos candidat (depuis Contact, pas Deal)
            'prenom': prenom or 'Bonjour',
            'nom': nom,
            'email': contact_data.get('Email') or deal_data.get('Email', ''),

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
            # session_preference: priorité à intent_context (détecté par triage) puis session_data (legacy)
            'session_preference': self._get_session_preference(context),
            'session_preference_soir': self._get_session_preference(context) == 'soir',
            'session_preference_jour': self._get_session_preference(context) == 'jour',
            # Données aplaties pour itération facile dans les templates
            # FILTRER selon la préférence si l'intention est CONFIRMATION_SESSION
            'sessions_proposees': self._flatten_session_options_filtered(context),
            'date_debut_formation': '',
            'date_fin_formation': '',

            # Statut
            'statut_actuel': statut_actuel,
            'evalbox_status': evalbox,
            'num_dossier_cma': examt3p_data.get('num_dossier', ''),

            # Booléens pour les statuts Evalbox (pour templates conditionnels)
            'evalbox_dossier_cree': evalbox == 'Dossier crée',
            'evalbox_dossier_synchronise': evalbox == 'Dossier Synchronisé',
            'evalbox_pret_a_payer': evalbox in ['Pret a payer', 'Pret a payer par cheque'],
            'evalbox_valide_cma': evalbox == 'VALIDE CMA',
            'evalbox_refus_cma': evalbox == 'Refusé CMA',
            'evalbox_convoc_recue': evalbox == 'Convoc CMA reçue',
            'no_evalbox_status': not evalbox or evalbox in ['None', '', 'N/A'],

            # Numéro de dossier
            'num_dossier': examt3p_data.get('num_dossier', '') or context.get('num_dossier', ''),

            # Prochaines étapes
            'prochaines_etapes': self._get_prochaines_etapes(state),

            # Booléens pour les conditions (aussi disponibles comme placeholders)
            # Note: uber_20 et is_uber_20_deal sont synonymes pour supporter les deux notations dans les templates
            'uber_20': context.get('is_uber_20_deal', False),
            'is_uber_20_deal': context.get('is_uber_20_deal', False),
            # uber_eligible = Uber 20€ + Compte_Uber vérifié + ELIGIBLE vérifié
            'uber_eligible': (
                context.get('is_uber_20_deal', False) and
                context.get('compte_uber', False) and
                context.get('eligible_uber', False)
            ),
            'can_choose_other_department': context.get('can_choose_other_department', False) or not context.get('compte_existe', True),
            'session_assigned': context.get('session_assigned', False),
            'compte_existe': context.get('compte_existe', False),
            'can_modify_exam_date': context.get('can_modify_exam_date', True),
            'cloture_passed': context.get('cloture_passed', False),
            'deadline_passed_reschedule': context.get('deadline_passed_reschedule', False),
            'new_exam_date': self._format_date(context.get('new_exam_date', '')) if context.get('new_exam_date') else '',
            'new_exam_date_cloture': self._format_date(context.get('new_exam_date_cloture', '')) if context.get('new_exam_date_cloture') else '',

            # Booléens pour proposer dates/sessions
            'date_examen_vide': not date_examen,
            'session_vide': not deal_data.get('Session'),
            'has_sessions_proposees': bool(self._flatten_session_options_filtered(context)),

            # Force majeure (pour les templates empathiques)
            'mentions_force_majeure': context.get('mentions_force_majeure', False),
            'force_majeure_type': context.get('force_majeure_type'),
            'force_majeure_details': context.get('force_majeure_details', ''),
            'is_force_majeure_deces': context.get('is_force_majeure_deces', False),
            'is_force_majeure_medical': context.get('is_force_majeure_medical', False),
            'is_force_majeure_accident': context.get('is_force_majeure_accident', False),
            'is_force_majeure_childcare': context.get('is_force_majeure_childcare', False),
            'is_force_majeure_other': context.get('is_force_majeure_other', False),

            # Context flags pour templates hybrides
            # AUTO-MAPPING: Génère automatiquement les flags depuis primary_intent et secondary_intents
            # Priorité: context_flags de la matrice > auto-mapping depuis intentions
            **self._auto_map_intention_flags(context),

            # Context flags pour conditions bloquantes (Section 0 de response_master)
            # Ces flags sont définis via context_flags dans la matrice STATE:INTENTION
            'uber_cas_a': context.get('uber_cas_a', False),
            'uber_cas_b': context.get('uber_cas_b', False),
            'uber_cas_d': context.get('uber_cas_d', False),
            'uber_cas_e': context.get('uber_cas_e', False),
            'uber_doublon': context.get('uber_doublon', False),

            # Résultats d'examen
            'resultat_admis': context.get('resultat_admis', False),
            'resultat_non_admis': context.get('resultat_non_admis', False),
            'resultat_absent': context.get('resultat_absent', False),

            # Report de date
            'report_bloque': context.get('report_bloque', False),
            'report_possible': context.get('report_possible', False),
            'report_force_majeure': context.get('report_force_majeure', False),

            # Problèmes d'identifiants
            'credentials_invalid': context.get('credentials_invalid', False),
            'credentials_inconnus': context.get('credentials_inconnus', False),

            # Données supplémentaires pour templates hybrides
            'has_next_dates': bool(context.get('next_dates', [])),
            'next_dates': self._format_next_dates_for_template(context.get('next_dates', [])),
            'preference_horaire_text': 'cours du soir' if self._get_session_preference(context) == 'soir' else 'cours du jour',

            # Filtrage par mois demandé (REPORT_DATE)
            'no_date_for_requested_month': context.get('no_date_for_requested_month', False),
            'requested_month_name': context.get('requested_month_name', ''),

            # Flags pour le template master (architecture modulaire)
            # Sections à afficher
            'show_statut_section': True,  # Toujours afficher le statut
            'show_dates_section': not date_examen and bool(context.get('next_dates', [])),
            'show_sessions_section': date_examen and not deal_data.get('Session') and bool(self._flatten_session_options_filtered(context)),

            # Actions requises (déterminées par l'état)
            **self._determine_required_actions(context, evalbox),
        }

        return result

    # Mapping state → flag pour les états WARNING
    STATE_FLAG_MAP = {
        'UBER_ACCOUNT_NOT_VERIFIED': 'uber_cas_d',
        'UBER_NOT_ELIGIBLE': 'uber_cas_e',
        'PERSONAL_ACCOUNT_WARNING': 'personal_account_warning',
        'DATE_MODIFICATION_BLOCKED': 'report_bloque',
        'TRAINING_MISSED_EXAM_IMMINENT': 'training_missed_alert',
    }

    # Mapping intention → flag
    INTENTION_FLAG_MAP = {
        'STATUT_DOSSIER': 'intention_statut_dossier',
        'DEMANDE_DATE_EXAMEN': 'intention_demande_date',
        'DEMANDE_AUTRES_DATES': 'intention_demande_date',
        'DEMANDE_DATES_FUTURES': 'intention_demande_date',  # Nouvelle intention
        'CONFIRMATION_DATE_EXAMEN': 'intention_demande_date',
        'DEMANDE_IDENTIFIANTS': 'intention_demande_identifiants',
        'ENVOIE_IDENTIFIANTS': 'intention_demande_identifiants',
        'CONFIRMATION_SESSION': 'intention_confirmation_session',
        'QUESTION_SESSION': 'intention_question_session',  # Nouvelle intention
        'DEMANDE_CONVOCATION': 'intention_demande_convocation',
        'DEMANDE_ELEARNING_ACCESS': 'intention_demande_elearning',
        'REPORT_DATE': 'intention_report_date',
        'FORCE_MAJEURE_REPORT': 'intention_report_date',
        'DOCUMENT_QUESTION': 'intention_probleme_documents',
        'SIGNALE_PROBLEME_DOCS': 'intention_probleme_documents',
        'ENVOIE_DOCUMENTS': 'intention_probleme_documents',
        'QUESTION_PROCESSUS': 'intention_question_processus',  # Nouvelle intention
        'DEMANDE_AUTRES_DEPARTEMENTS': 'intention_autres_departements',  # Nouvelle intention
        # Intentions fréquentes
        'QUESTION_GENERALE': 'intention_question_generale',
        'RESULTAT_EXAMEN': 'intention_resultat_examen',
        'QUESTION_UBER': 'intention_question_uber',
        # Synonymes courants
        'DEMANDE_RESULTAT': 'intention_resultat_examen',
        'NOTE_EXAMEN': 'intention_resultat_examen',
        'UBER_ELIGIBILITE': 'intention_question_uber',
        'UBER_OFFRE': 'intention_question_uber',
    }

    def _auto_map_intention_flags(self, context: Dict[str, Any]) -> Dict[str, bool]:
        """
        Auto-génère les flags intention_* depuis primary_intent ET secondary_intents.

        Convention: primary_intent est le standard, detected_intent est conservé pour rétrocompat.

        Cela évite de créer ~200 entrées manuelles dans la matrice STATE×INTENTION.
        Le template master (response_master.html) utilise ces flags pour afficher
        la section appropriée selon l'intention du candidat.

        Priorité: context_flags de la matrice > auto-mapping
        Si un flag est déjà défini dans le contexte (via matrice), il est conservé.
        """
        # Initialiser tous les flags à False
        flags = {
            'intention_statut_dossier': False,
            'intention_demande_date': False,
            'intention_confirmation_session': False,
            'intention_question_session': False,  # Nouvelle
            'intention_demande_identifiants': False,
            'intention_demande_convocation': False,
            'intention_demande_elearning': False,
            'intention_report_date': False,
            'intention_probleme_documents': False,
            'intention_question_processus': False,  # Nouvelle
            'intention_autres_departements': False,  # Nouvelle
            # Intentions fréquentes
            'intention_question_generale': False,
            'intention_resultat_examen': False,
            'intention_question_uber': False,
        }

        # Récupérer l'intention principale (rétrocompatibilité + nouveau format)
        primary_intent = context.get('primary_intent') or context.get('detected_intent', '')

        # Flags Section 0 qui couvrent déjà certaines intentions
        # Si ces flags sont actifs, ne pas auto-mapper l'intention correspondante pour éviter la duplication
        section0_overrides = {
            'intention_report_date': ['report_possible', 'report_bloque', 'report_force_majeure'],
            'intention_resultat_examen': ['resultat_admis', 'resultat_non_admis', 'resultat_absent'],
            'intention_demande_identifiants': ['credentials_invalid', 'credentials_inconnus'],
        }

        # Auto-mapper l'intention principale
        if primary_intent in self.INTENTION_FLAG_MAP:
            flag_name = self.INTENTION_FLAG_MAP[primary_intent]
            # Vérifier si un flag Section 0 couvre déjà cette intention
            skip_mapping = False
            if flag_name in section0_overrides:
                for section0_flag in section0_overrides[flag_name]:
                    if context.get(section0_flag):
                        skip_mapping = True
                        logger.debug(f"Skipping auto-map {flag_name} - covered by Section 0 flag {section0_flag}")
                        break
            if not skip_mapping:
                flags[flag_name] = True
                logger.debug(f"Auto-mapped primary_intent {primary_intent} -> {flag_name}")

        # Auto-mapper les intentions secondaires (avec vérification Section 0)
        secondary_intents = context.get('secondary_intents', [])
        for intent in secondary_intents:
            if intent in self.INTENTION_FLAG_MAP:
                flag_name = self.INTENTION_FLAG_MAP[intent]
                # Vérifier si un flag Section 0 couvre déjà cette intention secondaire
                skip_mapping = False
                if flag_name in section0_overrides:
                    for section0_flag in section0_overrides[flag_name]:
                        if context.get(section0_flag):
                            skip_mapping = True
                            logger.debug(f"Skipping secondary_intent {intent} - covered by Section 0 flag {section0_flag}")
                            break
                if not skip_mapping:
                    flags[flag_name] = True
                    logger.debug(f"Auto-mapped secondary_intent {intent} -> {flag_name}")

        # Priorité aux flags déjà définis dans le contexte (via matrice)
        for flag_name in flags:
            if context.get(flag_name) is True:
                flags[flag_name] = True

        return flags

    def _map_warning_state_flags(self, warning_states: List[DetectedState]) -> Dict[str, bool]:
        """
        Génère les flags pour les états WARNING.

        Ces flags sont utilisés par response_master.html pour afficher
        les alertes appropriées dans la réponse.
        """
        flags = {}
        for state in warning_states:
            state_flag = self.STATE_FLAG_MAP.get(state.name)
            if state_flag:
                flags[state_flag] = True
                logger.debug(f"Mapped WARNING state {state.name} -> {state_flag}")
        return flags

    def _determine_required_actions(self, context: Dict[str, Any], evalbox: str) -> Dict[str, bool]:
        """Détermine les actions requises selon l'état du candidat."""
        actions = {
            'has_required_action': False,
            'action_passer_test': False,
            'action_envoyer_documents': False,
            'action_completer_dossier': False,
            'action_choisir_date': False,
            'action_choisir_session': False,
            'action_surveiller_paiement': False,
            'action_attendre_convocation': False,
            'action_preparer_examen': False,
            'action_corriger_documents': False,
            'action_contacter_uber': False,
        }

        # Déterminer l'état Uber
        is_uber_20 = context.get('is_uber_20_deal', False)
        date_dossier_recu = context.get('date_dossier_recu')
        date_test_selection = context.get('date_test_selection')
        compte_uber = context.get('compte_uber', True)
        eligible_uber = context.get('eligible_uber', True)

        # États bloquants Uber
        if is_uber_20:
            if not date_dossier_recu:
                # CAS A: Documents non envoyés
                actions['action_envoyer_documents'] = True
                actions['has_required_action'] = True
                return actions
            if not date_test_selection:
                # CAS B: Test non passé
                actions['action_passer_test'] = True
                actions['has_required_action'] = True
                return actions
            if not compte_uber:
                # CAS D: Compte Uber non vérifié
                actions['action_contacter_uber'] = True
                actions['has_required_action'] = True
                return actions
            if not eligible_uber:
                # CAS E: Non éligible
                actions['action_contacter_uber'] = True
                actions['has_required_action'] = True
                return actions

        # Actions selon Evalbox
        if evalbox == 'Dossier crée':
            actions['action_completer_dossier'] = True
            actions['has_required_action'] = True
        elif evalbox == 'Dossier Synchronisé':
            actions['action_surveiller_paiement'] = True
            actions['has_required_action'] = True
        elif evalbox in ['Pret a payer', 'Pret a payer par cheque']:
            actions['action_surveiller_paiement'] = True
            actions['has_required_action'] = True
        elif evalbox == 'VALIDE CMA':
            actions['action_attendre_convocation'] = True
            actions['has_required_action'] = True
        elif evalbox == 'Refusé CMA':
            actions['action_corriger_documents'] = True
            actions['has_required_action'] = True
        elif evalbox == 'Convoc CMA reçue':
            actions['action_preparer_examen'] = True
            actions['has_required_action'] = True
        else:
            # Pas de statut Evalbox - vérifier si date/session manquantes
            date_examen = context.get('date_examen')
            session = context.get('deal_data', {}).get('Session')
            if not date_examen:
                actions['action_choisir_date'] = True
                actions['has_required_action'] = True
            elif not session:
                actions['action_choisir_session'] = True
                actions['has_required_action'] = True

        return actions

    def _format_next_dates_for_template(self, dates: List[Dict]) -> List[Dict]:
        """Formate les next_dates pour utilisation dans les templates {{#each}}."""
        if not dates:
            return []

        formatted = []
        seen_depts = set()

        for d in dates[:5]:  # Limiter à 5 dates
            date_str = d.get('Date_Examen', '')
            cloture_str = d.get('Date_Cloture_Inscription', '')
            dept = d.get('Departement', '')

            formatted.append({
                'date_examen_formatted': self._format_date(date_str) if date_str else '',
                'date_cloture_formatted': self._format_date(cloture_str) if cloture_str else '',
                'Departement': dept,
                'is_first_of_dept': dept not in seen_depts,
                # Conserver les champs originaux aussi
                'Date_Examen': date_str,
                'Date_Cloture_Inscription': cloture_str,
            })
            seen_depts.add(dept)

        return formatted

    def _extract_prenom_from_contact(self, contact_data: Dict[str, Any], deal_data: Dict[str, Any]) -> str:
        """Extrait le prénom du candidat depuis Contact (prioritaire) ou Deal_Name (fallback)."""
        # Priorité 1: First_Name du Contact
        first_name = contact_data.get('First_Name', '')
        if first_name and first_name.strip():
            return first_name.strip().capitalize()

        # Priorité 2: Extraire le prénom du Deal_Name (ex: "Thomas DUPONT" -> "Thomas")
        deal_name = deal_data.get('Deal_Name', '')
        if deal_name and ' ' in deal_name:
            # Prendre le premier mot qui n'est pas tout en majuscules
            parts = deal_name.split()
            for part in parts:
                if not part.isupper() and part.isalpha():
                    return part.capitalize()
            # Sinon prendre le premier mot
            return parts[0].capitalize()

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

                # Déterminer si c'est la première session de cette date d'examen
                is_first_of_exam = not any(
                    s.get('date_examen_raw') == date_examen for s in flattened
                )

                flattened.append({
                    'date_examen': date_examen_formatted,
                    'date_examen_formatted': date_examen_formatted,
                    'date_examen_raw': date_examen,
                    'departement': departement,
                    'cloture': cloture_formatted,
                    'date_cloture_formatted': cloture_formatted,
                    'nom': session_type_label or session.get('Name', ''),
                    'session_name': session.get('Name', ''),
                    'session_id': session.get('id', ''),
                    'debut': date_debut_formatted,
                    'date_debut': date_debut_formatted,
                    'fin': date_fin_formatted,
                    'date_fin': date_fin_formatted,
                    'type': session_type,
                    'horaires': horaires,
                    'is_jour': session_type == 'jour',
                    'is_soir': session_type == 'soir',
                    'is_first_of_exam': is_first_of_exam,
                })

        return flattened

    def _get_session_preference(self, context: Dict[str, Any]) -> str:
        """
        Récupère la préférence de session (jour/soir).
        Priorité: intent_context (triage) > session_data (legacy)
        """
        # 1. Priorité: intent_context (détecté par le triage depuis le message client)
        intent_context = context.get('intent_context', {})
        if intent_context.get('session_preference'):
            return intent_context['session_preference']

        # 2. Fallback: session_data (legacy helper)
        session_data = context.get('session_data', {})
        if session_data.get('session_preference'):
            return session_data['session_preference']

        return ''

    def _flatten_session_options_filtered(self, context: Dict[str, Any]) -> list:
        """
        Retourne les sessions aplaties, FILTRÉES selon la préférence si:
        - L'intention est CONFIRMATION_SESSION
        - ET une préférence (jour/soir) a été détectée

        Si le client dit "je veux le matin", on ne lui montre QUE les sessions du jour.
        """
        session_data = context.get('session_data', {})
        all_sessions = self._flatten_session_options(session_data)

        # Vérifier si on doit filtrer
        # Utiliser primary_intent avec fallback sur detected_intent (rétrocompat)
        primary_intent = context.get('primary_intent') or context.get('detected_intent', '')
        secondary_intents = context.get('secondary_intents', [])
        session_preference = self._get_session_preference(context)

        # Si CONFIRMATION_SESSION (primary OU secondary) et préférence claire, filtrer
        is_confirmation_session = (
            primary_intent == 'CONFIRMATION_SESSION' or
            'CONFIRMATION_SESSION' in secondary_intents
        )

        if is_confirmation_session and session_preference:
            filtered = [s for s in all_sessions if s.get('type') == session_preference]
            if filtered:
                logger.info(f"✅ Sessions filtrées selon préférence '{session_preference}': {len(filtered)}/{len(all_sessions)}")
                return filtered
            # Si aucune session ne correspond, retourner toutes (fallback)
            logger.warning(f"⚠️ Aucune session '{session_preference}' trouvée, affichage de toutes les sessions")

        return all_sessions

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

        if alert_type == 'personal_account_warning':
            # Charger le partial template et résoudre les variables
            template_content = self._load_partial_path('partials/warnings/personal_account_warning.html')
            if template_content:
                alert_context = {
                    'personal_account_email': alert.get('personal_account_email', ''),
                    'cab_account_email': alert.get('cab_account_email', '')
                }
                # Résoudre les conditionnels {{#if}} puis les variables {{variable}}
                rendered = self._resolve_if_blocks(template_content, alert_context)
                rendered, _ = self._replace_placeholders(rendered, alert_context)
                return f"<hr>\n{rendered}\n<hr>"
            return None

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
