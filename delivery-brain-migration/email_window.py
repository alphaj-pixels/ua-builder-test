"""Limit a workflow's email fetch (db_gmails_as_knowledge) to the past 14 days: a small step computes the cut-off, the fetch filters properties_date >= it."""
import copy
SINCE_CODE = "return [since: System.currentTimeMillis() - 14L * 86400000L]"
def apply(w, node_id, groovy_ctx):
    w = copy.deepcopy(w)
    sid = "n_since_" + node_id[2:]
    if any(n["id"] == sid for n in w["nodes"]) or any(n["id"] == "n_since" for n in w["nodes"] if node_id == "n_mail"): return w, False
    mail = [n for n in w["nodes"] if n["id"] == node_id][0]
    w["nodes"].append({"id": sid, "type": "ACTION", "title": "Emails since (14 days)", "context": copy.deepcopy(groovy_ctx), "groupId": mail.get("groupId"), "index": mail.get("index", 0),
                       "fallbackMode": "STOP", "skip": False,
                       "inputs": {"code": SINCE_CODE, "compile_static": False, "captureStdOutput": False, "parameters": {},
                                  "input": {"type": "object", "additionalProperties": False, "required": [], "properties": {}},
                                  "output": {"type": "object", "additionalProperties": False, "required": [], "properties": {"since": {"type": "integer", "title": "since"}}}}})
    tic = mail["inputs"].get("triggerInputCondition") or {}
    if not tic.get("filters"): tic = {"operator": "AND", "filters": []}
    tic["filters"].append({"property": "properties_date", "filter": {"operator": "GTE", "value": "{{ " + sid + ".outputs.result.since }}"}})
    mail["inputs"]["triggerInputCondition"] = tic
    for e in w["edges"]:
        if e["toNodeId"] == node_id and e.get("type") != "loopback": e["toNodeId"] = sid; e["id"] = f"{e['type']}@{e['fromNodeId']}@{sid}"
    w["edges"].append({"fromNodeId": sid, "toNodeId": node_id, "type": "next", "id": f"next@{sid}@{node_id}"})
    return w, True
