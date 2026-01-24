"""
Example: Test HTML cleaning for thread content.

This example demonstrates the difference between raw HTML content
and cleaned plain text that's sent to the AI agent.
"""
import logging
from src.utils.text_utils import clean_html_content, get_clean_thread_content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_html_cleaning():
    """Test the HTML cleaning function with various inputs."""

    print("\n" + "=" * 80)
    print("HTML CLEANING EXAMPLES")
    print("=" * 80)

    # Example 1: Simple HTML email
    html_simple = """
    <html>
    <body>
        <p>Hello,</p>
        <p>I have a question about <strong>A-Level</strong> subject selection.</p>
        <p>Can you help me?</p>
        <p>Best regards,<br>John</p>
    </body>
    </html>
    """

    print("\n1. SIMPLE HTML EMAIL")
    print("-" * 80)
    print("Raw HTML:")
    print(html_simple)
    print("\nCleaned text:")
    print(clean_html_content(html_simple))

    # Example 2: Complex HTML with CSS
    html_complex = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: Arial; }
            .signature { color: gray; font-size: 10px; }
        </style>
    </head>
    <body>
        <div style="padding: 20px; background: #f0f0f0;">
            <h2>Question about Chemistry A-Level</h2>
            <p>Hi there,</p>
            <p>I'm considering taking <span style="color: blue;">Chemistry</span> as one of my A-Levels.</p>
            <p>Is this a good choice for a medical career?</p>
            <br><br>
            <div class="signature">
                <p>Thanks,<br>Sarah Johnson<br>
                <a href="mailto:sarah@example.com">sarah@example.com</a></p>
            </div>
        </div>
        <script>
            console.log("This should be removed");
        </script>
    </body>
    </html>
    """

    print("\n2. COMPLEX HTML WITH CSS AND SCRIPTS")
    print("-" * 80)
    print("Raw HTML:")
    print(html_complex[:200] + "...")
    print("\nCleaned text:")
    print(clean_html_content(html_complex))

    # Example 3: Email with HTML entities
    html_entities = """
    <p>I&#39;m wondering about the &quot;best&quot; subjects for university.</p>
    <p>Is it better to choose Maths &amp; Physics or Biology &amp; Chemistry?</p>
    <p>I&nbsp;heard&nbsp;that&nbsp;top&nbsp;universities&nbsp;prefer&nbsp;certain&nbsp;combinations.</p>
    """

    print("\n3. HTML WITH ENTITIES")
    print("-" * 80)
    print("Raw HTML:")
    print(html_entities)
    print("\nCleaned text:")
    print(clean_html_content(html_entities))

    # Example 4: Real Zoho thread simulation
    thread_with_html = {
        "id": "thread123",
        "content": """
            <div class="email-body">
                <p>Dear Support Team,</p>
                <p>I'm struggling to decide between:</p>
                <ul>
                    <li>Mathematics</li>
                    <li>Further Mathematics</li>
                    <li>Physics</li>
                </ul>
                <p>Which combination would be best for engineering?</p>
                <br>
                <p style="color: #999;">Kind regards,<br>Michael</p>
            </div>
        """,
        "plainText": ""  # Empty plainText
    }

    thread_with_plaintext = {
        "id": "thread124",
        "plainText": "Dear Support,\n\nI need help choosing my A-Levels.\n\nThanks,\nEmily",
        "content": "<html>...</html>"  # HTML also present but plainText is preferred
    }

    print("\n4. ZOHO THREAD - HTML ONLY")
    print("-" * 80)
    content = get_clean_thread_content(thread_with_html)
    print("Cleaned content sent to AI:")
    print(content)

    print("\n5. ZOHO THREAD - WITH PLAINTEXT")
    print("-" * 80)
    content = get_clean_thread_content(thread_with_plaintext)
    print("Content sent to AI (plainText preferred):")
    print(content)


def compare_raw_vs_cleaned():
    """Compare what AI sees: raw HTML vs cleaned text."""

    print("\n" + "=" * 80)
    print("COMPARISON: WHAT THE AI AGENT SEES")
    print("=" * 80)

    raw_html = """
    <html><body style="font-family: sans-serif;">
    <div style="background: #eee; padding: 10px;">
        <h3 style="color: #333;">Urgent: A-Level Selection Help Needed</h3>
        <p>Hi,</p>
        <p>I&apos;m <strong>really</strong> confused about which subjects to pick.</p>
        <p>I want to study <span style="color: red;">Medicine</span> at university.</p>
        <ul>
            <li>Should I take Biology?</li>
            <li>Is Chemistry essential?</li>
            <li>What about Mathematics?</li>
        </ul>
        <p>Please help!</p>
        <br><br>
        <p style="font-size: 10px; color: gray;">
            Sent from my iPhone<br>
            <!-- Email signature -->
            <script>alert('spam');</script>
        </p>
    </div>
    </body></html>
    """

    cleaned = clean_html_content(raw_html)

    print("\n❌ WITHOUT CLEANING (Raw HTML sent to AI):")
    print("-" * 80)
    print(raw_html)
    print(f"\nLength: {len(raw_html)} characters")

    print("\n✅ WITH CLEANING (Clean text sent to AI):")
    print("-" * 80)
    print(cleaned)
    print(f"\nLength: {len(cleaned)} characters")

    print("\n📊 ANALYSIS:")
    print("-" * 80)
    print(f"Original HTML: {len(raw_html)} chars")
    print(f"Cleaned text: {len(cleaned)} chars")
    print(f"Reduction: {len(raw_html) - len(cleaned)} chars ({100 - len(cleaned)*100//len(raw_html)}%)")
    print("\nBenefits:")
    print("  ✅ No HTML tags cluttering the context")
    print("  ✅ No CSS styles wasting tokens")
    print("  ✅ No JavaScript or scripts")
    print("  ✅ HTML entities properly decoded")
    print("  ✅ Better AI comprehension")
    print("  ✅ Fewer tokens = lower cost")


def main():
    """Run all HTML cleaning tests."""
    test_html_cleaning()
    compare_raw_vs_cleaned()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\nThe system now:")
    print("  1. Prefers plainText field when available")
    print("  2. Cleans HTML from content field if plainText is empty")
    print("  3. Removes all HTML tags, CSS, and scripts")
    print("  4. Decodes HTML entities")
    print("  5. Normalizes whitespace")
    print("\nResult: Clean, readable text for AI analysis! ✅")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
