"""
Response RAG (Retrieval Augmented Generation) System

This utility enables semantic search through Fouad's 100 ticket responses
to find similar cases for few-shot prompting.

Features:
1. Find similar tickets based on subject + customer message
2. Return top-K most similar responses with context
3. Use as few-shot examples for Claude response generation
4. Calculate similarity using TF-IDF + cosine similarity (lightweight, no external API)

Usage:
    rag = ResponseRAG()
    similar_tickets = rag.find_similar_tickets(
        subject="Demande d'identifiants",
        customer_message="Je n'arrive pas à me connecter",
        top_k=3
    )
"""
import json
import re
from typing import List, Dict, Tuple
from collections import Counter
import math
from html import unescape
from bs4 import BeautifulSoup


class ResponseRAG:
    """RAG system for finding similar ticket responses."""

    def __init__(self, fouad_tickets_path: str = "fouad_tickets_analysis.json"):
        """Initialize RAG with Fouad's tickets."""
        with open(fouad_tickets_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.tickets = self.data.get('tickets', [])
        print(f"✅ RAG initialized with {len(self.tickets)} tickets")

        # Build index
        self._build_index()

    def clean_html(self, html_content: str) -> str:
        """Remove HTML tags and clean text."""
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        return unescape(text)

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Lowercase and extract words (4+ chars for better matching)
        text = text.lower()
        words = re.findall(r'\b\w{4,}\b', text)
        return words

    def _build_index(self):
        """Build TF-IDF index for all tickets."""
        print("🔨 Building TF-IDF index...")

        # Prepare documents (combine subject + customer questions)
        self.documents = []
        self.document_vectors = []

        for ticket in self.tickets:
            # Combine subject + customer questions
            subject = ticket.get('subject', '')
            customer_questions = ticket.get('customer_questions', [])

            combined_text = subject + " "
            for q in customer_questions:
                cleaned = self.clean_html(q.get('content', ''))
                combined_text += cleaned + " "

            self.documents.append({
                'ticket_id': ticket['ticket_id'],
                'text': combined_text,
                'ticket': ticket
            })

        # Calculate IDF (inverse document frequency)
        self.idf = self._calculate_idf()

        # Calculate TF-IDF vectors for all documents
        for doc in self.documents:
            vector = self._calculate_tfidf(doc['text'])
            self.document_vectors.append(vector)

        print(f"✅ Index built for {len(self.documents)} documents")

    def _calculate_idf(self) -> Dict[str, float]:
        """Calculate IDF for all terms."""
        # Count document frequency for each term
        df = Counter()
        total_docs = len(self.documents)

        for doc in self.documents:
            tokens = set(self.tokenize(doc['text']))
            for token in tokens:
                df[token] += 1

        # Calculate IDF: log(N / df(t))
        idf = {}
        for term, doc_freq in df.items():
            idf[term] = math.log(total_docs / doc_freq)

        return idf

    def _calculate_tfidf(self, text: str) -> Dict[str, float]:
        """Calculate TF-IDF vector for a document."""
        tokens = self.tokenize(text)
        tf = Counter(tokens)

        # Calculate TF-IDF for each term
        tfidf = {}
        for term, freq in tf.items():
            # TF: term frequency in document
            tf_score = freq / len(tokens) if tokens else 0

            # IDF: inverse document frequency
            idf_score = self.idf.get(term, 0)

            # TF-IDF
            tfidf[term] = tf_score * idf_score

        return tfidf

    def cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """Calculate cosine similarity between two TF-IDF vectors."""
        # Get all terms
        all_terms = set(vec1.keys()) | set(vec2.keys())

        # Calculate dot product
        dot_product = sum(vec1.get(term, 0) * vec2.get(term, 0) for term in all_terms)

        # Calculate magnitudes
        mag1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

        # Cosine similarity
        if mag1 == 0 or mag2 == 0:
            return 0.0

        return dot_product / (mag1 * mag2)

    def find_similar_tickets(
        self,
        subject: str,
        customer_message: str = "",
        top_k: int = 3
    ) -> List[Dict]:
        """
        Find top-K most similar tickets.

        Args:
            subject: Ticket subject
            customer_message: Customer's message/question
            top_k: Number of similar tickets to return

        Returns:
            List of dicts with:
                - ticket_id
                - similarity_score
                - subject
                - customer_questions
                - fouad_responses
                - context (metadata)
        """
        # Combine query
        query_text = subject + " " + customer_message

        # Calculate TF-IDF for query
        query_vector = self._calculate_tfidf(query_text)

        # Calculate similarity with all documents
        similarities = []
        for i, doc_vector in enumerate(self.document_vectors):
            similarity = self.cosine_similarity(query_vector, doc_vector)
            similarities.append((i, similarity))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Get top-K
        top_results = []
        for i, similarity in similarities[:top_k]:
            doc = self.documents[i]
            ticket = doc['ticket']

            # Clean Fouad's responses
            fouad_responses_clean = []
            for response in ticket.get('fouad_responses', []):
                fouad_responses_clean.append({
                    'content': self.clean_html(response['content']),
                    'created_time': response.get('created_time', ''),
                    'response_time': response.get('response_time', 'N/A')
                })

            # Clean customer questions
            customer_questions_clean = []
            for question in ticket.get('customer_questions', []):
                customer_questions_clean.append({
                    'content': self.clean_html(question['content']),
                    'created_time': question.get('created_time', ''),
                    'author_name': question.get('author_name', 'Unknown')
                })

            top_results.append({
                'ticket_id': ticket['ticket_id'],
                'ticket_number': ticket.get('ticket_number', ''),
                'similarity_score': round(similarity, 4),
                'subject': ticket['subject'],
                'customer_questions': customer_questions_clean,
                'fouad_responses': fouad_responses_clean,
                'context': {
                    'channel': ticket.get('channel'),
                    'priority': ticket.get('priority'),
                    'tags': ticket.get('tags', []),
                    'created_time': ticket.get('created_time', ''),
                    'closed_time': ticket.get('closed_time', '')
                }
            })

        return top_results

    def format_for_few_shot(self, similar_tickets: List[Dict]) -> str:
        """
        Format similar tickets as few-shot examples for Claude prompt.

        Returns formatted string ready to use in Claude prompt.
        """
        few_shot_examples = []

        for i, ticket in enumerate(similar_tickets, 1):
            # Get first customer question and first Fouad response
            customer_q = ticket['customer_questions'][0]['content'] if ticket['customer_questions'] else "N/A"
            fouad_resp = ticket['fouad_responses'][0]['content'] if ticket['fouad_responses'] else "N/A"

            # Truncate if too long (keep first 500 chars)
            if len(customer_q) > 500:
                customer_q = customer_q[:500] + "..."
            if len(fouad_resp) > 1000:
                fouad_resp = fouad_resp[:1000] + "..."

            example = f"""
<example_{i}>
**Sujet** : {ticket['subject']}
**Similarité** : {ticket['similarity_score']}

**Question client** :
{customer_q}

**Réponse de Fouad** :
{fouad_resp}
</example_{i}>
"""
            few_shot_examples.append(example)

        return "\n".join(few_shot_examples)

    def get_statistics(self) -> Dict:
        """Get RAG system statistics."""
        return {
            'total_tickets': len(self.tickets),
            'total_responses': sum(len(t.get('fouad_responses', [])) for t in self.tickets),
            'total_customer_messages': sum(len(t.get('customer_questions', [])) for t in self.tickets),
            'vocabulary_size': len(self.idf),
            'avg_response_per_ticket': round(
                sum(len(t.get('fouad_responses', [])) for t in self.tickets) / len(self.tickets), 2
            )
        }


def test_rag():
    """Test the RAG system with example queries."""
    print("\n" + "=" * 80)
    print("TEST DU SYSTÈME RAG")
    print("=" * 80)

    rag = ResponseRAG("fouad_tickets_analysis.json")

    # Display statistics
    stats = rag.get_statistics()
    print("\n📊 Statistiques du système RAG :")
    for key, value in stats.items():
        print(f"   - {key}: {value}")

    # Test queries
    test_queries = [
        {
            "subject": "Demande d'identifiants ExamenT3P",
            "message": "Bonjour, je n'arrive pas à me connecter sur la plateforme ExamenT3P. Pouvez-vous me renvoyer mes identifiants ?"
        },
        {
            "subject": "Report de ma formation",
            "message": "Je souhaite reporter ma formation prévue en janvier car j'ai décalé mon examen."
        },
        {
            "subject": "Document manquant",
            "message": "Vous me dites qu'il manque un document dans mon dossier, lequel ?"
        }
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST {i} : {query['subject']}")
        print(f"{'=' * 80}")
        print(f"\nMessage : {query['message']}")

        similar_tickets = rag.find_similar_tickets(
            subject=query['subject'],
            customer_message=query['message'],
            top_k=3
        )

        print(f"\n🔍 Top 3 tickets similaires :\n")
        for j, ticket in enumerate(similar_tickets, 1):
            print(f"{j}. [Score: {ticket['similarity_score']}] {ticket['subject']}")
            print(f"   Ticket #{ticket['ticket_number']}")
            print(f"   Réponses de Fouad : {len(ticket['fouad_responses'])}")
            if ticket['fouad_responses']:
                first_response = ticket['fouad_responses'][0]['content']
                preview = first_response[:150].replace('\n', ' ')
                print(f"   Aperçu : {preview}...")
            print()

        # Show few-shot format
        print(f"\n📝 Format few-shot pour Claude :\n")
        few_shot = rag.format_for_few_shot(similar_tickets[:2])  # Show 2 examples
        print(few_shot[:800] + "..." if len(few_shot) > 800 else few_shot)

    print("\n" + "=" * 80)
    print("✅ Test du RAG terminé")
    print("=" * 80)


if __name__ == "__main__":
    test_rag()
