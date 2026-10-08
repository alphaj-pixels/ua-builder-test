"""FDSE Slack engagement (past 30 days), built from real Slack @-tags in the mapped account channels (slack_channel).

Objects
  db_slack_channel_activity  one row per channel (top-level messages) and per thread (replies): who was tagged / posted / replied, with message timestamps
  db_fdse_slack_engagement   one row per FDSE (id = email): Slack user id, tags in the last 30 days by week, band
Workflows
  Channel  reads one channel's last 30 days (one history call): tags in top-level messages, posts, who replied in each thread, the thread list
  Threads  reads replies of threads with new activity (throttled, capped per run): tags inside threads
  Slack ids  FDSE email -> Slack user id (throttled, cached)
  Score    per-FDSE totals and band into db_fdse_slack_engagement
  Daily / Threads catch-up   schedules
Bands: Engaged = tagged in 3+ of the last 4 weeks; Low = tagged in 1-2 weeks; Zero = never tagged; Not on Slack = no Slack account for the email.
"""
import sys, json, copy; sys.path.insert(0, '.')
import ua, db_wf as W
from db_classify import fetch_all

SLACK_CONN = "6abdf66d30617960ef094a7c"   # "slack connection for all DB": reads the account channels (checked on BigBasket)
FLAGS = {"searchable": True, "sortable": True, "filterable": True}
REG = "db_automations.json"
def reg(): return json.load(open(REG))
def reg_set(k, v): r = reg(); r[k] = v; json.dump(r, open(REG, "w"), indent=1)

def f(t, **kw): return dict({"type": t, **FLAGS}, **kw)
EPOCH = dict(format="date-time", dateFormat="epoch")
OBJECTS = {
    "db_slack_channel_activity": ("Slack activity per account channel and thread for the FDSE engagement view: who was @-tagged, posted or replied, with timestamps.", {
        "channel_id": f("string"), "channel_name": f("string"), "account_name": f("string"), "account_id": f("string"),
        "kind": f("string"), "thread_ts": f("string"), "latest_reply": f("string"), "msg_count": f("integer"),
        "per_user": {"type": "string"}, "threads": {"type": "string"}, "ok": f("string"), "error": f("string"), "run_at": f("integer", **EPOCH)}),
    "db_fdse_slack_engagement": ("FDSE engagement from Slack: @-tags in mapped account channels over the last 30 days, by week.", {
        "email": f("string"), "name": f("string"), "role": f("string"), "manager_email": f("string"), "slack_user_id": f("string"),
        "not_on_slack": f("string"), "looked_up_at": f("integer", **EPOCH),
        "tags_30d": f("integer"), "tags_w1": f("integer"), "tags_w2": f("integer"), "tags_w3": f("integer"), "tags_w4": f("integer"),
        "weeks_tagged": f("integer"), "posts_30d": f("integer"), "thread_replies_30d": f("integer"), "accounts": f("string"), "accounts_n": f("integer"),
        "last_tagged_at": f("integer", **EPOCH), "band": f("string"), "updated_at": f("integer", **EPOCH)}),
}
def ensure_objects():
    for oid, (desc, props) in OBJECTS.items():
        try: cur = ua.call("GET", f"/api/entity-type?entityType={oid}")
        except RuntimeError: cur = None
        if not cur:
            ua.call("POST", "/api/entity-type", {"id": oid, "name": oid, "pluralName": oid, "description": desc, "metadata": {"storeDetails": {"store": "MONGO"}}, "tags": []})
            cur = ua.call("GET", f"/api/entity-type?entityType={oid}")
        have = (cur.get("schema") or {}).get("schema", {}).get("properties") or {}
        props2 = {**{k: dict(v, title=k) for k, v in props.items()}, **have}
        S = {"type": "object", "additionalProperties": True, "required": [], "properties": props2}
        cur["input"] = {"type": "SCHEMA_AND_LAYOUT", "schema": S, "layout": {"ui:order": list(props2)}}
        cur["schema"] = {"dynamic": False, "type": "SCHEMA", "schema": S}
        ua.call("POST", "/api/entity-type/update", cur)
        print(oid, len(ua.call("GET", f"/api/entity-type?entityType={oid}")["schema"]["schema"]["properties"]), "fields")

