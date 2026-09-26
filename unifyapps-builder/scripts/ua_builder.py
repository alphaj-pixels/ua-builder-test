#!/usr/bin/env python3
"""
UnifyApps spec-driven builder.

Describe agents, tasks and workflows as plain data at the bottom of this file, then run
it. Everything is created, validated, deployed and (optionally) smoke-tested.

    python ua_builder.py

Runs as YOUR account: set UA_USERNAME (and UA_IDP_ID on tenants other than UAT), then it
prompts for the password with hidden input. Nothing is stored. Standard library only
(Python 3.8+).

This is the generalised form of a fleet-operations agent that was built and verified end
to end against the UAT sandbox: 1 agent, 2 tasks, 4 workflows (Oracle SQL, REST,
branching, multi-step), 4 tools.

Environment:
    UA_USERNAME              required - your own local (non-SSO) account
    UA_ORACLE_CONNECTION_ID  required by the example spec - an Oracle connection you own
    UA_BASE_URL              optional, default https://orbit.uat.unifyapps.com
    UA_IDP_ID                required on tenants other than UAT
    UA_PASSWORD              optional; otherwise prompted with getpass (preferred)
"""

import getpass
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

# No credentials or personal accounts live in this file. Each user supplies their own
# account through the environment; the password is prompted for with hidden input.
BASE = os.environ.get("UA_BASE_URL", "https://orbit.uat.unifyapps.com").rstrip("/")
USERNAME = os.environ.get("UA_USERNAME", "")
# The local-login provider id is tenant-wide (not a secret). Known tenants are filled in;
# for any other tenant set UA_IDP_ID - see references/connect-and-call.md.
KNOWN_IDP_IDS = {"https://orbit.uat.unifyapps.com": "65d2f4cf672d16da08efc3d0"}
IDP_ID = os.environ.get("UA_IDP_ID") or KNOWN_IDP_IDS.get(BASE, "")
# Your own Oracle connection id on this tenant (find it with the Connection aggregation query).
ORACLE_CONNECTION_ID = os.environ.get("UA_ORACLE_CONNECTION_ID", "")

_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def require_account():
    missing = [n for n, v in (("UA_USERNAME", USERNAME), ("UA_IDP_ID", IDP_ID)) if not v]
    if missing:
        sys.exit("Set %s to your own local (non-SSO) UnifyApps account - see "
                 "references/connect-and-call.md. No account is built in." % " and ".join(missing))


def call(method, path, body=None, expect=(200, 201, 204)):
    url = path if path.startswith("http") else BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with _opener.open(req, timeout=120) as r:
            raw, status = r.read().decode("utf-8", "replace"), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode("utf-8", "replace"), e.code
    if status not in expect:
        raise RuntimeError(f"{method} {path} -> HTTP {status}\n{raw[:600]}")
    return json.loads(raw) if raw else None


def login(password):
    call("POST", "/auth/workflow/execute/node?name=emailAndPassLoginRequest", {
        "id": "emailAndPassLoginRequest",
        "context": {"appName": "auth_by_unifyapps", "resourceName": "auth_by_unifyapps_login"},
        "inputs": {"returnTo": "/", "failureReturnTo": f"{BASE}/login",
                   "formData": {"username": USERNAME, "password": password, "rememberMe": True},
                   "identityProviderId": IDP_ID},
        "options": {"cacheConfig": {}},
    })


# --------------------------------------------------------------- version resolution
# resourceVersion drifts between releases and environments - never hardcode it.
_VCACHE = {}


def version(node, resource):
    if node not in _VCACHE:
        res = call("GET", f"/api/workflow-builder/node/{node}/resources")
        _VCACHE[node] = {o["name"]: o["version"] for o in res.get("objects", [])}
    v = _VCACHE[node].get(resource)
    if v is None:
        raise RuntimeError(f"{resource} not found on node {node}")
    return v


# ------------------------------------------------------------------ node factories
GROUP = "g1"
SETTINGS = {"enableNodeLevelLogging": True, "enableRunLogging": True,
            "enableVariableLogging": True,
            "route": {"default": False, "tierName": "global"}}


