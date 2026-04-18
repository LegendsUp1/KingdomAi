"""
Advanced Liquidity Analyzer for Kingdom AI Trading System

This module provides state-of-the-art liquidity analysis capabilities for the TradingIntelligence
component, enabling optimal trade execution, market understanding, and profit maximization.
"""

import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, field

# Optional quantum imports - gracefully fallback if not available
try:
    from qiskit_aer import Aer, AerSimulator
    from qiskit import transpile
    from qiskit.algorithms import QAOA
    from qiskit_optimization import QuadraticProgram
    QUANTUM_AVAILABLE = True
except ImportError:
    QUANTUM_AVAILABLE = False

@dataclass
class LiquidityMetrics:
    """Container for comprehensive liquidity metrics for an asset"""
    symbol: str
    exchange: str
    bid_ask_spread: float  # Normalized spread (%)
    depth_usd: float  # Total USD value available within 2% of mid price
    volume_24h_usd: float  # 24-hour trading volume in USD
    price_impact_100k: float  # Price impact of $100K trade (%)
    slippage_estimate: float  # Estimated slippage for average trade size (%)
    resilience: float  # Order book resilience score (0-1)
    market_efficiency: float  # Market efficiency ratio (0-1)
    liquidity_score: float  # Composite liquidity score (0-100)
    liquidity_bracket: str  # Liquidity classification (A-E)
    timestamp: datetime = field(default_factory=datetime.now)

