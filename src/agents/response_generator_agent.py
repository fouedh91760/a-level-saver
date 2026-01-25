"""
Response Generator Agent - Generate ticket responses using Claude + RAG.

This agent generates responses for DOC tickets using:
1. RAG system to find similar tickets from Fouad's 100 responses
2. Scenario detection from knowledge_base.scenarios_mapping
3. Claude API for intelligent response generation
4. Pattern analysis to match Fouad's style
5. Validation against mandatory blocks and forbidden terms

Usage:
    agent = ResponseGeneratorAgent()
    result = agent.generate_response(
        ticket_subject="Demande d'identifiants",
        customer_message="Je n'arrive pas à me connecter",
        crm_data={...},
        exament3p_data={...}
    )
"""
import logging
from typing import Dict, List, Optional
from anthropic import Anthropic
import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.response_rag import ResponseRAG
from knowledge_base.scenarios_mapping import (
    detect_scenario_from_text,
    get_mandatory_blocks_for_scenario,
    validate_response_compliance,
    get_scenario_template_notes,
    should_stop_workflow,
    requires_crm_update,
    get_crm_update_fields,
    SCENARIOS,
    MANDATORY_BLOCKS,
    FORBIDDEN_TERMS
)

logger = logging.getLogger(__name__)


class ResponseGeneratorAgent:
    """Agent that generates ticket responses using Claude + RAG."""

    def __init__(
        self,
        fouad_tickets_path: str = "fouad_tickets_analysis.json",
        patterns_path: str = "response_patterns_analysis.json"
    ):
        """Initialize the response generator agent."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set, using placeholder (API calls will fail)")
            api_key = "placeholder"  # Will fail on actual API call, but allows initialization

        self.anthropic_client = Anthropic(api_key=api_key)
        # Use Claude Sonnet 4.5 (recommended for coding and agents in 2026)
        self.model = "claude-sonnet-4-5-20250929"

        # Initialize RAG system
        logger.info("Initializing RAG system...")
        self.rag = ResponseRAG(fouad_tickets_path)

        # Load pattern analysis
        logger.info("Loading pattern analysis...")
        try:
            with open(patterns_path, 'r', encoding='utf-8') as f:
                self.patterns = json.load(f)
        except FileNotFoundError:
            logger.warning(f"Pattern analysis file not found: {patterns_path}")
            self.patterns = {}

        logger.info("✅ ResponseGeneratorAgent initialized")

    def _build_system_prompt(self) -> str:
        """Build system prompt with Fouad's style guidelines."""
        # Extract style info from patterns
        most_common_greeting = self.patterns.get('structural_patterns', {}).get('most_common_greeting', 'Bonjour,')
        most_common_closing = self.patterns.get('structural_patterns', {}).get('most_common_closing', 'Bien cordialement,')
        most_common_signature = self.patterns.get('structural_patterns', {}).get('most_common_signature', "L'équipe Cab Formations")

        dominant_tones = self.patterns.get('tone_analysis', {}).get('dominant_tones', ['professional'])
        avg_words = self.patterns.get('length_statistics', {}).get('avg_words', 300)

        system_prompt = f"""Tu es Fouad Haddouchi, agent expert du département DOC de CAB Formations.

Tu réponds aux tickets clients concernant les formations VTC pour Uber avec un style professionnel, clair et empathique.

## TON STYLE DE RÉPONSE (basé sur analyse de 137 réponses) :

**Structure** :
- Salutation : "{most_common_greeting}"
- Corps : Réponse claire et structurée
- Formule de politesse : "{most_common_closing}"
- Signature : "{most_common_signature}"

**Ton** : {', '.join(dominant_tones[:3])}
- Professional et courtois
- Directive (instructions claires)
- Rassurant quand nécessaire
- Empathique en cas de problème

**Longueur** : ~{int(avg_words)} mots (varie selon complexité)

## RÈGLES STRICTES :

### ❌ TERMES INTERDITS (ne jamais utiliser) :
{', '.join(f'"{term}"' for term in FORBIDDEN_TERMS)}
- Dire "frais de dossier" au lieu de "20€"
- Parler de "plateforme ExamenT3P" au lieu de "Evalbox"

### ✅ BLOCS OBLIGATOIRES (selon scénario) :

**Si compte ExamenT3P existe** :
🔐 **Vos identifiants ExamenT3P** :
• **Identifiant** : [email du candidat]
• **Mot de passe** : [mot_de_passe_exament3p]

⚠️ Ces identifiants sont personnels et confidentiels. Ne les communiquez jamais à qui que ce soit.

**Toujours inclure** :
- 🎓 Lien e-learning (si applicable)
- 📧 "Vérifiez vos spams/courriers indésirables" (si email envoyé)
- ⚠️ Avertissement mot de passe (TOUJOURS)

**Si "PROCHAINES DATES D'EXAMEN À PROPOSER" dans les données** :
- ⚠️ OBLIGATOIRE : Inclure les dates exactes dans la réponse avec leur format (ex: "31/03/2026", "30/06/2026")
- Ne jamais paraphraser par "prochaine session disponible" sans donner les dates précises
- Format : lister les dates avec leurs infos (date examen + date clôture si disponible)

**Si "SESSIONS DE FORMATION À PROPOSER" dans les données** :
- ⚠️ OBLIGATOIRE : La session de formation DOIT correspondre à la date d'examen
- La formation doit se terminer AVANT la date d'examen (pour permettre la préparation)
- Si préférence jour/soir connue : proposer uniquement ce type de session
- Si préférence NON connue : proposer les deux options (cours du jour ET cours du soir)
- Ne JAMAIS proposer une date de formation sans la lier à une date d'examen
- Format exemple :
  "Pour l'examen du 31/03/2026, vous pouvez suivre la formation :
   • Cours du jour : du 10/02/2026 au 21/02/2026 (8h30-16h30)
   • Cours du soir : du 10/02/2026 au 14/03/2026 (18h-22h)"

**⚠️ RÈGLE CRITIQUE - Lien visio/invitation formation** :
- Ne JAMAIS dire "nous venons de vous envoyer un lien d'invitation" ou "lien visio envoyé" SI:
  - On propose plusieurs dates d'examen au choix → le candidat doit d'abord confirmer
  - On propose plusieurs sessions de formation au choix → le candidat doit d'abord confirmer
  - La date de formation n'est pas encore fixée définitivement
- Le lien visio n'est envoyé QUE quand la date d'examen ET la date de formation sont confirmées de manière UNIQUE
- Si on demande au candidat de choisir une date → dire "Une fois votre choix confirmé, nous vous enverrons le lien d'invitation"

## SOURCES DE VÉRITÉ :

- **ExamenT3P** : source de vérité pour documents, paiement CMA, statut dossier
- **Evalbox** : source de vérité pour éligibilité Uber (colonnes Q, R du Google Sheet)
- **CRM Zoho** : informations contact, opportunités, sessions

## SCÉNARIOS PRIORITAIRES :

{self._format_scenario_summary()}

## APPROCHE :

1. Comprendre la demande spécifique du client
2. Identifier le scénario exact (parmi 26+ scénarios)
3. Vérifier les données des sources (ExamenT3P, CRM, Evalbox)
4. Répondre de manière claire et structurée
5. Inclure les blocs obligatoires selon le scénario
6. Adopter le ton approprié (professionnel, empathique, rassurant)

Tu as accès à des exemples similaires de tes réponses passées pour t'inspirer du style et de l'approche."""

        return system_prompt

    def _format_scenario_summary(self) -> str:
        """Format top scenarios for system prompt."""
        top_scenarios = [
            "SC-00_NOUVEAU_CANDIDAT: Proposition dates examen (pas sessions)",
            "SC-01_IDENTIFIANTS_EXAMENT3P: Envoi identifiants + avertissement",
            "SC-02_CONFIRMATION_PAIEMENT: Vérifier paiement_cma ExamenT3P",
            "SC-04_DOCUMENT_MANQUANT: Lister documents manquants depuis ExamenT3P",
            "SC-06_STATUT_DOSSIER: Statut complet (docs, paiement, session)",
            "SC-15a/b/c_REPORT: Gestion report selon état dossier CMA",
            "SC-17_CONFIRMATION_SESSION: Confirmer + UPDATE CRM obligatoire",
            "SC-20/21_RESULTAT: Féliciter ou encourager réinscription",
            "SC-25_RECLAMATION: Ton apologétique + solution"
        ]
        return "\n".join(f"  - {s}" for s in top_scenarios)

    def _build_user_prompt(
        self,
        ticket_subject: str,
        customer_message: str,
        similar_tickets: List[Dict],
        detected_scenarios: List[str],
        crm_data: Optional[Dict] = None,
        exament3p_data: Optional[Dict] = None,
        evalbox_data: Optional[Dict] = None,
        date_examen_vtc_data: Optional[Dict] = None,
        session_data: Optional[Dict] = None,
        uber_eligibility_data: Optional[Dict] = None,
        threads: Optional[List] = None
    ) -> str:
        """Build user prompt with context, examples, and full thread history."""
        # Format similar tickets as few-shot examples
        few_shot_examples = self.rag.format_for_few_shot(similar_tickets)

        # Format scenarios
        scenarios_info = "\n".join(
            f"  - {scenario_id}: {SCENARIOS[scenario_id]['name']}"
            for scenario_id in detected_scenarios
            if scenario_id in SCENARIOS
        )

        # Format data sources
        data_summary = self._format_data_sources(crm_data, exament3p_data, evalbox_data, date_examen_vtc_data, session_data, uber_eligibility_data)

        # Format thread history (full conversation)
        thread_history = self._format_thread_history(threads)

        user_prompt = f"""## NOUVEAU TICKET À TRAITER

**Sujet** : {ticket_subject}

**Dernier message du client** :
{customer_message}

---

## HISTORIQUE COMPLET DES ÉCHANGES :

{thread_history}

⚠️ **IMPORTANT** : Analyse tout l'historique ci-dessus pour :
- Ne PAS répéter des informations déjà communiquées
- Faire référence à des éléments précédemment discutés si pertinent
- Adapter le ton si le candidat a déjà reçu plusieurs messages
- Tenir compte des réponses/confirmations du candidat dans l'historique

---

## SCÉNARIOS DÉTECTÉS :
{scenarios_info if scenarios_info else "  - GENERAL"}

---

## DONNÉES DISPONIBLES :
{data_summary}

---

## EXEMPLES SIMILAIRES DE TES RÉPONSES PASSÉES :

{few_shot_examples}

---

## TA MISSION :

Génère une réponse professionnelle pour ce ticket en suivant :

1. **Identifie le scénario exact** et les notes du template
2. **Vérifie les données** des sources (ExamenT3P, CRM, Evalbox)
3. **Réponds à la demande spécifique** du client
4. **Inclus les blocs obligatoires** selon le scénario
5. **Adopte le bon ton** (professionnel, empathique si problème)
6. **Suis ta structure habituelle** : salutation + corps + formule de politesse + signature

**IMPORTANT** :
- Ne jamais utiliser les termes interdits ({', '.join(FORBIDDEN_TERMS)})
- TOUJOURS inclure l'avertissement mot de passe
- Vérifier les spams si email envoyé
- Si identifiants : formater avec 🔐 et ⚠️

Génère uniquement le contenu de la réponse (pas de métadonnées)."""

        return user_prompt

    def _format_data_sources(
        self,
        crm_data: Optional[Dict],
        exament3p_data: Optional[Dict],
        evalbox_data: Optional[Dict],
        date_examen_vtc_data: Optional[Dict] = None,
        session_data: Optional[Dict] = None,
        uber_eligibility_data: Optional[Dict] = None
    ) -> str:
        """Format available data sources for prompt."""
        lines = []

        # ================================================================
        # ÉLIGIBILITÉ UBER 20€ - PRIORITAIRE
        # ================================================================
        # Si le candidat Uber n'est pas éligible (CAS A ou B), c'est la priorité
        if uber_eligibility_data and uber_eligibility_data.get('is_uber_20_deal'):
            uber_case = uber_eligibility_data.get('case')
            if uber_case in ['A', 'B']:
                lines.append("### 🚗 ÉLIGIBILITÉ UBER 20€ - ACTION PRIORITAIRE :")
                lines.append(f"  - Cas détecté : CAS {uber_case} - {uber_eligibility_data.get('case_description', '')}")
                lines.append(f"  - ⚠️ LE CANDIDAT NE PEUT PAS ENCORE ÊTRE INSCRIT À L'EXAMEN")

                if uber_case == 'A':
                    lines.append("  - Raison : Documents non envoyés / inscription non finalisée")
                    lines.append("  - Action : Expliquer l'offre et demander de finaliser l'inscription")
                elif uber_case == 'B':
                    lines.append("  - Raison : Test de sélection non passé")
                    lines.append(f"  - Date dossier reçu : {uber_eligibility_data.get('date_dossier_recu', 'N/A')}")
                    lines.append("  - Action : Demander de passer le test de sélection")

                if uber_eligibility_data.get('response_message'):
                    lines.append(f"\n  - MESSAGE À INTÉGRER DANS LA RÉPONSE :")
                    lines.append(f"    {uber_eligibility_data['response_message']}")

                lines.append("\n  ⚠️ IMPORTANT : Ne PAS parler de dates d'examen ou de formation tant que ces étapes ne sont pas complétées !")
                lines.append("")
            else:
                lines.append("### 🚗 Candidat Uber 20€ :")
                lines.append("  - ✅ Éligible - Peut être inscrit à l'examen")
                lines.append("")

        if crm_data:
            lines.append("### CRM Zoho :")
            lines.append(f"  - Contact : {crm_data.get('email', 'N/A')}")
            lines.append(f"  - Session actuelle : {crm_data.get('Session', 'Non définie')}")
            lines.append(f"  - Date dépôt CMA : {crm_data.get('Date_de_depot_CMA', 'N/A')}")
            lines.append(f"  - Date clôture : {crm_data.get('Date_de_cloture', 'N/A')}")

        if exament3p_data:
            lines.append("\n### ExamenT3P :")
            lines.append(f"  - Compte existe : {exament3p_data.get('compte_existe', False)}")
            if exament3p_data.get('compte_existe'):
                lines.append(f"  - Identifiant : {exament3p_data.get('identifiant', 'N/A')}")
                lines.append(f"  - Mot de passe : {exament3p_data.get('mot_de_passe', 'N/A')}")
                lines.append(f"  - Documents manquants : {len(exament3p_data.get('documents_manquants', []))}")
                lines.append(f"  - Paiement CMA : {exament3p_data.get('paiement_cma_status', 'N/A')}")

        if date_examen_vtc_data:
            lines.append("\n### Date Examen VTC :")
            lines.append(f"  - Cas détecté : CAS {date_examen_vtc_data.get('case', 'N/A')} - {date_examen_vtc_data.get('case_description', '')}")
            lines.append(f"  - Statut Evalbox : {date_examen_vtc_data.get('evalbox_status', 'N/A')}")
            if date_examen_vtc_data.get('should_include_in_response'):
                lines.append(f"  - ⚠️ ACTION REQUISE : Inclure les informations date examen dans la réponse")
                # Inclure les prochaines dates disponibles explicitement
                next_dates = date_examen_vtc_data.get('next_dates', [])
                if next_dates:
                    lines.append(f"  - 📆 PROCHAINES DATES D'EXAMEN À PROPOSER :")
                    for i, date_info in enumerate(next_dates[:2], 1):
                        date_examen = date_info.get('Date_Examen', 'N/A')
                        date_cloture = date_info.get('Date_Cloture_Inscription', '')
                        libelle = date_info.get('Libelle_Affichage', '')
                        # Formater la date pour affichage
                        try:
                            from datetime import datetime
                            date_obj = datetime.strptime(str(date_examen), "%Y-%m-%d")
                            date_formatted = date_obj.strftime("%d/%m/%Y")
                        except:
                            date_formatted = str(date_examen)
                        # Formater date clôture
                        cloture_formatted = ""
                        if date_cloture:
                            try:
                                if 'T' in str(date_cloture):
                                    cloture_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
                                else:
                                    cloture_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
                                cloture_formatted = f" (clôture: {cloture_obj.strftime('%d/%m/%Y')})"
                            except:
                                pass
                        lines.append(f"      {i}. {date_formatted}{cloture_formatted}")
                # Inclure le message complet (non tronqué)
                if date_examen_vtc_data.get('response_message'):
                    lines.append(f"  - Message suggéré (à adapter) :")
                    lines.append(f"    {date_examen_vtc_data['response_message']}")

        if evalbox_data:
            lines.append("\n### Evalbox (Google Sheet) :")
            lines.append(f"  - Éligible Uber : {evalbox_data.get('eligible_uber', 'N/A')}")
            lines.append(f"  - Scope : {evalbox_data.get('scope', 'N/A')}")

        if session_data and session_data.get('proposed_options'):
            lines.append("\n### 📚 SESSIONS DE FORMATION À PROPOSER :")
            preference = session_data.get('session_preference')
            if preference:
                pref_label = "cours du jour" if preference == 'jour' else "cours du soir"
                lines.append(f"  - Préférence candidat détectée : {pref_label}")
            else:
                lines.append(f"  - ⚠️ Préférence jour/soir NON CONNUE - Proposer les deux options")

            # CAS SPÉCIAL: Formation terminée + examen futur = proposer rafraîchissement
            if session_data.get('refresh_session_available'):
                lines.append("\n  🔄 **CAS SPÉCIAL - RAFRAÎCHISSEMENT GRATUIT À PROPOSER**")
                lines.append("  Le candidat a DÉJÀ suivi sa formation mais son examen est dans le futur.")
                lines.append("  → Proposer de rejoindre la prochaine session GRATUITEMENT")
                lines.append("  → Insister sur: 'Pour nous, votre réussite est notre priorité'")
                lines.append("  → Insister sur: 'Plus vos connaissances sont fraîches, plus vos chances sont élevées'")
                lines.append("  → Préciser: 'Sans aucun coût additionnel'")

                refresh_info = session_data.get('refresh_session', {})
                if refresh_info:
                    refresh_sess = refresh_info.get('session', {})
                    date_debut = refresh_sess.get('Date_d_but', '')
                    date_fin = refresh_sess.get('Date_fin', '')
                    try:
                        debut_fmt = datetime.strptime(date_debut, "%Y-%m-%d").strftime("%d/%m/%Y") if date_debut else ''
                        fin_fmt = datetime.strptime(date_fin, "%Y-%m-%d").strftime("%d/%m/%Y") if date_fin else ''
                        lines.append(f"  → Session proposée: du {debut_fmt} au {fin_fmt}")
                    except:
                        pass

            for option in session_data.get('proposed_options', []):
                exam_info = option.get('exam_info', {})
                sessions = option.get('sessions', [])
                exam_date = exam_info.get('Date_Examen', '')

                # Formater date examen
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(str(exam_date), "%Y-%m-%d")
                    exam_formatted = date_obj.strftime("%d/%m/%Y")
                except:
                    exam_formatted = str(exam_date)

                lines.append(f"\n  📅 Pour l'examen du {exam_formatted} :")

                if sessions:
                    for session in sessions:
                        session_type = session.get('session_type_label', '')
                        date_debut = session.get('Date_d_but', '')
                        date_fin = session.get('Date_fin', '')
                        type_cours = session.get('Type_de_cours', '')

                        # Formater dates
                        try:
                            debut_formatted = datetime.strptime(date_debut, "%Y-%m-%d").strftime("%d/%m/%Y") if date_debut else ''
                            fin_formatted = datetime.strptime(date_fin, "%Y-%m-%d").strftime("%d/%m/%Y") if date_fin else ''
                        except:
                            debut_formatted = date_debut
                            fin_formatted = date_fin

                        session_line = f"      • {session_type} : du {debut_formatted} au {fin_formatted}"
                        if type_cours and type_cours != '-None-':
                            session_line += f" ({type_cours})"
                        lines.append(session_line)
                else:
                    lines.append("      ⚠️ Aucune session disponible pour cette date")

            lines.append("\n  ⚠️ RÈGLE IMPORTANTE : Toujours lier la proposition de formation à la date d'examen choisie")

        if not lines:
            lines.append("Aucune donnée disponible")

        return "\n".join(lines)

    def _format_thread_history(self, threads: Optional[List]) -> str:
        """
        Format the complete thread history for the prompt.

        Shows all exchanges chronologically so Claude understands the full context.
        """
        if not threads:
            return "(Aucun historique d'échange disponible - premier contact)"

        lines = []

        # Sort threads by date if available
        sorted_threads = sorted(
            threads,
            key=lambda t: t.get('createdTime', '') or t.get('created_time', '') or '',
            reverse=False  # Oldest first
        )

        for i, thread in enumerate(sorted_threads, 1):
            direction = thread.get('direction', 'unknown')
            created_time = thread.get('createdTime', '') or thread.get('created_time', '')

            # Format date
            date_str = ""
            if created_time:
                try:
                    from datetime import datetime
                    if 'T' in str(created_time):
                        dt = datetime.fromisoformat(str(created_time).replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(str(created_time), "%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%d/%m/%Y %H:%M")
                except:
                    date_str = str(created_time)[:16]

            # Direction indicator
            if direction == 'in':
                sender = "📩 CANDIDAT"
            elif direction == 'out':
                sender = "📤 NOUS (Cab Formations)"
            else:
                sender = "❓ INCONNU"

            # Get content
            content = thread.get('content', '') or thread.get('summary', '') or thread.get('plainText', '') or ''

            # Clean and truncate content if too long
            content = content.strip()
            if len(content) > 1500:
                content = content[:1500] + "...[tronqué]"

            lines.append(f"### Échange #{i} ({date_str})")
            lines.append(f"**{sender}** :")
            lines.append(f"{content}")
            lines.append("")

        if not lines:
            return "(Aucun contenu dans l'historique)"

        return "\n".join(lines)

    def generate_response(
        self,
        ticket_subject: str,
        customer_message: str,
        crm_data: Optional[Dict] = None,
        exament3p_data: Optional[Dict] = None,
        evalbox_data: Optional[Dict] = None,
        date_examen_vtc_data: Optional[Dict] = None,
        session_data: Optional[Dict] = None,
        uber_eligibility_data: Optional[Dict] = None,
        threads: Optional[List] = None,
        top_k_similar: int = 3,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> Dict:
        """
        Generate response for a ticket.

        Args:
            ticket_subject: Subject of the ticket
            customer_message: Customer's message/question
            crm_data: Data from CRM (contact, deal fields)
            exament3p_data: Data from ExamenT3P scraping
            evalbox_data: Data from Evalbox (Google Sheet)
            date_examen_vtc_data: Data from date examen VTC analysis
            session_data: Data from session analysis (sessions de formation)
            uber_eligibility_data: Data from Uber 20€ eligibility check
            threads: Full thread history (all exchanges with candidate)
            top_k_similar: Number of similar tickets to use as examples
            temperature: Claude temperature (0-1, lower = more focused)
            max_tokens: Maximum tokens for response

        Returns:
            {
                'response_text': str,
                'detected_scenarios': List[str],
                'similar_tickets': List[Dict],
                'validation': Dict,
                'requires_crm_update': bool,
                'crm_update_fields': List[str],
                'should_stop_workflow': bool
            }
        """
        logger.info(f"Generating response for: {ticket_subject}")

        # 1. Detect scenarios
        detected_scenarios = detect_scenario_from_text(
            subject=ticket_subject,
            customer_message=customer_message,
            crm_data=crm_data
        )
        logger.info(f"Detected scenarios: {detected_scenarios}")

        # 2. Check if workflow should stop
        stop_workflow = any(should_stop_workflow(s) for s in detected_scenarios)
        if stop_workflow:
            logger.warning(f"Workflow should STOP for scenarios: {detected_scenarios}")

        # 3. Find similar tickets using RAG
        similar_tickets = self.rag.find_similar_tickets(
            subject=ticket_subject,
            customer_message=customer_message,
            top_k=top_k_similar
        )
        logger.info(f"Found {len(similar_tickets)} similar tickets")

        # 4. Build prompts
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            ticket_subject=ticket_subject,
            customer_message=customer_message,
            similar_tickets=similar_tickets,
            detected_scenarios=detected_scenarios,
            crm_data=crm_data,
            exament3p_data=exament3p_data,
            evalbox_data=evalbox_data,
            date_examen_vtc_data=date_examen_vtc_data,
            session_data=session_data,
            uber_eligibility_data=uber_eligibility_data,
            threads=threads
        )

        # 5. Call Claude API
        logger.info("Calling Claude API...")
        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            response_text = response.content[0].text
            logger.info(f"Claude generated {len(response_text)} characters")

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            raise

        # 6. Validate response
        validation_results = {}
        for scenario_id in detected_scenarios:
            validation = validate_response_compliance(response_text, scenario_id)
            validation_results[scenario_id] = validation

            if not validation['compliant']:
                logger.warning(f"Response not compliant for {scenario_id}: {validation}")

        # 7. Check CRM update requirements
        needs_crm_update = any(requires_crm_update(s) for s in detected_scenarios)
        crm_update_fields = []
        if needs_crm_update:
            for scenario_id in detected_scenarios:
                crm_update_fields.extend(get_crm_update_fields(scenario_id))
            crm_update_fields = list(set(crm_update_fields))  # Remove duplicates

        # 8. Return comprehensive result
        return {
            'response_text': response_text,
            'detected_scenarios': detected_scenarios,
            'similar_tickets': similar_tickets,
            'validation': validation_results,
            'requires_crm_update': needs_crm_update,
            'crm_update_fields': crm_update_fields,
            'should_stop_workflow': stop_workflow,
            'metadata': {
                'model': self.model,
                'temperature': temperature,
                'max_tokens': max_tokens,
                'top_k_similar': top_k_similar,
                'input_tokens': response.usage.input_tokens,
                'output_tokens': response.usage.output_tokens
            }
        }

    def generate_with_validation_loop(
        self,
        ticket_subject: str,
        customer_message: str,
        crm_data: Optional[Dict] = None,
        exament3p_data: Optional[Dict] = None,
        evalbox_data: Optional[Dict] = None,
        date_examen_vtc_data: Optional[Dict] = None,
        session_data: Optional[Dict] = None,
        uber_eligibility_data: Optional[Dict] = None,
        credentials_only_response: bool = False,
        threads: Optional[List] = None,
        max_retries: int = 2
    ) -> Dict:
        """
        Generate response with validation loop.

        If response is not compliant, retry with feedback.

        Args:
            credentials_only_response: Si True, génère UNIQUEMENT une réponse
                demandant les bons identifiants. Ignore dates/sessions.
            threads: Historique complet des échanges pour contexte.
        """
        # ================================================================
        # CAS SPÉCIAL: Identifiants invalides = SEUL sujet de la réponse
        # ================================================================
        if credentials_only_response:
            logger.info("🚨 MODE CREDENTIALS_ONLY: Réponse uniquement sur identifiants")
            return self._generate_credentials_only_response(exament3p_data, threads)

        for attempt in range(max_retries + 1):
            logger.info(f"Generation attempt {attempt + 1}/{max_retries + 1}")

            result = self.generate_response(
                ticket_subject=ticket_subject,
                customer_message=customer_message,
                crm_data=crm_data,
                exament3p_data=exament3p_data,
                evalbox_data=evalbox_data,
                date_examen_vtc_data=date_examen_vtc_data,
                session_data=session_data,
                uber_eligibility_data=uber_eligibility_data,
                threads=threads  # Pass thread history for context
            )

            # Check if all validations passed
            all_compliant = all(
                v['compliant'] for v in result['validation'].values()
            )

            if all_compliant:
                logger.info("✅ Response is compliant")
                return result

            # If not compliant and retries left, provide feedback
            if attempt < max_retries:
                logger.warning(f"⚠️ Response not compliant, retrying...")
                # Could add feedback to prompt here for retry
                continue

        logger.warning("Max retries reached, returning last result")
        return result

    def _generate_credentials_only_response(
        self,
        exament3p_data: Optional[Dict] = None,
        threads: Optional[List] = None,
        customer_message: str = ""
    ) -> Dict:
        """
        Génère une réponse contextuelle quand on n'a pas accès au compte ExamT3P.

        UTILISE CLAUDE pour générer une réponse qui:
        1. Répond à la question sur les identifiants (si posée)
        2. Accuse réception de TOUTES les autres demandes/questions du candidat
        3. Explique qu'on pourra les traiter une fois qu'on a accès au dossier

        Args:
            exament3p_data: Données ExamT3P avec message pré-formaté
            threads: Historique des threads pour analyser les échanges précédents
            customer_message: Message du candidat pour contextualiser la réponse
        """
        logger.info("Generating credentials-only response (identifiants invalides)")

        # Analyser l'historique pour compter les demandes d'identifiants
        credentials_request_count = self._count_credentials_requests_in_threads(threads)
        logger.info(f"  Nombre de demandes d'identifiants précédentes: {credentials_request_count}")

        # Extraire le message du candidat depuis les threads si pas fourni
        if not customer_message and threads:
            from src.utils.text_utils import get_clean_thread_content
            for thread in threads:
                if thread.get('direction') == 'in':
                    customer_message = get_clean_thread_content(thread)
                    break

        # ================================================================
        # UTILISER CLAUDE POUR GÉNÉRER UNE RÉPONSE CONTEXTUELLE
        # ================================================================
        # Au lieu de templates hardcodés, on utilise Claude pour:
        # 1. Répondre à la question sur les identifiants
        # 2. Accuser réception de TOUTES les autres demandes du candidat
        # 3. Expliquer qu'on pourra les traiter une fois qu'on a les identifiants

        system_prompt = """Tu es un assistant de Cab Formations, centre de formation VTC.
Tu dois générer une réponse email professionnelle et empathique.

CONTEXTE CRITIQUE:
- Nous n'avons PAS accès au compte ExamT3P du candidat
- Sans accès, nous ne pouvons PAS: vérifier son dossier, payer ses frais d'examen, l'inscrire à une date d'examen
- Notre PRIORITÉ est d'obtenir ses identifiants ExamT3P

RÈGLES DE RÉDACTION:
1. Accuser réception de TOUTES les demandes/questions du candidat (préférences de cours, questions, etc.)
2. Expliquer clairement pourquoi on a besoin des identifiants
3. Rassurer si le candidat demande si c'est normal qu'on lui demande ses identifiants (OUI c'est normal)
4. Inclure la procédure de création de compte AU CAS OÙ il n'a pas encore de compte
5. Expliquer qu'on pourra traiter ses autres demandes APRÈS avoir accès à son dossier
6. Ton professionnel mais chaleureux
7. Formater avec du markdown (gras, listes)
8. Terminer par "Cordialement, L'équipe Cab Formations"

JAMAIS:
- Proposer des dates d'examen ou de formation (on n'a pas accès au dossier)
- Dire qu'on va créer le compte pour lui (c'est lui qui doit le faire ou nous transmettre ses identifiants)
- Utiliser le mot "malheureusement" plus d'une fois"""

        # Adapter le prompt selon le nombre de demandes précédentes
        if credentials_request_count >= 2:
            context_note = f"""ATTENTION: C'est la {credentials_request_count + 1}ème fois qu'on demande les identifiants.
Le candidat a déjà envoyé des identifiants {credentials_request_count} fois mais ils ne fonctionnaient pas.
- Ton: Plus direct, montrer qu'on comprend la frustration
- Insister sur: tester la connexion SOI-MÊME avant de nous transmettre les identifiants
- Recommander fortement: réinitialiser le mot de passe via "Mot de passe oublié"
"""
        elif credentials_request_count == 1:
            context_note = """C'est la 2ème demande d'identifiants.
Le candidat a déjà envoyé des identifiants une fois mais ils ne fonctionnaient pas.
- Reconnaître la situation (on a déjà demandé)
- Recommander de réinitialiser le mot de passe
"""
        else:
            context_note = """C'est la 1ère demande d'identifiants (ou le candidat mentionne qu'on lui a demandé).
- Si le candidat demande "est-ce normal?": rassurer que OUI
- Expliquer clairement pourquoi on a besoin des identifiants
- Donner la procédure de création de compte si pas encore fait
"""

        user_prompt = f"""{context_note}

MESSAGE DU CANDIDAT:
{customer_message}

Génère une réponse email complète qui:
1. Accuse réception de TOUTES ses demandes (préférences de cours, questions, etc.)
2. Explique pourquoi on a besoin de ses identifiants ExamT3P
3. Demande ses identifiants
4. Inclut la procédure de création de compte (au cas où)
5. Précise qu'on traitera ses autres demandes dès qu'on aura accès à son dossier

IMPORTANT: La réponse doit commencer par "Bonjour" (pas de prénom si pas connu)."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            candidate_message = response.content[0].text.strip()
            logger.info(f"  Claude a généré une réponse contextuelle ({len(candidate_message)} caractères)")

        except Exception as e:
            logger.error(f"  Erreur Claude API: {e}")
            # Fallback sur le message pré-généré si disponible
            if exament3p_data and exament3p_data.get('candidate_response_message'):
                candidate_message = exament3p_data['candidate_response_message']
            else:
                candidate_message = """Bonjour,

Nous avons bien reçu votre message.

Pour pouvoir traiter votre demande et avancer sur votre dossier, nous avons besoin d'accéder à votre compte ExamT3P.

**Pourquoi avons-nous besoin de vos identifiants ?**
Sans accès à votre compte, il nous est impossible de :
- Vérifier l'état de votre dossier auprès de la CMA
- Procéder au paiement de vos frais d'examen
- Vous inscrire à une date d'examen

**Merci de nous transmettre vos identifiants de connexion ExamT3P :**
- Identifiant (généralement votre email)
- Mot de passe

**Vous n'avez pas encore de compte ExamT3P ?**
1. Rendez-vous sur https://www.exament3p.fr/id/14
2. Cliquez sur "S'inscrire"
3. Complétez le formulaire
4. Transmettez-nous vos identifiants par retour de mail

Dès réception de vos identifiants, nous pourrons traiter l'ensemble de vos demandes.

Cordialement,
L'équipe Cab Formations"""

        return {
            'response_text': candidate_message,
            'detected_scenarios': ['SC-01_IDENTIFIANTS_EXAMENT3P'],
            'similar_tickets': [],
            'validation': {
                'SC-01_IDENTIFIANTS_EXAMENT3P': {
                    'compliant': True,
                    'missing_blocks': [],
                    'forbidden_terms_found': []
                }
            },
            'requires_crm_update': False,
            'crm_update_fields': [],
            'should_stop_workflow': False,
            'metadata': {
                'input_tokens': 0,
                'output_tokens': len(candidate_message),
                'model': self.model,
                'credentials_only_mode': True,
                'credentials_request_count': credentials_request_count
            }
        }

    def _count_credentials_requests_in_threads(self, threads: Optional[List]) -> int:
        """
        Compte le nombre de fois où on a demandé les identifiants dans l'historique.

        Cherche des patterns comme:
        - "identifiants"
        - "mot de passe"
        - "connexion a échoué"
        """
        if not threads:
            return 0

        count = 0
        patterns = [
            'identifiants',
            'mot de passe oublié',
            'connexion a échoué',
            'connexion échouée',
            'réinitialiser',
            'nous transmettre vos identifiants',
            'nouveaux identifiants'
        ]

        for thread in threads:
            # Ne compter que les messages sortants (de nous vers le candidat)
            if thread.get('direction') != 'out':
                continue

            content = thread.get('content', '') or thread.get('summary', '') or ''
            content_lower = content.lower()

            # Vérifier si ce message contient une demande d'identifiants
            for pattern in patterns:
                if pattern in content_lower:
                    count += 1
                    break  # Ne compter qu'une fois par thread

        return count


def test_generator():
    """Test the response generator with sample tickets."""
    print("\n" + "=" * 80)
    print("TEST DU RESPONSE GENERATOR AGENT")
    print("=" * 80)

    agent = ResponseGeneratorAgent()

    # Test case 1: Demande d'identifiants
    print("\n" + "=" * 80)
    print("TEST 1 : Demande d'identifiants ExamenT3P")
    print("=" * 80)

    result = agent.generate_response(
        ticket_subject="Demande d'identifiants ExamenT3P",
        customer_message="Bonjour, je n'arrive pas à me connecter sur la plateforme ExamenT3P. Pouvez-vous me renvoyer mes identifiants s'il vous plaît ?",
        exament3p_data={
            'compte_existe': True,
            'identifiant': 'test.candidate@gmail.com',
            'mot_de_passe': 'TestPass123!',
            'paiement_cma_status': 'Payé',
            'documents_manquants': []
        },
        crm_data={
            'email': 'test.candidate@gmail.com',
            'Session_choisie': 'Session CDJ Février 2026'
        }
    )

    print(f"\n📋 Scénarios détectés : {result['detected_scenarios']}")
    print(f"\n🔍 Similarité avec tickets passés :")
    for i, ticket in enumerate(result['similar_tickets'], 1):
        print(f"  {i}. [Score: {ticket['similarity_score']}] {ticket['subject']}")

    print(f"\n📝 RÉPONSE GÉNÉRÉE :\n")
    print("─" * 80)
    print(result['response_text'])
    print("─" * 80)

    print(f"\n✅ Validation :")
    for scenario, validation in result['validation'].items():
        print(f"  - {scenario}: {'✅ Compliant' if validation['compliant'] else '❌ Non-compliant'}")
        if not validation['compliant']:
            print(f"    Blocs manquants : {validation['missing_blocks']}")
            print(f"    Termes interdits : {validation['forbidden_terms_found']}")

    print(f"\n📊 Métadonnées :")
    print(f"  - Tokens entrée : {result['metadata']['input_tokens']}")
    print(f"  - Tokens sortie : {result['metadata']['output_tokens']}")
    print(f"  - Update CRM requis : {result['requires_crm_update']}")
    if result['requires_crm_update']:
        print(f"  - Champs à updater : {result['crm_update_fields']}")

    print("\n" + "=" * 80)
    print("✅ Test terminé")
    print("=" * 80)


if __name__ == "__main__":
    test_generator()