def _node(nid, ntype, title, app, resource, inputs, index, group=GROUP,
          fallback="STOP", subtitle=None, extra_context=None):
    ctx = {"appName": app, "resourceName": resource,
           "resourceVersion": version(app, resource), "type": "APPLICATION"}
    if extra_context:
        ctx.update(extra_context)
    n = {"id": nid, "type": ntype, "title": title, "context": ctx, "inputs": inputs,
         "groupId": group, "index": index, "fallbackMode": fallback, "skip": False}
    if subtitle:
        n["subTitle"] = subtitle
    return n


def trigger(params, nid="n_in", index=1):
    """CALLABLE trigger. `params` is {name: json-schema-type}; it becomes the agent
    tool's argument contract."""
    props = {k: {"type": v, "title": k} for k, v in params.items()}
    n = _node(nid, "START", "Trigger via automation", "callables",
              "callables_from_automation",
              {"setup": {"type": "object", "additionalProperties": False,
                         "required": list(params), "properties": props}}, index)
    n["trigger"] = {"type": "CALLABLE"}
    n["context"].pop("type", None)          # trigger context carries no "type"
    return n


def respond(result, nid="n_out", index=99, group=GROUP):
    return _node(nid, "STOP", "Respond to automation", "callables",
                 "callables_return_to_automation", {"result": result}, index, group)


def sql(nid, statement, index, connection_id=None, fallback="CONTINUE"):
    return _node(nid, "ACTION", "Execute a SQL statement", "oracledb",
                 "oracledb_execute_sql", {"sql": statement}, index,
                 fallback=fallback, subtitle="Oracle DB",
                 extra_context={"connectionId": connection_id or ORACLE_CONNECTION_ID})


def http(nid, base_url, path, index, method="GET", fallback="CONTINUE", **extra):
    inputs = {"baseUrl": base_url, "path": path, "httpMethod": method,
              "requestTimeoutInSecs": 30, "sslVerify": True}
    inputs.update(extra)
    return _node(nid, "ACTION", "Execute REST request", "custom_http_endpoint",
                 "custom_http_endpoint_execute", inputs, index,
                 fallback=fallback, subtitle="HTTP")


def groovy(nid, code, params, outputs, index, group=GROUP, fallback="MANUAL"):
    """params: {name: "{{ template }}"}   outputs: [field names]
    Code reads params as bare variables and returns a map. Read results back as
    {{ nid.outputs.result.<field> }} - note the `result` nesting."""
    return _node(nid, "ACTION", "Execute Groovy code", "code_by_unifyapps",
                 "code_by_unifyapps_groovy", {
                     "input": {"type": "object", "additionalProperties": False,
                               "required": list(params),
                               "properties": {k: {"type": "string", "title": k} for k in params}},
                     "output": {"type": "object", "additionalProperties": False,
                                "required": outputs,
                                "properties": {k: {"type": "string", "title": k} for k in outputs}},
                     "code": code, "parameters": params,
                     "compile_static": False, "captureStdOutput": False,
                 }, index, group=group, fallback=fallback, subtitle="Code")


def condition(nid, prop, operator, value, index, group=GROUP):
    return _node(nid, "IF_ELSE", "Condition", "if_else", "if_else_condition",
                 {"operator": "AND",
                  "filters": [{"property": prop, "filter": {"operator": operator, "value": value}}]},
                 index, group=group, subtitle="Condition")


def edge(frm, to, etype="next", name=None):
    e = {"fromNodeId": frm, "toNodeId": to, "type": etype, "id": f"{etype}@{frm}@{to}"}
    if name:
        e["name"] = name
    return e


def branch_group(if_node_id, parent=GROUP, suffix="y"):
    """Nodes inside a branch/loop body need this groupId."""
    return f"{if_node_id}@{parent}@{suffix}"


