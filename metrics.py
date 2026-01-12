# metrics.py - Prometheus Metrics for Bookie-o-em
# Provides observability for API performance, predictions, and system health

import os
import time
import logging
from functools import wraps
from typing import Callable

# Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

logger = logging.getLogger("metrics")

# ============================================================================
# METRICS DEFINITIONS
# ============================================================================

if PROMETHEUS_AVAILABLE:
    # Request metrics
    REQUEST_COUNT = Counter(
        'bookie_requests_total',
        'Total HTTP requests',
        ['method', 'endpoint', 'status']
    )

    REQUEST_LATENCY = Histogram(
        'bookie_request_latency_seconds',
        'Request latency in seconds',
        ['method', 'endpoint'],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )

    # Prediction metrics
    PREDICTIONS_MADE = Counter(
        'bookie_predictions_total',
        'Total predictions made',
        ['sport', 'stat_type']
    )

    PREDICTION_CONFIDENCE = Histogram(
        'bookie_prediction_confidence',
        'Prediction confidence scores',
        ['sport'],
        buckets=[0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
    )

    SMASH_PICKS = Counter(
        'bookie_smash_picks_total',
        'Total SMASH picks generated',
        ['sport']
    )

    # Cache metrics
    CACHE_HITS = Counter(
        'bookie_cache_hits_total',
        'Cache hit count',
        ['cache_type']
    )

    CACHE_MISSES = Counter(
        'bookie_cache_misses_total',
        'Cache miss count',
        ['cache_type']
    )

    # External API metrics
    EXTERNAL_API_CALLS = Counter(
        'bookie_external_api_calls_total',
        'External API calls',
        ['api', 'status']
    )

    EXTERNAL_API_LATENCY = Histogram(
        'bookie_external_api_latency_seconds',
        'External API call latency',
        ['api'],
        buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )

    # System metrics
    ACTIVE_CONNECTIONS = Gauge(
        'bookie_active_connections',
        'Number of active connections'
    )

    SCHEDULER_RUNS = Counter(
        'bookie_scheduler_runs_total',
        'Scheduler job runs',
        ['job_type', 'status']
    )

    # Grader metrics
    PREDICTIONS_GRADED = Counter(
        'bookie_predictions_graded_total',
        'Predictions graded',
        ['sport', 'result']
    )

    HIT_RATE = Gauge(
        'bookie_hit_rate',
        'Current hit rate by sport',
        ['sport']
    )

    # App info
    APP_INFO = Info(
        'bookie_app',
        'Application information'
    )
    APP_INFO.info({
        'version': '14.2',
        'codename': 'PRODUCTION_HARDENED'
    })


# ============================================================================
# METRIC HELPERS
# ============================================================================

def track_request(method: str, endpoint: str, status: int, duration: float):
    """Track an HTTP request."""
    if not PROMETHEUS_AVAILABLE:
        return
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)


def track_prediction(sport: str, stat_type: str, confidence: float, is_smash: bool = False):
    """Track a prediction being made."""
    if not PROMETHEUS_AVAILABLE:
        return
    PREDICTIONS_MADE.labels(sport=sport, stat_type=stat_type).inc()
    PREDICTION_CONFIDENCE.labels(sport=sport).observe(confidence)
    if is_smash:
        SMASH_PICKS.labels(sport=sport).inc()


def track_cache(cache_type: str, hit: bool):
    """Track cache hit/miss."""
    if not PROMETHEUS_AVAILABLE:
        return
    if hit:
        CACHE_HITS.labels(cache_type=cache_type).inc()
    else:
        CACHE_MISSES.labels(cache_type=cache_type).inc()


def track_external_api(api: str, status: str, latency: float):
    """Track external API call."""
    if not PROMETHEUS_AVAILABLE:
        return
    EXTERNAL_API_CALLS.labels(api=api, status=status).inc()
    EXTERNAL_API_LATENCY.labels(api=api).observe(latency)


def track_scheduler_run(job_type: str, success: bool):
    """Track scheduler job execution."""
    if not PROMETHEUS_AVAILABLE:
        return
    status = "success" if success else "failure"
    SCHEDULER_RUNS.labels(job_type=job_type, status=status).inc()


def track_graded_prediction(sport: str, hit: bool):
    """Track a graded prediction."""
    if not PROMETHEUS_AVAILABLE:
        return
    result = "hit" if hit else "miss"
    PREDICTIONS_GRADED.labels(sport=sport, result=result).inc()


def update_hit_rate(sport: str, rate: float):
    """Update current hit rate for a sport."""
    if not PROMETHEUS_AVAILABLE:
        return
    HIT_RATE.labels(sport=sport).set(rate)


# ============================================================================
# MIDDLEWARE
# ============================================================================

def metrics_middleware(func: Callable) -> Callable:
    """Decorator to track endpoint metrics."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            status = 200
            return result
        except Exception as e:
            status = 500
            raise
        finally:
            duration = time.time() - start_time
            endpoint = func.__name__
            track_request("GET", endpoint, status, duration)
    return wrapper


# ============================================================================
# METRICS ENDPOINT
# ============================================================================

def get_metrics_response():
    """Generate Prometheus metrics response."""
    if not PROMETHEUS_AVAILABLE:
        return "# Prometheus client not available\n", "text/plain"
    return generate_latest(), CONTENT_TYPE_LATEST


def get_metrics_status():
    """Get metrics status for health check."""
    return {
        "prometheus_available": PROMETHEUS_AVAILABLE,
        "metrics_enabled": PROMETHEUS_AVAILABLE,
        "endpoint": "/metrics" if PROMETHEUS_AVAILABLE else None
    }
