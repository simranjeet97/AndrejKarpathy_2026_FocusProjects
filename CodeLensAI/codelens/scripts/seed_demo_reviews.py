import sqlite3
import json
import pandas as pd
from datetime import datetime, timezone

SQLITE_PATH = "data/sqlite/codelens.db"
EXCEL_PATH = "data/excel/codelens_reviews.xlsx"

DEMO_REVIEWS = [
    {
        "pr_id": 120486,
        "repo": "tensorflow/tensorflow",
        "author": "copybara-service[bot]",
        "jira_ticket": "TF-8921",
        "commit_sha": "574614a5283e52f66199e4ce21f2cfa885313afd",
        "approval": "COMMENT",
        "confidence": 0.95,
        "critical_issues": 0,
        "high_issues": 1,
        "total_issues": 5,
        "tokens_used": 3770,
        "latency_ms": 18450.0,
        "status": "Reviewed",
        "date": "2026-10-10 12:44:14",
        "summary": "This PR refactors the XLA GPU latency estimator model, deprecating the legacy MLIR context parameter and optimizing execution model ownership. Overall architecture is solid; however, parameter deprecation requires consistent cleanups across test suites to prevent compiler warnings.",
        "issues": [
            {
                "file_path": "third_party/xla/xla/service/gpu/model/sol_latency_estimator.cc",
                "line_number": 110,
                "severity": "HIGH",
                "category": "PERFORMANCE",
                "message": "Unused mlir_context parameter triggers unnecessary pointer dereferencing in tight model loops.",
                "suggestion": "Remove unused mlir_context argument from GpuPerformanceModelOwning signature."
            },
            {
                "file_path": "third_party/xla/xla/service/gpu/model/sol_latency_estimator.cc",
                "line_number": 299,
                "severity": "MEDIUM",
                "category": "STYLE",
                "message": "Direct instantiation lacks const-correctness for gpu_device_info reference.",
                "suggestion": "Mark gpu_device_info as const GpuDeviceInfo& to enforce immutability."
            },
            {
                "file_path": "third_party/xla/xla/service/gpu/model/sol_latency_estimator.cc",
                "line_number": 409,
                "severity": "LOW",
                "category": "BEST_PRACTICES",
                "message": "Missing explicit namespace qualification for latency calculation helpers.",
                "suggestion": "Use explicit ::xla::gpu::ComputeSolLatency namespace for clarity."
            },
            {
                "file_path": "third_party/xla/xla/service/gpu/model/sol_latency_estimator_test.cc",
                "line_number": 99,
                "severity": "LOW",
                "category": "TESTS",
                "message": "Mock test setup still instantiates dummy MLIR context fixture.",
                "suggestion": "Prune mlir_context fixture setup from SetUp() method in SolLatencyEstimatorTest."
            },
            {
                "file_path": "third_party/xla/xla/service/gpu/model/sol_latency_estimator_test.cc",
                "line_number": 142,
                "severity": "LOW",
                "category": "DOCUMENTATION",
                "message": "Test docstring references obsolete constructor parameters.",
                "suggestion": "Update Doxygen comment block to reflect new parameter requirements."
            }
        ],
        "suggestions": [
            "Ensure all callers of GpuPerformanceModelOwning pass gpu_device_info directly rather than through legacy constructor wrappers.",
            "Add benchmark coverage verifying that latency estimator memory overhead is reduced post-refactor."
        ]
    },
    {
        "pr_id": 5918,
        "repo": "pallets/flask",
        "author": "davidism",
        "jira_ticket": "FLASK-412",
        "commit_sha": "80669a0ea83fdabd4a4cd3da10afaac12394af6f",
        "approval": "APPROVE",
        "confidence": 0.98,
        "critical_issues": 0,
        "high_issues": 0,
        "total_issues": 2,
        "tokens_used": 2543,
        "latency_ms": 12100.0,
        "status": "Reviewed",
        "date": "2026-10-10 11:20:10",
        "summary": "Clean, backward-compatible optimization of Flask's URL routing map and Blueprint endpoint registry. Resolves ambiguous endpoint collision edge cases and reduces rule dispatch overhead by ~8%.",
        "issues": [
            {
                "file_path": "src/flask/sansio/blueprints.py",
                "line_number": 84,
                "severity": "MEDIUM",
                "category": "TYPE_SAFETY",
                "message": "Endpoint parameter type hint could be narrowed from Optional[str] to str | None for Python 3.10+ consistency.",
                "suggestion": "Use modern union type syntax: endpoint: str | None = None."
            },
            {
                "file_path": "tests/test_blueprints.py",
                "line_number": 215,
                "severity": "LOW",
                "category": "TEST_COVERAGE",
                "message": "Missing assertion verifying trailing slash normalization on nested blueprint prefix.",
                "suggestion": "Add test_nested_blueprint_trailing_slash test case checking 308 redirect behavior."
            }
        ],
        "suggestions": [
            "Update Sphinx docs under routing.rst with an example of nested blueprint route prefixing.",
            "Type annotation improvements align nicely with PEP 604 standards."
        ]
    },
    {
        "pr_id": 65823,
        "repo": "pandas-dev/pandas",
        "author": "rhshadrach",
        "jira_ticket": "PD-9941",
        "commit_sha": "30e2b182e6d9242f3d1881b7cba3e50f825be0d2",
        "approval": "APPROVE",
        "confidence": 0.94,
        "critical_issues": 0,
        "high_issues": 0,
        "total_issues": 3,
        "tokens_used": 2782,
        "latency_ms": 14250.0,
        "status": "Reviewed",
        "date": "2026-10-10 10:15:32",
        "summary": "Comprehensive improvement to masked array indexing and dtype preservation when slicing Series with ExtensionArray backends. Tests verify edge cases across ArrowDtype and NullableInteger.",
        "issues": [
            {
                "file_path": "pandas/core/arrays/masked.py",
                "line_number": 158,
                "severity": "MEDIUM",
                "category": "PERFORMANCE",
                "message": "Repeated boolean mask inversion allocates a temporary numpy array on every slice.",
                "suggestion": "Cache inverted mask using np.bitwise_not(mask, out=self._mask_cache) or in-place bitwise NOT."
            },
            {
                "file_path": "pandas/core/arrays/masked.py",
                "line_number": 290,
                "severity": "LOW",
                "category": "STYLE",
                "message": "Line length exceeds 88 character Black formatting limit.",
                "suggestion": "Break long tuple unpacking across multiple lines."
            },
            {
                "file_path": "pandas/tests/series/indexing/test_masked.py",
                "line_number": 72,
                "severity": "LOW",
                "category": "TESTS",
                "message": "Parameterized test fixture does not cover Float64Dtype with NaN vs NA sentinel values.",
                "suggestion": "Add Float64Dtype() to @pytest.mark.parametrize('any_numeric_ea_dtype')."
            }
        ],
        "suggestions": [
            "Benchmarking with asv show zero performance regressions on 1M row Series indexing.",
            "LGTM — safe to merge after fixing the Black line-length formatting nit."
        ]
    },
    {
        "pr_id": 1042,
        "repo": "tiangolo/fastapi",
        "author": "tiangolo",
        "jira_ticket": "FA-1042",
        "commit_sha": "f8a1239bc7145e12891230491823091283091823",
        "approval": "APPROVE",
        "confidence": 0.99,
        "critical_issues": 0,
        "high_issues": 0,
        "total_issues": 1,
        "tokens_used": 2190,
        "latency_ms": 10800.0,
        "status": "Reviewed",
        "date": "2026-10-10 09:30:00",
        "summary": "Optimizes FastAPI dependency cache resolution for concurrent async path operations. Eliminates redundant lock contention when resolving multiple sub-dependencies.",
        "issues": [
            {
                "file_path": "fastapi/dependencies/utils.py",
                "line_number": 320,
                "severity": "LOW",
                "category": "CONCURRENCY",
                "message": "Async dependency resolver uses asyncio.gather without return_exceptions=True.",
                "suggestion": "Wrap sub-dependency gathering with try/except to ensure clean cancellation if a sister dependency fails."
            }
        ],
        "suggestions": [
            "Excellent speedup for microservices with deep dependency graphs (Auth + DB + Permissions)."
        ]
    },
    {
        "pr_id": 8491,
        "repo": "pytorch/pytorch",
        "author": "ezyang",
        "jira_ticket": "TORCH-5510",
        "commit_sha": "d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",
        "approval": "REQUEST_CHANGES",
        "confidence": 0.97,
        "critical_issues": 1,
        "high_issues": 1,
        "total_issues": 4,
        "tokens_used": 4120,
        "latency_ms": 24800.0,
        "status": "Reviewed",
        "date": "2026-10-10 08:45:15",
        "summary": "Introduces CUDA asynchronous allocator stream sync improvements. However, a potential race condition in unified memory deallocation and missing bounds checks on block indices require changes before merge.",
        "issues": [
            {
                "file_path": "c10/cuda/CUDACachingAllocator.cpp",
                "line_number": 412,
                "severity": "CRITICAL",
                "category": "MEMORY_SAFETY",
                "message": "Block deallocation does not acquire device mutex before recycling stream pool block, risking use-after-free under multi-threaded inference.",
                "suggestion": "Enclose block recycling within std::lock_guard<std::mutex> lock(device_mutex[device]);"
            },
            {
                "file_path": "c10/cuda/CUDACachingAllocator.cpp",
                "line_number": 680,
                "severity": "HIGH",
                "category": "BOUNDS_CHECK",
                "message": "Unchecked device index integer could cause array out-of-bounds access on systems with >8 GPUs.",
                "suggestion": "Assert device >= 0 && device < C10_COMPILE_TIME_MAX_GPUS before indexing device_properties array."
            },
            {
                "file_path": "test/test_cuda.py",
                "line_number": 880,
                "severity": "MEDIUM",
                "category": "TEST_ISOLATION",
                "message": "Test leaves CUDA caching allocator in dirty state without calling torch.cuda.empty_cache().",
                "suggestion": "Add teardown fixture calling torch.cuda.empty_cache() after each test iteration."
            },
            {
                "file_path": "c10/cuda/CUDACachingAllocator.h",
                "line_number": 95,
                "severity": "LOW",
                "category": "DOCUMENTATION",
                "message": "Header file comments omit thread safety invariants for new allocator methods.",
                "suggestion": "Document thread safety guarantees in class docstrings."
            }
        ],
        "suggestions": [
            "Block merge until CUDA memory race condition is resolved with thread-safe lock guard.",
            "Run stress test suite with CUDA_LAUNCH_BLOCKING=1 to verify stream synchronization."
        ]
    }
]

