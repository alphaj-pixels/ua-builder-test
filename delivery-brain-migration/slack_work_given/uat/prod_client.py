"""Prod client: signs in with UA2_* from the environment (never printed); cookie jar kept in the scratchpad only."""
import os, json, http.cookiejar, urllib.request, urllib.error
BASE = "https://sales.prod.unifyapps.com"
JAR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".prod_cookies")
jar = http.cookiejar.LWPCookieJar(JAR)
if os.path.exists(JAR): jar.load(ignore_discard=True, ignore_expires=True)
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
def call(m, p, b=None, timeout=120):
    rq = urllib.request.Request(BASE + p, data=None if b is None else json.dumps(b).encode(), method=m, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with op.open(rq, timeout=timeout) as r: raw, ct = r.read(), r.headers.get("content-type", "")
    except urllib.error.HTTPError as e: return {"_err": e.code, "_body": e.read()[:300].decode("utf8", "replace")}
    if raw and "json" not in ct: return {"_err": "non-json", "_body": raw[:100].decode("utf8", "replace")}
    return json.loads(raw) if raw else None
def signin():
    me = call("GET", "/api/user-context?includeRoles=true")
    if isinstance(me, dict) and "_err" not in me: return me
    call("POST", "/auth/workflow/execute/node?name=emailAndPassLoginRequest", {"id": "emailAndPassLoginRequest",
         "context": {"appName": "auth_by_unifyapps", "resourceName": "auth_by_unifyapps_login"},
         "inputs": {"returnTo": "/", "failureReturnTo": BASE + "/login", "formData": {"username": os.environ["UA2_USERNAME"], "password": os.environ["UA2_PASSWORD"], "rememberMe": True},
                    "identityProviderId": os.environ["UA2_IDP_ID"]}, "options": {"cacheConfig": {}}})
    jar.save(ignore_discard=True, ignore_expires=True); os.chmod(JAR, 0o600)
    return call("GET", "/api/user-context?includeRoles=true")
def fetch(t, flt=None):
    out, off = [], 0
    while True:
        b = {"page": {"limit": 200, "offset": off}}
        if flt: b["filter"] = flt
        r = call("POST", f"/api/entity/{t}", b)
        if not isinstance(r, dict) or "_err" in r: raise SystemExit(f"{t}: {r}")
        out += r.get("objects") or []
        if not r.get("hasMore"): return out
        off += 200
