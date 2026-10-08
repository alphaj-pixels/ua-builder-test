"""Recreate the FDSE utilisation stack (and optionally the Slack -> task tracker flow) in a TARGET UnifyApps environment from bundle.json.

Target: --target https://<host> (or UA2_BASE_URL). Login: UA2_USERNAME / UA2_IDP_ID / UA2_PASSWORD when set, otherwise the
environment's existing UA_ login (never printed). Dry run by default: it signs in,
checks what already exists and prints the plan. Nothing is written without --apply.

  python3 migrate.py --target https://sales.prod.unifyapps.com   # dry run, group fdse
  python3 migrate.py --groups fdse,slack_sync          # include the Slack -> tracker flow
  python3 migrate.py --apply --app <interface id> [--conn google_workspace=<connection id>] [--tm-slug <task mgmt app slug>]
                     [--scope-root someone@company.com] [--nav-module <module page id>] [--reuse-existing] [--skip fdse_sync]

What --apply does, in order (idempotent: ids are kept in state_<host>.json, reruns update instead of duplicating):
  1. objects: creates missing objects with the source schema; adds missing fields to existing ones (never removes any);
     turns on record webhooks for db_user_management (needed by the new-user trigger)
  2. workflows: called workflows first; re-resolves every step's resourceVersion on the target; remaps workflow-to-workflow calls
     and connections; saves, stops on violations, deploys
  3. page: creates 'FDSE utilisation' in the target app with its data source pointed at the new data workflow
  4. nav (optional): adds the 'FDSE Utilisation' item to the given navigation module
"""
import sys, os, json, re, copy, time, argparse, http.cookiejar, urllib.request, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
B = json.load(open(os.path.join(HERE, "bundle.json")))

# ---------------------------------------------------------------- target client (own cookie jar; credentials never printed)
def _target():
    for i, x in enumerate(sys.argv):
        if x == "--target" and i + 1 < len(sys.argv): return sys.argv[i + 1]
        if x.startswith("--target="): return x.split("=", 1)[1]
    return os.environ.get("UA2_BASE_URL", "")
BASE = _target().rstrip("/")
# login for the target: UA2_* when set, otherwise the same login this environment already uses (UA_*)
CRED = {k: os.environ.get("UA2_" + k) or os.environ.get("UA_" + k) for k in ("USERNAME", "IDP_ID", "PASSWORD")}
JAR = os.path.join(HERE, ".ua2_cookies")
jar = http.cookiejar.LWPCookieJar(JAR)
if os.path.exists(JAR): jar.load(ignore_discard=True, ignore_expires=True)
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def call(method, path, body=None, timeout=90):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(), method=method,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with opener.open(req, timeout=timeout) as r: raw, status, ct = r.read(), r.status, r.headers.get("content-type", "")
    except urllib.error.HTTPError as e: raw, status, ct = e.read(), e.code, e.headers.get("content-type", "")
    except (urllib.error.URLError, OSError) as e:
        raise SystemExit(f"Cannot reach {urllib.parse.urlparse(BASE).hostname}: {getattr(e, 'reason', e)}. "
                         "If it is only reachable on the company network or VPN, run this from a machine that is on it.")
    if raw and "json" not in ct: raise RuntimeError(f"HTTP {status} non-JSON ({ct}) - not signed in?")
    out = json.loads(raw) if raw else None
    if status >= 400: raise RuntimeError(f"HTTP {status} {json.dumps(out)[:300]}")
    return out

