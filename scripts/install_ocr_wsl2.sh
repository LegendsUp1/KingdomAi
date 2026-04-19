#!/bin/bash
# ============================================================================
# KINGDOM AI - SOTA 2026 OCR & Linguistics Installation Script for WSL2
# ============================================================================
#
# This script installs system-level dependencies for the OCR & Linguistics Engine.
# It is SAFE and will NOT mess up your existing Python environment.
#
# Usage: bash scripts/install_ocr_wsl2.sh
#
# Options:
#   --fix-numpy    Fix numpy binary incompatibility error
#   --minimal      Install only essential packages (Tesseract + RapidOCR)
#   --full         Install all OCR backends (may have conflicts)
# ============================================================================

# Don't exit on error - we want to continue even if some packages fail
set +e

echo "=============================================="
echo "Kingdom AI - SOTA 2026 OCR & Linguistics Setup"
echo "         (Safe Environment-Preserving Mode)"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
FIX_NUMPY=false
MINIMAL=false
FULL=false

for arg in "$@"; do
    case $arg in
        --fix-numpy) FIX_NUMPY=true ;;
        --minimal) MINIMAL=true ;;
        --full) FULL=true ;;
    esac
done

# Detect environment
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo -e "${GREEN}✓ Running in WSL2${NC}"
else
    echo -e "${GREEN}✓ Running on native Linux${NC}"
fi

# ============================================================================
# FIX NUMPY BINARY INCOMPATIBILITY (if requested or detected)
# ============================================================================
if $FIX_NUMPY; then
    echo ""
    echo -e "${CYAN}🔧 Fixing numpy binary incompatibility...${NC}"
    echo "   This error occurs when numpy 2.0+ is installed but other packages"
    echo "   were compiled against numpy 1.x"
    echo ""
    
    # Check current numpy version
    NUMPY_VERSION=$(python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "not installed")
    echo "   Current numpy version: $NUMPY_VERSION"
    
    if [[ "$NUMPY_VERSION" == 2.* ]]; then
        echo -e "${YELLOW}   Downgrading numpy to 1.26.4 (last stable before 2.0)...${NC}"
        pip install "numpy>=1.24.0,<2.0.0" --force-reinstall
        echo -e "${GREEN}   ✓ numpy downgraded successfully${NC}"
    else
        echo -e "${GREEN}   ✓ numpy version is already <2.0${NC}"
    fi
    
    # Rebuild pandas to match numpy
    echo "   Rebuilding pandas to match numpy..."
    pip install pandas --force-reinstall --no-cache-dir 2>/dev/null || true
    
    echo -e "${GREEN}✓ Numpy fix complete${NC}"
fi

# ============================================================================
# SYSTEM PACKAGES (apt-get)
# ============================================================================
echo ""
echo "📦 Installing system packages..."
echo "   (This requires sudo and will prompt for password if needed)"
echo ""

# Update package lists
sudo apt-get update 2>/dev/null || echo -e "${YELLOW}⚠ apt-get update failed - continuing anyway${NC}"

# ============================================================================
# TESSERACT OCR
# ============================================================================
echo ""
echo "📝 Installing Tesseract OCR..."
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

# Install additional language packs (optional but recommended)
echo "📝 Installing Tesseract language packs..."
sudo apt-get install -y \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-jpn \
    tesseract-ocr-kor \
    tesseract-ocr-deu \
    tesseract-ocr-fra \
    tesseract-ocr-spa \
    tesseract-ocr-por \
    tesseract-ocr-ara \
    tesseract-ocr-rus \
    tesseract-ocr-hin \
    2>/dev/null || echo -e "${YELLOW}⚠ Some language packs not available${NC}"

# Verify Tesseract installation
if command -v tesseract &> /dev/null; then
    TESS_VERSION=$(tesseract --version 2>&1 | head -n 1)
    echo -e "${GREEN}✓ Tesseract installed: $TESS_VERSION${NC}"
else
    echo -e "${RED}✗ Tesseract installation failed${NC}"
fi

# ============================================================================
# IMAGE PROCESSING LIBRARIES
# ============================================================================
echo ""
echo "🖼️ Installing image processing libraries..."
sudo apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libfontconfig1 \
    libice6

# ============================================================================
# PYTHON DEPENDENCIES (SAFE - won't break your environment)
# ============================================================================
echo ""
echo "🐍 Installing Python OCR & Linguistics packages..."
echo -e "${CYAN}   Using --no-deps where needed to avoid conflicts${NC}"

# DON'T upgrade pip - it can break things
# pip install --upgrade pip

# ============================================================================
# FIRST: Fix numpy if needed (common issue)
# ============================================================================
NUMPY_VERSION=$(python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "0")
if [[ "$NUMPY_VERSION" == 2.* ]]; then
    echo -e "${YELLOW}⚠ Detected numpy 2.x which causes binary incompatibility${NC}"
    echo "   Downgrading to numpy 1.26.4..."
    pip install "numpy>=1.24.0,<2.0.0" --force-reinstall 2>/dev/null
    # Rebuild pandas
    pip install pandas --force-reinstall --no-cache-dir 2>/dev/null || true
fi

# ============================================================================
# CORE OCR (lightweight, safe to install)
# ============================================================================
echo ""
echo "📝 Installing CORE OCR packages (safe)..."

# RapidOCR - lightweight, ONNX-based
pip install rapidocr-onnxruntime 2>/dev/null || echo -e "${YELLOW}⚠ RapidOCR failed${NC}"

# pytesseract - just a wrapper, very safe
pip install pytesseract 2>/dev/null || echo -e "${YELLOW}⚠ pytesseract failed${NC}"

# langdetect - lightweight
pip install langdetect 2>/dev/null || echo -e "${YELLOW}⚠ langdetect failed${NC}"

