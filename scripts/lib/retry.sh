#!/bin/bash
# Shared retry library for CI scripts
# Source this file to get retry_curl function

# Retry curl with exponential backoff
# Usage: retry_curl URL [MAX_ATTEMPTS] [INITIAL_TIMEOUT]
# Returns: curl output on stdout, exit code 0 on success, 1 on failure
retry_curl() {
    local url="$1"
    local max_attempts="${2:-3}"
    local timeout="${3:-15}"
    local attempt=1
    local response=""
    local http_code=""

    while [ $attempt -le $max_attempts ]; do
        # Capture both body and http code
        response=$(curl -sS -w "\n%{http_code}" -m "$timeout" "$url" -H "X-API-Key: ${API_KEY:-}" 2>&1)
        local curl_exit=$?

        # Extract http code (last line) and body (everything else)
        http_code=$(echo "$response" | tail -n1)
        local body=$(echo "$response" | sed '$d')

        # Success conditions: curl succeeded AND (http 2xx OR valid JSON with no error)
        if [ $curl_exit -eq 0 ] && [[ "$http_code" =~ ^2 ]]; then
            # Verify it's valid JSON
            if echo "$body" | jq -e . >/dev/null 2>&1; then
                echo "$body"
                return 0
            fi
        fi

        # Transient failure - retry
        if [ $attempt -lt $max_attempts ]; then
            local wait_time=$((2 ** attempt))
            echo "  [retry] Attempt $attempt failed (HTTP $http_code), waiting ${wait_time}s..." >&2
            sleep $wait_time
        fi
        attempt=$((attempt + 1))
    done

    echo "  [retry] All $max_attempts attempts failed for $url" >&2
    echo "$body"  # Return last body anyway
    return 1
}

# Retry curl with headers (for endpoints that need API key)
# Usage: retry_curl_auth URL [MAX_ATTEMPTS] [INITIAL_TIMEOUT]
retry_curl_auth() {
    local url="$1"
    local max_attempts="${2:-3}"
    local timeout="${3:-15}"
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        local response
        response=$(curl -sS -w "\n%{http_code}" -m "$timeout" "$url" \
            -H "X-API-Key: ${API_KEY:-}" 2>&1)
        local curl_exit=$?

        local http_code=$(echo "$response" | tail -n1)
        local body=$(echo "$response" | sed '$d')

        if [ $curl_exit -eq 0 ] && [[ "$http_code" =~ ^2 ]]; then
            if echo "$body" | jq -e . >/dev/null 2>&1; then
                echo "$body"
                return 0
            fi
        fi

        if [ $attempt -lt $max_attempts ]; then
            local wait_time=$((2 ** attempt))
            echo "  [retry] Attempt $attempt failed (HTTP $http_code), waiting ${wait_time}s..." >&2
            sleep $wait_time
        fi
        attempt=$((attempt + 1))
    done

    echo "  [retry] All $max_attempts attempts failed for $url" >&2
    echo "$body"
    return 1
}

# Check if API is healthy with retries
# Usage: wait_for_api BASE_URL [MAX_ATTEMPTS]
wait_for_api() {
    local base_url="$1"
    local max_attempts="${2:-5}"
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        local health
        health=$(curl -sS -m 10 "$base_url/health" 2>&1)
        local curl_exit=$?

        if [ $curl_exit -eq 0 ]; then
            local status=$(echo "$health" | jq -r '.status // "unknown"' 2>/dev/null)
            if [ "$status" = "healthy" ] || [ "$status" = "ok" ]; then
                return 0
            fi
        fi

        if [ $attempt -lt $max_attempts ]; then
            local wait_time=$((2 ** attempt))
            echo "  [wait] API not ready, attempt $attempt/$max_attempts, waiting ${wait_time}s..." >&2
            sleep $wait_time
        fi
        attempt=$((attempt + 1))
    done

    return 1
}
