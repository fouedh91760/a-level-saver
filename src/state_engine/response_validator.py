"""
ResponseValidator - Validation stricte des réponses générées.

Ce module valide que les réponses générées respectent:
1. Les blocs obligatoires selon l'état
2. L'absence de blocs interdits
3. L'absence de termes interdits (BFS, Evalbox, 20€, etc.)
4. La cohérence des données (dates proposées = dates réelles, pas inventées)
5. L'absence d'hallucinations (montants, identifiants, etc.)
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date

from .state_detector import DetectedState

logger = logging.getLogger(__name__)


class ValidationError:
    """Représente une erreur de validation."""

    def __init__(
        self,
        error_type: str,
        message: str,
        severity: str = 'error',  # 'error', 'warning', 'info'
        location: Optional[str] = None
    ):
        self.error_type = error_type
        self.message = message
        self.severity = severity
        self.location = location

    def __repr__(self):
        return f"ValidationError({self.severity}: {self.error_type} - {self.message})"


class ValidationResult:
    """Résultat de la validation."""

    def __init__(self):
        self.valid = True
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.checks_passed: List[str] = []

    def add_error(self, error: ValidationError):
        if error.severity == 'error':
            self.errors.append(error)
            self.valid = False
        else:
            self.warnings.append(error)

    def add_passed(self, check_name: str):
        self.checks_passed.append(check_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'valid': self.valid,
            'errors': [{'type': e.error_type, 'message': e.message, 'location': e.location}
                       for e in self.errors],
            'warnings': [{'type': w.error_type, 'message': w.message, 'location': w.location}
                         for w in self.warnings],
            'checks_passed': self.checks_passed
        }


class ResponseValidator:
    """
    Valide les réponses générées pour éviter les hallucinations et erreurs.

    Validations effectuées:
    1. Termes interdits (BFS, Evalbox, 20€, etc.)
    2. Blocs obligatoires présents
    3. Blocs interdits absents
    4. Dates mentionnées = dates proposées (pas inventées)
    5. Identifiants = ceux du CRM (pas inventés)
    6. Montants cohérents
    7. Format et structure
    """

    # Termes toujours interdits
    FORBIDDEN_TERMS = [
        'BFS',
        'Evalbox',
        'CDJ',  # Utiliser "Cours du jour"
        'CDS',  # Utiliser "Cours du soir"
        '20€',  # Ne pas mentionner le prix de l'offre
        'Montreuil',  # Adresse interne
        'lookup',
        'CRM',
        'deal',
        'API',
        'ticket_id',
        'deal_id',
        'module',
        'field',
    ]

    # Patterns pour détecter les dates
    DATE_PATTERNS = [
        r'\d{2}/\d{2}/\d{4}',  # DD/MM/YYYY
        r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
        r'\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}',
    ]

    # Patterns pour détecter les montants
    AMOUNT_PATTERNS = [
        r'\d+\s*€',
        r'\d+\s*euros?',
        r'€\s*\d+',
    ]

    def __init__(self, forbidden_terms: Optional[List[str]] = None):
        """
        Initialise le validateur.

        Args:
            forbidden_terms: Liste additionnelle de termes interdits
        """
        self.forbidden_terms = self.FORBIDDEN_TERMS.copy()
        if forbidden_terms:
            self.forbidden_terms.extend(forbidden_terms)

    def validate(
        self,
        response_text: str,
        state: DetectedState,
        proposed_dates: Optional[List[Dict]] = None,
        allowed_amounts: Optional[List[int]] = None,
        template_used: Optional[str] = None
    ) -> ValidationResult:
        """
        Valide une réponse générée.

        Args:
            response_text: Texte de la réponse à valider
            state: État détecté (contient la config de validation)
            proposed_dates: Dates effectivement proposées au candidat
            allowed_amounts: Montants autorisés à mentionner
            template_used: Nom du template utilisé (pour ajuster les règles de validation)

        Returns:
            ValidationResult avec erreurs et warnings
        """
        result = ValidationResult()

        # 1. Vérifier les termes interdits
        self._check_forbidden_terms(response_text, result)

        # 2. Vérifier les blocs obligatoires
        # IMPORTANT: Si le template utilisé est différent du template par défaut de l'état,
        # on ne vérifie PAS les blocs requis de l'état (ils ne sont pas pertinents)
        # Exemples: report_bloque, credentials_refused, etc.
        skip_blocks_validation = self._should_skip_blocks_validation(state, template_used)
        if not skip_blocks_validation:
            self._check_required_blocks(response_text, state, result)

        # 3. Vérifier les blocs interdits
        self._check_forbidden_blocks(response_text, state, result)

        # 4. Vérifier les dates (pas d'hallucination)
        self._check_dates(response_text, proposed_dates, state, result)

        # 5. Vérifier les identifiants
        self._check_identifiants(response_text, state, result)

        # 6. Vérifier les montants
        self._check_amounts(response_text, allowed_amounts, result)

        # 7. Vérifier le format et la structure
        self._check_format(response_text, result)

        logger.info(f"Validation: {'✅ PASS' if result.valid else '❌ FAIL'} "
                    f"({len(result.errors)} erreurs, {len(result.warnings)} warnings)")

        return result

    def _check_forbidden_terms(self, response: str, result: ValidationResult):
        """Vérifie l'absence de termes interdits."""
        response_lower = response.lower()

        for term in self.forbidden_terms:
            # Recherche insensible à la casse mais mot entier
            pattern = r'\b' + re.escape(term.lower()) + r'\b'
            if re.search(pattern, response_lower):
                result.add_error(ValidationError(
                    'forbidden_term',
                    f"Terme interdit trouvé: '{term}'",
                    severity='error',
                    location=self._find_location(response, term)
                ))

        if not any(e.error_type == 'forbidden_term' for e in result.errors):
            result.add_passed('forbidden_terms')

    def _check_required_blocks(
        self,
        response: str,
        state: DetectedState,
        result: ValidationResult
    ):
        """Vérifie la présence des blocs obligatoires."""
        response_config = state.response_config
        required_blocks = response_config.get('blocks_required', [])

        # Mapping bloc → patterns de détection
        block_patterns = {
            'salutation': [r'bonjour', r'cher', r'chère', r'madame', r'monsieur'],
            'signature': [r'cordialement', r'l\'équipe', r'cab formations', r'bien à vous'],
            'identifiants_examt3p': [r'identifiant', r'mot de passe', r'intras\.fr'],
            'warning_spam': [r'spam', r'indésirable', r'courrier'],
            'dates_proposees': [r'\d{2}/\d{2}/\d{4}', r'date.*examen', r'📅'],
            'call_to_action': [r'merci de', r'veuillez', r'n\'hésitez pas', r'contactez'],
            'lien_plateforme': [r'intras\.fr', r'https://'],
            'confirmation_choix': [r'enregistré', r'confirmé', r'validé'],
            # Blocs pour credentials_invalid
            'explication_probleme_identifiants': [
                r'identifiants de connexion',
                r'plateforme examt3p',
                r'avons besoin de vos identifiants',
            ],
            'instructions_recuperation': [
                r'retrouver vos identifiants',
                r'recherchez dans votre bo[îi]te mail',
                r'noreply@intras\.fr',
            ],
            # Blocs pour credentials_refused_security
            'comprendre_besoin_identifiants': [
                r'pourquoi.*besoin.*identifiants',
                r'chambre des m[ée]tiers',
                r'cma',
                r'paiement des frais',
                r'en votre nom',
            ],
            'alternative_autonomie': [
                r'vous pr[ée]f[ée]rez.*vous-m[êe]me',
                r'c\'est tout [àa] fait possible',
                r'voici la proc[ée]dure',
                r'241.*€',
            ],
        }

        for block in required_blocks:
            patterns = block_patterns.get(block, [block.lower()])
            found = any(
                re.search(pattern, response, re.IGNORECASE)
                for pattern in patterns
            )

            if not found:
                result.add_error(ValidationError(
                    'missing_block',
                    f"Bloc obligatoire manquant: '{block}'",
                    severity='error'
                ))

        if not any(e.error_type == 'missing_block' for e in result.errors):
            result.add_passed('required_blocks')

    def _check_forbidden_blocks(
        self,
        response: str,
        state: DetectedState,
        result: ValidationResult
    ):
        """Vérifie l'absence de blocs interdits."""
        response_config = state.response_config
        forbidden_blocks = response_config.get('blocks_forbidden', [])

        # Mapping bloc → patterns de détection
        block_patterns = {
            'dates_examen': [r'date.*examen', r'examen.*\d{2}/\d{2}', r'📅.*\d{2}/\d{2}'],
            'sessions_formation': [r'cours du jour', r'cours du soir', r'session.*formation'],
            'identifiants': [r'identifiant.*:', r'mot de passe.*:'],
            'confirmation_inscription': [r'inscription.*confirmée', r'bien inscrit'],
            'dates_proposees': [r'prochaines dates', r'dates disponibles'],
        }

        for block in forbidden_blocks:
            patterns = block_patterns.get(block, [block.lower()])
            for pattern in patterns:
                if re.search(pattern, response, re.IGNORECASE):
                    result.add_error(ValidationError(
                        'forbidden_block',
                        f"Bloc interdit présent: '{block}'",
                        severity='error',
                        location=self._find_location(response, pattern)
                    ))
                    break

        if not any(e.error_type == 'forbidden_block' for e in result.errors):
            result.add_passed('forbidden_blocks')

    def _check_dates(
        self,
        response: str,
        proposed_dates: Optional[List[Dict]],
        state: DetectedState,
        result: ValidationResult
    ):
        """Vérifie que les dates mentionnées sont réelles (pas inventées)."""
        # Extraire toutes les dates de la réponse
        dates_found = []
        for pattern in self.DATE_PATTERNS:
            dates_found.extend(re.findall(pattern, response, re.IGNORECASE))

        if not dates_found:
            result.add_passed('dates_coherence')
            return

        # Si on a des dates proposées, vérifier la cohérence
        if proposed_dates:
            # Convertir les dates proposées en formats comparables
            valid_dates = set()
            for date_info in proposed_dates:
                date_str = date_info.get('Date_Examen', '')
                if date_str:
                    # Ajouter format YYYY-MM-DD
                    valid_dates.add(date_str)
                    # Ajouter format DD/MM/YYYY
                    try:
                        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
                        valid_dates.add(dt.strftime('%d/%m/%Y'))
                    except Exception as e:
                        pass

            # Vérifier chaque date trouvée
            for date_found in dates_found:
                normalized = self._normalize_date(date_found)
                if normalized and normalized not in valid_dates:
                    # Vérifier si c'est une date du contexte (date examen assignée, etc.)
                    context = state.context_data
                    context_dates = {
                        context.get('date_examen'),
                        context.get('date_cloture'),
                    }
                    context_dates = {d for d in context_dates if d}
                    # Ajouter les formats alternatifs
                    for d in list(context_dates):
                        try:
                            dt = datetime.strptime(d[:10], '%Y-%m-%d')
                            context_dates.add(dt.strftime('%d/%m/%Y'))
                        except Exception as e:
                            pass

                    if normalized not in context_dates:
                        result.add_error(ValidationError(
                            'invented_date',
                            f"Date potentiellement inventée: '{date_found}'",
                            severity='warning',  # Warning car peut être une date valide non listée
                            location=self._find_location(response, date_found)
                        ))

        # Vérifier que les dates ne sont pas dans le passé (sauf contexte spécifique)
        today = date.today()
        for date_found in dates_found:
            try:
                dt = self._parse_date(date_found)
                if dt and dt < today:
                    # C'est peut-être une date passée mentionnée volontairement
                    result.add_error(ValidationError(
                        'past_date',
                        f"Date passée mentionnée: '{date_found}'",
                        severity='warning'
                    ))
            except Exception as e:
                pass

        if not any(e.error_type in ['invented_date', 'past_date'] for e in result.errors):
            result.add_passed('dates_coherence')

    def _check_identifiants(
        self,
        response: str,
        state: DetectedState,
        result: ValidationResult
    ):
        """Vérifie que les identifiants sont ceux du CRM."""
        examt3p_data = state.context_data.get('examt3p_data', {})

        # Si la réponse contient des identifiants, ils doivent correspondre au CRM
        if 'identifiant' in response.lower() and ':' in response:
            real_identifiant = examt3p_data.get('identifiant', '')

            if real_identifiant:
                # Vérifier que l'identifiant réel est présent
                if real_identifiant.lower() not in response.lower():
                    # Chercher des emails qui ne correspondent pas
                    emails_found = re.findall(
                        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                        response
                    )
                    for email in emails_found:
                        if email.lower() != real_identifiant.lower():
                            # Vérifier si c'est l'email du candidat (peut être différent)
                            candidate_email = state.context_data.get('deal_data', {}).get('Email', '')
                            if email.lower() != candidate_email.lower():
                                result.add_error(ValidationError(
                                    'wrong_identifiant',
                                    f"Identifiant possiblement incorrect: '{email}'",
                                    severity='warning'
                                ))

        result.add_passed('identifiants_check')

    def _check_amounts(
        self,
        response: str,
        allowed_amounts: Optional[List[int]],
        result: ValidationResult
    ):
        """Vérifie que les montants sont autorisés."""
        # Montants généralement OK à mentionner
        default_allowed = [241, 60]  # Frais CMA, frais dossier
        if allowed_amounts:
            default_allowed.extend(allowed_amounts)

        # Extraire les montants de la réponse
        for pattern in self.AMOUNT_PATTERNS:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for match in matches:
                # Extraire le nombre
                amount = int(re.search(r'\d+', match).group())

                # 20€ est toujours interdit
                if amount == 20:
                    result.add_error(ValidationError(
                        'forbidden_amount',
                        "Montant 20€ interdit (ne pas mentionner le prix de l'offre)",
                        severity='error',
                        location=self._find_location(response, match)
                    ))
                elif amount not in default_allowed and amount > 10:
                    # Montants inhabituels = warning
                    result.add_error(ValidationError(
                        'unusual_amount',
                        f"Montant inhabituel: {amount}€",
                        severity='warning'
                    ))

        if not any(e.error_type in ['forbidden_amount', 'unusual_amount'] for e in result.errors):
            result.add_passed('amounts_check')

    def _check_format(self, response: str, result: ValidationResult):
        """Vérifie le format et la structure de la réponse."""
        # Longueur raisonnable
        if len(response) < 50:
            result.add_error(ValidationError(
                'too_short',
                "Réponse trop courte",
                severity='warning'
            ))

        if len(response) > 5000:
            result.add_error(ValidationError(
                'too_long',
                "Réponse trop longue",
                severity='warning'
            ))

        # Commence par une salutation
        if not re.match(r'^(bonjour|cher|chère|madame|monsieur)', response, re.IGNORECASE):
            result.add_error(ValidationError(
                'missing_greeting',
                "La réponse ne commence pas par une salutation",
                severity='warning'
            ))

        # Se termine par une formule de politesse
        if not re.search(r'(cordialement|bien à vous|salutations)', response[-200:], re.IGNORECASE):
            result.add_error(ValidationError(
                'missing_closing',
                "La réponse ne se termine pas par une formule de politesse",
                severity='warning'
            ))

        # Pas de placeholders non résolus
        unresolved = re.findall(r'\{\{[^}]+\}\}', response)
        if unresolved:
            result.add_error(ValidationError(
                'unresolved_placeholder',
                f"Placeholders non résolus: {unresolved}",
                severity='error'
            ))

        if not any(e.error_type in ['too_short', 'too_long', 'missing_greeting',
                                     'missing_closing', 'unresolved_placeholder']
                   for e in result.errors + result.warnings):
            result.add_passed('format_check')

    def _should_skip_blocks_validation(
        self,
        state: DetectedState,
        template_used: Optional[str]
    ) -> bool:
        """
        Détermine si on doit ignorer la validation des blocs obligatoires.

        Quand le template utilisé est différent du template par défaut de l'état
        (ex: report_bloque utilisé pour CONVOCATION_RECEIVED avec intention REPORT_DATE),
        les blocs requis de l'état ne sont pas pertinents.

        Args:
            state: État détecté
            template_used: Nom du template réellement utilisé

        Returns:
            True si on doit ignorer la validation des blocs
        """
        if not template_used:
            return False

        # Templates qui ont leurs propres règles de validation
        # et ne doivent pas être validés avec les blocs de l'état détecté
        override_templates = [
            'report_bloque',
            'report_bloque_force_majeure',
            'credentials_refused',
            'credentials_refused_security',
        ]

        # Si le template utilisé est un template "override", on ignore la validation
        # des blocs de l'état car ils ne sont pas pertinents
        for override in override_templates:
            if override in template_used.lower():
                logger.info(f"⚡ Validation des blocs ignorée (template override: {template_used})")
                return True

        # Vérifier aussi par intention - si l'intention est REPORT_DATE ou REFUS_PARTAGE_CREDENTIALS
        # et que le template n'est pas celui par défaut de l'état, ignorer la validation
        context = state.context_data
        detected_intent = context.get('detected_intent')

        if detected_intent in ['REPORT_DATE', 'REFUS_PARTAGE_CREDENTIALS', 'FORCE_MAJEURE_REPORT']:
            # Pour ces intentions, le template utilisé est souvent différent du template de l'état
            default_template = state.response_config.get('template', '')
            if default_template and template_used and default_template != template_used:
                logger.info(f"⚡ Validation des blocs ignorée (intention {detected_intent}, template {template_used} != {default_template})")
                return True

        return False

    def _find_location(self, text: str, search: str) -> str:
        """Trouve la position approximative d'un texte."""
        idx = text.lower().find(search.lower())
        if idx == -1:
            return ""

        # Extraire le contexte
        start = max(0, idx - 20)
        end = min(len(text), idx + len(search) + 20)
        context = text[start:end]

        return f"...{context}..."

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """Normalise une date en YYYY-MM-DD."""
        try:
            # Essayer DD/MM/YYYY
            dt = datetime.strptime(date_str, '%d/%m/%Y')
            return dt.strftime('%Y-%m-%d')
        except Exception as e:
            pass

        try:
            # Essayer YYYY-MM-DD
            dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
            return dt.strftime('%Y-%m-%d')
        except Exception as e:
            pass

        return None

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse une date en objet date."""
        normalized = self._normalize_date(date_str)
        if normalized:
            return datetime.strptime(normalized, '%Y-%m-%d').date()
        return None