# -------------------------------------------------------------- workflow lifecycle
def build_workflow(name, description, nodes, edges, deploy=True):
    created = call("POST", "/api/workflow-definition", {
        "name": name, "description": description,
        "nodes": [{"id": "n_seed", "type": "START", "title": "seed",
                   "trigger": {"type": "EVENT"}, "index": 0, "groupId": "n_seed-1",
                   "fallbackMode": "STOP", "skip": False}],
        "edges": [],
    })
    wid = created["id"]
    saved = call("POST", "/api/workflow-definition/saveAndReturnViolations", {
        "id": wid, "name": name, "description": description,
        "version": created["version"], "standard": False, "schemaReferences": [],
        "settings": SETTINGS, "nodes": nodes, "edges": edges,
    })
    violations = saved.get("violations") or saved.get("nodeViolations")
    if violations:
        raise RuntimeError(f"{name}: violations {json.dumps(violations)[:400]}")
    ver = saved["workflowDefinition"]["version"]
    if deploy:
        call("POST", f"/api/workflow-definition/{wid}/deploy?version={ver}",
             {"deploymentNotes": "built by ua_builder", "_type": "WORKFLOW_DEPLOY_OPTIONS"})
    return wid


def run_workflow(wid, payload, timeout_s=25):
    wf = call("GET", f"/api/workflow-definition/{wid}")
    defn = {k: v for k, v in wf.items() if k != "id"}
    run = call("POST", f"/api/test-workflow/initiate-test/{wid}",
               {"payload": payload, "type": "MOCK", "workflowDefinition": defn})
    rid, cols = run["runId"], None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(0.8)
        res = call("POST", "/api/aggregation?entityType=WORKFLOW_EXECUTION&group=TEST_WORKFLOW_EXECUTION", {
            "entityType": "WORKFLOW_EXECUTION", "group": "TEST_WORKFLOW_EXECUTION",
            "projections": [{"name": "ID"}, {"name": "STATUS"}, {"name": "EXECUTION_TIME"},
                            {"name": "START_TIME"}, {"name": "END_TIME"}, {"name": "FAILED_NODES"}],
            "filter": {"op": "IN", "field": "ID", "values": [rid]},
            "page": {"limit": 5, "offset": 0}})
        objs = res.get("objects") or []
        if objs:
            cols = objs[0]["columns"]
            if cols.get("STATUS") in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
                break
    out = call("POST", "/api/lookup?ByKeys=TEST_WORKFLOW_VARIABLE", {
        "type": "ByKeys", "lookupType": "TEST_WORKFLOW_VARIABLE",
        "keys": [f"{rid}.{rid}.n_out"],
        "options": {"startTime": cols["START_TIME"] - 10000,
                    "endTime": (cols.get("END_TIME") or cols["START_TIME"]) + 10000,
                    "workflowId": wid}})
    entries = out["response"]["objects"].get(f"{rid}.{rid}.n_out", [])
    return {"status": cols.get("STATUS"), "ms": cols.get("EXECUTION_TIME"),
            "failed": cols.get("FAILED_NODES"),
            "output": entries[0]["payload"] if entries else None}


# ----------------------------------------------------------------- agent lifecycle
def build_agent(name, instructions, agent_type="CONVERSATIONAL"):
    a = call("POST", "/api/entity", {"entityType": "ai_agent", "properties": {
        "name": name, "agentType": agent_type, "instructions": instructions}})
    return a["id"]


def build_task(agent_id, name, when_to_use, steps):
    t = call("POST", "/api/entity", {"entityType": "e_topic_ai_agent", "properties": {
        "name": name, "description": when_to_use, "instructions": steps,
        "aiAgentId": agent_id, "enabled": True, "isAppConnector": False,
        "runTimeConnectionEnabled": False, "governanceConfig": {}}})
    return t["id"]


def build_tool(agent_id, topic_id, name, description, workflow_id):
    t = call("POST", "/api/entity", {"entityType": "e_action_ai_agent", "properties": {
        "name": name, "description": description,
        "aiAgentId": agent_id, "topicId": topic_id,
        "context": {"appName": "callables", "resourceName": "callables_call_automation"},
        "inputs": {"automationId": workflow_id, "version": "-1", "synchronous": True,
                   "runtimeConnections": {}, "parameters": {}},
        "enabled": True}})     # enabled defaults to False if omitted
    return t["id"]


