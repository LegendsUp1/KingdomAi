#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
AnalyticsEngine component for Kingdom AI.
Responsible for data analysis, tracking, and visualization for trading and mining metrics.
"""

import os
import logging
import json
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from io import BytesIO
import base64

from core.base_component import BaseComponent

logger = logging.getLogger(__name__)

class AnalyticsEngine(BaseComponent):
    """
    Component for analytics and data visualization.
    Provides trading statistics, performance metrics, and trend analysis.
    """
    
    def __init__(self, event_bus, config=None):
        """
        Initialize the AnalyticsEngine component.
        
        Args:
            event_bus: The event bus for component communication
            config: Configuration dictionary
        """
        super().__init__(event_bus, config)
        self.name = "AnalyticsEngine"
        self.description = "Analytics and visualization engine"
        
        # Configuration
        self.data_dir = self.config.get("data_dir", os.path.join(os.path.dirname(__file__), "..", "data", "analytics"))
        self.history_limit = self.config.get("history_limit", 1000)
        self.update_interval = self.config.get("update_interval", 60)  # seconds
        
        # Data storage
        self.market_data = {}  # Symbol -> OHLCV data
        self.trade_history = []  # List of trade records
        self.mining_stats = {}  # Coin -> mining statistics
        self.portfolio_history = []  # Historical portfolio value
        self.prediction_accuracy = {}  # Model -> accuracy metrics
        
        # Tasks
        self.update_task = None
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize the AnalyticsEngine component."""
        logger.info("Initializing AnalyticsEngine")
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Load saved analytics data
        await self._load_data()
        
        # Subscribe to events
        self.event_bus.subscribe_sync("market.update", self.on_market_update)
        self.event_bus.subscribe_sync("trading.order.completed", self.on_trade_completed)
        self.event_bus.subscribe_sync("wallet.balance.update", self.on_balance_update)
        self.event_bus.subscribe_sync("mining.stats", self.on_mining_stats)
        self.event_bus.subscribe_sync("model.prediction", self.on_model_prediction)
        self.event_bus.subscribe_sync("analytics.generate", self.on_generate_analytics)
        self.event_bus.subscribe_sync("system.shutdown", self.on_shutdown)
        
        # Start periodic update task
        self.update_task = asyncio.create_task(self._update_periodically())
        
        self.is_initialized = True
        logger.info("AnalyticsEngine initialized")
        
    async def _load_data(self):
        """Load saved analytics data from disk."""
        try:
            # Load trade history
            trades_path = os.path.join(self.data_dir, "trade_history.json")
            if os.path.exists(trades_path):
                with open(trades_path, "r") as f:
                    self.trade_history = json.load(f)
                logger.info(f"Loaded {len(self.trade_history)} trade history records")
            
            # Load portfolio history
            portfolio_path = os.path.join(self.data_dir, "portfolio_history.json")
            if os.path.exists(portfolio_path):
                with open(portfolio_path, "r") as f:
                    self.portfolio_history = json.load(f)
                logger.info(f"Loaded {len(self.portfolio_history)} portfolio history records")
            
            # Load mining stats
            mining_path = os.path.join(self.data_dir, "mining_stats.json")
            if os.path.exists(mining_path):
                with open(mining_path, "r") as f:
                    self.mining_stats = json.load(f)
                logger.info(f"Loaded mining stats for {len(self.mining_stats)} coins")
            
            # Load prediction accuracy
            prediction_path = os.path.join(self.data_dir, "prediction_accuracy.json")
            if os.path.exists(prediction_path):
                with open(prediction_path, "r") as f:
                    self.prediction_accuracy = json.load(f)
                logger.info(f"Loaded prediction accuracy for {len(self.prediction_accuracy)} models")
                
        except Exception as e:
            logger.error(f"Error loading analytics data: {e}")
            # Continue with empty data structures
    
    async def _save_data(self):
        """Save analytics data to disk."""
        if not self.is_initialized:
            return
            
        try:
            # Save trade history
            trades_path = os.path.join(self.data_dir, "trade_history.json")
            with open(trades_path, "w") as f:
                json.dump(self.trade_history[-self.history_limit:], f, indent=2)
            
            # Save portfolio history
            portfolio_path = os.path.join(self.data_dir, "portfolio_history.json")
            with open(portfolio_path, "w") as f:
                json.dump(self.portfolio_history[-self.history_limit:], f, indent=2)
            
            # Save mining stats
            mining_path = os.path.join(self.data_dir, "mining_stats.json")
            with open(mining_path, "w") as f:
                json.dump(self.mining_stats, f, indent=2)
            
            # Save prediction accuracy
            prediction_path = os.path.join(self.data_dir, "prediction_accuracy.json")
            with open(prediction_path, "w") as f:
                json.dump(self.prediction_accuracy, f, indent=2)
                
            logger.info("Saved analytics data")
        except Exception as e:
            logger.error(f"Error saving analytics data: {e}")
    
    async def _update_periodically(self):
        """Periodically update analytics and save data."""
        try:
            while True:
                await asyncio.sleep(self.update_interval)
                
                # Calculate any new metrics
                await self._update_metrics()
                
                # Save data
                await self._save_data()
                
        except asyncio.CancelledError:
            # Save one last time before exiting
            await self._save_data()
    
    async def _update_metrics(self):
        """Update calculated metrics."""
        # Only calculate if we have enough data
        if not self.trade_history or not self.portfolio_history:
            return
            
        try:
            # Calculate overall trading metrics
            await self._calculate_trading_metrics()
            
            # Calculate mining profitability
            await self._calculate_mining_profitability()
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    async def _calculate_trading_metrics(self):
        """Calculate overall trading metrics."""
        if not self.trade_history:
            return
            
        try:
            # Convert to DataFrame for easier analysis
            df = pd.DataFrame(self.trade_history)
            if df.empty or 'profit' not in df.columns:
                return
                
            # Aggregate metrics
            metrics = {
                "total_trades": len(df),
                "profitable_trades": int(df['profit'].gt(0).sum()),
                "unprofitable_trades": int(df['profit'].lt(0).sum()),
                "total_profit": float(df['profit'].sum()),
                "average_profit": float(df['profit'].mean()),
                "max_profit": float(df['profit'].max()),
                "max_loss": float(df['profit'].min()),
                "win_rate": float(df['profit'].gt(0).mean())
            }
            
            # Publish metrics event
            await self.event_bus.publish("analytics.metrics.trading", {
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error calculating trading metrics: {e}")
    
    async def _calculate_mining_profitability(self):
        """Calculate mining profitability metrics."""
        if not self.mining_stats:
            return
            
        try:
            profitability = {}
            
            for coin, stats in self.mining_stats.items():
                if 'hashrate' in stats and 'price' in stats and 'reward' in stats:
                    # Simple calculation: reward * price * hashrate - cost
                    reward = stats['reward']
                    price = stats['price']
                    hashrate = stats['hashrate']
                    cost = stats.get('cost', 0)
                    
                    daily_profit = (reward * price * hashrate * 24) - (cost * 24)
                    weekly_profit = daily_profit * 7
                    monthly_profit = daily_profit * 30
                    
                    profitability[coin] = {
                        "daily_profit": daily_profit,
                        "weekly_profit": weekly_profit,
                        "monthly_profit": monthly_profit,
                        "roi_days": cost / daily_profit if daily_profit > 0 else float('inf')
                    }
            
            # Publish profitability event
            await self.event_bus.publish("analytics.metrics.mining", {
                "profitability": profitability,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error calculating mining profitability: {e}")
    
    async def generate_chart(self, chart_type, params):
        """
        Generate a chart based on the specified type and parameters.
        
        Args:
            chart_type: Type of chart to generate
            params: Chart parameters
            
        Returns:
            Base64 encoded image of the chart
        """
        if not self.is_initialized:
            return None
            
        try:
            if chart_type == "portfolio_history":
                return await self._generate_portfolio_chart(params)
            elif chart_type == "trade_distribution":
                return await self._generate_trade_distribution(params)
            elif chart_type == "profit_loss":
                return await self._generate_profit_loss_chart(params)
            elif chart_type == "mining_profitability":
                return await self._generate_mining_chart(params)
            elif chart_type == "market_analysis":
                return await self._generate_market_analysis(params)
            elif chart_type == "prediction_accuracy":
                return await self._generate_prediction_accuracy(params)
            else:
                logger.warning(f"Unknown chart type: {chart_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating chart {chart_type}: {e}")
            return None
    
    async def _generate_portfolio_chart(self, params):
        """Generate portfolio history chart."""
        if not self.portfolio_history:
            return None
            
        time_range = params.get("time_range", "7d")
        
        # Filter data by time range
        now = datetime.now()
        if time_range == "1d":
            start_time = now - timedelta(days=1)
        elif time_range == "7d":
            start_time = now - timedelta(days=7)
        elif time_range == "30d":
            start_time = now - timedelta(days=30)
        elif time_range == "90d":
            start_time = now - timedelta(days=90)
        elif time_range == "1y":
            start_time = now - timedelta(days=365)
        else:
            start_time = now - timedelta(days=7)  # Default to 7 days
        
        # Convert to DataFrame for easier processing
        df = pd.DataFrame(self.portfolio_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df[df['timestamp'] >= start_time.isoformat()]
        
        if df.empty:
            return None
            
        # Create the plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['total_value'],
            mode='lines',
            name='Portfolio Value',
            line=dict(color='blue', width=2)
        ))
        
        fig.update_layout(
            title='Portfolio Value History',
            xaxis_title='Date',
            yaxis_title='Value (USD)',
            template='plotly_dark'
        )
        
        # Convert to base64 image
        img_bytes = BytesIO()
        fig.write_image(img_bytes, format='png')
        img_bytes.seek(0)
        return base64.b64encode(img_bytes.read()).decode('utf-8')
    
    async def _generate_trade_distribution(self, params):
        """Generate trade distribution chart."""
        if not self.trade_history:
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(self.trade_history)
        if df.empty or 'symbol' not in df.columns:
            return None
            
        # Group by symbol
        symbol_counts = df['symbol'].value_counts().head(10)
        
        # Create the plot
        fig = go.Figure(go.Pie(
            labels=symbol_counts.index,
            values=symbol_counts.values,
            hole=0.3
        ))
        
        fig.update_layout(
            title='Top 10 Traded Assets',
            template='plotly_dark'
        )
        
        # Convert to base64 image
        img_bytes = BytesIO()
        fig.write_image(img_bytes, format='png')
        img_bytes.seek(0)
        return base64.b64encode(img_bytes.read()).decode('utf-8')
    
    async def _generate_profit_loss_chart(self, params):
        """Generate profit/loss chart."""
        if not self.trade_history:
            return None
            
        time_range = params.get("time_range", "7d")
        
        # Filter data by time range
        now = datetime.now()
        if time_range == "1d":
            start_time = now - timedelta(days=1)
        elif time_range == "7d":
            start_time = now - timedelta(days=7)
        elif time_range == "30d":
            start_time = now - timedelta(days=30)
        elif time_range == "90d":
            start_time = now - timedelta(days=90)
        elif time_range == "1y":
            start_time = now - timedelta(days=365)
        else:
            start_time = now - timedelta(days=7)  # Default to 7 days
        
        # Convert to DataFrame
        df = pd.DataFrame(self.trade_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df[df['timestamp'] >= start_time.isoformat()]
        
        if df.empty or 'profit' not in df.columns:
            return None
            
        # Calculate cumulative profit
        df = df.sort_values('timestamp')
        df['cumulative_profit'] = df['profit'].cumsum()
        
        # Create the plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['cumulative_profit'],
            mode='lines',
            name='Cumulative Profit/Loss',
            line=dict(color='green' if df['cumulative_profit'].iloc[-1] >= 0 else 'red', width=2)
        ))
        
        fig.update_layout(
            title='Cumulative Profit/Loss',
            xaxis_title='Date',
            yaxis_title='Profit/Loss (USD)',
            template='plotly_dark'
        )
        
        # Convert to base64 image
        img_bytes = BytesIO()
        fig.write_image(img_bytes, format='png')
        img_bytes.seek(0)
        return base64.b64encode(img_bytes.read()).decode('utf-8')
    
    async def _generate_mining_chart(self, params):
        """Generate mining profitability chart."""
        if not self.mining_stats:
            return None
            
        # Prepare data
        coins = []
        daily_profits = []
        
        for coin, stats in self.mining_stats.items():
            if 'hashrate' in stats and 'price' in stats and 'reward' in stats:
                # Calculate daily profit
                reward = stats['reward']
                price = stats['price']
                hashrate = stats['hashrate']
                cost = stats.get('cost', 0)
                
                daily_profit = (reward * price * hashrate * 24) - (cost * 24)
                
                coins.append(coin)
                daily_profits.append(daily_profit)
        
        if not coins:
            return None
            
        # Create the plot
        colors = ['green' if profit >= 0 else 'red' for profit in daily_profits]
        
        fig = go.Figure(go.Bar(
            x=coins,
            y=daily_profits,
            marker_color=colors
        ))
        
        fig.update_layout(
            title='Daily Mining Profitability by Coin',
            xaxis_title='Coin',
            yaxis_title='Daily Profit/Loss (USD)',
            template='plotly_dark'
        )
        
        # Convert to base64 image
        img_bytes = BytesIO()
        fig.write_image(img_bytes, format='png')
        img_bytes.seek(0)
        return base64.b64encode(img_bytes.read()).decode('utf-8')
    
    async def _generate_market_analysis(self, params):
        """Generate market analysis chart."""
        symbol = params.get("symbol", "BTC/USD")
        
        if symbol not in self.market_data:
            return None
            
        # Get market data
        ohlcv_data = self.market_data[symbol]
        if not ohlcv_data:
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Create candlestick chart
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.1, 
                           subplot_titles=(f'{symbol} Price', 'Volume'), 
                           row_heights=[0.7, 0.3])
        
        # Add candlestick trace
        fig.add_trace(go.Candlestick(
            x=df['timestamp'],
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Price'
        ), row=1, col=1)
        
        # Add volume trace
        fig.add_trace(go.Bar(
            x=df['timestamp'],
            y=df['volume'],
            name='Volume',
            marker=dict(color='blue')
        ), row=2, col=1)
        
        fig.update_layout(
            title=f'{symbol} Market Analysis',
            xaxis_title='Date',
            template='plotly_dark',
            showlegend=False
        )
        
        # Convert to base64 image
        img_bytes = BytesIO()
        fig.write_image(img_bytes, format='png')
        img_bytes.seek(0)
        return base64.b64encode(img_bytes.read()).decode('utf-8')
    
    async def _generate_prediction_accuracy(self, params):
        """Generate prediction accuracy chart."""
        if not self.prediction_accuracy:
            return None
            
        # Prepare data
        models = []
        accuracies = []
        
        for model, metrics in self.prediction_accuracy.items():
            if 'accuracy' in metrics:
                models.append(model)
                accuracies.append(metrics['accuracy'])
        
        if not models:
            return None
            
        # Sort by accuracy
        sorted_indices = np.argsort(accuracies)[::-1]  # Descending
        models = [models[i] for i in sorted_indices]
        accuracies = [accuracies[i] for i in sorted_indices]
        
        # Create the plot
        fig = go.Figure(go.Bar(
            x=models,
            y=accuracies,
            marker_color='blue'
        ))
        
        fig.update_layout(
            title='Prediction Model Accuracy',
            xaxis_title='Model',
            yaxis_title='Accuracy',
            yaxis=dict(tickformat='.1%'),
            template='plotly_dark'
        )
        
        # Convert to base64 image
        img_bytes = BytesIO()
        fig.write_image(img_bytes, format='png')
        img_bytes.seek(0)
        return base64.b64encode(img_bytes.read()).decode('utf-8')
    
    async def on_market_update(self, data):
        """
        Handle market update event.
        
        Args:
            data: Market data
        """
        symbol = data.get("symbol")
        ohlcv = data.get("ohlcv")
        
        if not symbol or not ohlcv:
            return
            
        # Store market data
        if symbol not in self.market_data:
            self.market_data[symbol] = []
        
        # Add new data point
        self.market_data[symbol].append(ohlcv)
        
        # Limit history size
        if len(self.market_data[symbol]) > self.history_limit:
            self.market_data[symbol] = self.market_data[symbol][-self.history_limit:]
    
    async def on_trade_completed(self, data):
        """
        Handle trade completed event.
        
        Args:
            data: Trade data
        """
        # Add timestamp if not present
        if "timestamp" not in data:
            data["timestamp"] = datetime.now().isoformat()
        
        # Add to trade history
        self.trade_history.append(data)
        
        # Limit history size
        if len(self.trade_history) > self.history_limit:
            self.trade_history = self.trade_history[-self.history_limit:]
    
    async def on_balance_update(self, data):
        """
        Handle balance update event.
        
        Args:
            data: Balance data
        """
        total_value = data.get("total_value", 0)
        
        # Add to portfolio history
        portfolio_entry = {
            "timestamp": datetime.now().isoformat(),
            "total_value": total_value,
            "assets": data.get("assets", {})
        }
        
        self.portfolio_history.append(portfolio_entry)
        
        # Limit history size
        if len(self.portfolio_history) > self.history_limit:
            self.portfolio_history = self.portfolio_history[-self.history_limit:]
    
    async def on_mining_stats(self, data):
        """
        Handle mining stats event.
        
        Args:
            data: Mining stats data
        """
        coin = data.get("coin")
        stats = data.get("stats")
        
        if not coin or not stats:
            return
            
        # Update mining stats
        self.mining_stats[coin] = stats
    
    async def on_model_prediction(self, data):
        """
        Handle model prediction event.
        
        Args:
            data: Prediction data
        """
        model = data.get("model")
        predicted = data.get("predicted")
        actual = data.get("actual")
        
        if not model or predicted is None or actual is None:
            return
            
        # Check if model exists in accuracy dict
        if model not in self.prediction_accuracy:
            self.prediction_accuracy[model] = {
                "correct": 0,
                "total": 0,
                "accuracy": 0.0
            }
        
        # Update prediction accuracy
        if predicted == actual:
            self.prediction_accuracy[model]["correct"] += 1
        
        self.prediction_accuracy[model]["total"] += 1
        self.prediction_accuracy[model]["accuracy"] = (
            self.prediction_accuracy[model]["correct"] / 
            self.prediction_accuracy[model]["total"]
        )
    
    async def on_generate_analytics(self, data):
        """
        Handle analytics generation request.
        
        Args:
            data: Request data
        """
        request_id = data.get("request_id")
        chart_type = data.get("chart_type")
        params = data.get("params", {})
        
        if not chart_type:
            await self.event_bus.publish("analytics.generate.result", {
                "request_id": request_id,
                "success": False,
                "error": "Chart type not specified"
            })
            return
        
        # Generate requested chart
        chart_image = await self.generate_chart(chart_type, params)
        
        if chart_image:
            await self.event_bus.publish("analytics.generate.result", {
                "request_id": request_id,
                "success": True,
                "chart_type": chart_type,
                "image": chart_image
            })
        else:
            await self.event_bus.publish("analytics.generate.result", {
                "request_id": request_id,
                "success": False,
                "chart_type": chart_type,
                "error": "Failed to generate chart"
            })
    
    async def on_shutdown(self, _):
        """Handle system shutdown event."""
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the AnalyticsEngine component."""
        logger.info("Shutting down AnalyticsEngine")
        
        # Cancel update task
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass
        
        # Save data one last time
        await self._save_data()
        
        logger.info("AnalyticsEngine shut down successfully")
