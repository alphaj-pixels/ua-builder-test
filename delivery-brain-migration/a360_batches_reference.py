"""Account 360 batching: every workflow call stays short (a synchronous call that runs ~15 min was dropping the nightly's 360 step).
- DB | Daily Account Report | Batches: 15 accounts per DAR | Run call, then calls itself (async) for the next batch; after the last
  batch runs Account 360 | Run with health_only=true (health for all accounts, no agents).
- DB | Account 360 | Batches: 4 non-churned accounts per Account 360 | Run call, then calls itself (async) for the next batch.
- DB | Account 360 | Weekly (all accounts): Mondays 01:00 IST, starts DB | Account 360 | Batches at batch 0.
- DB | Daily Account Report (nightly 23:00 IST): now starts DB | Daily Account Report | Batches at batch 0 (async)."""
import copy, json
DAR, A360 = "6abb9ce10682570f118cb518", "6ac4351b5523f02aa5677650"
NIGHTLY, WEEKLY_SNAPSHOT = "6abba0d5c52e534bc7ec3b37", "6abe24c58838fb5226dbd5c8"
SETTINGS = {"enableNodeLevelLogging": True, "enableRunLogging": True, "enableVariableLogging": True, "route": {"default": False, "tierName": "global"}}
PLAN = r'''
def S = { v -> v == null ? '' : v.toString().trim() }
def all = (binding.hasVariable('accs') && accs instanceof List) ? accs : []
def ids = all.findAll { r -> !ACTIVE_ONLY || S(r?.properties?.churn_flag).toLowerCase() != 'true' }.collect { S(it?.id) }.findAll { it }.unique().sort()
int b = 0
try { b = (S(binding.hasVariable('batch') ? batch : '') ?: '0') as int } catch (e) { b = 0 }
int size = SIZE
def slice = ids.drop(b * size).take(size)
boolean more = (b + 1) * size < ids.size() && b < 80
return [accounts: slice.join(','), has_more: more ? 'yes' : 'no', next: b + 1, batch: b, total: ids.size()]
'''
def _n(nid, ntype, title, ctx, inputs, idx, fb="STOP", trig=None):
    n = {"id": nid, "type": ntype, "title": title, "context": copy.deepcopy(ctx), "inputs": inputs, "groupId": "g1", "index": idx, "fallbackMode": fb, "skip": False}
    if trig: n["trigger"] = {"type": trig}
    return n
def _call(nid, title, ctx, target, params, sync, idx):
    return _n(nid, "CALL_WORKFLOW", title, ctx, {"automationId": target, "runtimeConnections": {}, "synchronous": sync, "version": "-1", "parameters": params}, idx, fb="CONTINUE")
def _e(a, b, t="next", name=None):
    e = {"fromNodeId": a, "toNodeId": b, "id": f"{t}@{a}@{b}", "priority": 0, "skip": False, "type": t}
    if name: e["name"] = name
    return e
