"""Export the FDSE utilisation stack (and the Slack -> task tracker flow) from the SOURCE environment (UA_* env vars) into bundle.json.
Read-only. The bundle holds object schemas, workflow definitions, the page, its data source and the nav item, plus a dependency map:
workflow-to-workflow calls, connections, object types and hard-coded emails that must be checked in the target."""
import sys, os, json, re; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
import ua
ua.ensure_session()
REG = json.load(open("db_automations.json"))
GROUPS = {
  "fdse": {"workflows": ["fdse_page", "fdse_score", "fdse_score_daily", "fdse_sync", "fdse_sync_daily", "fdse_newuser", "deleted_users"],
           "objects": ["db_fdse", "fdse_archive", "db_user_management", "deleted_user_management", "db_task_tracker"]},
  "slack_sync": {"workflows": ["slack_write", "slack_task_sync"], "objects": ["db_cxo_intelligence_slack", "db_task_tracker", "account_db", "db_account_usecase"]},
}
WF_IDS = dict(REG); WF_IDS["slack_write"] = "6aba455da3760e42b2b7b888"
FU = json.load(open("fu_page.json"))            # {"page": ..., "ds": ...}
APP = "e-69f9786e285b7c092e6d2749"; NAV_MODULE = "e_69f979151dfa014b39659988"
bundle = {"source_host": ua.BASE, "groups": GROUPS, "workflows": {}, "objects": {}, "page": None, "data_source": None, "nav_blocks": None, "deps": {}}
id2key = {v: k for k, v in WF_IDS.items()}
for g in GROUPS.values():
    for k in g["workflows"]:
        if k in bundle["workflows"]: continue
        d = ua.call("GET", f"/api/workflow-definition/{WF_IDS[k]}")
        nodes = d["nodes"]; blob = json.dumps(nodes)
        calls = sorted({(n.get("inputs") or {}).get("automationId") for n in nodes if (n.get("context") or {}).get("resourceName") == "callables_call_automation"} - {None})
        conns = sorted({(n.get("context") or {}).get("connectionId") for n in nodes if (n.get("context") or {}).get("connectionId")})
        apps = sorted({(n.get("context") or {}).get("appName") for n in nodes} - {None})
        objs = sorted({(n.get("inputs") or {}).get("object_type") for n in nodes if (n.get("inputs") or {}).get("object_type")})
        emails = sorted(set(re.findall(r"[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}", blob.lower())) - {"x@y.z"})
        bundle["workflows"][k] = {"id": WF_IDS[k], "name": d["name"], "description": d.get("description"), "nodes": nodes, "edges": d["edges"], "settings": d.get("settings"),
                                  "deployed": (d.get("deploymentState") or {}).get("workflowVersion") == d.get("version")}
        bundle["deps"][k] = {"calls": [id2key.get(c, c) for c in calls], "connections": conns, "apps": apps, "objects": objs, "emails": emails}
for g in GROUPS.values():
    for o in g["objects"]:
        if o in bundle["objects"]: continue
        bundle["objects"][o] = ua.call("GET", f"/api/entity-type?entityType={o}")
conn_info = {}
for k, dep in bundle["deps"].items():
    for c in dep["connections"]:
        if c in conn_info: continue
        try:
            r = ua.call("POST", "/api/aggregation?entityType=Connection&group=STANDARD", {"entityType": "Connection", "group": "STANDARD",
                "filter": {"op": "EQUAL", "field": "id", "values": [c]}, "sorts": [], "projections": [{"name": "id"}, {"name": "name"}, {"name": "appName"}], "page": {"limit": 1, "offset": 0}})
            col = (r.get("objects") or [{}])[0].get("columns", {}); conn_info[c] = {"name": col.get("name"), "appName": col.get("appName")}
        except Exception as e: conn_info[c] = {"error": str(e)[:80]}
bundle["connections"] = conn_info
page = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": FU["page"], "allowedEntityTypes": ["e_component"]})["entity"]
bundle["page"] = {"id": FU["page"], "properties": page["properties"]}
bundle["data_source"] = ua.call("GET", f"/api/entity/e_data_source/{FU['ds']}")
nav = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": NAV_MODULE, "allowedEntityTypes": ["e_component"]})["entity"]
bundle["nav_blocks"] = {k: v for k, v in nav["properties"]["blocks"].items() if k.startswith("b_nav_fu")}
pblob = json.dumps(bundle["page"]) + json.dumps(bundle["data_source"])
bundle["page_refs"] = {"emails": sorted(set(re.findall(r"[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}", pblob.lower()))),
                       "task_mgmt_paths": sorted(set(re.findall(r"/p/0/interfaces/[a-z0-9-]+/preview/[a-zA-Z0-9_-]*", pblob))),
                       "data_source_ids": sorted(set(re.findall(r"e_[0-9a-f]{24}", pblob)))}
json.dump(bundle, open(os.path.join(os.path.dirname(__file__), "bundle.json"), "w"), indent=1)
print("bundle written:", len(bundle["workflows"]), "workflows,", len(bundle["objects"]), "objects, page blocks", len(bundle["page"]["properties"]["blocks"]))
for k, d in bundle["deps"].items(): print(f"  {k}: {bundle['workflows'][k]['name']} | calls {d['calls']} | connections {[conn_info[c].get('appName') for c in d['connections']]} | apps {d['apps']} | emails {d['emails']}")
print("  page refs:", bundle["page_refs"])
