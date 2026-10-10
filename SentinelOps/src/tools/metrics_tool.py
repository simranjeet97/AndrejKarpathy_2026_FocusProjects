import time
from typing import Any, Dict

def query_service_metrics(service_name: str, symptom: str = "") -> Dict[str, Any]:
    """Simulates querying Prometheus / Datadog time-series telemetry for a service."""
    symptom_lower = symptom.lower()
    service_lower = service_name.lower()

    if "oom" in symptom_lower or "memory" in symptom_lower or "crash" in symptom_lower:
        return {
            "service": service_name,
            "cpu_utilization_pct": 74.2,
            "memory_usage_bytes": "4.28 GB",
            "memory_limit_bytes": "4.00 GB",
            "memory_saturation_pct": 107.0,
            "pod_restarts_last_hour": 14,
            "exit_code": 137,
            "p99_latency_ms": 320.5,
            "error_rate_pct": 6.8,
            "status": "CRITICAL",
        }
    elif "pool" in symptom_lower or "postgres" in symptom_lower or "db" in service_lower:
        return {
            "service": service_name,
            "active_connections": 500,
            "max_connections": 500,
            "pool_utilization_pct": 100.0,
            "waiting_client_threads": 182,
            "p99_latency_ms": 4820.0,
            "cpu_utilization_pct": 89.4,
            "error_rate_pct": 14.2,
            "status": "CRITICAL",
        }
    elif "502" in symptom_lower or "504" in symptom_lower or "gateway" in service_lower or "ingress" in service_lower:
        return {
            "service": service_name,
            "request_throughput_rps": 3840,
            "http_5xx_rate_pct": 18.4,
            "upstream_connect_timeouts": 1420,
            "active_backend_pods": 3,
            "healthy_endpoints_pct": 37.5,
            "p99_latency_ms": 5200.0,
            "status": "CRITICAL",
        }
    elif "redis" in service_lower or "cache" in symptom_lower or "eviction" in symptom_lower:
        return {
            "service": service_name,
            "used_memory_bytes": "15.8 GB",
            "maxmemory_bytes": "16.0 GB",
            "memory_saturation_pct": 98.7,
            "evicted_keys_per_sec": 4210,
            "hit_ratio_pct": 41.2,
            "connected_clients": 890,
            "status": "DEGRADED",
        }
    elif "dns" in symptom_lower or "coredns" in service_lower or "udp" in symptom_lower:
        return {
            "service": service_name,
            "dns_lookup_avg_ms": 4650.0,
            "servfail_rate_pct": 22.8,
            "udp_packet_drop_count": 8940,
            "conntrack_table_usage_pct": 94.6,
            "status": "CRITICAL",
        }
    else:
        return {
            "service": service_name,
            "cpu_utilization_pct": 88.5,
            "memory_saturation_pct": 82.1,
            "p99_latency_ms": 940.0,
            "error_rate_pct": 5.4,
            "status": "WARNING",
        }