HEAD = r"""
import groovy.json.JsonOutput
import groovy.json.JsonSlurper
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def SKIP = ['channel_join', 'channel_leave', 'channel_topic', 'channel_purpose', 'channel_name', 'bot_add', 'bot_remove'] as Set
def TAG = ~/<@(U[A-Z0-9]+)(?:\|[^>]*)?>/
def per = [:]
def U = { String k -> per[k] ?: (per[k] = [t: [], p: [], r: []]) }
"""
# one channel: top-level messages (tags, posts), who replied in each thread, the thread list
PARSE_CHANNEL = HEAD + r"""
def threads = []
int n = 0
L('msgs').each { m ->
  if (!(m instanceof Map)) return
  def ts = S(m.ts); if (!ts || S(m.subtype) in SKIP) return
  n++
  def a = S(m.user); if (a) U(a).p << ts
  (S(m.text) =~ TAG).collect { it[1] }.unique().findAll { it != a }.each { U(it).t << ts }
  if (((m.reply_count ?: 0) as int) > 0 && (!S(m.thread_ts) || S(m.thread_ts) == ts)) {
    threads << [ts: ts, latest: S(m.latest_reply), n: (m.reply_count as int)]
    (m.reply_users instanceof List ? m.reply_users : []).collect { S(it) }.findAll { it }.unique().each { U(it).r << ts } } }
return [id: channel_id, n: n, row: [channel_id: channel_id, channel_name: channel_name, account_name: account_name, account_id: account_id, kind: 'channel',
        thread_ts: '', latest_reply: '', msg_count: n, per_user: JsonOutput.toJson(per), threads: JsonOutput.toJson(threads),
        ok: S(binding.hasVariable('ok') ? ok : ''), error: S(binding.hasVariable('err') ? err : ''), run_at: System.currentTimeMillis()]]
"""
# one thread: tags and posts in the replies (the parent is counted with the channel); latest_reply only kept on success so a failed read is retried
PARSE_THREAD = HEAD + r"""
int n = 0
def okv = S(binding.hasVariable('ok') ? ok : '')
L('msgs').each { m ->
  if (!(m instanceof Map)) return
  def ts = S(m.ts); if (!ts || ts == S(parent_ts) || S(m.subtype) in SKIP) return
  n++
  def a = S(m.user); if (a) U(a).p << ts
  (S(m.text) =~ TAG).collect { it[1] }.unique().findAll { it != a }.each { U(it).t << ts } }
return [id: channel_id + '_' + parent_ts, n: n, row: [channel_id: channel_id, channel_name: channel_name, account_name: account_name, account_id: account_id, kind: 'thread',
        thread_ts: parent_ts, latest_reply: okv == 'true' ? S(latest) : '', msg_count: n, per_user: JsonOutput.toJson(per), threads: '',
        ok: okv, error: S(binding.hasVariable('err') ? err : ''), run_at: System.currentTimeMillis()]]
"""
# threads with replies we have not read yet (or with newer replies), newest activity first
PLAN_THREADS = r"""
import groovy.json.JsonSlurper
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def num = { v -> try { new BigDecimal(S(v) ?: '0') } catch (e) { BigDecimal.ZERO } }
def oldest = (System.currentTimeMillis() / 1000.0) - 30 * 86400
def rows = L('act').collect { it.properties ?: [:] }
def seen = rows.findAll { it.kind == 'thread' }.collectEntries { [S(it.channel_id) + '_' + S(it.thread_ts), num(it.latest_reply)] }
def all = []
rows.findAll { it.kind == 'channel' && S(it.threads) }.each { c ->
  def ts = []; try { ts = new JsonSlurper().parseText(S(c.threads)) } catch (e) { }
  ts.findAll { num(it.ts) >= oldest }.each { t -> all << [channel_id: S(c.channel_id), channel_name: S(c.channel_name), account_name: S(c.account_name), account_id: S(c.account_id),
                                                          ts: S(t.ts), latest: S(t.latest), k: S(c.channel_id) + '_' + S(t.ts)] } }
def todo = all.findAll { !seen.containsKey(it.k) || seen[it.k] < num(it.latest) }.sort { a, b -> num(b.latest) <=> num(a.latest) }
int cap = (S(binding.hasVariable('max') ? max : '') ==~ /\d+/) ? (max as int) : 400
return [todo: todo.take(cap), counts: [threads: all.size(), up_to_date: all.size() - todo.size(), to_read: todo.size(), this_run: Math.min(cap, todo.size())]]
"""
# FDSEs (role contains "forward deployed") without a Slack id looked up in the last 7 days
PLAN_IDS = r"""
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def now = System.currentTimeMillis()
def E = L('eng').collectEntries { [S(it.id).toLowerCase(), it.properties ?: [:]] }
def fdse = L('um').collect { it.properties ?: [:] }.findAll { S(it.role).toLowerCase().contains('forward deployed') && S(it.emp_email).contains('@') }.collect { S(it.emp_email).toLowerCase() }.unique()
def todo = fdse.findAll { e -> def x = E[e]; !x || (!S(x.slack_user_id) && (((x.looked_up_at ?: 0) as long) < now - 7L * 86400000L)) }
int cap = (S(binding.hasVariable('max') ? max : '') ==~ /\d+/) ? (max as int) : 400
return [todo: todo.take(cap).collect { [email: it, prev: E[it] ?: [:]] }, counts: [fdse: fdse.size(), to_look_up: todo.size()]]
"""
ID_ROW = r"""
def S = { v -> v == null ? '' : v.toString().trim() }
def p = new LinkedHashMap((binding.hasVariable('prev') && prev instanceof Map) ? prev : [:])
p.email = S(email); p.slack_user_id = S(uid); p.looked_up_at = System.currentTimeMillis()
p.not_on_slack = (S(ok) == 'true' && S(uid)) ? 'no' : (S(err) == 'users_not_found' ? 'yes' : (S(p.not_on_slack) ?: ''))
return [id: S(email), row: p]
"""
SCORE = r"""
import groovy.json.JsonSlurper
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def num = { v -> try { new BigDecimal(S(v) ?: '0') } catch (e) { BigDecimal.ZERO } }
def now = System.currentTimeMillis(); def nowS = now / 1000.0; def oldest = nowS - 30 * 86400
def tags = [:], posts = [:], reps = [:]
int chN = 0, thN = 0, thTotal = 0
L('act').collect { it.properties ?: [:] }.each { r ->
  if (r.kind == 'channel') {
    chN++
    try { thTotal += new JsonSlurper().parseText(S(r.threads) ?: '[]').count { num(it.ts) >= oldest } } catch (e) { }
  } else if (S(r.latest_reply) && num(r.thread_ts) >= oldest) thN++
  def per = [:]; try { per = new JsonSlurper().parseText(S(r.per_user) ?: '{}') } catch (e) { }
  def acc = S(r.account_name) ?: S(r.channel_name); def ch = S(r.channel_id)
  per.each { uid, v ->
    (v.t ?: []).each { ts -> def x = num(ts); if (x >= oldest) { (tags[uid] ?: (tags[uid] = [:]))[ch + '|' + ts] = [ts: x, acc: acc] } }
    (v.p ?: []).each { ts -> if (num(ts) >= oldest) posts[uid] = (posts[uid] ?: 0) + 1 }
    (v.r ?: []).each { ts -> if (num(ts) >= oldest) reps[uid] = (reps[uid] ?: 0) + 1 } } }
def E = L('eng').collectEntries { [S(it.id).toLowerCase(), it.properties ?: [:]] }
def people = L('um').collect { it.properties ?: [:] }.findAll { S(it.role).toLowerCase().contains('forward deployed') && S(it.emp_email).contains('@') }
  .collectEntries { [S(it.emp_email).toLowerCase(), it] }
def writes = []; def cnt = [:].withDefault { 0 }
people.each { email, u ->
  def prev = E[email] ?: [:]; def uid = S(prev.slack_user_id)
  def tg = uid ? (tags[uid] ?: [:]).values() : []
  def w = [0, 0, 0, 0]
  tg.each { def age = (nowS - it.ts) / 86400; w[age < 7 ? 3 : age < 14 ? 2 : age < 21 ? 1 : 0]++ }
  def weeks = w.count { it > 0 }
  def accs = tg.countBy { it.acc }.sort { -it.value }.keySet().toList()
  def band = !uid ? (S(prev.not_on_slack) == 'yes' ? 'Not on Slack' : 'Not matched') : (tg.size() == 0 ? 'Zero' : (weeks >= 3 ? 'Engaged' : 'Low'))
  cnt[band]++
  def p = new LinkedHashMap(prev)
  p.putAll([email: email, name: S(u.emp_name), role: S(u.role), manager_email: S(u.manager_email).toLowerCase(), slack_user_id: uid,
            tags_30d: tg.size(), tags_w1: w[0], tags_w2: w[1], tags_w3: w[2], tags_w4: w[3], weeks_tagged: weeks,
            posts_30d: uid ? (posts[uid] ?: 0) : 0, thread_replies_30d: uid ? (reps[uid] ?: 0) : 0,
            accounts: accs.take(6).join(', '), accounts_n: accs.size(),
            last_tagged_at: tg ? ((tg.collect { it.ts }.max() * 1000) as long) : null, band: band, updated_at: now])
  writes << [id: email, payload: p] }
def summary = [fdse: people.size(), engaged: cnt['Engaged'], low: cnt['Low'], zero: cnt['Zero'], not_on_slack: cnt['Not on Slack'],
        not_matched: cnt['Not matched'], channels: chN, threads_read: thN, threads_total: thTotal]
writes << [id: '__summary__', payload: [email: '__summary__', band: '__summary__', name: groovy.json.JsonOutput.toJson(summary), updated_at: now]]
return [writes: writes, summary: summary]
"""
PLAN_CHANNELS = r"""
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def seen = [] as Set
def ch = L('ch').collect { it.properties ?: [:] }.findAll { S(it.channel_id) && seen.add(S(it.channel_id)) }
  .collect { [channel_id: S(it.channel_id), channel_name: S(it.channel_name), account_name: S(it.account_name), account_id: S(it.account_id ?: it.acc_id)] }
return [channels: ch, oldest: ((long) (System.currentTimeMillis() / 1000) - 30L * 86400L).toString(), n: ch.size()]
"""

