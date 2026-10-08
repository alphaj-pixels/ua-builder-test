"""Minimal UnifyApps client: cookie-jar login from env vars (Option B). Never prints credentials."""
import json, os, sys, http.cookiejar, urllib.request, urllib.error
BASE = os.environ["UA_BASE_URL"].rstrip("/")
JAR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".ua_cookies")
jar = http.cookiejar.LWPCookieJar(JAR_PATH)
if os.path.exists(JAR_PATH):
    jar.load(ignore_discard=True, ignore_expires=True)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def call(method, path, body=None, timeout=60):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with opener.open(req, timeout=timeout) as r:
            raw, status, ct = r.read(), r.status, r.headers.get("content-type", "")
    except urllib.error.HTTPError as e:
        raw, status, ct = e.read(), e.code, e.headers.get("content-type", "")
    if raw and "json" not in ct:
        raise RuntimeError(f"HTTP {status} non-JSON ({ct}) - session expired?")
    out = json.loads(raw) if raw else None
    if status >= 400:
        raise RuntimeError(f"HTTP {status} {json.dumps(out)[:400]}")
    return out

def login():
    call("POST", "/auth/workflow/execute/node?name=emailAndPassLoginRequest", {
        "id": "emailAndPassLoginRequest",
        "context": {"appName": "auth_by_unifyapps", "resourceName": "auth_by_unifyapps_login"},
        "inputs": {"returnTo": "/", "failureReturnTo": BASE + "/login",
                   "formData": {"username": os.environ["UA_USERNAME"],
                                "password": os.environ["UA_PASSWORD"], "rememberMe": True},
                   "identityProviderId": os.environ["UA_IDP_ID"]},
        "options": {"cacheConfig": {}}})
    jar.save(ignore_discard=True, ignore_expires=True)
    os.chmod(JAR_PATH, 0o600)

def ensure_session():
    try:
        return call("GET", "/api/user-context?includeRoles=true")
    except RuntimeError:
        login()
        return call("GET", "/api/user-context?includeRoles=true")
