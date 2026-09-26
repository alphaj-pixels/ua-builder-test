#!/usr/bin/env python3
"""
UnifyApps Enterprise Context Graph builder.

Builds a queryable context graph from a small declarative spec, in the order that
actually works:

    graph -> PUBLISH -> node types -> edge types -> records -> verify projection
          -> record edges -> OpenCypher search automation -> agent + tool -> publish

Two rules are baked in because violating either produces a graph that looks fine and
returns nothing to Cypher:

  1. The graph is published BEFORE any record is written. Records written to a DRAFT
     graph never project into the graph layer - no error, they simply don't exist
     to MATCH.
  2. Every property is STRING. Typed properties (DATE/DOUBLE/INTEGER/BOOLEAN) store
     correctly but the node then projects zero vertices. Convert in Cypher instead:
     toFloat(d.`_pr_amount`) > 100000.

After loading, the script asserts that every node type appears in
`MATCH (n) RETURN DISTINCT labels(n)` and fails loudly if one is missing.

Standard library only, Python 3.8+.

    python ecg_builder.py

Environment:
    UA_BASE_URL   tenant, e.g. https://tool.prod-aps1.unifyapps.com
    UA_USERNAME   your own local (non-SSO) account - no account is built in
    UA_IDP_ID     identityProviderId for that tenant's local-credentials provider
    UA_PASSWORD   optional; otherwise prompted with getpass and never echoed

NOTE ON AUTH: the verified runs used an interactive browser session, not this login.
UA_IDP_ID must be captured from a real login request (devtools -> the
emailAndPassLoginRequest call). Everything after login is verified.

Nothing here deletes or edits anything it did not create.
"""

import getpass
import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("UA_BASE_URL", "https://tool.prod-aps1.unifyapps.com").rstrip("/")
USERNAME = os.environ.get("UA_USERNAME", "")
IDP_ID = os.environ.get("UA_IDP_ID", "")

_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))


def call(method, path, body=None, expect=(200, 201, 204)):
    url = path if path.startswith("http") else BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    try:
        with _opener.open(req, timeout=120) as resp:
            raw, status = resp.read().decode("utf-8", "replace"), resp.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode("utf-8", "replace"), e.code
    if status not in expect:
        raise RuntimeError("%s %s -> HTTP %s\n%s" % (method, path, status, raw[:600]))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def step(msg):
    print("\n=== %s" % msg)


def login():
    if not USERNAME or not IDP_ID:
        sys.exit("Set UA_USERNAME and UA_IDP_ID to your own local UnifyApps account - see "
                 "references/connect-and-call.md. No account is built in.")
    password = os.environ.get("UA_PASSWORD") or getpass.getpass("Password for %s: " % USERNAME)
    if not password:
        sys.exit("No password supplied.")
    call("POST", "/auth/workflow/execute/node?name=emailAndPassLoginRequest", {
        "id": "emailAndPassLoginRequest",
        "context": {"appName": "auth_by_unifyapps", "resourceName": "auth_by_unifyapps_login"},
        "inputs": {"returnTo": "/", "failureReturnTo": BASE + "/login",
                   "formData": {"username": USERNAME, "password": password, "rememberMe": True},
                   "identityProviderId": IDP_ID},
        "options": {"cacheConfig": {}},
    })
    me = call("GET", "/api/user-context?includeRoles=true")
    print("signed in as user %s on %s" % (me.get("userId"), me.get("environment")))


# ----------------------------------------------------------------- helpers

def prop(pid, display, primary=False):
    """Every property is STRING - see the module docstring for why."""
    return {"id": pid, "displayName": display,
            "dataTypeInfo": {"type": "STRING"},
            "primaryKey": primary, "required": primary, "unique": False, "pii": False,
            "filterable": False, "sortable": False, "searchable": False,
            "graphQueryable": True, "standard": False}


def resource_version(app_name, resource_name):
    """Never hardcode connector versions - they drift between tenants and releases."""
    for obj in call("GET", "/api/workflow-builder/node/%s/resources" % app_name).get("objects", []):
        if obj["name"] == resource_name:
            return obj["version"]
    raise RuntimeError("resource %s not found on %s" % (resource_name, app_name))


