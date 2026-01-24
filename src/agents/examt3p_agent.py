"""
Agent pour extraire les données depuis exament3p.fr via Playwright.

Ce site n'ayant pas d'API, on utilise le scraping avec Playwright
pour récupérer les informations du compte candidat.
"""
import logging
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ExamT3PAgent(BaseAgent):
    """Agent pour scraper les données depuis exament3p.fr."""

    BASE_URL = "https://www.exament3p.fr"
    LOGIN_URL = f"{BASE_URL}/id/14"
    TIMEOUT = 30000  # 30 secondes

    def __init__(self, headless: bool = True):
        """
        Initialize ExamT3P agent.

        Args:
            headless: Run browser in headless mode (default: True)
        """
        super().__init__(
            name="ExamT3PAgent",
            system_prompt="Agent for scraping exament3p.fr candidate data"
        )
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    def _start_browser(self) -> None:
        """Démarre le navigateur Playwright."""
        if self.browser is None:
            logger.info("Starting Playwright browser...")
            playwright = sync_playwright().start()
            self.browser = playwright.chromium.launch(headless=self.headless)
            self.page = self.browser.new_page()
            logger.info("Browser started successfully")

    def _close_browser(self) -> None:
        """Ferme le navigateur."""
        if self.browser:
            logger.info("Closing browser...")
            self.browser.close()
            self.browser = None
            self.page = None

    def login(self, username: str, password: str) -> bool:
        """
        Se connecte à exament3p.fr.

        Args:
            username: IDENTIFIANT_EVALBOX
            password: MDP_EVALBOX

        Returns:
            True si connexion réussie, False sinon
        """
        try:
            self._start_browser()

            logger.info(f"Navigating to login page: {self.LOGIN_URL}")
            self.page.goto(self.LOGIN_URL, timeout=self.TIMEOUT)

            # TODO: Adapter les sélecteurs selon la vraie structure HTML
            logger.info("Filling login form...")

            # Exemple de sélecteurs (À ADAPTER) :
            # self.page.fill('input[name="username"]', username)
            # self.page.fill('input[name="password"]', password)
            # self.page.click('button[type="submit"]')

            # Attendre la redirection après login
            # self.page.wait_for_url("**/dashboard**", timeout=self.TIMEOUT)

            logger.info("Login successful")
            return True

        except PlaywrightTimeoutError as e:
            logger.error(f"Login timeout: {e}")
            return False
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def get_candidate_data(self, dossier_number: str) -> Dict[str, Any]:
        """
        Récupère toutes les données du candidat.

        Args:
            dossier_number: NUM_DOSSIER_EVALBOX

        Returns:
            Dict avec toutes les données extraites
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call login() first.")

        data = {
            "dossier_number": dossier_number,
            "convocations": self._get_convocations(),
            "resultats": self._get_resultats(),
            "statut_inscription": self._get_statut_inscription(),
            "documents": self._get_documents()
        }

        return data

    def _get_convocations(self) -> list:
        """Extrait les convocations d'examen."""
        # TODO: Implémenter selon la structure HTML
        logger.info("Extracting convocations...")

        try:
            # Exemple :
            # self.page.goto(f"{self.BASE_URL}/convocations")
            # convocations = self.page.query_selector_all('.convocation-item')
            # return [self._parse_convocation(conv) for conv in convocations]

            return []

        except Exception as e:
            logger.error(f"Failed to extract convocations: {e}")
            return []

    def _get_resultats(self) -> list:
        """Extrait les résultats d'examen."""
        # TODO: Implémenter selon la structure HTML
        logger.info("Extracting résultats...")

        try:
            # Exemple :
            # self.page.goto(f"{self.BASE_URL}/resultats")
            # resultats = self.page.query_selector_all('.resultat-item')
            # return [self._parse_resultat(res) for res in resultats]

            return []

        except Exception as e:
            logger.error(f"Failed to extract résultats: {e}")
            return []

    def _get_statut_inscription(self) -> Optional[str]:
        """Extrait le statut d'inscription."""
        # TODO: Implémenter selon la structure HTML
        logger.info("Extracting statut inscription...")

        try:
            # Exemple :
            # self.page.goto(f"{self.BASE_URL}/mon-dossier")
            # statut = self.page.text_content('.statut-inscription')
            # return statut

            return None

        except Exception as e:
            logger.error(f"Failed to extract statut: {e}")
            return None

    def _get_documents(self) -> list:
        """Extrait la liste des documents disponibles."""
        # TODO: Implémenter selon la structure HTML
        logger.info("Extracting documents...")

        try:
            # Exemple :
            # self.page.goto(f"{self.BASE_URL}/documents")
            # docs = self.page.query_selector_all('.document-item')
            # return [self._parse_document(doc) for doc in docs]

            return []

        except Exception as e:
            logger.error(f"Failed to extract documents: {e}")
            return []

    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process method requis par BaseAgent.

        Args:
            data: Dict contenant username, password, dossier_number

        Returns:
            Dict avec les données extraites
        """
        username = data.get("username")
        password = data.get("password")
        dossier_number = data.get("dossier_number")

        if not all([username, password, dossier_number]):
            return {
                "success": False,
                "error": "Missing credentials or dossier_number"
            }

        try:
            # Login
            if not self.login(username, password):
                return {
                    "success": False,
                    "error": "Login failed"
                }

            # Extract data
            candidate_data = self.get_candidate_data(dossier_number)

            return {
                "success": True,
                "data": candidate_data
            }

        except Exception as e:
            logger.error(f"ExamT3P agent error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

        finally:
            self._close_browser()

    def __enter__(self):
        """Context manager support."""
        self._start_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self._close_browser()
