"""Workflow helpers for the Sales tenant (versions resolved live on this tenant)."""
import sys, json, time; sys.path.insert(0, '.')
import sales, ua
G = "g1"
SETTINGS = {"enableNodeLevelLogging": True, "enableRunLogging": True, "enableVariableLogging": True, "route": {"default": False, "tierName": "global"}}
ROW = {"type": "object", "additionalProperties": False, "properties": {}}
_V = {}
def V(node, res):
    if node not in _V: _V[node] = {o["name"]: o["version"] for o in ua.call("GET", f"/api/workflow-builder/node/{node}/resources")["objects"]}
    return _V[node][res]
def node(nid, ntype, title, app, res, inputs, index, group=G, fallback="STOP", ctype=True):
    ctx = {"appName": app, "resourceName": res, "resourceVersion": V(app, res)}
    if ctype: ctx["type"] = "APPLICATION"
    return {"id": nid, "type": ntype, "title": title, "context": ctx, "inputs": inputs, "groupId": group, "index": index, "fallbackMode": fallback, "skip": False}
def start(props, required, index=1):
    n = node("n_in", "START", "Trigger via automation", "callables", "callables_from_automation",
             {"setup": {"type": "object", "additionalProperties": False, "required": required, "properties": {k: dict(v, title=k) for k, v in props.items()}}}, index, ctype=False)
    n["trigger"] = {"type": "CALLABLE"}; return n
def schedule_start(cron, index=1):
    n = node("n_in", "START", "Schedule", "schedule", "schedule_default", {"cron": "EXPRESSION", "expression": cron, "sequential": True}, index, ctype=False)
    n["trigger"] = {"type": "SCHEDULED"}; return n
def stop(result, index, nid="n_out", group=G):
    return node(nid, "STOP", "Respond to automation", "callables", "callables_return_to_automation", {"result": result}, index, group)
def invoke_agent(nid, title, agent_ref, query_ref, index, group=G, fallback="MANUAL"):
    return node(nid, "CALL_INTERFACE_WORKFLOW", title, "ai_agents_by_unifyapps", "ai_agents_by_unifyapps_invoke_agent",
                {"callableInterfaceId": "__ua__invoke_ai_agent_by_unifyapps", "triggerWorkflowWithRuntimeType": "IN_MEMORY",
                 "defaultFallbackWorkflowId": "68050ca67df58855654804a0",
                 "parameters": {"aiAgentId": agent_ref, "userQuery": query_ref}}, index, group, fallback=fallback, ctype=False)
def groovy(nid, title, code, params, ptypes, outputs, index, group=G):
    ins = {k: ({"type": "array", "items": ROW, "title": k} if ptypes.get(k) == "array" else {"type": ptypes.get(k, "string"), "title": k}) for k in params}
    outs = {k: (dict(v, title=k) if isinstance(v, dict) else {"type": v, "title": k}) for k, v in outputs.items()}
    return node(nid, "ACTION", title, "code_by_unifyapps", "code_by_unifyapps_groovy",
                {"input": {"type": "object", "additionalProperties": False, "required": [], "properties": ins},
                 "output": {"type": "object", "additionalProperties": False, "required": list(outputs), "properties": outs},
                 "code": code, "parameters": params, "compile_static": False, "captureStdOutput": False}, index, group, sub=None) if False else \
           {**node(nid, "ACTION", title, "code_by_unifyapps", "code_by_unifyapps_groovy",
                {"input": {"type": "object", "additionalProperties": False, "required": [], "properties": ins},
                 "output": {"type": "object", "additionalProperties": False, "required": list(outputs), "properties": outs},
                 "code": code, "parameters": params, "compile_static": False, "captureStdOutput": False}, index, group)}
def arr(ref): return {"source": "{{ %s }}" % ref, "items": "{{ %s[0] }}" % ref, "ua:type": "mappedArray"}
def e(a, b, t="next", name=None):
    d = {"fromNodeId": a, "toNodeId": b, "type": t, "id": f"{t}@{a}@{b}"}
    if name: d["name"] = name
    return d
def save(name, desc, nodes, edges, wid=None, tags=("DB",)):
    if wid is None:
        wid = ua.call("POST", "/api/workflow-definition", {"name": name, "description": desc, "tags": list(tags),
              "nodes": [{"id": "n_seed", "type": "START", "title": "seed", "trigger": {"type": "EVENT"}, "index": 0, "groupId": "n_seed-1", "fallbackMode": "STOP", "skip": False}], "edges": []})["id"]
    cur = ua.call("GET", f"/api/workflow-definition/{wid}")
    r = ua.call("POST", "/api/workflow-definition/saveAndReturnViolations", {"id": wid, "name": name, "description": desc, "version": cur["version"],
         "standard": False, "schemaReferences": [], "settings": SETTINGS, "tags": list(tags), "nodes": nodes, "edges": edges})
    return wid, r["workflowDefinition"]["version"], r.get("violations")
def deploy(wid, notes):
    ver = ua.call("GET", f"/api/workflow-definition/{wid}")["version"]
    ua.call("POST", f"/api/workflow-definition/{wid}/deploy?version={ver}", {"deploymentNotes": notes, "_type": "WORKFLOW_DEPLOY_OPTIONS"})
    wf = ua.call("GET", f"/api/workflow-definition/{wid}")
    return wf.get("version"), (wf.get("deploymentState") or {}).get("workflowVersion")
def test(wid, payload, nodes=("n_out",), timeout_s=300, init_timeout=120):
    wf = ua.call("GET", f"/api/workflow-definition/{wid}")
    try:
        rid = ua.call("POST", f"/api/test-workflow/initiate-test/{wid}", {"payload": payload, "type": "MOCK", "workflowDefinition": {k: v for k, v in wf.items() if k != "id"}}, timeout=init_timeout)["runId"]
    except RuntimeError as ex:
        return {"status": "START_ERROR", "error": str(ex)[:300], "nodes": {}}
    cols, dl = None, time.time() + timeout_s
    while time.time() < dl:
        time.sleep(3)
        o = ua.call("POST", "/api/aggregation?entityType=WORKFLOW_EXECUTION&group=TEST_WORKFLOW_EXECUTION", {"entityType": "WORKFLOW_EXECUTION", "group": "TEST_WORKFLOW_EXECUTION",
            "projections": [{"name": n} for n in ("ID", "STATUS", "EXECUTION_TIME", "START_TIME", "END_TIME", "FAILED_NODES")],
            "filter": {"op": "IN", "field": "ID", "values": [rid]}, "page": {"limit": 1, "offset": 0}}).get("objects") or []
        if o:
            cols = o[0]["columns"]
            if cols.get("STATUS") in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"): break
    if not cols: return {"status": "NO_STATUS", "runId": rid, "nodes": {}}
    keys = [f"{rid}.{rid}.{n}" for n in nodes]
    out = ua.call("POST", "/api/lookup?ByKeys=TEST_WORKFLOW_VARIABLE", {"type": "ByKeys", "lookupType": "TEST_WORKFLOW_VARIABLE", "keys": keys,
          "options": {"startTime": cols["START_TIME"] - 10000, "endTime": (cols.get("END_TIME") or cols["START_TIME"]) + 10000, "workflowId": wid}})["response"]["objects"]
    res = {}
    for n, k in zip(nodes, keys):
        for ent in out.get(k, []): res.setdefault(n, {})[ent["type"]] = ent.get("payload")
    return {"runId": rid, "status": cols.get("STATUS"), "ms": cols.get("EXECUTION_TIME"), "failed": cols.get("FAILED_NODES"), "nodes": res}
