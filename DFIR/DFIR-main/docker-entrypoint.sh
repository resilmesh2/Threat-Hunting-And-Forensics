#!/bin/bash
# Docker entrypoint script for CAI DFIR container
# Configures network and environment based on CAI_MODEL

set -e

echo "🚀 CAI DFIR Container - Starting..."
echo "======================================"

# Load environment variables from .env if it exists
if [ -f /app/.env ]; then
    echo "📄 Loading environment from .env file..."
    export $(cat /app/.env | grep -v '^#' | xargs)
fi

# Determine which model is configured
CAI_MODEL=${CAI_MODEL:-alias1}
echo "🤖 CAI_MODEL configured: $CAI_MODEL"

# If using Ollama, wait for it to be ready and download model if needed
if [ "$CAI_MODEL" = "ollama" ]; then
    echo "✅ Using Ollama model"
    OLLAMA_API_BASE=${OLLAMA_API_BASE:-http://localhost:11434/v1}
    OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.2:1b}
    
    echo "⏳ Waiting for Ollama to be ready..."
    max_attempts=30
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -f "${OLLAMA_API_BASE%/v1}/api/tags" >/dev/null 2>&1; then
            echo "✅ Ollama is ready!"
            break
        fi
        attempt=$((attempt + 1))
        echo "   Attempt $attempt/$max_attempts..."
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo "⚠️  Warning: Ollama not ready after $max_attempts attempts"
    fi
    
    # Check if model is available, download if not
    echo "📥 Checking for model: $OLLAMA_MODEL"
    if ! curl -s "${OLLAMA_API_BASE%/v1}/api/tags" | grep -q "$OLLAMA_MODEL"; then
        echo "📥 Downloading model: $OLLAMA_MODEL"
        curl -X POST "${OLLAMA_API_BASE%/v1}/api/pull" -d "{\"name\": \"$OLLAMA_MODEL\"}"
    else
        echo "✅ Model $OLLAMA_MODEL is available"
    fi
else
    echo "✅ Using external API model: $CAI_MODEL"
    if [ -n "$OPENAI_API_BASE" ]; then
        echo "   API Base: $OPENAI_API_BASE"
    fi
    if [ -n "$OPENAI_API_KEY" ] || [ -n "$ALIAS_API_KEY" ]; then
        echo "   API Key: ✅ Configured"
    else
        echo "   ⚠️  Warning: No API key configured"
    fi
fi

echo ""
echo "🎯 Starting DFIR analysis..."
echo ""

# Execute the main script
exec python main.py "$@"