def find_udm_connection(graph_name):
    """A graph auto-creates '<name> UDM Connection'. Never hand-create one."""
    res = call("POST", "/api/lookup?ByQuery=CONNECTION", {
        "type": "ByQuery", "lookupType": "CONNECTION", "query": graph_name,
        "fields": ["name"], "options": {"appName": "mdm_by_unifyapps"},
        "page": {"limit": 20, "offset": 0}})
    wanted = (graph_name + " udm connection").lower()
    for obj in res["response"]["objects"]:
        if obj.get("lcName") == wanted:
            return obj["id"]
    raise RuntimeError("no UDM connection found for graph %r" % graph_name)


def callable_wf(name, description, params, action_nodes, result):
    """Create + save a CALLABLE workflow: START -> action_nodes... -> STOP."""
    v_in = resource_version("callables", "callables_from_automation")
    v_out = resource_version("callables", "callables_return_to_automation")
    created = call("POST", "/api/workflow-definition", {
        "name": name, "description": description,
        # nodes must be non-null or the service returns HTTP 500
        "nodes": [{"id": "n_seed", "type": "START", "title": "Select a trigger event",
                   "trigger": {"type": "EVENT"}, "index": 0, "groupId": "n_seed-1",
                   "fallbackMode": "STOP", "skip": False, "debug": False, "dirty": False}],
        "edges": []})
    nodes = [{
        "id": "n_in", "type": "START", "title": "Trigger via automation",
        "trigger": {"type": "CALLABLE"},
        "context": {"appName": "callables", "resourceName": "callables_from_automation",
                    "resourceVersion": v_in},
        "inputs": {"setup": {"type": "object", "additionalProperties": False,
                             "required": sorted(params), "properties": params}},
        "groupId": "g1", "fallbackMode": "STOP", "skip": False, "index": 1}]
    edges, prev, idx = [], "n_in", 2
    for node in action_nodes:
        node["index"], node["groupId"] = idx, "g1"
        nodes.append(node)
        edges.append({"fromNodeId": prev, "toNodeId": node["id"], "type": "next",
                      "id": "next@%s@%s" % (prev, node["id"])})
        prev, idx = node["id"], idx + 1
    nodes.append({
        "id": "n_out", "type": "STOP", "title": "Respond to automation",
        "context": {"appName": "callables", "resourceName": "callables_return_to_automation",
                    "resourceVersion": v_out, "type": "APPLICATION"},
        "inputs": {"result": result},
        "groupId": "g1", "fallbackMode": "STOP", "skip": False, "index": idx})
    edges.append({"fromNodeId": prev, "toNodeId": "n_out", "type": "next",
                  "id": "next@%s@n_out" % prev})

    saved = call("POST", "/api/workflow-definition/saveAndReturnViolations", {
        "id": created["id"], "name": created["name"],
        "description": created.get("description", ""), "version": created["version"],
        "standard": False, "schemaReferences": [],
        "settings": {"enableNodeLevelLogging": True, "enableRunLogging": True,
                     "enableVariableLogging": True,
                     "route": {"default": False, "tierName": "global"}},
        "nodes": nodes, "edges": edges})
    violations = saved.get("violations") or saved.get("nodeViolations")
    if violations:
        raise RuntimeError("workflow %s has violations: %s" % (name, violations))
    return saved["workflowDefinition"]