def signin():
    if not BASE: raise SystemExit("No target: pass --target https://<host> or set UA2_BASE_URL")
    missing = [k for k, v in CRED.items() if not v]
    if missing: raise SystemExit("Missing login settings (UA2_ or UA_): " + ", ".join(missing))
    try: return call("GET", "/api/user-context?includeRoles=true")
    except RuntimeError: pass
    call("POST", "/auth/workflow/execute/node?name=emailAndPassLoginRequest", {"id": "emailAndPassLoginRequest",
         "context": {"appName": "auth_by_unifyapps", "resourceName": "auth_by_unifyapps_login"},
         "inputs": {"returnTo": "/", "failureReturnTo": BASE + "/login", "formData": {"username": CRED["USERNAME"],
                    "password": CRED["PASSWORD"], "rememberMe": True}, "identityProviderId": CRED["IDP_ID"]},
         "options": {"cacheConfig": {}}})
    jar.save(ignore_discard=True, ignore_expires=True); os.chmod(JAR, 0o600)
    return call("GET", "/api/user-context?includeRoles=true")

# ---------------------------------------------------------------- helpers
STATE_PATH = os.path.join(HERE, "state_" + (urllib.parse.urlparse(BASE).hostname or "unknown") + ".json")
state = json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {"workflows": {}, "page": None, "ds": None}
def save_state(): json.dump(state, open(STATE_PATH, "w"), indent=1)
_RV = {}
def resource_version(app, res):
    if app not in _RV:
        try: _RV[app] = {o["name"]: o["version"] for o in call("GET", f"/api/workflow-builder/node/{app}/resources")["objects"]}
        except RuntimeError: _RV[app] = {}
    return _RV[app].get(res)
def find_workflow(name):
    r = call("POST", "/api/aggregation?entityType=WorkflowDefinition&group=STANDARD", {"entityType": "WorkflowDefinition", "group": "STANDARD",
             "filter": {"op": "EQUAL", "field": "name", "values": [name]}, "sorts": [], "projections": [{"name": "id"}, {"name": "name"}], "page": {"limit": 5, "offset": 0}})
    return [o["columns"]["id"] for o in (r.get("objects") or [])]
def connections_for(app):
    r = call("POST", "/api/aggregation?entityType=Connection&group=STANDARD", {"entityType": "Connection", "group": "STANDARD",
             "filter": {"op": "AND", "values": [{"field": "appName", "op": "EQUAL", "values": [app]}, {"field": "active", "op": "EQUAL", "values": [True]}]},
             "sorts": [], "projections": [{"name": "id"}, {"name": "name"}], "page": {"limit": 20, "offset": 0}})
    return [(o["columns"]["id"], o["columns"].get("name")) for o in (r.get("objects") or [])]
def get_type(oid):
    try: return call("GET", f"/api/entity-type?entityType={oid}")
    except RuntimeError: return None
def order_workflows(keys):
    done, out = set(), []
    def visit(k):
        if k in done or k not in keys: return
        done.add(k)
        for c in B["deps"][k]["calls"]: visit(c)
        out.append(k)
    for k in keys: visit(k)
    return out

# ---------------------------------------------------------------- main
ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true"); ap.add_argument("--target"); ap.add_argument("--groups", default="fdse")
ap.add_argument("--app"); ap.add_argument("--conn", action="append", default=[]); ap.add_argument("--tm-slug")
ap.add_argument("--scope-root"); ap.add_argument("--nav-module"); ap.add_argument("--reuse-existing", action="store_true")
ap.add_argument("--skip", help="workflow keys to leave out, comma separated (as printed in [brackets]); their callers are left out too")
a = ap.parse_args()
groups = [g.strip() for g in a.groups.split(",") if g.strip()]
for g in groups:
    if g not in B["groups"]: raise SystemExit(f"unknown group {g}; choose from {list(B['groups'])}")
me = signin()
who = (me or {}).get("user", me or {})
print(f"Target: {urllib.parse.urlparse(BASE).hostname} | signed in as user {who.get('id') or who.get('userId')} | {'APPLY' if a.apply else 'DRY RUN'} | groups {groups}")
if urllib.parse.urlparse(BASE).hostname == urllib.parse.urlparse(B["source_host"]).hostname:
    print("  note: the target is the SOURCE environment" + ("; refusing to apply." if a.apply else "; dry run only."))
    if a.apply: raise SystemExit(1)
