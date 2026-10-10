from typing import Any, Dict, List

def fetch_service_logs(service_name: str, symptom: str = "", limit: int = 5) -> List[str]:
    """Extracts raw error stack traces and application log streams."""
    symptom_lower = symptom.lower()
    service_lower = service_name.lower()

    if "oom" in symptom_lower or "memory" in symptom_lower or "crash" in symptom_lower:
        return [
            "2026-10-10T16:20:11.102Z [WARN] JVM Garbage Collector: Allocation stall in Old Gen (Heap usage 99.4%)",
            "2026-10-10T16:20:12.441Z [ERROR] java.lang.OutOfMemoryError: Java heap space at com.payment.service.BufferPool.allocate()",
            "2026-10-10T16:20:13.001Z [CRIT] kubelet: Container payment-service-app exceeded memory limit (4294967296 bytes)",
            "2026-10-10T16:20:13.002Z [ALERT] kernel: [19482.110291] oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),cpuset=/,mems_allowed=0,task=payment-service,pid=4192",
            "2026-10-10T16:20:14.210Z [INFO] kubelet: Pod payment-service-v2-7df89b crashed with exitCode 137. Restarting container in 10s...",
        ]
    elif "pool" in symptom_lower or "postgres" in symptom_lower or "db" in service_lower:
        return [
            "2026-10-10T16:22:00.812Z [ERROR] pool-worker: Timeout waiting for free connection from pool 'rds-core' after 30000ms",
            "2026-10-10T16:22:01.204Z [FATAL] postgresql: FATAL: remaining connection slots are reserved for non-replication superuser connections",
            "2026-10-10T16:22:03.992Z [WARN] pgbouncer: pool rds-core-db reached max_client_conn (500/500). Queuing 182 inbound queries",
            "2026-10-10T16:22:04.110Z [ERROR] checkout-api: org.postgresql.util.PSQLException: Connection to 10.0.4.12:5432 refused",
        ]
    elif "502" in symptom_lower or "504" in symptom_lower or "gateway" in service_lower or "ingress" in service_lower:
        return [
            "2026-10-10T16:24:10.001Z [ERROR] envoy.router: Upstream connect timeout for cluster 'billing-upstream' after 5000ms",
            "2026-10-10T16:24:11.119Z [WARN] nginx-ingress: 502 Bad Gateway while reading response header from upstream server: 10.244.2.89:8080",
            "2026-10-10T16:24:12.440Z [ERROR] ingress-controller: Service endpoints empty for backend 'billing-service' in namespace 'prod'",
        ]
    elif "redis" in service_lower or "cache" in symptom_lower or "eviction" in symptom_lower:
        return [
            "2026-10-10T16:25:01.320Z [WARN] redis-server: # WARNING: 98.7% maxmemory reached. Volatile key eviction triggered",
            "2026-10-10T16:25:02.100Z [INFO] redis-server: * 4210 keys evicted in 1000ms according to noeviction / volatile-lru policy",
            "2026-10-10T16:25:04.550Z [ERROR] session-manager: Cache miss storm. High latency on DB fallback reads",
        ]
    elif "dns" in symptom_lower or "coredns" in service_lower or "udp" in symptom_lower:
        return [
            "2026-10-10T16:26:01.000Z [ERROR] coredns: [ERROR] plugin/errors: 2 auth.internal.corp. A: read udp 10.244.0.12:53: i/o timeout",
            "2026-10-10T16:26:02.110Z [WARN] kernel: [29104.992] nf_conntrack: table full, dropping packet",
            "2026-10-10T16:26:03.801Z [ERROR] payment-worker: dial tcp: lookup postgres.internal.net on 10.96.0.10:53: no such host (SERVFAIL)",
        ]
    else:
        return [
            f"2026-10-10T16:27:00.000Z [WARN] {service_name}: Circuit breaker in HALF_OPEN state due to high latency",
            f"2026-10-10T16:27:01.000Z [ERROR] {service_name}: Unhandled RequestTimeoutException processing batch payload",
        ]
