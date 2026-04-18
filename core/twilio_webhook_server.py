#!/usr/bin/env python3
"""
KINGDOM AI - TWILIO WEBHOOK SERVER
===================================
Receives incoming SMS messages and forwards them to Kingdom AI/Ollama for processing.

Setup:
1. Run this server: python core/twilio_webhook_server.py
2. Use ngrok to expose it: ngrok http 5000
3. Configure Twilio webhook: https://console.twilio.com -> Phone Numbers -> Your Number -> Messaging -> Webhook URL

Author: Kingdom AI Team
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import sys
import asyncio

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("KingdomAI.TwilioWebhook")

# Store received messages
received_messages = []


def create_webhook_app():
    """Create Flask app for Twilio webhook"""
    try:
        from flask import Flask, request, Response
    except ImportError:
        logger.error("Flask not installed. Run: pip install flask")
        return None
    
    app = Flask(__name__)
    
    @app.route('/sms/receive', methods=['POST'])
    def receive_sms():
        """Receive incoming SMS from Twilio"""
        # Get message data from Twilio
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        body = request.form.get('Body', '')
        message_sid = request.form.get('MessageSid', '')
        
        timestamp = datetime.now().isoformat()
        
        message_data = {
            'from': from_number,
            'to': to_number,
            'body': body,
            'message_sid': message_sid,
            'timestamp': timestamp
        }
        
        # Store message
        received_messages.append(message_data)
        
        logger.info(f"📨 INCOMING SMS from {from_number}")
        logger.info(f"   Message: {body}")
        logger.info(f"   SID: {message_sid}")
        
        # Try to forward to Ollama for processing
        try:
            response_text = process_incoming_with_ollama(body, from_number)
        except Exception as e:
            logger.error(f"Error processing with Ollama: {e}")
            response_text = None
        
        # Create TwiML response
        if response_text:
            # Auto-reply with Ollama's response
            twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{response_text}</Message>
</Response>'''
            logger.info(f"📤 AUTO-REPLY: {response_text}")
        else:
            # Empty response (no auto-reply)
            twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
        
        return Response(twiml, mimetype='text/xml')
    
    @app.route('/sms/status', methods=['POST'])
    def sms_status():
        """Receive SMS delivery status updates"""
        message_sid = request.form.get('MessageSid', '')
        status = request.form.get('MessageStatus', '')
        
        logger.info(f"📊 SMS Status Update: {message_sid} -> {status}")
        
        return Response('OK', status=200)
    
    @app.route('/messages', methods=['GET'])
    def get_messages():
        """Get all received messages (API endpoint)"""
        return json.dumps(received_messages, indent=2)
    
    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint"""
        return json.dumps({
            'status': 'running',
            'messages_received': len(received_messages),
            'timestamp': datetime.now().isoformat()
        })
    
    return app


def process_incoming_with_ollama(message: str, from_number: str) -> Optional[str]:
    """Process incoming SMS with Ollama and generate response"""
    try:
        from core.thoth_ollama_connector import ThothOllamaConnector
        
        connector = ThothOllamaConnector(event_bus=None)
        
        # Get event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Initialize connector
        loop.run_until_complete(connector.initialize())
        
        if not connector.active:
            logger.warning("Ollama not active - cannot generate response")
            return None
        
        # Generate response
        prompt = f"""You are Kingdom AI, responding to an SMS message.
Keep your response brief and conversational (under 160 characters).

User's SMS: {message}

Your SMS response:"""
        
        response = loop.run_until_complete(connector.generate_text(prompt))
        
        if response:
            # Clean up response
            response = response.strip().strip('"').strip("'")
            # Truncate if too long
            if len(response) > 160:
                response = response[:157] + "..."
            return response
        
        return None
        
    except Exception as e:
        logger.error(f"Error in Ollama processing: {e}")
        return None


def run_webhook_server(port: int = 5000, auto_reply: bool = True):
    """Run the webhook server"""
    app = create_webhook_app()
    if app is None:
        return
    
    print("\n" + "=" * 60)
    print("  🤖 KINGDOM AI - TWILIO WEBHOOK SERVER")
    print("=" * 60)
    print(f"  Server running on: http://0.0.0.0:{port}")
    print(f"  SMS Webhook URL:   http://YOUR_PUBLIC_IP:{port}/sms/receive")
    print(f"  Auto-reply:        {'Enabled (Ollama)' if auto_reply else 'Disabled'}")
    print()
    print("  SETUP STEPS:")
    print("  1. Expose this server with ngrok: ngrok http {port}")
    print("  2. Copy the https URL (e.g., https://abc123.ngrok.io)")
    print("  3. Go to Twilio Console -> Phone Numbers -> Your Number")
    print("  4. Set Messaging Webhook to: https://YOUR_NGROK_URL/sms/receive")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Kingdom AI Twilio Webhook Server")
    parser.add_argument("--port", "-p", type=int, default=5000, help="Server port")
    parser.add_argument("--no-reply", action="store_true", help="Disable auto-reply")
    
    args = parser.parse_args()
    
    run_webhook_server(port=args.port, auto_reply=not args.no_reply)