def slack(nid, title, res, inputs, idx, group=W.G):
    n = W.node(nid, "ACTION", title, "slack", res, inputs, idx, group, fallback="CONTINUE"); n["context"]["connectionId"] = SLACK_CONN; return n
def upsert(nid, obj, src, idx, group=W.G, id_expr=None, row_expr=None):
    return W.node(nid, "ACTION", "Save row", "storage_by_unifyapps", "storage_by_unifyapps_update_record_by_id",
                  {"object_type": obj, "recordId": id_expr or "{{ %s.outputs.result.id }}" % src, "useRawPayload": True, "upsert": True,
                   "writeThroughSessionVariables": False, "rawPayload": row_expr or "{{ %s.outputs.result.row }}" % src}, idx, group)
def loop(nid, title, src, idx): return W.node(nid, "LOOP", title, "loop", "loop_for_each", {"repeatMode": "SINGLE", "listSource": src, "captureIterations": False}, idx)
def delay(nid, ms, idx, group=W.G): return W.node(nid, "ACTION", "Wait (Slack rate limit)", "delay", "delay_for", {"duration": ms, "unit": "MILLISECONDS"}, idx, group)
def call(nid, title, key, params, idx, group=W.G):
    return W.node(nid, "CALL_WORKFLOW", title, "callables", "callables_call_automation",
                  {"automationId": reg()[key], "runtimeConnections": {}, "synchronous": True, "version": "-1", "parameters": params}, idx, group, fallback="CONTINUE")
