"""
Analyse préliminaire de l'échantillon de 5 tickets de Fouad.

Ce script montre ce qu'on peut apprendre même avec un petit échantillon.
"""
import json
import re
from collections import Counter
from typing import Dict, Any, List

def load_test_data():
    """Charge les données de test."""
    with open("fouad_tickets_test.json", 'r', encoding='utf-8') as f:
        return json.load(f)


def clean_html(text: str) -> str:
    """Nettoie le HTML pour extraire le texte."""
    # Enlever les balises HTML
    text = re.sub(r'<[^>]+>', ' ', text)
    # Enlever les entités HTML
    text = re.sub(r'&[a-z]+;', ' ', text)
    # Normaliser les espaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_keywords(text: str, min_length: int = 4) -> List[str]:
    """Extrait les mots-clés d'un texte."""
    text_clean = clean_html(text).lower()
    words = re.findall(r'\b\w{' + str(min_length) + r',}\b', text_clean)

    # Stop words français courants
    stop_words = {
        'pour', 'avec', 'dans', 'être', 'avoir', 'faire', 'aller',
        'dire', 'cette', 'votre', 'vous', 'nous', 'elle', 'bien',
        'tout', 'plus', 'alors', 'sans', 'tous', 'comme', 'après',
        'avant', 'très', 'aussi', 'même', 'encore', 'peut', 'dont',
        'chez', 'mais', 'donc', 'quoi', 'leur', 'leurs', 'cela',
        'bonjour', 'merci', 'cordialement', 'madame', 'monsieur',
        'svp', 'salut', 'hello', 'nbsp', 'quot', 'mailto', 'target',
        'blank', 'noreferrer', 'gmail', 'style', 'margin', 'padding',
        'border', 'left', 'solid', 'dotted', 'font', 'family', 'size',
        'color', 'width', 'height', 'ltr', 'auto', 'content', 'text',
        'html', 'charset', 'utf', 'meta', 'itemprop', 'href', 'class',
        'dir', 'cab-formations', 'formations', 'zoho', 'desk', 'zdeskinteg'
    }

    return [w for w in words if w not in stop_words]


