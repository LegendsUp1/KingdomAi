"""
Trading Asset Search - Search functionality for finding assets across all connected exchanges
Supports text and voice input, integrates with Ollama brain
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger("KingdomAI.TradingAssetSearch")


def _search_asset(self):
    """Search for an asset across all connected exchanges."""
    try:
        query = self.asset_search_input.text().strip().upper()
        if not query:
            self.search_results_label.setText("⚠️ Please enter a symbol to search")
            self.search_results_label.setVisible(True)
            return
        
        logger.info(f"🔍 Searching for asset: {query}")
        
        # Search across connected exchanges
        results = self._search_across_exchanges(query)
        
        if results:
            # Display results
            exchanges = [r['exchange'] for r in results]
            self.search_results_label.setText(f"✅ Found {query} on: {', '.join(exchanges)}")
            self.search_results_label.setStyleSheet("""
                QLabel {
                    color: #00FF00;
                    font-size: 9px;
                    padding: 4px;
                    background-color: #0A2E0A;
                    border-radius: 3px;
                }
            """)
            self.search_results_label.setVisible(True)
            
            # Select the asset and display info
            self._select_searched_asset(query, results)
            
            # Send to Ollama brain for analysis
            if self.event_bus:
                self.event_bus.publish('ollama.analyze.asset', {
                    'symbol': query,
                    'exchanges': exchanges,
                    'results': results,
                    'source': 'trading_search'
                })
        else:
            self.search_results_label.setText(f"❌ {query} not found on connected exchanges")
            self.search_results_label.setStyleSheet("""
                QLabel {
                    color: #FF0000;
                    font-size: 9px;
                    padding: 4px;
                    background-color: #2E0A0A;
                    border-radius: 3px;
                }
            """)
            self.search_results_label.setVisible(True)
            
            # Still send to Ollama for suggestions
            if self.event_bus:
                self.event_bus.publish('ollama.suggest.asset', {
                    'query': query,
                    'source': 'trading_search'
                })
        
    except Exception as e:
        logger.error(f"Error searching asset: {e}")
        self.search_results_label.setText(f"⚠️ Search error: {str(e)}")
        self.search_results_label.setVisible(True)


def _on_search_text_changed(self, text: str):
    """Handle search text changes for auto-suggestions."""
    try:
        if len(text) < 2:
            self.search_results_label.setVisible(False)
            return
        
        # Show suggestions as user types
        query = text.strip().upper()
        suggestions = self._get_asset_suggestions(query)
        
        if suggestions:
            self.search_results_label.setText(f"💡 Suggestions: {', '.join(suggestions[:5])}")
            self.search_results_label.setStyleSheet("""
                QLabel {
                    color: #FFD700;
                    font-size: 9px;
                    padding: 4px;
                    background-color: #2E2E0A;
                    border-radius: 3px;
                }
            """)
            self.search_results_label.setVisible(True)
        else:
            self.search_results_label.setVisible(False)
            
    except Exception as e:
        logger.debug(f"Error in search text changed: {e}")


def _voice_search_asset(self):
    """Activate voice search for asset lookup."""
    try:
        logger.info("🎤 Voice search activated")
        
        # Update button to show listening state
        self.voice_search_button.setText("🔴")
        self.voice_search_button.setStyleSheet("""
            QPushButton {
                background-color: #FF0000;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 14px;
                font-weight: bold;
                animation: pulse 1s infinite;
            }
        """)
        
        # Send voice search request to Ollama brain
        if self.event_bus:
            self.event_bus.publish('ollama.voice.search.start', {
                'context': 'trading_asset_search',
                'callback': 'trading.asset.voice_result'
            })
            
            # Also trigger Thoth voice recognition
            self.event_bus.publish('thoth.voice.listen', {
                'context': 'asset_search',
                'callback': 'trading.asset.voice_result'
            })
        
        # Set placeholder
        self.asset_search_input.setPlaceholderText("🎤 Listening... Say asset symbol...")
        
        logger.info("✅ Voice search request sent to Ollama brain and Thoth")
        
    except Exception as e:
        logger.error(f"Error activating voice search: {e}")
        self._reset_voice_search_button()


def _handle_voice_search_result(self, data: Dict[str, Any]):
    """Handle voice search result from Ollama brain or Thoth."""
    try:
        text = data.get('text', '').strip().upper()
        confidence = data.get('confidence', 0)
        
        logger.info(f"🎤 Voice result: {text} (confidence: {confidence})")
        
        if text and confidence > 0.5:
            # Set the search input
            self.asset_search_input.setText(text)
            
            # Trigger search
            self._search_asset()
            
            # Send to Ollama for context
            if self.event_bus:
                self.event_bus.publish('ollama.context.voice_search', {
                    'text': text,
                    'confidence': confidence,
                    'result': 'success'
                })
        else:
            self.search_results_label.setText(f"⚠️ Could not understand. Try again or type manually.")
            self.search_results_label.setVisible(True)
            
            if self.event_bus:
                self.event_bus.publish('ollama.context.voice_search', {
                    'text': text,
                    'confidence': confidence,
                    'result': 'failed'
                })
        
        # Reset button
        self._reset_voice_search_button()
        
    except Exception as e:
        logger.error(f"Error handling voice search result: {e}")
        self._reset_voice_search_button()


def _reset_voice_search_button(self):
    """Reset voice search button to normal state."""
    try:
        self.voice_search_button.setText("🎤")
        self.voice_search_button.setStyleSheet("""
            QPushButton {
                background-color: #00AAFF;
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0080FF;
            }
        """)
        self.asset_search_input.setPlaceholderText("Type symbol (e.g., BTC, AAPL, ETH) or speak...")
    except Exception as e:
        logger.debug(f"Error resetting voice button: {e}")


def _search_across_exchanges(self, symbol: str) -> List[Dict[str, Any]]:
    """Search for a symbol across all connected exchanges."""
    results = []
    
    try:
        # Search crypto exchanges
        if hasattr(self, '_exchanges') and self._exchanges:
            for exchange_name, exchange in self._exchanges.items():
                try:
                    if hasattr(exchange, 'markets') and exchange.markets:
                        # Check if symbol exists in markets
                        for market_symbol in exchange.markets.keys():
                            if symbol in market_symbol.upper():
                                results.append({
                                    'exchange': exchange_name,
                                    'symbol': market_symbol,
                                    'type': 'crypto',
                                    'market_info': exchange.markets[market_symbol]
                                })
                                break
                except Exception as e:
                    logger.debug(f"Error searching {exchange_name}: {e}")
        
        # Search stock brokers
        if hasattr(self, 'real_stock_executor') and self.real_stock_executor:
            try:
                # Check if symbol is a valid stock
                if hasattr(self.real_stock_executor, 'alpaca') and self.real_stock_executor.alpaca:
                    # Alpaca stocks
                    results.append({
                        'exchange': 'Alpaca',
                        'symbol': symbol,
                        'type': 'stock',
                        'market_info': {'type': 'US Stock'}
                    })
            except Exception as e:
                logger.debug(f"Error searching stocks: {e}")
        
        # Check cached prices
        if hasattr(self, '_asset_prices') and self._asset_prices:
            for cached_symbol in self._asset_prices.keys():
                if symbol in cached_symbol.upper() and not any(r['symbol'] == cached_symbol for r in results):
                    results.append({
                        'exchange': 'Cached',
                        'symbol': cached_symbol,
                        'type': 'unknown',
                        'market_info': self._asset_prices[cached_symbol]
                    })
        
    except Exception as e:
        logger.error(f"Error searching across exchanges: {e}")
    
    return results


def _get_asset_suggestions(self, query: str) -> List[str]:
    """Get asset suggestions based on partial query."""
    suggestions = []
    
    try:
        # Common crypto assets
        common_crypto = ['BTC', 'ETH', 'SOL', 'XRP', 'ADA', 'DOGE', 'MATIC', 'DOT', 'LINK', 'UNI']
        suggestions.extend([s for s in common_crypto if s.startswith(query)])
        
        # Common stocks
        common_stocks = ['AAPL', 'TSLA', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NFLX']
        suggestions.extend([s for s in common_stocks if s.startswith(query)])
        
        # Search in connected exchanges
        if hasattr(self, '_exchanges') and self._exchanges:
            for exchange in self._exchanges.values():
                try:
                    if hasattr(exchange, 'markets') and exchange.markets:
                        for market_symbol in list(exchange.markets.keys())[:100]:  # Limit to first 100
                            base = market_symbol.split('/')[0]
                            if base.startswith(query) and base not in suggestions:
                                suggestions.append(base)
                                if len(suggestions) >= 10:
                                    break
                except Exception:
                    pass
        
    except Exception as e:
        logger.debug(f"Error getting suggestions: {e}")
    
    return suggestions[:10]


def _select_searched_asset(self, symbol: str, results: List[Dict[str, Any]]):
    """Select and display info for a searched asset."""
    try:
        if not results:
            return
        
        # Use the first result
        result = results[0]
        exchange = result['exchange']
        full_symbol = result['symbol']
        asset_type = result['type']
        
        # Update current asset
        self._current_asset = symbol
        self._current_asset_type = asset_type
        
        # Request price data
        if self.event_bus:
            self.event_bus.publish('trading.price.request', {
                'symbol': full_symbol,
                'exchange': exchange,
                'asset_type': asset_type,
                'source': 'search'
            })
        
        # Update asset info display
        self._update_asset_info_display(symbol, results)
        
        logger.info(f"✅ Selected searched asset: {symbol} from {exchange}")
        
    except Exception as e:
        logger.error(f"Error selecting searched asset: {e}")


def _update_asset_info_display(self, symbol: str, results: List[Dict[str, Any]]):
    """Update the asset info display with detailed information."""
    try:
        if not results:
            return
        
        # Gather info from all results
        exchanges = [r['exchange'] for r in results]
        result = results[0]
        market_info = result.get('market_info', {})
        
        # Get price data if available
        price_data = self._asset_prices.get(result['symbol'], {})
        price = price_data.get('price', '--')
        volume_24h = price_data.get('volume_24h', '--')
        high_24h = price_data.get('high_24h', '--')
        low_24h = price_data.get('low_24h', '--')
        market_cap = price_data.get('market_cap', '--')
        
        # Format display
        info_text = (
            f"🏷️ Symbol: {symbol}\n"
            f"💹 Type: {result['type'].upper()}\n\n"
            f"📊 Market Cap: {self._format_number(market_cap)}\n"
            f"📈 24h Volume: {self._format_number(volume_24h)}\n"
            f"📉 24h High/Low: {self._format_number(high_24h)} / {self._format_number(low_24h)}\n"
            f"💹 Available on: {', '.join(exchanges)}\n"
            f"🔄 Last Updated: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        self.asset_info_display.setText(info_text)
        
        # Send to Ollama for analysis
        if self.event_bus:
            self.event_bus.publish('ollama.analyze.asset_info', {
                'symbol': symbol,
                'exchanges': exchanges,
                'price': price,
                'volume': volume_24h,
                'market_cap': market_cap,
                'type': result['type']
            })
        
    except Exception as e:
        logger.error(f"Error updating asset info display: {e}")


def _format_number(self, value) -> str:
    """Format a number for display."""
    try:
        if value == '--' or value is None:
            return '--'
        
        num = float(value)
        
        if num >= 1_000_000_000:
            return f"${num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"${num / 1_000_000:.2f}M"
        elif num >= 1_000:
            return f"${num / 1_000:.2f}K"
        else:
            return f"${num:.2f}"
    except:
        return str(value)


def init_asset_search_handlers(trading_tab_class):
    """Add asset search handler methods to TradingTab class."""
    trading_tab_class._search_asset = _search_asset
    trading_tab_class._on_search_text_changed = _on_search_text_changed
    trading_tab_class._voice_search_asset = _voice_search_asset
    trading_tab_class._handle_voice_search_result = _handle_voice_search_result
    trading_tab_class._reset_voice_search_button = _reset_voice_search_button
    trading_tab_class._search_across_exchanges = _search_across_exchanges
    trading_tab_class._get_asset_suggestions = _get_asset_suggestions
    trading_tab_class._select_searched_asset = _select_searched_asset
    trading_tab_class._update_asset_info_display = _update_asset_info_display
    trading_tab_class._format_number = _format_number
    logger.info("✅ Asset search handlers added to TradingTab class")
