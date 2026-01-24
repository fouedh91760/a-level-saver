"""
Script pour analyser les tickets traités par Fouad Haddouchi dans le département DOC.

Ce script :
1. Récupère TOUS les tickets du département DOC (avec pagination)
2. Pour chaque ticket, récupère les threads complets
3. Filtre les tickets où Fouad a répondu
4. Limite à 500 tickets maximum
5. Extrait les questions clients et réponses de Fouad
6. Génère une analyse détaillée avec patterns et recommandations

Résultat sauvegardé dans : fouad_tickets_analysis.json
"""
import logging
import json
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


def ticket_has_fouad_response(threads):
    """Vérifie si Fouad a répondu dans les threads."""
    for thread in threads:
        author = thread.get("author", {})
        if author.get("id") == FOUAD_AGENT_ID:
            return True
    return False


def extract_fouad_responses(threads):
    """Extrait toutes les réponses de Fouad dans les threads."""
    fouad_responses = []

    for thread in threads:
        author = thread.get("author", {})
        if author.get("id") == FOUAD_AGENT_ID and author.get("type") == "AGENT":
            fouad_responses.append({
                "content": thread.get("summary", ""),
                "created_time": thread.get("createdTime", ""),
                "response_time": thread.get("respondedIn", "N/A")
            })

    return fouad_responses


def extract_customer_questions(threads):
    """Extrait les questions/messages des clients."""
    customer_messages = []

    for thread in threads:
        author = thread.get("author", {})
        # Messages venant de END_USER ou direction "in"
        if author.get("type") == "END_USER" or thread.get("direction") == "in":
            customer_messages.append({
                "content": thread.get("summary", ""),
                "created_time": thread.get("createdTime", ""),
                "author_name": author.get("name", "Unknown")
            })

    return customer_messages