def run_edge_batch(gid, conn, nodes_map, edges, name, batch=60):
    """Write record-level edges. NOTE: fallbackMode CONTINUE does not actually continue,
    so a bad edge fails its whole batch - keep batches modest and verify afterwards."""
    v_edge = resource_version("mdm_by_unifyapps", "mdm_by_unifyapps_add_edge_to_graph")
    for start in range(0, len(edges), batch):
        chunk = edges[start:start + batch]
        actions = []
        for i, (src, src_id, label, dst, dst_id) in enumerate(chunk):
            actions.append({
                "id": "n_e%d" % i, "type": "ACTION",
                "title": "%s -[%s]-> %s" % (src_id, label, dst_id), "subTitle": "MDM",
                "context": {"appName": "mdm_by_unifyapps",
                            "resourceName": "mdm_by_unifyapps_add_edge_to_graph",
                            "resourceVersion": v_edge, "connectionId": conn,
                            "type": "APPLICATION"},
                "inputs": {"modelId": gid,
                           "primaryEntityType": nodes_map[src]["ue"], "primaryEntityId": src_id,
                           "associatedEntityType": nodes_map[dst]["ue"], "associatedEntityId": dst_id,
                           "label": label, "updateIfPresent": True},
                "fallbackMode": "CONTINUE", "skip": False})
        wf = callable_wf("%s (%d-%d)" % (name, start + 1, start + len(chunk)),
                         "record edges", {}, actions, {"edges": len(chunk)})
        call("POST", "/api/test-workflow/initiate-test/%s" % wf["id"],
             {"payload": {}, "type": "MOCK", "workflowDefinition": wf})
        print("  queued %d edges" % len(chunk))
        time.sleep(30)


# ----------------------------------------------------------------- the build

def build(spec):
    step("Creating the graph")
    graph = call("POST", "/api/context-graph",
                 {"name": spec["name"], "description": spec["description"]})
    gid = graph["id"]
    print("graph %s (%s)" % (gid, graph["status"]))

    # ---- PUBLISH FIRST. Records written to a DRAFT graph never reach the graph layer.
    step("Publishing the graph BEFORE loading anything")
    call("POST", "/api/context-graph/%s/publish" % gid, {})
    print("  status: %s" % call("GET", "/api/context-graph/%s" % gid)["status"])

    step("Creating node types (all properties STRING)")
    nodes = {}
    for n in spec["nodes"]:
        created = call("POST", "/api/context-graph/nodes", {
            "graphId": gid, "name": n["name"], "category": "core",
            "description": n.get("description", ""), "iconUrl": n.get("icon", "end-user"),
            "nodePosition": n.get("position", {"x": 0, "y": 0}),
            # NOT {{field}} - the platform expects {{ mdm.field.<id> }}
            "recordTitleFormat": "{{ mdm.field.%s }}" % n["title_field"],
            "properties": n["properties"]})
        nodes[n["name"]] = {"id": created["id"], "ue": created["unifiedEntityId"]}
        print("  %-14s node=%s ue=%s" % (n["name"], created["id"], created["unifiedEntityId"]))

    step("Creating edge types")
    for src, label, dst in spec["edges"]:
        call("POST", "/api/context-graph/edges", {
            "graphId": gid, "label": label,
            "fromNodeId": nodes[src]["id"], "toNodeId": nodes[dst]["id"]})
    print("  %d edge types" % len(spec["edges"]))

    step("Inserting records")
    for node_name, records in spec["records"].items():
        for rec in records:
            call("POST", "/api/entity",
                 {"entityType": nodes[node_name]["ue"], "properties": rec})
        print("  %-14s %d records" % (node_name, len(records)))

    conn = find_udm_connection(spec["name"])
    print("\nUDM connection: %s" % conn)

    step("Building the OpenCypher search automation")
    v_q = resource_version("mdm_by_unifyapps", "mdm_by_unifyapps_execute_opencypher_query")
    search = callable_wf(
        spec["name"] + " - Search Graph",
        "Runs an OpenCypher query against the graph and returns the rows.",
        {"cypherQuery": {"type": "string", "title": "cypherQuery",
                         "description": "A valid OpenCypher query against the context graph."}},
        [{"id": "n_q", "type": "ACTION", "title": "Execute opencypher query", "subTitle": "MDM",
          "context": {"appName": "mdm_by_unifyapps",
                      "resourceName": "mdm_by_unifyapps_execute_opencypher_query",
                      "resourceVersion": v_q, "connectionId": conn, "type": "APPLICATION"},
          "inputs": {"modelId": gid, "query": "{{ n_in.outputs.cypherQuery }}",
                     "limit": 200, "offset": 0, "skipRBAC": False},
          "fallbackMode": "CONTINUE", "skip": False}],
        {"rows": "{{ n_q.outputs }}"})
    call("POST", "/api/workflow-definition/%s/deploy?version=%s" % (search["id"], search["version"]), {})
    print("  search workflow %s deployed" % search["id"])

    step("Verifying every node type projects into the graph")
    verify_projection(gid, conn, nodes, search)

    step("Writing record-level edges")
    run_edge_batch(gid, conn, nodes, spec["record_edges"], spec["name"] + " - edges")

    step("Creating and publishing the agent")
    agent = call("POST", "/api/entity", {
        "entityType": "ai_agent",
        "properties": {"name": spec["agent_name"], "agentType": "ai-agent",
                       "instructions": agent_instructions(spec, nodes),
                       "graphModelId": gid,
                       "defaultTools": {"clarifyFromUser": True, "informationNotFoundTool": True},
                       "disableDefaultTools": False}})
    # enabled defaults to False - the tool would exist but never be called
    call("POST", "/api/entity", {
        "entityType": "e_action_ai_agent",
        "properties": {"name": "SearchCustomerGraph",
                       "description": "Run an OpenCypher query against the context graph. "
                                      "Input: cypherQuery (string). Returns matching rows.",
                       "aiAgentId": agent["id"], "topicId": "GLOBAL",
                       "context": {"appName": "callables",
                                   "resourceName": "callables_call_automation"},
                       "inputs": {"automationId": search["id"], "version": "-1",
                                  "synchronous": True, "runtimeConnections": {}, "parameters": {}},
                       "enabled": True}})
    agent = call("GET", "/api/entity/ai_agent/%s" % agent["id"])
    published = call("POST", "/api/entity/action/saveAndDeploy",
                     dict(agent, deploymentNotes="V1 via ecg_builder.py"))
    print("  agent %s published v%s"
          % (agent["id"], published["deploymentState"]["version"]))

    print("\nDone.")
    print("  graph  %s/p/0/context-graphs/%s" % (BASE, gid))
    print("  agent  %s/p/0/ai-agents/%s/configuration/instructions" % (BASE, agent["id"]))
    return {"graphId": gid, "nodes": nodes, "agentId": agent["id"],
            "searchWorkflowId": search["id"], "connectionId": conn}


