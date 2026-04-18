#!/usr/bin/env python3
"""
NLTK SSL Certificate Fix for Kingdom AI
Disables SSL verification for NLTK downloads in development
"""

import ssl
import nltk

# Disable SSL verification for NLTK downloads
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Download required NLTK data
def download_nltk_data():
    """Download required NLTK datasets"""
    datasets = ['wordnet', 'punkt', 'averaged_perceptron_tagger', 'maxent_ne_chunker', 'words']
    
    for dataset in datasets:
        try:
            nltk.download(dataset, quiet=True)
            print(f"✅ Downloaded NLTK dataset: {dataset}")
        except Exception as e:
            print(f"⚠️ Failed to download {dataset}: {e}")

# Auto-run on import
download_nltk_data()
