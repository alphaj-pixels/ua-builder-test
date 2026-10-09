"""Copy prod's Slack work-given results into UAT under the same ids (prod is the only place the agent runs).
Objects: db_slack_assignments, db_fdse_slack_engagement (incl. __summary__/__coverage__), 'Slack assignment' tasks in db_task_tracker.
Creates missing records, updates changed ones, skips identical ones; reports UAT-only ids (not deleted here)."""
import sys, json, time, concurrent.futures as CF; sys.path.insert(0, '.')
import ua, prod_client as P
ua.ensure_session(); P.signin()
def uat_fetch(obj, flt=None):
    out, off = [], 0
    while True:
        b = {"page": {"limit": 200, "offset": off}}
        if flt: b["filter"] = flt
        r = ua.call("POST", f"/api/entity/{obj}", b); out += r.get("objects") or []
        if not r.get("hasMore"): return out
        off += 200
SETS = [("db_slack_assignments", None), ("db_fdse_slack_engagement", None),
        ("db_task_tracker", {"op": "EQUAL", "field": "properties.created_from", "values": ["Slack assignment"]})]
def put(obj, prod_rec, cur):
    for i in range(5):
        try:
            if cur: ua.call("POST", "/api/entity/update", {**cur, "properties": prod_rec["properties"]})
            else: ua.call("POST", "/api/entity", {"entityType": obj, "id": prod_rec["id"], "properties": prod_rec["properties"]})
            return "ok"
        except Exception as e:
            err = str(e)
            if i == 4: return "ERR " + err[:160]
            time.sleep(2 * (i + 1))
report = {}
for obj, flt in SETS:
    pr = P.fetch(obj, flt); ur = {r["id"]: r for r in uat_fetch(obj, flt)}
    todo = [(r, ur.get(r["id"])) for r in pr if not ur.get(r["id"]) or json.dumps(ur[r["id"]]["properties"], sort_keys=True) != json.dumps(r["properties"], sort_keys=True)]
    only_uat = sorted(set(ur) - {r["id"] for r in pr})
    with CF.ThreadPoolExecutor(4) as ex: res = list(ex.map(lambda x: put(obj, *x), todo))
    errs = [x for x in res if x != "ok"]
    report[obj] = {"prod": len(pr), "uat_before": len(ur), "created": sum(1 for (r, c), x in zip(todo, res) if x == "ok" and not c), "updated": sum(1 for (r, c), x in zip(todo, res) if x == "ok" and c),
                   "unchanged": len(pr) - len(todo), "errors": len(errs), "uat_only": len(only_uat), "uat_only_sample": only_uat[:5], "err_sample": errs[:3]}
    print(obj, json.dumps(report[obj]), flush=True)
json.dump(report, open("uat_copy_report.json", "w"), indent=1)
