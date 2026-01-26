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
import re


def _candidate_requests_earlier_dates(message: str) -> bool:
    """
    Détecte si le candidat demande explicitement des dates plus tôt ou d'autres options.

    Retourne True si le candidat mentionne vouloir:
    - Une date plus proche/tôt
    - Un autre département
    - Toutes les options disponibles
    - Une urgence particulière
    """
    if not message:
        return False

    message_lower = message.lower()

    # Mots-clés indiquant une demande de dates plus tôt ou autres options
    earlier_keywords = [
        'plus tôt', 'plus tot', 'plus proche', 'au plus vite',
        'le plus rapidement', 'urgent', 'urgence', 'pressé',
        'autre département', 'autre departement', 'autres départements',
        'ailleurs', 'd\'autres options', 'toutes les options',
        'toutes les dates', 'autres dates', 'date plus rapide',
        'avant', 'rapidement possible'
    ]

    for keyword in earlier_keywords:
        if keyword in message_lower:
            return True

    return False
from typing import Dict, List, Optional, Tuple
from anthropic import Anthropic
import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv


def _parse_crm_updates(response_text: str) -> Tuple[str, Dict[str, str]]:
    """
    Parse CRM_UPDATES block from Claude's response.

    Args:
        response_text: Full response from Claude

    Returns:
        Tuple of (clean_response_text, crm_updates_dict)
    """
    crm_updates = {}

    # Find and extract CRM_UPDATES block
    pattern = r'\[CRM_UPDATES\](.*?)\[/CRM_UPDATES\]'
    match = re.search(pattern, response_text, re.DOTALL)

    if match:
        updates_text = match.group(1).strip()
        # Remove the block from response
        clean_response = re.sub(pattern, '', response_text, flags=re.DOTALL).strip()

        # Parse key-value pairs
        for line in updates_text.split('\n'):
            line = line.strip()
            if ':' in line and line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()
                if value and value.lower() not in ['none', 'null', '']:
                    crm_updates[key] = value

        logger.info(f"📊 Extracted CRM updates: {crm_updates}")
    else:
        clean_response = response_text

    return clean_response, crm_updates

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.response_rag import ResponseRAG
from src.utils.date_examen_vtc_helper import (
    filter_dates_by_region_relevance,
    detect_candidate_region,
    DEPT_TO_REGION
)
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
🔐 Vos identifiants pour accéder à [Mon espace ExamenT3P](https://www.exament3p.fr) :
• Identifiant : [email du candidat]
• Mot de passe : [mot_de_passe_exament3p]

⚠️ Ces identifiants sont personnels et confidentiels. Ne les communiquez jamais à qui que ce soit.

**Toujours inclure** :
- 🎓 Lien e-learning (si applicable) : [Mon E-LEARNING](https://cab-formations.fr/user)
- 📧 "Vérifiez vos spams/courriers indésirables" (si email envoyé)
- ⚠️ Avertissement mot de passe (TOUJOURS pour ExamT3P)
- 🔗 Lien ExamenT3P cliquable quand on donne les identifiants

### ⚠️ IDENTIFIANTS : EXAMENT3P ≠ E-LEARNING (TRÈS IMPORTANT) :

**Les identifiants ExamT3P et E-learning sont DIFFÉRENTS :**
- **ExamT3P** : identifiants fournis dans les données → les donner avec le lien
- **E-learning** : l'identifiant est l'EMAIL D'INSCRIPTION du candidat (voir "Email contact CRM" ci-dessous)

**Si le candidat demande ses identifiants e-learning :**
1. Lui indiquer que son identifiant est l'email utilisé lors de son inscription
2. S'il a perdu son mot de passe → cliquer sur **"Mot de passe oublié"** sur la page de connexion
3. Donner le lien : [Mon E-LEARNING](https://cab-formations.fr/user)

⚠️ NE JAMAIS inventer d'identifiants e-learning - utiliser uniquement l'email du contact CRM si disponible

### 💬 COMMUNICATION DIPLOMATIQUE (TRÈS IMPORTANT) :

**Si le candidat se plaint de ne pas avoir reçu d'information :**
- NE PAS dire "erreur de notre part" ou "manque de communication de notre côté"
- PLUTÔT : "Il est probable que cet email se soit retrouvé dans vos spams/courriers indésirables"
- Ajouter diplomatiquement : "N'hésitez pas à nous alerter dès que vous constatez un manque d'information"
- Rester ultra-diplomatique : reconnaître la frustration sans prendre la faute
- Exemple : "Je comprends votre inquiétude. Ces informations vous ont été envoyées le [date], il est possible qu'elles soient dans vos spams."

### 🔗 LIENS OFFICIELS - NE JAMAIS INVENTER D'URL :

**Utiliser UNIQUEMENT ces liens avec leur nom cliquable :**

| Contexte | Lien | Texte à afficher |
|----------|------|------------------|
| Plateforme ExamenT3P | https://www.exament3p.fr | [Mon espace ExamenT3P](https://www.exament3p.fr) |
| E-learning / cours en ligne | https://cab-formations.fr/user | [Mon E-LEARNING](https://cab-formations.fr/user) |
| Test de sélection Uber | https://cab-formations.fr/user/login?destination=/course/test-de-s%C3%A9lection | [Test de sélection](https://cab-formations.fr/user/login?destination=/course/test-de-s%C3%A9lection) |
| Inscription offre Uber 20€ | https://cab-formations.fr/uberxcab_welcome | [Plateforme inscription offre Cab Uber](https://cab-formations.fr/uberxcab_welcome) |

⚠️ RÈGLES STRICTES POUR LES LIENS :
- NE JAMAIS inventer d'URL
- Toujours utiliser des liens cliquables en markdown : [Texte](URL)
- Pour ExamenT3P : TOUJOURS inclure le lien [Mon espace ExamenT3P](https://www.exament3p.fr) quand on donne les identifiants
- Pour le e-learning : utiliser [Mon E-LEARNING](https://cab-formations.fr/user)
- Pour le test de sélection : utiliser [Test de sélection](https://cab-formations.fr/user/login?destination=/course/test-de-s%C3%A9lection)
- Pour l'inscription Uber : utiliser [Plateforme inscription offre Cab Uber](https://cab-formations.fr/uberxcab_welcome)

### 📝 FORMATAGE DU TEXTE :
- ÉVITER l'abus de **gras** - n'utiliser que pour les éléments vraiment importants
- Les identifiants et mots de passe : pas de gras, juste les valeurs
- Les liens cliquables remplacent le besoin de mettre en gras
- Privilégier les emojis et la structure pour la lisibilité plutôt que le gras excessif

**Si "PROCHAINES DATES D'EXAMEN À PROPOSER" dans les données** :
- ⚠️ OBLIGATOIRE : Inclure les dates exactes dans la réponse avec leur format (ex: "31/03/2026", "30/06/2026")
- Ne jamais paraphraser par "prochaine session disponible" sans donner les dates précises
- Format : lister les dates avec leurs infos (date examen + date clôture si disponible)
- ⚠️ CRITIQUE : Vérifier que la date de clôture est APRÈS la DATE DU JOUR (voir en haut)
- Si une date de clôture est PASSÉE → NE PAS proposer cette session (elle est expirée !)

### 🌍 RÈGLES DÉPARTEMENT ET CHOIX DE CMA :

**NOTE : Le filtrage géographique est fait automatiquement par le système.**
- Les dates affichées ci-dessous sont DÉJÀ filtrées selon la région du candidat
- Si "RÉGION DÉTECTÉE" apparaît → les dates sont pertinentes pour cette région
- Tu dois proposer TOUTES les dates listées (elles sont déjà triées par pertinence)

**RÈGLE IMPORTANTE - NE JAMAIS INVENTER DE RESTRICTIONS RÉGIONALES :**
- ⚠️ NE JAMAIS dire "vous devez passer l'examen dans votre région d'inscription"
- ⚠️ Cette règle est FAUSSE - un candidat PEUT s'inscrire dans n'importe quel département

**Restrictions réelles (compte ExamT3P existant) :**
- Une fois le compte ExamT3P créé, le département est assigné
- Pour changer : créer un nouveau compte avec des identifiants différents (sans frais)
- Si le premier compte a déjà payé les frais CMA : attente du remboursement (long délai)

**Si "SESSIONS DE FORMATION À PROPOSER" dans les données** :
- ⚠️ OBLIGATOIRE : La session de formation DOIT correspondre à la date d'examen
- La formation doit se terminer AVANT la date d'examen (pour permettre la préparation)
- Si préférence jour/soir connue : proposer uniquement ce type de session
- Si préférence NON connue : proposer les deux options (cours du jour ET cours du soir)
- Ne JAMAIS proposer une date de formation sans la lier à une date d'examen

### 🚨 DURÉES DE FORMATION - RÈGLE ABSOLUE (NE JAMAIS INVENTER) :
**Toutes les formations = 40 heures au total**
- **Cours du jour** : 8h30-16h30 → Durée **1 SEMAINE** (5 jours consécutifs)
- **Cours du soir** : 18h00-22h00 → Durée **2 SEMAINES** (soirées du lundi au vendredi)
⚠️ NE JAMAIS INVENTER de durées différentes. Ces durées sont FIXES et DÉFINITIVES.

**⚠️ RÈGLE CRITIQUE - Lien visio/invitation formation** :
- Ne JAMAIS dire "nous venons de vous envoyer un lien d'invitation" ou "lien visio envoyé" SI:
  - On propose plusieurs dates d'examen au choix → le candidat doit d'abord confirmer
  - On propose plusieurs sessions de formation au choix → le candidat doit d'abord confirmer
  - La date de formation n'est pas encore fixée définitivement
- Le lien visio n'est envoyé QUE quand la date d'examen ET la date de formation sont confirmées de manière UNIQUE
- Si on demande au candidat de choisir une date → dire "Une fois votre choix confirmé, nous vous enverrons le lien d'invitation"

### 🚫 RÈGLE CAS A / CAS B (DOSSIER NON REÇU OU TEST NON PASSÉ) :
**Si les données indiquent "CAS A" ou "CAS B" → BLOCAGE TOTAL :**
- **NE JAMAIS** parler de dates d'examen
- **NE JAMAIS** parler de sessions de formation
- **NE JAMAIS** parler de durées de cours
- **NE JAMAIS** mentionner de départements ou CMA
- **UNIQUEMENT** répondre sur:
  * CAS A: Demander de finaliser l'inscription et d'envoyer les documents
  * CAS B: Demander de passer le test de sélection
- Utiliser le message pré-généré fourni dans les données

### 🌍 CONTEXTE GÉOGRAPHIQUE (FILTRAGE AUTOMATIQUE) :

✅ **Le système a DÉJÀ filtré les dates selon la région du candidat.**
- Les dates affichées sont PERTINENTES pour le candidat - propose-les toutes
- Les dates d'autres régions ne sont PAS incluses (sauf si le candidat les a demandées explicitement)
- Tu n'as PAS besoin de faire le tri toi-même, le backend s'en charge

### 🔄 CORRECTION DIPLOMATIQUE DES ERREURS D'INFORMATION :
**Si le candidat cite une information erronée (ex: "on m'a dit mai pour l'examen") :**
- Comparer avec les données système (prochaines dates réelles)
- Corriger DIPLOMATIQUEMENT sans accuser ni créer de confusion
- Ne PAS dire "vous vous trompez" ou "c'est faux"
- PLUTÔT dire : "Je comprends, cependant les prochaines dates disponibles sont en [MOIS]..."
- Ou : "Il y a peut-être eu un malentendu, car les sessions les plus proches sont en [MOIS]..."
- → Cela rassure le candidat tout en lui donnant l'info correcte

### 📄 RÈGLES MÉTIER CMA (TRÈS IMPORTANT) :

**Justificatif de domicile :**
- ⚠️ Le justificatif de domicile doit avoir **MOINS DE 3 MOIS** (pas 6 mois !)
- C'est une règle CMA stricte - ne jamais dire "moins de 6 mois"
- Documents acceptés : facture d'électricité, gaz, eau, téléphone fixe/mobile, avis d'imposition

**Dates de formation - NE JAMAIS INVENTER :**
- ⚠️ NE JAMAIS inventer ou supposer les dates de formation du candidat
- Utiliser UNIQUEMENT les données "Session_choisie" ou "Session actuelle" fournies dans les données CRM
- Si la session indique "janvier", dire "janvier" (pas "décembre")
- Si aucune session n'est mentionnée, ne pas en inventer une

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

Tu as accès à des exemples similaires de tes réponses passées pour t'inspirer du style et de l'approche.

## 📊 EXTRACTION DES MISES À JOUR CRM (OBLIGATOIRE)

Après ta réponse email, tu DOIS analyser la conversation pour déterminer si des champs CRM doivent être mis à jour.

**Contexte à analyser :**
- Si le candidat CONFIRME EXPLICITEMENT une date d'examen (en disant "je choisis", "Option 1", "je confirme", etc.)
- Si le candidat confirme une session de formation
- Si le candidat indique une préférence (jour/soir)
- Tout autre information qui doit être enregistrée dans le CRM

**Format de sortie :**
À la FIN de ta réponse (après la signature), ajoute un bloc structuré :

```
[CRM_UPDATES]
Date_examen_VTC: YYYY-MM-DD (si date d'examen confirmée PAR LE CANDIDAT)
Session_choisie: Nom de la session (si session confirmée)
Preference_horaire: jour|soir (si préférence confirmée)
[/CRM_UPDATES]
```

**⚠️ DISTINCTION CRITIQUE : SESSION ≠ DATE D'EXAMEN :**
- **Session de formation** (Session_choisie) = horaires de cours (jour 9h-13h / soir 18h-22h)
- **Date d'examen VTC** (Date_examen_VTC) = date de passage de l'examen à la CMA
- Ces sont DEUX CHOSES DIFFÉRENTES ! Un candidat qui dit "cours du soir" confirme sa SESSION, PAS sa date d'examen

**Règles CRITIQUES pour Date_examen_VTC :**
- ⚠️ NE JAMAIS mettre à jour Date_examen_VTC si tu PROPOSES des dates dans ta réponse (proposition ≠ confirmation)
- ⚠️ NE JAMAIS changer une date existante sauf si le candidat DEMANDE EXPLICITEMENT un changement de date d'EXAMEN
- ⚠️ NE PAS confondre confirmation de SESSION (cours jour/soir) avec confirmation de DATE D'EXAMEN
- ✅ Mettre à jour UNIQUEMENT si le candidat CONFIRME une date D'EXAMEN (dit "je choisis la date du 24/02", "Option 1 pour l'examen", etc.)
- Si le candidat demande des dates plus tôt : PROPOSE dans la réponse, mais NE MET PAS à jour le CRM

**Règles générales :**
- N'inclus QUE les champs qui doivent être mis à jour suite à une CONFIRMATION EXPLICITE du candidat
- Si aucune mise à jour n'est nécessaire, mets `[CRM_UPDATES][/CRM_UPDATES]` (bloc vide)
- Les dates doivent être au format YYYY-MM-DD
- Analyse le contexte complet : si le candidat dit "Option 1" en réponse à une question sur les dates, retrouve la date correspondante dans l'historique"""

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
        threads: Optional[List] = None,
        intent_context: Optional[Dict] = None
    ) -> str:
        """Build user prompt with context, examples, and full thread history.

        Args:
            intent_context: Contexte d'intention du TriageAgent (wants_earlier_date, etc.)
        """
        # Format similar tickets as few-shot examples
        few_shot_examples = self.rag.format_for_few_shot(similar_tickets)

        # Format scenarios
        scenarios_info = "\n".join(
            f"  - {scenario_id}: {SCENARIOS[scenario_id]['name']}"
            for scenario_id in detected_scenarios
            if scenario_id in SCENARIOS
        )

        # Format data sources
        data_summary = self._format_data_sources(crm_data, exament3p_data, evalbox_data, date_examen_vtc_data, session_data, uber_eligibility_data, threads, intent_context)

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
        uber_eligibility_data: Optional[Dict] = None,
        threads: Optional[List] = None,
        intent_context: Optional[Dict] = None
    ) -> str:
        """Format available data sources for prompt.

        Args:
            intent_context: Contexte d'intention du TriageAgent (wants_earlier_date, etc.)
        """
        from datetime import datetime
        lines = []

        # ================================================================
        # DATE DU JOUR - CRITIQUE POUR ÉVALUER LES DÉLAIS
        # ================================================================
        today = datetime.now()
        lines.append(f"📅 **DATE DU JOUR : {today.strftime('%d/%m/%Y')}**")
        lines.append("⚠️ IMPORTANT : Toute date de clôture AVANT cette date est EXPIRÉE - ne PAS proposer ces sessions !")
        lines.append("")

        # ================================================================
        # ÉLIGIBILITÉ UBER 20€ - PRIORITAIRE
        # ================================================================
        # Si le candidat Uber n'est pas éligible (CAS A ou B), c'est la priorité
        if uber_eligibility_data and uber_eligibility_data.get('is_uber_20_deal'):
            uber_case = uber_eligibility_data.get('case')
            if uber_case in ['A', 'B']:
                lines.append("=" * 60)
                lines.append("🚨🚨🚨 BLOCAGE ABSOLU - CAS {} 🚨🚨🚨".format(uber_case))
                lines.append("=" * 60)
                lines.append(f"  Cas détecté : CAS {uber_case} - {uber_eligibility_data.get('case_description', '')}")
                lines.append("")
                lines.append("  ⛔ INTERDICTIONS ABSOLUES - NE JAMAIS MENTIONNER :")
                lines.append("     - Dates d'examen")
                lines.append("     - Sessions de formation")
                lines.append("     - Durées de cours (jour/soir)")
                lines.append("     - Départements ou CMA")
                lines.append("")

                if uber_case == 'A':
                    lines.append("  📋 SEUL CONTENU AUTORISÉ :")
                    lines.append("     - Expliquer l'offre Uber 20€")
                    lines.append("     - Demander de finaliser l'inscription")
                    lines.append("     - Demander d'envoyer les documents")
                elif uber_case == 'B':
                    lines.append("  📋 SEUL CONTENU AUTORISÉ :")
                    lines.append("     - Remercier pour les documents reçus")
                    lines.append("     - Demander de passer le test de sélection")
                    lines.append(f"     - Date dossier reçu : {uber_eligibility_data.get('date_dossier_recu', 'N/A')}")

                if uber_eligibility_data.get('response_message'):
                    lines.append("")
                    lines.append("  📝 MESSAGE À UTILISER (copier tel quel) :")
                    lines.append("-" * 40)
                    lines.append(f"    {uber_eligibility_data['response_message']}")
                    lines.append("-" * 40)

                lines.append("")
                lines.append("=" * 60)
                lines.append("")
            else:
                lines.append("### 🚗 Candidat Uber 20€ :")
                lines.append("  - ✅ Éligible - Peut être inscrit à l'examen")
                lines.append("")

        if crm_data:
            lines.append("### CRM Zoho :")
            # Email du contact = identifiant e-learning
            contact_email = crm_data.get('Email') or crm_data.get('email') or crm_data.get('IDENTIFIANT_EVALBOX')
            if not contact_email:
                # Essayer d'extraire depuis Contact_Name si c'est un lookup
                contact_info = crm_data.get('Contact_Name')
                if isinstance(contact_info, dict):
                    contact_email = contact_info.get('email')
            lines.append(f"  - 📧 Email contact CRM : {contact_email or 'N/A'}")
            lines.append(f"  - 🎓 **Email e-learning (identifiant)** : {contact_email or 'N/A'}")
            if contact_email:
                lines.append(f"  - ⚠️ Si demande identifiants e-learning → utiliser cet email + 'Mot de passe oublié'")

            # Extraire le nom de la session (peut être un dict avec 'name' ou une string)
            session_data_crm = crm_data.get('Session_choisie') or crm_data.get('Session')
            if isinstance(session_data_crm, dict):
                session_name = session_data_crm.get('name', 'Non définie')
            else:
                session_name = session_data_crm or 'Non définie'
            lines.append(f"  - 📅 Session de formation choisie : {session_name}")
            lines.append(f"  - ⚠️ UTILISER CETTE SESSION - NE PAS INVENTER DE DATES")
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

                # ⚠️ ALERTE COMPTE PERSONNEL POTENTIEL
                if exament3p_data.get('potential_personal_account'):
                    personal_email = exament3p_data.get('potential_personal_email', 'inconnu')
                    lines.append("")
                    lines.append(f"  🚨 **ATTENTION - COMPTE PERSONNEL POTENTIEL DÉTECTÉ** 🚨")
                    lines.append(f"  - Le candidat a peut-être un compte ExamT3P personnel avec : {personal_email}")
                    lines.append(f"  - Il pourrait se connecter à CE compte et voir : PAS DE PAIEMENT, PAS DE VALIDATION")
                    lines.append(f"  - C'est probablement pourquoi il est confus !")
                    lines.append(f"  - ⚠️ **DANS TA RÉPONSE, TU DOIS :**")
                    lines.append(f"    1. Expliquer clairement qu'il doit utiliser UNIQUEMENT le compte CAB")
                    lines.append(f"    2. Préciser que son email personnel ({personal_email}) N'EST PAS le bon identifiant")
                    lines.append(f"    3. Rassurer que tout est fait sur le compte CAB (paiement, validation)")

        if date_examen_vtc_data:
            lines.append("\n### Date Examen VTC :")
            lines.append(f"  - Cas détecté : CAS {date_examen_vtc_data.get('case', 'N/A')} - {date_examen_vtc_data.get('case_description', '')}")
            lines.append(f"  - Statut Evalbox : {date_examen_vtc_data.get('evalbox_status', 'N/A')}")
            if date_examen_vtc_data.get('should_include_in_response'):
                lines.append(f"  - ⚠️ ACTION REQUISE : Inclure les informations date examen dans la réponse")

                # ================================================================
                # Extraire le message du candidat depuis les threads (pour filtrage)
                # ================================================================
                candidate_message = ""
                if threads:
                    for thread in threads:
                        # Chercher le thread entrant (du candidat)
                        direction = thread.get('direction', thread.get('type', ''))
                        if direction in ['in', 'incoming', 'received']:
                            candidate_message = thread.get('content', thread.get('summary', ''))
                            break
                    # Si pas de direction, prendre le premier thread
                    if not candidate_message and threads:
                        candidate_message = threads[0].get('content', threads[0].get('summary', ''))

                # Extraire le département du CRM
                candidate_dept = None
                if crm_data:
                    cma_depot = crm_data.get('CMA_de_depot')
                    if cma_depot and isinstance(cma_depot, dict):
                        candidate_dept = cma_depot.get('name', '').split('_')[0] if '_' in str(cma_depot.get('name', '')) else None

                # Inclure les prochaines dates disponibles explicitement
                next_dates = date_examen_vtc_data.get('next_dates', [])
                if next_dates:
                    # ================================================================
                    # FILTRAGE INTELLIGENT PAR RÉGION (Backend - pas d'hallucination)
                    # ================================================================
                    # Appliquer le filtrage intelligent
                    filtered_dates = filter_dates_by_region_relevance(
                        all_dates=next_dates,
                        candidate_message=candidate_message,
                        candidate_department=candidate_dept
                    )

                    # Détecter la région pour l'affichage
                    detected_region = detect_candidate_region(
                        text=candidate_message,
                        department=candidate_dept
                    )

                    if detected_region:
                        lines.append(f"  - 🌍 RÉGION DÉTECTÉE : **{detected_region}** (filtrage appliqué)")
                        lines.append(f"  - 📆 DATES PERTINENTES ({len(filtered_dates)} options après filtrage) :")
                    else:
                        lines.append(f"  - 📆 PROCHAINES DATES D'EXAMEN DISPONIBLES ({len(filtered_dates)} options) :")
                        filtered_dates = next_dates  # Pas de filtrage si région inconnue

                    lines.append("")
                    # Afficher les dates filtrées
                    for i, date_info in enumerate(filtered_dates, 1):
                        date_examen = date_info.get('Date_Examen', 'N/A')
                        date_cloture = date_info.get('Date_Cloture_Inscription', '')
                        departement = date_info.get('Departement', '')
                        # Formater la date pour affichage
                        try:
                            from datetime import datetime
                            date_obj = datetime.strptime(str(date_examen), "%Y-%m-%d")
                            date_formatted = date_obj.strftime("%d/%m/%Y")
                        except:
                            date_formatted = str(date_examen)
                        # Formater date clôture avec délai pré-calculé
                        cloture_formatted = ""
                        is_expired = False
                        if date_cloture:
                            try:
                                if 'T' in str(date_cloture):
                                    cloture_obj = datetime.fromisoformat(str(date_cloture).replace('Z', '+00:00'))
                                    cloture_obj = cloture_obj.replace(tzinfo=None)
                                else:
                                    cloture_obj = datetime.strptime(str(date_cloture), "%Y-%m-%d")
                                # Calculer le nombre de jours jusqu'à la clôture
                                today_date = datetime.now().date()
                                cloture_date = cloture_obj.date()
                                days_until_cloture = (cloture_date - today_date).days
                                # Créer un label explicite pour le délai
                                if days_until_cloture < 0:
                                    is_expired = True
                                    delay_label = "⛔ EXPIRÉE"
                                elif days_until_cloture == 0:
                                    delay_label = "🔴 AUJOURD'HUI - trop serré"
                                    is_expired = True  # Considérer comme expiré car trop serré
                                elif days_until_cloture == 1:
                                    delay_label = "🟠 DEMAIN - très serré"
                                elif days_until_cloture <= 3:
                                    delay_label = f"🟡 dans {days_until_cloture} jours - serré"
                                elif days_until_cloture <= 7:
                                    delay_label = f"🟢 dans {days_until_cloture} jours"
                                else:
                                    delay_label = f"✅ dans {days_until_cloture} jours"
                                cloture_formatted = f" (clôture: {cloture_obj.strftime('%d/%m/%Y')} → {delay_label})"
                            except:
                                pass
                        # Ajouter la région pour faciliter le choix géographique
                        region = DEPT_TO_REGION.get(str(departement), '')
                        region_info = f" - {region}" if region else ""
                        dept_info = f" [Dept {departement}{region_info}]" if departement else ""
                        if is_expired:
                            lines.append(f"      {i}. ⛔ {date_formatted}{dept_info}{cloture_formatted} - NE PAS PROPOSER")
                        else:
                            lines.append(f"      {i}. {date_formatted}{dept_info}{cloture_formatted}")

                # Dates alternatives dans d'autres départements
                # SEULEMENT si le candidat demande explicitement des dates plus tôt ou autres options
                alt_dates = date_examen_vtc_data.get('alternative_department_dates', [])
                # Utiliser l'intent_context du TriageAgent si disponible, sinon fallback sur keywords
                candidate_wants_earlier = (
                    (intent_context or {}).get('wants_earlier_date', False) or
                    _candidate_requests_earlier_dates(candidate_message)  # Fallback rétrocompatibilité
                )
                if alt_dates and date_examen_vtc_data.get('can_choose_other_department') and candidate_wants_earlier:
                    lines.append(f"\n  - 🌍 DATES PLUS TÔT DANS D'AUTRES DÉPARTEMENTS (candidat a demandé) :")
                    lines.append(f"    ⚠️ IMPORTANT : Ces dates sont disponibles car le candidat n'a PAS encore de compte ExamT3P.")
                    lines.append(f"    Le candidat peut s'inscrire dans N'IMPORTE QUEL département.")
                    for j, alt_date in enumerate(alt_dates[:3], 1):
                        alt_date_examen = alt_date.get('Date_Examen', 'N/A')
                        alt_dept = alt_date.get('Departement', '')
                        alt_cloture = alt_date.get('Date_Cloture_Inscription', '')
                        try:
                            alt_date_obj = datetime.strptime(str(alt_date_examen), "%Y-%m-%d")
                            alt_date_formatted = alt_date_obj.strftime("%d/%m/%Y")
                        except:
                            alt_date_formatted = str(alt_date_examen)
                        alt_cloture_formatted = ""
                        alt_is_expired = False
                        if alt_cloture:
                            try:
                                if 'T' in str(alt_cloture):
                                    alt_cloture_obj = datetime.fromisoformat(str(alt_cloture).replace('Z', '+00:00'))
                                    alt_cloture_obj = alt_cloture_obj.replace(tzinfo=None)
                                else:
                                    alt_cloture_obj = datetime.strptime(str(alt_cloture), "%Y-%m-%d")
                                # Calculer le nombre de jours jusqu'à la clôture
                                today_date = datetime.now().date()
                                alt_cloture_date = alt_cloture_obj.date()
                                alt_days_until = (alt_cloture_date - today_date).days
                                # Créer un label explicite pour le délai
                                if alt_days_until < 0:
                                    alt_is_expired = True
                                    alt_delay_label = "⛔ EXPIRÉE"
                                elif alt_days_until == 0:
                                    alt_delay_label = "🔴 AUJOURD'HUI - trop serré"
                                    alt_is_expired = True
                                elif alt_days_until == 1:
                                    alt_delay_label = "🟠 DEMAIN - très serré"
                                elif alt_days_until <= 3:
                                    alt_delay_label = f"🟡 dans {alt_days_until} jours - serré"
                                elif alt_days_until <= 7:
                                    alt_delay_label = f"🟢 dans {alt_days_until} jours"
                                else:
                                    alt_delay_label = f"✅ dans {alt_days_until} jours"
                                alt_cloture_formatted = f" (clôture: {alt_cloture_obj.strftime('%d/%m/%Y')} → {alt_delay_label})"
                            except:
                                pass
                        if alt_is_expired:
                            lines.append(f"      {j}. ⛔ {alt_date_formatted} - Département {alt_dept}{alt_cloture_formatted} - NE PAS PROPOSER")
                        else:
                            lines.append(f"      {j}. {alt_date_formatted} - Département {alt_dept}{alt_cloture_formatted}")

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

        # ================================================================
        # ALERTES TEMPORAIRES
        # ================================================================
        # Alertes temporaires (bugs CMA, situations exceptionnelles)
        # Déclenchées par statut Evalbox OU par mots-clés dans le message
        from src.utils.alerts_helper import get_alerts_for_response
        alerts_text = get_alerts_for_response(
            deal_data=crm_data,
            examt3p_data=exament3p_data,
            threads=threads
        )
        if alerts_text:
            lines.append(alerts_text)

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
        max_tokens: int = 2000,
        intent_context: Optional[Dict] = None
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
            intent_context: Contexte d'intention du TriageAgent (wants_earlier_date, etc.)

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
            crm_data=crm_data,
            examt3p_data=exament3p_data
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
            threads=threads,
            intent_context=intent_context
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

            raw_response = response.content[0].text
            logger.info(f"Claude generated {len(raw_response)} characters")

            # Parse CRM updates from response
            response_text, extracted_crm_updates = _parse_crm_updates(raw_response)

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
        # If AI extracted CRM updates, use those; otherwise use scenario-based fields
        has_ai_updates = bool(extracted_crm_updates)
        if has_ai_updates:
            needs_crm_update = True  # Override if AI found updates

        return {
            'response_text': response_text,
            'detected_scenarios': detected_scenarios,
            'similar_tickets': similar_tickets,
            'validation': validation_results,
            'requires_crm_update': needs_crm_update,
            'crm_update_fields': crm_update_fields,
            'crm_updates': extracted_crm_updates,  # Actual values from AI
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
        training_exam_consistency_data: Optional[Dict] = None,
        triage_result: Optional[Dict] = None,
        max_retries: int = 2
    ) -> Dict:
        """
        Generate response with validation loop.

        If response is not compliant, retry with feedback.

        Args:
            credentials_only_response: Si True, génère UNIQUEMENT une réponse
                demandant les bons identifiants. Ignore dates/sessions.
            threads: Historique complet des échanges pour contexte.
            training_exam_consistency_data: Données de cohérence formation/examen.
                Si 'has_consistency_issue' est True, utilise le message pré-généré.
            triage_result: Résultat du triage IA avec detected_intent et intent_context.
                Permet d'appliquer des procédures strictes (ex: force majeure pour report).
        """
        # ================================================================
        # CAS SPÉCIAL #0: Prospect ou CAS A/B Uber (AVANT identifiants!)
        # ================================================================
        # PROSPECT: Candidat intéressé mais paiement non effectué
        # CAS A: Candidat a payé 20€ mais n'a pas finalisé son inscription
        # CAS B: Candidat a envoyé documents mais n'a pas passé le test
        # → Utiliser le message pré-généré (PAS demande identifiants ExamT3P!)
        if uber_eligibility_data:
            uber_case = uber_eligibility_data.get('case')
            is_uber_deal = uber_eligibility_data.get('is_uber_20_deal')
            is_prospect = uber_eligibility_data.get('is_uber_prospect')

            if uber_case == 'PROSPECT' and is_prospect:
                logger.info("🚨 MODE PROSPECT: Candidat intéressé, paiement non effectué")
                return self._generate_uber_prospect_response(
                    uber_eligibility_data=uber_eligibility_data,
                    customer_message=customer_message,
                    threads=threads
                )
            elif uber_case in ['A', 'B', 'D', 'E'] and is_uber_deal:
                # CAS A: Documents non envoyés
                # CAS B: Test de sélection non passé
                # CAS D: Compte Uber non vérifié (email ≠ Uber Driver)
                # CAS E: Non éligible selon Uber (raisons inconnues)
                logger.info(f"🚨 MODE CAS {uber_case}: Utilisation message pré-généré Uber")
                return self._generate_uber_case_response(
                    uber_eligibility_data=uber_eligibility_data,
                    customer_message=customer_message,
                    threads=threads
                )

        # ================================================================
        # CAS SPÉCIAL #1: Identifiants invalides = SEUL sujet de la réponse
        # ================================================================
        if credentials_only_response:
            logger.info("🚨 MODE CREDENTIALS_ONLY: Réponse uniquement sur identifiants")
            return self._generate_credentials_only_response(
                exament3p_data=exament3p_data,
                threads=threads,
                customer_message=customer_message
            )

        # ================================================================
        # CAS SPÉCIAL: Formation manquée + Examen imminent
        # ================================================================
        # Candidat a manqué sa formation et son examen est dans les 14 prochains jours
        # → Proposer 2 options: maintenir examen (e-learning) ou reporter (force majeure)
        if training_exam_consistency_data and training_exam_consistency_data.get('has_consistency_issue'):
            logger.info("🚨 MODE TRAINING_EXAM_CONSISTENCY: Formation manquée + Examen imminent")
            return self._generate_training_exam_options_response(
                training_exam_consistency_data=training_exam_consistency_data,
                exament3p_data=exament3p_data,
                crm_data=crm_data
            )

        # ================================================================
        # Extraire intent_context pour tous les cas (pas seulement REPORT_DATE)
        # ================================================================
        intent_context = triage_result.get('intent_context', {}) if triage_result else {}

        # ================================================================
        # CAS SPÉCIAL: REPORT_DATE (Demande de changement de date)
        # ================================================================
        # Détecté par IA dans TriageAgent - applique la procédure stricte
        # Si dossier CMA clôturé → Force majeure OBLIGATOIRE
        if triage_result and triage_result.get('detected_intent') == 'REPORT_DATE':
            logger.info("🚨 MODE REPORT_DATE: Demande de changement de date détectée par IA")

            # Vérifier si le dossier CMA est clôturé (Evalbox avancé)
            evalbox_status = None
            if crm_data:
                evalbox_status = crm_data.get('Evalbox', '')
            elif exament3p_data:
                evalbox_status = exament3p_data.get('statut_dossier', '')

            # Statuts indiquant un dossier CMA clôturé
            cma_closed_statuses = ['VALIDE CMA', 'Convoc CMA reçue', 'En attente de convocation', 'Valide']

            if evalbox_status in cma_closed_statuses:
                logger.info(f"  📋 Dossier CMA clôturé (Evalbox: {evalbox_status}) → Procédure force majeure")
                return self._generate_report_date_response(
                    crm_data=crm_data,
                    exament3p_data=exament3p_data,
                    date_examen_vtc_data=date_examen_vtc_data,
                    intent_context=intent_context,
                    customer_message=customer_message
                )
            else:
                logger.info(f"  📋 Dossier CMA non clôturé (Evalbox: {evalbox_status}) → Report plus simple")
                # On laisse l'IA générer la réponse, mais on injecte les infos de l'intent
                # pour qu'elle sache que c'est un report

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
                threads=threads,  # Pass thread history for context
                intent_context=intent_context  # Pass intent context from triage (wants_earlier_date, etc.)
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
            response = self.anthropic_client.messages.create(
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

    def _generate_uber_prospect_response(
        self,
        uber_eligibility_data: Dict,
        customer_message: str = "",
        threads: Optional[List] = None
    ) -> Dict:
        """
        Génère une réponse pour les PROSPECTS Uber (paiement non effectué).

        Le candidat a créé son compte mais n'a pas encore payé les 20€.
        → Répondre à sa question
        → Expliquer l'offre et ses avantages
        → L'encourager à finaliser son paiement
        """
        logger.info("Generating Uber PROSPECT response")

        # ================================================================
        # Vérifier les alertes temporaires (ex: double convocation CMA)
        # ================================================================
        from src.utils.alerts_helper import get_alerts_for_response
        alerts_text = get_alerts_for_response(
            customer_message=customer_message,
            threads=threads
        )
        if alerts_text:
            logger.info("📢 Alertes détectées en mode PROSPECT - injection dans le prompt")

        system_prompt = """Tu es un assistant de Cab Formations, centre de formation VTC.
Tu dois générer une réponse email professionnelle, rassurante et commerciale.

CONTEXTE:
- Le candidat a créé son compte mais n'a PAS encore payé les 20€
- Il pose probablement une question générale sur l'offre ou la formation
- Tu dois RÉPONDRE À SA QUESTION et l'ENCOURAGER À FINALISER SON PAIEMENT

L'OFFRE UBER 20€ COMPREND:
1. **Paiement des frais d'examen de 241€** à la CMA - PAYÉ PAR CAB FORMATIONS (économie de 241€!)
2. **Formation en visio-conférence de 40 heures** avec un formateur professionnel
   - À HORAIRES FIXES (pas à la demande!)
   - 2 options pour s'adapter aux contraintes:
     * Cours du JOUR: 8h30-16h30, durée 1 SEMAINE (lundi-vendredi)
     * Cours du SOIR: 18h00-22h00, durée 2 SEMAINES (soirs du lundi-vendredi)
3. **Accès illimité au e-learning** pour réviser à son rythme
4. **Accompagnement personnalisé** jusqu'à l'obtention de la carte VTC

RÈGLES DE RÉDACTION:
- TOUJOURS répondre à la question posée par le candidat en PREMIER
- Ensuite mettre en avant les avantages de l'offre (notamment les 241€ de frais d'examen payés!)
- Être rassurant et enthousiaste
- Créer un sentiment d'urgence: "Les places sont limitées", "Les dates se remplissent vite"
- Encourager à finaliser le paiement: "Finalisez votre inscription dès maintenant"
- Formater avec du markdown (gras, listes, emojis)
- Ne JAMAIS mentionner de dates d'examen spécifiques
- Ne JAMAIS demander d'identifiants ExamT3P
- Terminer par "Cordialement, L'équipe Cab Formations"

DURÉES DE FORMATION - ABSOLUMENT CORRECT:
- Cours du jour: 1 SEMAINE (pas 2!)
- Cours du soir: 2 SEMAINES (pas 4!)"""

        # Ajouter les alertes temporaires au prompt si présentes
        if alerts_text:
            system_prompt += f"""

{alerts_text}

IMPORTANT: Si l'alerte ci-dessus correspond à la situation du candidat (par exemple
s'il mentionne avoir reçu deux convocations), TRAITE D'ABORD L'ALERTE avant de
parler de l'offre commerciale. L'alerte est PRIORITAIRE."""

        user_prompt = f"""MESSAGE DU CANDIDAT:
{customer_message}

Génère une réponse email complète qui:
1. Répond à sa question spécifique (sur les horaires, l'offre, etc.)
2. Met en avant les avantages de l'offre (241€ économisés!)
3. L'encourage à finaliser son paiement de 20€

Commence par "Bonjour," (pas de prénom)."""

        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            response_message = response.content[0].text.strip()
            logger.info(f"  Claude a généré une réponse PROSPECT ({len(response_message)} caractères)")

        except Exception as e:
            logger.error(f"  Erreur Claude API: {e}")
            # Fallback sur message par défaut
            pre_generated = uber_eligibility_data.get('response_message', '')
            response_message = f"""Bonjour,

Merci pour votre message et votre intérêt pour notre formation VTC !

{pre_generated if pre_generated else '''Pour répondre à votre question : nos formations se déroulent à **horaires fixes** selon un planning établi. Nous proposons **deux types de sessions** pour nous adapter au mieux à vos contraintes :

📅 **Cours du jour** : 8h30 - 16h30
   → Durée : **1 semaine** (du lundi au vendredi)

🌙 **Cours du soir** : 18h00 - 22h00
   → Durée : **2 semaines** (soirées du lundi au vendredi)

**Ce que comprend l'offre à 20€ :**

✅ **Paiement des frais d'examen de 241€** à la CMA - entièrement pris en charge par CAB Formations
✅ **Formation en visio-conférence de 40 heures** avec un formateur professionnel
✅ **Accès illimité au e-learning** pour réviser à votre rythme
✅ **Accompagnement personnalisé** jusqu'à l'obtention de votre carte VTC

**Pour profiter de cette offre exceptionnelle, il vous suffit de finaliser votre paiement de 20€** sur notre plateforme.

N'attendez plus pour démarrer votre parcours vers la carte VTC ! Les places sont limitées et les dates d'examen se remplissent vite.'''}

Cordialement,
L'équipe Cab Formations"""

        logger.info(f"  Message généré: {len(response_message)} caractères")

        return {
            'response_text': response_message,
            'detected_scenarios': ['SC-UBER_PROSPECT'],
            'similar_tickets': [],
            'validation': {
                'SC-UBER_PROSPECT': {
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
                'output_tokens': len(response_message),
                'model': self.model,
                'uber_prospect_mode': True
            }
        }

    def _generate_uber_case_response(
        self,
        uber_eligibility_data: Dict,
        customer_message: str = "",
        threads: Optional[List] = None
    ) -> Dict:
        """
        Génère une réponse CONTEXTUELLE pour les CAS Uber (A, B, D, E).

        CAS A: Candidat a payé 20€ mais n'a pas finalisé son inscription
               → Récapituler l'offre et pousser à envoyer le dossier

        CAS B: Candidat a envoyé documents mais n'a pas passé le test
               → Demander de passer le test de sélection

        CAS D: Compte Uber non vérifié (email ≠ Uber Driver)
               → Vérifier email, contacter Uber via l'app si nécessaire

        CAS E: Non éligible selon Uber (raisons inconnues de CAB)
               → Contacter Uber via l'app pour comprendre

        UTILISE CLAUDE pour générer une réponse contextuelle qui répond
        à la question du candidat tout en poussant à l'action.
        """
        uber_case = uber_eligibility_data.get('case', 'A')
        logger.info(f"Generating Uber CAS {uber_case} contextual response")

        # ================================================================
        # Vérifier les alertes temporaires (ex: double convocation CMA)
        # ================================================================
        from src.utils.alerts_helper import get_alerts_for_response
        alerts_text = get_alerts_for_response(
            customer_message=customer_message,
            threads=threads
        )
        if alerts_text:
            logger.info(f"📢 Alertes détectées en mode CAS {uber_case} - injection dans le prompt")

        # ================================================================
        # UTILISER CLAUDE POUR GÉNÉRER UNE RÉPONSE CONTEXTUELLE
        # ================================================================
        if uber_case == 'A':
            system_prompt = """Tu es un assistant de Cab Formations, centre de formation VTC.
Tu dois générer une réponse email professionnelle, rassurante et qui pousse à l'action.

CONTEXTE:
- Le candidat a payé 20€ pour l'offre Uber VTC mais n'a PAS encore envoyé son dossier
- Il pose probablement une question générale sur l'offre ou la formation
- Tu dois RÉPONDRE À SA QUESTION tout en le poussant à finaliser son inscription

L'OFFRE UBER 20€ COMPREND:
1. **Paiement des frais d'examen de 241€** à la CMA (Chambre des Métiers) - PAYÉ PAR CAB FORMATIONS
2. **Formation en visio-conférence de 40 heures** avec un formateur professionnel
   - À HORAIRES FIXES (pas à la demande!)
   - 2 options pour s'adapter aux contraintes:
     * Cours du JOUR: 8h30-16h30, durée 1 SEMAINE (lundi-vendredi)
     * Cours du SOIR: 18h00-22h00, durée 2 SEMAINES (soirs du lundi-vendredi)
3. **Accès illimité au e-learning** pour réviser à son rythme
4. **Accompagnement personnalisé** jusqu'à l'obtention de la carte VTC

POUR BÉNÉFICIER DE L'OFFRE, IL DOIT:
1. Finaliser son inscription sur la plateforme CAB Formations
2. Nous envoyer ses documents (pièce d'identité, justificatif de domicile, etc.)
3. Passer un test de sélection simple (envoyé par email après réception des documents)

RÈGLES DE RÉDACTION:
- TOUJOURS répondre à la question posée par le candidat en PREMIER
- Ensuite récapituler les avantages de l'offre
- Être rassurant et enthousiaste
- Pousser à l'action: "Envoyez-nous vos documents dès que possible pour..."
- Formater avec du markdown (gras, listes)
- Ne JAMAIS mentionner de dates d'examen ou de formation spécifiques (on n'a pas son dossier!)
- Ne JAMAIS demander d'identifiants ExamT3P (le compte n'existe pas encore!)
- Terminer par "Cordialement, L'équipe Cab Formations"

DURÉES DE FORMATION - ABSOLUMENT CORRECT:
- Cours du jour: 1 SEMAINE (pas 2!)
- Cours du soir: 2 SEMAINES (pas 4!)"""
        elif uber_case == 'B':
            date_dossier = uber_eligibility_data.get('date_dossier_recu', '')
            system_prompt = f"""Tu es un assistant de Cab Formations, centre de formation VTC.
Tu dois générer une réponse email professionnelle et rassurante.

CONTEXTE:
- Le candidat a payé 20€ ET envoyé son dossier (reçu le {date_dossier if date_dossier else 'récemment'})
- Il n'a PAS encore passé le test de sélection
- Tu dois RÉPONDRE À SA QUESTION tout en lui rappelant de passer le test

LE TEST DE SÉLECTION:
- Test simple et rapide
- Ne nécessite AUCUNE préparation (pas besoin de réviser)
- Le lien a été envoyé par email le jour de la réception du dossier
- OBLIGATOIRE pour déclencher l'inscription à l'examen

SI QUESTION SUR LA FORMATION:
- À HORAIRES FIXES (pas à la demande!)
- 2 options:
  * Cours du JOUR: 8h30-16h30, durée 1 SEMAINE
  * Cours du SOIR: 18h00-22h00, durée 2 SEMAINES

RÈGLES:
- TOUJOURS répondre à la question posée en PREMIER
- Rappeler de passer le test de sélection
- Si pas reçu l'email du test → proposer de le renvoyer
- Ne JAMAIS mentionner de dates d'examen spécifiques
- Ne JAMAIS demander d'identifiants ExamT3P
- Terminer par "Cordialement, L'équipe Cab Formations"

DURÉES DE FORMATION - ABSOLUMENT CORRECT:
- Cours du jour: 1 SEMAINE (pas 2!)
- Cours du soir: 2 SEMAINES (pas 4!)"""
        elif uber_case == 'D':
            # CAS D: Compte Uber non vérifié
            system_prompt = """Tu es un assistant de Cab Formations, centre de formation VTC.
Tu dois générer une réponse email professionnelle et empathique.

CONTEXTE:
- Le candidat a payé 20€ pour l'offre Uber VTC
- L'email utilisé pour l'inscription n'est PAS lié à un compte Uber chauffeur actif
- Tu dois RÉPONDRE À SA QUESTION tout en expliquant le problème du compte Uber

SITUATION COMPTE UBER:
- Pour bénéficier de l'offre partenariat Uber, l'email d'inscription DOIT être le même que celui du compte Uber Driver (chauffeur)
- Si le candidat a utilisé un email différent → nous donner le bon email
- Si c'est le même email mais compte non reconnu → contacter Uber

COMMENT CONTACTER UBER:
- Se connecter à l'application Uber Driver
- Aller dans Compte → Aide
- Utiliser le chat intégré pour échanger avec le support

RÈGLES:
- TOUJOURS répondre à la question posée en PREMIER
- Ensuite expliquer le problème du compte Uber
- Être empathique: on comprend que c'est frustrant
- Expliquer que CAB n'a AUCUNE visibilité sur les critères Uber
- Ne JAMAIS mentionner de dates d'examen (tant que le compte Uber n'est pas vérifié)
- Ne JAMAIS demander d'identifiants ExamT3P
- Terminer par "Cordialement, L'équipe Cab Formations"

IMPORTANT: Ne pas inventer de numéro de téléphone ou email Uber. Le SEUL moyen de contacter Uber est via l'application."""
        else:  # CAS E
            # CAS E: Non éligible selon Uber
            system_prompt = """Tu es un assistant de Cab Formations, centre de formation VTC.
Tu dois générer une réponse email professionnelle et empathique.

CONTEXTE:
- Le candidat a payé 20€ pour l'offre Uber VTC
- Uber considère le candidat comme NON ÉLIGIBLE à l'offre partenariat
- CAB Formations n'a AUCUNE visibilité sur les raisons (critères internes Uber)
- Tu dois RÉPONDRE À SA QUESTION tout en expliquant la situation

CE QUE CELA SIGNIFIE:
- Uber applique ses propres critères d'éligibilité
- Seul Uber peut expliquer pourquoi le candidat n'est pas éligible
- CAB ne peut pas inscrire le candidat tant qu'Uber ne le considère pas éligible

COMMENT CONTACTER UBER:
- Se connecter à l'application Uber Driver
- Aller dans Compte → Aide
- Utiliser le chat intégré pour échanger avec le support
- Expliquer qu'il souhaite bénéficier de l'offre formation VTC en partenariat avec CAB Formations

ALTERNATIVE:
- Si Uber confirme la non-éligibilité, le candidat peut s'inscrire à la formation VTC classique
- Ne pas donner de prix (nous contacter pour plus d'infos)

RÈGLES:
- TOUJOURS répondre à la question posée en PREMIER
- Être empathique: on comprend la frustration
- Expliquer clairement que CAB n'a pas de visibilité sur les raisons Uber
- Ne JAMAIS mentionner de dates d'examen
- Ne JAMAIS demander d'identifiants ExamT3P
- Terminer par "Cordialement, L'équipe Cab Formations"

IMPORTANT: Ne pas inventer de numéro de téléphone ou email Uber. Le SEUL moyen de contacter Uber est via l'application."""

        # Ajouter les alertes temporaires au prompt si présentes
        if alerts_text:
            system_prompt += f"""

{alerts_text}

IMPORTANT: Si l'alerte ci-dessus correspond à la situation du candidat (par exemple
s'il mentionne avoir reçu deux convocations), TRAITE D'ABORD L'ALERTE avant de
parler de l'offre ou de demander les documents. L'alerte est PRIORITAIRE."""

        # Construire le user_prompt en fonction du cas
        case_instructions = {
            'A': "Récapitule les avantages de l'offre et pousse à envoyer le dossier",
            'B': "Rappelle de passer le test de sélection",
            'D': "Explique le problème du compte Uber et comment le résoudre",
            'E': "Explique la non-éligibilité Uber et les alternatives"
        }

        user_prompt = f"""MESSAGE DU CANDIDAT:
{customer_message}

Génère une réponse email complète qui:
1. Répond à sa question spécifique
2. {case_instructions.get(uber_case, "Explique la situation")}

Commence par "Bonjour," (pas de prénom).

IMPORTANT - À la fin de ta réponse, ajoute sur une nouvelle ligne:
[PREFERENCE:jour] si le candidat mentionne vouloir le cours de JOUR (8h-16h30, matin, journée)
[PREFERENCE:soir] si le candidat mentionne vouloir le cours du SOIR (18h-22h)
[PREFERENCE:aucune] si aucune préférence n'est mentionnée
Cette ligne sera retirée du message final, c'est juste pour l'extraction."""

        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=1500,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            response_message = response.content[0].text.strip()
            logger.info(f"  Claude a généré une réponse contextuelle CAS {uber_case} ({len(response_message)} caractères)")

        except Exception as e:
            logger.error(f"  Erreur Claude API: {e}")
            # Fallback sur message pré-généré de uber_eligibility_helper
            pre_generated_message = uber_eligibility_data.get('response_message')
            if pre_generated_message:
                response_message = f"Bonjour,\n\n{pre_generated_message}\n\nCordialement,\nL'équipe Cab Formations"
            elif uber_case == 'A':
                response_message = """Bonjour,

Merci pour votre message et votre intérêt pour notre formation VTC !

**Récapitulatif de votre offre Uber à 20€ :**

✅ **Paiement des frais d'examen de 241€** à la CMA - entièrement pris en charge par CAB Formations
✅ **Formation en visio-conférence de 40 heures** avec un formateur professionnel
✅ **Accès illimité au e-learning** pour réviser à votre rythme
✅ **Accompagnement personnalisé** jusqu'à l'obtention de votre carte VTC

**Pour profiter de ces avantages, il vous reste à :**

1. **Finaliser votre inscription** sur notre plateforme
2. **Nous envoyer vos documents** (pièce d'identité, justificatif de domicile, etc.)
3. **Passer un test de sélection simple** - vous recevrez le lien par email

N'hésitez pas à nous envoyer vos documents dès que possible pour démarrer votre parcours vers la carte VTC !

Cordialement,
L'équipe Cab Formations"""
            elif uber_case == 'B':
                response_message = """Bonjour,

Merci pour votre message !

**Il vous reste une dernière étape pour finaliser votre inscription :**

Vous devez passer le **test de sélection**. Un email contenant le lien vers ce test vous a été envoyé le jour de la réception de votre dossier.

Ce test est **simple et rapide**, il ne nécessite aucune préparation. Il nous permet de déclencher votre inscription à l'examen.

Si vous n'avez pas reçu l'email, n'hésitez pas à nous le signaler et nous vous renverrons le lien immédiatement.

Cordialement,
L'équipe Cab Formations"""
            elif uber_case == 'D':
                response_message = """Bonjour,

Nous avons vérifié votre inscription et constaté que l'adresse email utilisée n'est pas liée à un compte Uber chauffeur actif.

**Voici les étapes à suivre :**

1️⃣ **Vérifiez que vous utilisez la bonne adresse email**
   - L'email utilisé pour votre inscription CAB Formations doit être **exactement le même** que celui de votre compte **Uber Driver** (chauffeur), et non votre compte Uber client.
   - Si vous avez utilisé une adresse différente, merci de nous communiquer l'adresse email liée à votre compte Uber Driver.

2️⃣ **Si les adresses sont identiques**
   - Contactez directement le support Uber pour comprendre la situation.
   - **Comment contacter Uber :** Connectez-vous à l'application Uber Driver → Compte → Aide → Chat

⚠️ Nous n'avons aucune visibilité sur les critères internes d'Uber. Seul leur support peut vous expliquer pourquoi votre compte n'est pas reconnu.

Cordialement,
L'équipe Cab Formations"""
            else:  # CAS E
                response_message = """Bonjour,

Nous avons vérifié votre dossier auprès d'Uber et malheureusement, votre profil n'est **pas éligible** à l'offre VTC en partenariat avec Uber.

Uber applique ses propres critères d'éligibilité. Malheureusement, **nous n'avons aucune visibilité** sur les raisons de cette décision.

**Ce que vous devez faire :**

📱 Contactez le support Uber pour comprendre pourquoi :
   - Connectez-vous à l'application Uber Driver
   - Allez dans Compte → Aide
   - Utilisez le chat intégré pour échanger avec le support

Expliquez-leur que vous souhaitez bénéficier de l'offre de formation VTC en partenariat avec CAB Formations.

**Alternative :** Si Uber confirme que vous n'êtes pas éligible, vous pouvez toujours vous inscrire à notre formation VTC classique. N'hésitez pas à nous contacter pour plus d'informations.

Cordialement,
L'équipe Cab Formations"""

        logger.info(f"  Message généré: {len(response_message)} caractères")

        # ================================================================
        # EXTRACTION DE LA PRÉFÉRENCE HORAIRE
        # ================================================================
        import re
        crm_updates = {}
        preference_match = re.search(r'\[PREFERENCE:(jour|soir|aucune)\]', response_message, re.IGNORECASE)
        if preference_match:
            preference = preference_match.group(1).lower()
            # Retirer le tag du message
            response_message = re.sub(r'\s*\[PREFERENCE:(jour|soir|aucune)\]\s*', '', response_message, flags=re.IGNORECASE).strip()
            if preference != 'aucune':
                crm_updates['Preference_horaire'] = preference
                logger.info(f"  📝 Préférence horaire détectée: {preference}")

        has_crm_updates = bool(crm_updates)

        return {
            'response_text': response_message,
            'detected_scenarios': [f'SC-UBER_CAS_{uber_case}'],
            'similar_tickets': [],
            'validation': {
                f'SC-UBER_CAS_{uber_case}': {
                    'compliant': True,
                    'missing_blocks': [],
                    'forbidden_terms_found': []
                }
            },
            'requires_crm_update': has_crm_updates,
            'crm_updates': crm_updates,
            'crm_update_fields': list(crm_updates.keys()),
            'should_stop_workflow': False,
            'metadata': {
                'input_tokens': 0,
                'output_tokens': len(response_message),
                'model': self.model,
                'uber_case_mode': True,
                'uber_case': uber_case
            }
        }

    def _generate_training_exam_options_response(
        self,
        training_exam_consistency_data: Dict,
        exament3p_data: Optional[Dict] = None,
        crm_data: Optional[Dict] = None
    ) -> Dict:
        """
        Génère une réponse quand le candidat a manqué sa formation et son examen est imminent.

        Le candidat doit choisir entre:
        - Option A: Maintenir l'examen (considère que le e-learning lui a suffi)
        - Option B: Reporter l'examen (nécessite un justificatif de force majeure)

        Le message est pré-généré par training_exam_consistency_helper.py
        """
        logger.info("Generating training/exam options response")

        # Utiliser le message pré-généré par le helper
        response_message = training_exam_consistency_data.get('response_message', '')

        if not response_message:
            # Fallback: générer un message basique
            exam_date = training_exam_consistency_data.get('exam_date_formatted', 'N/A')
            next_exam_date = training_exam_consistency_data.get('next_exam_date_formatted', 'prochaine date disponible')

            response_message = f"""Bonjour,

Nous avons bien pris connaissance de votre message concernant la formation.

**⚠️ Information importante : Vous êtes inscrit(e) à l'examen VTC du {exam_date}.**

La formation en visioconférence et le e-learning sont des outils de préparation, mais votre inscription à l'examen est déjà validée auprès de la CMA (Chambre des Métiers et de l'Artisanat).

Vous avez deux possibilités :

---

## Option A : Maintenir votre examen au {exam_date}

Si vous estimez que le **e-learning** (formation à distance) vous a permis d'acquérir les connaissances nécessaires, vous pouvez passer l'examen à la date prévue.

📚 **Rappel** : Vous avez accès aux cours en ligne sur : **https://elearning.cab-formations.fr**

La formation en visioconférence est un complément, mais n'est pas obligatoire pour se présenter à l'examen.

---

## Option B : Reporter votre examen

Si vous souhaitez reporter votre examen, **un justificatif de force majeure couvrant la date du {exam_date} est obligatoire**.

⚠️ **Attention** : Le certificat médical doit couvrir **le jour de l'examen** ({exam_date}), pas seulement la période de la formation.

En cas de report accepté par la CMA, vous serez repositionné(e) sur le {next_exam_date}.

**Pour demander un report :**
1. Envoyez-nous un **certificat médical** (ou autre justificatif de force majeure) **couvrant la date du {exam_date}**
2. Nous transmettrons votre demande à la CMA
3. La CMA vous repositionnera sur la prochaine date d'examen disponible

⚠️ **Important** : Le simple fait de ne pas avoir suivi la formation n'est **pas** un motif valable de report auprès de la CMA. Seule la force majeure (maladie le jour de l'examen, accident, décès d'un proche, etc.) permet de reporter.

---

**Merci de nous indiquer votre choix** afin que nous puissions vous accompagner au mieux.

Cordialement,
L'équipe Cab Formations"""

        logger.info(f"  Message généré: {len(response_message)} caractères")
        logger.info(f"  Examen prévu le: {training_exam_consistency_data.get('exam_date_formatted')}")
        logger.info(f"  Prochaine date disponible: {training_exam_consistency_data.get('next_exam_date_formatted')}")
        if training_exam_consistency_data.get('force_majeure_detected'):
            logger.info(f"  Force majeure détectée: {training_exam_consistency_data.get('force_majeure_type')}")

        return {
            'response_text': response_message,
            'detected_scenarios': ['SC-TRAINING_EXAM_CONSISTENCY'],
            'similar_tickets': [],
            'validation': {
                'SC-TRAINING_EXAM_CONSISTENCY': {
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
                'output_tokens': len(response_message),
                'model': self.model,
                'training_exam_consistency_mode': True,
                'issue_type': training_exam_consistency_data.get('issue_type'),
                'exam_date': training_exam_consistency_data.get('exam_date'),
                'next_exam_date': training_exam_consistency_data.get('next_exam_date'),
                'force_majeure_detected': training_exam_consistency_data.get('force_majeure_detected'),
                'force_majeure_type': training_exam_consistency_data.get('force_majeure_type')
            }
        }

    def _generate_report_date_response(
        self,
        crm_data: Optional[Dict] = None,
        exament3p_data: Optional[Dict] = None,
        date_examen_vtc_data: Optional[Dict] = None,
        intent_context: Optional[Dict] = None,
        customer_message: str = ""
    ) -> Dict:
        """
        Génère une réponse pour les demandes de report de date d'examen (dossier CMA clôturé).

        PROCÉDURE STRICTE:
        - Force majeure OBLIGATOIRE (pas optionnelle)
        - Sans justificatif = frais de réinscription 241€
        - Certificat médical doit couvrir le jour de l'EXAMEN
        - Demander le justificatif par EMAIL (pas téléphone)

        Args:
            crm_data: Données CRM du candidat
            exament3p_data: Données ExamT3P
            date_examen_vtc_data: Données sur la date d'examen
            intent_context: Contexte de l'intention (force majeure détectée, urgence, etc.)
            customer_message: Message original du candidat
        """
        logger.info("Generating REPORT_DATE response (CMA closed - force majeure required)")

        intent_context = intent_context or {}
        from datetime import datetime

        # Extraire la date d'examen (plusieurs sources possibles)
        exam_date_formatted = "N/A"
        exam_date_raw = None

        # Source 1: date_examen_vtc_data.date_examen_info (dict complet avec name)
        # IMPORTANT: date_examen_vtc contient l'ID, date_examen_info contient le dict {'name': '51_2026-01-27', 'id': '...'}
        if date_examen_vtc_data:
            exam_date_raw = date_examen_vtc_data.get('date_examen_info')

        # Source 2: crm_data.Date_examen_VTC (dict avec name/id)
        if not exam_date_raw and crm_data:
            exam_date_raw = crm_data.get('Date_examen_VTC')

        logger.info(f"  📅 exam_date_raw: {exam_date_raw}")

        # Parser la date selon son format
        if exam_date_raw:
            if isinstance(exam_date_raw, dict):
                # Priorité 1: Champ Date_Examen du module Dates_Examens_VTC_TAXI (si appel API réussi)
                date_examen = exam_date_raw.get('Date_Examen')
                if date_examen:
                    logger.info(f"  📅 Date_Examen from API: {date_examen}")
                    try:
                        exam_date = datetime.strptime(date_examen, "%Y-%m-%d")
                        exam_date_formatted = exam_date.strftime("%d/%m/%Y")
                    except:
                        exam_date_formatted = date_examen
                else:
                    # Priorité 2: Parser depuis 'name' (format '51_2026-01-27' si lookup brut)
                    exam_name = exam_date_raw.get('name', '')
                    logger.info(f"  📅 exam_name from dict: {exam_name}")
                    if '_' in exam_name:
                        date_part = exam_name.split('_')[1]
                        try:
                            exam_date = datetime.strptime(date_part, "%Y-%m-%d")
                            exam_date_formatted = exam_date.strftime("%d/%m/%Y")
                        except:
                            exam_date_formatted = date_part
                    elif exam_name:
                        exam_date_formatted = exam_name
            elif isinstance(exam_date_raw, str):
                # Format string: "2026-01-27" ou "27/01/2026"
                try:
                    if '-' in exam_date_raw:
                        exam_date = datetime.strptime(exam_date_raw, "%Y-%m-%d")
                        exam_date_formatted = exam_date.strftime("%d/%m/%Y")
                    else:
                        exam_date_formatted = exam_date_raw
                except:
                    exam_date_formatted = exam_date_raw

        logger.info(f"  📅 exam_date_formatted: {exam_date_formatted}")

        # Extraire la prochaine date disponible
        next_exam_date = "la prochaine date disponible"
        if date_examen_vtc_data and date_examen_vtc_data.get('next_dates'):
            next_dates = date_examen_vtc_data.get('next_dates', [])
            if next_dates:
                first_next = next_dates[0]
                if isinstance(first_next, dict):
                    next_date_str = first_next.get('Date_Examen', '')
                    if next_date_str:
                        try:
                            from datetime import datetime
                            next_date = datetime.strptime(next_date_str, "%Y-%m-%d")
                            next_exam_date = f"le **{next_date.strftime('%d/%m/%Y')}**"
                        except:
                            next_exam_date = f"le **{next_date_str}**"

        # Extraire les identifiants ExamT3P si disponibles
        identifiant = exament3p_data.get('identifiant', '') if exament3p_data else ''
        mot_de_passe = exament3p_data.get('mot_de_passe', '') if exament3p_data else ''

        # Adapter l'introduction selon si force majeure mentionnée
        force_majeure_detected = intent_context.get('mentions_force_majeure', False)
        force_majeure_type = intent_context.get('force_majeure_type')
        force_majeure_details = intent_context.get('force_majeure_details', '')

        if force_majeure_detected and force_majeure_type == 'medical':
            intro = f"""Nous avons bien pris connaissance de votre situation concernant votre demande de report d'examen.

Nous espérons sincèrement que la situation s'améliore rapidement."""
        elif force_majeure_detected and force_majeure_type == 'death':
            intro = """Nous avons bien pris connaissance de votre situation et vous présentons nos sincères condoléances.

Nous comprenons parfaitement votre besoin de reporter l'examen dans ces circonstances."""
        elif force_majeure_detected and force_majeure_type == 'accident':
            intro = """Nous avons bien pris connaissance de votre situation suite à cet accident.

Nous espérons que vous vous remettrez rapidement."""
        else:
            intro = """Nous avons bien pris connaissance de votre demande de report de date d'examen."""

        # Bloc identifiants (si disponibles)
        identifiants_bloc = ""
        if identifiant and mot_de_passe:
            identifiants_bloc = f"""

**Vos identifiants ExamT3P** (pour contacter la CMA via la plateforme) :
- Identifiant : {identifiant}
- Mot de passe : {mot_de_passe}

"""

        # Message principal avec procédure stricte
        response_message = f"""Bonjour,

{intro}

Votre examen est actuellement prévu pour le **{exam_date_formatted}**.

**Votre dossier ayant été validé par la CMA, un report de date d'examen n'est possible qu'avec un justificatif de force majeure.**

---

**Pour demander un report, merci de nous transmettre par email :**

1. **Votre justificatif de force majeure** :
   - Certificat médical couvrant **la date de l'examen** ({exam_date_formatted})
   - Ou autre document officiel (certificat de décès, convocation judiciaire, etc.)

2. **Une brève explication de votre situation**

Nous transmettrons ensuite votre demande à la CMA pour validation du report.
{identifiants_bloc}
---

**Points importants :**

- Le certificat médical doit **obligatoirement couvrir le jour de l'examen** ({exam_date_formatted}), pas une autre période
- **Sans justificatif de force majeure valide**, des frais de réinscription de **241€** seront nécessaires pour une nouvelle inscription
- La CMA est seule décisionnaire pour accepter ou refuser le report
- En cas d'acceptation, vous serez repositionné(e) sur {next_exam_date}

---

Nous restons à votre disposition pour toute question.

Cordialement,

L'équipe Cab Formations"""

        logger.info(f"  Message REPORT_DATE généré: {len(response_message)} caractères")
        logger.info(f"  Examen prévu le: {exam_date_formatted}")
        logger.info(f"  Force majeure mentionnée: {force_majeure_detected} ({force_majeure_type})")

        return {
            'response_text': response_message,
            'detected_scenarios': ['SC-15c_REPORT_APRES_CLOTURE'],
            'similar_tickets': [],
            'validation': {
                'SC-15c_REPORT_APRES_CLOTURE': {
                    'compliant': True,
                    'missing_blocks': [],
                    'forbidden_terms_found': []
                }
            },
            'requires_crm_update': False,
            'crm_update_fields': [],
            'crm_updates': {},
            'should_stop_workflow': False,
            'metadata': {
                'input_tokens': 0,
                'output_tokens': len(response_message),
                'model': self.model,
                'report_date_mode': True,
                'exam_date': exam_date_formatted,
                'force_majeure_detected': force_majeure_detected,
                'force_majeure_type': force_majeure_type
            }
        }


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
