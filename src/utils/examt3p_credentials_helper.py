"""
Helper pour gérer les identifiants ExamT3P et leur validation.

Workflow complet :
1. Recherche identifiants dans Zoho CRM
2. Si absents, recherche dans les threads de mail
3. Si aucun identifiant trouvé : Ne PAS demander au candidat (création de compte par nous)
4. Test de connexion OBLIGATOIRE pour les identifiants trouvés
5. Mise à jour Zoho si identifiants trouvés dans les mails et connexion OK
6. Si connexion échoue : Demander au candidat de réinitialiser via "Mot de passe oublié ?"
"""
import logging
import re
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)


def extract_credentials_from_threads(threads: List[Dict]) -> Optional[Dict[str, str]]:
    """
    Extrait les identifiants ExamT3P depuis les threads de mail.

    Cherche des patterns comme :
    - Identifiant: xxx
    - Email: xxx
    - Mot de passe: xxx
    - Password: xxx
    - Login: xxx
    - MDP: xxx

    Args:
        threads: Liste des threads de ticket (direction 'in' = messages client)

    Returns:
        Dict avec 'identifiant' et 'mot_de_passe' si trouvés, None sinon
    """
    from src.utils.text_utils import get_clean_thread_content

    # Patterns pour détecter les identifiants
    # Pattern pour identifiant/email (amélioration: capture jusqu'à la fin de ligne ou prochain champ)
    identifiant_patterns = [
        r'identifiant\s*:?\s*([^\n]+?)(?:\s*(?:mot|mdp|password|pass|$))',
        r'login\s*:?\s*([^\n]+?)(?:\s*(?:mot|mdp|password|pass|$))',
        r'email\s*:?\s*([^\n]+?)(?:\s*(?:mot|mdp|password|pass|$))',
        r'utilisateur\s*:?\s*([^\n]+?)(?:\s*(?:mot|mdp|password|pass|$))',
        r'username\s*:?\s*([^\n]+?)(?:\s*(?:mot|mdp|password|pass|$))',
        # Fallback simple patterns
        r'identifiant\s*:?\s*([^\s\n]+)',
        r'login\s*:?\s*([^\s\n]+)',
        r'email\s*:?\s*([^\s\n]+)',
    ]

    # Pattern pour mot de passe (amélioration: capture jusqu'à la fin de ligne)
    password_patterns = [
        r'mot\s+de\s+passe\s*:?\s*([^\n]+?)(?:\n|$)',
        r'mdp\s*:?\s*([^\n]+?)(?:\n|$)',
        r'password\s*:?\s*([^\n]+?)(?:\n|$)',
        r'pass\s*:?\s*([^\n]+?)(?:\n|$)',
        # Fallback simple patterns
        r'mot\s+de\s+passe\s*:?\s*([^\s\n]+)',
        r'mdp\s*:?\s*([^\s\n]+)',
        r'password\s*:?\s*([^\s\n]+)',
    ]

    identifiant = None
    mot_de_passe = None

    # Parcourir les threads (messages entrants du client)
    for thread in threads:
        if thread.get('direction') != 'in':
            continue

        # Nettoyer le contenu
        content = get_clean_thread_content(thread)
        content_lower = content.lower()

        # Chercher l'identifiant
        if not identifiant:
            for pattern in identifiant_patterns:
                match = re.search(pattern, content_lower, re.IGNORECASE)
                if match:
                    # Récupérer l'identifiant et nettoyer les espaces
                    extracted = match.group(1).strip()
                    # Vérifier que ce n'est pas juste un fragment
                    if len(extracted) > 3 and '@' in extracted or len(extracted) > 5:
                        identifiant = extracted
                        logger.info(f"Identifiant trouvé dans les threads: {identifiant}")
                        break

        # Chercher le mot de passe
        if not mot_de_passe:
            for pattern in password_patterns:
                match = re.search(pattern, content_lower, re.IGNORECASE)
                if match:
                    # Récupérer le mot de passe et nettoyer les espaces
                    extracted = match.group(1).strip()
                    # Vérifier que ce n'est pas juste un fragment
                    if len(extracted) > 3:
                        mot_de_passe = extracted
                        logger.info("Mot de passe trouvé dans les threads: ****")
                        break

        # Si on a les deux, on peut arrêter
        if identifiant and mot_de_passe:
            break

    if identifiant and mot_de_passe:
        return {
            'identifiant': identifiant,
            'mot_de_passe': mot_de_passe,
            'source': 'email_threads'
        }

    if identifiant or mot_de_passe:
        logger.warning(
            f"Identifiants incomplets trouvés dans les threads: "
            f"identifiant={'Oui' if identifiant else 'Non'}, "
            f"mot_de_passe={'Oui' if mot_de_passe else 'Non'}"
        )

    return None


