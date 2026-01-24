"""
Script de test pour valider l'analyse de Fouad avec SEULEMENT 5 tickets.

Ce test rapide (1-2 minutes) permet de vérifier :
- La récupération du contenu complet des threads fonctionne
- Le filtrage des tickets de Fouad fonctionne
- L'extraction des questions/réponses fonctionne
- Le format JSON de sortie est correct

Résultat sauvegardé dans : fouad_tickets_test.json

Si ce test réussit, lancez analyze_fouad_tickets.py pour les 500 tickets complets.
"""
import logging
import json
import time
from datetime import datetime
from collections import Counter
import re
from dotenv import load_dotenv
from src.zoho_client import ZohoDeskClient
from config import settings

# Charger .env
load_dotenv()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# ID de Fouad Haddouchi
FOUAD_AGENT_ID = "198709000018519157"

# Fichier de sortie pour le test
OUTPUT_FILE = "fouad_tickets_test.json"


def ticket_has_fouad_response(threads):
    """Vérifie si Fouad a répondu dans les threads."""
    for thread in threads:
        author = thread.get("author", {})
        if author.get("id") == FOUAD_AGENT_ID:
            return True
    return False


def extract_content_from_thread(thread):
    """Extrait le contenu complet d'un thread (pas juste le summary)."""
    # Essayer d'abord 'content', sinon 'summary'
    content = thread.get("content", "")
    if not content:
        content = thread.get("summary", "")
    return content


def extract_fouad_responses(threads):
    """Extrait toutes les réponses de Fouad avec CONTENU COMPLET."""
    fouad_responses = []

    for thread in threads:
        author = thread.get("author", {})
        if author.get("id") == FOUAD_AGENT_ID and author.get("type") == "AGENT":
            fouad_responses.append({
                "content": extract_content_from_thread(thread),
                "created_time": thread.get("createdTime", ""),
                "response_time": thread.get("respondedIn", "N/A")
            })

    return fouad_responses


def extract_customer_questions(threads):
    """Extrait les questions/messages des clients avec CONTENU COMPLET."""
    customer_messages = []

    for thread in threads:
        author = thread.get("author", {})
        # Messages venant de END_USER ou direction "in"
        if author.get("type") == "END_USER" or thread.get("direction") == "in":
            customer_messages.append({
                "content": extract_content_from_thread(thread),
                "created_time": thread.get("createdTime", ""),
                "author_name": author.get("name", "Unknown")
            })

    return customer_messages


