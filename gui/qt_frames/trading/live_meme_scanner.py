#!/usr/bin/env python3
"""
LIVE Meme Scanner - Real DEX Data Integration
Scans DEXs for new tokens, rug detection, and moonshot opportunities
NO MOCK DATA - 100% LIVE
"""

import asyncio
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class MemeToken:
    """Meme token data."""
    symbol: str
    name: str
    address: str
    chain: str  # 'ethereum', 'bsc', 'polygon', etc.
    price: float
    price_change_1h: float
    price_change_24h: float
    liquidity_usd: float
    volume_24h: float
    market_cap: float
    holder_count: int
    rug_score: float  # 0.0 (safe) to 1.0 (likely rug)
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    dex: str  # 'uniswap', 'pancakeswap', etc.
    created_at: Optional[datetime] = None
    contract_verified: bool = False
    honeypot_detected: bool = False
    held_in_wallet: bool = False
    held_amount: Optional[float] = None


class LiveMemeScanner:
    """
    LIVE Meme Coin Scanner
    Scans DEXs for new tokens and analyzes rug pull risk
    """
    
    def __init__(self, api_keys: Optional[Dict] = None, kingdom_web3=None):
        """
        Initialize meme scanner.
        
        Args:
            api_keys: API keys for DEX APIs (DexScreener, Moralis, etc.)
            kingdom_web3: KingdomWeb3 for on-chain data
        """
        self.api_keys = api_keys or {}
        self.kingdom_web3 = kingdom_web3
        self.meme_tokens: List[MemeToken] = []
        
        # API availability - DexScreener is FREE (no API key required)
        self.has_dexscreener = True  # DexScreener free tier doesn't need API key
        self.has_moralis = 'moralis' in self.api_keys
        self.has_etherscan = 'etherscan' in self.api_keys
        
        logger.info("✅ Live Meme Scanner initialized")
        logger.info(f"   DexScreener: ✅ (free tier)")
        logger.info(f"   Moralis: {'✅' if self.has_moralis else '❌'}")
        logger.info(f"   Etherscan: {'✅' if self.has_etherscan else '❌'}")
    
    async def scan_new_tokens(self, chains: List[str] = None, min_liquidity: float = 10000) -> List[MemeToken]:
        """
        Scan DEXs for new tokens.
        
        Args:
            chains: Blockchain chains to scan (default: ['ethereum', 'bsc', 'polygon'])
            min_liquidity: Minimum liquidity in USD
            
        Returns:
            List of discovered meme tokens
        """
        if chains is None:
            chains = ['ethereum', 'bsc', 'polygon']
        
        all_tokens = []
        
        for chain in chains:
            try:
                # Scan chain for new tokens
                tokens = await self._scan_chain(chain, min_liquidity)
                all_tokens.extend(tokens)
                
            except Exception as e:
                logger.error(f"Error scanning {chain}: {e}")
        
        # Analyze rug risk for all tokens
        for token in all_tokens:
            await self._analyze_rug_risk(token)
        
        # Annotate tokens based on actual wallet holdings when possible
        self._annotate_wallet_holdings(all_tokens)
        
        # Sort by volume (most active first)
        all_tokens.sort(key=lambda t: t.volume_24h, reverse=True)
        
        self.meme_tokens = all_tokens[:50]  # Keep top 50
        
        logger.info(f"🚀 Scanned {len(all_tokens)} meme tokens")
        logger.info(f"   Safe: {sum(1 for t in all_tokens if t.risk_level == 'low')}")
        logger.info(f"   Risky: {sum(1 for t in all_tokens if t.risk_level in ['high', 'critical'])}")
        
        return self.meme_tokens

    def _annotate_wallet_holdings(self, tokens: List[MemeToken]) -> None:
        """Mark tokens that correspond to symbols held in the user's wallets.

        Uses kingdom_web3.get_tracked_wallets() when available. This is a
        best-effort overlay; it never fabricates holdings and it is safe if
        WalletSystem/KingdomWeb3 are not wired in the current session.
        """
        if not tokens:
            return

        kw3 = getattr(self, 'kingdom_web3', None)
        if kw3 is None:
            return

        wallets_method = getattr(kw3, 'get_tracked_wallets', None)
        if not callable(wallets_method):
            return

        try:
            wallets = wallets_method()
        except Exception as e:
            logger.error(f"Error retrieving tracked wallets for meme scanner: {e}")
            return

        if not isinstance(wallets, list):
            return

        held_symbols = set()
        try:
            for entry in wallets:
                if not isinstance(entry, dict):
                    continue
                sym_raw = entry.get('symbol') or entry.get('chain') or entry.get('network')
                if not sym_raw:
                    continue
                sym = str(sym_raw).strip().upper()
                if not sym:
                    continue
                held_symbols.add(sym)
        except Exception as e:
            logger.error(f"Error processing wallet entries for meme scanner: {e}")
            return

        if not held_symbols:
            return

        for token in tokens:
            try:
                sym = (token.symbol or '').upper()
                if sym and sym in held_symbols:
                    token.held_in_wallet = True
            except Exception:
                continue
    
    async def _scan_chain(self, chain: str, min_liquidity: float) -> List[MemeToken]:
        """
        Scan specific chain for new tokens.
        
        Args:
            chain: Blockchain name
            min_liquidity: Minimum liquidity
            
        Returns:
            List of tokens on chain
        """
        tokens = []
        
        try:
            # Use DexScreener API (free tier available)
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                # DexScreener trending tokens endpoint
                url = f"https://api.dexscreener.com/latest/dex/tokens/{chain}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for pair in data.get('pairs', [])[:100]:  # Limit to 100
                            try:
                                # Extract token data
                                base_token = pair.get('baseToken', {})
                                quote_token = pair.get('quoteToken', {})
                                
                                # Filter by liquidity
                                liquidity = float(pair.get('liquidity', {}).get('usd', 0))
                                if liquidity < min_liquidity:
                                    continue
                                
                                # Get price data
                                price = float(pair.get('priceUsd', 0))
                                price_change_1h = float(pair.get('priceChange', {}).get('h1', 0))
                                price_change_24h = float(pair.get('priceChange', {}).get('h24', 0))
                                
                                # Only include tokens with significant price movement
                                if abs(price_change_24h) < 10:
                                    continue
                                
                                token = MemeToken(
                                    symbol=base_token.get('symbol', 'UNKNOWN'),
                                    name=base_token.get('name', 'Unknown'),
                                    address=base_token.get('address', ''),
                                    chain=chain,
                                    price=price,
                                    price_change_1h=price_change_1h,
                                    price_change_24h=price_change_24h,
                                    liquidity_usd=liquidity,
                                    volume_24h=float(pair.get('volume', {}).get('h24', 0)),
                                    market_cap=float(pair.get('fdv', 0)),
                                    holder_count=0,  # Would get from chain
                                    rug_score=0.0,  # Calculated later
                                    risk_level='unknown',
                                    dex=pair.get('dexId', 'unknown'),
                                    created_at=None,
                                    contract_verified=False,
                                    honeypot_detected=False
                                )
                                
                                tokens.append(token)
                                
                            except Exception as e:
                                logger.debug(f"Error parsing token data: {e}")
                                continue
            
            logger.info(f"✅ Found {len(tokens)} tokens on {chain}")
            
        except Exception as e:
            logger.error(f"Error scanning {chain}: {e}")
        
        return tokens
    
    async def _analyze_rug_risk(self, token: MemeToken):
        """
        Analyze rug pull risk for token.
        
        Args:
            token: MemeToken to analyze
        """
        try:
            risk_score = 0.0
            
            # 1. Liquidity risk (low liquidity = higher risk)
            if token.liquidity_usd < 50000:
                risk_score += 0.3
            elif token.liquidity_usd < 100000:
                risk_score += 0.1
            
            # 2. Volume to liquidity ratio
            if token.liquidity_usd > 0:
                vol_liq_ratio = token.volume_24h / token.liquidity_usd
                if vol_liq_ratio > 5:  # Unusual volume
                    risk_score += 0.2
            
            # 3. Extreme price changes (pump and dump indicator)
            if token.price_change_24h > 500:  # >500% in 24h
                risk_score += 0.3
            elif token.price_change_24h > 200:
                risk_score += 0.2
            
            # 4. Contract verification
            if not token.contract_verified:
                risk_score += 0.1
            
            # 5. Honeypot detection
            if token.honeypot_detected:
                risk_score = 1.0  # Automatic critical risk
            
            # Normalize score
            token.rug_score = min(risk_score, 1.0)
            
            # Determine risk level
            if token.rug_score >= 0.7:
                token.risk_level = 'critical'
            elif token.rug_score >= 0.5:
                token.risk_level = 'high'
            elif token.rug_score >= 0.3:
                token.risk_level = 'medium'
            else:
                token.risk_level = 'low'
            
        except Exception as e:
            logger.error(f"Error analyzing rug risk for {token.symbol}: {e}")
            token.rug_score = 0.5
            token.risk_level = 'unknown'
    
    async def check_honeypot(self, token_address: str, chain: str) -> bool:
        """
        Check if token is a honeypot.
        
        Args:
            token_address: Token contract address
            chain: Blockchain name
            
        Returns:
            True if honeypot detected
        """
        try:
            # Use Honeypot.is API (free tier available)
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                url = f"https://api.honeypot.is/v2/IsHoneypot"
                params = {'address': token_address, 'chainID': self._get_chain_id(chain)}
                
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('honeypotResult', {}).get('isHoneypot', False)
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking honeypot: {e}")
            return False
    
    def _get_chain_id(self, chain: str) -> int:
        """Get chain ID for blockchain name."""
        chain_ids = {
            'ethereum': 1,
            'bsc': 56,
            'polygon': 137,
            'avalanche': 43114,
            'fantom': 250,
            'arbitrum': 42161,
            'optimism': 10
        }
        return chain_ids.get(chain.lower(), 1)
    
    def get_moonshots(self, min_change: float = 100.0) -> List[MemeToken]:
        """
        Get potential moonshot tokens.
        
        Args:
            min_change: Minimum 24h price change percentage
            
        Returns:
            List of moonshot candidates
        """
        moonshots = [
            token for token in self.meme_tokens
            if token.price_change_24h >= min_change
            and token.risk_level in ['low', 'medium']
            and token.liquidity_usd >= 50000
        ]
        
        moonshots.sort(key=lambda t: t.price_change_24h, reverse=True)
        
        return moonshots[:10]  # Top 10
    
    def get_safe_tokens(self) -> List[MemeToken]:
        """Get tokens with low rug risk."""
        safe = [
            token for token in self.meme_tokens
            if token.risk_level == 'low'
            and token.liquidity_usd >= 100000
        ]
        
        safe.sort(key=lambda t: t.volume_24h, reverse=True)
        
        return safe
    
    def get_scan_summary(self) -> str:
        """Get formatted scan summary."""
        if not self.meme_tokens:
            return "No tokens scanned yet"
        
        moonshots = self.get_moonshots()
        safe_count = sum(1 for t in self.meme_tokens if t.risk_level == 'low')
        risky_count = sum(1 for t in self.meme_tokens if t.risk_level in ['high', 'critical'])
        
        summary = f"""
🚀 MEME COIN SCAN RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Total Scanned: {len(self.meme_tokens)}
✅ Safe Tokens: {safe_count}
⚠️ Risky Tokens: {risky_count}

💎 TOP MOONSHOTS:
"""
        
        for i, token in enumerate(moonshots[:5], 1):
            risk_emoji = "✅" if token.risk_level == 'low' else "⚠️" if token.risk_level == 'medium' else "❌"
            summary += f"\n{i}. {token.symbol} ({token.chain.upper()})"
            summary += f"\n   Price: ${token.price:.8f}"
            summary += f"\n   24h Change: {token.price_change_24h:+.1f}%"
            summary += f"\n   Liquidity: ${token.liquidity_usd:,.0f}"
            summary += f"\n   Risk: {risk_emoji} {token.risk_level.upper()}"
        
        return summary.strip()
    
    def get_tokens(self) -> List[MemeToken]:
        """Get all scanned tokens."""
        return self.meme_tokens