def test_examt3p_connection(identifiant: str, mot_de_passe: str) -> Tuple[bool, Optional[str]]:
    """
    Test la connexion ExamT3P avec les identifiants fournis.

    Args:
        identifiant: IDENTIFIANT_EVALBOX
        mot_de_passe: MDP_EVALBOX

    Returns:
        Tuple (success: bool, error_message: str or None)
    """
    import asyncio

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Module playwright non installé")
        return False, "Module playwright non installé - impossible de tester la connexion"

    logger.info(f"Test de connexion ExamT3P pour {identifiant}...")

    async def test_login():
        """Test de login asynchrone."""
        try:
            async with async_playwright() as p:
                # Lancer le navigateur en mode headless
                # Note: Playwright trouvera automatiquement le navigateur installé (cross-platform)
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )

                context = await browser.new_context(viewport={'width': 1280, 'height': 720})
                context.set_default_timeout(30000)  # 30 secondes
                page = await context.new_page()

                try:
                    # Accéder à la page de connexion
                    await page.goto("https://www.exament3p.fr/id/14", wait_until='networkidle', timeout=30000)
                    await asyncio.sleep(2)

                    # Cliquer sur "Me connecter" pour ouvrir la modal
                    try:
                        me_connecter_btn = await page.wait_for_selector('button:has-text("Me connecter")', timeout=10000)
                        if me_connecter_btn:
                            await me_connecter_btn.click()
                            await asyncio.sleep(1)
                    except:
                        pass

                    # Remplir le formulaire
                    email_selectors = ['#loginEmail', 'input[type="email"]', 'input[name="email"]']
                    email_filled = False
                    for selector in email_selectors:
                        try:
                            await page.wait_for_selector(selector, state='visible', timeout=5000)
                            await page.fill(selector, identifiant)
                            email_filled = True
                            break
                        except:
                            continue

                    if not email_filled:
                        return False, "Champ email non trouvé"

                    password_selectors = ['#loginPassword', 'input[type="password"]', 'input[name="password"]']
                    password_filled = False
                    for selector in password_selectors:
                        try:
                            await page.fill(selector, mot_de_passe)
                            password_filled = True
                            break
                        except:
                            continue

                    if not password_filled:
                        return False, "Champ mot de passe non trouvé"

                    # Cliquer sur le bouton de connexion
                    submit_selectors = [
                        '#loginModal button:has-text("Se connecter")',
                        'button:has-text("Se connecter")',
                        'button[type="submit"]'
                    ]

                    submitted = False
                    for selector in submit_selectors:
                        try:
                            btn = await page.query_selector(selector)
                            if btn:
                                await btn.click()
                                submitted = True
                                break
                        except:
                            continue

                    if not submitted:
                        await page.keyboard.press('Enter')

                    # Attendre la navigation
                    await asyncio.sleep(3)

                    # Vérifier si connecté
                    success_indicators = [
                        "Vue d'ensemble",
                        "Mon Espace Candidat",
                        "Déconnexion",
                        "Bienvenue"
                    ]

                    content = await page.content()
                    for indicator in success_indicators:
                        if indicator in content:
                            return True, None

                    # Vérifier l'URL
                    current_url = page.url
                    if "mon-espace" in current_url or "dashboard" in current_url:
                        return True, None

                    # Vérifier si erreur de connexion visible
                    if "Identifiant ou mot de passe incorrect" in content or "invalid" in content.lower():
                        return False, "Identifiants invalides"

                    return False, "Connexion échouée - page d'accueil non détectée"

                finally:
                    await browser.close()

        except Exception as e:
            return False, f"Erreur lors du test de connexion: {str(e)}"

    try:
        # Exécuter le test de login
        success, error = asyncio.run(test_login())

        if success:
            logger.info("✅ Test de connexion ExamT3P réussi")
            return True, None
        else:
            logger.warning(f"❌ Test de connexion ExamT3P échoué: {error}")
            return False, error

    except Exception as e:
        logger.error(f"❌ Erreur lors du test de connexion ExamT3P: {e}")
        return False, str(e)