def publish_agent(agent_id, notes="published by ua_builder"):
    ent = call("GET", f"/api/entity/ai_agent/{agent_id}")
    call("POST", "/api/entity/action/saveAndDeploy", {**ent, "deploymentNotes": notes})
    return call("GET", f"/api/entity/ai_agent/{agent_id}").get("deploymentState")


# ====================================================================== THE SPEC
# Edit from here down. Each workflow is a function so node ids stay local.

def wf_vehicle_lookup():
    return build_workflow(
        "Fleet - Vehicle Lookup", "Look up a vehicle record in Oracle by id",
        [trigger({"vehicleId": "string"}),
         sql("n_sql", "SELECT '{{ n_in.outputs.vehicleId }}' AS VEHICLE_ID, "
                      "'ACTIVE' AS STATUS, SYSDATE AS AS_OF FROM DUAL", 2),
         respond({"vehicleId": "{{ n_in.outputs.vehicleId }}",
                  "rows": "{{ n_sql.outputs.rows }}",
                  "rowsCount": "{{ n_sql.outputs.rowsCount }}"}, index=3)],
        [edge("n_in", "n_sql"), edge("n_sql", "n_out")])


def wf_vehicle_telemetry():
    return build_workflow(
        "Fleet - Vehicle Telemetry", "Fetch live telemetry for a vehicle",
        [trigger({"vehicleId": "string"}),
         http("n_http", "https://jsonplaceholder.typicode.com", "/posts/1", 2),
         respond({"vehicleId": "{{ n_in.outputs.vehicleId }}",
                  "status": "{{ n_http.outputs.status }}",
                  "telemetry": "{{ n_http.outputs.result }}"}, index=3)],
        [edge("n_in", "n_http"), edge("n_http", "n_out")])


def wf_maintenance_due():
    gy = branch_group("n_if")
    return build_workflow(
        "Fleet - Maintenance Due Check",
        "Decide whether a vehicle is due for service using mileage and its service record",
        [trigger({"vehicleId": "string", "mileage": "integer"}),
         sql("n_sql", "SELECT '{{ n_in.outputs.vehicleId }}' AS VEHICLE_ID, "
                      "9000 AS LAST_SERVICE_KM, SYSDATE AS AS_OF FROM DUAL", 2),
         condition("n_if", "{{ n_in.outputs.mileage }}", "GTE", "10000", 3),
         groovy("n_due", 'return ["recommendation": "Service now - odometer at " + km + " km"];',
                {"km": "{{ n_in.outputs.mileage }}"}, ["recommendation"], 4, group=gy),
         respond({"vehicleId": "{{ n_in.outputs.vehicleId }}",
                  "mileage": "{{ n_in.outputs.mileage }}",
                  "serviceRecord": "{{ n_sql.outputs.rows }}",
                  "recommendation": "{{ n_due.outputs.result.recommendation }}"}, index=5)],
        # both branches converge on n_out
        [edge("n_in", "n_sql"), edge("n_sql", "n_if"),
         edge("n_if", "n_due", "if", "yes"), edge("n_due", "n_out"),
         edge("n_if", "n_out", "next", "no")])


def wf_service_ticket():
    return build_workflow(
        "Fleet - Raise Service Ticket", "Create a service ticket and return a reference",
        [trigger({"vehicleId": "string", "issue": "string"}),
         http("n_http", "https://jsonplaceholder.typicode.com", "/posts", 2,
              method="POST", fallback="MANUAL"),
         groovy("n_ref",
                'def ref = "TKT-" + vid.toUpperCase() + "-" + (System.currentTimeMillis() % 100000);\n'
                'return ["ticketRef": ref, "summary": "Ticket " + ref + " raised for " + issue];',
                {"vid": "{{ n_in.outputs.vehicleId }}", "issue": "{{ n_in.outputs.issue }}"},
                ["ticketRef", "summary"], 3),
         respond({"ok": False, "reason": "ticketing call failed"},
                 nid="n_err", index=4, group=branch_group("n_http", suffix="error")),
         respond({"ok": True, "vehicleId": "{{ n_in.outputs.vehicleId }}",
                  "httpStatus": "{{ n_http.outputs.status }}",
                  "ticketRef": "{{ n_ref.outputs.result.ticketRef }}",
                  "summary": "{{ n_ref.outputs.result.summary }}"}, index=5)],
        [edge("n_in", "n_http"), edge("n_http", "n_err", "error", "error"),
         edge("n_http", "n_ref"), edge("n_ref", "n_out")])


