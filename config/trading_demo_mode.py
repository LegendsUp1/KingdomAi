# Demo Trading Mode Configuration
# Set these to True to enable demo trading without real API keys

DEMO_MODE_ENABLED = False
USE_TESTNET = False  # Set to True for testnet trading

# Demo mode will:
# - Use simulated order execution
# - Show real market data
# - Not require API keys
# - Not place actual trades

# To use real trading:
# 1. Set DEMO_MODE_ENABLED = False
# 2. Add your API keys to config/api_keys.json
# 3. Ensure you have sufficient funds in your exchange account
