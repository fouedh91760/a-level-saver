#!/usr/bin/env python3
"""
Script minimaliste pour tester la connexion Playwright vers ExamT3P.

Usage:
    python test_connexion_simple.py
"""
import asyncio
import sys

async def test_connexion():
    """Test de connexion simple sans login."""
    print("=" * 60)
    print("TEST CONNEXION PLAYWRIGHT -> EXAMT3P")
    print("=" * 60)

    try:
        from playwright.async_api import async_playwright
        print("[OK] Module playwright importé")
    except ImportError as e:
        print(f"[ERREUR] Playwright non installé: {e}")
        print("         Installez avec: pip install playwright && playwright install chromium")
        return False

    print("\n[INFO] Lancement du navigateur (mode visible)...")

    try:
        async with async_playwright() as p:
            # Mode visible pour debug
            browser = await p.chromium.launch(
                headless=False,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            print("[OK] Navigateur lancé")

            page = await browser.new_page()
            print("[OK] Page créée")

            print("\n[INFO] Connexion à https://www.exament3p.fr ...")

            try:
                await page.goto("https://www.exament3p.fr", timeout=30000)
                print(f"[OK] Page chargée!")
                print(f"     URL: {page.url}")
                print(f"     Titre: {await page.title()}")

                # Attendre 5 secondes pour voir la page
                print("\n[INFO] Attente 5 secondes (vérifiez la fenêtre du navigateur)...")
                await asyncio.sleep(5)

                print("\n[SUCCES] Connexion réussie!")
                result = True

            except Exception as e:
                print(f"\n[ERREUR] Échec de connexion: {e}")
                print("\n[DEBUG] Type d'erreur:", type(e).__name__)
                result = False

            await browser.close()
            print("[OK] Navigateur fermé")

            return result

    except Exception as e:
        print(f"\n[ERREUR] Impossible de lancer le navigateur: {e}")
        print("\n[DEBUG] Vérifiez que Chromium est installé:")
        print("         playwright install chromium")
        return False


def main():
    print("\nDémarrage du test...\n")

    success = asyncio.run(test_connexion())

    print("\n" + "=" * 60)
    if success:
        print("RESULTAT: SUCCES - La connexion fonctionne")
    else:
        print("RESULTAT: ECHEC - Problème de connexion")
        print("\nCauses possibles:")
        print("  1. Proxy/VPN actif qui bloque")
        print("  2. Antivirus/Firewall qui bloque Playwright")
        print("  3. Chromium non installé (playwright install chromium)")
        print("  4. Problème réseau temporaire")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