def analyze_subjects(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse les sujets des tickets."""
    subjects = [ticket['subject'] for ticket in tickets]

    # Catégorisation basique
    categories = {
        'Formation/Programme': 0,
        'Problème/Réclamation': 0,
        'Question/Assistance': 0,
        'Examen/Test': 0,
        'Autre': 0
    }

    for subject in subjects:
        subject_lower = subject.lower()
        if any(word in subject_lower for word in ['formation', 'programme', 'cours', 'webinar']):
            categories['Formation/Programme'] += 1
        elif any(word in subject_lower for word in ['manquement', 'problème', 'erreur', 'grave']):
            categories['Problème/Réclamation'] += 1
        elif any(word in subject_lower for word in ['examen', 'test', 'vtc', 'sélection']):
            categories['Examen/Test'] += 1
        elif any(word in subject_lower for word in ['assistance', 'question', 'form submission']):
            categories['Question/Assistance'] += 1
        else:
            categories['Autre'] += 1

    return {
        'subjects': subjects,
        'categories': categories
    }


def analyze_customer_questions(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse les questions des clients."""
    all_questions = []
    question_keywords = Counter()

    for ticket in tickets:
        questions = ticket.get('customer_questions', [])
        for q in questions:
            content = q.get('content', '')
            all_questions.append(content)

            # Extraire les mots-clés
            keywords = extract_keywords(content, min_length=5)
            question_keywords.update(keywords)

    return {
        'total_questions': len(all_questions),
        'avg_per_ticket': round(len(all_questions) / len(tickets), 1),
        'top_keywords': dict(question_keywords.most_common(20))
    }


def analyze_fouad_responses(tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyse les réponses de Fouad."""
    all_responses = []
    response_keywords = Counter()
    opening_phrases = []
    closing_phrases = []

    for ticket in tickets:
        responses = ticket.get('fouad_responses', [])
        for r in responses:
            content = r.get('content', '')
            all_responses.append(content)

            # Nettoyer et extraire le texte
            clean_content = clean_html(content)

            # Extraire les mots-clés
            keywords = extract_keywords(content, min_length=5)
            response_keywords.update(keywords)

            # Extraire les phrases d'ouverture
            sentences = clean_content.split('.')
            if sentences:
                first = sentences[0].strip()
                if len(first) > 10 and len(first) < 200:
                    opening_phrases.append(first)

            # Extraire les phrases de clôture
            if len(sentences) > 1:
                # Chercher "Cordialement", "Bien cordialement", etc.
                for i in range(len(sentences) - 1, max(0, len(sentences) - 5), -1):
                    sent = sentences[i].strip().lower()
                    if any(word in sent for word in ['cordialement', 'équipe', 'formations']):
                        closing_phrases.append(sentences[i].strip())
                        break

    return {
        'total_responses': len(all_responses),
        'avg_per_ticket': round(len(all_responses) / len(tickets), 1),
        'avg_length': round(sum(len(r) for r in all_responses) / len(all_responses)) if all_responses else 0,
        'top_keywords': dict(response_keywords.most_common(20)),
        'opening_phrases': opening_phrases,
        'closing_phrases': closing_phrases
    }


def identify_common_issues(tickets: List[Dict[str, Any]]) -> List[str]:
    """Identifie les problèmes/thèmes récurrents."""
    issues = []

    for ticket in tickets:
        subject = ticket.get('subject', '').lower()

        # Questions client
        for q in ticket.get('customer_questions', []):
            content = clean_html(q.get('content', '')).lower()

            # Identifier les problématiques
            if any(word in content for word in ['formation', 'cours', 'programme', 'webinar']):
                issues.append('Formation/Accès au contenu')
            if any(word in content for word in ['payer', 'payé', 'paiement', 'facture']):
                issues.append('Paiement/Facturation')
            if any(word in content for word in ['examen', 'test', 'date', 'convocation']):
                issues.append('Examen/Planification')
            if any(word in content for word in ['erreur', 'problème', 'bug', 'fonctionne pas']):
                issues.append('Problème technique')
            if any(word in content for word in ['prenom', 'prénom', 'nom', 'modification']):
                issues.append('Modification données personnelles')
            if any(word in content for word in ['retard', 'délai', 'attente', 'réponse']):
                issues.append('Délai de réponse/Suivi')

    return Counter(issues).most_common(10)


def main():
    """Analyse principale."""
    print("\n" + "=" * 80)
    print("ANALYSE PRÉLIMINAIRE - 5 TICKETS DE FOUAD")
    print("=" * 80)

    data = load_test_data()
    tickets = data['tickets']

    print(f"\n📊 Données brutes :")
    print(f"   - Tickets analysés : {len(tickets)}")
    print(f"   - Tickets vérifiés : {data['total_tickets_checked']}")
    print(f"   - Taux de Fouad : {round(len(tickets)/data['total_tickets_checked']*100, 1)}%")

    # Analyse des sujets
    print("\n" + "=" * 80)
    print("1. ANALYSE DES SUJETS DE TICKETS")
    print("=" * 80)

    subject_analysis = analyze_subjects(tickets)
    print(f"\n📋 Sujets complets :")
    for i, subject in enumerate(subject_analysis['subjects'], 1):
        print(f"   {i}. {subject}")

    print(f"\n📂 Catégorisation :")
    for category, count in subject_analysis['categories'].items():
        if count > 0:
            print(f"   - {category}: {count}")

    # Analyse des questions clients
    print("\n" + "=" * 80)
    print("2. ANALYSE DES QUESTIONS CLIENTS")
    print("=" * 80)

    question_analysis = analyze_customer_questions(tickets)
    print(f"\n❓ Statistiques :")
    print(f"   - Total questions : {question_analysis['total_questions']}")
    print(f"   - Moyenne par ticket : {question_analysis['avg_per_ticket']}")

    print(f"\n🔑 Top 15 mots-clés dans les questions :")
    for i, (keyword, count) in enumerate(list(question_analysis['top_keywords'].items())[:15], 1):
        print(f"   {i:2d}. {keyword:20s} : {count:2d}")

    # Analyse des réponses de Fouad
    print("\n" + "=" * 80)
    print("3. ANALYSE DES RÉPONSES DE FOUAD")
    print("=" * 80)

    response_analysis = analyze_fouad_responses(tickets)
    print(f"\n💬 Statistiques :")
    print(f"   - Total réponses : {response_analysis['total_responses']}")
    print(f"   - Moyenne par ticket : {response_analysis['avg_per_ticket']}")
    print(f"   - Longueur moyenne : {response_analysis['avg_length']} caractères")

    print(f"\n🔑 Top 15 mots-clés dans les réponses de Fouad :")
    for i, (keyword, count) in enumerate(list(response_analysis['top_keywords'].items())[:15], 1):
        print(f"   {i:2d}. {keyword:20s} : {count:2d}")

    print(f"\n📝 Phrases d'ouverture typiques :")
    for i, phrase in enumerate(response_analysis['opening_phrases'][:5], 1):
        print(f"   {i}. \"{phrase[:80]}...\"")

    print(f"\n📝 Signatures/Clôtures :")
    unique_closings = list(set(response_analysis['closing_phrases']))[:3]
    for i, phrase in enumerate(unique_closings, 1):
        print(f"   {i}. \"{phrase[:80]}...\"")

    # Problématiques récurrentes
    print("\n" + "=" * 80)
    print("4. PROBLÉMATIQUES RÉCURRENTES")
    print("=" * 80)

    common_issues = identify_common_issues(tickets)
    print(f"\n🎯 Top problématiques identifiées :")
    for i, (issue, count) in enumerate(common_issues, 1):
        print(f"   {i}. {issue:40s} : {count} occurrence(s)")

    # Recommandations
    print("\n" + "=" * 80)
    print("5. RECOMMANDATIONS PRÉLIMINAIRES")
    print("=" * 80)

    print(f"\n📌 Basé sur cet échantillon de {len(tickets)} tickets :")

    print(f"\n✅ Mots-clés à ajouter au routing DOC :")
    # Prendre les top keywords qui ne sont pas déjà dans business_rules
    existing_keywords = ['uber', 'a-level', 'document', 'formation', 'programme', 'cours']
    new_keywords = []
    for keyword, _ in list(question_analysis['top_keywords'].items())[:20]:
        if keyword not in existing_keywords and len(keyword) > 4:
            new_keywords.append(keyword)

    for keyword in new_keywords[:10]:
        print(f"   - \"{keyword}\"")

    print(f"\n✅ Patterns de réponses de Fouad :")
    print(f"   - Style : Professionnel mais empathique")
    print(f"   - Longueur moyenne : {response_analysis['avg_length']} caractères")
    print(f"   - Réponses par ticket : {response_analysis['avg_per_ticket']} en moyenne")

    print(f"\n⚠️  Note importante :")
    print(f"   Cette analyse est basée sur seulement {len(tickets)} tickets.")
    print(f"   Pour des recommandations robustes, lancer l'analyse complète de 500 tickets.")

    print("\n" + "=" * 80)
    print("PROCHAINE ÉTAPE")
    print("=" * 80)
    print("\n▶️  Lancer l'analyse complète :")
    print("   python analyze_fouad_tickets.py")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
