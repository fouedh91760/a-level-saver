"""
MODULE D'EXTRACTION AUTOMATIQUE EXAMENT3P VIA PLAYWRIGHT
Version: 4.0
Date: 05/01/2026

Extrait automatiquement TOUTES les données du portail ExamenT3P :
- Vue d'ensemble : statut dossier, progression, actions requises, historique
- Mes Examens : dates, convocation
- Mes Documents : statut de chaque pièce justificative
- Mon Compte : informations personnelles
- Mes Paiements : historique complet des paiements
- Messages : échanges avec la CMA

Features v4.0:
- Système de retry automatique (3 tentatives par défaut)
- Gestion d'erreurs robuste avec fallbacks
- Timeouts configurables
- Logs détaillés pour debugging

Usage:
    from exament3p_playwright import extract_exament3p_sync

    data = extract_exament3p_sync(identifiant, password)
"""

import asyncio
import re
from typing import Dict, List, Optional
from datetime import datetime
import traceback


# Configuration des retries et timeouts
MAX_RETRIES = 3
RETRY_DELAY = 2  # secondes entre chaque retry
PAGE_LOAD_TIMEOUT = 30000  # 30 secondes
ELEMENT_TIMEOUT = 10000  # 10 secondes
ACTION_DELAY = 1  # délai entre actions (secondes)


class RetryError(Exception):
    """Exception levée après épuisement des retries."""
    pass


