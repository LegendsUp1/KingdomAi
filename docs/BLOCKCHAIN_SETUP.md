# Blockchain Configuration and Verification

This document outlines how to set up and verify blockchain connectivity for the Kingdom AI system.

## Prerequisites

1. Python 3.8+
2. Required Python packages (install with `pip install -r requirements.txt`):
   - web3>=7.0.0
   - aiohttp
   - python-dotenv
   - eth-typing

## Environment Setup

1. Copy the example environment file and update with your API keys:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file and add your API keys and RPC endpoints.

## Configuration Files

The system uses the following configuration files in `config/blockchain/`:

- `bitcoin.json`: Bitcoin network configuration
- `ethereum.json`: Ethereum network configuration
- `crosschain.json`: Cross-chain bridge configuration

## Verification Tools

### 1. Blockchain Connection Checker

Run a quick check of blockchain connectivity:

```bash
python scripts/check_blockchain.py
```

This will test connections to all configured blockchain networks and public nodes.

### 2. Full Blockchain Verifier

For a more thorough verification:

```bash
python scripts/verify_blockchain.py
```

## Troubleshooting

### Common Issues

1. **Connection Failures**:
   - Check your internet connection
   - Verify RPC URLs in the config files
   - Ensure API keys are correctly set in `.env`

2. **Rate Limiting**:
   - Some public RPC endpoints have rate limits
   - Consider using your own node or a paid service for production use

3. **SSL Certificate Issues**:
   - If you encounter SSL errors, verify the certificate chain
   - For development, you can disable SSL verification (not recommended for production)

## Adding New Blockchains

To add support for a new blockchain:

1. Create a new config file in `config/blockchain/`
2. Add RPC endpoints and API keys
3. Update the verification scripts to include the new chain

## Security Notes

- Never commit API keys or private keys to version control
- Use environment variables for sensitive information
- Regularly rotate API keys and update the `.env` file
