#!/bin/bash
# ASCII Art Generator - Termux Startup Script

# Configuration
APP_DIR="$HOME/PYTHON\ PROJECTS/1/Ascii_ART-GEN"
PORT=5000

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Starting ASCII Art Generator...${NC}"

# Create logs directory
mkdir -p "$HOME/PYTHON PROJECTS/1/Ascii_ART-GEN/logs"

# Check if already running
if pgrep -f "python.*app.py" > /dev/null; then
    echo -e "${YELLOW}Server is already running!${NC}"
    pgrep -f "python.*app.py" | xargs ps -p
    exit 1
fi

# Start the server
cd "$HOME/PYTHON PROJECTS/1/Ascii_ART-GEN"
export FLASK_ENV=production
export PORT=$PORT

python app.py &

# Wait a moment and check
sleep 2

if pgrep -f "python.*app.py" > /dev/null; then
    echo -e "${GREEN}Server started successfully!${NC}"
    echo -e "Access at: ${YELLOW}http://localhost:$PORT${NC}"
    echo -e "Health check: ${YELLOW}http://localhost:$PORT/health${NC}"
else
    echo -e "${RED}Failed to start server. Check logs/app.log${NC}"
    exit 1
fi
