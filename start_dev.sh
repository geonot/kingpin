#!/usr/bin/env bash
set -e

# Kingpin Casino Development Startup Script
# Elite, clean, and efficient - just how we like it.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/casino_be"
FRONTEND_DIR="$PROJECT_ROOT/casino_fe"

# Terminal detection and command setup
detect_terminal() {
    if command -v gnome-terminal >/dev/null 2>&1; then
        echo "gnome-terminal"
    elif command -v konsole >/dev/null 2>&1; then
        echo "konsole"
    elif command -v xterm >/dev/null 2>&1; then
        echo "xterm"
    elif command -v alacritty >/dev/null 2>&1; then
        echo "alacritty"
    elif command -v kitty >/dev/null 2>&1; then
        echo "kitty"
    else
        echo "unknown"
    fi
}

launch_terminal() {
    local title="$1"
    local command="$2"
    local terminal=$(detect_terminal)

    case "$terminal" in
        gnome-terminal)
            gnome-terminal --title="$title" -- bash -c "$command; exec bash" >/dev/null 2>&1 &
            ;;
        konsole)
            konsole --title "$title" -e bash -c "$command; exec bash" >/dev/null 2>&1 &
            ;;
        xterm)
            xterm -title "$title" -e bash -c "$command; exec bash" >/dev/null 2>&1 &
            ;;
        alacritty)
            alacritty --title "$title" -e bash -c "$command; exec bash" >/dev/null 2>&1 &
            ;;
        kitty)
            kitty --title "$title" bash -c "$command; exec bash" >/dev/null 2>&1 &
            ;;
        *)
            echo "⚠️  No supported terminal found. Run manually:"
            echo "   $command"
            return 1
            ;;
    esac
}

check_prerequisites() {
    echo "🔍 Checking prerequisites..."
    
    # Check if we're in the right directory
    if [[ ! -d "$BACKEND_DIR" ]] || [[ ! -d "$FRONTEND_DIR" ]]; then
        echo "❌ Run this script from the project root directory"
        exit 1
    fi

    # Check backend .env file
    if [[ ! -f "$BACKEND_DIR/.env" ]]; then
        echo "❌ Backend .env file not found. Run bootstrap.sh first."
        exit 1
    fi

    # Check node_modules
    if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
        echo "❌ Frontend dependencies not installed. Run 'npm install' in casino_fe/"
        exit 1
    fi

    echo "✅ Prerequisites check passed"
}

start_postgresql() {
    echo "🐘 Checking PostgreSQL status..."
    
    if pg_isready -q 2>/dev/null; then
        echo "✅ PostgreSQL is running"
        return 0
    fi

    echo "🚀 Starting PostgreSQL..."
    if sudo service postgresql start; then
        # Wait for PostgreSQL to be ready
        local retries=10
        while ! pg_isready -q 2>/dev/null && [[ $retries -gt 0 ]]; do
            echo "   ⏳ Waiting for PostgreSQL... ($retries attempts left)"
            sleep 2
            ((retries--))
        done

        if pg_isready -q 2>/dev/null; then
            echo "✅ PostgreSQL started successfully"
        else
            echo "❌ PostgreSQL failed to start properly"
            exit 1
        fi
    else
        echo "❌ Failed to start PostgreSQL service"
        exit 1
    fi
}

start_services() {
    echo "🚀 Launching development services..."
    
    # Backend terminal
    local backend_cmd="cd '$BACKEND_DIR' && echo '🔧 Loading environment...' && source .env && echo '🔧 Starting Flask backend...' && flask run --host=0.0.0.0"
    launch_terminal "Kingpin Backend" "$backend_cmd"
    
    # Wait a moment for backend to start
    sleep 2
    
    # Frontend terminal  
    local frontend_cmd="cd '$FRONTEND_DIR' && echo '🎨 Starting Vue.js frontend...' && npm run serve"
    launch_terminal "Kingpin Frontend" "$frontend_cmd"
    
    echo "✅ Services launched in separate terminals"
    echo ""
    echo "📍 Access points:"
    echo "   Backend:  http://localhost:5000"
    echo "   Frontend: http://localhost:8080"
    echo ""
    echo "💡 Tip: Check the terminal windows for startup logs"
}

main() {
    echo "🎰 Kingpin Casino Development Environment"
    echo "========================================"
    
    check_prerequisites
    start_postgresql
    start_services
    
    echo "🎉 Development environment ready!"
    echo "   Press Ctrl+C in the terminal windows to stop services"
}

# Handle interrupts gracefully
trap 'echo ""; echo "👋 Startup script interrupted"; exit 130' INT

main "$@"