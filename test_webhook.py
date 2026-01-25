#!/usr/bin/env python3
"""
Script de test pour le webhook A-Level Saver
Permet de tester facilement le webhook avec différents scénarios
"""

import os
import json
import hmac
import hashlib
import requests
import argparse
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
WEBHOOK_URL = os.getenv('WEBHOOK_TEST_URL', 'http://localhost:5000')
WEBHOOK_SECRET = os.getenv('ZOHO_WEBHOOK_SECRET', '')


def calculate_hmac_signature(payload: str, secret: str) -> str:
    """
    Calculate HMAC-SHA256 signature for webhook payload

    Args:
        payload: JSON payload as string
        secret: HMAC secret

    Returns:
        Hex digest of HMAC signature
    """
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def test_health_check(base_url: str):
    """Test health check endpoint"""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)

    url = f"{base_url}/health"
    print(f"URL: {url}")

    try:
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_stats(base_url: str):
    """Test stats endpoint"""
    print("\n" + "=" * 60)
    print("TEST 2: Webhook Stats")
    print("=" * 60)

    url = f"{base_url}/webhook/stats"
    print(f"URL: {url}")

    try:
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_webhook_simple(base_url: str, ticket_id: str, auto_flags: Dict[str, bool] = None):
    """Test webhook with simple test endpoint (no signature)"""
    print("\n" + "=" * 60)
    print("TEST 3: Simple Webhook Test (No Signature)")
    print("=" * 60)

    url = f"{base_url}/webhook/test"
    print(f"URL: {url}")
    print(f"Ticket ID: {ticket_id}")

    # Build payload
    payload = {
        "ticket_id": ticket_id
    }

    if auto_flags:
        payload.update(auto_flags)

    print(f"Payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=120
        )
        print(f"\nStatus: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_webhook_with_signature(base_url: str, ticket_id: str, secret: str, event_type: str = "ticket.created"):
    """Test webhook with HMAC signature verification"""
    print("\n" + "=" * 60)
    print("TEST 4: Webhook with HMAC Signature")
    print("=" * 60)

    url = f"{base_url}/webhook/zoho-desk"
    print(f"URL: {url}")
    print(f"Ticket ID: {ticket_id}")
    print(f"Event Type: {event_type}")

    # Build payload (format Zoho Desk)
    payload = {
        "ticket": {
            "id": ticket_id
        },
        "event_type": event_type,
        "timestamp": "2026-01-25T12:00:00.000Z",
        "orgId": "648790851"
    }

    payload_str = json.dumps(payload)
    print(f"Payload: {payload_str}")

    # Calculate signature
    if secret:
        signature = calculate_hmac_signature(payload_str, secret)
        print(f"Signature: {signature[:16]}... (truncated)")
    else:
        signature = ""
        print("⚠️  No secret provided - signature verification will fail!")

    try:
        response = requests.post(
            url,
            data=payload_str,
            headers={
                'Content-Type': 'application/json',
                'X-Zoho-Signature': signature
            },
            timeout=120
        )
        print(f"\nStatus: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


def test_with_real_ticket_data(base_url: str):
    """Test with real ticket data from JSON files"""
    print("\n" + "=" * 60)
    print("TEST 5: Real Ticket Data")
    print("=" * 60)

    # Read real ticket data
    ticket_files = [
        "ticket_198709000438366101_all_fields.json",
        "test_results_198709000438366101.json"
    ]

    for filename in ticket_files:
        if not os.path.exists(filename):
            print(f"⚠️  File not found: {filename}")
            continue

        print(f"\n📄 Testing with file: {filename}")

        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract ticket ID
        ticket_id = data.get('ticket_id') or data.get('id')

        if not ticket_id:
            print(f"❌ No ticket_id found in {filename}")
            continue

        print(f"Ticket ID: {ticket_id}")

        # Test with simple endpoint
        success = test_webhook_simple(base_url, ticket_id, {
            "auto_dispatch": True,
            "auto_link": True,
            "auto_respond": False
        })

        if success:
            print(f"✅ Test passed for {filename}")
        else:
            print(f"❌ Test failed for {filename}")


def test_invalid_payloads(base_url: str):
    """Test error handling with invalid payloads"""
    print("\n" + "=" * 60)
    print("TEST 6: Invalid Payloads (Error Handling)")
    print("=" * 60)

    test_cases = [
        {
            "name": "Empty payload",
            "payload": {},
            "expected_status": 400
        },
        {
            "name": "Missing ticket_id",
            "payload": {"event_type": "ticket.created"},
            "expected_status": 400
        },
        {
            "name": "Invalid ticket_id",
            "payload": {"ticket_id": "invalid_id"},
            "expected_status": 500  # Will fail when orchestrator tries to fetch
        },
        {
            "name": "Malformed JSON",
            "payload": "not a json",
            "expected_status": 400
        }
    ]

    url = f"{base_url}/webhook/test"

    for test_case in test_cases:
        print(f"\n🧪 Test: {test_case['name']}")
        print(f"Payload: {test_case['payload']}")

        try:
            if isinstance(test_case['payload'], str):
                response = requests.post(
                    url,
                    data=test_case['payload'],
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
            else:
                response = requests.post(
                    url,
                    json=test_case['payload'],
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )

            print(f"Status: {response.status_code} (expected: {test_case['expected_status']})")

            if response.status_code == test_case['expected_status']:
                print("✅ Behaves as expected")
            else:
                print(f"⚠️  Unexpected status code")

            try:
                print(f"Response: {json.dumps(response.json(), indent=2)}")
            except:
                print(f"Response: {response.text}")

        except Exception as e:
            print(f"❌ Error: {str(e)}")


def run_all_tests(base_url: str, ticket_id: str, secret: str):
    """Run all tests"""
    print("\n" + "🚀" * 30)
    print("RUNNING ALL WEBHOOK TESTS")
    print("🚀" * 30)
    print(f"Base URL: {base_url}")
    print(f"Test Ticket ID: {ticket_id}")
    print(f"Secret configured: {'Yes' if secret else 'No'}")

    results = []

    # Test 1: Health check
    results.append(("Health Check", test_health_check(base_url)))

    # Test 2: Stats
    results.append(("Stats", test_stats(base_url)))

    # Test 3: Simple webhook
    results.append(("Simple Webhook", test_webhook_simple(base_url, ticket_id)))

    # Test 4: Webhook with signature
    if secret:
        results.append(("Webhook with Signature", test_webhook_with_signature(base_url, ticket_id, secret)))
    else:
        print("\n⚠️  Skipping signature test - ZOHO_WEBHOOK_SECRET not set")

    # Test 5: Real ticket data
    if os.path.exists("ticket_198709000438366101_all_fields.json"):
        test_with_real_ticket_data(base_url)

    # Test 6: Invalid payloads
    test_invalid_payloads(base_url)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")

    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")


def main():
    parser = argparse.ArgumentParser(description='Test A-Level Saver Webhook')
    parser.add_argument(
        '--url',
        default=WEBHOOK_URL,
        help='Webhook base URL (default: http://localhost:5000)'
    )
    parser.add_argument(
        '--ticket-id',
        default='198709000438366101',
        help='Test ticket ID (default: 198709000438366101)'
    )
    parser.add_argument(
        '--secret',
        default=WEBHOOK_SECRET,
        help='HMAC secret for signature verification'
    )
    parser.add_argument(
        '--test',
        choices=['health', 'stats', 'simple', 'signature', 'real', 'invalid', 'all'],
        default='all',
        help='Which test to run (default: all)'
    )

    args = parser.parse_args()

    # Run selected test
    if args.test == 'health':
        test_health_check(args.url)
    elif args.test == 'stats':
        test_stats(args.url)
    elif args.test == 'simple':
        test_webhook_simple(args.url, args.ticket_id)
    elif args.test == 'signature':
        if not args.secret:
            print("❌ Secret required for signature test. Set ZOHO_WEBHOOK_SECRET in .env")
            return
        test_webhook_with_signature(args.url, args.ticket_id, args.secret)
    elif args.test == 'real':
        test_with_real_ticket_data(args.url)
    elif args.test == 'invalid':
        test_invalid_payloads(args.url)
    else:
        run_all_tests(args.url, args.ticket_id, args.secret)


if __name__ == '__main__':
    main()
