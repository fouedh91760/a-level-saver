#!/usr/bin/env python3
"""
Zoho Desk Webhook Server
Receives webhook events from Zoho Desk and triggers automation workflows
"""

import os
import json
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from datetime import datetime
import traceback

from src.orchestrator import ZohoAutomationOrchestrator
from src.utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = os.getenv('ZOHO_WEBHOOK_SECRET', '')  # HMAC secret for signature verification
AUTO_DISPATCH = os.getenv('WEBHOOK_AUTO_DISPATCH', 'true').lower() == 'true'
AUTO_LINK = os.getenv('WEBHOOK_AUTO_LINK', 'true').lower() == 'true'
AUTO_RESPOND = os.getenv('WEBHOOK_AUTO_RESPOND', 'false').lower() == 'true'
AUTO_UPDATE_TICKET = os.getenv('WEBHOOK_AUTO_UPDATE_TICKET', 'false').lower() == 'true'
AUTO_UPDATE_DEAL = os.getenv('WEBHOOK_AUTO_UPDATE_DEAL', 'false').lower() == 'true'
AUTO_ADD_NOTE = os.getenv('WEBHOOK_AUTO_ADD_NOTE', 'false').lower() == 'true'


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify HMAC-SHA256 signature from Zoho webhook

    Args:
        payload: Raw request body as bytes
        signature: Signature from X-Zoho-Signature header

    Returns:
        True if signature is valid, False otherwise
    """
    if not WEBHOOK_SECRET:
        logger.warning("ZOHO_WEBHOOK_SECRET not configured - skipping signature verification")
        return True

    if not signature:
        logger.warning("No signature provided in request headers")
        return False

    try:
        # Compute HMAC-SHA256 signature
        computed_signature = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Compare signatures (constant-time comparison)
        is_valid = hmac.compare_digest(computed_signature, signature)

        if not is_valid:
            logger.error("Signature verification failed")
            logger.debug(f"Expected: {computed_signature[:8]}...")
            logger.debug(f"Received: {signature[:8]}...")

        return is_valid

    except Exception as e:
        logger.error(f"Error verifying signature: {str(e)}")
        return False


def extract_ticket_id_from_payload(data: Dict[str, Any]) -> Optional[str]:
    """
    Extract ticket ID from Zoho webhook payload

    Zoho can send different payload structures depending on event type.
    Common patterns:
    - data['ticket']['id']
    - data['id']
    - data['entityId']

    Args:
        data: Parsed webhook payload

    Returns:
        Ticket ID or None if not found
    """
    # Try common patterns
    if 'ticket' in data and isinstance(data['ticket'], dict):
        return data['ticket'].get('id')

    if 'id' in data:
        return data['id']

    if 'entityId' in data:
        return data['entityId']

    # Try nested structures
    if 'data' in data:
        if isinstance(data['data'], dict):
            return extract_ticket_id_from_payload(data['data'])

    return None


def parse_webhook_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse webhook event data and extract relevant information

    Args:
        data: Raw webhook payload

    Returns:
        Parsed event data with normalized fields
    """
    event_info = {
        'event_type': data.get('event_type') or data.get('eventType') or 'unknown',
        'ticket_id': extract_ticket_id_from_payload(data),
        'timestamp': data.get('timestamp') or datetime.utcnow().isoformat(),
        'org_id': data.get('orgId'),
        'raw_data': data
    }

    logger.info(f"Parsed webhook event: {event_info['event_type']} for ticket {event_info['ticket_id']}")

    return event_info


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'a-level-saver-webhook',
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/webhook/zoho-desk', methods=['POST'])
def handle_zoho_desk_webhook():
    """
    Main webhook endpoint for Zoho Desk events

    Expected event types:
    - ticket.created
    - ticket.updated
    - ticket.status_changed
    - ticket.assigned

    Returns:
        JSON response with success status
    """
    start_time = datetime.utcnow()

    # Get raw payload for signature verification
    raw_payload = request.get_data()
    signature = request.headers.get('X-Zoho-Signature', '')

    logger.info(f"Received webhook request from {request.remote_addr}")
    logger.debug(f"Headers: {dict(request.headers)}")

    # Verify signature
    if not verify_webhook_signature(raw_payload, signature):
        logger.error("Webhook signature verification failed")
        return jsonify({
            'success': False,
            'error': 'Invalid signature'
        }), 401

    # Parse JSON payload
    try:
        data = request.get_json(force=True)
    except Exception as e:
        logger.error(f"Failed to parse JSON payload: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Invalid JSON payload'
        }), 400

    # Parse event data
    try:
        event_info = parse_webhook_event(data)
    except Exception as e:
        logger.error(f"Failed to parse webhook event: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to parse event data'
        }), 400

    # Validate ticket ID
    ticket_id = event_info['ticket_id']
    if not ticket_id:
        logger.error("No ticket ID found in webhook payload")
        logger.debug(f"Payload: {json.dumps(data, indent=2)}")
        return jsonify({
            'success': False,
            'error': 'No ticket ID found in payload'
        }), 400

    logger.info(f"Processing webhook for ticket {ticket_id}, event: {event_info['event_type']}")

    # Process ticket with orchestrator
    orchestrator = None
    try:
        orchestrator = ZohoAutomationOrchestrator()

        result = orchestrator.process_ticket_complete_workflow(
            ticket_id=ticket_id,
            auto_dispatch=AUTO_DISPATCH,
            auto_link=AUTO_LINK,
            auto_respond=AUTO_RESPOND,
            auto_update_ticket=AUTO_UPDATE_TICKET,
            auto_update_deal=AUTO_UPDATE_DEAL,
            auto_add_note=AUTO_ADD_NOTE
        )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        logger.info(f"✅ Webhook processed successfully in {processing_time:.2f}s")
        logger.info(f"Summary: {result.get('summary', {})}")

        return jsonify({
            'success': True,
            'ticket_id': ticket_id,
            'event_type': event_info['event_type'],
            'processing_time_seconds': processing_time,
            'result': {
                'dispatcher': result.get('dispatcher', {}).get('success'),
                'deal_linking': result.get('deal_linking', {}).get('success'),
                'desk_agent': result.get('desk_agent', {}).get('success'),
                'crm_agent': result.get('crm_agent', {}).get('success'),
                'summary': result.get('summary', {})
            }
        }), 200

    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}")
        logger.error(traceback.format_exc())

        return jsonify({
            'success': False,
            'ticket_id': ticket_id,
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

    finally:
        if orchestrator:
            try:
                orchestrator.close()
            except:
                pass


@app.route('/webhook/test', methods=['POST'])
def test_webhook():
    """
    Test endpoint for manual webhook testing without signature verification

    Usage:
        curl -X POST http://localhost:5000/webhook/test \
          -H "Content-Type: application/json" \
          -d '{"ticket_id": "198709000438366101"}'
    """
    try:
        data = request.get_json(force=True)
        ticket_id = data.get('ticket_id')

        if not ticket_id:
            return jsonify({
                'success': False,
                'error': 'ticket_id required'
            }), 400

        logger.info(f"Test webhook triggered for ticket {ticket_id}")

        orchestrator = ZohoAutomationOrchestrator()
        try:
            result = orchestrator.process_ticket_complete_workflow(
                ticket_id=ticket_id,
                auto_dispatch=data.get('auto_dispatch', AUTO_DISPATCH),
                auto_link=data.get('auto_link', AUTO_LINK),
                auto_respond=data.get('auto_respond', AUTO_RESPOND),
                auto_update_ticket=data.get('auto_update_ticket', AUTO_UPDATE_TICKET),
                auto_update_deal=data.get('auto_update_deal', AUTO_UPDATE_DEAL),
                auto_add_note=data.get('auto_add_note', AUTO_ADD_NOTE)
            )

            return jsonify({
                'success': True,
                'ticket_id': ticket_id,
                'result': result
            }), 200

        finally:
            orchestrator.close()

    except Exception as e:
        logger.error(f"Test webhook error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/webhook/stats', methods=['GET'])
def webhook_stats():
    """
    Get webhook statistics and configuration

    Returns current configuration and status
    """
    return jsonify({
        'service': 'a-level-saver-webhook',
        'status': 'running',
        'configuration': {
            'auto_dispatch': AUTO_DISPATCH,
            'auto_link': AUTO_LINK,
            'auto_respond': AUTO_RESPOND,
            'auto_update_ticket': AUTO_UPDATE_TICKET,
            'auto_update_deal': AUTO_UPDATE_DEAL,
            'auto_add_note': AUTO_ADD_NOTE,
            'signature_verification': bool(WEBHOOK_SECRET)
        },
        'timestamp': datetime.utcnow().isoformat()
    })


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'available_endpoints': [
            'GET /health',
            'POST /webhook/zoho-desk',
            'POST /webhook/test',
            'GET /webhook/stats'
        ]
    }), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500


if __name__ == '__main__':
    # Configuration
    host = os.getenv('WEBHOOK_HOST', '0.0.0.0')
    port = int(os.getenv('WEBHOOK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    logger.info("=" * 60)
    logger.info("🚀 A-Level Saver Webhook Server Starting")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Debug: {debug}")
    logger.info(f"Auto Dispatch: {AUTO_DISPATCH}")
    logger.info(f"Auto Link: {AUTO_LINK}")
    logger.info(f"Auto Respond: {AUTO_RESPOND}")
    logger.info(f"Auto Update Ticket: {AUTO_UPDATE_TICKET}")
    logger.info(f"Auto Update Deal: {AUTO_UPDATE_DEAL}")
    logger.info(f"Auto Add Note: {AUTO_ADD_NOTE}")
    logger.info(f"Signature Verification: {'Enabled' if WEBHOOK_SECRET else 'Disabled (WARNING!)'}")
    logger.info("=" * 60)

    if not WEBHOOK_SECRET:
        logger.warning("⚠️  ZOHO_WEBHOOK_SECRET not set - signature verification disabled!")
        logger.warning("⚠️  This is INSECURE for production use!")

    # Run Flask app
    app.run(
        host=host,
        port=port,
        debug=debug
    )
