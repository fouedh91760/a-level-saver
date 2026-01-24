"""
Example: Analyzing ticket with complete context (full thread history).

This example demonstrates how the agent now accesses:
- Complete email threads (full content, not summaries)
- All conversations
- Modification history

This provides much better context for AI analysis.
"""
import logging
import json
from src.agents import DeskTicketAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def display_complete_context(result):
    """Display the complete context that was provided to the AI agent."""
    print("\n" + "=" * 80)
    print("COMPLETE TICKET CONTEXT AVAILABLE TO AI")
    print("=" * 80)

    complete_context = result.get("complete_context", {})

    # Basic ticket info
    ticket = complete_context.get("ticket", {})
    print(f"\n📋 Basic Information:")
    print(f"  Ticket Number: {ticket.get('ticketNumber')}")
    print(f"  Subject: {ticket.get('subject')}")
    print(f"  Status: {ticket.get('status')}")
    print(f"  Priority: {ticket.get('priority')}")
    print(f"  Created: {ticket.get('createdTime')}")

    # Thread history (full email content)
    threads = complete_context.get("threads", [])
    if threads:
        print(f"\n📧 Complete Thread History ({len(threads)} threads):")
        for idx, thread in enumerate(threads, 1):
            print(f"\n  Thread #{idx}:")
            print(f"    Direction: {thread.get('direction')}")
            from_email = thread.get('from', {})
            if isinstance(from_email, dict):
                print(f"    From: {from_email.get('emailId', 'N/A')} ({from_email.get('name', 'N/A')})")
            else:
                print(f"    From: {from_email}")
            print(f"    Subject: {thread.get('subject')}")
            print(f"    Time: {thread.get('createdTime')}")

            # Show full content
            content = thread.get('content', thread.get('plainText', 'N/A'))
            print(f"    Content (full):")
            # Truncate for display but note it's the full content
            if len(content) > 200:
                print(f"      {content[:200]}...")
                print(f"      (Full content: {len(content)} characters)")
            else:
                print(f"      {content}")
    else:
        print("\n📧 No thread history found")

    # Conversation history
    conversations = complete_context.get("conversations", [])
    if conversations:
        print(f"\n💬 Conversation History ({len(conversations)} conversations):")
        for idx, conv in enumerate(conversations, 1):
            print(f"\n  Conversation #{idx}:")
            print(f"    Type: {conv.get('type')}")
            author = conv.get('author', {})
            if isinstance(author, dict):
                print(f"    Author: {author.get('name', 'N/A')}")
            else:
                print(f"    Author: {author}")
            print(f"    Time: {conv.get('createdTime')}")
            print(f"    Public: {conv.get('isPublic')}")
            content = conv.get('content', 'N/A')
            if len(content) > 150:
                print(f"    Content: {content[:150]}...")
            else:
                print(f"    Content: {content}")
    else:
        print("\n💬 No conversation history found")

    # Modification history
    history = complete_context.get("history", [])
    if history:
        print(f"\n📝 Modification History ({len(history)} changes):")
        for idx, hist in enumerate(history[-5:], 1):  # Show last 5
            actor = hist.get('actor', {})
            actor_name = actor.get('name', 'N/A') if isinstance(actor, dict) else actor
            print(f"  {idx}. {hist.get('fieldName')}: {hist.get('oldValue')} → {hist.get('newValue')}")
            print(f"     By: {actor_name} at {hist.get('modifiedTime')}")
    else:
        print("\n📝 No modification history found")


def main():
    """Demonstrate full context analysis."""
    agent = DeskTicketAgent()

    try:
        # Process a ticket - the agent now gets FULL context
        logger.info("Processing ticket with complete context...")

        ticket_id = "123456789"  # Replace with actual ticket ID

        result = agent.process({
            "ticket_id": ticket_id,
            "auto_respond": False,
            "auto_update": False
        })

        # Display what context was available to the AI
        display_complete_context(result)

        # Display AI analysis based on full context
        print("\n" + "=" * 80)
        print("AI ANALYSIS (based on complete context above)")
        print("=" * 80)

        analysis = result['agent_analysis']

        print(f"\n🤖 Agent's Understanding:")
        print(f"{analysis['analysis']}")

        print(f"\n📊 Assessment:")
        print(f"  Priority: {analysis['priority']}")
        print(f"  Suggested Status: {analysis['suggested_status']}")
        print(f"  Escalation Needed: {analysis['should_escalate']}")

        if analysis['should_escalate']:
            print(f"\n⚠️  ESCALATION REASON:")
            print(f"  {analysis['escalation_reason']}")

        print(f"\n💡 Suggested Response:")
        print(f"{analysis['suggested_response']}")

        print(f"\n📝 Internal Notes:")
        print(f"{analysis['internal_notes']}")

        print(f"\n🏷️  Suggested Tags:")
        print(f"  {', '.join(analysis.get('tags', []))}")

        # Show the difference
        print("\n" + "=" * 80)
        print("KEY IMPROVEMENT")
        print("=" * 80)
        print("\n✅ BEFORE: Agent only saw ticket summary/description")
        print("✅ NOW: Agent sees:")
        print("   - Complete email threads (full text, not summaries)")
        print("   - All back-and-forth conversations")
        print("   - History of modifications")
        print("   - Full context to understand the customer journey")
        print("\nThis results in much more accurate and context-aware responses!")

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        agent.close()


if __name__ == "__main__":
    main()