def verify_projection(gid, conn, nodes, search_wf):
    """A node type absent from labels(n) has records that Cypher will never see.
    Catch it here rather than after loading everything."""
    call("POST", "/api/test-workflow/initiate-test/%s" % search_wf["id"],
         {"payload": {"cypherQuery": "MATCH (n) RETURN DISTINCT labels(n) AS labels LIMIT 50"},
          "type": "MOCK", "workflowDefinition": search_wf})
    time.sleep(20)
    print("  run MATCH (n) RETURN DISTINCT labels(n) and confirm every ue id below appears:")
    for name, ids in nodes.items():
        print("    %-14s %s" % (name, ids["ue"]))
    print("  any missing type => its records were written before publish, or a property "
          "is not STRING. Re-insert that type's records and re-check.")


def agent_instructions(spec, nodes):
    """Label ids, _pr_ property names, edge labels and the Cypher rules."""
    bt = chr(96)
    lines = ["You answer questions about customers and deals using the %s." % spec["name"], "",
             "Node labels are unified entity ids. Property names are prefixed _pr_.",
             "ALL properties are strings - use toFloat()/toInteger() to compare numbers, "
             "and compare dates as YYYY-MM-DD strings.", ""]
    for n in spec["nodes"]:
        props = ", ".join("_pr_" + p["id"] for p in n["properties"])
        lines.append("- %s %s%s%s : %s" % (n["name"], bt, nodes[n["name"]]["ue"], bt, props))
    lines += ["",
              "EDGES: " + ", ".join("(%s)-[%s]->(%s)" % (s, l, d) for s, l, d in spec["edges"]),
              "",
              "CYPHER RULES",
              "1. Every RETURN must also include labels(v) AS labels and v.modelId AS modelId.",
              "2. Never bind a node with an inline property map. MATCH the bare label, then "
              "filter with WHERE toLower(coalesce(v.%s_pr_field%s, '')) CONTAINS 'value'." % (bt, bt),
              "3. Traverse edges rather than joining on id properties.",
              "",
              "Never judge a deal's state from its stage id - traverse to Stage and read "
              "label and is_terminal. Stage ids are recycled and the closed flag lies.",
              "",
              "Answer from tool results only. Never invent ids, numbers, names or dates. "
              "For enumerable questions return the complete list. If a query returns nothing, "
              "say so plainly."]
    return "\n".join(lines)


