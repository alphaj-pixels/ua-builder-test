#!/usr/bin/env python3
"""
UnifyApps automation client — end-to-end demo.

Logs in with a service account, then builds, deploys, runs and reads back a workflow
using nothing but HTTP calls.

    Callable trigger (customerId, maxRows)
        -> Oracle SQL      (optional, only if UA_ORACLE_CONNECTION_ID is set)
        -> HTTP REST call
        -> JSON response

Zero third-party dependencies: standard library only (Python 3.8+).

USAGE — runs as YOUR account; no account is built in:

    UA_USERNAME=<your local username> python ua_client.py

It prompts for the password (hidden input), then runs the whole scenario.

Environment:
    UA_USERNAME              required - your own local (non-SSO) account
    UA_IDP_ID                required on tenants other than UAT
    UA_ORACLE_CONNECTION_ID  optional - an Oracle connection you own; Oracle step skipped if unset
    UA_BASE_URL, UA_HTTP_BASE_URL, UA_HTTP_PATH, UA_SKIP_ORACLE=1, UA_PASSWORD  optional

The password is never echoed, never written to disk, and never logged.
"""

import getpass
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.parse
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
HTTP_BASE_URL = os.environ.get("UA_HTTP_BASE_URL", "https://jsonplaceholder.typicode.com")
HTTP_PATH = os.environ.get("UA_HTTP_PATH", "/users/1")

# Set UA_SKIP_ORACLE=1 to build the workflow without the database step.
if os.environ.get("UA_SKIP_ORACLE"):
    ORACLE_CONNECTION_ID = None

if not USERNAME or not IDP_ID:
    sys.exit("Set UA_USERNAME (and UA_IDP_ID on tenants other than UAT) to your own local "
             "UnifyApps account - see references/connect-and-call.md. No account is built in.")

print(f"UnifyApps : {BASE}")
print(f"user      : {USERNAME}")
print(f"oracle    : {ORACLE_CONNECTION_ID or '(skipped)'}")

# Prompted, never echoed, never stored.
PASSWORD = os.environ.get("UA_PASSWORD") or getpass.getpass(f"Password for {USERNAME}: ")
if not PASSWORD:
    sys.exit("No password supplied.")

