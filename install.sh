#!/bin/bash
set -e

# Configuration
REPO_URL="https://github.com/appff/NightShift.git"
INSTALL_DIR="$HOME/.night_shift_app"
BRANCH="main"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}   Night Shift Installer / Updater     ${NC}"
echo -e "${BLUE}=======================================${NC}"

# 1. Check Prerequisites
command -v git >/dev/null 2>&1 || { echo -e "${RED}Error: git is not installed.${NC}"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}Error: python3 is not installed.${NC}"; exit 1; }

# Recommended but optional for core (required for MCP)
echo -e "${BLUE}Checking optional prerequisites for MCP features...${NC}"
command -v uv >/dev/null 2>&1 || echo -e "${YELLOW}Warning: 'uv' not found. Recommended for Serena MCP.${NC}"
command -v npx >/dev/null 2>&1 || echo -e "${YELLOW}Warning: 'npx' not found. Required for Sequential Thinking MCP.${NC}"

# 2. Clone or Update Repo
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Found existing installation at $INSTALL_DIR${NC}"
    echo -e "${GREEN}Updating Night Shift...${NC}"
    cd "$INSTALL_DIR"
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}Warning: You have uncommitted changes in the installation directory.${NC}"
        echo -e "${YELLOW}Stashing changes before update...${NC}"
        git stash
    fi
    
    git fetch origin
    git checkout $BRANCH
    git pull origin $BRANCH
else
    echo -e "${GREEN}Cloning Night Shift into $INSTALL_DIR...${NC}"
    git clone -b $BRANCH $REPO_URL "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# 3. Setup Virtual Environment
echo -e "${GREEN}Setting up Python virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

# 4. Install Dependencies
echo -e "${GREEN}Installing/Updating dependencies...${NC}"
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${RED}Error: requirements.txt not found!${NC}"
    exit 1
fi

# 5. Create Launcher Script (Wrapper)
echo -e "${GREEN}Creating 'nightshift' launcher...${NC}"
cat > "$INSTALL_DIR/nightshift" <<EOF
#!/bin/bash
# Wrapper to run Night Shift from anywhere with the correct venv
SOURCE_DIR="$INSTALL_DIR"
source "\$SOURCE_DIR/.venv/bin/activate"
python "\$SOURCE_DIR/night_shift.py" "\$@"
EOF

chmod +x "$INSTALL_DIR/nightshift"

# 6. Add to PATH (if needed)
SHELL_CONFIG=""
case "$SHELL" in
  */zsh) SHELL_CONFIG="$HOME/.zshrc" ;;
  */bash) SHELL_CONFIG="$HOME/.bashrc" ;;
  *) SHELL_CONFIG="$HOME/.profile" ;;
esac

if [[ ":$PATH:" != ":$INSTALL_DIR:"* ]]; then
    echo -e "${YELLOW}Adding $INSTALL_DIR to PATH in $SHELL_CONFIG...${NC}"
    echo "" >> "$SHELL_CONFIG"
    echo "# Night Shift CLI" >> "$SHELL_CONFIG"
    echo "export PATH=\"
$PATH:$INSTALL_DIR\"" >> "$SHELL_CONFIG"
    echo -e "${GREEN}Added to PATH. Please restart your terminal or run: source $SHELL_CONFIG${NC}"
else
    echo -e "${GREEN}Path already configured.${NC}"
fi

echo -e "${BLUE}=======================================${NC}"
echo -e "${GREEN}Night Shift installation complete! 🌙${NC}"
echo -e "${BLUE}Try running: ${YELLOW}nightshift --help${NC}"
echo -e "${BLUE}=======================================${NC}"
