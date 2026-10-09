"""UAT -> prod promotion helpers. UAT via ua (UA_*), prod via prod_client (UA2_*); credentials never printed."""
import sys, os, json, hashlib, datetime, gzip
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "slack_work_given", "prod"))   # ua.py (UAT, UA_*) and prod_client.py (prod, UA2_*)
import ua, prod_client as P
BK = os.path.join(HERE, "prod_backups", "slices")
def login(): ua.ensure_session(); P.signin()
def uat(m, p, b=None): return ua.call(m, p, b)
def prod(m, p, b=None, timeout=120):
    r = P.call(m, p, b, timeout=timeout)
    if isinstance(r, dict) and "_err" in r: raise RuntimeError(f"prod {m} {p}: {r['_err']} {r['_body'][:300]}")
    return r
def canon(x): return json.dumps(x, sort_keys=True, separators=(",", ":"))
def wf_hash(w): return hashlib.sha256(canon({"nodes": sorted(w.get("nodes") or [], key=lambda n: n["id"]), "edges": sorted(w.get("edges") or [], key=lambda e: e["id"])}).encode()).hexdigest()[:10]
def ts(ms): return datetime.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%MZ") if ms else None
def backup(kind, ident, obj):
    p = os.path.join(BK, f"prod_{kind}_{ident}_v{obj.get('version')}.json.gz")
    if not os.path.exists(p):
        with gzip.open(p, "wt") as f: json.dump(obj, f)
    return p
def node_resources(w): return sorted({(n["context"]["appName"], n["context"]["resourceName"], n["context"].get("resourceVersion")) for n in w.get("nodes") or [] if n.get("context")})
_RV = {}
def prod_has_version(app, res, ver):
    if app not in _RV: _RV[app] = {(o["name"], o["version"]) for o in prod("GET", f"/api/workflow-builder/node/{app}/resources")["objects"]}
    return (res, ver) in _RV[app]

import time
def prod_test(wid, defn, payload, nodes, timeout_s=240):
    """Test-run a workflow definition on prod without saving it (read-only workflows only)."""
    body = {"payload": payload, "type": "MOCK", "workflowDefinition": {k: v for k, v in defn.items() if k != "id"}}
    rid = prod("POST", f"/api/test-workflow/initiate-test/{wid}", body)["runId"]
    cols, dl = None, time.time() + timeout_s
    while time.time() < dl:
        time.sleep(3)
        o = prod("POST", "/api/aggregation?entityType=WORKFLOW_EXECUTION&group=TEST_WORKFLOW_EXECUTION", {"entityType": "WORKFLOW_EXECUTION", "group": "TEST_WORKFLOW_EXECUTION",
            "projections": [{"name": n} for n in ("ID", "STATUS", "EXECUTION_TIME", "START_TIME", "END_TIME", "FAILED_NODES")],
            "filter": {"op": "IN", "field": "ID", "values": [rid]}, "page": {"limit": 1, "offset": 0}}).get("objects") or []
        if o and o[0].get("columns"):
            cols = o[0]["columns"]
            if cols.get("STATUS") in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"): break
    if not cols: return {"status": "NO_STATUS", "runId": rid, "nodes": {}}
    keys = [f"{rid}.{rid}.{n}" for n in nodes]
    out = prod("POST", "/api/lookup?ByKeys=TEST_WORKFLOW_VARIABLE", {"type": "ByKeys", "lookupType": "TEST_WORKFLOW_VARIABLE", "keys": keys,
          "options": {"startTime": cols["START_TIME"] - 10000, "endTime": (cols.get("END_TIME") or cols["START_TIME"]) + 10000, "workflowId": wid}})["response"]["objects"]
    res = {}
    for n, k in zip(nodes, keys):
        for ent in out.get(k, []): res.setdefault(n, {})[ent["type"]] = ent.get("payload")
    return {"runId": rid, "status": cols.get("STATUS"), "ms": cols.get("EXECUTION_TIME"), "failed": cols.get("FAILED_NODES"), "nodes": res}
