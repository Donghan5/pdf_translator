#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Easy PDF Translator — Launch Script
# =============================================================================

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CPP_SERVER_BIN="$PROJECT_DIR/cpp_server/build/vectordb_server"
CPP_SERVER_PID=""
VENV_DIR="$PROJECT_DIR/venv"

RED='\033[91m'
GREEN='\033[92m'
YELLOW='\033[93m'
BOLD='\033[1m'
RESET='\033[0m'

cleanup() {
    if [[ -n "$CPP_SERVER_PID" ]] && kill -0 "$CPP_SERVER_PID" 2>/dev/null; then
        echo -e "\n${YELLOW}Stopping cpp_server (PID $CPP_SERVER_PID)...${RESET}"
        kill "$CPP_SERVER_PID" 2>/dev/null || true
        wait "$CPP_SERVER_PID" 2>/dev/null || true
        echo -e "${GREEN}cpp_server stopped.${RESET}"
    fi
}
trap cleanup EXIT INT TERM

# -----------------------------------------------------------------------------
# 1. Check Python
# -----------------------------------------------------------------------------
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo -e "${RED}Error: Python 3 not found. Please install Python 3.9+.${RESET}"
    exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 9 ]]; then
    echo -e "${RED}Error: Python 3.9+ required (found $PY_VERSION).${RESET}"
    exit 1
fi
echo -e "${GREEN}Python $PY_VERSION found.${RESET}"

# -----------------------------------------------------------------------------
# 2. Virtual environment
# -----------------------------------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
    echo -e "${YELLOW}Creating virtual environment...${RESET}"
    "$PYTHON" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo -e "${GREEN}Virtual environment activated.${RESET}"

# -----------------------------------------------------------------------------
# 3. Install Python dependencies
# -----------------------------------------------------------------------------
echo "Checking Python dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "$PROJECT_DIR/requirements.txt"
echo -e "${GREEN}Python dependencies ready.${RESET}"

# Download NLTK data (needed for sentence tokenization)
"$PYTHON" -c "import nltk; nltk.download('punkt_tab', quiet=True)" 2>/dev/null || true

# -----------------------------------------------------------------------------
# 4. Check .env file
# -----------------------------------------------------------------------------
if [[ ! -f "$PROJECT_DIR/.env" ]]; then
    echo -e "${YELLOW}No .env file found. Creating template...${RESET}"
    cat > "$PROJECT_DIR/.env" <<'ENVEOF'
GROQ_API_KEY=
GROQ_MODEL_TRANSLATE=llama-3.1-8b-instant
GROQ_MODEL_QA=llama-3.3-70b-versatile
CPP_SERVER_HOST=localhost
CPP_SERVER_PORT=50051
CHUNK_TOKEN_SIZE=1500
CHUNK_OVERLAP_SENTENCES=2
DEFAULT_SOURCE_LANG=en
DEFAULT_TARGET_LANG=ko
ENVEOF
    echo -e "${RED}Please set your GROQ_API_KEY in $PROJECT_DIR/.env and re-run.${RESET}"
    exit 1
fi

# Validate GROQ_API_KEY is set
GROQ_KEY=$(grep -E '^GROQ_API_KEY=' "$PROJECT_DIR/.env" | cut -d'=' -f2-)
if [[ -z "$GROQ_KEY" ]]; then
    echo -e "${RED}Error: GROQ_API_KEY is empty in .env. Please set it and re-run.${RESET}"
    exit 1
fi
echo -e "${GREEN}.env loaded.${RESET}"

# -----------------------------------------------------------------------------
# 5. Build C++ server (if needed)
# -----------------------------------------------------------------------------
if [[ ! -x "$CPP_SERVER_BIN" ]]; then
    echo -e "${YELLOW}Building C++ VectorDB server...${RESET}"

    if ! command -v cmake &>/dev/null; then
        echo -e "${RED}Error: cmake not found. Install it to build the C++ server.${RESET}"
        echo "  Ubuntu/Debian: sudo apt install cmake build-essential"
        echo "  Fedora:        sudo dnf install cmake gcc-c++"
        echo "  macOS:         brew install cmake"
        exit 1
    fi

    mkdir -p "$PROJECT_DIR/cpp_server/build"
    cmake -S "$PROJECT_DIR/cpp_server" -B "$PROJECT_DIR/cpp_server/build" -DCMAKE_BUILD_TYPE=Release
    cmake --build "$PROJECT_DIR/cpp_server/build" --parallel "$(nproc 2>/dev/null || echo 4)"

    if [[ ! -x "$CPP_SERVER_BIN" ]]; then
        echo -e "${RED}Error: C++ server build failed.${RESET}"
        exit 1
    fi
    echo -e "${GREEN}C++ server built successfully.${RESET}"
else
    echo -e "${GREEN}C++ server binary found.${RESET}"
fi

# -----------------------------------------------------------------------------
# 6. Start C++ server in background
# -----------------------------------------------------------------------------
CPP_PORT=$(grep -E '^CPP_SERVER_PORT=' "$PROJECT_DIR/.env" | cut -d'=' -f2- || echo "50051")
CPP_PORT="${CPP_PORT:-50051}"

if lsof -i :"$CPP_PORT" &>/dev/null || ss -tlnp 2>/dev/null | grep -q ":${CPP_PORT} "; then
    echo -e "${GREEN}cpp_server already running on port $CPP_PORT.${RESET}"
else
    echo -e "${YELLOW}Starting cpp_server on port $CPP_PORT...${RESET}"
    "$CPP_SERVER_BIN" &
    CPP_SERVER_PID=$!
    sleep 1

    if kill -0 "$CPP_SERVER_PID" 2>/dev/null; then
        echo -e "${GREEN}cpp_server started (PID $CPP_SERVER_PID).${RESET}"
    else
        echo -e "${YELLOW}Warning: cpp_server may not have started correctly.${RESET}"
        CPP_SERVER_PID=""
    fi
fi

# -----------------------------------------------------------------------------
# 7. Create input directory
# -----------------------------------------------------------------------------
mkdir -p "$PROJECT_DIR/input"

# -----------------------------------------------------------------------------
# 8. Launch the translator
# -----------------------------------------------------------------------------
echo ""
echo -e "${BOLD}Launching Easy PDF Translator...${RESET}"
echo ""

cd "$PROJECT_DIR"
"$PYTHON" main.py