def main():
    require_account()
    if not ORACLE_CONNECTION_ID:
        sys.exit("Set UA_ORACLE_CONNECTION_ID to an Oracle connection you own on this tenant "
                 "(the example spec uses one) - see references/connect-and-call.md section 4.")
    pw = os.environ.get("UA_PASSWORD") or getpass.getpass(f"Password for {USERNAME}: ")
    print(f"\nlogging in to {BASE} as {USERNAME}")
    login(pw)

    print("\nbuilding workflows")
    wfs = {
        "lookup": wf_vehicle_lookup(),
        "telemetry": wf_vehicle_telemetry(),
        "maintenance": wf_maintenance_due(),
        "ticket": wf_service_ticket(),
    }
    for k, v in wfs.items():
        print(f"  {k:12} {v}")

    print("\nsmoke tests")
    checks = [("lookup", {"vehicleId": "VH-1042"}),
              ("telemetry", {"vehicleId": "VH-1042"}),
              ("maintenance", {"vehicleId": "VH-1042", "mileage": 14200}),
              ("ticket", {"vehicleId": "VH-1042", "issue": "brake wear warning"})]
    for key, payload in checks:
        r = run_workflow(wfs[key], payload)
        print(f"  {key:12} {r['status']:10} {r['ms']}ms  failed={r['failed']}")

    print("\nbuilding agent")
    agent = build_agent("Fleet Operations Assistant",
        "You help fleet operators check vehicle status and manage servicing. Always confirm "
        "the vehicle id before acting. Use the tools rather than guessing; if a tool returns "
        "no data, say so plainly instead of inventing values.")

    task_status = build_task(agent, "Vehicle Status",
        "Use this task when the user asks about a vehicle's current status, record, or live telemetry.",
        ["Confirm the vehicle id with the user if it was not given.",
         "Call VehicleLookup to get the vehicle record from the fleet database.",
         "If the user asks about live data, also call VehicleTelemetry.",
         "Summarise the record and telemetry together in plain English. Do not show raw JSON."])

    task_service = build_task(agent, "Maintenance and Service",
        "Use this task when the user asks whether a vehicle needs servicing, or asks to raise a service ticket.",
        ["Confirm the vehicle id and current mileage.",
         "Call MaintenanceDueCheck with the vehicle id and mileage.",
         "If a recommendation comes back, tell the user the vehicle is due and ask whether to raise a ticket.",
         "Only if the user confirms, call RaiseServiceTicket with the vehicle id and a short issue description.",
         "Report the returned ticket reference back to the user."])

    build_tool(agent, task_status, "VehicleLookup",
               "Look up a vehicle record by vehicle id. Returns the vehicle row and its status.", wfs["lookup"])
    build_tool(agent, task_status, "VehicleTelemetry",
               "Fetch live telemetry for a vehicle by vehicle id.", wfs["telemetry"])
    build_tool(agent, task_service, "MaintenanceDueCheck",
               "Check whether a vehicle is due for service. Requires vehicle id and current mileage.", wfs["maintenance"])
    build_tool(agent, task_service, "RaiseServiceTicket",
               "Raise a service ticket. Requires vehicle id and a short issue description.", wfs["ticket"])

    state = publish_agent(agent)
    print(f"  agent {agent} published v{state.get('version')}")
    print(f"\n{BASE}/p/0/ai-agents/{agent}/configuration/topics")


if __name__ == "__main__":
    main()
