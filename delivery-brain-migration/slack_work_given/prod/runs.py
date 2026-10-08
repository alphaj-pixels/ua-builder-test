"""Latest test runs of a UAT workflow, with chosen node outputs. Usage: runs.py <registry key or id> node,node [n]"""
import sys, json, time, datetime as D; sys.path.insert(0, '.')
import ua; ua.ensure_session()
def runs(wid, nodes=(), n=1):
    o = ua.call("POST", "/api/aggregation?entityType=WORKFLOW_EXECUTION&group=TEST_WORKFLOW_EXECUTION", {"entityType": "WORKFLOW_EXECUTION", "group": "TEST_WORKFLOW_EXECUTION",
        "projections": [{"name": x} for x in ("ID", "STATUS", "START_TIME", "END_TIME", "EXECUTION_TIME", "FAILED_NODES")],
        "filter": {"op": "EQUAL", "field": "WORKFLOW_ID", "values": [wid]}, "sorts": [{"field": "START_TIME", "order": "DESC"}], "page": {"limit": n, "offset": 0}}).get("objects") or []
    out = []
    for x in o:
        c = x["columns"]; rid = c["ID"]; res = {}
        if nodes:
            keys = [f"{rid}.{rid}.{k}" for k in nodes]
            lk = ua.call("POST", "/api/lookup?ByKeys=TEST_WORKFLOW_VARIABLE", {"type": "ByKeys", "lookupType": "TEST_WORKFLOW_VARIABLE", "keys": keys,
                 "options": {"startTime": c["START_TIME"] - 10000, "endTime": (c.get("END_TIME") or int(time.time() * 1000)) + 10000, "workflowId": wid}})["response"]["objects"]
            for k, key in zip(nodes, keys):
                for ent in lk.get(key, []): res.setdefault(k, {})[ent["type"]] = ent.get("payload")
        out.append({"id": rid, "status": c.get("STATUS"), "start": D.datetime.utcfromtimestamp(c["START_TIME"] / 1000).strftime("%H:%M:%S UTC"),
                    "secs": round(((c.get("END_TIME") or time.time() * 1000) - c["START_TIME"]) / 1000), "failed": c.get("FAILED_NODES"), "nodes": res})
    return out
if __name__ == "__main__":
    R = json.load(open("db_automations.json")); wid = R.get(sys.argv[1], sys.argv[1])
    for r in runs(wid, tuple(x for x in (sys.argv[2] if len(sys.argv) > 2 else "").split(",") if x), int(sys.argv[3]) if len(sys.argv) > 3 else 1):
        print(r["id"], r["status"], r["start"], f"{r['secs']}s", "failed", r["failed"])
        for k, v in r["nodes"].items(): print("  ", k, json.dumps(v)[:600])
