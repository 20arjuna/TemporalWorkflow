#!/bin/bash

echo "Hey there! Let's get you set up..."
if ! docker info >/dev/null 2>&1; then
    echo ""
    echo "❌ Docker Desktop is not running!"
    echo ""
    echo "PLease start Docker Desktop and run this script again."
    echo ""
    echo "If you don't have Docker Desktop installed, you can download it here:"
    echo "   macOS: https://docs.docker.com/desktop/install/mac-install/"
    echo "   Linux: https://docs.docker.com/desktop/install/linux-install/"  
    echo "   Windows: https://docs.docker.com/desktop/install/windows-install/"
    echo ""
    echo "👋 Come back and run ./start4.sh when Docker Desktop is running!"
    exit 1
fi



# Function to show loading animation
show_loading() {
    local message="$1"
    local pid=$2
    local delay=0.5
    local spinstr='|/-\'
    
    echo -n "$message "
    while kill -0 $pid 2>/dev/null; do
        local temp=${spinstr#?}
        printf " [%c]  " "$spinstr"
        local spinstr=$temp${spinstr%"$temp"}
        sleep $delay
        printf "\b\b\b\b\b\b"
    done
    printf "    \b\b\b\b"
    echo "✅"
}

# Function to run setup silently in background
setup_environment() {
    # 1. Create venv silently
    python3 -m venv venv >/dev/null 2>&1
    
    # 2. Activate and install deps silently  
    source venv/bin/activate
    pip3 install -r requirements.txt >/dev/null 2>&1
    
    # 3. Start docker services silently
    docker compose down >/dev/null 2>&1
    docker compose -f docker-compose.yml up -d >/dev/null 2>&1
    
    # 4. Wait for Temporal to be ready
    while ! nc -z localhost 7233 2>/dev/null; do
        sleep 2
    done
}

# Run setup in background and show loading
setup_environment &
SETUP_PID=$!

show_loading "🚀 Setting up your workflow environment..." $SETUP_PID

wait $SETUP_PID

echo ""
# echo "🎯 Everything is ready! Launching CLI..."
echo ""

# Activate venv and run CLI
source venv/bin/activate
python3 cli.py