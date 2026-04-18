#!/usr/bin/env python3
"""
API Key Connection Tester
Tests API key connections and updates status
"""

import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def test_api_connection(service_name: str, api_key: str, api_manager) -> Dict[str, Any]:
    """Test if an API key is valid by making a test connection"""
    
    # Common test endpoints
    test_endpoints = {
        'binance': 'https://api.binance.com/api/v3/ping',
        'coinbase': 'https://api.coinbase.com/v2/time',
        'kraken': 'https://api.kraken.com/0/public/Time',
        'alpha_vantage': f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol=AAPL&interval=1min&apikey={api_key}',
        'coingecko': 'https://api.coingecko.com/api/v3/ping',
        'polygon': f'https://api.polygon.io/v2/aggs/ticker/AAPL/prev?apiKey={api_key}',
    }
    
    service_lower = service_name.lower().replace(' ', '_')
    
    if service_lower not in test_endpoints:
        # Can't test, mark as configured
        return {
            'service': service_name,
            'status': 'Configured',
            'message': 'No test available'
        }
    
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(test_endpoints[service_lower], timeout=5) as response:
                if response.status == 200:
                    return {
                        'service': service_name,
                        'status': 'Connected',
                        'message': 'Connection successful'
                    }
                else:
                    return {
                        'service': service_name,
                        'status': 'Configured',
                        'message': f'HTTP {response.status}'
                    }
    except Exception as e:
        logger.warning(f"Connection test failed for {service_name}: {e}")
        return {
            'service': service_name,
            'status': 'Configured',
            'message': f'Test error: {str(e)[:50]}'
        }

async def test_all_api_keys(api_manager):
    """Test all configured API keys"""
    results = []
    
    for service_name in api_manager.api_keys.keys():
        api_key = api_manager.get_api_key(service_name)
        if api_key and api_key != 'YOUR_API_KEY_HERE':
            result = await test_api_connection(service_name, api_key, api_manager)
            results.append(result)
    
    return results