def seed():
    # 1. Update SQLite
    conn = sqlite3.connect(SQLITE_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM reviews")

    for r in DEMO_REVIEWS:
        c.execute(
            """
            INSERT INTO reviews (pr_id, repo, commit_sha, summary, approval, tokens_used, created_at, issues_json, suggestions_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                r["pr_id"],
                r["repo"],
                r["commit_sha"],
                r["summary"],
                r["approval"],
                r["tokens_used"],
                r["date"],
                json.dumps(r["issues"]),
                json.dumps(r["suggestions"])
            )
        )
    conn.commit()
    conn.close()
    print("Seeded SQLite reviews table successfully.")

    # 2. Update Excel
    excel_records = []
    for r in DEMO_REVIEWS:
        excel_records.append({
            "date": r["date"],
            "pr_id": r["pr_id"],
            "repo": r["repo"],
            "author": r["author"],
            "jira_ticket": r["jira_ticket"],
            "approval": r["approval"],
            "confidence": r["confidence"],
            "critical_issues": r["critical_issues"],
            "high_issues": r["high_issues"],
            "total_issues": r["total_issues"],
            "summary": r["summary"],
            "tokens_used": r["tokens_used"],
            "latency_ms": r["latency_ms"],
            "status": r["status"]
        })

    df = pd.DataFrame(excel_records)
    with pd.ExcelWriter(EXCEL_PATH, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="PR Reviews", index=False)
    print("Seeded Excel workbook successfully.")

if __name__ == "__main__":
    seed()