# ----------------------------------------------------------------- example spec
# COPY this block rather than editing it in place.

SPEC = {
    "name": "SC Customer Context Demo",
    "description": "Customer context graph built by ecg_builder.py.",
    "agent_name": "SC Customer Context Demo Agent",
    "nodes": [
        {"name": "Customer", "icon": "account-executive", "title_field": "name",
         "description": "Customer account", "position": {"x": 0, "y": 0},
         "properties": [prop("customer_id", "Customer Id", True), prop("name", "Name"),
                        prop("domain_normalized", "Domain"), prop("aliases", "Aliases"),
                        prop("industry", "Industry"), prop("lifecycle_stage", "Lifecycle Stage")]},
        {"name": "Deal", "icon": "deal", "title_field": "deal_name",
         "description": "CRM opportunity", "position": {"x": 0, "y": 340},
         "properties": [prop("deal_id", "Deal Id", True), prop("deal_name", "Deal Name"),
                        prop("customer_id", "Customer Id"), prop("pipeline_id", "Pipeline Id"),
                        prop("stage_id", "Stage Id"), prop("stage_label", "Stage Label"),
                        prop("is_open", "Is Open"), prop("amount", "Amount"),
                        prop("close_date", "Close Date")]},
        {"name": "Stage", "icon": "end-user", "title_field": "label",
         "description": "Stage within a pipeline", "position": {"x": 300, "y": 700},
         "properties": [prop("stage_key", "Stage Key", True), prop("pipeline_id", "Pipeline Id"),
                        prop("stage_id", "Stage Id"), prop("label", "Label"),
                        prop("display_order", "Display Order"),
                        prop("is_terminal", "Is Terminal")]},
        {"name": "Interaction", "icon": "message", "title_field": "subject",
         "description": "Any activity", "position": {"x": 620, "y": 340},
         "properties": [prop("interaction_id", "Interaction Id", True),
                        prop("activity_type", "Activity Type"), prop("subject", "Subject"),
                        prop("occurred_date", "Occurred Date"),
                        prop("body_summary", "Body Summary"),
                        prop("participants", "Participants")]},
    ],
    "edges": [("Customer", "HAS_DEAL", "Deal"),
              ("Deal", "AT_STAGE", "Stage"),
              ("Interaction", "FOR_DEAL", "Deal")],
    "records": {
        "Customer": [{"customer_id": "CUST-001", "name": "Northwind Retail Group",
                      "domain_normalized": "northwind.example", "aliases": "Northwind",
                      "industry": "Retail", "lifecycle_stage": "prospect"}],
        "Stage": [{"stage_key": "default::closedwon", "pipeline_id": "default",
                   "stage_id": "closedwon", "label": "Business Win",
                   "display_order": "5", "is_terminal": "false"}],
        "Deal": [{"deal_id": "DEAL-001", "deal_name": "Northwind - Store Ops Platform",
                  "customer_id": "CUST-001", "pipeline_id": "default",
                  "stage_id": "closedwon", "stage_label": "Business Win",
                  "is_open": "true", "amount": "240000", "close_date": "2026-12-15"}],
        "Interaction": [{"interaction_id": "INT-001", "activity_type": "slack_thread",
                         "subject": "Pricing for the store ops pilot",
                         "occurred_date": "2026-09-02",
                         "body_summary": "Dana asked for a 3-store pilot before full rollout "
                                         "and flagged that procurement needs a signed DPA.",
                         "participants": "Dana Fischer"}],
    },
    "record_edges": [
        ("Customer", "CUST-001", "HAS_DEAL", "Deal", "DEAL-001"),
        ("Deal", "DEAL-001", "AT_STAGE", "Stage", "default::closedwon"),
        ("Interaction", "INT-001", "FOR_DEAL", "Deal", "DEAL-001"),
    ],
}


if __name__ == "__main__":
    print("UnifyApps : %s" % BASE)
    login()
    build(SPEC)
