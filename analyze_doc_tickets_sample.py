"""
Script de test pour analyser la structure des tickets du département DOC.

Ce script récupère un échantillon de tickets pour comprendre :
- Comment identifier l'agent assigné (Fouad Haddouch)
- La structure des threads/réponses
- Les champs disponibles

Résultat sauvegardé dans : doc_tickets_sample.json
"""
import logging
import json
from datetime import datetime
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


def analyze_doc_tickets():
    """Récupère un échantillon de tickets DOC pour analyse."""
    print("\n" + "=" * 80)
    print("ANALYSE D'ÉCHANTILLON - TICKETS DÉPARTEMENT DOC")
    print("=" * 80)

    desk_client = ZohoDeskClient()

    try:
        # ID du département DOC
        doc_department_id = "198709000025523146"

        print(f"\n🔍 Récupération d'un échantillon de 10 tickets du département DOC...")

        # Récupérer 10 tickets du département DOC
        # Utiliser l'API directement avec le filtre departmentId
        url = f"{settings.zoho_desk_api_url}/tickets"
        params = {
            "orgId": settings.zoho_desk_org_id,
            "departmentId": doc_department_id,
            "status": "Closed",  # Tickets fermés pour avoir l'historique complet
            "limit": 10,
            "from": 0
        }
        response = desk_client._make_request("GET", url, params=params)

        tickets_data = response.get("data", [])

        if not tickets_data:
            print("\n⚠️  Aucun ticket trouvé dans le département DOC")
            return

        print(f"\n✅ {len(tickets_data)} tickets récupérés")

        # Pour chaque ticket, récupérer les détails complets et les threads
        detailed_tickets = []

        for i, ticket in enumerate(tickets_data, 1):
            ticket_id = ticket.get("id")
            print(f"\n📋 Analyse du ticket {i}/{len(tickets_data)} - ID: {ticket_id}")

            # Récupérer les threads/commentaires du ticket
            try:
                threads_url = f"{settings.zoho_desk_api_url}/tickets/{ticket_id}/threads"
                threads_response = desk_client._make_request(
                    "GET",
                    threads_url,
                    params={"orgId": settings.zoho_desk_org_id}
                )
                threads = threads_response.get("data", [])
                print(f"   - {len(threads)} threads trouvés")
            except Exception as e:
                logger.warning(f"Erreur récupération threads pour ticket {ticket_id}: {e}")
                threads = []

            # Construire l'objet complet
            detailed_ticket = {
                "ticket_id": ticket_id,
                "subject": ticket.get("subject", ""),
                "description": ticket.get("description", ""),
                "status": ticket.get("status", ""),
                "priority": ticket.get("priority", ""),
                "channel": ticket.get("channel", ""),
                "created_time": ticket.get("createdTime", ""),
                "closed_time": ticket.get("closedTime", ""),

                # Informations sur l'agent/assigné
                "assignee": ticket.get("assignee", {}),
                "assignee_id": ticket.get("assigneeId", ""),
                "owner": ticket.get("owner", {}),
                "team": ticket.get("team", {}),

                # Contact
                "contact": ticket.get("contact", {}),
                "email": ticket.get("email", ""),

                # Metadata
                "department_id": ticket.get("departmentId", ""),
                "tags": ticket.get("tags", []),
                "custom_fields": ticket.get("customFields", {}),

                # Threads complets
                "threads": threads,

                # Données brutes pour analyse
                "raw_ticket_fields": list(ticket.keys())
            }

            detailed_tickets.append(detailed_ticket)

        # Analyser les patterns
        analysis = analyze_patterns(detailed_tickets)

        # Sauvegarder le résultat
        output = {
            "timestamp": datetime.now().isoformat(),
            "department": "DOC",
            "department_id": doc_department_id,
            "sample_size": len(detailed_tickets),
            "tickets": detailed_tickets,
            "analysis": analysis
        }

        output_file = "doc_tickets_sample.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Résultats sauvegardés dans : {output_file}")

        # Afficher un résumé
        print("\n" + "=" * 80)
        print("RÉSUMÉ DE L'ANALYSE")
        print("=" * 80)
        print(f"\n✅ {len(detailed_tickets)} tickets analysés")
        print(f"\n🔑 Champs disponibles pour identifier l'agent :")
        for field in analysis["assignee_identification_fields"]:
            print(f"   - {field}")

        print(f"\n👥 Agents uniques trouvés :")
        for agent_info in analysis["unique_agents"][:5]:  # Top 5
            print(f"   - {agent_info}")

        return output

    except Exception as e:
        print(f"\n❌ Erreur lors de l'analyse : {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        desk_client.close()


def analyze_patterns(tickets):
    """Analyse les patterns dans les tickets."""
    analysis = {
        "assignee_identification_fields": set(),
        "unique_agents": set(),
        "thread_authors": set(),
        "statuses": set(),
        "priorities": set()
    }

    for ticket in tickets:
        # Identifier tous les champs liés à l'assigné
        if ticket.get("assignee"):
            assignee = ticket["assignee"]
            if isinstance(assignee, dict):
                # Ajouter le nom si présent
                if "name" in assignee:
                    analysis["unique_agents"].add(assignee["name"])
                # Lister les clés
                for key in assignee.keys():
                    analysis["assignee_identification_fields"].add(f"assignee.{key}")

        if ticket.get("assignee_id"):
            analysis["assignee_identification_fields"].add("assignee_id")

        if ticket.get("owner"):
            owner = ticket["owner"]
            if isinstance(owner, dict) and "name" in owner:
                analysis["unique_agents"].add(owner["name"])
                for key in owner.keys():
                    analysis["assignee_identification_fields"].add(f"owner.{key}")

        # Analyser les threads pour voir qui répond
        for thread in ticket.get("threads", []):
            if isinstance(thread, dict):
                author = thread.get("author", {})
                if isinstance(author, dict) and "name" in author:
                    analysis["thread_authors"].add(author["name"])

        # Autres stats
        if ticket.get("status"):
            analysis["statuses"].add(ticket["status"])
        if ticket.get("priority"):
            analysis["priorities"].add(ticket["priority"])

    # Convertir les sets en listes pour JSON
    return {
        "assignee_identification_fields": sorted(list(analysis["assignee_identification_fields"])),
        "unique_agents": sorted(list(analysis["unique_agents"])),
        "thread_authors": sorted(list(analysis["thread_authors"])),
        "statuses": sorted(list(analysis["statuses"])),
        "priorities": sorted(list(analysis["priorities"]))
    }


def main():
    """Point d'entrée principal."""
    result = analyze_doc_tickets()

    if result:
        print("\n" + "=" * 80)
        print("PROCHAINES ÉTAPES")
        print("=" * 80)
        print("\n1. Commitez le fichier JSON :")
        print("   git add doc_tickets_sample.json")
        print("   git commit -m 'Add DOC tickets sample for analysis'")
        print("   git push")
        print("\n2. Je vais analyser la structure pour identifier comment filtrer par Fouad")
        print("\n3. Je créerai ensuite le script complet pour récupérer tous les tickets")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