conn_map = dict(x.split("=", 1) for x in a.conn)
problems = []

# 1. objects
objects = sorted({o for g in groups for o in B["groups"][g]["objects"]})
print("\n1. Objects")
for oid in objects:
    src = B["objects"][oid]["schema"]["schema"]["properties"]; cur = get_type(oid)
    if not cur:
        print(f"  {oid}: missing -> create with {len(src)} fields")
        if a.apply:
            call("POST", "/api/entity-type", {"id": oid, "name": oid, "pluralName": oid, "description": B["objects"][oid].get("description") or "",
                 "metadata": {"storeDetails": {"store": "MONGO"}}, "tags": []})
            cur = get_type(oid)
            props = dict(src)
            S = {"type": "object", "additionalProperties": True, "required": [], "properties": props}
            cur["input"] = {"type": "SCHEMA_AND_LAYOUT", "schema": S, "layout": {"ui:order": list(props)}}
            cur["schema"] = {"dynamic": False, "type": "SCHEMA", "schema": S}
            call("POST", "/api/entity-type/update", cur)
    else:
        have = cur["schema"]["schema"]["properties"]; add = {k: v for k, v in src.items() if k not in have}
        print(f"  {oid}: exists, {len(have)} fields" + (f" -> add {len(add)}: {', '.join(list(add)[:12])}{' …' if len(add) > 12 else ''}" if add else ", nothing to add"))
        if a.apply and add:
            props = {**have, **add}
            S = {"type": "object", "additionalProperties": True, "required": cur["schema"]["schema"].get("required", []), "properties": props}
            cur["schema"]["schema"] = S
            if cur.get("input", {}).get("schema"): cur["input"]["schema"] = S; cur["input"].setdefault("layout", {}).setdefault("ui:order", list(have)); cur["input"]["layout"]["ui:order"] += [k for k in add]
            call("POST", "/api/entity-type/update", cur)
    if oid == "db_user_management" and "fdse" in groups:
        cur = get_type(oid)
        if cur and not (cur.get("metadata") or {}).get("supportsWebhook"):
            print("  db_user_management: record webhooks off -> turn on (needed by the new-user trigger)")
            if a.apply: cur.setdefault("metadata", {})["supportsWebhook"] = True; call("POST", "/api/entity-type/update", cur)

# 2. workflows
keys = order_workflows([k for g in groups for k in B["groups"][g]["workflows"]])
skip = {s.strip() for s in (a.skip or "").split(",") if s.strip()}
while True:   # skipping a workflow also skips the ones that call it
    more = {k for k in keys if k not in skip and set(B["deps"][k]["calls"]) & skip}
    if not more: break
    skip |= more