# One cookie jar for the whole session. The session cookie is httpOnly, so it must be
# stored and replayed rather than read out by hand.
_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def call(method, path, body=None, expect=(200, 201, 204)):
    """Send a JSON request and return the decoded JSON response (or None)."""
    url = path if path.startswith("http") else BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with _opener.open(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        status = e.code
    if status not in expect:
        raise RuntimeError(f"{method} {path} -> HTTP {status}\n{raw[:600]}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def step(msg):
    print(f"\n=== {msg}")


# ---------------------------------------------------------------- 1. authenticate
step("Logging in")
try:
    call("POST", "/auth/workflow/execute/node?name=emailAndPassLoginRequest", {
        "id": "emailAndPassLoginRequest",
        "context": {"appName": "auth_by_unifyapps", "resourceName": "auth_by_unifyapps_login"},
        "inputs": {
            "returnTo": "/",
            "failureReturnTo": f"{BASE}/login",
            "formData": {"username": USERNAME, "password": PASSWORD, "rememberMe": True},
            "identityProviderId": IDP_ID,
        },
        "options": {"cacheConfig": {}},
    })
except RuntimeError as e:
    if "401" in str(e):
        sys.exit(
            "\nLogin rejected.\n"
            "  - wrong username or password, or\n"
            "  - the account still has 'First Login' set (log in once in a browser to clear it), or\n"
            "  - MFA is enforced on this account, or\n"
            f"  - the tenant uses a different identityProviderId than {IDP_ID}\n"
        )
    raise

try:
    me = call("GET", "/api/user-context?includeRoles=true")
except RuntimeError as e:
    sys.exit(f"\nLogged in, but could not read the user context - likely a permissions gap.\n{e}\n")
who = me.get("email") or me.get("username") or me.get("name") if isinstance(me, dict) else None
print(f"authenticated as: {who}")


# ------------------------------------------------- 2. resolve action versions live
step("Resolving action versions from the node catalog")


def resolve(node_name, resource_name):
    """resourceVersion moves between environments - always look it up."""
    res = call("GET", f"/api/workflow-builder/node/{node_name}/resources")
    for obj in res.get("objects", []):
        if obj.get("name") == resource_name:
            return obj["version"]
    raise RuntimeError(f"{resource_name} not found on node {node_name}")


V_CALLABLE_IN = resolve("callables", "callables_from_automation")
V_CALLABLE_OUT = resolve("callables", "callables_return_to_automation")
V_HTTP = resolve("custom_http_endpoint", "custom_http_endpoint_execute")
V_SQL = resolve("oracledb", "oracledb_execute_sql") if ORACLE_CONNECTION_ID else None
print(f"callable in/out: {V_CALLABLE_IN}/{V_CALLABLE_OUT}  http: {V_HTTP}  sql: {V_SQL}")


# ------------------------------------------------------------------- 3. create it
step("Creating the workflow")
created = call("POST", "/api/workflow-definition", {
    "name": f"Agent Built {int(time.time())}",
    "description": "created end-to-end by ua_client.py",
    # nodes must be non-null or the service returns HTTP 500
    "nodes": [{
        "id": "n_seed", "type": "START", "title": "Select a trigger event",
        "trigger": {"type": "EVENT"}, "index": 0, "groupId": "n_seed-1",
        "fallbackMode": "STOP", "skip": False, "debug": False, "dirty": False,
    }],
    "edges": [],
})
wf_id = created["id"]
print(f"workflow id: {wf_id}")


# ------------------------------------------------------- 4. build the real graph
step("Saving the full graph")

nodes = [{
    "id": "n_in", "type": "START", "title": "Trigger via automation",
    "trigger": {"type": "CALLABLE"},
    "context": {"appName": "callables", "resourceName": "callables_from_automation",
                "resourceVersion": V_CALLABLE_IN},
    "inputs": {"setup": {
        "type": "object", "additionalProperties": False, "required": ["customerId"],
        "properties": {
            "customerId": {"type": "string", "title": "customerId"},
            "maxRows": {"type": "integer", "title": "maxRows"},
        },
    }},
    "groupId": "g1", "fallbackMode": "STOP", "skip": False, "index": 1,
}]
edges = []
prev = "n_in"
idx = 2

if ORACLE_CONNECTION_ID:
    nodes.append({
        "id": "n_sql", "type": "ACTION", "title": "Execute a SQL statement", "subTitle": "Oracle DB",
        "context": {"appName": "oracledb", "resourceName": "oracledb_execute_sql",
                    "resourceVersion": V_SQL, "connectionId": ORACLE_CONNECTION_ID,
                    "type": "APPLICATION"},
        # the trigger parameter is injected straight into live SQL
        "inputs": {"sql": "SELECT '{{ n_in.outputs.customerId }}' AS CUSTOMER_ID, "
                          "SYSDATE AS AS_OF FROM DUAL"},
        "groupId": "g1", "fallbackMode": "CONTINUE", "skip": False, "index": idx,
    })
    edges.append({"fromNodeId": prev, "toNodeId": "n_sql", "type": "next",
                  "id": f"next@{prev}@n_sql"})
    prev, idx = "n_sql", idx + 1

nodes.append({
    "id": "n_http", "type": "ACTION", "title": "Execute REST request", "subTitle": "HTTP",
    "context": {"appName": "custom_http_endpoint", "resourceName": "custom_http_endpoint_execute",
                "resourceVersion": V_HTTP, "type": "APPLICATION"},
    "inputs": {"baseUrl": HTTP_BASE_URL, "path": HTTP_PATH, "httpMethod": "GET",
               "requestTimeoutInSecs": 30, "sslVerify": True},
    "groupId": "g1", "fallbackMode": "CONTINUE", "skip": False, "index": idx,
})
edges.append({"fromNodeId": prev, "toNodeId": "n_http", "type": "next",
              "id": f"next@{prev}@n_http"})
idx += 1

result = {
    "customerId": "{{ n_in.outputs.customerId }}",
    "maxRows": "{{ n_in.outputs.maxRows }}",
    "http": {"status": "{{ n_http.outputs.status }}", "body": "{{ n_http.outputs.result }}"},
}
if ORACLE_CONNECTION_ID:
    result["oracle"] = {"rows": "{{ n_sql.outputs.rows }}",
                        "rowsCount": "{{ n_sql.outputs.rowsCount }}"}

nodes.append({
    "id": "n_out", "type": "STOP", "title": "Respond to automation",
    "context": {"appName": "callables", "resourceName": "callables_return_to_automation",
                "resourceVersion": V_CALLABLE_OUT, "type": "APPLICATION"},
    "inputs": {"result": result},
    "groupId": "g1", "fallbackMode": "STOP", "skip": False, "index": idx,
})
edges.append({"fromNodeId": "n_http", "toNodeId": "n_out", "type": "next",
              "id": "next@n_http@n_out"})

definition = {
    "id": wf_id,
    "name": created["name"],
    "description": created.get("description", ""),
    "version": created["version"],
    "standard": False,
    "schemaReferences": [],
    "settings": {"enableNodeLevelLogging": True, "enableRunLogging": True,
                 "enableVariableLogging": True,
                 "route": {"default": False, "tierName": "global"}},
    "nodes": nodes,
    "edges": edges,
}

saved = call("POST", "/api/workflow-definition/saveAndReturnViolations", definition)
wf = saved["workflowDefinition"]
violations = saved.get("violations") or saved.get("nodeViolations")
print(f"saved version {wf['version']}, appsUsed={wf.get('appsUsed')}, violations={violations}")
if violations:
    sys.exit("Refusing to continue - the graph has violations.")


# ----------------------------------------------------------------- 5. deploy it
step("Deploying")
deployed = call("POST", f"/api/workflow-definition/{wf_id}/deploy?version={wf['version']}", {
    "deploymentNotes": "deployed by ua_client.py",
    "_type": "WORKFLOW_DEPLOY_OPTIONS",
})
dw = deployed.get("workflowDefinition", deployed)
print(f"deployed version: {dw.get('deployedWorkflowVersion')}")


# -------------------------------------------------------------------- 6. run it
step("Running with input parameters")
payload = {"customerId": "CUST-12345", "maxRows": 10}
run = call("POST", f"/api/test-workflow/initiate-test/{wf_id}", {
    "payload": payload,
    "type": "MOCK",
    "workflowDefinition": {k: v for k, v in wf.items() if k != "id"},
})
run_id = run["runId"]
print(f"runId: {run_id}  payload: {json.dumps(payload)}")

status, started, ended = None, None, None
for _ in range(60):
    time.sleep(1)
    res = call("POST", "/api/aggregation?entityType=WORKFLOW_EXECUTION&group=TEST_WORKFLOW_EXECUTION", {
        "entityType": "WORKFLOW_EXECUTION", "group": "TEST_WORKFLOW_EXECUTION",
        "projections": [{"name": "STATUS"}, {"name": "EXECUTION_TIME"},
                        {"name": "START_TIME"}, {"name": "END_TIME"},
                        {"name": "FAILED_NODES"}, {"name": "ID"}],
        "filter": {"op": "IN", "field": "ID", "values": [run_id]},
        "page": {"limit": 30, "offset": 0},
    })
    objs = res.get("objects") or []
    if objs:
        cols = objs[0]["columns"]
        status = cols.get("STATUS")
        started, ended = cols.get("START_TIME"), cols.get("END_TIME")
        if status in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
            print(f"status: {status} in {cols.get('EXECUTION_TIME')}ms "
                  f"failed={cols.get('FAILED_NODES')}")
            break
else:
    sys.exit(f"Run did not settle; last status {status}")


# ------------------------------------------------------------- 7. read the output
step("Reading the response JSON")
now = int(time.time() * 1000)
out = call("POST", "/api/lookup?ByKeys=TEST_WORKFLOW_VARIABLE", {
    "type": "ByKeys",
    "lookupType": "TEST_WORKFLOW_VARIABLE",
    "keys": [f"{run_id}.{run_id}.n_out"],
    "options": {"startTime": (started or now) - 10000,
                "endTime": (ended or now) + 10000,
                "workflowId": wf_id},
})
entries = out["response"]["objects"].get(f"{run_id}.{run_id}.n_out", [])
if not entries:
    sys.exit("No output recorded for n_out.")
print(json.dumps(entries[0]["payload"], indent=2))

print(f"\nDone. Workflow {wf_id} is deployed in {BASE}.")
print("Delete it with: POST /api/workflow-definition/delete/ when you are finished.")
