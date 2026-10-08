"""UAT copy of prod's raw Slack ingestion (Harshit): object db_slack_conversations + workflow 'fetch-slack-bulk-record (copy)' v87.
Same nodes, with: window from inputs (run_date, window_days; default yesterday, 1 day) instead of the hard-coded test date; UAT's Slack
connection; a 1.2 s wait before each thread-replies call (Slack rate limit on a 30-day backfill); the two voc_slack_agent calls skipped.
A daily wrapper runs it for the previous day."""
import sys, json, copy, os; sys.path.insert(0, '.')
import ua, db_wf as W
import prod_client as P

SLACK_CONN = "6abcfcdfbb9ccc4126a4cf52"   # deliverybrainslack-1, as in Harshit's workflow
REG = "db_automations.json"
def reg(): return json.load(open(REG))
def reg_set(k, v): r = reg(); r[k] = v; json.dump(r, open(REG, "w"), indent=1)

WINDOW = r"""
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZoneOffset
def S = { v -> v == null ? '' : v.toString().trim() }
def rd = S(binding.hasVariable('run_date') ? run_date : '')
def wd = S(binding.hasVariable('window_days') ? window_days : '')
LocalDate runDate = rd ==~ /\d{4}-\d{2}-\d{2}/ ? LocalDate.parse(rd) : LocalDate.now(ZoneId.of('Asia/Kolkata'))
int days = wd ==~ /\d+/ ? (wd as int) : 1
LocalDate startDay = runDate.minusDays(days)
// window = the `days` full UTC days before run_date
return [run_date: runDate.toString(), window_start_sec: Long.toString(startDay.atStartOfDay(ZoneOffset.UTC).toEpochSecond()),
        window_end_sec: Long.toString(runDate.atStartOfDay(ZoneOffset.UTC).toEpochSecond())]
"""

def ensure_object():
    src = P.call("GET", "/api/entity-type?entityType=db_slack_conversations")
    props = src["schema"]["schema"]["properties"]
    try: cur = ua.call("GET", "/api/entity-type?entityType=db_slack_conversations")
    except RuntimeError: cur = None
    if not cur:
        ua.call("POST", "/api/entity-type", {"id": "db_slack_conversations", "name": "db_slack_conversations", "pluralName": "db_slack_conversations",
                "description": src.get("description") or "DB | Slack Conversations", "metadata": {"storeDetails": {"store": "MONGO"}}, "tags": []})
        cur = ua.call("GET", "/api/entity-type?entityType=db_slack_conversations")
    S = {"type": "object", "additionalProperties": True, "required": [], "properties": props}
    cur["input"] = {"type": "SCHEMA_AND_LAYOUT", "schema": S, "layout": {"ui:order": list(props)}}
    cur["schema"] = {"dynamic": False, "type": "SCHEMA", "schema": S}
    ua.call("POST", "/api/entity-type/update", cur)
    return len(ua.call("GET", "/api/entity-type?entityType=db_slack_conversations")["schema"]["schema"]["properties"])

def fetch_wf():
    w = json.load(open("prod_fetch_slack_bulk_copy.json"))
    nodes, edges = copy.deepcopy(w["nodes"]), copy.deepcopy(w["edges"])
    N = {n["id"]: n for n in nodes}
    N["n_zADpO"]["inputs"] = {"setup": {"type": "object", "additionalProperties": False, "required": [],
                                        "properties": {"run_date": {"type": "string", "title": "run_date"}, "window_days": {"type": "string", "title": "window_days"}}}}
    win = N["n_nsyjV"]["inputs"]
    win["code"] = WINDOW
    win["input"] = {"type": "object", "additionalProperties": False, "required": [], "properties": {"run_date": {"type": "string", "title": "run_date"}, "window_days": {"type": "string", "title": "window_days"}}}
    win["parameters"] = {"run_date": "{{ n_zADpO.outputs.run_date }}", "window_days": "{{ n_zADpO.outputs.window_days }}"}
    for n in nodes:
        c = n.get("context") or {}
        if c.get("appName") == "slack":
            c["connectionId"] = SLACK_CONN
        if c.get("resourceName") == "ai_agents_by_unifyapps_invoke_agent": n["skip"] = True   # voc_slack_agent calls off in UAT
        if c.get("appName") and c.get("resourceName"):
            try: c["resourceVersion"] = W.V(c["appName"], c["resourceName"])
            except KeyError: print("  no UAT version for", c["appName"], c["resourceName"])
    N["n_Ujg7E"]["inputs"]["triggerInputCondition"] = {}   # prod test version fetched only C_303 (Alternicq); all accounts here
    N["n_Ujg7E"]["inputs"]["page"]["limit"] = 1000
    d = W.node("n_dly", "ACTION", "Wait (Slack rate limit)", "delay", "delay_for", {"duration": 1200, "unit": "MILLISECONDS"}, N["n_H9DmI"]["index"], N["n_H9DmI"]["groupId"])
    nodes.append(d)
    for e in edges:
        if e["fromNodeId"] == "n_VcJvH" and e["toNodeId"] == "n_H9DmI": e["toNodeId"] = "n_dly"; e["id"] = "loop@n_VcJvH@n_dly"
    edges.append(W.e("n_dly", "n_H9DmI"))
    return nodes, edges, w.get("settings")

def daily_wf():
    st = W.schedule_start(os.environ.get("CONV_CRON", "45 5 * * *")); st["inputs"]["timezone"] = "Asia/Kolkata"
    c = W.node("n_call", "CALL_WORKFLOW", "Fetch Slack conversations", "callables", "callables_call_automation",
               {"automationId": reg()["slack_conv_fetch"], "runtimeConnections": {}, "synchronous": True, "version": "-1",
                "parameters": {"run_date": os.environ.get("CONV_RUN_DATE", ""), "window_days": os.environ.get("CONV_DAYS", "1")}}, 2, fallback="CONTINUE")
    return [st, c, W.stop({"ok": "yes"}, 3)], [W.e("n_in", "n_call"), W.e("n_call", "n_out")]

if __name__ == "__main__":
    ua.ensure_session(); P.signin()
    a = sys.argv[1:]
    if "object" in a: print("db_slack_conversations fields:", ensure_object())
    if "fetch" in a:
        nodes, edges, settings = fetch_wf()
        wid, ver, viol = W.save("DB | Slack conversations | Fetch", "Copy of prod's fetch-slack-bulk-record (copy) v87 (Harshit): writes db_slack_conversations for each account's channels over a window. All accounts (prod's test version only fetched C_303); window from inputs; voc_slack_agent calls skipped in UAT; 1.2 s wait between thread reads.",
                                nodes, edges, wid=reg().get("slack_conv_fetch"))
        reg_set("slack_conv_fetch", wid); print("fetch:", wid, ver, viol)
        if not viol: print("  deployed", W.deploy(wid, "copy of prod fetch-slack-bulk-record (copy) v87"))
    if "daily" in a:
        nodes, edges = daily_wf()
        wid, ver, viol = W.save(os.environ.get("CONV_NAME", "DB | Slack conversations | Daily"), "Daily 05:45 IST: fetches the previous day's Slack conversations into db_slack_conversations.", nodes, edges, wid=reg().get("slack_conv_daily"))
        reg_set("slack_conv_daily", wid); print("daily:", wid, ver, viol)
        if not viol: print("  deployed", W.deploy(wid, "daily Slack conversations"))
