"""
Helper pour gérer l'éligibilité des candidats Uber 20€.

Vérifie si le candidat a complété toutes les étapes nécessaires pour
bénéficier de l'offre en partenariat avec Uber.

CONTEXTE:
- L'offre Uber à 20€ inclut:
  * Inscription à l'examen VTC (frais de 241€ payés par CAB Formations)
  * Accès à la plateforme e-learning
  * Formation en visio avec formateur (cours du jour ET cours du soir disponibles)

ÉTAPES POUR ÊTRE ÉLIGIBLE:
1. Payer les 20€ de l'offre (Opp gagnée à 20€)
2. Envoyer tous les documents et finaliser l'inscription sur la plateforme CAB Formations
   → Champ: Date_Dossier_re_u non vide
3. Réussir le test de sélection (lien envoyé par mail après finalisation)
   → Champ: Date_test_selection non vide
   → IMPORTANT: Obligatoire UNIQUEMENT si Date_Dossier_re_u > 19/05/2025
   → Pour les dossiers antérieurs, le test n'est PAS obligatoire

CAS GÉRÉS:
- PROSPECT: Opp 20€ EN ATTENTE (pas encore payé)
            → Répondre aux questions générales sur l'offre

- CAS A: Opp 20€ gagnée + Date_Dossier_re_u vide
         → Candidat a payé mais pas envoyé ses documents
         → Expliquer l'offre + demander de finaliser inscription

- CAS D: Compte_Uber = false (après vérification à Date_Dossier_recu + 1 jour)
         → Email inscription ≠ Email compte Uber Driver
         → Demander de vérifier l'email ou contacter Uber via l'app

- CAS E: ELIGIBLE = false (après vérification à Date_Dossier_recu + 1 jour)
         → Uber considère le candidat non éligible (raisons inconnues de CAB)
         → Demander de contacter Uber via l'app pour comprendre

- CAS B: Date_Dossier_re_u non vide + Date_test_selection vide (si > 19/05/2025)
         → Candidat a envoyé documents mais pas passé le test
         → Demander de passer le test (mail reçu le jour de Date_Dossier_re_u)

- ÉLIGIBLE: Toutes les vérifications OK
            → Candidat peut être inscrit à l'examen

ORDRE DE VÉRIFICATION:
1. PROSPECT (Stage = EN ATTENTE)
2. NOT_UBER (Amount ≠ 20€)
3. CAS A (Date_Dossier_recu vide)
4. CAS D (Compte_Uber = false, après J+1)
5. CAS E (ELIGIBLE = false, après J+1)
6. CAS B (Test sélection non passé, si obligatoire)
7. ÉLIGIBLE
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

from src.utils.date_utils import parse_date_flexible, format_date_for_display

logger = logging.getLogger(__name__)


def is_uber_20_deal(deal_data: Dict[str, Any]) -> bool:
    """
    Vérifie si le deal est une opportunité Uber à 20€ GAGNÉE (paiement effectué).

    Critères:
    - Stage = GAGNÉ (paiement des 20€ effectué)
    - Amount = 20 (ou proche de 20€)

    Note: Stage "EN ATTENTE" = prospect qui n'a pas encore payé (pas CAS A/B)
    """
    if not deal_data:
        return False

    stage = deal_data.get('Stage', '')
    amount = deal_data.get('Amount', 0)

    # Vérifier si le stage est gagné (paiement effectué)
    stage_is_won = stage and 'GAGN' in str(stage).upper()

    # Vérifier si le montant est 20€ (avec tolérance)
    try:
        amount_float = float(amount) if amount else 0
        amount_is_20 = 15 <= amount_float <= 25  # Tolérance pour les variations
    except (ValueError, TypeError):
        amount_is_20 = False

    return stage_is_won and amount_is_20


def is_uber_prospect(deal_data: Dict[str, Any]) -> bool:
    """
    Vérifie si le deal est un prospect Uber (EN ATTENTE, pas encore payé).

    Critères:
    - Stage = EN ATTENTE (ou similaire)
    - Amount = 20 (ou proche de 20€)

    Ces prospects posent des questions générales sur l'offre avant de payer.
    """
    if not deal_data:
        return False

    stage = deal_data.get('Stage', '')
    amount = deal_data.get('Amount', 0)

    # Vérifier si le stage est en attente
    stage_upper = str(stage).upper()
    stage_is_pending = 'ATTENTE' in stage_upper or 'PENDING' in stage_upper

    # Vérifier si le montant est 20€ (avec tolérance)
    try:
        amount_float = float(amount) if amount else 0
        amount_is_20 = 15 <= amount_float <= 25
    except (ValueError, TypeError):
        amount_is_20 = False

    return stage_is_pending and amount_is_20


def analyze_uber_eligibility(deal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse l'éligibilité d'un candidat Uber 20€.

    Args:
        deal_data: Données du deal CRM

    Returns:
        {
            'is_uber_20_deal': bool,
            'case': str ('A', 'B', 'ELIGIBLE', 'NOT_UBER'),
            'case_description': str,
            'should_include_in_response': bool,
            'response_message': str or None,
            'date_dossier_recu': str or None,
            'date_test_selection': str or None
        }
    """
    result = {
        'is_uber_20_deal': False,
        'is_uber_prospect': False,
        'case': 'NOT_UBER',
        'case_description': '',
        'should_include_in_response': False,
        'response_message': None,
        'date_dossier_recu': None,
        'date_test_selection': None
    }

    logger.info("🔍 Analyse de l'éligibilité Uber 20€...")

    # ================================================================
    # CAS PROSPECT: Deal EN ATTENTE (pas encore payé)
    # ================================================================
    if is_uber_prospect(deal_data):
        result['is_uber_prospect'] = True
        result['case'] = 'PROSPECT'
        result['case_description'] = "Prospect Uber - Paiement non effectué"
        result['should_include_in_response'] = True
        result['response_message'] = generate_prospect_message()
        logger.info("  ➡️ PROSPECT Uber: En attente de paiement")
        return result

    # Vérifier si c'est un deal Uber 20€ GAGNÉ
    if not is_uber_20_deal(deal_data):
        result['case'] = 'NOT_UBER'
        result['case_description'] = "Pas une opportunité Uber 20€"
        logger.info("  ➡️ Pas une opportunité Uber 20€")
        return result

    result['is_uber_20_deal'] = True
    logger.info("  ✅ Opportunité Uber 20€ détectée")

    # Récupérer les dates clés
    date_dossier_recu = deal_data.get('Date_Dossier_re_u')
    date_test_selection = deal_data.get('Date_test_selection')

    result['date_dossier_recu'] = date_dossier_recu
    result['date_test_selection'] = date_test_selection

    logger.info(f"  Date_Dossier_re_u: {date_dossier_recu}")
    logger.info(f"  Date_test_selection: {date_test_selection}")

    # CAS A: Date_Dossier_re_u vide → Documents non envoyés
    if not date_dossier_recu:
        result['case'] = 'A'
        result['case_description'] = "Documents non envoyés - Expliquer offre et demander finalisation"
        result['should_include_in_response'] = True
        result['response_message'] = generate_documents_missing_message()
        logger.info("  ➡️ CAS A: Documents non envoyés")
        return result

    # ================================================================
    # VÉRIFICATION COMPTE UBER ET ÉLIGIBILITÉ
    # La vérification manuelle se fait à Date_Dossier_recu + 1 jour
    # Avant ce délai, on ne sait pas encore → ne pas bloquer
    # ================================================================
    verification_done = False
    dossier_date = parse_date_flexible(date_dossier_recu, "Date_Dossier_recu")
    if dossier_date:
        verification_date = dossier_date + timedelta(days=1)
        today = datetime.now().date()
        verification_done = today >= verification_date
        logger.info(f"  📋 Vérification Uber: {'✅ Faite' if verification_done else '⏳ En attente'} (dossier: {dossier_date}, vérif: {verification_date})")

    # CAS D & E : Vérification Compte_Uber et ELIGIBLE (uniquement si vérification faite)
    if verification_done:
        compte_uber = deal_data.get('Compte_Uber', False)
        eligible = deal_data.get('ELIGIBLE', False)

        logger.info(f"  Compte_Uber: {compte_uber}")
        logger.info(f"  ELIGIBLE: {eligible}")

        # CAS D: Compte_Uber = false → Email pas lié à un compte Uber Driver
        if not compte_uber:
            result['case'] = 'D'
            result['case_description'] = "Compte Uber non vérifié - Email non lié à un compte Uber Driver"
            result['should_include_in_response'] = True
            result['response_message'] = generate_compte_uber_missing_message()
            logger.info("  ➡️ CAS D: Compte_Uber non vérifié")
            return result

        # CAS E: ELIGIBLE = false → Uber considère le candidat non éligible
        if not eligible:
            result['case'] = 'E'
            result['case_description'] = "Non éligible selon Uber - Raisons inconnues de CAB"
            result['should_include_in_response'] = True
            result['response_message'] = generate_not_eligible_message()
            logger.info("  ➡️ CAS E: Non éligible selon Uber")
            return result

    # CAS B: Date_Dossier_re_u OK mais Date_test_selection vide → Test non passé
    # IMPORTANT: Le test de sélection n'est obligatoire que pour les dossiers
    # reçus APRÈS le 19/05/2025. Pour les dossiers antérieurs, on passe directement
    # à ÉLIGIBLE sans exiger le test.
    TEST_SELECTION_MANDATORY_FROM = datetime(2025, 5, 19).date()

    # Déterminer si le test est obligatoire en fonction de la date de réception
    # Note: dossier_date déjà parsé plus haut via parse_date_flexible
    test_is_mandatory = False
    if dossier_date:
        test_is_mandatory = dossier_date > TEST_SELECTION_MANDATORY_FROM
        logger.info(f"  📅 Date dossier: {dossier_date} | Test obligatoire: {test_is_mandatory} (seuil: {TEST_SELECTION_MANDATORY_FROM})")

    if not date_test_selection and test_is_mandatory:
        result['case'] = 'B'
        result['case_description'] = "Test de sélection non passé - Demander de passer le test"
        result['should_include_in_response'] = True

        # Formater la date de réception du dossier pour le message
        date_dossier_formatted = format_date_for_display(date_dossier_recu)
        result['response_message'] = generate_test_selection_missing_message(date_dossier_formatted)
        logger.info("  ➡️ CAS B: Test de sélection non passé (obligatoire car dossier après 19/05/2025)")
        return result
    elif not date_test_selection and not test_is_mandatory:
        logger.info("  ℹ️ Test de sélection non passé MAIS non obligatoire (dossier avant 19/05/2025)")

    # ÉLIGIBLE: Les deux dates sont remplies
    result['case'] = 'ELIGIBLE'
    result['case_description'] = "Candidat éligible - Peut être inscrit à l'examen"
    result['should_include_in_response'] = False  # Pas de message spécial, processus normal
    logger.info("  ✅ ÉLIGIBLE: Candidat peut être inscrit à l'examen")
    return result