def fetch(nid, title, obj, idx, limit=10000):
    n = fetch_all(nid, title, obj, idx); n["inputs"]["page"]["limit"] = limit; return n
ARR = {"type": "array", "items": W.ROW}
CH_IN = ("channel_id", "channel_name", "account_name", "account_id")

def wf_channel():
    I = lambda k: "{{ n_in.outputs.%s }}" % k
    nodes = [W.start({k: {"type": "string"} for k in CH_IN + ("oldest",)}, ["channel_id"]),
             slack("n_h", "Slack history (30 days)", "slack_list_conversation_history", {"channel": I("channel_id"), "oldest": I("oldest"), "limit": 999}, 2),
             W.groovy("n_g", "Who was tagged, posted, replied", PARSE_CHANNEL, dict({k: I(k) for k in CH_IN}, msgs="{{ n_h.outputs.messages }}", ok="{{ n_h.outputs.ok }}", err="{{ n_h.outputs.error }}"),
                      {"msgs": "array"}, {"id": "string", "n": "integer", "row": {"type": "object"}}, 3),
             upsert("n_w", "db_slack_channel_activity", "n_g", 4),
             W.stop({"channel": I("channel_id"), "messages": "{{ n_g.outputs.result.n }}", "ok": "{{ n_h.outputs.ok }}"}, 5)]
    return nodes, [W.e("n_in", "n_h"), W.e("n_h", "n_g"), W.e("n_g", "n_w"), W.e("n_w", "n_out")]

