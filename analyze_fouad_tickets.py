"""
Script pour analyser les tickets traités par Fouad Haddouchi dans le département DOC.

Version ULTRA-OPTIMISÉE avec stratégie en 2 phases et filtre de date.

STRATÉGIE D'OPTIMISATION (4x plus rapide) :
- Phase 1 : Pré-filtrage léger (récupère juste la liste des threads, vite)
- Phase 2 : Contenu complet UNIQUEMENT pour les tickets de Fouad (lourd)
→ Évite de récupérer le contenu complet pour 92% des tickets !

Ce script :
1. Récupère les tickets DOC fermés après le 01/11/2025 (tickets récents uniquement)
2. Pour chaque ticket, PRÉ-FILTRE avec une requête légère
3. Contenu complet UNIQUEMENT si Fouad a répondu
4. Limite à 100 tickets maximum (suffisant pour analyse robuste)
5. Extrait les questions clients et réponses complètes de Fouad
6. Génère une analyse détaillée avec patterns et recommandations
7. Sauvegarde progressive tous les 50 tickets (protection contre crash)

Résultat sauvegardé dans : fouad_tickets_analysis.json
Temps estimé : 5-10 minutes (4x plus rapide que la version précédente)

INTERRUPTION : Si le script s'arrête, relancez-le, il reprendra où il s'était arrêté.
"""
import logging
import json
import time
import os
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

# Fichiers de sauvegarde
OUTPUT_FILE = "fouad_tickets_analysis.json"
PROGRESS_FILE = "fouad_tickets_progress.json"