async def retry_async(func, max_retries=MAX_RETRIES, delay=RETRY_DELAY, description="opération"):
    """
    Exécute une fonction async avec retry automatique.

    Args:
        func: Fonction async à exécuter
        max_retries: Nombre maximum de tentatives
        delay: Délai entre les tentatives (secondes)
        description: Description de l'opération pour les logs

    Returns:
        Résultat de la fonction

    Raises:
        RetryError: Si toutes les tentatives échouent
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                print(f"      ⚠️ Tentative {attempt}/{max_retries} échouée pour {description}: {str(e)[:50]}...")
                await asyncio.sleep(delay)
            else:
                print(f"      ❌ Échec après {max_retries} tentatives pour {description}")

    raise RetryError(f"Échec de {description} après {max_retries} tentatives: {last_error}")


class ExamenT3PPlaywright:
    """Extracteur automatique complet ExamenT3P via Playwright avec gestion d'erreurs robuste."""

    URL_BASE = "https://www.exament3p.fr"
    URL_LOGIN = "https://www.exament3p.fr/id/14"

    def __init__(self, identifiant: str, password: str, max_retries: int = MAX_RETRIES):
        """
        Initialise l'extracteur.

        Args:
            identifiant: Email du candidat (login ExamenT3P)
            password: Mot de passe ExamenT3P
            max_retries: Nombre maximum de tentatives pour chaque opération
        """
        self.identifiant = identifiant
        self.password = password
        self.max_retries = max_retries
        self.data = {
            'identifiant': identifiant,
            'extraction_requise': True,
            'errors': []
        }
        self.browser = None
        self.page = None

    async def extract_all(self) -> Dict:
        """
        Extraction complète de TOUTES les données ExamenT3P avec retry global.

        Returns:
            Dictionnaire avec toutes les données extraites
        """
        from playwright.async_api import async_playwright

        for global_attempt in range(1, self.max_retries + 1):
            try:
                async with async_playwright() as p:
                    # Lancer le navigateur en mode headless
                    # NOTE: Ne PAS spécifier executable_path pour laisser Playwright utiliser son navigateur bundlé
                    # Installer les navigateurs avec: playwright install chromium
                    self.browser = await p.chromium.launch(
                        headless=True,
                        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                    )

                    # Créer un contexte avec timeout configuré
                    context = await self.browser.new_context(
                        viewport={'width': 1280, 'height': 720}
                    )
                    context.set_default_timeout(PAGE_LOAD_TIMEOUT)

                    self.page = await context.new_page()

                    try:
                        # 1. Connexion avec retry
                        print("   🔐 Connexion en cours...")
                        connected = await self._login_with_retry()
                        if not connected:
                            raise Exception("Échec de connexion après retries")

                        print("   ✅ Connexion réussie")

                        # 2. Extraction de chaque page avec gestion d'erreurs individuelle
                        await self._extract_all_pages()

                        # 3. Déconnexion (non bloquante)
                        await self._safe_logout()

                        # Marquer l'extraction comme réussie
                        self.data['extraction_requise'] = False
                        self.data['extraction_date'] = datetime.now().isoformat()
                        self.data['extraction_attempt'] = global_attempt

                        print("   ✅ Extraction complète terminée")
                        return self.data

                    except Exception as e:
                        self.data['errors'].append(f"Tentative {global_attempt}: {str(e)}")
                        raise
                    finally:
                        await self.browser.close()

            except Exception as e:
                if global_attempt < self.max_retries:
                    print(f"   ⚠️ Tentative globale {global_attempt}/{self.max_retries} échouée: {str(e)[:80]}")
                    print(f"   🔄 Nouvelle tentative dans {RETRY_DELAY * 2}s...")
                    await asyncio.sleep(RETRY_DELAY * 2)
                else:
                    print(f"   ❌ Échec après {self.max_retries} tentatives globales")
                    self.data['error'] = str(e)
                    return self.data

        return self.data

    async def _login_with_retry(self) -> bool:
        """Connexion avec système de retry."""
        async def attempt_login():
            return await self._login()

        try:
            return await retry_async(attempt_login, max_retries=self.max_retries, description="connexion")
        except RetryError:
            return False

    async def _login(self) -> bool:
        """Connexion au portail ExamenT3P."""
        try:
            # Accéder à la page de connexion
            await self.page.goto(self.URL_LOGIN, wait_until='networkidle', timeout=PAGE_LOAD_TIMEOUT)
            await asyncio.sleep(ACTION_DELAY * 2)

            # Méthode 1: Cliquer sur "Me connecter" pour ouvrir la modal
            try:
                me_connecter_btn = await self.page.wait_for_selector(
                    'button:has-text("Me connecter")',
                    timeout=ELEMENT_TIMEOUT
                )
                if me_connecter_btn:
                    await me_connecter_btn.click()
                    await asyncio.sleep(ACTION_DELAY)
            except:
                # Méthode 2: La modal est peut-être déjà ouverte
                pass

            # Attendre que la modal soit visible avec plusieurs sélecteurs possibles
            modal_selectors = ['#loginModal', '.modal.show', '[role="dialog"]']
            modal_found = False
            for selector in modal_selectors:
                try:
                    await self.page.wait_for_selector(selector, state='visible', timeout=ELEMENT_TIMEOUT)
                    modal_found = True
                    break
                except:
                    continue

            if not modal_found:
                # Essayer de trouver directement les champs de login
                pass

            # Remplir le formulaire - essayer plusieurs sélecteurs
            email_selectors = ['#loginEmail', 'input[type="email"]', 'input[name="email"]']
            password_selectors = ['#loginPassword', 'input[type="password"]', 'input[name="password"]']

            email_filled = False
            for selector in email_selectors:
                try:
                    await self.page.wait_for_selector(selector, state='visible', timeout=ELEMENT_TIMEOUT // 2)
                    await self.page.fill(selector, self.identifiant)
                    email_filled = True
                    break
                except:
                    continue

            if not email_filled:
                raise Exception("Champ email non trouvé")

            await asyncio.sleep(ACTION_DELAY / 2)

            password_filled = False
            for selector in password_selectors:
                try:
                    await self.page.fill(selector, self.password)
                    password_filled = True
                    break
                except:
                    continue

            if not password_filled:
                raise Exception("Champ mot de passe non trouvé")

            await asyncio.sleep(ACTION_DELAY / 2)

            # Cliquer sur le bouton de connexion - essayer plusieurs sélecteurs
            submit_selectors = [
                '#loginModal button:has-text("Se connecter")',
                'button:has-text("Se connecter")',
                'button[type="submit"]',
                '.btn-primary:has-text("connecter")'
            ]

            submitted = False
            for selector in submit_selectors:
                try:
                    btn = await self.page.query_selector(selector)
                    if btn:
                        await btn.click()
                        submitted = True
                        break
                except:
                    continue

            if not submitted:
                # Fallback: appuyer sur Enter
                await self.page.keyboard.press('Enter')

            # Attendre la navigation avec plusieurs indicateurs de succès
            await asyncio.sleep(ACTION_DELAY * 3)

            # Vérifier si connecté avec plusieurs indicateurs
            success_indicators = [
                "Vue d'ensemble",
                "Mon Espace Candidat",
                "Déconnexion",
                "Bienvenue",
                "monEspaceContainer"
            ]

            content = await self.page.content()
            for indicator in success_indicators:
                if indicator in content:
                    return True

            # Vérifier l'URL
            current_url = self.page.url
            if "mon-espace" in current_url or "dashboard" in current_url:
                return True

            return False

        except Exception as e:
            raise Exception(f"Erreur login: {e}")

    async def _extract_all_pages(self):
        """Extrait toutes les pages avec gestion d'erreurs individuelle."""

        # Liste des extractions à effectuer
        extractions = [
            ("📋 Vue d'ensemble", self._extract_overview),
            ("📅 Mes Examens", self._extract_examens),
            ("📄 Mes Documents", self._extract_documents),
            ("👤 Mon Compte", self._extract_compte),
            ("💳 Mes Paiements", self._extract_paiements),
            ("💬 Messages", self._extract_messages),
        ]

        for name, extract_func in extractions:
            print(f"   {name}...")
            try:
                await extract_func()
            except Exception as e:
                error_msg = f"Erreur {name}: {str(e)[:50]}"
                print(f"      ⚠️ {error_msg}")
                self.data['errors'].append(error_msg)
                # Continuer avec les autres extractions

    async def _safe_click(self, selector: str, timeout: int = ELEMENT_TIMEOUT) -> bool:
        """Clic sécurisé avec gestion d'erreurs."""
        try:
            await self.page.click(selector, timeout=timeout)
            await asyncio.sleep(ACTION_DELAY)
            return True
        except Exception as e:
            return False

    async def _safe_get_text(self) -> str:
        """Récupère le texte de la page de manière sécurisée."""
        try:
            return await self.page.inner_text('body')
        except:
            try:
                return await self.page.content()
            except:
                return ""

    def _extract_refusal_reason(self, text_content: str, doc_name: str) -> Optional[str]:
        """
        Extrait le motif de refus d'un document depuis le texte de la page.

        Sur ExamT3P, les motifs de refus sont typiquement affichés après le statut REFUSÉ
        sous forme de message ou dans une section commentaire.

        Motifs courants de refus par la CMA:
        - Photo floue / non conforme aux normes
        - Document illisible
        - Document expiré
        - Justificatif de domicile de plus de 6 mois
        - Permis de conduire non valide
        - Signature non manuscrite
        - etc.
        """
        # Patterns pour trouver le motif de refus après le nom du document
        refusal_patterns = [
            # Pattern: "Document REFUSÉ: raison du refus"
            rf"{re.escape(doc_name)}.*?REFUS[ÉE]?\s*[:\-]?\s*([^\n]{{10,200}})",
            # Pattern: "REFUSÉ" suivi d'un commentaire/motif
            rf"{re.escape(doc_name)}.*?REFUS[ÉE]?.*?\n\s*([A-Za-zÀ-ÿ][^\n]{{10,200}})",
            # Pattern: Commentaire CMA après le document
            rf"{re.escape(doc_name)}.*?REFUS[ÉE]?.*?(?:Commentaire|Motif|Raison)\s*[:\-]?\s*([^\n]{{5,200}})",
        ]

        for pattern in refusal_patterns:
            match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
            if match:
                motif = match.group(1).strip()
                # Nettoyer le motif (enlever caractères parasites)
                motif = re.sub(r'\s+', ' ', motif)
                # Filtrer les faux positifs (textes trop courts ou génériques)
                if len(motif) > 5 and not motif.upper().startswith('VALID'):
                    return motif

        # Motifs par défaut basés sur le type de document
        default_reasons = {
            "Pièce d'identité": "Document non conforme ou illisible - veuillez fournir une copie lisible recto/verso",
            "Photo d'identité": "Photo non conforme aux normes (fond non uni, visage non centré, ou qualité insuffisante)",
            "Signature": "Signature non manuscrite ou non conforme - une signature manuscrite scannée est requise",
            "Justificatif de domicile": "Document de plus de 6 mois ou non conforme - veuillez fournir un justificatif récent",
            "Permis de conduire": "Permis non valide ou illisible - veuillez fournir une copie lisible recto/verso",
        }

        return default_reasons.get(doc_name, "Motif non précisé par la CMA")

    def _get_solution_for_document(self, doc_name: str) -> str:
        """
        Retourne la solution/action à effectuer pour corriger un document refusé.

        Ces solutions sont personnalisées selon le type de document pour guider
        le candidat dans la correction.
        """
        solutions = {
            "Pièce d'identité": (
                "Scannez ou photographiez votre pièce d'identité (carte d'identité ou passeport) "
                "RECTO et VERSO sur un fond uni et bien éclairé. "
                "Assurez-vous que le document est lisible et non coupé."
            ),
            "Photo d'identité": (
                "Fournissez une photo d'identité récente aux normes officielles : "
                "fond uni clair, visage de face bien centré, expression neutre, "
                "sans lunettes si possible. Format recommandé : 35x45mm minimum."
            ),
            "Signature": (
                "Signez sur une feuille blanche avec un stylo noir, "
                "puis scannez ou photographiez votre signature. "
                "La signature doit être manuscrite (pas de signature électronique)."
            ),
            "Justificatif de domicile": (
                "Fournissez un justificatif de domicile de moins de 6 mois à votre nom : "
                "facture d'électricité, de gaz, d'eau, de téléphone fixe ou mobile, "
                "ou avis d'imposition. Le document doit être complet et lisible."
            ),
            "Permis de conduire": (
                "Scannez ou photographiez votre permis de conduire "
                "RECTO et VERSO sur un fond uni. "
                "Le permis doit être en cours de validité et lisible."
            ),
        }

        return solutions.get(doc_name, "Veuillez nous fournir un nouveau document conforme.")

    async def _extract_overview(self):
        """Extraction des données de la Vue d'ensemble."""
        # S'assurer qu'on est sur Vue d'ensemble
        clicked = await self._safe_click('a:has-text("Vue d\'ensemble")')
        if not clicked:
            # Peut-être déjà sur la page
            pass
        await asyncio.sleep(ACTION_DELAY)

        text_content = await self._safe_get_text()

        # === INFORMATIONS CANDIDAT ===
        match = re.search(r'Bienvenue\s+([A-Za-zÀ-ÿ\s]+)\s+-', text_content)
        if match:
            self.data['nom_candidat'] = match.group(1).strip()

        # Numéro de dossier
        match = re.search(r'N°\s*Dossier[:\s]*(\d+)', text_content)
        if match:
            self.data['num_dossier'] = match.group(1)
        else:
            match = re.search(r'(\d{8})\s*-\s*VTC', text_content)
            if match:
                self.data['num_dossier'] = match.group(1)

        # Type d'examen et département
        match = re.search(r'-\s*(VTC|Taxi|VMDTR)\s*-\s*(Complète|Réinscription|Mobilité)?\s*-?\s*(\d{2,3})?', text_content)
        if match:
            self.data['type_examen'] = match.group(1)
            if match.group(2):
                self.data['type_epreuve'] = match.group(2)
            if match.group(3):
                self.data['departement'] = match.group(3)

        # === STATUT DU DOSSIER ===
        # Liste des statuts possibles sur ExamT3P
        # IMPORTANT: Ces statuts sont mappés vers le champ Evalbox du CRM
        # Voir examt3p_crm_sync.py pour le mapping complet
        #
        # ATTENTION: La détection doit être PRÉCISE pour éviter les faux positifs
        # Par exemple "Valide" peut apparaître dans "Document VALIDÉ" alors que
        # le statut du dossier est "Incomplet"
        #
        # Priorité: Les statuts NÉGATIFS doivent être vérifiés EN PREMIER
        # car ils sont plus spécifiques et critiques
        statuts_par_priorite = [
            # Statuts négatifs/critiques en premier
            ('Incomplet', [r'statut[:\s]*incomplet', r'dossier[:\s]*incomplet', r'\bincomplet\b(?!\s*validé)']),
            ('Refusé', [r'statut[:\s]*refusé', r'dossier[:\s]*refusé', r'\brefusé\b']),
            ('En attente du paiement', [r'en attente du paiement', r'attente[:\s]*paiement']),
            ('En cours de composition', [r'en cours de composition']),
            # Statuts intermédiaires
            ('En attente d\'instruction des pièces', [r"en attente d'instruction", r'instruction des pièces']),
            ('En cours d\'instruction', [r"en cours d'instruction"]),
            # Statuts positifs (vérifiés en dernier pour éviter faux positifs)
            ('En attente de convocation', [r'en attente de convocation', r'attente[:\s]*convocation']),
            ('Dossier validé', [r'dossier validé', r'dossier[:\s]*validé']),
            ('Valide', [r'statut[:\s]*valide\b', r'(?<!document[:\s])(?<!pièce[:\s])valide\s*$']),
        ]

        # Chercher le statut avec patterns précis
        for statut, patterns in statuts_par_priorite:
            for pattern in patterns:
                if re.search(pattern, text_content, re.IGNORECASE):
                    self.data['statut_dossier'] = statut
                    break
            if 'statut_dossier' in self.data:
                break

        # Fallback: recherche simple si aucun pattern trouvé
        if 'statut_dossier' not in self.data:
            statuts_simples = [
                'Incomplet',  # Priorité aux négatifs
                'Refusé',
                'En attente du paiement',
                'En cours de composition',
                'En attente de convocation',
                'En attente d\'instruction des pièces',
                'En cours d\'instruction',
                'Dossier validé',
                'Valide',
            ]
            for statut in statuts_simples:
                # Éviter les faux positifs avec "VALIDÉ" des documents
                if statut.lower() == 'valide':
                    # Ne pas matcher "validé" seul (souvent documents)
                    # Chercher contexte "statut valide" ou "dossier valide"
                    if re.search(r'(statut|dossier)[:\s]*valide', text_content, re.IGNORECASE):
                        self.data['statut_dossier'] = statut
                        break
                elif statut.lower() in text_content.lower():
                    self.data['statut_dossier'] = statut
                    break

        # Date de réception du dossier
        match = re.search(r'Dossier reçu le\s+(\d{2}/\d{2}/\d{4})', text_content)
        if match:
            self.data['date_reception_dossier'] = match.group(1)

        # === PROCHAINE SESSION ===
        match = re.search(r'À partir du\s+(\d{1,2}\s+\w+\s+\d{4})', text_content)
        if match:
            self.data['date_examen'] = match.group(1)

        # Type d'épreuve de la session
        match = re.search(r'Examen\s+(vtc|taxi|vmdtr)\s*-\s*Épreuve\s+(écrite|pratique)', text_content, re.IGNORECASE)
        if match:
            self.data['epreuve_session'] = match.group(2).capitalize()

        # === PROGRESSION DU DOSSIER ===
        self.data['progression'] = {}

        # Convocation d'examen
        if re.search(r'Convocation d\'examen.*?EN ATTENTE', text_content, re.DOTALL | re.IGNORECASE):
            self.data['progression']['convocation'] = 'EN ATTENTE'
        elif re.search(r'Convocation d\'examen.*?VALIDÉ', text_content, re.DOTALL | re.IGNORECASE):
            self.data['progression']['convocation'] = 'VALIDÉ'

        # Documents justificatifs
        if re.search(r'Documents justificatifs.*?À VALIDER', text_content, re.DOTALL | re.IGNORECASE):
            self.data['progression']['documents'] = 'À VALIDER'
        elif re.search(r'Documents justificatifs.*?VALIDÉ', text_content, re.DOTALL | re.IGNORECASE):
            self.data['progression']['documents'] = 'VALIDÉ'
        elif re.search(r'Documents justificatifs.*?EN ATTENTE', text_content, re.DOTALL | re.IGNORECASE):
            self.data['progression']['documents'] = 'EN ATTENTE'

        # Paiement
        paiement_match = re.search(r'Paiement\s*\n\s*(\d{2}/\d{2}/\d{4})\s*\n\s*(\d+[.,]\d{2})\s*€\s*-\s*Paiement par\s*(\w+)\s*\n\s*(VALIDÉ|EN ATTENTE|REFUSÉ)', text_content, re.IGNORECASE)
        if paiement_match:
            self.data['paiement_cma'] = {
                'date': paiement_match.group(1),
                'montant': float(paiement_match.group(2).replace(',', '.')),
                'mode': paiement_match.group(3),
                'statut': paiement_match.group(4).upper()
            }
            self.data['progression']['paiement'] = paiement_match.group(4).upper()
        else:
            if re.search(r'Paiement.*?VALIDÉ', text_content, re.DOTALL | re.IGNORECASE):
                self.data['progression']['paiement'] = 'VALIDÉ'
                match = re.search(r'(\d+[.,]\d{2})\s*€', text_content)
                if match:
                    self.data['paiement_cma'] = {'montant': float(match.group(1).replace(',', '.')), 'statut': 'VALIDÉ'}

        # Informations personnelles
        if re.search(r'Informations personnelles.*?À VALIDER', text_content, re.DOTALL | re.IGNORECASE):
            self.data['progression']['infos_perso'] = 'À VALIDER'
        elif re.search(r'Informations personnelles.*?VALIDÉ', text_content, re.DOTALL | re.IGNORECASE):
            self.data['progression']['infos_perso'] = 'VALIDÉ'

        # Choix département/session
        match = re.search(r'Choix du département.*?(\d{2,3})\s*-\s*([A-Za-zÀ-ÿ\-\s]+).*?(À VALIDER|VALIDÉ)', text_content, re.DOTALL | re.IGNORECASE)
        if match:
            self.data['departement'] = match.group(1)
            self.data['region'] = match.group(2).strip()
            self.data['progression']['choix_session'] = match.group(3).upper()

        # Type d'examen sélectionné
        match = re.search(r'Type d\'examen sélectionné.*?(VTC|Taxi|VMDTR).*?(À VALIDER|VALIDÉ)', text_content, re.DOTALL | re.IGNORECASE)
        if match:
            self.data['progression']['type_examen'] = match.group(2).upper()

        # === ACTIONS REQUISES ===
        self.data['actions_requises'] = []

        if 'Reçu de paiement disponible' in text_content:
            self.data['actions_requises'].append({
                'type': 'recu_disponible',
                'description': 'Reçu de paiement disponible'
            })

        if 'Photo non conforme' in text_content or ('photo' in text_content.lower() and 'à valider' in text_content.lower()):
            self.data['actions_requises'].append({
                'type': 'photo_requise',
                'description': 'Photo d\'identité à mettre à jour'
            })

        # === HISTORIQUE DES ÉTAPES ===
        self.data['historique_etapes'] = []
        etapes = [
            'En cours de composition',
            'En attente du paiement',
            'En attente d\'instruction des pièces',
            'Incomplet',
            'Valide'
        ]
        for etape in etapes:
            if etape.lower() in text_content.lower():
                self.data['historique_etapes'].append(etape)

        # Convocation
        self.data['convocation'] = self.data['progression'].get('convocation', 'EN ATTENTE')

    async def _extract_examens(self):
        """Extraction des données de Mes Examens."""
        await self._safe_click('a:has-text("Mes Examens")')
        await asyncio.sleep(ACTION_DELAY)

        text_content = await self._safe_get_text()

        self.data['examens'] = {}

        # Date d'examen
        match = re.search(r'Date\s*:\s*(\d{2}/\d{2}/\d{4})', text_content)
        if match:
            self.data['examens']['date'] = match.group(1)

        # Lieu d'examen
        match = re.search(r'Lieu\s*:\s*([^\n]+)', text_content)
        if match:
            self.data['examens']['lieu'] = match.group(1).strip()

        # Statut convocation
        if 'Convocation disponible' in text_content or 'Télécharger la convocation' in text_content:
            self.data['examens']['convocation_disponible'] = True
            self.data['convocation'] = 'DISPONIBLE'
        else:
            self.data['examens']['convocation_disponible'] = False

        # Résultats si disponibles
        if 'Résultat' in text_content:
            match = re.search(r'Résultat\s*:\s*(Admis|Ajourné|En attente)', text_content, re.IGNORECASE)
            if match:
                self.data['examens']['resultat'] = match.group(1)

    async def _extract_documents(self):
        """Extraction du statut des documents."""
        await self._safe_click('a:has-text("Mes Documents")')
        await asyncio.sleep(ACTION_DELAY)

        text_content = await self._safe_get_text()

        # Liste des documents à extraire avec patterns améliorés
        # Patterns multiples pour gérer différents formats de page
        # AMÉLIORATION: Capture aussi la raison du refus quand disponible
        documents_config = [
            {'nom': "Pièce d'identité", 'patterns': [
                r"Pièce d'identité[^\n]*\n[^\n]*\n[^\n]*(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Pièce d'identité.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Carte.*?identité.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)"
            ]},
            {'nom': "Photo d'identité", 'patterns': [
                r"Photo d'identité[^\n]*\n[^\n]*\n[^\n]*(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Photo d'identité.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Photo.*?récente.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)"
            ]},
            {'nom': "Signature", 'patterns': [
                r"Signature[^\n]*\n[^\n]*\n[^\n]*(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Signature.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Signature.*?manuscrite.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)"
            ]},
            {'nom': "Justificatif de domicile", 'patterns': [
                r"Justificatif de domicile[^\n]*\n[^\n]*\n[^\n]*(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Justificatif de domicile.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"JDD.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)"
            ]},
            {'nom': "Permis de conduire", 'patterns': [
                r"Permis de conduire[^\n]*\n[^\n]*\n[^\n]*(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Permis de conduire.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)",
                r"Permis.*?en cours.*?(VALIDÉ|VALIDE|À VALIDER|A VALIDER|REFUSÉ|REFUSE)"
            ]},
        ]

        self.data['documents'] = []

        for doc_config in documents_config:
            doc_info = {'nom': doc_config['nom'], 'statut': 'INCONNU', 'motif_refus': None}

            # Essayer chaque pattern jusqu'à trouver un match
            for pattern in doc_config['patterns']:
                match = re.search(pattern, text_content, re.IGNORECASE | re.DOTALL)
                if match:
                    statut = match.group(1).upper()
                    # Normaliser les statuts
                    if statut in ['VALIDÉ', 'VALIDE']:
                        doc_info['statut'] = 'VALIDÉ'
                    elif statut in ['À VALIDER', 'A VALIDER']:
                        doc_info['statut'] = 'À VALIDER'
                    elif statut in ['REFUSÉ', 'REFUSE']:
                        doc_info['statut'] = 'REFUSÉ'
                        # Chercher le motif de refus (texte après REFUSÉ)
                        doc_info['motif_refus'] = self._extract_refusal_reason(
                            text_content, doc_config['nom']
                        )
                    break

            self.data['documents'].append(doc_info)

        # Documents facultatifs
        self.data['documents_facultatifs'] = []
        if 'Pièce d\'identité - Justificatif FACULTATIF' in text_content:
            self.data['documents_facultatifs'].append({'nom': "Pièce d'identité - Justificatif FACULTATIF", 'statut': 'OPTIONNEL'})
        if 'Permis de conduire - Justificatif FACULTATIF' in text_content:
            self.data['documents_facultatifs'].append({'nom': "Permis de conduire - Justificatif FACULTATIF", 'statut': 'OPTIONNEL'})

        # FALLBACK: Si le statut du dossier est "Valide", tous les documents sont validés
        # Un dossier ne peut pas être "Valide" si des documents sont manquants ou refusés
        statut_dossier = self.data.get('statut_dossier', '').lower()
        docs_inconnus = sum(1 for d in self.data['documents'] if d['statut'] == 'INCONNU')

        if statut_dossier == 'valide' and docs_inconnus > 0:
            # Le dossier est validé par la CMA, donc tous les documents sont forcément validés
            for doc in self.data['documents']:
                if doc['statut'] == 'INCONNU':
                    doc['statut'] = 'VALIDÉ'

        # Calculer le statut global
        statuts = [d['statut'] for d in self.data['documents']]
        if all(s == 'VALIDÉ' for s in statuts):
            self.data['statut_documents'] = 'VALIDÉ'
        elif any(s == 'REFUSÉ' for s in statuts):
            self.data['statut_documents'] = 'REFUSÉ'
        elif any(s == 'À VALIDER' for s in statuts):
            self.data['statut_documents'] = 'À VALIDER'
        elif any(s == 'INCONNU' for s in statuts):
            self.data['statut_documents'] = 'INCONNU'
        else:
            self.data['statut_documents'] = 'EN COURS'

        validés = sum(1 for s in statuts if s == 'VALIDÉ')
        self.data['documents_valides'] = f"{validés}/{len(statuts)}"

        # Identifier les documents en attente et les documents refusés
        self.data['documents_en_attente'] = []
        self.data['documents_refuses'] = []
        # Liste détaillée avec motifs de refus pour la réponse au candidat
        self.data['pieces_refusees_details'] = []

        for doc in self.data['documents']:
            if doc['statut'] == 'À VALIDER':
                # Document uploadé, en attente de validation CMA (pas d'action requise)
                self.data['documents_en_attente'].append(doc['nom'])
            elif doc['statut'] == 'REFUSÉ':
                # Document refusé, action requise du candidat
                self.data['documents_refuses'].append(doc['nom'])

                # Ajouter le détail avec motif de refus
                self.data['pieces_refusees_details'].append({
                    'nom': doc['nom'],
                    'motif': doc.get('motif_refus', 'Motif non précisé'),
                    'solution': self._get_solution_for_document(doc['nom'])
                })

                if 'document_problematique' not in self.data:
                    self.data['document_problematique'] = doc['nom']
                    self.data['document_problematique_statut'] = 'REFUSÉ'
                    self.data['document_problematique_motif'] = doc.get('motif_refus')

        # Indicateur si action requise du candidat
        self.data['action_candidat_requise'] = len(self.data['documents_refuses']) > 0

    async def _extract_compte(self):
        """Extraction des informations du compte."""
        await self._safe_click('a:has-text("Mon Compte")')
        await asyncio.sleep(ACTION_DELAY)

        text_content = await self._safe_get_text()

        self.data['compte'] = {}

        # Genre
        if 'Homme' in text_content:
            self.data['compte']['genre'] = 'Homme'
        elif 'Femme' in text_content:
            self.data['compte']['genre'] = 'Femme'

        # Prénom
        match = re.search(r'Prénom\(?s?\)?\s*\n\s*([A-Za-zÀ-ÿ\s\-]+)', text_content)
        if match:
            self.data['compte']['prenom'] = match.group(1).strip()

        # Nom
        match = re.search(r'Nom\s*\n\s*([A-Za-zÀ-ÿ\s\-]+)', text_content)
        if match:
            self.data['compte']['nom'] = match.group(1).strip()

        # Date de naissance
        match = re.search(r'Date de naissance\s*\n\s*(\d{2}/\d{2}/\d{4})', text_content)
        if match:
            self.data['compte']['date_naissance'] = match.group(1)

        # Lieu de naissance
        match = re.search(r'Lieu de naissance\s*\n\s*([A-Za-zÀ-ÿ\s\-]+)', text_content)
        if match:
            self.data['compte']['lieu_naissance'] = match.group(1).strip()

        # Adresse
        match = re.search(r'Adresse de domicile\s*\n\s*([^\n]+)', text_content)
        if match:
            self.data['compte']['adresse'] = match.group(1).strip()

        # Code postal et ville
        match = re.search(r'Code postal\s*\n\s*(\d{5})', text_content)
        if match:
            self.data['compte']['code_postal'] = match.group(1)

        match = re.search(r'Ville\s*\n\s*([A-Za-zÀ-ÿ\s\-]+)', text_content)
        if match:
            self.data['compte']['ville'] = match.group(1).strip()

        # Email
        match = re.search(r'Email\s*\n\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text_content)
        if match:
            self.data['compte']['email'] = match.group(1)

        # Téléphone
        match = re.search(r'Téléphone\s*\n\s*([0-9\s\+]+)', text_content)
        if match:
            self.data['compte']['telephone'] = match.group(1).strip()

    async def _extract_paiements(self):
        """Extraction de l'historique des paiements."""
        await self._safe_click('a:has-text("Mes Paiements")')
        await asyncio.sleep(ACTION_DELAY)

        text_content = await self._safe_get_text()

        self.data['historique_paiements'] = []

        # Chercher les lignes de paiement dans le tableau
        pattern = r'(\d{8})\s+(\d{2}/\d{2}/\d{4})\s+([^\n]+?)\s+(\d+[.,]\d{2})\s*€\s+(VALIDÉ|REFUSÉ|EN ATTENTE)'
        matches = re.findall(pattern, text_content, re.IGNORECASE)

        for match in matches:
            self.data['historique_paiements'].append({
                'num_dossier': match[0],
                'date': match[1],
                'description': match[2].strip(),
                'montant': float(match[3].replace(',', '.')),
                'statut': match[4].upper()
            })

        # Si pas de match, essayer d'extraire au moins le montant total
        if not self.data['historique_paiements']:
            match = re.search(r'(\d+[.,]\d{2})\s*€', text_content)
            if match:
                self.data['historique_paiements'].append({
                    'montant': float(match.group(1).replace(',', '.')),
                    'statut': 'VALIDÉ' if 'VALIDÉ' in text_content else 'INCONNU'
                })

    async def _extract_messages(self):
        """Extraction des messages avec la CMA."""
        await self._safe_click('a:has-text("Messages")')
        await asyncio.sleep(ACTION_DELAY)

        text_content = await self._safe_get_text()

        self.data['messages'] = {
            'nombre': 0,
            'liste': []
        }

        # Compter les nouveaux messages
        match = re.search(r'(\d+)\s*nouveau[sx]?', text_content, re.IGNORECASE)
        if match:
            self.data['messages']['nombre'] = int(match.group(1))

        # Extraire les messages si présents
        messages_pattern = r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})\s*\n\s*(CMA|Candidat)\s*\n\s*([^\n]+)'
        matches = re.findall(messages_pattern, text_content, re.IGNORECASE)

        for match in matches:
            self.data['messages']['liste'].append({
                'date': match[0],
                'expediteur': match[1],
                'contenu': match[2].strip()
            })

    async def _safe_logout(self):
        """Déconnexion sécurisée (non bloquante)."""
        try:
            await self._safe_click('a:has-text("Déconnexion")', timeout=5000)
        except:
            pass


def extract_exament3p_sync(identifiant: str, password: str, max_retries: int = MAX_RETRIES) -> Dict:
    """
    Fonction synchrone pour extraire les données ExamenT3P avec retry.

    Args:
        identifiant: Email du candidat
        password: Mot de passe ExamenT3P
        max_retries: Nombre maximum de tentatives

    Returns:
        Dictionnaire avec les données extraites
    """
    extractor = ExamenT3PPlaywright(identifiant, password, max_retries)
    return asyncio.run(extractor.extract_all())