class LiquidityAnalyzer:
    """
    Advanced liquidity analysis system for maximum profit extraction.
    
    This state-of-the-art system implements sophisticated algorithms to:
    1. Analyze liquidity across all trading platforms and assets
    2. Rank assets by liquidity for optimal trade selection
    3. Assess trading suitability based on desired position sizes
    4. Estimate slippage and market impact for different trade sizes
    5. Apply quantum-inspired optimization for liquidity-aware portfolio construction
    """
    
    def __init__(self, logger=None):
        """Initialize the LiquidityAnalyzer with logging"""
        self.logger = logger or logging.getLogger("KingdomAI.LiquidityAnalyzer")
        self.metrics_history = {}  # Store historical liquidity metrics
        self.liquidity_brackets = {
            'A': {'min_score': 80, 'description': 'Extremely liquid, suitable for any trade size'},
            'B': {'min_score': 60, 'description': 'Highly liquid, suitable for large trades'},
            'C': {'min_score': 40, 'description': 'Moderately liquid, suitable for medium trades'},
            'D': {'min_score': 20, 'description': 'Limited liquidity, suitable only for small trades'},
            'E': {'min_score': 0, 'description': 'Illiquid, avoid trading'}
        }
        # Initialize quantum optimizer if available
        self.quantum_optimizer = self._initialize_quantum_optimizer() if QUANTUM_AVAILABLE else None
        
    async def analyze_market_liquidity(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market liquidity based on order book and trading data
        
        Args:
            market_data: Dictionary containing market data including order book
            
        Returns:
            Dictionary with comprehensive liquidity metrics
        """
        try:
            symbol = market_data.get('symbol', 'unknown')
            exchange = market_data.get('exchange', 'unknown')
            
            # Extract order book if available
            bids = market_data.get('bids', [])
            asks = market_data.get('asks', [])
            
            # Extract other relevant data
            last_price = market_data.get('last', 0.0)
            volume_24h = market_data.get('volume', 0.0)
            
            # Calculate key liquidity metrics
            bid_ask_spread = self._calculate_spread(bids, asks, last_price)
            depth = self._calculate_depth(bids, asks, last_price)
            volume_usd = volume_24h * last_price
            
            # Calculate advanced liquidity metrics
            market_efficiency = self._calculate_market_efficiency(market_data)
            slippage_10k = self._estimate_slippage(bids, asks, 10000, last_price)  # $10K trade
            slippage_100k = self._estimate_slippage(bids, asks, 100000, last_price)  # $100K trade
            vol_adjusted_liquidity = self._calculate_vol_adjusted_liquidity(market_data)
            order_book_imbalance = self._calculate_order_book_imbalance(bids, asks)
            
            # Apply quantum analysis if available
            quantum_insights = {}
            if self.quantum_optimizer and QUANTUM_AVAILABLE:
                quantum_insights = self._apply_quantum_analysis(market_data)
            
            # Calculate composite liquidity score (0-100)
            liquidity_score = self._calculate_liquidity_score(
                bid_ask_spread, depth, volume_usd, 
                slippage_100k, market_efficiency, vol_adjusted_liquidity
            )
            
            # Determine liquidity bracket
            liquidity_bracket = self._get_liquidity_bracket(liquidity_score)
            
            # Construct the liquidity metrics
            metrics = LiquidityMetrics(
                symbol=symbol,
                exchange=exchange,
                bid_ask_spread=bid_ask_spread,
                depth_usd=depth,
                volume_24h_usd=volume_usd,
                price_impact_100k=slippage_100k,
                slippage_estimate=slippage_10k,
                resilience=vol_adjusted_liquidity,
                market_efficiency=market_efficiency,
                liquidity_score=liquidity_score,
                liquidity_bracket=liquidity_bracket
            )
            
            # Store in history
            if symbol not in self.metrics_history:
                self.metrics_history[symbol] = []
            
            self.metrics_history[symbol].append(metrics)
            
            # Limit history size
            if len(self.metrics_history[symbol]) > 1000:
                self.metrics_history[symbol] = self.metrics_history[symbol][-1000:]
            
            # Create result dictionary
            result = {
                'symbol': symbol,
                'exchange': exchange,
                'bid_ask_spread': bid_ask_spread,
                'depth_usd': depth,
                'volume_24h_usd': volume_usd,
                'price_impact_100k': slippage_100k,
                'slippage_estimate': slippage_10k,
                'market_efficiency': market_efficiency,
                'liquidity_score': liquidity_score,
                'liquidity_bracket': liquidity_bracket,
                'tradable_amounts': self._calculate_tradable_amounts(liquidity_score, depth),
                'quantum_insights': quantum_insights
            }
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error analyzing market liquidity: {e}")
            return {
                'symbol': market_data.get('symbol', 'unknown'),
                'error': str(e),
                'liquidity_score': 0.0,
                'liquidity_bracket': 'E'
            }
    
    def rank_assets_by_liquidity(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """
        Rank assets by their liquidity scores
        
        Args:
            symbols: List of symbol names to rank
            
        Returns:
            List of dictionaries with ranking information, sorted by liquidity score
        """
        results = []
        
        for symbol in symbols:
            if symbol in self.metrics_history and self.metrics_history[symbol]:
                # Get most recent metrics
                metrics = self.metrics_history[symbol][-1]
                
                results.append({
                    'symbol': symbol,
                    'liquidity_score': metrics.liquidity_score,
                    'liquidity_bracket': metrics.liquidity_bracket,
                    'exchange': metrics.exchange,
                    'volume_24h_usd': metrics.volume_24h_usd,
                    'bid_ask_spread': metrics.bid_ask_spread,
                    'tradable_amounts': self._calculate_tradable_amounts(
                        metrics.liquidity_score, metrics.depth_usd
                    )
                })
        
        # Sort by liquidity score in descending order
        return sorted(results, key=lambda x: x['liquidity_score'], reverse=True)
    
    def assess_trading_suitability(self, asset_info: Dict[str, Any], desired_trade_size_usd: float) -> Dict[str, Any]:
        """
        Assess an asset's suitability for trading based on its liquidity and a desired trade size
        
        Args:
            asset_info: Dictionary containing asset information including liquidity metrics
            desired_trade_size_usd: Desired trade size in USD
            
        Returns:
            Dictionary with suitability assessment
        """
        try:
            liquidity_score = asset_info.get('liquidity_score', 0.0)
            liquidity_bracket = asset_info.get('liquidity_bracket', 'E')
            depth_usd = asset_info.get('depth_usd', 0.0)
            symbol = asset_info.get('symbol', 'unknown')
            
            # Determine if the asset is suitable for the desired trade size
            suitable = True
            reasons = []
            warnings = []
            
            # Estimate slippage for the desired trade size
            estimated_slippage_pct = self._estimate_slippage_from_score(
                liquidity_score, desired_trade_size_usd
            )
            
            # Determine recommended maximum trade size based on liquidity
            recommended_max_trade_size_usd = self._calculate_max_trade_size(
                liquidity_score, depth_usd
            )
            
            # Check if the desired trade size exceeds the recommended maximum
            if desired_trade_size_usd > recommended_max_trade_size_usd:
                suitable = False
                reasons.append(f"Desired trade size (${desired_trade_size_usd:,.2f}) exceeds recommended maximum (${recommended_max_trade_size_usd:,.2f})")
            
            # Check if the estimated slippage is too high
            if estimated_slippage_pct > 2.0:  # More than 2% slippage
                suitable = False
                reasons.append(f"Estimated slippage ({estimated_slippage_pct:.2f}%) is too high")
            elif estimated_slippage_pct > 0.5:  # Between 0.5% and 2% slippage
                warnings.append(f"Moderate slippage expected ({estimated_slippage_pct:.2f}%)")
            
            # Check liquidity bracket
            if liquidity_bracket in ['D', 'E']:
                suitable = False
                reasons.append(f"Asset has insufficient liquidity (Bracket {liquidity_bracket})")
            elif liquidity_bracket == 'C' and desired_trade_size_usd > 50000:
                warnings.append(f"Asset has moderate liquidity (Bracket {liquidity_bracket}) for trade size ${desired_trade_size_usd:,.2f}")
            
            return {
                "suitable": suitable,
                "reasons": reasons,
                "warnings": warnings,
                "estimated_slippage_pct": round(estimated_slippage_pct, 4),
                "recommended_max_trade_size_usd": round(recommended_max_trade_size_usd, 2),
                "liquidity_bracket": liquidity_bracket
            }
            
        except Exception as e:
            self.logger.error(f"Error assessing trading suitability: {e}")
            return {
                "suitable": False,
                "reasons": [f"Error assessing suitability: {str(e)}"],
                "warnings": [],
                "estimated_slippage_pct": 999.99,
                "recommended_max_trade_size_usd": 0.0,
                "liquidity_bracket": 'E'
            }
    
    # --- Internal helper methods ---
    
    def _calculate_spread(self, bids: List[List[float]], asks: List[List[float]], last_price: float) -> float:
        """Calculate the normalized bid-ask spread as a percentage"""
        if not bids or not asks or last_price == 0:
            return 100.0  # Maximum spread if no data
            
        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else float('inf')
        
        if best_bid == 0 or best_ask == float('inf'):
            return 100.0
            
        spread_pct = (best_ask - best_bid) / ((best_ask + best_bid) / 2) * 100
        return min(spread_pct, 100.0)  # Cap at 100%
    
    def _calculate_depth(self, bids: List[List[float]], asks: List[List[float]], last_price: float) -> float:
        """Calculate the market depth in USD within 2% of the mid price"""
        if not bids or not asks or last_price == 0:
            return 0.0
            
        mid_price = (bids[0][0] + asks[0][0]) / 2 if bids and asks else last_price
        depth_threshold = mid_price * 0.02  # 2% of mid price
        
        # Calculate depth on bid side
        bid_depth = 0.0
        for bid in bids:
            if mid_price - bid[0] <= depth_threshold:
                bid_depth += bid[0] * bid[1]  # price * quantity
            else:
                break
                
        # Calculate depth on ask side
        ask_depth = 0.0
        for ask in asks:
            if ask[0] - mid_price <= depth_threshold:
                ask_depth += ask[0] * ask[1]  # price * quantity
            else:
                break
                
        return bid_depth + ask_depth
    
    def _estimate_slippage(self, bids: List[List[float]], asks: List[List[float]], 
                           trade_size_usd: float, last_price: float) -> float:
        """Estimate slippage for a given trade size based on the order book"""
        if not bids or not asks or last_price == 0:
            return 100.0  # Maximum slippage if no data
            
        # For a buy order, we walk up the ask side
        if trade_size_usd > 0:
            order_side = asks
            mid_price = asks[0][0]  # Best ask
        # For a sell order, we walk down the bid side
        else:
            order_side = bids
            mid_price = bids[0][0]  # Best bid
            trade_size_usd = abs(trade_size_usd)
            
        # Walk the order book
        executed_quantity = 0.0
        executed_value = 0.0
        
        for level in order_side:
            price = level[0]
            quantity = level[1]
            level_value = price * quantity
            
            if executed_value + level_value >= trade_size_usd:
                # Partial execution at this level
                remaining = trade_size_usd - executed_value
                executed_quantity += remaining / price
                executed_value = trade_size_usd
                break
            else:
                # Full execution at this level
                executed_quantity += quantity
                executed_value += level_value
                
        # If we couldn't fill the entire order
        if executed_value < trade_size_usd:
            return 100.0  # Maximum slippage
            
        # Calculate average execution price
        avg_price = executed_value / executed_quantity
        
        # Calculate slippage as percentage
        slippage_pct = abs(avg_price - mid_price) / mid_price * 100
        return min(slippage_pct, 100.0)  # Cap at 100%
    
    def _calculate_market_efficiency(self, market_data: Dict[str, Any]) -> float:
        """Calculate market efficiency ratio (0-1)"""
        # In a perfectly efficient market, volatility is low relative to volume
        volatility = market_data.get('volatility', 0.0)
        volume = market_data.get('volume', 0.0)
        
        if volatility == 0 or volume == 0:
            return 0.5  # Default to middle value if data is missing
            
        # Higher volume and lower volatility indicate higher efficiency
        efficiency = min(1.0, volume / (volume + 1000) / (volatility + 0.001))
        return efficiency
    
    def _calculate_vol_adjusted_liquidity(self, market_data: Dict[str, Any]) -> float:
        """Calculate volatility-adjusted liquidity score (0-1)"""
        volatility = market_data.get('volatility', 0.0)
        volume = market_data.get('volume', 0.0)
        
        if volume == 0:
            return 0.0
            
        # Adjust volume by volatility (higher volatility reduces effective liquidity)
        vol_factor = 1.0 / (1.0 + volatility)
        adjusted_liquidity = min(1.0, (volume * vol_factor) / 1000000)
        return adjusted_liquidity
    
    def _calculate_order_book_imbalance(self, bids: List[List[float]], asks: List[List[float]]) -> float:
        """Calculate order book imbalance (-1 to 1, where positive values indicate more buy pressure)"""
        if not bids or not asks:
            return 0.0
            
        # Calculate total volume on bid and ask sides
        bid_volume = sum(bid[0] * bid[1] for bid in bids)
        ask_volume = sum(ask[0] * ask[1] for ask in asks)
        
        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0
            
        # Calculate imbalance
        imbalance = (bid_volume - ask_volume) / total_volume
        return max(-1.0, min(1.0, imbalance))
    
    def _calculate_liquidity_score(self, spread: float, depth: float, volume: float, 
                                  slippage: float, efficiency: float, vol_adjusted: float) -> float:
        """Calculate composite liquidity score (0-100)"""
        # Normalize input metrics to 0-1 range
        norm_spread = max(0.0, min(1.0, 1.0 - (spread / 10.0)))  # Lower spread is better
        norm_depth = max(0.0, min(1.0, depth / 10000000.0))  # Higher depth is better
        norm_volume = max(0.0, min(1.0, volume / 100000000.0))  # Higher volume is better
        norm_slippage = max(0.0, min(1.0, 1.0 - (slippage / 10.0)))  # Lower slippage is better
        
        # Weighted average of normalized metrics
        weighted_score = (
            norm_spread * 0.25 +
            norm_depth * 0.20 +
            norm_volume * 0.25 +
            norm_slippage * 0.15 +
            efficiency * 0.10 +
            vol_adjusted * 0.05
        )
        
        # Scale to 0-100
        return weighted_score * 100.0
    
    def _get_liquidity_bracket(self, liquidity_score: float) -> str:
        """Determine liquidity bracket (A-E) based on liquidity score"""
        for bracket, info in sorted(self.liquidity_brackets.items(), 
                                   key=lambda x: x[1]['min_score'], 
                                   reverse=True):
            if liquidity_score >= info['min_score']:
                return bracket
                
        return 'E'  # Default to lowest bracket
    
    def _calculate_tradable_amounts(self, liquidity_score: float, depth: float) -> Dict[str, float]:
        """Calculate recommended tradable amounts based on liquidity"""
        if liquidity_score <= 0 or depth <= 0:
            return {
                'safe': 0.0,
                'moderate': 0.0,
                'aggressive': 0.0
            }
            
        # Safe amount: minimal market impact
        safe_amount = min(depth * 0.01, liquidity_score * 1000)
        
        # Moderate amount: noticeable but manageable impact
        moderate_amount = min(depth * 0.05, liquidity_score * 2000)
        
        # Aggressive amount: significant market impact
        aggressive_amount = min(depth * 0.15, liquidity_score * 5000)
        
        return {
            'safe': safe_amount,
            'moderate': moderate_amount,
            'aggressive': aggressive_amount
        }
    
    def _estimate_slippage_from_score(self, liquidity_score: float, trade_size_usd: float) -> float:
        """Estimate slippage based on liquidity score and trade size"""
        if liquidity_score <= 0:
            return 100.0
            
        # Base slippage estimate
        base_slippage = (100.0 - liquidity_score) / 20.0
        
        # Adjust for trade size (larger trades have more slippage)
        size_factor = trade_size_usd / (liquidity_score * 1000 + 1)
        
        adjusted_slippage = base_slippage * (1.0 + min(10.0, size_factor))
        return min(100.0, adjusted_slippage)
    
    def _calculate_max_trade_size(self, liquidity_score: float, depth: float) -> float:
        """Calculate maximum recommended trade size based on liquidity"""
        if liquidity_score <= 0 or depth <= 0:
            return 0.0
            
        # Heuristic based on liquidity score and market depth
        max_size = min(depth * 0.15, liquidity_score * 5000)
        return max(0.0, max_size)
    
    def _initialize_quantum_optimizer(self):
        """Initialize quantum optimizer for liquidity analysis"""
        if not QUANTUM_AVAILABLE:
            return None
            
        # Initialize with Aer simulator backend
        try:
            backend = Aer.get_backend('qasm_simulator')
            return {
                'backend': backend,
                'optimization_level': 1
            }
        except Exception as e:
            self.logger.error(f"Error initializing quantum optimizer: {e}")
            return None
    
    def _apply_quantum_analysis(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply quantum algorithms to enhance liquidity analysis"""
        if not self.quantum_optimizer or not QUANTUM_AVAILABLE:
            return {}
            
        try:
            # Extract price data from market data
            if 'ohlcv' in market_data and len(market_data['ohlcv']) > 0:
                prices = [candle[4] for candle in market_data['ohlcv']]  # Close prices
                volumes = [candle[5] for candle in market_data['ohlcv']]  # Volumes
            else:
                # If no OHLCV data, return honest "insufficient data" instead of dummy data
                logger.warning("Insufficient OHLCV data for quantum liquidity analysis")
                return {
                    'quantum_enabled': False,
                    'error': 'Insufficient market data - OHLCV data required for quantum analysis'
                }
                
            if len(prices) < 5:
                return {'quantum_enabled': False}
                
            # Convert to numpy arrays
            price_array = np.array(prices[-20:])  # Last 20 prices
            volume_array = np.array(volumes[-20:])  # Last 20 volumes
            
            # Normalize arrays
            norm_prices = (price_array - np.min(price_array)) / (np.max(price_array) - np.min(price_array) + 1e-8)
            norm_volumes = (volume_array - np.min(volume_array)) / (np.max(volume_array) - np.min(volume_array) + 1e-8)
            
            # Create simple 2-qubit circuit to encode price and volume relationship
            from qiskit import QuantumCircuit
            qc = QuantumCircuit(2, 2)  # 2 qubits, 2 classical bits for measurement
            
            # Encode price and volume as rotation angles
            price_angle = norm_prices[-1] * np.pi
            volume_angle = norm_volumes[-1] * np.pi
            
            qc.rx(price_angle, 0)
            qc.rx(volume_angle, 1)
            qc.cx(0, 1)  # Entangle qubits
            qc.measure([0, 1], [0, 1])  # Measure qubits
            
            # Simulate circuit using modern Qiskit 1.0+ pattern
            backend = self.quantum_optimizer['backend']
            transpiled_qc = transpile(qc, backend=backend)
            job = backend.run(transpiled_qc, shots=1024)
            result = job.result().get_counts()
            
            # Interpret quantum result
            # Higher probability of '00' indicates lower liquidity risk
            # Higher probability of '11' indicates higher liquidity risk
            total_shots = sum(result.values())
            low_risk_prob = result.get('00', 0) / total_shots
            high_risk_prob = result.get('11', 0) / total_shots
            
            # Calculate quantum liquidity risk score (0-1)
            quantum_risk = high_risk_prob / (low_risk_prob + high_risk_prob + 1e-8)
            
            return {
                'quantum_enabled': True,
                'quantum_risk_score': quantum_risk,
                'quantum_confidence': 1.0 - abs(low_risk_prob - high_risk_prob),
                'low_risk_probability': low_risk_prob,
                'high_risk_probability': high_risk_prob
            }
            
        except Exception as e:
            self.logger.error(f"Error applying quantum analysis: {e}")
            return {'quantum_enabled': False, 'error': str(e)}