# Note: format_date_for_display est importé depuis date_utils
# La fonction originale a été supprimée au profit de la version centralisée


def generate_prospect_message() -> str:
    """
    Génère le message pour les PROSPECTS: candidat intéressé mais paiement non effectué.

    Répond aux questions générales et encourage à finaliser le paiement.
    """
    return """Merci pour votre intérêt pour notre formation VTC en partenariat avec Uber !

**Concernant votre question sur les formations :**

Nos formations de 40 heures en visio-conférence se déroulent à **horaires fixes** selon un planning établi. Nous proposons **deux types de sessions** pour nous adapter au mieux à vos contraintes :

📅 **Cours du jour** : 8h30 - 16h30
   → Durée : **1 semaine** (du lundi au vendredi)

🌙 **Cours du soir** : 18h00 - 22h00
   → Durée : **2 semaines** (soirées du lundi au vendredi)

**Ce que comprend l'offre à 20€ :**

✅ **Paiement des frais d'examen de 241€** à la CMA - entièrement pris en charge par CAB Formations
✅ **Formation en visio-conférence de 40 heures** avec un formateur professionnel
✅ **Accès illimité au e-learning** pour réviser à votre rythme
✅ **Accompagnement personnalisé** jusqu'à l'obtention de votre carte VTC

**Pour profiter de cette offre exceptionnelle, il vous suffit de :**

1. **Finaliser votre paiement de 20€** sur notre plateforme
2. Nous envoyer vos documents (pièce d'identité, justificatif de domicile, etc.)
3. Passer un test de sélection simple

Dès réception de votre paiement et de vos documents, nous pourrons vous proposer les prochaines dates d'examen disponibles dans votre région.

**N'attendez plus** pour démarrer votre parcours vers la carte VTC ! Les places sont limitées et les dates d'examen se remplissent vite."""


