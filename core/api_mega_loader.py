#!/usr/bin/env python3
"""
Mega API Key Loader - Loads 100+ keys from ALL sources
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

def load_all_api_keys(project_root):
    """Load every API key from .env and all JSON files"""
    all_keys = {}
    
    # 1. Load from .env
    env_file = project_root / '.env'
    if env_file.exists():
        load_dotenv(env_file)
    
    # 2. Scan environment variables
    for key, value in os.environ.items():
        if any(term in key.lower() for term in ['api', 'key', 'token', 'secret']):
            if value and value not in ['', 'YOUR_API_KEY_HERE', 'none', 'None']:
                all_keys[key.lower()] = value
    
    # 3. Load from ALL JSON files in config dirs
    search_paths = [
        project_root / 'config',
        project_root / 'data' / 'api_keys',
        project_root / 'configs',
        project_root / '.config',
        project_root / 'data'
    ]
    
    for search_path in search_paths:
        if not search_path.exists():
            continue
        
        for json_file in search_path.rglob('*.json'):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                extracted = extract_keys_recursive(data)
                all_keys.update(extracted)
            except:
                pass
    
    return all_keys

def extract_keys_recursive(data, prefix=''):
    """Recursively extract all API keys from nested JSON"""
    keys = {}
    
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str):
                k_lower = k.lower()
                if any(term in k_lower for term in ['api', 'key', 'token', 'secret']):
                    if v and v not in ['', 'YOUR_API_KEY_HERE', 'none', 'None']:
                        key_name = f"{prefix}{k}".lower().replace(' ', '_')
                        keys[key_name] = v
            elif isinstance(v, (dict, list)):
                nested = extract_keys_recursive(v, f"{prefix}{k}_")
                keys.update(nested)
    
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                nested = extract_keys_recursive(item, prefix)
                keys.update(nested)
    
    return keys
