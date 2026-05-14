#!/bin/sh
set -e

echo "[$(date)] Starting services..."

start_agentmemory() {
    export AGENTMEMORY_URL="${AGENTMEMORY_URL:-http://127.0.0.1:3111}"
    agentmemory_openai_base_url="${AGENTMEMORY_OPENAI_BASE_URL:-http://192.168.1.146:1236}"
    agentmemory_openai_embedding_model="${AGENTMEMORY_OPENAI_EMBEDDING_MODEL:-text-embedding-embeddinggemma-300m}"
    agentmemory_openai_embedding_dimensions="${AGENTMEMORY_OPENAI_EMBEDDING_DIMENSIONS:-768}"

    if ! command -v iii > /dev/null 2>&1 || ! command -v agentmemory > /dev/null 2>&1; then
        echo "[$(date)] WARNING: agentmemory runtime is not installed in this image"
        return 0
    fi

    mkdir -p /hermes-home/agentmemory/data /hermes-home/logs

    if curl -fsS "$AGENTMEMORY_URL/agentmemory/livez" > /dev/null 2>&1; then
        echo "[$(date)] agentmemory already running at $AGENTMEMORY_URL"
        return 0
    fi

    if ! pgrep -f "iii --config /opt/agentmemory/iii-config.yaml" > /dev/null 2>&1; then
        echo "[$(date)] Starting iii engine for agentmemory (ports 3111/3112)..."
        nohup iii --config /opt/agentmemory/iii-config.yaml --no-update-check \
            > /hermes-home/logs/agentmemory-iii.log 2>&1 &
        echo "[$(date)] iii engine started (PID $!)"
    fi

    i=0
    while [ "$i" -lt 30 ]; do
        if curl -sS -o /dev/null "http://127.0.0.1:3111/" > /dev/null 2>&1; then
            break
        fi
        i=$((i + 1))
        sleep 1
    done

    if ! pgrep -f "agentmemory --no-engine" > /dev/null 2>&1; then
        echo "[$(date)] Starting agentmemory worker with embeddings at $agentmemory_openai_base_url ($agentmemory_openai_embedding_model, ${agentmemory_openai_embedding_dimensions}d)..."
        AGENTMEMORY_URL="$AGENTMEMORY_URL" \
        OPENAI_API_KEY="${AGENTMEMORY_OPENAI_API_KEY:-${OPENAI_API_KEY:-dummy}}" \
        OPENAI_BASE_URL="$agentmemory_openai_base_url" \
        OPENAI_EMBEDDING_MODEL="$agentmemory_openai_embedding_model" \
        OPENAI_EMBEDDING_DIMENSIONS="$agentmemory_openai_embedding_dimensions" \
        EMBEDDING_PROVIDER="${AGENTMEMORY_EMBEDDING_PROVIDER:-openai}" \
        nohup agentmemory --no-engine \
            > /hermes-home/logs/agentmemory.log 2>&1 &
        echo "[$(date)] agentmemory worker started (PID $!)"
    fi

    i=0
    while [ "$i" -lt 30 ]; do
        if curl -fsS "$AGENTMEMORY_URL/agentmemory/livez" > /dev/null 2>&1; then
            echo "[$(date)] agentmemory ready at $AGENTMEMORY_URL"
            return 0
        fi
        i=$((i + 1))
        sleep 1
    done

    echo "[$(date)] WARNING: agentmemory did not become ready; see /hermes-home/logs/agentmemory*.log"
}

start_agentmemory_viewer_proxy() {
    mkdir -p /hermes-home/logs

    if ! command -v python > /dev/null 2>&1 || [ ! -f /usr/local/bin/hermes-tcp-proxy.py ]; then
        echo "[$(date)] WARNING: cannot expose agentmemory viewer; proxy helper is unavailable"
        return 0
    fi

    if pgrep -f "hermes-tcp-proxy.py 0.0.0.0 13113 127.0.0.1 3113" > /dev/null 2>&1; then
        echo "[$(date)] agentmemory viewer proxy already running on port 13113"
        return 0
    fi

    echo "[$(date)] Starting agentmemory viewer proxy (host 3113 -> container 127.0.0.1:3113)..."
    nohup python /usr/local/bin/hermes-tcp-proxy.py 0.0.0.0 13113 127.0.0.1 3113 \
        > /hermes-home/logs/agentmemory-viewer-proxy.log 2>&1 &
    echo "[$(date)] agentmemory viewer proxy started (PID $!)"
}

start_hermes_dashboard() {
    mkdir -p /hermes-home/logs

    hermes_bin="${HERMES_BIN:-/opt/venv/bin/hermes}"

    if [ ! -x "$hermes_bin" ]; then
        echo "[$(date)] WARNING: hermes CLI is not installed; dashboard not started"
        return 0
    fi

    if pgrep -f "hermes dashboard" > /dev/null 2>&1; then
        echo "[$(date)] Stopping existing Hermes dashboard process..."
        "$hermes_bin" dashboard --stop > /hermes-home/logs/hermes-dashboard-stop.log 2>&1 || true
    fi

    echo "[$(date)] Starting Hermes dashboard on 0.0.0.0:9119..."
    nohup "$hermes_bin" dashboard --host 0.0.0.0 --port 9119 --insecure --no-open --skip-build \
        > /hermes-home/logs/hermes-dashboard.log 2>&1 &
    echo "[$(date)] Hermes dashboard started (PID $!)"
}

start_kiwix() {
    if [ -f /workspace/kiwix-serve ]; then
        if ! pgrep -f kiwix-serve > /dev/null 2>&1; then
            echo "[$(date)] Starting kiwix-serve (port 8090)..."
            nohup /workspace/kiwix-serve \
                --port 8090 \
                "/host/e/wikix/kiwi_download/wikipedia_en_all_maxi_2025-08.zim" \
                "/workspace/hien-personal.zim" \
                > /workspace/kiwix.log 2>&1 &
            echo "[$(date)] kiwix-serve started (PID $!)"
        else
            echo "[$(date)] kiwix-serve already running"
        fi
    else
        echo "[$(date)] WARNING: kiwix-serve binary not found at /workspace/kiwix-serve"
    fi
}

start_agentmemory
start_agentmemory_viewer_proxy
start_hermes_dashboard
start_kiwix

sleep 2

echo "[$(date)] Starting Hermes agent..."
exec /opt/venv/bin/hermes gateway run
