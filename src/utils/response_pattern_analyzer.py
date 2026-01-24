"""
Response Pattern Analyzer - Extract patterns from Fouad's 100 ticket responses.

This utility analyzes Fouad's responses to extract:
1. Structural patterns (greeting, body, closing, signature)
2. Tone and style (formal, empathetic, apologetic)
3. Common phrases and formulas
4. Length statistics
5. Scenario detection (using real 26+ scenarios from knowledge base)
6. Mandatory element compliance

Used for:
- RAG system training
- Response generation templates
- Quality validation rules
"""
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from collections import Counter
from html import unescape
from bs4 import BeautifulSoup

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from knowledge_base.scenarios_mapping import (
    SCENARIOS,
    detect_scenario_from_text,
    validate_response_compliance,
    MANDATORY_BLOCKS,
    FORBIDDEN_TERMS
)


class ResponsePatternAnalyzer:
    """Analyzes Fouad's response patterns for RAG and template generation."""

    def __init__(self, fouad_tickets_path: str = "fouad_tickets_analysis.json"):
        """Initialize analyzer with Fouad's tickets."""
        with open(fouad_tickets_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.tickets = self.data.get('tickets', [])
        self.all_responses = self._extract_all_responses()

    def _extract_all_responses(self) -> List[Dict]:
        """Extract all Fouad responses with context."""
        all_responses = []

        for ticket in self.tickets:
            ticket_context = {
                'ticket_id': ticket['ticket_id'],
                'subject': ticket['subject'],
                'customer_questions': ticket.get('customer_questions', []),
                'priority': ticket.get('priority'),
                'channel': ticket.get('channel'),
                'tags': ticket.get('tags', [])
            }

            for response in ticket.get('fouad_responses', []):
                all_responses.append({
                    'content': response['content'],
                    'created_time': response.get('created_time', ''),
                    'response_time': response.get('response_time', 'N/A'),
                    'context': ticket_context
                })

        return all_responses

    def clean_html(self, html_content: str) -> str:
        """Remove HTML tags and clean text."""
        if not html_content:
            return ""

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return unescape(text)

    def extract_greeting(self, text: str) -> str:
        """Extract greeting pattern."""
        # Common greetings
        greetings = [
            r'^Bonjour\s+(?:Mr?|Mme|Madame|Monsieur)\s+\w+',
            r'^Bonjour\s*,?',
            r'^Hello',
            r'^Re\s*bonjour',
            r'^Bonsoir'
        ]

        for pattern in greetings:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return ""

    def extract_closing(self, text: str) -> str:
        """Extract closing formula."""
        # Common closings
        closings = [
            r'Bien cordialement[,.]?\s*',
            r'Cordialement[,.]?\s*',
            r'Bonne journée[,.]?\s*',
            r'Bonne soirée[,.]?\s*',
            r'Merci[,.]?\s*',
            r'À bientôt[,.]?\s*'
        ]

        for pattern in closings:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()

        return ""

    def extract_signature(self, text: str) -> str:
        """Extract signature pattern."""
        # Common signatures
        signatures = [
            r"L'équipe\s+(?:CAB|Cab)\s+Formations",
            r"(?:CAB|Cab)\s+Formations",
            r"Fouad\s+Haddouchi",
            r"Service\s+Documentation"
        ]

        for pattern in signatures:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return ""

    def detect_tone(self, text: str) -> List[str]:
        """Detect tone markers in response."""
        tones = []

        # Apologetic
        apologetic_patterns = [
            r'désolé', r'excuses?', r'pardon',
            r'nous nous excusons', r"toutes nos excuses"
        ]
        if any(re.search(p, text, re.IGNORECASE) for p in apologetic_patterns):
            tones.append('apologetic')

        # Empathetic
        empathetic_patterns = [
            r'je comprends', r'nous comprenons',
            r'difficile pour vous', r'compliqué pour vous'
        ]
        if any(re.search(p, text, re.IGNORECASE) for p in empathetic_patterns):
            tones.append('empathetic')

        # Reassuring
        reassuring_patterns = [
            r'pas de souci', r'pas d\'inquiétude',
            r'nous allons', r'je vais', r'ne vous inquiétez pas'
        ]
        if any(re.search(p, text, re.IGNORECASE) for p in reassuring_patterns):
            tones.append('reassuring')

        # Directive (clear instructions)
        directive_patterns = [
            r'vous devez', r'il faut', r'merci de',
            r'veuillez', r'pour cela'
        ]
        if any(re.search(p, text, re.IGNORECASE) for p in directive_patterns):
            tones.append('directive')

        # Professional
        professional_patterns = [
            r'cordialement', r'bien cordialement',
            r'je vous confirme', r'nous vous confirmons'
        ]
        if any(re.search(p, text, re.IGNORECASE) for p in professional_patterns):
            tones.append('professional')

        return tones if tones else ['neutral']

    def detect_scenario(self, text: str, subject: str) -> List[str]:
        """
        Detect scenario type using real 26+ scenarios from knowledge base.

        Uses knowledge_base.scenarios_mapping.detect_scenario_from_text()
        """
        # Use the official scenario detection from knowledge base
        scenarios = detect_scenario_from_text(
            subject=subject,
            customer_message="",  # We're analyzing Fouad's response, not customer message
            crm_data=None  # No CRM data available in this analysis
        )

        # Also check the response text itself for scenario keywords
        combined_text = (text + " " + subject).lower()

        # Additional scenario detection from response content
        for scenario_id, scenario_def in SCENARIOS.items():
            triggers = scenario_def.get("triggers", [])
            for trigger in triggers:
                if trigger.lower() in combined_text and scenario_id not in scenarios:
                    scenarios.append(scenario_id)
                    break

        return scenarios if scenarios else ['GENERAL']

    def check_mandatory_elements(self, text: str) -> Dict[str, bool]:
        """
        Check for mandatory elements in response.

        Uses real MANDATORY_BLOCKS from knowledge base.
        """
        return {
            'has_identifiants': bool(re.search(r'identifiant|login|mot de passe', text, re.IGNORECASE)),
            'has_password_warning': bool(re.search(r'ne communiquez jamais|ne partagez jamais|confidentialité', text, re.IGNORECASE)),
            'has_elearning_link': bool(re.search(r'e-?learning|plateforme|formation en ligne', text, re.IGNORECASE)),
            'has_spam_warning': bool(re.search(r'spam|courrier indésirable|vérifiez vos spam', text, re.IGNORECASE)),

            # Check forbidden terms
            'has_forbidden_terms': any(
                term.lower() in text.lower() for term in FORBIDDEN_TERMS
            ),
            'forbidden_terms_found': [
                term for term in FORBIDDEN_TERMS if term.lower() in text.lower()
            ]
        }

    def analyze_length(self, text: str) -> Dict[str, int]:
        """Analyze response length."""
        words = text.split()
        sentences = re.split(r'[.!?]+', text)

        return {
            'char_count': len(text),
            'word_count': len(words),
            'sentence_count': len([s for s in sentences if s.strip()]),
            'avg_word_length': sum(len(w) for w in words) / len(words) if words else 0,
            'avg_sentence_length': len(words) / len([s for s in sentences if s.strip()]) if sentences else 0
        }

    def extract_common_phrases(self, texts: List[str], min_length: int = 4) -> List[Tuple[str, int]]:
        """Extract common phrases (n-grams)."""
        phrase_counter = Counter()

        for text in texts:
            words = text.lower().split()

            # Extract 3-grams and 4-grams
            for n in [3, 4]:
                for i in range(len(words) - n + 1):
                    phrase = ' '.join(words[i:i+n])
                    # Filter out phrases with too many common words
                    if not all(w in ['le', 'la', 'les', 'un', 'une', 'des', 'de', 'à', 'et'] for w in words[i:i+n]):
                        phrase_counter[phrase] += 1

        # Return phrases that appear at least min_length times
        return [(phrase, count) for phrase, count in phrase_counter.most_common(50) if count >= min_length]

    def analyze_all_responses(self) -> Dict:
        """Perform comprehensive analysis of all responses."""
        print("\n" + "=" * 80)
        print("ANALYSE DES PATTERNS DE RÉPONSE - FOUAD HADDOUCHI")
        print("=" * 80)
        print(f"\nNombre de réponses à analyser : {len(self.all_responses)}")

        # Storage for analysis
        greetings = []
        closings = []
        signatures = []
        tones_list = []
        scenarios_list = []
        lengths = []
        mandatory_checks = []
        cleaned_texts = []

        print("\n🔍 Analyse en cours...")

        for i, response_data in enumerate(self.all_responses):
            if (i + 1) % 20 == 0:
                print(f"   ⏳ Analysé {i + 1}/{len(self.all_responses)} réponses...")

            # Clean HTML
            text = self.clean_html(response_data['content'])
            cleaned_texts.append(text)

            # Extract patterns
            greetings.append(self.extract_greeting(text))
            closings.append(self.extract_closing(text))
            signatures.append(self.extract_signature(text))

            # Analyze tone
            tones = self.detect_tone(text)
            tones_list.extend(tones)

            # Detect scenarios
            scenarios = self.detect_scenario(text, response_data['context']['subject'])
            scenarios_list.extend(scenarios)

            # Length analysis
            lengths.append(self.analyze_length(text))

            # Mandatory elements
            mandatory_checks.append(self.check_mandatory_elements(text))

        print("✅ Analyse structurelle terminée\n")

        # Extract common phrases
        print("🔍 Extraction des phrases communes...")
        common_phrases = self.extract_common_phrases(cleaned_texts, min_length=5)
        print(f"✅ {len(common_phrases)} phrases récurrentes identifiées\n")

        # Aggregate statistics
        greeting_counts = Counter(g for g in greetings if g)
        closing_counts = Counter(c for c in closings if c)
        signature_counts = Counter(s for s in signatures if s)
        tone_counts = Counter(tones_list)
        scenario_counts = Counter(scenarios_list)

        # Length statistics
        avg_char = sum(l['char_count'] for l in lengths) / len(lengths)
        avg_word = sum(l['word_count'] for l in lengths) / len(lengths)
        avg_sentence = sum(l['sentence_count'] for l in lengths) / len(lengths)

        # Mandatory element compliance
        mandatory_stats = {
            'identifiants_rate': sum(1 for m in mandatory_checks if m['has_identifiants']) / len(mandatory_checks),
            'password_warning_rate': sum(1 for m in mandatory_checks if m['has_password_warning']) / len(mandatory_checks),
            'elearning_link_rate': sum(1 for m in mandatory_checks if m['has_elearning_link']) / len(mandatory_checks),
            'spam_warning_rate': sum(1 for m in mandatory_checks if m['has_spam_warning']) / len(mandatory_checks)
        }

        # Build final analysis
        analysis = {
            'metadata': {
                'total_responses_analyzed': len(self.all_responses),
                'total_tickets': len(self.tickets),
                'analysis_date': self.data.get('timestamp', ''),
                'agent': self.data.get('agent', {})
            },

            'structural_patterns': {
                'greetings': dict(greeting_counts.most_common(10)),
                'closings': dict(closing_counts.most_common(10)),
                'signatures': dict(signature_counts.most_common(5)),
                'most_common_greeting': greeting_counts.most_common(1)[0][0] if greeting_counts else "",
                'most_common_closing': closing_counts.most_common(1)[0][0] if closing_counts else "",
                'most_common_signature': signature_counts.most_common(1)[0][0] if signature_counts else ""
            },

            'tone_analysis': {
                'tone_distribution': dict(tone_counts.most_common()),
                'dominant_tones': [tone for tone, _ in tone_counts.most_common(3)],
                'tone_diversity': len(tone_counts)
            },

            'scenario_detection': {
                'scenario_distribution': dict(scenario_counts.most_common()),
                'top_scenarios': [scenario for scenario, _ in scenario_counts.most_common(5)],
                'scenario_coverage': len(scenario_counts)
            },

            'length_statistics': {
                'avg_characters': round(avg_char, 2),
                'avg_words': round(avg_word, 2),
                'avg_sentences': round(avg_sentence, 2),
                'min_words': min(l['word_count'] for l in lengths),
                'max_words': max(l['word_count'] for l in lengths),
                'median_words': sorted(l['word_count'] for l in lengths)[len(lengths) // 2]
            },

            'common_phrases': {
                'top_50_phrases': [
                    {'phrase': phrase, 'count': count}
                    for phrase, count in common_phrases
                ]
            },

            'mandatory_elements': {
                'compliance_rates': {
                    'identifiants': f"{mandatory_stats['identifiants_rate'] * 100:.1f}%",
                    'password_warning': f"{mandatory_stats['password_warning_rate'] * 100:.1f}%",
                    'elearning_link': f"{mandatory_stats['elearning_link_rate'] * 100:.1f}%",
                    'spam_warning': f"{mandatory_stats['spam_warning_rate'] * 100:.1f}%"
                },
                'raw_rates': mandatory_stats
            },

            'recommendations': self._generate_recommendations(
                tone_counts, scenario_counts, mandatory_stats, avg_word
            )
        }

        return analysis

    def _generate_recommendations(
        self, tone_counts, scenario_counts, mandatory_stats, avg_word
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Tone recommendations
        top_tone = tone_counts.most_common(1)[0][0] if tone_counts else "professional"
        recommendations.append(
            f"Use '{top_tone}' tone as primary style (appears in {tone_counts[top_tone]} responses)"
        )

        # Scenario coverage
        top_scenario = scenario_counts.most_common(1)[0][0] if scenario_counts else "GENERAL"
        recommendations.append(
            f"Most common scenario: {top_scenario} ({scenario_counts[top_scenario]} occurrences)"
        )

        # Length recommendation
        if avg_word < 50:
            recommendations.append("Keep responses concise (avg: 30-80 words)")
        elif avg_word > 200:
            recommendations.append("Responses can be detailed (avg: 150-250 words)")
        else:
            recommendations.append(f"Maintain moderate length (avg: {int(avg_word)} words)")

        # Mandatory element compliance
        if mandatory_stats['identifiants_rate'] > 0.3:
            recommendations.append(
                "Frequently include identifiants ExamenT3P in responses (30%+ of cases)"
            )

        if mandatory_stats['spam_warning_rate'] > 0.2:
            recommendations.append(
                "Often remind to check spam folder (20%+ of cases)"
            )

        return recommendations

    def save_analysis(self, output_path: str = "response_patterns_analysis.json"):
        """Save analysis to JSON file."""
        analysis = self.analyze_all_responses()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Analyse sauvegardée : {output_path}")
        return analysis

    def display_summary(self, analysis: Dict):
        """Display analysis summary."""
        print("\n" + "=" * 80)
        print("RÉSUMÉ DE L'ANALYSE DES PATTERNS")
        print("=" * 80)

        print(f"\n📊 Statistiques globales :")
        print(f"   - Réponses analysées : {analysis['metadata']['total_responses_analyzed']}")
        print(f"   - Tickets traités : {analysis['metadata']['total_tickets']}")

        print(f"\n✉️  Patterns structurels :")
        print(f"   - Salutation la plus courante : {analysis['structural_patterns']['most_common_greeting']}")
        print(f"   - Formule de politesse : {analysis['structural_patterns']['most_common_closing']}")
        print(f"   - Signature : {analysis['structural_patterns']['most_common_signature']}")

        print(f"\n🎭 Analyse du ton :")
        for tone, count in list(analysis['tone_analysis']['tone_distribution'].items())[:5]:
            print(f"   - {tone}: {count}")

        print(f"\n📋 Scénarios détectés :")
        for scenario, count in list(analysis['scenario_detection']['scenario_distribution'].items())[:5]:
            print(f"   - {scenario}: {count}")

        print(f"\n📏 Statistiques de longueur :")
        print(f"   - Moyenne : {analysis['length_statistics']['avg_words']:.0f} mots")
        print(f"   - Min : {analysis['length_statistics']['min_words']} mots")
        print(f"   - Max : {analysis['length_statistics']['max_words']} mots")
        print(f"   - Médiane : {analysis['length_statistics']['median_words']} mots")

        print(f"\n✅ Conformité éléments obligatoires :")
        for element, rate in analysis['mandatory_elements']['compliance_rates'].items():
            print(f"   - {element}: {rate}")

        print(f"\n💡 Recommandations :")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"   {i}. {rec}")

        print(f"\n🔑 Top 10 phrases récurrentes :")
        for item in analysis['common_phrases']['top_50_phrases'][:10]:
            print(f"   - \"{item['phrase']}\" ({item['count']}x)")

        print("\n" + "=" * 80)


def main():
    """Main execution."""
    print("\n🚀 Démarrage de l'analyse des patterns de réponse...")

    analyzer = ResponsePatternAnalyzer("fouad_tickets_analysis.json")
    analysis = analyzer.save_analysis("response_patterns_analysis.json")
    analyzer.display_summary(analysis)

    print("\n✅ Analyse terminée avec succès !")
    print("\n📂 Fichiers générés :")
    print("   - response_patterns_analysis.json (patterns détaillés)")
    print("\n🎯 Prochaine étape : Créer le système RAG pour recherche de similarité")


if __name__ == "__main__":
    main()
