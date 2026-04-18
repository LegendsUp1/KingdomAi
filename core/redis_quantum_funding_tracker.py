"""
Enhanced Redis Quantum Nexus Integration for Funding Rate and Basis Tracking (2025)
Implements advanced data structures and methods for tracking, storing, and analyzing
funding rates and basis data across multiple exchanges with high performance.
"""
import asyncio
import logging
import time
from datetime import datetime
import json
import pandas as pd
from typing import Optional

from core.base_component import BaseComponent
from utils.redis_client import RedisClient
from utils.async_utils import AsyncSupport

class RedisQuantumFundingTracker(BaseComponent):
    """
    Enhanced Redis Quantum Nexus integration for funding rate and basis tracking.
    Provides high-performance storage and retrieval of critical trading data.
    """
    
    def __init__(self, event_bus=None, config=None):
        """Initialize the Redis Quantum Funding Tracker component."""
        super().__init__("RedisQuantumFundingTracker", event_bus, config)
        self.redis_client = None
        
        # Configuration
        self.config = config or {
            "data_retention_days": 90,
            "update_interval_seconds": 60,
            "compaction_interval_hours": 24,
            "exchanges": ["binance", "okx", "bybit", "deribit", "gate"],
            "trading_pairs": ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "AVAX-USDT"],
            "time_series_resolution": {
                "1min": 60 * 24 * 3,      # 3 days of 1-minute data
                "5min": 60 * 12 * 7,      # 7 days of 5-minute data
                "1h": 24 * 30,            # 30 days of hourly data
                "4h": 6 * 60,             # 60 days of 4-hour data
                "1d": 365                  # 365 days of daily data
            },
            "correlation_tracking_enabled": True,
            "anomaly_detection_enabled": True,
            "real_time_alerts_enabled": True
        }
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize the component and connect to Redis Quantum Nexus."""
        self.logger.info("Initializing Redis Quantum Funding Tracker")
        
        # Connect to Redis Quantum Nexus with strict enforcement of connection parameters
        try:
            self.redis_client = RedisClient(
                host="localhost", 
                port=6380,
                password="QuantumNexus2025",
                db=0,
                decode_responses=True
            )
            # Test connection
            ping_result = await self.redis_client.ping()
            if not ping_result:
                raise ConnectionError("Redis ping failed")
            self.logger.info("Successfully connected to Redis Quantum Nexus")
        except Exception as e:
            self.logger.critical(f"Failed to connect to Redis Quantum Nexus: {e}")
            # Enforcing strict no-fallback policy
            raise SystemExit("Critical failure: Redis Quantum Nexus connection failed. Halting system.")
            
        # Register event handlers
        if self.event_bus:
            await self.event_bus.subscribe("funding_rate_update", self.on_funding_rate_update)
            await self.event_bus.subscribe("market_data_update", self.on_market_data_update)
            await self.event_bus.subscribe("basis_data_update", self.on_basis_update)
            await self.event_bus.subscribe("exchange_connected", self.on_exchange_connected)
            await self.event_bus.subscribe("system_shutdown", self.on_shutdown)
            
        # Initialize data structures
        await self.initialize_data_structures()
        
        # Start background tasks
        AsyncSupport.create_background_task(self.periodic_data_compaction())
        AsyncSupport.create_background_task(self.correlation_analysis_task())
        AsyncSupport.create_background_task(self.anomaly_detection_task())
        AsyncSupport.create_background_task(self.cross_exchange_analysis_task())
        
        self.logger.info("Redis Quantum Funding Tracker initialized successfully")
        return True
    
    async def initialize_data_structures(self):
        """Initialize Redis data structures for efficient time series storage."""
        try:
            # Create sorted sets for time series data if they don't exist
            for exchange in self.config["exchanges"]:
                for pair in self.config["trading_pairs"]:
                    # Set up funding rate time series
                    key_prefix = f"ts:funding_rate:{exchange}:{pair}"
                    for resolution in self.config["time_series_resolution"].keys():
                        await self.redis_client.exists(f"{key_prefix}:{resolution}")
                    
                    # Set up basis tracking time series
                    basis_key_prefix = f"ts:basis:{exchange}:{pair}"
                    for resolution in self.config["time_series_resolution"].keys():
                        await self.redis_client.exists(f"{basis_key_prefix}:{resolution}")
                    
                    # Set up index structures for faster querying
                    await self.redis_client.exists(f"idx:funding:{exchange}:{pair}")
                    await self.redis_client.exists(f"idx:basis:{exchange}:{pair}")
            
            # Set up correlation matrices storage
            await self.redis_client.exists("matrix:funding_correlation")
            await self.redis_client.exists("matrix:basis_correlation")
            
            # Set up anomaly detection data structures
            await self.redis_client.exists("anomaly:funding_rates")
            await self.redis_client.exists("anomaly:basis")
            
            self.logger.info("Redis data structures initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis data structures: {e}")
            raise
    
    async def on_funding_rate_update(self, data):
        """Store and process new funding rate data."""
        try:
            exchange = data.get("exchange")
            pair = data.get("pair")
            rate = data.get("rate")
            timestamp = data.get("timestamp", time.time())
            
            if not all([exchange, pair, rate is not None]):
                self.logger.warning(f"Incomplete funding rate update data: {data}")
                return
                
            # Store in Redis with TTL based on resolution
            for resolution, retention_points in self.config["time_series_resolution"].items():
                # Calculate the normalized timestamp for this resolution
                norm_ts = self._normalize_timestamp(timestamp, resolution)
                key = f"ts:funding_rate:{exchange}:{pair}:{resolution}"
                
                # Store in sorted set with score as timestamp
                await self.redis_client.zadd(key, {f"{norm_ts}:{rate}": norm_ts})
                
                # Set expiry for automatic cleanup
                ttl_seconds = self._resolution_to_seconds(resolution) * retention_points
                await self.redis_client.expire(key, ttl_seconds)
                
            # Store latest value in hash for quick access
            latest_key = "latest:funding_rate"
            field = f"{exchange}:{pair}"
            await self.redis_client.hset(latest_key, field, json.dumps({
                "rate": rate,
                "timestamp": timestamp,
                "updated_at": time.time()
            }))
            
            # Update index for faster time-based queries
            idx_key = f"idx:funding:{exchange}:{pair}"
            await self.redis_client.zadd(idx_key, {str(timestamp): timestamp})
            
            # Publish event to notify other components
            if self.event_bus:
                await self.event_bus.publish("funding_rate_stored", {
                    "exchange": exchange,
                    "pair": pair,
                    "rate": rate,
                    "timestamp": timestamp
                })
                
            # Check for anomalies
            if self.config["anomaly_detection_enabled"]:
                await self._check_funding_rate_anomaly(exchange, pair, rate)
                
        except Exception as e:
            self.logger.error(f"Error processing funding rate update: {e}")
    
    async def on_basis_update(self, data):
        """Store and process new basis data (spot-futures price difference)."""
        try:
            exchange = data.get("exchange")
            pair = data.get("pair")
            spot_price = data.get("spot_price")
            futures_price = data.get("futures_price")
            timestamp = data.get("timestamp", time.time())
            
            if not all([exchange, pair, spot_price is not None, futures_price is not None]):
                self.logger.warning(f"Incomplete basis update data: {data}")
                return
                
            # Calculate basis and percentage
            basis = futures_price - spot_price
            basis_percentage = (basis / spot_price) * 100
            
            # Store in Redis with TTL based on resolution
            for resolution, retention_points in self.config["time_series_resolution"].items():
                # Calculate the normalized timestamp for this resolution
                norm_ts = self._normalize_timestamp(timestamp, resolution)
                key = f"ts:basis:{exchange}:{pair}:{resolution}"
                
                # Store in sorted set with score as timestamp
                value = {
                    "basis": basis,
                    "basis_percentage": basis_percentage,
                    "spot": spot_price,
                    "futures": futures_price
                }
                await self.redis_client.zadd(key, {f"{norm_ts}:{json.dumps(value)}": norm_ts})
                
                # Set expiry for automatic cleanup
                ttl_seconds = self._resolution_to_seconds(resolution) * retention_points
                await self.redis_client.expire(key, ttl_seconds)
                
            # Store latest value in hash for quick access
            latest_key = "latest:basis"
            field = f"{exchange}:{pair}"
            await self.redis_client.hset(latest_key, field, json.dumps({
                "basis": basis,
                "basis_percentage": basis_percentage,
                "spot": spot_price,
                "futures": futures_price,
                "timestamp": timestamp,
                "updated_at": time.time()
            }))
            
            # Update index for faster time-based queries
            idx_key = f"idx:basis:{exchange}:{pair}"
            await self.redis_client.zadd(idx_key, {str(timestamp): timestamp})
            
            # Publish event to notify other components
            if self.event_bus:
                await self.event_bus.publish("basis_stored", {
                    "exchange": exchange,
                    "pair": pair,
                    "basis": basis,
                    "basis_percentage": basis_percentage,
                    "spot": spot_price,
                    "futures": futures_price,
                    "timestamp": timestamp
                })
                
            # Check for anomalies
            if self.config["anomaly_detection_enabled"]:
                await self._check_basis_anomaly(exchange, pair, basis_percentage)
                
        except Exception as e:
            self.logger.error(f"Error processing basis update: {e}")
    
    async def on_market_data_update(self, data):
        """Process market data updates to derive basis information."""
        try:
            if not isinstance(data, dict):
                return
            exchange = data.get("exchange")
            pair = data.get("pair") or data.get("symbol")
            spot_price = data.get("spot_price") or data.get("price")
            futures_price = data.get("futures_price") or data.get("mark_price")
            timestamp = data.get("timestamp", time.time())
            if not all([exchange, pair, spot_price is not None]):
                return
            if futures_price is not None and spot_price:
                await self.on_basis_update({
                    "exchange": exchange,
                    "pair": pair,
                    "spot_price": float(spot_price),
                    "futures_price": float(futures_price),
                    "timestamp": timestamp
                })
            else:
                latest_key = "latest:market_price"
                field = f"{exchange}:{pair}"
                await self.redis_client.hset(latest_key, field, json.dumps({
                    "price": float(spot_price),
                    "timestamp": timestamp,
                    "updated_at": time.time()
                }))
        except Exception as e:
            self.logger.error(f"Error processing market data update: {e}")
    
    async def on_exchange_connected(self, data):
        """Handle when a new exchange connection is established."""
        exchange = data.get("exchange")
        self.logger.info(f"Exchange connected: {exchange}")
        # Add new exchange to tracking list if not already present
        if exchange and exchange not in self.config["exchanges"]:
            self.config["exchanges"].append(exchange)
    
    async def on_shutdown(self, data):
        """Clean up resources on system shutdown."""
        self.logger.info("Shutting down Redis Quantum Funding Tracker")
        self.shutdown_event.set()
        if self.redis_client:
            await self.redis_client.close()
    
    async def get_funding_rates(self, exchange: str, pair: str, 
                               start_time: Optional[float] = None, 
                               end_time: Optional[float] = None,
                               resolution: str = "1h") -> pd.DataFrame:
        """
        Retrieve funding rates for specified exchange and pair.
        Returns pandas DataFrame with timestamp index and rate column.
        """
        try:
            if resolution not in self.config["time_series_resolution"]:
                raise ValueError(f"Invalid resolution: {resolution}")
            
            key = f"ts:funding_rate:{exchange}:{pair}:{resolution}"
            
            # Default to last 24 hours if no time range specified
            if start_time is None:
                start_time = time.time() - 86400  # 24 hours
            if end_time is None:
                end_time = time.time()
                
            # Normalize timestamps to resolution
            start_norm = self._normalize_timestamp(start_time, resolution)
            end_norm = self._normalize_timestamp(end_time, resolution) + 1
            
            # Retrieve data from Redis
            data = await self.redis_client.zrangebyscore(key, start_norm, end_norm, withscores=True)
            
            if not data:
                return pd.DataFrame(columns=['timestamp', 'rate'])
            
            # Parse results
            records = []
            for item, score in data:
                ts, rate = item.split(':', 1)
                records.append({
                    'timestamp': float(ts),
                    'rate': float(rate)
                })
            
            # Convert to DataFrame
            df = pd.DataFrame(records)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('datetime', inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error retrieving funding rates: {e}")
            raise
    
    async def get_basis_data(self, exchange: str, pair: str,
                           start_time: Optional[float] = None,
                           end_time: Optional[float] = None,
                           resolution: str = "1h") -> pd.DataFrame:
        """
        Retrieve basis data for specified exchange and pair.
        Returns pandas DataFrame with timestamp index and basis columns.
        """
        try:
            if resolution not in self.config["time_series_resolution"]:
                raise ValueError(f"Invalid resolution: {resolution}")
            
            key = f"ts:basis:{exchange}:{pair}:{resolution}"
            
            # Default to last 24 hours if no time range specified
            if start_time is None:
                start_time = time.time() - 86400  # 24 hours
            if end_time is None:
                end_time = time.time()
                
            # Normalize timestamps to resolution
            start_norm = self._normalize_timestamp(start_time, resolution)
            end_norm = self._normalize_timestamp(end_time, resolution) + 1
            
            # Retrieve data from Redis
            data = await self.redis_client.zrangebyscore(key, start_norm, end_norm, withscores=True)
            
            if not data:
                return pd.DataFrame(columns=['timestamp', 'basis', 'basis_percentage', 'spot', 'futures'])
            
            # Parse results
            records = []
            for item, score in data:
                ts, json_data = item.split(':', 1)
                parsed = json.loads(json_data)
                records.append({
                    'timestamp': float(ts),
                    'basis': parsed['basis'],
                    'basis_percentage': parsed['basis_percentage'],
                    'spot': parsed['spot'],
                    'futures': parsed['futures']
                })
            
            # Convert to DataFrame
            df = pd.DataFrame(records)
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            df.set_index('datetime', inplace=True)
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error retrieving basis data: {e}")
            raise
    
    # Background tasks
    
    async def periodic_data_compaction(self):
        """Periodically compact older data to save space."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running periodic data compaction")
                
                compacted = 0
                cutoff_hours = self.config.get("compaction_retention_hours", 168)
                cutoff_ts = time.time() - (cutoff_hours * 3600)
                for exchange in self.config.get("exchanges", []):
                    for pair in self.config.get("trading_pairs", []):
                        for prefix in ("funding_rates", "basis_data"):
                            key = f"{prefix}:{exchange}:{pair}"
                            try:
                                removed = await self.redis_client.zremrangebyscore(key, "-inf", cutoff_ts)
                                compacted += removed if removed else 0
                            except Exception as compact_err:
                                self.logger.debug(f"Compaction skip for {key}: {compact_err}")
                
                if compacted:
                    self.logger.info(f"Data compaction removed {compacted} stale entries (>{cutoff_hours}h old)")
                
                # Sleep until next compaction interval
                compaction_interval = self.config.get("compaction_interval_hours", 24) * 3600
                await asyncio.sleep(compaction_interval)
        except asyncio.CancelledError:
            self.logger.info("Data compaction task cancelled")
        except Exception as e:
            self.logger.error(f"Error in data compaction task: {e}")
    
    async def correlation_analysis_task(self):
        """Analyze correlations between funding rates across exchanges and pairs."""
        try:
            while not self.shutdown_event.is_set():
                if self.config["correlation_tracking_enabled"]:
                    self.logger.debug("Running correlation analysis")
                    await self._update_correlation_matrices()
                
                # Run every hour
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            self.logger.info("Correlation analysis task cancelled")
        except Exception as e:
            self.logger.error(f"Error in correlation analysis task: {e}")
    
    async def anomaly_detection_task(self):
        """Detect anomalies in funding rates and basis data."""
        try:
            while not self.shutdown_event.is_set():
                if self.config["anomaly_detection_enabled"]:
                    self.logger.debug("Running anomaly detection")
                    for exchange in self.config.get("exchanges", []):
                        for pair in self.config.get("trading_pairs", []):
                            try:
                                df = await self.get_funding_rates(exchange, pair, resolution="1h")
                                if df is not None and len(df) >= 20:
                                    mean_rate = df['rate'].mean()
                                    std_rate = df['rate'].std()
                                    if std_rate > 0:
                                        latest = df['rate'].iloc[-1]
                                        z_score = abs(latest - mean_rate) / std_rate
                                        if z_score > 3.0:
                                            self.logger.warning(
                                                f"Anomaly detected: {exchange}:{pair} funding rate "
                                                f"z-score={z_score:.2f} (rate={latest:.6f})"
                                            )
                                            if self.event_bus:
                                                await self.event_bus.publish("funding_anomaly_detected", {
                                                    "exchange": exchange,
                                                    "pair": pair,
                                                    "z_score": z_score,
                                                    "rate": latest,
                                                    "mean": mean_rate,
                                                    "std": std_rate,
                                                    "timestamp": time.time()
                                                })
                            except Exception as anom_err:
                                self.logger.debug(f"Anomaly check skip for {exchange}:{pair}: {anom_err}")
                
                # Run every 5 minutes
                await asyncio.sleep(300)
        except asyncio.CancelledError:
            self.logger.info("Anomaly detection task cancelled")
        except Exception as e:
            self.logger.error(f"Error in anomaly detection task: {e}")
    
    async def cross_exchange_analysis_task(self):
        """Analyze cross-exchange opportunities and differentials."""
        try:
            while not self.shutdown_event.is_set():
                self.logger.debug("Running cross-exchange analysis")
                await self._analyze_cross_exchange_opportunities()
                
                # Run every 5 minutes
                await asyncio.sleep(300)
        except asyncio.CancelledError:
            self.logger.info("Cross-exchange analysis task cancelled")
        except Exception as e:
            self.logger.error(f"Error in cross-exchange analysis task: {e}")
    
    # Helper methods
    
    def _normalize_timestamp(self, timestamp: float, resolution: str) -> int:
        """Normalize timestamp to the specified resolution."""
        dt = datetime.fromtimestamp(timestamp)
        
        if resolution == "1min":
            return int(datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute).timestamp())
        elif resolution == "5min":
            return int(datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute - dt.minute % 5).timestamp())
        elif resolution == "1h":
            return int(datetime(dt.year, dt.month, dt.day, dt.hour).timestamp())
        elif resolution == "4h":
            return int(datetime(dt.year, dt.month, dt.day, dt.hour - dt.hour % 4).timestamp())
        elif resolution == "1d":
            return int(datetime(dt.year, dt.month, dt.day).timestamp())
        else:
            raise ValueError(f"Unsupported resolution: {resolution}")
    
    def _resolution_to_seconds(self, resolution: str) -> int:
        """Convert resolution string to seconds."""
        if resolution == "1min":
            return 60
        elif resolution == "5min":
            return 300
        elif resolution == "1h":
            return 3600
        elif resolution == "4h":
            return 14400
        elif resolution == "1d":
            return 86400
        else:
            raise ValueError(f"Unsupported resolution: {resolution}")
    
    async def _update_correlation_matrices(self):
        """Update correlation matrices for funding rates and basis."""
        try:
            funding_series = {}
            for exchange in self.config["exchanges"]:
                for pair in self.config["trading_pairs"]:
                    label = f"{exchange}:{pair}"
                    df = await self.get_funding_rates(exchange, pair, resolution="1h")
                    if df is not None and not df.empty:
                        funding_series[label] = df['rate']
            if len(funding_series) >= 2:
                combined = pd.DataFrame(funding_series)
                combined = combined.dropna(axis=1, how='all').ffill()
                if combined.shape[1] >= 2:
                    corr_matrix = combined.corr()
                    corr_json = corr_matrix.to_json()
                    await self.redis_client.set("matrix:funding_correlation", corr_json)
                    self.logger.debug(
                        f"Updated funding correlation matrix: {corr_matrix.shape[0]}x{corr_matrix.shape[1]}"
                    )
                    if self.event_bus:
                        await self.event_bus.publish("correlation_matrix_updated", {
                            "type": "funding_rate",
                            "size": corr_matrix.shape[0],
                            "timestamp": time.time()
                        })
        except Exception as e:
            self.logger.error(f"Error updating correlation matrices: {e}")
    
    async def _analyze_cross_exchange_opportunities(self):
        """Analyze cross-exchange arbitrage opportunities based on funding and basis."""
        try:
            for pair in self.config["trading_pairs"]:
                latest_rates = {}
                latest_basis = {}
                for exchange in self.config["exchanges"]:
                    rate_raw = await self.redis_client.hget(
                        "latest:funding_rate", f"{exchange}:{pair}"
                    )
                    if rate_raw:
                        parsed = json.loads(rate_raw)
                        latest_rates[exchange] = parsed.get("rate", 0)
                    basis_raw = await self.redis_client.hget(
                        "latest:basis", f"{exchange}:{pair}"
                    )
                    if basis_raw:
                        parsed = json.loads(basis_raw)
                        latest_basis[exchange] = parsed.get("basis_percentage", 0)
                if len(latest_rates) >= 2:
                    max_ex = max(latest_rates, key=latest_rates.get)
                    min_ex = min(latest_rates, key=latest_rates.get)
                    rate_diff = latest_rates[max_ex] - latest_rates[min_ex]
                    if abs(rate_diff) > 0.005:
                        opportunity = {
                            "type": "cross_exchange_funding",
                            "pair": pair,
                            "long_exchange": min_ex,
                            "short_exchange": max_ex,
                            "rate_differential": rate_diff,
                            "rates": latest_rates,
                            "timestamp": time.time()
                        }
                        await self.redis_client.lpush(
                            "opportunities:cross_exchange",
                            json.dumps(opportunity)
                        )
                        await self.redis_client.ltrim("opportunities:cross_exchange", 0, 999)
                        self.logger.info(
                            f"Cross-exchange opportunity: {pair} "
                            f"rate_diff={rate_diff:.4f} ({min_ex} vs {max_ex})"
                        )
                        if self.event_bus:
                            await self.event_bus.publish(
                                "cross_exchange_opportunity", opportunity
                            )
        except Exception as e:
            self.logger.error(f"Error analyzing cross-exchange opportunities: {e}")
    
    async def _check_funding_rate_anomaly(self, exchange, pair, rate):
        """Check if a funding rate is anomalous and issue alerts if needed."""
        try:
            df = await self.get_funding_rates(exchange, pair, resolution="1h")
            if df is None or len(df) < 20:
                return
            mean_rate = df['rate'].mean()
            std_rate = df['rate'].std()
            if std_rate == 0:
                return
            z_score = (rate - mean_rate) / std_rate
            if abs(z_score) > 2.5:
                anomaly = {
                    "type": "funding_rate_anomaly",
                    "exchange": exchange,
                    "pair": pair,
                    "rate": rate,
                    "z_score": z_score,
                    "mean": mean_rate,
                    "std": std_rate,
                    "severity": "critical" if abs(z_score) > 4 else "warning",
                    "timestamp": time.time()
                }
                await self.redis_client.lpush(
                    "anomaly:funding_rates", json.dumps(anomaly)
                )
                await self.redis_client.ltrim("anomaly:funding_rates", 0, 999)
                self.logger.warning(
                    f"Funding rate anomaly: {exchange}:{pair} "
                    f"rate={rate:.6f} z={z_score:.2f}"
                )
                if self.config["real_time_alerts_enabled"] and self.event_bus:
                    await self.event_bus.publish("anomaly.funding_rate", anomaly)
        except Exception as e:
            self.logger.error(f"Error checking funding rate anomaly: {e}")
    
    async def _check_basis_anomaly(self, exchange, pair, basis_percentage):
        """Check if basis is anomalous and issue alerts if needed."""
        try:
            df = await self.get_basis_data(exchange, pair, resolution="1h")
            if df is None or len(df) < 20:
                return
            mean_basis = df['basis_percentage'].mean()
            std_basis = df['basis_percentage'].std()
            if std_basis == 0:
                return
            z_score = (basis_percentage - mean_basis) / std_basis
            if abs(z_score) > 2.5:
                anomaly = {
                    "type": "basis_anomaly",
                    "exchange": exchange,
                    "pair": pair,
                    "basis_percentage": basis_percentage,
                    "z_score": z_score,
                    "mean": mean_basis,
                    "std": std_basis,
                    "severity": "critical" if abs(z_score) > 4 else "warning",
                    "timestamp": time.time()
                }
                await self.redis_client.lpush(
                    "anomaly:basis", json.dumps(anomaly)
                )
                await self.redis_client.ltrim("anomaly:basis", 0, 999)
                self.logger.warning(
                    f"Basis anomaly: {exchange}:{pair} "
                    f"basis={basis_percentage:.4f}% z={z_score:.2f}"
                )
                if self.config["real_time_alerts_enabled"] and self.event_bus:
                    await self.event_bus.publish("anomaly.basis", anomaly)
        except Exception as e:
            self.logger.error(f"Error checking basis anomaly: {e}")