def wf_threads():
    it = lambda k: "{{ n_lt.outputs.item.%s }}" % k
    nodes = [W.start({"max": {"type": "string"}}, []),
             fetch("n_act", "Activity rows", "db_slack_channel_activity", 2),
             W.groovy("n_plan", "Threads to read", PLAN_THREADS, {"act": W.arr("n_act.outputs.objects"), "max": "{{ n_in.outputs.max }}"}, {"act": "array"},
                      {"todo": ARR, "counts": {"type": "object"}}, 3),
             loop("n_lt", "For each thread", "{{ n_plan.outputs.result.todo }}", 4),
             delay("n_d", 1200, 5),
             slack("n_r", "Thread replies", "slack_list_conversations_replies", {"channel": it("channel_id"), "ts": it("ts"), "limit": 300}, 6),
             W.groovy("n_g", "Who was tagged in the thread", PARSE_THREAD, dict({k: it(k) for k in CH_IN}, parent_ts=it("ts"), latest=it("latest"),
                      msgs="{{ n_r.outputs.messages }}", ok="{{ n_r.outputs.ok }}", err="{{ n_r.outputs.error }}"), {"msgs": "array"},
                      {"id": "string", "n": "integer", "row": {"type": "object"}}, 7),
             upsert("n_w", "db_slack_channel_activity", "n_g", 8),
             W.stop("{{ n_plan.outputs.result.counts }}", 9)]
    edges = [W.e("n_in", "n_act"), W.e("n_act", "n_plan"), W.e("n_plan", "n_lt"), W.e("n_lt", "n_d", "loop"), W.e("n_d", "n_r"), W.e("n_r", "n_g"), W.e("n_g", "n_w"),
             W.e("n_w", "n_lt", "next", name="loopback"), W.e("n_lt", "n_out")]
    return nodes, edges

def wf_ids():
    it = lambda k: "{{ n_li.outputs.item.%s }}" % k
    nodes = [W.start({"max": {"type": "string"}}, []),
             fetch("n_um", "User management", "db_user_management", 2), fetch("n_eng", "Engagement rows", "db_fdse_slack_engagement", 3),
             W.groovy("n_plan", "FDSEs without a Slack id", PLAN_IDS, {"um": W.arr("n_um.outputs.objects"), "eng": W.arr("n_eng.outputs.objects"), "max": "{{ n_in.outputs.max }}"},
                      {"um": "array", "eng": "array"}, {"todo": ARR, "counts": {"type": "object"}}, 4),
             loop("n_li", "For each FDSE", "{{ n_plan.outputs.result.todo }}", 5),
             delay("n_d", 1200, 6),
             slack("n_lk", "Slack user by email", "slack_get_user_info_by_email", {"email": it("email")}, 7),
             W.groovy("n_g", "Slack id row", ID_ROW, {"email": it("email"), "prev": it("prev"), "uid": "{{ n_lk.outputs.user.id }}", "ok": "{{ n_lk.outputs.ok }}", "err": "{{ n_lk.outputs.error }}"},
                      {"prev": "object"}, {"id": "string", "row": {"type": "object"}}, 8),
             upsert("n_w", "db_fdse_slack_engagement", "n_g", 9),
             W.stop("{{ n_plan.outputs.result.counts }}", 10)]
    edges = [W.e("n_in", "n_um"), W.e("n_um", "n_eng"), W.e("n_eng", "n_plan"), W.e("n_plan", "n_li"), W.e("n_li", "n_d", "loop"), W.e("n_d", "n_lk"), W.e("n_lk", "n_g"),
             W.e("n_g", "n_w"), W.e("n_w", "n_li", "next", name="loopback"), W.e("n_li", "n_out")]
    return nodes, edges

def wf_score():
    nodes = [W.start({}, []),
             fetch("n_act", "Activity rows", "db_slack_channel_activity", 2), fetch("n_um", "User management", "db_user_management", 3),
             fetch("n_eng", "Engagement rows", "db_fdse_slack_engagement", 4),
             W.groovy("n_s", "Tags per FDSE (30 days)", SCORE, {"act": W.arr("n_act.outputs.objects"), "um": W.arr("n_um.outputs.objects"), "eng": W.arr("n_eng.outputs.objects")},
                      {"act": "array", "um": "array", "eng": "array"}, {"writes": ARR, "summary": {"type": "object"}}, 5),
             loop("n_lw", "For each FDSE", "{{ n_s.outputs.result.writes }}", 6),
             upsert("n_w", "db_fdse_slack_engagement", None, 7, id_expr="{{ n_lw.outputs.item.id }}", row_expr="{{ n_lw.outputs.item.payload }}"),
             W.stop("{{ n_s.outputs.result.summary }}", 8)]
    edges = [W.e("n_in", "n_act"), W.e("n_act", "n_um"), W.e("n_um", "n_eng"), W.e("n_eng", "n_s"), W.e("n_s", "n_lw"), W.e("n_lw", "n_w", "loop"),
             W.e("n_w", "n_lw", "next", name="loopback"), W.e("n_lw", "n_out")]
    return nodes, edges