def generate_documents_missing_message() -> str:
    """
    Génère le message pour CAS A: candidat a payé 20€ mais n'a pas envoyé ses documents.

    Explique l'offre et demande de finaliser l'inscription.
    """
    return """Nous avons bien reçu votre paiement de 20€ pour l'offre VTC en partenariat avec Uber. Merci pour votre confiance !

**Ce que comprend votre offre :**

- **Inscription à l'examen VTC** incluant le paiement des frais d'examen de 241€ (pris en charge par CAB Formations)
- **Accès à notre plateforme e-learning** pour réviser à votre rythme
- **Formation en visio** avec un formateur professionnel (cours du jour OU cours du soir selon votre disponibilité)

**Pour bénéficier de cette offre, il vous reste à :**

1. **Finaliser votre inscription** sur la plateforme CAB Formations où vous avez effectué le paiement
2. **Nous transmettre tous vos documents** requis (pièce d'identité, justificatif de domicile, etc.)
3. **Passer un test de sélection simple** - Vous recevrez le lien par email une fois votre inscription finalisée

Le test de sélection est rapide et ne nécessite aucune préparation particulière. Il nous permet simplement de déclencher votre inscription à l'examen.

Merci de finaliser votre inscription au plus vite afin que nous puissions vous proposer les prochaines dates d'examen disponibles."""