def runner(kind, self_id, ctx):
    size, active = (15, False) if kind == "dar" else (4, True)
    code = PLAN.replace("ACTIVE_ONLY", "true" if active else "false").replace("SIZE", str(size))
    nodes = [
        _n("n_in", "START", "Trigger via automation", ctx["start"], {"setup": {"type": "object", "additionalProperties": False, "required": [], "properties": {"batch": {"type": "integer", "title": "batch"}}}}, 1, trig="CALLABLE"),
        _n("n_acc", "ACTION", "Accounts", ctx["fetch"], {"triggerInputCondition": {}, "shouldSearchInAnalyticsStore": False, "object_type": "account_db", "includeRoleMappings": False,
            "includeCurrentUserPermissions": False, "translationsOption": "DEFAULT", "page": {"paginateBy": "OFFSET", "limit": 2000, "offset": 0}, "numberOfRecordsToFetch": "MULTIPLE",
            "readThroughSessionVariables": False, "includeTotalCount": False}, 2),
        _n("n_plan", "ACTION", f"This batch ({size} accounts)", ctx["groovy"], {"code": code, "compile_static": False, "captureStdOutput": False,
            "parameters": {"batch": "{{ n_in.outputs.batch }}", "accs": {"source": "{{ n_acc.outputs.objects }}", "items": "{{ n_acc.outputs.objects[0] }}", "ua:type": "mappedArray"}},
            "input": {"type": "object", "additionalProperties": False, "required": [], "properties": {"batch": {"type": "integer", "title": "batch"},
                      "accs": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {}}, "title": "accs"}}},
            "output": {"type": "object", "additionalProperties": False, "required": [], "properties": {"accounts": {"type": "string", "title": "accounts"}, "has_more": {"type": "string", "title": "has_more"},
                       "next": {"type": "integer", "title": "next"}, "batch": {"type": "integer", "title": "batch"}, "total": {"type": "integer", "title": "total"}}}}, 3),
        _call("n_run", "Daily account reports for this batch" if kind == "dar" else "Account 360 for this batch", ctx["call"], DAR if kind == "dar" else A360,
              {"accountIds": "{{ n_plan.outputs.result.accounts }}", "dryRun": False, "reportDate": ""} if kind == "dar" else {"accounts": "{{ n_plan.outputs.result.accounts }}", "health_only": ""}, True, 4),
        _n("n_if", "IF_ELSE", "More batches?", ctx["if"], {"filters": [{"property": "{{ n_plan.outputs.result.has_more }}", "filter": {"operator": "EQUAL", "value": "yes"}}], "operator": "AND"}, 5),
        _call("n_next", "Next batch (runs on its own)", ctx["call"], self_id, {"batch": "{{ n_plan.outputs.result.next }}"}, False, 6),
        _n("n_out", "STOP", "Respond to automation", ctx["ret"], {"result": {"batch": "{{ n_plan.outputs.result.batch }}", "accounts": "{{ n_plan.outputs.result.accounts }}", "has_more": "{{ n_plan.outputs.result.has_more }}"}}, 8)]
    edges = [_e("n_in", "n_acc"), _e("n_acc", "n_plan"), _e("n_plan", "n_run"), _e("n_run", "n_if"), _e("n_if", "n_next", "if", "yes"), _e("n_next", "n_out")]
    if kind == "dar":
        nodes.insert(6, _call("n_health", "Health for all accounts (no agents)", ctx["call"], A360, {"accounts": "", "health_only": "true"}, True, 7))
        edges += [_e("n_if", "n_health", "next", "no"), _e("n_health", "n_out")]
    else:
        edges += [_e("n_if", "n_out", "next", "no")]
    return {"name": "DB | Daily Account Report | Batches" if kind == "dar" else "DB | Account 360 | Batches",
            "description": ("Nightly daily reports in batches of 15 accounts (each call short), then health for all accounts." if kind == "dar"
                            else "Account 360 (Risk Theme + Composer) in batches of 4 non-churned accounts; each batch starts the next."),
            "settings": SETTINGS, "tags": ["DB"], "nodes": nodes, "edges": edges}
def weekly(ctx, a360_batches_id, expression="0 1 * * 1"):
    nodes = [_n("n_in", "START", "Schedule", ctx["schedule"], {"cron": "EXPRESSION", "expression": expression, "timezone": "Asia/Kolkata", "sequential": True}, 1, trig="SCHEDULED"),
             _call("n_call", "Start Account 360 batches", ctx["call"], a360_batches_id, {"batch": 0}, False, 2),
             _n("n_out", "STOP", "Respond to automation", ctx["ret"], {"result": "{{ n_call.outputs }}"}, 3)]
    return {"name": "DB | Account 360 | Weekly (all accounts)", "description": "Mondays 01:00 IST: Account 360 for every non-churned account, in batches.",
            "settings": SETTINGS, "tags": ["DB"], "nodes": nodes, "edges": [_e("n_in", "n_call"), _e("n_call", "n_out")]}
def nightly(w, dar_batches_id):
    """Nightly 23:00 IST: one async call to the daily-report batches (which ends with health for all accounts)."""
    w = copy.deepcopy(w); N = {n["id"]: n for n in w["nodes"]}
    call = N["n_call"]; call["inputs"] = {**call["inputs"], "automationId": dar_batches_id, "synchronous": False, "parameters": {"batch": 0}}; call["title"] = "Start daily report batches"
    w["nodes"] = [n for n in w["nodes"] if n["id"] != "n_call2"]
    w["edges"] = [e for e in w["edges"] if "n_call2" not in (e["fromNodeId"], e["toNodeId"])] + [_e("n_call", "n_out")]
    w["edges"] = list({e["id"]: e for e in w["edges"]}.values())
    return w