def test_fouad_analysis():
    """Test rapide avec 5 tickets seulement."""
    print("\n" + "=" * 80)
    print("TEST RAPIDE - ANALYSE DE 5 TICKETS DE FOUAD")
    print("VERSION AVEC CONTENU COMPLET")
    print("=" * 80)

    desk_client = ZohoDeskClient()

    try:
        # ID du département DOC
        doc_department_id = "198709000025523146"

        print(f"\n🔍 Récupération des tickets du département DOC...")

        # Récupérer les tickets fermés du département DOC
        url = f"{settings.zoho_desk_api_url}/tickets"
        params = {
            "orgId": settings.zoho_desk_org_id,
            "departmentId": doc_department_id,
            "status": "Closed",
            "limit": 100,  # Prendre 100 pour avoir assez de chances d'en trouver 5 de Fouad
            "from": 0
        }

        response = desk_client._make_request("GET", url, params=params)
        all_tickets = response.get("data", [])

        print(f"✅ {len(all_tickets)} tickets récupérés")
        print(f"\n🔎 Recherche de 5 tickets traités par Fouad...")

        fouad_tickets = []
        tickets_checked = 0

        for ticket in all_tickets:
            tickets_checked += 1
            ticket_id = ticket.get("id")

            print(f"   Analyse du ticket {tickets_checked}... ", end="", flush=True)

            # Récupérer les threads avec CONTENU COMPLET
            try:
                threads = desk_client.get_all_threads_with_full_content(ticket_id)
                time.sleep(0.3)  # Délai pour éviter le rate limiting
            except Exception as e:
                logger.warning(f"Erreur récupération threads pour ticket {ticket_id}: {e}")
                threads = []
                print("❌")
                continue

            # Vérifier si Fouad a répondu
            if ticket_has_fouad_response(threads):
                print("✅ Fouad trouvé!")

                # Extraire les informations
                ticket_data = {
                    "ticket_id": ticket_id,
                    "ticket_number": ticket.get("ticketNumber", ""),
                    "subject": ticket.get("subject", ""),
                    "description": ticket.get("description", ""),
                    "status": ticket.get("status", ""),
                    "priority": ticket.get("priority", ""),
                    "channel": ticket.get("channel", ""),
                    "created_time": ticket.get("createdTime", ""),
                    "closed_time": ticket.get("closedTime", ""),
                    "contact_email": ticket.get("email", ""),
                    "tags": ticket.get("tags", []),

                    # Extraire questions clients et réponses Fouad (CONTENU COMPLET)
                    "customer_questions": extract_customer_questions(threads),
                    "fouad_responses": extract_fouad_responses(threads),

                    # Métadonnées
                    "total_threads": len(threads),
                    "fouad_response_count": len(extract_fouad_responses(threads))
                }

                fouad_tickets.append(ticket_data)

                # Limiter à 5 tickets pour le test
                if len(fouad_tickets) >= 5:
                    print(f"\n✅ 5 tickets de Fouad trouvés sur {tickets_checked} tickets analysés")
                    break
            else:
                print("⏭️")

        if not fouad_tickets:
            print("\n⚠️  Aucun ticket traité par Fouad trouvé dans les 100 premiers tickets")
            return None

        # Afficher un aperçu
        print(f"\n📊 Aperçu des tickets trouvés :")
        for i, ticket in enumerate(fouad_tickets, 1):
            print(f"\n   {i}. Ticket #{ticket['ticket_number']}")
            print(f"      Sujet : {ticket['subject'][:60]}...")
            print(f"      Questions client : {len(ticket['customer_questions'])}")
            print(f"      Réponses Fouad : {len(ticket['fouad_responses'])}")

            # Vérifier si le contenu est complet (pas juste un summary)
            if ticket['fouad_responses']:
                first_response = ticket['fouad_responses'][0]['content']
                content_length = len(first_response)
                print(f"      Longueur 1ère réponse : {content_length} caractères", end="")
                if content_length > 500:
                    print(" ✅ (contenu complet)")
                else:
                    print(" ⚠️  (possiblement tronqué)")

        # Sauvegarder le résultat
        output = {
            "timestamp": datetime.now().isoformat(),
            "test_mode": True,
            "agent": {
                "name": "Fouad Haddouchi",
                "id": FOUAD_AGENT_ID,
                "email": "fouad@cab-formations.fr"
            },
            "department": "DOC",
            "department_id": doc_department_id,
            "total_tickets_checked": tickets_checked,
            "tickets_with_fouad_response": len(fouad_tickets),
            "tickets": fouad_tickets
        }

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Résultats du test sauvegardés dans : {OUTPUT_FILE}")

        # Validation
        print("\n" + "=" * 80)
        print("VALIDATION DU TEST")
        print("=" * 80)

        all_ok = True

        # Test 1: Au moins 5 tickets trouvés
        if len(fouad_tickets) >= 5:
            print("✅ Test 1: 5 tickets de Fouad trouvés")
        else:
            print(f"❌ Test 1: Seulement {len(fouad_tickets)} tickets trouvés (attendu: 5)")
            all_ok = False

        # Test 2: Contenu complet récupéré
        has_long_content = False
        for ticket in fouad_tickets:
            if ticket['fouad_responses']:
                if len(ticket['fouad_responses'][0]['content']) > 500:
                    has_long_content = True
                    break

        if has_long_content:
            print("✅ Test 2: Contenu complet récupéré (>500 caractères)")
        else:
            print("⚠️  Test 2: Contenu possiblement tronqué (tous <500 caractères)")

        # Test 3: Questions clients extraites
        has_questions = any(len(t['customer_questions']) > 0 for t in fouad_tickets)
        if has_questions:
            print("✅ Test 3: Questions clients extraites")
        else:
            print("❌ Test 3: Aucune question client trouvée")
            all_ok = False

        # Test 4: Réponses Fouad extraites
        has_responses = all(len(t['fouad_responses']) > 0 for t in fouad_tickets)
        if has_responses:
            print("✅ Test 4: Réponses de Fouad extraites pour tous les tickets")
        else:
            print("❌ Test 4: Certains tickets n'ont pas de réponses de Fouad")
            all_ok = False

        print("\n" + "=" * 80)
        if all_ok:
            print("✅ TOUS LES TESTS RÉUSSIS")
            print("\nVous pouvez maintenant lancer l'analyse complète :")
            print("   python analyze_fouad_tickets.py")
        else:
            print("⚠️  CERTAINS TESTS ONT ÉCHOUÉ")
            print("\nVérifiez les erreurs ci-dessus avant de lancer l'analyse complète")
        print("=" * 80)

        return output

    except Exception as e:
        print(f"\n❌ Erreur lors du test : {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        desk_client.close()


def main():
    """Point d'entrée principal."""
    result = test_fouad_analysis()

    if result:
        print("\n" + "=" * 80)
        print("PROCHAINES ÉTAPES")
        print("=" * 80)
        print("\n1. Examinez fouad_tickets_test.json pour vérifier les données")
        print("\n2. Si tout est OK, lancez l'analyse complète :")
        print("   python analyze_fouad_tickets.py")
        print("\n3. Commitez le fichier de test :")
        print("   git add fouad_tickets_test.json")
        print("   git commit -m 'Add Fouad analysis test results (5 tickets)'")
        print("   git push")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
