import sqlite3
import uuid
from datetime import datetime, timezone

def seed():
    conn = sqlite3.connect("autoforge.db")
    cursor = conn.cursor()

    # Ensure table columns exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            issue_number INTEGER,
            repo_full_name TEXT,
            title TEXT,
            body TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT,
            base_commit_sha TEXT,
            patch_diff TEXT,
            summary TEXT
        )
    """)
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN patch_diff TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN summary TEXT")
    except Exception:
        pass
    conn.commit()

    # Clear existing to ensure clean deduplicated list
    cursor.execute("DELETE FROM tasks")

    demo_tasks = [
        (
            "task_fastapi_9124",
            9124,
            "tiangolo/fastapi",
            "Fix JWT expired signature handling and return 401 instead of unhandled 500 error",
            "When a client passes an expired JWT token, jwt.decode raises jwt.ExpiredSignatureError which wasn't caught by the OAuth2PasswordBearer handler, resulting in an internal 500 status instead of 401 Unauthorized.",
            "completed",
            "2026-10-10T09:15:00Z",
            "2026-10-10T09:16:12Z",
            "a8f7c9e",
            """--- a/fastapi/security/oauth2.py
+++ b/fastapi/security/oauth2.py
@@ -154,6 +154,8 @@ def verify_token(token: str):
     try:
         return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
+    except jwt.ExpiredSignatureError:
+        raise HTTPException(status_code=401, detail="Token signature expired")
+    except jwt.JWTError:
+        raise HTTPException(status_code=401, detail="Invalid authentication credentials")""",
            "Identified unhandled ExpiredSignatureError in OAuth2 password bearer. Added explicit exception trap returning 401 Unauthorized. 24 unit tests passed with 0 regressions."
        ),
        (
            "task_pydantic_6721",
            6721,
            "pydantic/pydantic",
            "Fix recursive serialization of Union types with discriminator fields in nested models",
            "When validating nested models containing discriminated unions, the serializer failed to resolve custom validator hooks on inner attributes, discarding custom serializer mappings.",
            "completed",
            "2026-10-10T08:45:00Z",
            "2026-10-10T08:46:30Z",
            "c3d2e1b",
            """--- a/pydantic/main.py
+++ b/pydantic/main.py
@@ -312,7 +312,9 @@ def _serialize_union(field, value):
     discriminator = getattr(field, 'discriminator', None)
+    if discriminator and isinstance(value, dict):
+        return field.sub_types[value[discriminator]].validate(value)
     for sub_type in field.sub_types:
         try:""",
            "Resolved discriminator lookup recursion order in discriminated union serialization. Added regression test in test_discriminated_union.py. All 42 tests passing."
        ),
        (
            "task_httpx_2291",
            2291,
            "encode/httpx",
            "Prevent connection socket leak when streaming response body is partially consumed",
            "If an asynchronous streaming response context manager exits without consuming all chunks, the underlying connection pool didn't explicitly trigger transport.aclose(), exhausting socket descriptors.",
            "completed",
            "2026-10-10T07:30:00Z",
            "2026-10-10T07:31:45Z",
            "e5f4a3c",
            """--- a/httpx/_transports/default.py
+++ b/httpx/_transports/default.py
@@ -88,6 +88,8 @@ async def close(self):
     if self._pool is not None:
+        await self._pool.aclose()
+        self._pool = None
     self._is_closed = True""",
            "Patched transport socket cleanup on early stream exit. Added pytest fixture verifying socket file descriptor release. 18 suite tests passed."
        ),
        (
            "task_requests_5438",
            5438,
            "psf/requests",
            "Preserve user custom SSL ciphers when connecting through HTTPS proxy tunnel",
            "When routing HTTPS requests via an intermediate CONNECT proxy, urllib3 SSLContext ciphers were overridden by default system cipher suites rather than maintaining user-specified adapter ciphers.",
            "completed",
            "2026-10-10T06:12:00Z",
            "2026-10-10T06:13:20Z",
            "b9e8d7f",
            """--- a/requests/adapters.py
+++ b/requests/adapters.py
@@ -234,6 +234,8 @@ def init_poolmanager(self, connections, maxsize, block=DEFAULT_POOLBLOCK, **po
     if self._ssl_context:
+        pool_kwargs["ssl_context"] = self._ssl_context
+        pool_kwargs["ciphers"] = self._ssl_context.get_ciphers()""",
            "Ensured proxy tunnel initialization inherits parent HTTPAdapter SSLContext and custom ciphers. Verified against OpenSSL 3.0 test suite."
        ),
        (
            "task_flask_4812",
            4812,
            "pallets/flask",
            "Enforce SameSite=None session cookie requirement for cross-site iframe HTTPS contexts",
            "Session cookies configured with SESSION_COOKIE_SAMESITE='None' did not automatically mandate Secure flag, causing modern browser rejections.",
            "completed",
            "2026-10-10T05:00:00Z",
            "2026-10-10T05:01:15Z",
            "f1a2b3c",
            """--- a/flask/sessions.py
+++ b/flask/sessions.py
@@ -198,6 +198,8 @@ def save_session(self, app, session, response):
     samesite = app.config.get("SESSION_COOKIE_SAMESITE")
+    if samesite and samesite.lower() == "none" and not secure:
+        secure = True  # Modern browser spec requires Secure with SameSite=None""",
            "Enforced Secure attribute when SameSite=None is specified per modern browser RFC specs. Unit tests in test_sessions.py passing 100%."
        )
    ]

    for t in demo_tasks:
        cursor.execute("""
            INSERT INTO tasks (id, issue_number, repo_full_name, title, body, status, created_at, updated_at, base_commit_sha, patch_diff, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, t)

    conn.commit()
    conn.close()
    print(f"Seeded {len(demo_tasks)} benchmark SWE tasks successfully.")

if __name__ == "__main__":
    seed()
