
import ccxt
import os
import json
import logging
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

# Load .env file
load_dotenv()

logger = logging.getLogger(__name__)

class ExchangeConnector:
    """
    Manages connection to Crypto Exchanges via CCXT.
    Supports Real-time data fetching and Order Execution.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.exchange_name = self.config.get("name", "okx")
        self.api_key = self.config.get("api_key")
        self.secret = self.config.get("secret")
        self.password = self.config.get("password") # OKX/Kucoin uses password/passphrase
        self.sandbox = self.config.get("sandbox", False)
        self.options = self.config.get("options", {})
        
        self.exchange = self._initialize_exchange()
        
    def _initialize_exchange(self):
        """Initialize CCXT exchange instance"""
        
        exchange_class = getattr(ccxt, self.exchange_name)
        
        # Check for environment variables if placeholders are found
        if self.api_key == "YOUR_OKX_API_KEY":
            self.api_key = os.getenv("OKX_API_KEY")
        if self.secret == "YOUR_OKX_SECRET":
            self.secret = os.getenv("OKX_SECRET")
        if self.password == "YOUR_OKX_PASSWORD":
            self.password = os.getenv("OKX_PASSWORD")
            
        params = {
            'apiKey': self.api_key,
            'secret': self.secret,
            'password': self.password,
            'enableRateLimit': True,
            'options': self.options,
        }
        
        exchange = exchange_class(params)
        
        if self.sandbox:
            logger.info(f"Enabling SANDBOX mode for {self.exchange_name}")
            exchange.set_sandbox_mode(True)
            
        return exchange
    
    def check_connection(self):
        """Verify connectivity by fetching balance or time"""
        try:
            # Load markets first (required for many operations)
            self.exchange.load_markets()
            logger.info(f"Markets loaded. Symbols: {len(self.exchange.markets)}")
            
            # Fetch Time
            time = self.exchange.fetch_time()
            logger.info(f"Server Time: {time}")
            
            # Try to fetch balance if keys are provided
            if self.api_key and self.secret:
                balance = self.exchange.fetch_balance()
                # Just show total USDT for brevity
                usdt = balance.get('USDT', {})
                logger.info(f"Account Balance (prop): {usdt}")
                return True, "Connected & Authenticated"
            else:
                return True, "Connected (Public Only)"
                
        except Exception as e:
            logger.error(f"Connection Failed: {e}")
            return False, str(e)

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1h', limit: int = 100):
        """Fetch OHLCV data"""
        return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

    def get_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Fetch latest prices for a list of symbols"""
        try:
            # Most exchanges support fetch_tickers
            tickers = self.exchange.fetch_tickers(symbols)
            return {s: tickers[s]['last'] for s in symbols if s in tickers}
        except Exception as e:
            logger.warning(f"Batch fetch_tickers failed: {e}. Falling back to individual fetch.")
            prices = {}
            for symbol in symbols:
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    prices[symbol] = ticker['last']
                except Exception as e2:
                    logger.error(f"Failed to fetch price for {symbol}: {e2}")
            return prices

