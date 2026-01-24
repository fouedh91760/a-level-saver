"""
Script pour générer des recommandations de business rules basées sur l'analyse de Fouad.

Ce script lit fouad_tickets_analysis.json et génère :
1. Recommandations pour les mots-clés de routing par département
2. Patterns de questions clients les plus fréquents
3. Patterns de réponses de Fouad
4. Suggestions pour les règles de deal linking

Résultat sauvegardé dans : business_rules_recommendations.json
"""
import json
import logging
from datetime import datetime
from collections import Counter
from typing import Dict, Any, List, Set
import re

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def load_analysis() -> Dict[str, Any]:
    """Charge l'analyse de Fouad."""
    try:
        with open("fouad_tickets_analysis.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("\n❌ Erreur : fouad_tickets_analysis.json n'existe pas")
        print("   Vous devez d'abord exécuter : python analyze_fouad_tickets.py")
        exit(1)
    except Exception as e:
        print(f"\n❌ Erreur lors de la lecture du fichier : {e}")
        exit(1)


def extract_keywords_from_text(text: str, min_length: int = 4) -> List[str]:
    """Extrait les mots-clés d'un texte."""
    # Convertir en minuscules et extraire les mots
    text_lower = text.lower()
    words = re.findall(r'\b\w{' + str(min_length) + r',}\b', text_lower)
    return words


def analyze_common_patterns(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyse les patterns communs dans les tickets de Fouad."""

    tickets = analysis_data.get("tickets", [])
    analysis = analysis_data.get("analysis", {})

    print(f"\n🔍 Analyse de {len(tickets)} tickets traités par Fouad...")

    # 1. Mots-clés dans les sujets (déjà dans l'analyse)
    top_subject_keywords = analysis.get("top_subject_keywords", {})

    # 2. Mots-clés dans les questions clients (déjà dans l'analyse)
    top_customer_keywords = analysis.get("top_customer_keywords", {})

    # 3. Mots-clés dans les réponses de Fouad (déjà dans l'analyse)
    top_fouad_keywords = analysis.get("top_fouad_keywords", {})

    # 4. Analyser les sujets de tickets pour identifier les catégories
    subject_categories = categorize_tickets_by_subject(tickets)

    # 5. Analyser les questions types
    common_question_patterns = identify_question_patterns(tickets)

    # 6. Analyser les réponses types de Fouad
    common_response_patterns = identify_response_patterns(tickets)

    # 7. Statistiques par canal
    channels = analysis.get("channels", {})

    # 8. Tags utilisés
    top_tags = analysis.get("top_tags", {})

    return {
        "subject_keywords": dict(list(top_subject_keywords.items())[:30]),
        "customer_keywords": dict(list(top_customer_keywords.items())[:30]),
        "fouad_keywords": dict(list(top_fouad_keywords.items())[:30]),
        "subject_categories": subject_categories,
        "question_patterns": common_question_patterns,
        "response_patterns": common_response_patterns,
        "channels": channels,
        "top_tags": top_tags,
        "stats": {
            "total_tickets": len(tickets),
            "total_responses": analysis.get("total_fouad_responses", 0),
            "avg_responses_per_ticket": analysis.get("avg_responses_per_ticket", 0)
        }
    }


def categorize_tickets_by_subject(tickets: List[Dict[str, Any]]) -> Dict[str, int]:
    """Catégorise les tickets par sujet."""
    categories = {
        "Uber / Livraison": 0,
        "Documents / Certificats": 0,
        "Formation / Cours": 0,
        "Inscription / Registration": 0,
        "CAB / Capacité": 0,
        "CMA": 0,
        "Questions générales": 0,
        "Problèmes techniques": 0,
        "Autre": 0
    }

    keywords_map = {
        "Uber / Livraison": ["uber", "livraison", "delivery", "chauffeur", "driver"],
        "Documents / Certificats": ["document", "certificat", "attestation", "diplôme", "certificate"],
        "Formation / Cours": ["formation", "cours", "training", "learning", "programme"],
        "Inscription / Registration": ["inscription", "registration", "enregistrement", "register"],
        "CAB / Capacité": ["cab", "capacité", "capacite"],
        "CMA": ["cma"],
        "Questions générales": ["question", "information", "renseignement", "help"],
        "Problèmes techniques": ["problème", "erreur", "bug", "technical", "issue"]
    }

    for ticket in tickets:
        subject = ticket.get("subject", "").lower()
        description = ticket.get("description", "").lower()
        combined_text = f"{subject} {description}"

        categorized = False
        for category, keywords in keywords_map.items():
            if any(keyword in combined_text for keyword in keywords):
                categories[category] += 1
                categorized = True
                break

        if not categorized:
            categories["Autre"] += 1

    return categories


def identify_question_patterns(tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Identifie les patterns de questions fréquentes."""

    # Mots-clés de questions fréquentes
    question_keywords = Counter()
    question_starters = Counter()

    for ticket in tickets:
        customer_questions = ticket.get("customer_questions", [])

        for question in customer_questions:
            content = question.get("content", "").lower()

            # Extraire les premiers mots (questions starters)
            words = content.split()[:5]
            if words:
                starter = " ".join(words[:3])
                if len(starter) > 10:  # Éviter les starters trop courts
                    question_starters[starter] += 1

            # Extraire tous les mots-clés
            keywords = extract_keywords_from_text(content, min_length=5)
            question_keywords.update(keywords)

    # Top 20 question starters
    top_starters = [
        {"starter": starter, "count": count}
        for starter, count in question_starters.most_common(20)
    ]

    # Top 30 question keywords
    top_keywords = dict(question_keywords.most_common(30))

    return {
        "top_question_starters": top_starters,
        "top_question_keywords": top_keywords
    }


def identify_response_patterns(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Identifie les patterns de réponses de Fouad."""

    # Mots-clés de réponses fréquentes
    response_keywords = Counter()
    response_starters = Counter()

    # Phrases d'ouverture et de clôture fréquentes
    opening_phrases = Counter()
    closing_phrases = Counter()

    for ticket in tickets:
        fouad_responses = ticket.get("fouad_responses", [])

        for response in fouad_responses:
            content = response.get("content", "")

            if not content:
                continue

            # Nettoyer le contenu
            content_clean = content.strip()

            # Extraire les premiers mots (opening)
            sentences = content_clean.split('.')
            if sentences:
                first_sentence = sentences[0].strip().lower()
                if len(first_sentence) > 10 and len(first_sentence) < 200:
                    opening_phrases[first_sentence] += 1

            # Extraire les derniers mots (closing)
            if len(sentences) > 1:
                last_sentence = sentences[-2].strip().lower()  # -2 car le dernier peut être vide
                if len(last_sentence) > 10 and len(last_sentence) < 200:
                    closing_phrases[last_sentence] += 1

            # Extraire les mots-clés
            keywords = extract_keywords_from_text(content.lower(), min_length=5)
            response_keywords.update(keywords)

    return {
        "top_opening_phrases": dict(opening_phrases.most_common(15)),
        "top_closing_phrases": dict(closing_phrases.most_common(15)),
        "top_response_keywords": dict(response_keywords.most_common(30))
    }


def generate_routing_keywords_recommendations(patterns: Dict[str, Any]) -> Dict[str, List[str]]:
    """Génère des recommandations de mots-clés pour le routing DOC."""

    # Utiliser les mots-clés les plus fréquents dans les sujets
    subject_keywords = patterns.get("subject_keywords", {})

    # Filtrer les mots-clés pertinents (exclure les stop words communs)
    stop_words = {
        "bonjour", "merci", "svp", "madame", "monsieur",
        "cordialement", "salut", "hello", "pour", "avec",
        "être", "avoir", "faire", "aller", "cette", "votre"
    }

    # Sélectionner les top keywords qui ne sont pas des stop words
    relevant_keywords = [
        keyword for keyword, count in subject_keywords.items()
        if keyword not in stop_words and len(keyword) > 3
    ][:20]

    return {
        "DOC": relevant_keywords
    }


def generate_recommendations(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """Génère toutes les recommandations."""

    print("\n📊 Génération des recommandations...")

    # Analyser les patterns
    patterns = analyze_common_patterns(analysis_data)

    # Générer les recommandations de routing
    routing_keywords = generate_routing_keywords_recommendations(patterns)

    # Recommandations pour business_rules.py
    business_rules_recommendations = {
        "department_routing_rules": {
            "DOC": {
                "recommended_keywords": routing_keywords["DOC"],
                "rationale": "Basé sur l'analyse de {} tickets traités par Fouad".format(
                    patterns["stats"]["total_tickets"]
                )
            }
        },
        "common_patterns": patterns
    }

    return business_rules_recommendations


def display_recommendations(recommendations: Dict[str, Any]):
    """Affiche les recommandations de manière formatée."""

    print("\n" + "=" * 80)
    print("RECOMMANDATIONS POUR BUSINESS_RULES.PY")
    print("=" * 80)

    patterns = recommendations.get("common_patterns", {})
    stats = patterns.get("stats", {})

    print(f"\n📊 Statistiques globales :")
    print(f"   - Total tickets analysés : {stats.get('total_tickets', 0)}")
    print(f"   - Total réponses de Fouad : {stats.get('total_responses', 0)}")
    print(f"   - Moyenne réponses/ticket : {stats.get('avg_responses_per_ticket', 0)}")

    print(f"\n🔑 Top 15 mots-clés dans les SUJETS de tickets :")
    subject_keywords = patterns.get("subject_keywords", {})
    for i, (keyword, count) in enumerate(list(subject_keywords.items())[:15], 1):
        print(f"   {i:2d}. {keyword:20s} : {count:4d} occurrences")

    print(f"\n❓ Top 15 mots-clés dans les QUESTIONS clients :")
    customer_keywords = patterns.get("customer_keywords", {})
    for i, (keyword, count) in enumerate(list(customer_keywords.items())[:15], 1):
        print(f"   {i:2d}. {keyword:20s} : {count:4d} occurrences")

    print(f"\n💬 Top 15 mots-clés dans les RÉPONSES de Fouad :")
    fouad_keywords = patterns.get("fouad_keywords", {})
    for i, (keyword, count) in enumerate(list(fouad_keywords.items())[:15], 1):
        print(f"   {i:2d}. {keyword:20s} : {count:4d} occurrences")

    print(f"\n📂 Catégories de tickets (par sujet) :")
    categories = patterns.get("subject_categories", {})
    for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            percentage = (count / stats.get('total_tickets', 1)) * 100
            print(f"   - {category:30s} : {count:4d} ({percentage:5.1f}%)")

    print(f"\n📞 Canaux de communication :")
    channels = patterns.get("channels", {})
    for channel, count in sorted(channels.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {channel:20s} : {count:4d}")

    print(f"\n🏷️  Top 10 tags utilisés :")
    top_tags = patterns.get("top_tags", {})
    for tag, count in list(top_tags.items())[:10]:
        print(f"   - {tag:30s} : {count:4d}")

    # Recommandations spécifiques
    dept_routing = recommendations.get("department_routing_rules", {})
    doc_rules = dept_routing.get("DOC", {})

    print(f"\n✅ RECOMMANDATIONS pour department_routing_rules['DOC'] :")
    print(f"   Rationale : {doc_rules.get('rationale', '')}")
    print(f"\n   Mots-clés recommandés :")
    for keyword in doc_rules.get("recommended_keywords", [])[:15]:
        print(f"   - \"{keyword}\"")

    print("\n" + "=" * 80)


def main():
    """Point d'entrée principal."""
    print("\n" + "=" * 80)
    print("GÉNÉRATION DES RECOMMANDATIONS BUSINESS RULES")
    print("Basé sur l'analyse de Fouad Haddouchi")
    print("=" * 80)

    # Charger l'analyse
    analysis_data = load_analysis()

    # Générer les recommandations
    recommendations = generate_recommendations(analysis_data)

    # Afficher les recommandations
    display_recommendations(recommendations)

    # Sauvegarder les recommandations
    output_file = "business_rules_recommendations.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "source_analysis": "fouad_tickets_analysis.json",
            "recommendations": recommendations
        }, f, indent=2, ensure_ascii=False)

    print(f"\n📄 Recommandations détaillées sauvegardées dans : {output_file}")

    print("\n" + "=" * 80)
    print("PROCHAINES ÉTAPES")
    print("=" * 80)
    print("\n1. Examinez les recommandations ci-dessus")
    print("\n2. Mettez à jour business_rules.py avec les mots-clés recommandés")
    print("\n3. Commitez les fichiers :")
    print("   git add business_rules_recommendations.json")
    print("   git commit -m 'Add business rules recommendations based on Fouad analysis'")
    print("   git push")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