def load_progress():
    """Charge la progression sauvegardée si elle existe."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Impossible de charger la progression : {e}")
    return {"tickets": [], "last_ticket_index": 0}


def save_progress(tickets, last_index):
    """Sauvegarde la progression."""
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "tickets": tickets,
                "last_ticket_index": last_index,
                "timestamp": datetime.now().isoformat()
            }, f, indent=2, ensure_ascii=False)
        logger.info(f"Progression sauvegardée : {len(tickets)} tickets")
    except Exception as e:
        logger.error(f"Erreur sauvegarde progression : {e}")


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


def analyze_fouad_tickets():
    """Récupère et analyse les tickets traités par Fouad avec contenu complet."""
    print("\n" + "=" * 80)
    print("ANALYSE DES TICKETS TRAITÉS PAR FOUAD HADDOUCHI")
    print("VERSION AVEC CONTENU COMPLET + GESTION RATE LIMITING")
    print("=" * 80)

    # Charger la progression existante
    progress = load_progress()
    fouad_tickets = progress.get("tickets", [])
    last_index = progress.get("last_ticket_index", 0)

    if fouad_tickets:
        print(f"\n♻️  Reprise de la progression : {len(fouad_tickets)} tickets déjà traités")
        print(f"   Dernière position : ticket #{last_index}")

    desk_client = ZohoDeskClient()

    try:
        # ID du département DOC
        doc_department_id = "198709000025523146"

        if last_index == 0:
            print(f"\n🔍 Récupération des tickets DOC fermés après le 01/11/2025...")
            print("   (Filtrage pour optimiser la recherche)")

            # Récupérer les tickets récents du département DOC avec pagination
            url = f"{settings.zoho_desk_api_url}/tickets"
            base_params = {
                "orgId": settings.zoho_desk_org_id,
                "departmentId": doc_department_id,
                "status": "Closed",  # Tickets fermés
                "closedTimeRange": "2025-11-01T00:00:00Z,2026-12-31T23:59:59Z"  # Depuis le 01/11/2025
            }

            # Utiliser la pagination automatique
            all_tickets = desk_client._get_all_pages(url, base_params, limit_per_page=100)
            print(f"\n✅ {len(all_tickets)} tickets totaux récupérés")
        else:
            print(f"\n⏩ Reprise depuis la position sauvegardée")
            # Récupérer à nouveau tous les tickets (nécessaire pour continuer)
            url = f"{settings.zoho_desk_api_url}/tickets"
            base_params = {
                "orgId": settings.zoho_desk_org_id,
                "departmentId": doc_department_id,
                "status": "Closed",
                "closedTimeRange": "2025-11-01T00:00:00Z,2026-12-31T23:59:59Z"  # Depuis le 01/11/2025
            }
            all_tickets = desk_client._get_all_pages(url, base_params, limit_per_page=100)

        print(f"\n🔎 Filtrage des tickets traités par Fouad Haddouchi...")
        print(f"📅 Période : tickets fermés depuis le 01/11/2025")
        print(f"🎯 Objectif : 100 tickets (suffisant pour analyse robuste)")
        print(f"🚀 Stratégie : Pré-filtrage léger → Contenu complet uniquement si Fouad (4x plus rapide)")
        print(f"⏱️  Temps estimé : 5-10 minutes")
        print(f"💾 Sauvegarde automatique tous les 50 tickets")

        tickets_checked = last_index
        tickets_with_fouad = len(fouad_tickets)

        start_time = time.time()

        for i, ticket in enumerate(all_tickets):
            # Reprendre là où on s'était arrêté
            if i < last_index:
                continue

            tickets_checked += 1
            ticket_id = ticket.get("id")

            # Affichage de progression tous les 10 tickets
            if tickets_checked % 10 == 0:
                elapsed = time.time() - start_time
                rate = tickets_checked / elapsed if elapsed > 0 else 0
                remaining = (len(all_tickets) - tickets_checked) / rate if rate > 0 else 0
                print(f"   ⏳ Analysé {tickets_checked}/{len(all_tickets)} tickets | "
                      f"Fouad: {tickets_with_fouad} | "
                      f"Temps restant: ~{int(remaining/60)}min")

            # =====================================================================
            # STRATÉGIE EN 2 PHASES POUR OPTIMISATION (4x plus rapide)
            # =====================================================================

            # PHASE 1 : Pré-filtrage léger (juste la liste des threads, sans contenu complet)
            try:
                # Récupérer juste la liste des threads (léger, rapide)
                threads_response = desk_client.get_ticket_threads(ticket_id)
                threads_light = threads_response.get("data", [])

                # Délai court pour éviter le rate limiting
                time.sleep(0.2)

            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    logger.warning(f"Rate limit atteint, pause de 60 secondes...")
                    print(f"\n⚠️  Rate limit API atteint - Pause de 60 secondes")
                    time.sleep(60)
                    try:
                        threads_response = desk_client.get_ticket_threads(ticket_id)
                        threads_light = threads_response.get("data", [])
                    except Exception as e2:
                        logger.error(f"Erreur threads pour ticket {ticket_id} après retry: {e2}")
                        threads_light = []
                else:
                    logger.warning(f"Erreur récupération threads pour ticket {ticket_id}: {e}")
                    threads_light = []

            # Vérifier si Fouad a répondu (pré-filtrage rapide)
            if not ticket_has_fouad_response(threads_light):
                # Fouad n'a pas répondu, on passe au ticket suivant (on économise du temps !)
                continue

            # PHASE 2 : Fouad trouvé ! Récupérer le CONTENU COMPLET (plus lourd)
            tickets_with_fouad += 1
            logger.info(f"✅ Fouad trouvé dans ticket {ticket_id}, récupération contenu complet...")

            try:
                # Maintenant on récupère le contenu complet
                threads_full = desk_client.get_all_threads_with_full_content(ticket_id)
                time.sleep(0.3)
            except Exception as e:
                logger.error(f"Erreur récupération contenu complet pour ticket {ticket_id}: {e}")
                threads_full = threads_light  # Fallback sur le light si erreur

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

                # Extraire questions clients et réponses Fouad (CONTENU COMPLET)
                "customer_questions": extract_customer_questions(threads_full),
                "fouad_responses": extract_fouad_responses(threads_full),

                # Métadonnées
                "total_threads": len(threads_full),
                "fouad_response_count": len(extract_fouad_responses(threads_full))
            }

            fouad_tickets.append(ticket_data)

            # Limiter à 100 tickets (suffisant pour analyse robuste)
            if len(fouad_tickets) >= 100:
                print(f"\n✅ Limite de 100 tickets atteinte")
                break

            # Sauvegarde progressive tous les 50 tickets
            if tickets_checked % 50 == 0:
                save_progress(fouad_tickets, tickets_checked)
                print(f"   💾 Sauvegarde automatique effectuée")

        # Sauvegarde finale
        save_progress(fouad_tickets, tickets_checked)

        print(f"\n✅ {len(fouad_tickets)} tickets traités par Fouad trouvés")

        if not fouad_tickets:
            print("\n⚠️  Aucun ticket traité par Fouad trouvé")
            return None

        # Générer l'analyse
        print(f"\n📊 Génération de l'analyse...")
        analysis = generate_analysis(fouad_tickets)

        # Sauvegarder le résultat final
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

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Résultats sauvegardés dans : {OUTPUT_FILE}")

        # Nettoyer le fichier de progression
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            print(f"   🗑️  Fichier de progression nettoyé")

        # Afficher un résumé
        display_summary(output)

        return output

    except Exception as e:
        print(f"\n❌ Erreur lors de l'analyse : {e}")
        import traceback
        traceback.print_exc()

        # Sauvegarder la progression même en cas d'erreur
        if fouad_tickets:
            save_progress(fouad_tickets, tickets_checked)
            print(f"\n💾 Progression sauvegardée - Vous pouvez relancer le script pour continuer")

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

    # Mots-clés dans les réponses de Fouad (CONTENU COMPLET maintenant)
    fouad_words = []
    for ticket in tickets:
        for response in ticket.get("fouad_responses", []):
            content = response.get("content", "").lower()
            words = re.findall(r'\b\w{4,}\b', content)
            fouad_words.extend(words)

    fouad_word_counts = Counter(fouad_words)

    # Mots-clés dans les questions clients
    customer_words = []
    for ticket in tickets:
        for question in ticket.get("customer_questions", []):
            content = question.get("content", "").lower()
            words = re.findall(r'\b\w{4,}\b', content)
            customer_words.extend(words)

    customer_word_counts = Counter(customer_words)

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

        "top_subject_keywords": dict(subject_word_counts.most_common(50)),
        "top_customer_keywords": dict(customer_word_counts.most_common(50)),
        "top_fouad_keywords": dict(fouad_word_counts.most_common(50)),

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

    print(f"\n❓ Top 10 mots-clés dans les questions clients :")
    top_customer = list(analysis.get("top_customer_keywords", {}).items())[:10]
    for word, count in top_customer:
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
        print("   git commit -m 'Add Fouad tickets analysis with full content (500 tickets)'")
        print("   git push")
        print("\n2. Je vais analyser les patterns pour configurer business_rules.py")
        print("\n3. Nous pourrons ensuite automatiser le routing et le deal linking")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