def get_credentials_with_validation(
    deal_data: Dict,
    threads: List[Dict],
    crm_client=None,
    deal_id: Optional[str] = None,
    auto_update_crm: bool = False
) -> Dict:
    """
    Workflow complet pour récupérer et valider les identifiants ExamT3P.

    Étapes:
    1. Chercher dans le CRM (deal_data)
    2. Si absents, chercher dans les threads de mail
    3. Tester la connexion (OBLIGATOIRE)
    4. Si connexion OK et identifiants viennent des mails → MAJ CRM
    5. Si connexion KO → préparer réponse au candidat

    Args:
        deal_data: Données du deal CRM
        threads: Threads du ticket
        crm_client: Client Zoho CRM (pour mise à jour)
        deal_id: ID du deal (pour mise à jour)
        auto_update_crm: Mettre à jour automatiquement le CRM

    Returns:
        {
            'credentials_found': bool,
            'credentials_source': 'crm' | 'email_threads' | None,
            'identifiant': str or None,
            'mot_de_passe': str or None,
            'connection_test_success': bool,
            'connection_error': str or None,
            'crm_updated': bool,
            'should_respond_to_candidate': bool,
            'candidate_response_message': str or None
        }
    """
    result = {
        'credentials_found': False,
        'credentials_source': None,
        'identifiant': None,
        'mot_de_passe': None,
        'connection_test_success': False,
        'connection_error': None,
        'crm_updated': False,
        'should_respond_to_candidate': False,
        'candidate_response_message': None
    }

    # ================================================================
    # ÉTAPE 1: Chercher dans le CRM
    # ================================================================
    logger.info("🔍 Recherche des identifiants ExamT3P...")
    logger.info("  Étape 1/3: Vérification dans le CRM...")

    identifiant_crm = deal_data.get('IDENTIFIANT_EVALBOX')
    mdp_crm = deal_data.get('MDP_EVALBOX')

    identifiant = None
    mot_de_passe = None
    source = None

    if identifiant_crm and mdp_crm:
        identifiant = identifiant_crm
        mot_de_passe = mdp_crm
        source = 'crm'
        logger.info(f"  ✅ Identifiants trouvés dans le CRM: {identifiant}")
        result['credentials_found'] = True
        result['credentials_source'] = 'crm'
    else:
        logger.info("  ⚠️  Identifiants absents du CRM")

        # ================================================================
        # ÉTAPE 2: Chercher dans les threads de mail
        # ================================================================
        logger.info("  Étape 2/3: Recherche dans les threads de mail...")

        credentials_from_threads = extract_credentials_from_threads(threads)

        if credentials_from_threads:
            identifiant = credentials_from_threads['identifiant']
            mot_de_passe = credentials_from_threads['mot_de_passe']
            source = 'email_threads'
            logger.info(f"  ✅ Identifiants trouvés dans les threads: {identifiant}")
            result['credentials_found'] = True
            result['credentials_source'] = 'email_threads'
        else:
            logger.warning("  ⚠️  Identifiants introuvables dans les threads")

    # Si aucun identifiant trouvé, arrêter ici
    # NOTE: On ne demande PAS les identifiants car c'est nous qui allons créer le compte
    if not identifiant or not mot_de_passe:
        logger.warning("❌ Identifiants ExamT3P non trouvés - Création de compte nécessaire")
        result['should_respond_to_candidate'] = False  # Pas de demande au candidat
        result['candidate_response_message'] = None
        return result

    result['identifiant'] = identifiant
    result['mot_de_passe'] = mot_de_passe

    # ================================================================
    # ÉTAPE 3: TEST DE CONNEXION (OBLIGATOIRE)
    # ================================================================
    logger.info("  Étape 3/3: Test de connexion...")

    connection_ok, connection_error = test_examt3p_connection(identifiant, mot_de_passe)

    result['connection_test_success'] = connection_ok
    result['connection_error'] = connection_error

    # ================================================================
    # ÉTAPE 4: Actions selon résultat du test
    # ================================================================
    if connection_ok:
        logger.info("✅ Connexion ExamT3P validée")

        # Si identifiants viennent des mails, mettre à jour le CRM
        if source == 'email_threads' and auto_update_crm and crm_client and deal_id:
            logger.info("📝 Mise à jour du CRM avec les identifiants trouvés dans les mails...")
            try:
                crm_client.update_deal(deal_id, {
                    'IDENTIFIANT_EVALBOX': identifiant,
                    'MDP_EVALBOX': mot_de_passe
                })
                logger.info("✅ CRM mis à jour avec les nouveaux identifiants")
                result['crm_updated'] = True
            except Exception as e:
                logger.error(f"❌ Erreur lors de la mise à jour du CRM: {e}")

    else:
        # ================================================================
        # ÉTAPE 5: Connexion échouée → Réponse au candidat
        # ================================================================
        logger.warning(f"❌ Connexion ExamT3P échouée: {connection_error}")
        result['should_respond_to_candidate'] = True

        # Générer le message selon la source des identifiants
        if source == 'crm':
            result['candidate_response_message'] = generate_invalid_credentials_response_crm()
        else:
            result['candidate_response_message'] = generate_invalid_credentials_response_email()

    return result


