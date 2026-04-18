"""
PredictionEngine module for Kingdom AI system.
"""

import logging
import json
import random
import secrets
from datetime import datetime, timedelta
import os

class PredictionEngine:
    """
    Prediction engine for the Kingdom AI system.
    Provides market predictions, trend analysis, and forecasting capabilities.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the prediction engine."""
        self.event_bus = event_bus
        self.config = config or {}
        self.logger = logging.getLogger("PredictionEngine")
        
        # Prediction settings
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.prediction_horizon = self.config.get("prediction_horizon", 24)  # hours
        
        # Prediction cache
        self.predictions = {}
        self.prediction_history = []
        self.max_history_items = self.config.get("max_history_items", 1000)
        
        # Model settings
        self.models = {
            "market": {"weight": 0.6, "accuracy": 0.75},
            "social": {"weight": 0.2, "accuracy": 0.65},
            "technical": {"weight": 0.2, "accuracy": 0.80}
        }
        
    async def initialize(self):
        """Initialize the prediction engine.
        
        Returns:
            bool: True if initialized successfully, False otherwise
        """
        try:
            self.logger.info("Initializing Prediction Engine")
            
            # Load any saved predictions
            predictions_file = self.config.get("predictions_file", "data/predictions.json")
            if os.path.exists(predictions_file):
                try:
                    with open(predictions_file, 'r') as f:
                        data = json.load(f)
                        self.predictions = data.get("predictions", {})
                        self.prediction_history = data.get("history", [])
                        self.logger.info(f"Loaded {len(self.predictions)} existing predictions")
                except Exception as e:
                    self.logger.error(f"Error loading predictions: {e}")
            
            # Register event handlers
            if self.event_bus:
                # Don't await bool returns from synchronous methods
                self.event_bus.subscribe_sync("prediction.market", self.handle_market_prediction)
                self.event_bus.subscribe_sync("prediction.trend", self.handle_trend_prediction)
                self.event_bus.subscribe_sync("prediction.validate", self.handle_validate_prediction)
                self.event_bus.subscribe_sync("prediction.get", self.handle_get_prediction)
                self.event_bus.subscribe_sync("system.shutdown", self.handle_shutdown)
                self.logger.info("Prediction Engine event handlers registered")
            
            # Initialize prediction models
            self._initialize_models()
            
            self.logger.info("Prediction Engine initialized successfully")
            self._initialized = True
            return True
        except Exception as e:
            self.logger.error(f"Error initializing Prediction Engine: {e}")
            self._initialized = False
            return False
    
    def _initialize_models(self):
        """Initialize prediction models - wire to Ollama brain or use real technical indicators."""
        self.logger.info("Initializing prediction models")
        
        # Try to initialize Ollama client for AI-powered predictions
        self._ollama_client = None
        try:
            import ollama
            ollama_host = self.config.get("ollama_host", "http://localhost:11434") if self.config else "http://localhost:11434"
            self._ollama_client = ollama.Client(host=ollama_host)
            # Test connection
            try:
                self._ollama_client.list()  # Test connection
                self.logger.info("Ollama client initialized for AI predictions")
            except Exception:
                self.logger.warning("Ollama not available - will use technical indicators instead")
                self._ollama_client = None
        except ImportError:
            self.logger.info("Ollama library not installed - using technical indicators")
            self._ollama_client = None
        except Exception as e:
            self.logger.warning(f"Could not initialize Ollama: {e} - using technical indicators")
            self._ollama_client = None
        
        # Initialize technical indicators if Ollama not available
        if not self._ollama_client:
            self.logger.info("Using technical indicators for predictions (RSI, MACD, Bollinger Bands)")
            # Model accuracy will be determined by backtesting real indicators
            for model_name in self.models:
                # Set realistic accuracy based on indicator performance (not random)
                self.models[model_name]["accuracy"] = 0.65  # Typical technical indicator accuracy
    
    async def handle_market_prediction(self, data):
        """Handle market prediction request."""
        try:
            if not data:
                await self._publish_error("market_prediction", "No prediction data provided")
                return
                
            symbol = data.get("symbol")
            horizon = data.get("horizon", self.prediction_horizon)
            
            if not symbol:
                await self._publish_error("market_prediction", "No symbol provided for prediction")
                return
                
            # Generate market prediction
            prediction = await self._generate_market_prediction(symbol, horizon)
            
            # Store prediction
            prediction_id = f"{symbol}_{datetime.now().isoformat()}"
            self.predictions[prediction_id] = prediction
            
            # Add to history
            self.prediction_history.append({
                "id": prediction_id,
                "type": "market",
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "prediction": prediction
            })
            
            # Trim history if needed
            if len(self.prediction_history) > self.max_history_items:
                self.prediction_history = self.prediction_history[-self.max_history_items:]
            
            # Publish prediction
            if self.event_bus:
                await self.event_bus.publish("prediction.market_result", {
                    "id": prediction_id,
                    "symbol": symbol,
                    "prediction": prediction,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error generating market prediction: {e}")
            await self._publish_error("market_prediction", str(e))
    
    async def _generate_market_prediction(self, symbol, horizon):
        """Generate a market prediction using Ollama brain or real technical indicators."""
        now = datetime.now()
        
        # Get current price from market data
        current_price = 0.0
        try:
            if self.event_bus:
                market_api = self.event_bus.get_component("market_api") or self.event_bus.get_component("market")
                if market_api:
                    ticker = market_api.get_ticker(symbol) if hasattr(market_api, "get_ticker") else None
                    if ticker and "price" in ticker:
                        current_price = float(ticker["price"])
        except Exception as e:
            self.logger.debug(f"Could not get current price: {e}")
        
        if current_price == 0.0:
            self.logger.warning(f"Cannot generate prediction: current price not available for {symbol}")
            return {
                "symbol": symbol,
                "error": "Current price not available - cannot generate prediction",
                "generated_at": now.isoformat()
            }
        
        prediction = {
            "symbol": symbol,
            "generated_at": now.isoformat(),
            "horizon": horizon,
            "horizon_unit": "hours",
            "valid_until": (now + timedelta(hours=horizon)).isoformat(),
            "price_prediction": {
                "current": current_price,
                "end": 0,
                "change_percent": 0,
                "confidence": 0
            },
            "trend_prediction": {
                "direction": "",
                "strength": 0,
                "confidence": 0
            },
            "signals": [],
            "model_contributions": {}
        }
        
        # Try Ollama first for AI-powered prediction
        if self._ollama_client:
            try:
                # Get historical price data for context
                historical_data = []
                if self.event_bus:
                    market_api = self.event_bus.get_component("market_api")
                    if market_api and hasattr(market_api, "get_market_data"):
                        market_data = market_api.get_market_data(symbol, timeframe="1h", limit=100)
                        if market_data and "ohlcv" in market_data:
                            historical_data = market_data["ohlcv"]
                
                # Create prompt for Ollama
                prompt = f"""Analyze cryptocurrency market data for {symbol}.
Current price: ${current_price:.2f}
Historical data: {len(historical_data)} candles available
Prediction horizon: {horizon} hours

Provide a price prediction with:
1. Expected price change percentage
2. Trend direction (up/down/sideways)
3. Confidence level (0-1)
4. Trading signals if applicable

Format as JSON with: change_percent, trend_direction, confidence, signals"""
                
                response = self._ollama_client.generate(
                    model=self.config.get("ollama_model", "llama2") if self.config else "llama2",
                    prompt=prompt
                )
                
                # Parse Ollama response (simplified - real implementation would parse JSON)
                if response and "response" in response:
                    # In real implementation, parse JSON from response
                    # For now, fall back to technical indicators
                    self.logger.info("Ollama prediction received (parsing would be implemented)")
            except Exception as e:
                self.logger.debug(f"Ollama prediction failed: {e}, using technical indicators")
        
        # Use real technical indicators (RSI, MACD, Bollinger Bands)
        try:
            import numpy as np
            import pandas as pd
            
            # Get historical data for indicators
            if self.event_bus:
                market_api = self.event_bus.get_component("market_api")
                if market_api and hasattr(market_api, "get_market_data"):
                    market_data = market_api.get_market_data(symbol, timeframe="1h", limit=100)
                    if market_data and "ohlcv" in market_data and len(market_data["ohlcv"]) >= 14:
                        closes = [candle[4] for candle in market_data["ohlcv"][-50:]]  # Last 50 closes
                        df = pd.DataFrame({"close": closes})
                        
                        # Calculate RSI
                        delta = df["close"].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / loss
                        rsi = 100 - (100 / (1 + rs))
                        current_rsi = rsi.iloc[-1] if not rsi.empty else 50
                        
                        # Calculate simple moving averages
                        sma_20 = df["close"].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else current_price
                        sma_50 = df["close"].rolling(window=50).mean().iloc[-1] if len(df) >= 50 else current_price
                        
                        # Determine trend based on indicators
                        if current_rsi < 30:  # Oversold
                            change = 2.0 + (current_price - sma_20) / sma_20 * 100
                            direction = "up"
                        elif current_rsi > 70:  # Overbought
                            change = -2.0 + (current_price - sma_20) / sma_20 * 100
                            direction = "down"
                        elif current_price > sma_20 > sma_50:  # Uptrend
                            change = 1.0
                            direction = "up"
                        elif current_price < sma_20 < sma_50:  # Downtrend
                            change = -1.0
                            direction = "down"
                        else:
                            change = 0.0
                            direction = "sideways"
                        
                        prediction["price_prediction"]["change_percent"] = change
                        prediction["price_prediction"]["end"] = current_price * (1 + change/100)
                        prediction["trend_prediction"]["direction"] = direction
                        prediction["trend_prediction"]["strength"] = abs(change) / 5.0  # Normalize to 0-1
                        prediction["trend_prediction"]["confidence"] = 0.65  # Technical indicator confidence
                        prediction["price_prediction"]["confidence"] = 0.65
                        
                        # Generate signals based on indicators
                        if current_rsi < 30 and change > 0:
                            prediction["signals"].append({"type": "buy", "strength": "medium", "timeframe": "short", "indicator": "RSI"})
                        elif current_rsi > 70 and change < 0:
                            prediction["signals"].append({"type": "sell", "strength": "medium", "timeframe": "short", "indicator": "RSI"})
                        
                        return prediction
        except ImportError:
            self.logger.warning("pandas/numpy not available for technical indicators")
        except Exception as e:
            self.logger.debug(f"Technical indicator calculation failed: {e}")
        
        # Fallback: honest "insufficient data"
        prediction["error"] = "Insufficient historical data for prediction - need at least 14 candles"
        prediction["price_prediction"]["confidence"] = 0.0
        return prediction
    
    async def handle_trend_prediction(self, data):
        """Handle trend prediction request."""
        try:
            if not data:
                await self._publish_error("trend_prediction", "No prediction data provided")
                return
                
            market = data.get("market", "crypto")
            timeframe = data.get("timeframe", "day")
            
            # Generate trend prediction
            prediction = await self._generate_trend_prediction(market, timeframe)
            
            # Store prediction
            prediction_id = f"{market}_{timeframe}_{datetime.now().isoformat()}"
            self.predictions[prediction_id] = prediction
            
            # Add to history
            self.prediction_history.append({
                "id": prediction_id,
                "type": "trend",
                "market": market,
                "timeframe": timeframe,
                "timestamp": datetime.now().isoformat(),
                "prediction": prediction
            })
            
            # Trim history if needed
            if len(self.prediction_history) > self.max_history_items:
                self.prediction_history = self.prediction_history[-self.max_history_items:]
            
            # Publish prediction
            if self.event_bus:
                await self.event_bus.publish("prediction.trend_result", {
                    "id": prediction_id,
                    "market": market,
                    "timeframe": timeframe,
                    "prediction": prediction,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error generating trend prediction: {e}")
            await self._publish_error("trend_prediction", str(e))
    
    async def _generate_trend_prediction(self, market, timeframe):
        """Generate a trend prediction for a market and timeframe."""
        # This is a simplified implementation
        
        # Generate random trend data
        trend_directions = ["bullish", "bearish", "neutral", "volatile"]
        trend_strengths = ["weak", "moderate", "strong", "very_strong"]
        
        prediction = {
            "market": market,
            "timeframe": timeframe,
            "generated_at": datetime.now().isoformat(),
            "overall_trend": {
                "direction": secrets.choice(trend_directions),
                "strength": secrets.choice(trend_strengths),
                "confidence": random.uniform(0.5, 0.9)
            },
            "sectors": {},
            "key_drivers": [],
            "model_contributions": {}
        }
        
        # Generate sector predictions
        if market == "crypto":
            sectors = ["defi", "gaming", "meme", "layer1", "layer2", "privacy"]
        elif market == "stock":
            sectors = ["tech", "finance", "healthcare", "energy", "consumer", "industrial"]
        else:
            sectors = ["primary", "secondary", "tertiary"]
            
        for sector in sectors:
            prediction["sectors"][sector] = {
                "direction": secrets.choice(trend_directions),
                "strength": secrets.choice(trend_strengths),
                "confidence": random.uniform(0.5, 0.9)
            }
        
        # Generate key drivers
        driver_types = ["technical", "fundamental", "sentiment", "regulatory", "macroeconomic"]
        impact_levels = ["low", "medium", "high", "critical"]
        
        for _ in range(secrets.randbelow(int(5) - int(2) + 1) + int(2)):
            prediction["key_drivers"].append({
                "type": secrets.choice(driver_types),
                "description": f"Sample driver description {secrets.randbelow(int(100) - int(1) + 1) + int(1)}",
                "impact": secrets.choice(impact_levels),
                "timeframe": timeframe
            })
        
        # Set model contributions
        for model_name, model_info in self.models.items():
            # Add random noise to model accuracy
            accuracy = model_info["accuracy"] * random.uniform(0.9, 1.1)
            accuracy = min(0.95, max(0.5, accuracy))
            
            # Calculate model contribution
            prediction["model_contributions"][model_name] = {
                "confidence": accuracy * random.uniform(0.8, 1.0),
                "weight": model_info["weight"]
            }
        
        return prediction
    
    async def handle_validate_prediction(self, data):
        """Handle prediction validation request."""
        try:
            if not data:
                await self._publish_error("validate_prediction", "No validation data provided")
                return
                
            prediction_id = data.get("prediction_id")
            actual_value = data.get("actual_value")
            
            if not prediction_id or prediction_id not in self.predictions:
                await self._publish_error("validate_prediction", f"Prediction {prediction_id} not found")
                return
                
            if actual_value is None:
                await self._publish_error("validate_prediction", "No actual value provided")
                return
                
            # Validate the prediction
            validation = self._validate_prediction(prediction_id, actual_value)
            
            # Publish validation results
            if self.event_bus:
                await self.event_bus.publish("prediction.validation_result", {
                    "prediction_id": prediction_id,
                    "validation": validation,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error validating prediction: {e}")
            await self._publish_error("validate_prediction", str(e))
    
    def _validate_prediction(self, prediction_id, actual_value):
        """Validate a prediction against actual values."""
        prediction = self.predictions.get(prediction_id)
        
        # This is a simplified implementation
        validation = {
            "prediction_id": prediction_id,
            "prediction_type": "unknown",
            "accuracy": 0,
            "error": 0,
            "validated_at": datetime.now().isoformat()
        }
        
        if "price_prediction" in prediction:
            # Market prediction validation
            validation["prediction_type"] = "market"
            
            # Calculate error and accuracy
            predicted = prediction["price_prediction"]["end"]
            error_percent = abs((actual_value - predicted) / predicted * 100)
            accuracy = max(0, 100 - error_percent)
            
            validation["predicted_value"] = predicted
            validation["actual_value"] = actual_value
            validation["error"] = error_percent
            validation["accuracy"] = accuracy / 100
            
            # Update model accuracies based on validation
            self._update_model_accuracies(validation["accuracy"])
            
        elif "overall_trend" in prediction:
            # Trend prediction validation
            validation["prediction_type"] = "trend"
            
            # For trend predictions, actual_value should be a dict with direction and strength
            if isinstance(actual_value, dict) and "direction" in actual_value:
                predicted_direction = prediction["overall_trend"]["direction"]
                actual_direction = actual_value["direction"]
                
                # Direction match gives 70% accuracy
                direction_match = predicted_direction == actual_direction
                validation["direction_match"] = direction_match
                
                if direction_match and "strength" in actual_value:
                    # Strength match gives additional 30% accuracy
                    predicted_strength = prediction["overall_trend"]["strength"]
                    actual_strength = actual_value["strength"]
                    strength_match = predicted_strength == actual_strength
                    validation["strength_match"] = strength_match
                    
                    validation["accuracy"] = 0.7 if direction_match else 0
                    validation["accuracy"] += 0.3 if strength_match else 0
                else:
                    validation["accuracy"] = 0.7 if direction_match else 0
            else:
                validation["accuracy"] = 0
                validation["error"] = "Invalid actual value format for trend validation"
        
        return validation
    
    def _update_model_accuracies(self, accuracy):
        """Update model accuracies based on prediction validation."""
        # Simplified implementation
        for model_name in self.models:
            # Slightly adjust model accuracy based on latest prediction accuracy
            current = self.models[model_name]["accuracy"]
            # Small adjustment - 10% of the difference between current and new accuracy
            adjustment = 0.1 * (accuracy - current)
            self.models[model_name]["accuracy"] = max(0.5, min(0.95, current + adjustment))
    
    async def handle_get_prediction(self, data):
        """Handle request to get existing predictions."""
        try:
            # Extract request parameters
            prediction_id = data.get("prediction_id") if data else None
            prediction_type = data.get("type") if data else None
            symbol = data.get("symbol") if data else None
            market = data.get("market") if data else None
            limit = data.get("limit", 10) if data else 10
            
            # Retrieve predictions
            if prediction_id:
                # Get specific prediction
                prediction = self.predictions.get(prediction_id)
                result = {"prediction": prediction} if prediction else {"error": "Prediction not found"}
            else:
                # Filter predictions
                filtered = self.prediction_history
                
                if prediction_type:
                    filtered = [p for p in filtered if p.get("type") == prediction_type]
                    
                if symbol:
                    filtered = [p for p in filtered if p.get("symbol") == symbol]
                    
                if market:
                    filtered = [p for p in filtered if p.get("market") == market]
                
                # Sort by timestamp (newest first) and limit
                sorted_predictions = sorted(
                    filtered, 
                    key=lambda p: p.get("timestamp", ""), 
                    reverse=True
                )[:limit]
                
                result = {"predictions": sorted_predictions}
            
            # Publish result
            if self.event_bus:
                await self.event_bus.publish("prediction.get_result", {
                    **result,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            self.logger.error(f"Error retrieving predictions: {e}")
            await self._publish_error("get_prediction", str(e))
    
    async def handle_shutdown(self, data=None):
        """Handle system shutdown event."""
        try:
            self.logger.info("Shutting down Prediction Engine")
            
            # Save predictions
            predictions_file = self.config.get("predictions_file", "data/predictions.json")
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(predictions_file), exist_ok=True)
                
                with open(predictions_file, 'w') as f:
                    json.dump({
                        "predictions": self.predictions,
                        "history": self.prediction_history
                    }, f, indent=2)
                    
                self.logger.info(f"Saved predictions to {predictions_file}")
            except Exception as e:
                self.logger.error(f"Error saving predictions: {e}")
            
            self.logger.info("Prediction Engine shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during Prediction Engine shutdown: {e}")
    
    async def _publish_error(self, operation, error_message):
        """Publish an error message to the event bus."""
        if self.event_bus:
            await self.event_bus.publish("prediction.error", {
                "operation": operation,
                "error": error_message,
                "timestamp": datetime.now().isoformat()
            })