linked = {}   # same-name workflows already on the target that are left as they are
print("\n2. Workflows (called workflows first)")
for k in keys:
    w = B["workflows"][k]
    if k in skip: print(f"  [{k}] {w['name']}: skipped"); continue
    existing = state["workflows"].get(k)
    same_name = [] if existing else find_workflow(w["name"])
    if same_name and not a.reuse_existing:
        linked[k] = same_name[0]
        print(f"  [{k}] {w['name']}: already exists as {same_name[0]}, left as it is (--reuse-existing replaces it with this version)")
        continue
    if same_name: existing = same_name[0]
    nodes = copy.deepcopy(w["nodes"]); notes = []
    for n in nodes:
        ctx = n.get("context") or {}
        if ctx.get("appName") and ctx.get("resourceName"):
            v = resource_version(ctx["appName"], ctx["resourceName"])
            if v is None: problems.append(f"{w['name']}: step {n['id']} uses {ctx['appName']}/{ctx['resourceName']}, not available on the target")
            else: ctx["resourceVersion"] = v
        if ctx.get("connectionId"):
            app = ctx.get("appName"); tgt = conn_map.get(app)
            if not tgt:
                cands = connections_for(app)
                if len(cands) == 1: tgt = cands[0][0]; notes.append(f"connection {app} -> {cands[0][1]}")
                else: problems.append(f"{w['name']}: needs a {app} connection; pass --conn {app}=<id> (target has {len(cands)}: {[c[1] for c in cands][:5]})")
            if tgt: ctx["connectionId"] = tgt
        inp = n.get("inputs") or {}
        if ctx.get("resourceName") == "callables_call_automation" and inp.get("automationId"):
            ck = next((kk for kk, ww in B["workflows"].items() if ww["id"] == inp["automationId"]), None)
            if ck and (state["workflows"].get(ck) or linked.get(ck)): inp["automationId"] = state["workflows"].get(ck) or linked[ck]
            elif ck: notes.append(f"call to {B['workflows'][ck]['name']} remapped once it exists")
            else: problems.append(f"{w['name']}: calls workflow {inp['automationId']} that is not in the bundle")
        if a.scope_root and k == "fdse_page" and isinstance(inp.get("code"), str):
            inp["code"] = inp["code"].replace("sumeet@unifyapps.com", a.scope_root)
    print(f"  [{k}] {w['name']}: {('update ' + existing) if existing else 'create'}" + (f" | {'; '.join(notes)}" if notes else ""))
    if a.apply:
        if not existing:
            existing = call("POST", "/api/workflow-definition", {"name": w["name"], "description": w.get("description") or "", "tags": ["DB", "migrated"],
                "nodes": [{"id": "n_seed", "type": "START", "title": "seed", "trigger": {"type": "EVENT"}, "index": 0, "groupId": "n_seed-1", "fallbackMode": "STOP", "skip": False}], "edges": []})["id"]
        state["workflows"][k] = existing; save_state()
        cur = call("GET", f"/api/workflow-definition/{existing}")
        r = call("POST", "/api/workflow-definition/saveAndReturnViolations", {"id": existing, "name": w["name"], "description": w.get("description") or "",
                 "version": cur["version"], "standard": False, "schemaReferences": [], "settings": w.get("settings") or {}, "tags": ["DB", "migrated"],
                 "nodes": nodes, "edges": w["edges"]})
        if r.get("violations"): raise SystemExit(f"  {w['name']}: saved with violations, not deploying: {json.dumps(r['violations'])[:400]}")
        ver = call("GET", f"/api/workflow-definition/{existing}")["version"]
        call("POST", f"/api/workflow-definition/{existing}/deploy?version={ver}", {"deploymentNotes": "migrated from " + B["source_host"], "_type": "WORKFLOW_DEPLOY_OPTIONS"})
        dep = (call("GET", f"/api/workflow-definition/{existing}").get("deploymentState") or {}).get("workflowVersion")
        print(f"    saved v{ver}, deployed v{dep}")

