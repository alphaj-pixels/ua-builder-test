"""Fetch everything the Delivery Brain app uses, from both environments, into fd/snap.json."""
import sys, os, json, re, concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mig as M
M.login()
APP = "e-69f9786e285b7c092e6d2749"
ENV = {"prod": M.prod, "uat": M.uat}
def safe(call, m, p, b=None):
    try:
        r = call(m, p, b)
        return r if r is not None else {"_err": "None"}
    except Exception as ex: return {"_err": str(ex)[:160]}
def comps(call):
    out = []; off = 0
    while True:
        r = call("POST", "/api/entity/e_component", {"filter": {"op": "EQUAL", "field": "properties.interfaceId", "values": [APP]}, "page": {"limit": 100, "offset": off}})["objects"]; out += r
        if len(r) < 100: return out
        off += 100
def dss(call, pid):
    return call("POST", "/api/entity/e_data_source", {"filter": {"op": "EQUAL", "field": "properties.interfacePageId", "values": [pid]}, "page": {"limit": 300, "offset": 0}})["objects"]
def list_wf(call):
    out = []; off = 0
    while True:
        r = call("POST", "/api/aggregation?entityType=WorkflowDefinition&group=STANDARD", {"entityType": "WorkflowDefinition", "group": "STANDARD", "filter": {"op": "AND", "filters": []},
             "sorts": [], "projections": [{"name": "id"}, {"name": "name"}], "page": {"limit": 200, "offset": off}})
        objs = r.get("objects") or []; out += [(o["columns"].get("id"), o["columns"].get("name")) for o in objs]
        if len(objs) < 200: return out
        off += 200
snap = {}
for env, call in ENV.items():
    pages = {c["id"]: c for c in comps(call)}
    with cf.ThreadPoolExecutor(10) as ex:
        ds = dict(zip(pages, ex.map(lambda pid: dss(call, pid), pages)))
        live = dict(zip(pages, ex.map(lambda pid: safe(call, "GET", f"/api/entity/deployed/e_component/{pid}"), pages)))
    app = safe(call, "GET", f"/api/entity/e_interface/{APP}"); app_live = safe(call, "GET", f"/api/entity/deployed/e_interface/{APP}")
    snap[env] = {"pages": pages, "ds": ds, "live": live, "app": app, "app_live": app_live, "wflist": list_wf(call)}
    print(env, "pages", len(pages), "ds", sum(len(v) for v in ds.values()), "workflows listed", len(snap[env]["wflist"]), flush=True)
# workflows in scope: referenced by data sources, named "DB |"/"db |", plus everything they call (recursively), plus schedulers calling them
def refs(w):
    s = M.canon(w.get("nodes") or [])
    return set(re.findall(r'"automationId":"([0-9a-f]{24})"', s))
seed = set()
for env in ENV:
    for lst in snap[env]["ds"].values():
        for d in lst:
            a = (d["properties"].get("inputs") or {}).get("automationId")
            if a: seed.add(a)
    seed |= {i for i, n in snap[env]["wflist"] if n and re.match(r"\s*(db|delivery brain|task management)\b", n, re.I)}
wfs = {}; todo = set(seed)
while todo:
    batch = list(todo - set(wfs)); todo = set()
    with cf.ThreadPoolExecutor(12) as ex:
        for wid, res in zip(batch, ex.map(lambda w: {env: safe(call, "GET", f"/api/workflow-definition/{w}") for env, call in ENV.items()}, batch)):
            wfs[wid] = res
            for w in res.values():
                if "_err" not in w: todo |= refs(w)
    todo -= set(wfs)
snap["wfs"] = wfs
print("workflows in scope:", len(wfs), flush=True)
# objects and agents used
objs, agents = set(), set()
for env in ENV:
    for lst in snap[env]["ds"].values():
        for d in lst:
            i = d["properties"].get("inputs") or {}
            if i.get("object_type"): objs.add(i["object_type"])
    for p in snap[env]["pages"].values():
        objs |= set(re.findall(r'"entityId":\s*"([a-z][a-z0-9_]+)"', json.dumps(p["properties"].get("blocks") or {})))
for res in wfs.values():
    for w in res.values():
        if "_err" in w: continue
        s = M.canon(w.get("nodes") or [])
        objs |= set(re.findall(r'"object_type":"([a-z][a-z0-9_]+)"', s))
        agents |= set(re.findall(r'"(?:agentId|aiAgentId|agent_id)":"(e_[0-9a-f]{24})"', s))
        agents |= set(re.findall(r'(e_[0-9a-f]{24})', " ".join(json.dumps(n.get("inputs")) for n in w.get("nodes") or [] if "invoke_agent" in str((n.get("context") or {}).get("resourceName")))))
objs = sorted(o for o in objs if not o.startswith("e_"))
with cf.ThreadPoolExecutor(10) as ex:
    snap["objects"] = dict(zip(objs, ex.map(lambda o: {env: safe(call, "GET", f"/api/entity-type?entityType={o}") for env, call in ENV.items()}, objs)))
    snap["agents"] = dict(zip(sorted(agents), ex.map(lambda a: {env: safe(call, "GET", f"/api/entity/ai_agent/{a}") for env, call in ENV.items()}, sorted(agents))))
print("objects", len(snap["objects"]), "agents", len(snap["agents"]), flush=True)
json.dump(snap, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fd", "snap.json"), "w"))
