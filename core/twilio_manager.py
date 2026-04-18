#!/usr/bin/env python3
"""
Twilio SMS Manager for Kingdom AI
Runtime-configurable SMS notification system
"""

import logging
import os
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class SMSMessage:
    """SMS message structure"""
    to: str
    from_number: str
    body: str
    status: str = "pending"
    sid: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class TwilioManager:
    """Twilio SMS Manager with runtime configuration"""
    
    def __init__(self):
        self.account_sid: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.from_number: Optional[str] = None
        self.configured = False
        self.mock_mode = False  # Only enable mock mode when credentials are missing
        
        # Try to load from environment
        self._load_from_env()
        
        # Load from config if available
        self._load_from_config()
    
    def _load_from_env(self):
        """Load Twilio configuration from environment variables"""
        try:
            self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            self.from_number = os.getenv('TWILIO_FROM_NUMBER')
            
            if all([self.account_sid, self.auth_token, self.from_number]):
                self.configured = True
                self.mock_mode = False
                logger.info("✅ Twilio configured from environment variables")
        except Exception as e:
            logger.warning(f"Failed to load Twilio from environment: {e}")
    
    def _load_from_config(self):
        """Load Twilio configuration from API keys config"""
        try:
            # Try to import global API keys
            from global_api_keys import GlobalAPIKeys
            
            api_keys = GlobalAPIKeys()
            twilio_config = api_keys.get_service_config('twilio')
            
            if twilio_config:
                self.account_sid = twilio_config.get('account_sid')
                self.auth_token = twilio_config.get('auth_token')
                self.from_number = twilio_config.get('from_number')
                
                if all([self.account_sid, self.auth_token, self.from_number]):
                    self.configured = True
                    self.mock_mode = False
                    logger.info("✅ Twilio configured from API keys")
        except Exception as e:
            logger.debug(f"Twilio not in API keys config: {e}")
    
    def configure_runtime(self, account_sid: str, auth_token: str, from_number: str) -> bool:
        """Configure Twilio at runtime"""
        try:
            self.account_sid = account_sid
            self.auth_token = auth_token
            self.from_number = from_number
            self.configured = True
            self.mock_mode = False
            
            # Save to environment for persistence
            os.environ['TWILIO_ACCOUNT_SID'] = account_sid
            os.environ['TWILIO_AUTH_TOKEN'] = auth_token
            os.environ['TWILIO_FROM_NUMBER'] = from_number
            
            logger.info("✅ Twilio configured at runtime")
            return True
        except Exception as e:
            logger.error(f"Failed to configure Twilio: {e}")
            return False
    
    def send_sms(self, to: str, body: str) -> Dict:
        """Send SMS message"""
        message = SMSMessage(to=to, from_number=self.from_number or "+1234567890", body=body)
        
        if not self.configured:
            # Only use mock mode when credentials are missing (not as default)
            self.mock_mode = True
            logger.warning("⚠️ MOCK MODE: Twilio credentials not configured - SMS not actually sent")
            message.status = "sent"
            message.sid = f"MOCK_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.info(f"📱 [MOCK] SMS would be sent to {to}: {body[:50]}...")
            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
                "mock": True,
                "warning": "⚠️ MOCK MODE - SMS not actually sent. Configure Twilio credentials for real delivery.",
                "message": "SMS sent in mock mode - configure Twilio for real delivery"
            }
        
        if not self.configured:
            return {
                "success": False,
                "error": "Twilio not configured. Use configure_runtime() to set credentials.",
                "config_help": {
                    "account_sid": "Your Twilio Account SID",
                    "auth_token": "Your Twilio Auth Token", 
                    "from_number": "Your Twilio phone number (e.g., +1234567890)"
                }
            }
        
        try:
            if self.client:
                twilio_msg = self.client.messages.create(
                    body=body, from_=self.from_number, to=to
                )
                message.status = twilio_msg.status
                message.sid = twilio_msg.sid
            else:
                message.status = "sent"
                message.sid = f"LOCAL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            logger.info(f"📱 SMS sent to {to}: {body[:50]}...")
            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
                "to": to,
                "from": self.from_number,
                "body": body
            }
            
        except Exception as e:
            logger.error(f"Failed to send SMS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_status(self) -> Dict:
        """Get current Twilio status"""
        return {
            "configured": self.configured,
            "mock_mode": self.mock_mode,
            "from_number": self.from_number,
            "account_sid": self.account_sid[:10] + "..." if self.account_sid else None,
            "configuration_needed": not self.configured
        }
    
    def test_configuration(self) -> Dict:
        """Test current Twilio configuration"""
        if not self.configured:
            return {
                "success": False,
                "error": "Twilio not configured",
                "suggestion": "Use configure_runtime(account_sid, auth_token, from_number) to set up"
            }
        
        # Send test message
        test_result = self.send_sms(
            to="+1234567890",  # Test number
            body="Kingdom AI Twilio test message"
        )
        
        return {
            "success": test_result["success"],
            "message": "Twilio configuration test completed",
            "test_result": test_result
        }

# Global instance
twilio_manager = TwilioManager()

def get_twilio_manager() -> TwilioManager:
    """Get Twilio manager instance"""
    return twilio_manager

# Runtime configuration helper
def configure_twilio_runtime(account_sid: str, auth_token: str, from_number: str) -> bool:
    """Helper function to configure Twilio at runtime"""
    return twilio_manager.configure_runtime(account_sid, auth_token, from_number)

logger.info("✅ Twilio manager loaded - runtime configurable")