# 3. page
if "fdse" in groups:
    print("\n3. Page 'FDSE utilisation'")
    tm = B["page_refs"]["task_mgmt_paths"]
    print(f"  access limited to: {', '.join(B['page_refs']['emails'])}")
    print(f"  Task Management links point at app slug 'task-management-application-clone'" + (f" -> '{a.tm_slug}'" if a.tm_slug else " (pass --tm-slug if the target app has another slug)"))
    if not a.app and not state.get("page"): problems.append("page: pass --app <target interface id> for the app that should hold the page")
    elif a.apply:
        app_id = a.app
        pid = state.get("page")
        if not pid:
            props = {"componentType": "PAGE", "interfaceId": app_id, "name": "FDSE utilisation", "slug": "fdse-utilisation", "publicAccess": False, "interfaceType": "application",
                     "documentTitle": "FDSE utilisation", "layout": {"body": "root_id", "header": "header_id", "footer": "footer_id"}, "blocks": {}, "pageVariables": {}, "dataSources": {},
                     "flags": {"shouldUseBuiltDependencies": True}, "eligibleOverrides": [], "inputSchema": B["page"]["properties"].get("inputSchema"),
                     "outputSchema": {"type": "SCHEMA_AND_LAYOUT", "dynamic": False}, "metadata": {"_version": 2}}
            appent = call("GET", f"/api/entity/e_interface/{app_id}")
            appent["properties"]["entityDetailsMap"] = {**(appent["properties"].get("entityDetailsMap") or {}), "NEW_ENTITY_ID": {"slug": "fdse-utilisation", "isPublic": False, "type": "PAGE", "name": "FDSE utilisation"}}
            res = call("POST", "/api/entity/create-update-or-delete/hierarchical", {"entity": {"entityType": "e_component", "properties": props}, "requestType": "CREATED",
                       "parentEntities": [{"type": "e_interface", "id": app_id}], "postUpdateEntities": [appent]})
            res = res if isinstance(res, list) else [res]
            pid = next(x["id"] for x in res if x.get("id", "").startswith("e_") and x["id"] != app_id)
            appent = call("GET", f"/api/entity/e_interface/{app_id}"); edm = appent["properties"].get("entityDetailsMap") or {}
            if "NEW_ENTITY_ID" in edm: edm[pid] = edm.pop("NEW_ENTITY_ID"); call("POST", "/api/entity/update", appent)
            state["page"] = pid; save_state()
        dsp = copy.deepcopy(B["data_source"]["properties"])
        dsp.update({"interfaceId": app_id, "interfacePageId": pid}); dsp["inputs"]["automationId"] = state["workflows"]["fdse_page"]
        if not state.get("ds"): state["ds"] = call("POST", "/api/entity", {"entityType": "e_data_source", "properties": dsp})["id"]; save_state()
        cur = call("GET", f"/api/entity/e_data_source/{state['ds']}"); call("POST", "/api/entity/update", {**cur, "properties": dsp})
        txt = json.dumps({k: B["page"]["properties"].get(k) for k in ("blocks", "pageVariables", "customCode", "metadata")})
        txt = txt.replace(B["data_source"]["id"], state["ds"]).replace(B["page"]["id"], pid)
        if a.tm_slug: txt = txt.replace("task-management-application-clone", a.tm_slug)
        parts = json.loads(txt)
        page = call("POST", "/api/entity/embedded-entities/e_component", {"entityId": pid, "allowedEntityTypes": ["e_component"]})["entity"]
        page["properties"].update(parts)
        call("POST", "/api/entity/create-update-or-delete/hierarchical", {"entity": page, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": app_id}]})
        print(f"  page {pid} with data source {state['ds']}")
    if a.nav_module and a.apply and state.get("page"):
        m = call("POST", "/api/entity/embedded-entities/e_component", {"entityId": a.nav_module, "allowedEntityTypes": ["e_component"]})["entity"]
        blocks = m["properties"]["blocks"]
        if "b_nav_fu_item" not in blocks:
            nb = json.loads(json.dumps(B["nav_blocks"]).replace(B["page"]["id"], state["page"]))
            right = next((b for b in blocks.values() if (b["component"].get("content") or {}).get("blockIds") is not None and b.get("id") == "b_nav_right"), None)
            if not right: problems.append("nav: the module has no 'b_nav_right' container; add the nav item by hand")
            else:
                blocks.update(nb); right["component"]["content"]["blockIds"].insert(len(right["component"]["content"]["blockIds"]) - 1, "b_nav_fu_item")
                nb["b_nav_fu_item"]["parentId"] = "b_nav_right"
                call("POST", "/api/entity/create-update-or-delete/hierarchical", {"entity": m, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": a.app}]})
                print("  nav item added")

print("\nNeeds attention:" if problems else "\nNo blockers found.")
for p in problems: print("  - " + p)
if not a.apply: print("\nDry run only: nothing was written.")