def analyze_fouad_tickets():
    """Récupère et analyse les tickets traités par Fouad."""
    print("\n" + "=" * 80)
    print("ANALYSE DES TICKETS TRAITÉS PAR FOUAD HADDOUCHI")
    print("=" * 80)

    desk_client = ZohoDeskClient()

    try:
        # ID du département DOC
        doc_department_id = "198709000025523146"

        print(f"\n🔍 Récupération de TOUS les tickets du département DOC...")
        print("   (Cela peut prendre plusieurs minutes selon le volume)")

        # Récupérer TOUS les tickets du département DOC avec pagination
        url = f"{settings.zoho_desk_api_url}/tickets"
        base_params = {
            "orgId": settings.zoho_desk_org_id,
            "departmentId": doc_department_id,
            "status": "Closed"  # Tickets fermés pour avoir l'historique complet
        }

        # Utiliser la pagination automatique
        all_tickets = desk_client._get_all_pages(url, base_params, limit_per_page=100)

        print(f"\n✅ {len(all_tickets)} tickets totaux récupérés")
        print(f"\n🔎 Filtrage des tickets traités par Fouad Haddouchi...")

        # Filtrer les tickets où Fouad a répondu
        fouad_tickets = []
        tickets_checked = 0
        tickets_with_fouad = 0

        for ticket in all_tickets:
            tickets_checked += 1

            if tickets_checked % 50 == 0:
                print(f"   Analysé {tickets_checked}/{len(all_tickets)} tickets - Trouvés avec Fouad : {tickets_with_fouad}")

            ticket_id = ticket.get("id")

            # Récupérer les threads du ticket
            try:
                threads_url = f"{settings.zoho_desk_api_url}/tickets/{ticket_id}/threads"
                threads_response = desk_client._make_request(
                    "GET",
                    threads_url,
                    params={"orgId": settings.zoho_desk_org_id}
                )
                threads = threads_response.get("data", [])
            except Exception as e:
                logger.warning(f"Erreur récupération threads pour ticket {ticket_id}: {e}")
                threads = []

            # Vérifier si Fouad a répondu
            if ticket_has_fouad_response(threads):
                tickets_with_fouad += 1

                # Extraire les informations pertinentes
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

                    # Extraire questions clients et réponses Fouad
                    "customer_questions": extract_customer_questions(threads),
                    "fouad_responses": extract_fouad_responses(threads),

                    # Métadonnées
                    "total_threads": len(threads),
                    "fouad_response_count": len(extract_fouad_responses(threads))
                }

                fouad_tickets.append(ticket_data)

                # Limiter à 500 tickets
                if len(fouad_tickets) >= 500:
                    print(f"\n✅ Limite de 500 tickets atteinte")
                    break

        print(f"\n✅ {len(fouad_tickets)} tickets traités par Fouad trouvés")

        if not fouad_tickets:
            print("\n⚠️  Aucun ticket traité par Fouad trouvé")
            return None

        # Générer l'analyse
        print(f"\n📊 Génération de l'analyse...")
        analysis = generate_analysis(fouad_tickets)

        # Sauvegarder le résultat
        output = {
            "timestamp": datetime.now().isoformat(),
            "agent": {
                "name": "Fouad Haddouchi",
                "id": FOUAD_AGENT_ID,
                "email": "fouad@cab-formations.fr"
            },
            "department": "DOC",
            "department_id": doc_department_id,
            "total_tickets_checked": tickets_checked,
            "tickets_with_fouad_response": len(fouad_tickets),
            "tickets": fouad_tickets,
            "analysis": analysis
        }

        output_file = "fouad_tickets_analysis.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Résultats sauvegardés dans : {output_file}")

        # Afficher un résumé
        display_summary(output)

        return output

    except Exception as e:
        print(f"\n❌ Erreur lors de l'analyse : {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        desk_client.close()


def generate_analysis(tickets):
    """Génère une analyse détaillée des tickets."""

    # Mots-clés dans les sujets
    subject_words = []
    for ticket in tickets:
        subject = ticket.get("subject", "").lower()
        # Extraire les mots de plus de 3 caractères
        words = re.findall(r'\b\w{4,}\b', subject)
        subject_words.extend(words)

    subject_word_counts = Counter(subject_words)

    # Mots-clés dans les réponses de Fouad
    fouad_words = []
    for ticket in tickets:
        for response in ticket.get("fouad_responses", []):
            content = response.get("content", "").lower()
            words = re.findall(r'\b\w{4,}\b', content)
            fouad_words.extend(words)

    fouad_word_counts = Counter(fouad_words)

    # Canaux de communication
    channels = Counter(ticket.get("channel", "Unknown") for ticket in tickets)

    # Tags utilisés
    all_tags = []
    for ticket in tickets:
        all_tags.extend(ticket.get("tags", []))
    tag_counts = Counter(all_tags)

    # Temps de réponse moyen (si disponible)
    response_times = []
    for ticket in tickets:
        for response in ticket.get("fouad_responses", []):
            rt = response.get("response_time", "")
            if rt and rt != "N/A":
                response_times.append(rt)

    return {
        "total_tickets_analyzed": len(tickets),
        "total_fouad_responses": sum(ticket.get("fouad_response_count", 0) for ticket in tickets),

        "top_subject_keywords": dict(subject_word_counts.most_common(30)),
        "top_fouad_keywords": dict(fouad_word_counts.most_common(30)),

        "channels": dict(channels),
        "top_tags": dict(tag_counts.most_common(20)),

        "avg_responses_per_ticket": round(
            sum(ticket.get("fouad_response_count", 0) for ticket in tickets) / len(tickets), 2
        ) if tickets else 0,

        "sample_response_times": response_times[:20]  # Échantillon
    }


def display_summary(output):
    """Affiche un résumé de l'analyse."""
    print("\n" + "=" * 80)
    print("RÉSUMÉ DE L'ANALYSE")
    print("=" * 80)

    analysis = output.get("analysis", {})

    print(f"\n📊 Statistiques globales :")
    print(f"   - Tickets vérifiés : {output.get('total_tickets_checked', 0)}")
    print(f"   - Tickets traités par Fouad : {output.get('tickets_with_fouad_response', 0)}")
    print(f"   - Total réponses de Fouad : {analysis.get('total_fouad_responses', 0)}")
    print(f"   - Moyenne réponses/ticket : {analysis.get('avg_responses_per_ticket', 0)}")

    print(f"\n🔑 Top 10 mots-clés dans les sujets :")
    top_subjects = list(analysis.get("top_subject_keywords", {}).items())[:10]
    for word, count in top_subjects:
        print(f"   - {word}: {count}")

    print(f"\n💬 Top 10 mots-clés dans les réponses de Fouad :")
    top_responses = list(analysis.get("top_fouad_keywords", {}).items())[:10]
    for word, count in top_responses:
        print(f"   - {word}: {count}")

    print(f"\n📞 Canaux de communication :")
    for channel, count in analysis.get("channels", {}).items():
        print(f"   - {channel}: {count}")


def main():
    """Point d'entrée principal."""
    result = analyze_fouad_tickets()

    if result:
        print("\n" + "=" * 80)
        print("PROCHAINES ÉTAPES")
        print("=" * 80)
        print("\n1. Commitez le fichier JSON :")
        print("   git add fouad_tickets_analysis.json")
        print("   git commit -m 'Add Fouad tickets analysis (500 tickets)'")
        print("   git push")
        print("\n2. Je vais analyser les patterns pour configurer business_rules.py")
        print("\n3. Nous pourrons ensuite automatiser le routing et le deal linking")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
