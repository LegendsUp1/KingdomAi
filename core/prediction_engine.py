#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PredictionEngine component for Kingdom AI.
Handles market prediction and trend forecasting.
"""

import os
import logging
import json
import asyncio
from datetime import datetime

# Try to import ML libraries with proper error handling
SKLEARN_AVAILABLE = False
try:
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.linear_model import LinearRegression
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.metrics import mean_squared_error, mean_absolute_error
    SKLEARN_AVAILABLE = True
    logging.info("Scikit-learn loaded successfully")
except ImportError as e:
    logging.warning(f"Scikit-learn import error: {e}. ML predictions will be limited.")
except Exception as e:
    logging.warning(f"Unexpected error loading scikit-learn: {e}. ML predictions will be limited.")

# Try to import deep learning libraries with proper error handling
# CRITICAL: Catch ALL exceptions including AttributeError from JAX/ml_dtypes compatibility issues
TENSORFLOW_AVAILABLE = False
tf = None
Sequential = None
load_model = None
save_model = None
Dense = None
LSTM = None
Dropout = None
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model, save_model
    from tensorflow.keras.layers import Dense, LSTM, Dropout
    TENSORFLOW_AVAILABLE = True
    # Configure TensorFlow to avoid warnings
    tf.get_logger().setLevel('ERROR')
    logging.info("TensorFlow loaded successfully")
except (ImportError, AttributeError, ModuleNotFoundError) as e:
    logging.warning(f"TensorFlow import error: {e}. Deep learning predictions will be disabled.")
except Exception as e:
    logging.warning(f"Unexpected error loading TensorFlow: {e}. Deep learning predictions will be disabled.")

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class PredictionEngine(BaseComponent):
    """
    Component for market prediction and trend forecasting.
    Implements various prediction models and techniques.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the PredictionEngine component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "PredictionEngine"
        self.description = "Market prediction and trend forecasting engine"
        
        # Configuration
        self.models_dir = self.config.get("models_dir", os.path.join(os.path.dirname(__file__), "..", "data", "models"))
        self.prediction_interval = self.config.get("prediction_interval", 3600)  # seconds
        self.default_timeframes = self.config.get("timeframes", ["1h", "4h", "1d", "1w"])
        self.default_prediction_horizons = self.config.get("prediction_horizons", [1, 3, 7, 14])  # days
        self.auto_train = self.config.get("auto_train", True)
        self.training_interval = self.config.get("training_interval", 86400)  # seconds (1 day)
        
        # Model configurations
        self.model_configs = self.config.get("model_configs", {
            "linear": {
                "enabled": True,
                "weight": 0.2
            },
            "random_forest": {
                "enabled": True,
                "weight": 0.3,
                "params": {
                    "n_estimators": 100,
                    "max_depth": 10
                }
            },
            "gradient_boosting": {
                "enabled": True,
                "weight": 0.3,
                "params": {
                    "n_estimators": 100,
                    "learning_rate": 0.1,
                    "max_depth": 5
                }
            },
            "lstm": {
                "enabled": TENSORFLOW_AVAILABLE,
                "weight": 0.2,
                "params": {
                    "units": 50,
                    "dropout": 0.2,
                    "epochs": 50,
                    "batch_size": 32
                }
            }
        })
        
        # State
        self.models = {}
        self.scalers = {}
        self.predictions = {}
        self.historical_accuracy = {}
        self.features = {}
        self.is_training = False
        self.training_task = None
        self.prediction_task = None
        self.last_trained = {}
        self.last_predicted = {}
        self.market_data = {}
        
        # Feature configurations
        self.feature_configs = self.config.get("feature_configs", {
            "price": True,
            "volume": True,
            "technical_indicators": {
                "enabled": True,
                "sma": [7, 21, 50],
                "ema": [7, 21, 50],
                "rsi": [14],
                "macd": True,
                "bollinger": [20, 2.0],
                "stochastic": [14, 3, 3]
            }
        })
        
        # Dependencies
        self.market_api = None
        self.meta_learning = None
        
    async def initialize(self):
        """Initialize the PredictionEngine component."""
        logger.info("Initializing PredictionEngine")
        
        # Create models directory if it doesn't exist
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Subscribe to events
        self.event_bus.subscribe("prediction.request", self.on_prediction_request)
        self.event_bus.subscribe("prediction.train", self.on_train_request)
        self.event_bus.subscribe("prediction.evaluate", self.on_evaluate_request)
        self.event_bus.subscribe("market.data.update", self.on_market_data_update)
        self.event_bus.subscribe("system.shutdown", self.on_shutdown)
        
        # Load trained models if they exist
        await self._load_models()
        
        # Start prediction task if auto-predict is enabled
        if self.config.get("auto_predict", True):
            self.prediction_task = asyncio.create_task(self._predict_periodically())
        
        # Start training task if auto-train is enabled
        if self.auto_train:
            self.training_task = asyncio.create_task(self._train_periodically())
        
        logger.info("PredictionEngine initialized")
        return True
        
    async def _load_models(self):
        """Load trained models from disk."""
        try:
            model_info_path = os.path.join(self.models_dir, "model_info.json")
            if os.path.exists(model_info_path):
                with open(model_info_path, "r") as f:
                    model_info = json.load(f)
                
                # Load last training times
                self.last_trained = model_info.get("last_trained", {})
                
                # Load historical accuracy
                self.historical_accuracy = model_info.get("accuracy", {})
                
                # Load each model based on type
                for symbol in model_info.get("models", {}):
                    self.models[symbol] = {}
                    self.scalers[symbol] = {}
                    
                    for timeframe in model_info["models"][symbol]:
                        self.models[symbol][timeframe] = {}
                        self.scalers[symbol][timeframe] = {}
                        
                        for model_type, model_path in model_info["models"][symbol][timeframe].items():
                            if model_type == "linear" and SKLEARN_AVAILABLE:
                                model_file = os.path.join(self.models_dir, model_path)
                                if os.path.exists(model_file):
                                    with open(model_file, "rb") as f:
                                        self.models[symbol][timeframe][model_type] = pickle.load(f)
                            
                            elif model_type in ["random_forest", "gradient_boosting"] and SKLEARN_AVAILABLE:
                                model_file = os.path.join(self.models_dir, model_path)
                                if os.path.exists(model_file):
                                    with open(model_file, "rb") as f:
                                        self.models[symbol][timeframe][model_type] = pickle.load(f)
                            
                            elif model_type == "lstm" and TENSORFLOW_AVAILABLE:
                                model_dir = os.path.join(self.models_dir, model_path)
                                if os.path.exists(model_dir):
                                    self.models[symbol][timeframe][model_type] = load_model(model_dir)
                
                # Load scalers
                scalers_path = os.path.join(self.models_dir, "scalers.pkl")
                if os.path.exists(scalers_path):
                    with open(scalers_path, "rb") as f:
                        self.scalers = pickle.load(f)
                
                logger.info(f"Loaded models for {len(self.models)} symbols")
            else:
                logger.info("No saved models found")
        
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            # Continue with empty models
    
    async def _save_models(self):
        """Save trained models to disk."""
        try:
            # Create model info structure
            model_info = {
                "models": {},
                "last_trained": self.last_trained,
                "accuracy": self.historical_accuracy,
                "last_saved": datetime.now().isoformat()
            }
            
            # Save each model based on type
            for symbol in self.models:
                model_info["models"][symbol] = {}
                
                for timeframe in self.models[symbol]:
                    model_info["models"][symbol][timeframe] = {}
                    
                    for model_type, model in self.models[symbol][timeframe].items():
                        if model_type == "linear" and SKLEARN_AVAILABLE:
                            model_path = f"{symbol}_{timeframe}_{model_type}.pkl"
                            with open(os.path.join(self.models_dir, model_path), "wb") as f:
                                pickle.dump(model, f)
                            model_info["models"][symbol][timeframe][model_type] = model_path
                        
                        elif model_type in ["random_forest", "gradient_boosting"] and SKLEARN_AVAILABLE:
                            model_path = f"{symbol}_{timeframe}_{model_type}.pkl"
                            with open(os.path.join(self.models_dir, model_path), "wb") as f:
                                pickle.dump(model, f)
                            model_info["models"][symbol][timeframe][model_type] = model_path
                        
                        elif model_type == "lstm" and TENSORFLOW_AVAILABLE:
                            model_path = f"{symbol}_{timeframe}_{model_type}"
                            model_dir = os.path.join(self.models_dir, model_path)
                            model.save(model_dir)
                            model_info["models"][symbol][timeframe][model_type] = model_path
            
            # Save model info
            with open(os.path.join(self.models_dir, "model_info.json"), "w") as f:
                json.dump(model_info, f, indent=2)
            
            # Save scalers
            with open(os.path.join(self.models_dir, "scalers.pkl"), "wb") as f:
                pickle.dump(self.scalers, f)
            
            logger.info(f"Saved models for {len(self.models)} symbols")
        
        except Exception as e:
            logger.error(f"Error saving models: {e}")
