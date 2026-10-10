import sqlite3
import hashlib
import json
import uuid
from datetime import datetime, timezone

def seed():
    conn = sqlite3.connect("sentinelops.db")
    cursor = conn.cursor()

    # Create tables if not exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            incident_number INTEGER,
            service TEXT,
            severity TEXT,
            title TEXT,
            description TEXT,
            status TEXT,
            root_cause TEXT,
            remediation_patch TEXT,
            confidence_score REAL,
            risk_level TEXT,
            eval_passed BOOLEAN,
            audit_hash TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_actions (
            id TEXT PRIMARY KEY,
            incident_id TEXT,
            agent_role TEXT,
            action_type TEXT,
            summary TEXT,
            payload TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_ledger (
            id TEXT PRIMARY KEY,
            incident_id TEXT,
            event_type TEXT,
            payload TEXT,
            previous_hash TEXT,
            hash TEXT,
            created_at TEXT
        )
    """)

    # Clean existing to ensure deduplication
    cursor.execute("DELETE FROM incidents")
    cursor.execute("DELETE FROM agent_actions")
    cursor.execute("DELETE FROM audit_ledger")

    demo_incidents = [
        (
            "inc_001",
            101,
            "payment-service-v2",
            "P1",
            "Kubernetes Pod CrashLoopBackOff & Exit Code 137 (OOMKilled at 4.28GB)",
            "Container continuously crashes upon traffic spikes. Memory limit was set to 4Gi while OldGen heap allocation peaked at 4.28Gi, triggering Linux kernel cgroup OOM killer.",
            "RESOLVED",
            "JVM Old Generation heap exhaustion triggered Linux cgroup OOM termination (exitCode 137). Correlated metrics show pod restarted 14 times in 60 minutes.",
            """# Apply Kubernetes memory limit increase from 4Gi to 6Gi
kubectl patch deployment payment-service-v2 -n production --patch '{"spec":{"template":{"spec":{"containers":[{"name":"app","resources":{"limits":{"memory":"6Gi"},"requests":{"memory":"4Gi"}}}]}}}}'
kubectl rollout status deployment/payment-service-v2 -n production""",
            0.96,
            "LOW",
            True,
            "a1f8c9e2b4d70154823901452938472910492837461928374659283746192837",
            "2026-10-10T15:45:00Z",
            "2026-10-10T15:46:12Z"
        ),
        (
            "inc_002",
            102,
            "rds-core-db",
            "P1",
            "PostgreSQL Connection Pool Starvation (Active Conns: 500/500, Latency: 4820ms)",
            "Inbound checkout transactions timing out. PgBouncer pool reached max connection ceiling of 500. 182 client worker threads blocked waiting for connections.",
            "RESOLVED",
            "Connection pool exhaustion caused by unindexed long-running queries holding idle-in-transaction status > 60s. Client queue depth reached 182 threads.",
            """-- Terminate lingering idle-in-transaction connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
WHERE state = 'idle in transaction' AND state_change < now() - INTERVAL '60 seconds';

-- Dynamically increase PgBouncer pool ceiling
pgbouncer-cli set max_client_conn=750;
pgbouncer-cli reload;""",
            0.94,
            "MEDIUM",
            True,
            "b2e7d8f1c3a60948273619283746592019482736451928374659201948273645",
            "2026-10-10T14:30:00Z",
            "2026-10-10T14:32:05Z"
        ),
        (
            "inc_003",
            103,
            "api-gateway-proxy",
            "P1",
            "502 Bad Gateway Error Spike (18.4% HTTP 5xx Rate Across Ingress Mesh)",
            "External users experiencing sudden 502 errors. Upstream connect timeouts to billing microservices surging after replica scale-down.",
            "RESOLVED",
            "Upstream endpoint exhaustion following traffic spike. Healthy backend pods dropped to 3 out of 8, causing gateway connection backlog.",
            """# Scale ingress proxy and upstream billing workers
kubectl scale deployment api-gateway-proxy -n ingress --replicas=8
kubectl scale deployment billing-service -n production --replicas=12
kubectl rollout status deployment/billing-service -n production""",
            0.95,
            "LOW",
            True,
            "c3d6e5a4b2f10928374651928374650192837465102938475610293847561029",
            "2026-10-10T13:15:00Z",
            "2026-10-10T13:17:30Z"
        ),
        (
            "inc_004",
            104,
            "cache-cluster-01",
            "P2",
            "Redis Memory Saturation (98.7% MaxMemory, 4210 Evictions/Sec)",
            "Cache miss storm observed across checkout flows. Used memory hit 15.8GB / 16.0GB limit, triggering volatile key evictions and database load spikes.",
            "RESOLVED",
            "High eviction frequency due to missing TTLs on bulk session tokens. Memory pressure degraded cache hit ratio from 94% down to 41.2%.",
            """# Switch to volatile-lru eviction policy and purge stale segments
redis-cli -h cache-cluster-01 -p 6379 CONFIG SET maxmemory-policy volatile-lru
redis-cli -h cache-cluster-01 -p 6379 MEMORY PURGE""",
            0.93,
            "LOW",
            True,
            "d4c5b6a7f8e90192837465102938475610293847561029384756102938475610",
            "2026-10-10T11:00:00Z",
            "2026-10-10T11:02:15Z"
        ),
        (
            "inc_005",
            105,
            "auth-dns-resolver",
            "P2",
            "CoreDNS Resolution Degradation (SERVFAIL at 22.8%, P99 Latency: 4650ms)",
            "Pods failing internal DNS resolution for service discovery. Linux kernel conntrack table saturation dropping UDP port 53 packets.",
            "RESOLVED",
            "Worker node conntrack table saturation (94.6% utilization) resulting in dropped UDP DNS lookups and intermittent SERVFAIL timeouts.",
            """# Scale CoreDNS replicas and expand worker conntrack table
kubectl scale deployment coredns -n kube-system --replicas=6
sudo sysctl -w net.netfilter.nf_conntrack_max=1048576""",
            0.91,
            "MEDIUM",
            True,
            "e5b4a3f2c1d09876543210987654321098765432109876543210987654321098",
            "2026-10-10T09:30:00Z",
            "2026-10-10T09:31:45Z"
        )
    ]

    for inc in demo_incidents:
        cursor.execute("""
            INSERT INTO incidents (
                id, incident_number, service, severity, title, description, status,
                root_cause, remediation_patch, confidence_score, risk_level, eval_passed,
                audit_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, inc)

        cursor.execute("""
            INSERT INTO audit_ledger (
                id, incident_id, event_type, payload, previous_hash, hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            f"aud_{uuid.uuid4().hex[:8]}",
            inc[0],
            "INCIDENT_RESOLVED",
            json.dumps({"service": inc[2], "severity": inc[3], "confidence_score": inc[9]}),
            "GENESIS_ROOT",
            inc[12],
            inc[13]
        ))

    conn.commit()
    conn.close()
    print(f"Seeded {len(demo_incidents)} production DevOps incidents successfully.")

if __name__ == "__main__":
    seed()