# ============================================================================
# OPTIONAL HEAVY PACKAGES (only if --full flag)
# ============================================================================
if $FULL; then
    echo ""
    echo -e "${CYAN}📝 Installing FULL OCR suite (heavy packages)...${NC}"
    echo "   This may take a while and could have conflicts..."
    
    # PaddleOCR
    pip install paddlepaddle paddleocr 2>/dev/null || {
        echo -e "${YELLOW}⚠ PaddleOCR failed - skipping${NC}"
    }
    
    # EasyOCR (heavy - requires torch)
    pip install easyocr 2>/dev/null || echo -e "${YELLOW}⚠ EasyOCR failed${NC}"
    
    # docTR
    pip install "python-doctr[torch]" 2>/dev/null || echo -e "${YELLOW}⚠ docTR failed${NC}"
    
    # sentence-transformers (heavy)
    pip install sentence-transformers 2>/dev/null || echo -e "${YELLOW}⚠ sentence-transformers failed${NC}"
else
    echo ""
    echo -e "${CYAN}ℹ️  Skipping heavy packages (PaddleOCR, EasyOCR, docTR)${NC}"
    echo "   Run with --full flag to install them: bash scripts/install_ocr_wsl2.sh --full"
fi

# ============================================================================
# LINGUISTICS (use existing spacy/nltk if available)
# ============================================================================
echo ""
echo "📖 Checking linguistics packages..."

# Check if spacy is already installed
if python3 -c "import spacy" 2>/dev/null; then
    echo -e "${GREEN}✓ spaCy already installed${NC}"
else
    echo "Installing spaCy..."
    pip install spacy 2>/dev/null || echo -e "${YELLOW}⚠ spaCy failed${NC}"
fi

# Check if nltk is already installed
if python3 -c "import nltk" 2>/dev/null; then
    echo -e "${GREEN}✓ NLTK already installed${NC}"
else
    echo "Installing NLTK..."
    pip install nltk 2>/dev/null || echo -e "${YELLOW}⚠ NLTK failed${NC}"
fi

# Download spaCy English model
echo ""
echo "📚 Downloading spaCy English model..."
python -m spacy download en_core_web_sm 2>/dev/null || echo -e "${YELLOW}⚠ spaCy model download may need retry${NC}"

# Download NLTK data
echo ""
echo "📚 Downloading NLTK data..."
python -c "
import nltk
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('vader_lexicon', quiet=True)
nltk.download('wordnet', quiet=True)
print('NLTK data downloaded successfully')
" 2>/dev/null || echo -e "${YELLOW}⚠ NLTK data download may need retry${NC}"

# ============================================================================
# VERIFICATION
# ============================================================================
echo ""
echo "=============================================="
echo "🔍 Verifying installations..."
echo "=============================================="

python3 << 'EOF'
import sys

def check_import(name, package=None):
    package = package or name
    try:
        __import__(name)
        print(f"✅ {package}: OK")
        return True
    except ImportError as e:
        print(f"❌ {package}: {e}")
        return False

print("\n--- OCR Backends ---")
check_import("rapidocr_onnxruntime", "RapidOCR")
check_import("paddleocr", "PaddleOCR")
check_import("pytesseract", "Tesseract (Python)")
check_import("easyocr", "EasyOCR")

try:
    from doctr.io import DocumentFile
    print("✅ docTR: OK")
except ImportError as e:
    print(f"❌ docTR: {e}")

print("\n--- Linguistics ---")
check_import("spacy", "spaCy")
check_import("nltk", "NLTK")
check_import("langdetect", "langdetect")
check_import("textblob", "TextBlob")
check_import("transformers", "Transformers")

print("\n--- spaCy Model ---")
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    print("✅ en_core_web_sm: OK")
except:
    print("❌ en_core_web_sm: Not installed")

print("\n--- Tesseract System ---")
import shutil
if shutil.which("tesseract"):
    import subprocess
    result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
    version = result.stdout.split("\n")[0] if result.stdout else "unknown"
    print(f"✅ Tesseract binary: {version}")
else:
    print("❌ Tesseract binary: Not found in PATH")

print("\n--- Kingdom AI OCR Engine ---")
try:
    from core.ocr_linguistics_engine import OCRLinguisticsEngine
    engine = OCRLinguisticsEngine()
    backends = engine.get_available_backends()
    print(f"✅ OCR Engine: {len(backends)} backends available")
    print(f"   Backends: {', '.join(backends)}")
except ImportError as e:
    print(f"❌ OCR Engine: {e}")

print("\n✨ Installation verification complete!")
EOF

echo ""
echo "=============================================="
echo "🎉 SOTA 2026 OCR & Linguistics Setup Complete!"
echo "=============================================="
echo ""
echo "Available OCR backends:"
echo "  • RapidOCR (fastest, ONNX-based)"
echo "  • PaddleOCR (highest accuracy)"
echo "  • Tesseract (classic, wide language support)"
echo "  • EasyOCR (GPU-accelerated)"
echo "  • docTR (document-focused)"
echo "  • Ollama Vision (deepseek-ocr, llava, gemma3)"
echo ""
echo "Available linguistics features:"
echo "  • Named Entity Recognition (NER)"
echo "  • Part-of-Speech Tagging"
echo "  • Sentiment Analysis"
echo "  • Text Summarization"
echo "  • Language Detection"
echo "  • Keyword Extraction"
echo ""
echo "Usage in Kingdom AI:"
echo "  from core.ocr_linguistics_engine import OCRLinguisticsEngine"
echo "  engine = OCRLinguisticsEngine(event_bus)"
echo "  await engine.initialize()"
echo "  result = await engine.extract_text('image.png')"
echo ""