def generate_test_selection_missing_message(date_dossier_recu: str) -> str:
    """
    Génère le message pour CAS B: candidat a envoyé ses documents mais n'a pas passé le test.

    Demande de passer le test de sélection.
    """
    date_text = f" le **{date_dossier_recu}**" if date_dossier_recu else ""

    return f"""Nous avons bien reçu votre dossier{date_text}. Merci !

**Pour finaliser votre inscription à l'examen VTC, il vous reste une dernière étape :**

Vous devez passer le **test de sélection**. Un email contenant le lien vers ce test vous a été envoyé{date_text}.

**À propos du test de sélection :**

- C'est un test **simple et rapide**
- Il **ne nécessite pas de consulter les cours** au préalable
- Il nous permet de **déclencher votre inscription à l'examen**

**Important :** Nous ne pouvons pas procéder à votre inscription à l'examen tant que vous n'avez pas réussi ce test.

Si vous n'avez pas reçu l'email ou si vous avez des difficultés pour accéder au test, n'hésitez pas à nous le signaler et nous vous renverrons le lien.

Merci de passer ce test dès que possible afin que nous puissions vous proposer les prochaines dates d'examen."""


def generate_compte_uber_missing_message() -> str:
    """
    Génère le message pour CAS D: Compte_Uber = false après vérification.

    L'email utilisé pour l'inscription n'est pas lié à un compte Uber Driver actif.
    Le candidat doit vérifier son email et contacter Uber si nécessaire.
    """
    return """Nous avons vérifié votre inscription et constaté que l'adresse email utilisée n'est pas liée à un compte Uber chauffeur actif.

**Voici les étapes à suivre :**

1️⃣ **Vérifiez que vous utilisez la bonne adresse email**
   - L'email utilisé pour votre inscription CAB Formations doit être **exactement le même** que celui de votre compte **Uber Driver** (chauffeur), et non votre compte Uber client.
   - Si vous avez utilisé une adresse différente, merci de nous communiquer l'adresse email liée à votre compte Uber Driver afin que nous puissions mettre à jour votre dossier.

2️⃣ **Si les adresses sont identiques**
   - Votre compte Uber chauffeur semble inactif ou non reconnu par Uber.
   - Vous devez contacter directement le support Uber pour comprendre la situation.

**Comment contacter Uber :**
   - Connectez-vous à l'application **Uber Driver**
   - Allez dans **Compte** → **Aide**
   - Utilisez le **chat intégré** pour échanger avec le support Uber

⚠️ **Important :** Nous n'avons aucune visibilité sur les critères internes d'Uber. Seul leur support peut vous expliquer pourquoi votre compte n'est pas reconnu.

Une fois la situation clarifiée avec Uber, revenez vers nous pour que nous puissions finaliser votre inscription."""


def generate_not_eligible_message() -> str:
    """
    Génère le message pour CAS E: ELIGIBLE = false après vérification.

    Uber considère le candidat comme non éligible à l'offre partenariat.
    CAB n'a aucune visibilité sur les raisons - le candidat doit contacter Uber.
    """
    return """Nous avons vérifié votre dossier auprès d'Uber et malheureusement, votre profil n'est **pas éligible** à l'offre VTC en partenariat avec Uber.

**Ce que cela signifie :**

Uber applique ses propres critères d'éligibilité pour cette offre partenariat. Malheureusement, **nous n'avons aucune visibilité** sur les raisons de cette décision - seul Uber peut vous les communiquer.

**Ce que vous devez faire :**

📱 **Contactez le support Uber** pour comprendre pourquoi vous n'êtes pas éligible :
   - Connectez-vous à l'application **Uber Driver**
   - Allez dans **Compte** → **Aide**
   - Utilisez le **chat intégré** pour échanger avec le support

Expliquez-leur que vous souhaitez bénéficier de l'offre de formation VTC en partenariat avec CAB Formations et demandez pourquoi votre profil n'est pas éligible.

**Alternatives possibles :**

Si Uber confirme que vous n'êtes pas éligible à leur offre partenariat, vous pouvez toujours vous inscrire à notre formation VTC classique. N'hésitez pas à nous contacter pour plus d'informations sur cette option.

Nous restons à votre disposition pour toute question."""