def generate_invalid_credentials_response_crm() -> str:
    """
    Génère le message à envoyer au candidat quand les identifiants du CRM ne fonctionnent pas.
    """
    return """Bonjour,

Nous avons tenté d'accéder à votre dossier sur la plateforme ExamenT3P avec les identifiants que vous nous aviez précédemment transmis, mais la connexion a échoué.

Il est possible que vous ayez modifié votre mot de passe depuis.

Pour accéder à votre compte, veuillez suivre la procédure de réinitialisation :

1. Rendez-vous sur la plateforme ExamenT3P : https://www.exament3p.fr
2. Cliquez sur "Me connecter"
3. Utilisez la fonction "Mot de passe oublié ?"
4. Suivez les instructions pour réinitialiser votre mot de passe

Une fois votre mot de passe réinitialisé, merci de nous transmettre vos nouveaux identifiants afin que nous puissions assurer le suivi de votre dossier.

Cordialement,
L'équipe DOC"""


def generate_invalid_credentials_response_email() -> str:
    """
    Génère le message à envoyer au candidat quand les identifiants trouvés dans les mails ne fonctionnent pas.
    """
    return """Bonjour,

Nous avons tenté d'accéder à votre dossier sur la plateforme ExamenT3P avec les identifiants que vous nous avez transmis, mais la connexion a échoué.

Il est possible que vous ayez modifié votre mot de passe ou que les identifiants ne soient plus à jour.

Pour accéder à votre compte, veuillez suivre la procédure de réinitialisation :

1. Rendez-vous sur la plateforme ExamenT3P : https://www.exament3p.fr
2. Cliquez sur "Me connecter"
3. Utilisez la fonction "Mot de passe oublié ?"
4. Suivez les instructions pour réinitialiser votre mot de passe

Une fois votre mot de passe réinitialisé, merci de nous transmettre vos nouveaux identifiants afin que nous puissions assurer le suivi de votre dossier.

Cordialement,
L'équipe DOC"""