def wf_run(scheduled, threads_max="600", cron="15 4 * * *"):
    it = lambda k: "{{ n_lc.outputs.item.%s }}" % k
    st = W.schedule_start(cron) if scheduled else W.start({}, [])
    if scheduled: st["inputs"]["timezone"] = "Asia/Kolkata"
    nodes = [st, fetch("n_ch", "Account channels", "slack_channel", 2),
             W.groovy("n_plan", "Channels (unique)", PLAN_CHANNELS, {"ch": W.arr("n_ch.outputs.objects")}, {"ch": "array"}, {"channels": ARR, "oldest": "string", "n": "integer"}, 3),
             loop("n_lc", "For each channel", "{{ n_plan.outputs.result.channels }}", 4),
             call("n_c", "Read channel", "slack_eng_channel", dict({k: it(k) for k in CH_IN}, oldest="{{ n_plan.outputs.result.oldest }}"), 5),
             call("n_ids", "Slack ids", "slack_eng_ids", {"max": "400"}, 6),
             call("n_th", "Thread replies", "slack_eng_threads", {"max": threads_max}, 7),
             call("n_sc", "Score", "slack_eng_score", {}, 8),
             W.stop({"channels": "{{ n_plan.outputs.result.n }}"}, 9)]
    edges = [W.e("n_in", "n_ch"), W.e("n_ch", "n_plan"), W.e("n_plan", "n_lc"), W.e("n_lc", "n_c", "loop"), W.e("n_c", "n_lc", "next", name="loopback"),
             W.e("n_lc", "n_ids"), W.e("n_ids", "n_th"), W.e("n_th", "n_sc"), W.e("n_sc", "n_out")]
    return nodes, edges

def wf_catchup():
    st = W.schedule_start("0 */2 * * *"); st["inputs"]["timezone"] = "Asia/Kolkata"
    nodes = [st, call("n_th", "Thread replies", "slack_eng_threads", {"max": "1500"}, 2), call("n_sc", "Score", "slack_eng_score", {}, 3), W.stop({"ok": "yes"}, 4)]
    return nodes, [W.e("n_in", "n_th"), W.e("n_th", "n_sc"), W.e("n_sc", "n_out")]

DEFS = [("slack_eng_channel", "DB | FDSE | Slack engagement | Channel", "Reads one account channel's last 30 days (one history call): @-tags in top-level messages, posts, who replied in each thread.", wf_channel),
        ("slack_eng_threads", "DB | FDSE | Slack engagement | Threads", "Reads replies of threads with new activity (throttled to stay under Slack's rate limit): @-tags inside threads.", wf_threads),
        ("slack_eng_ids", "DB | FDSE | Slack engagement | Slack ids", "Looks up each FDSE's Slack user id by email (throttled, cached; re-checked weekly when not found).", wf_ids),
        ("slack_eng_score", "DB | FDSE | Slack engagement | Score", "Per FDSE: @-tags in mapped account channels over the last 30 days by week, and the band (Engaged / Low / Zero / Not on Slack).", wf_score),
        ("slack_eng_run", "DB | FDSE | Slack engagement | Run", "Runs it all: every mapped account channel, Slack ids, a batch of thread replies, then the scores.", lambda: wf_run(False)),
        ("slack_eng_daily", "DB | FDSE | Slack engagement daily", "Daily 04:15 IST: every mapped account channel, Slack ids, a batch of thread replies, then the scores.", lambda: wf_run(True, cron=__import__("os").environ.get("DAILY_CRON", "15 4 * * *"))),
        ("slack_eng_catchup", "DB | FDSE | Slack engagement | Threads every 2h", "Every 2 hours: reads more thread replies (new activity first), then re-scores.", wf_catchup)]

if __name__ == "__main__":
    ua.ensure_session()
    which = sys.argv[1:]
    if "objects" in which: ensure_objects()
    for key, name, desc, fn in DEFS:
        if which and key not in which and "all" not in which: continue
        nodes, edges = fn()
        wid, ver, viol = W.save(name, desc, nodes, edges, wid=reg().get(key))
        reg_set(key, wid); print(f"{key}: {wid} v{ver} violations={viol}")
        if not viol: print("   deployed", W.deploy(wid, desc[:120]))
