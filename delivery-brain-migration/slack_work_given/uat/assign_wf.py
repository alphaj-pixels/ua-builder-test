"""Slack work assignments for FDSEs (UAT).
db_slack_conversations (raw Slack, copied from prod) -> Slack Task Assignment agent -> db_slack_assignments (one row per person per piece of work,
plus a 'checked' row per conversation) and db_task_tracker (each new assignment as a task, created_from 'Slack assignment').
Then the score writes db_fdse_slack_engagement: work given per FDSE over the last 30 days by week -> Engaged / Low / Zero."""
import sys, json, os; sys.path.insert(0, '.')
import ua, db_wf as W
import slack_eng as SE

AGENT = json.load(open("assign_agent.json"))["agent"]
F = SE.f; EPOCH = SE.EPOCH
OBJ = {"db_slack_assignments": ("Work given to FDSEs in Slack (found by the Slack Task Assignment agent): one row per person per piece of work, plus one 'checked' row per conversation read.", {
    "row_kind": F("string"), "source_id": F("string"), "account_id": F("string"), "account_name": F("string"), "channel_id": F("string"), "channel_name": F("string"),
    "message_datetime": F("string"), "message_ts": F("string"), "person_email": F("string"), "person_name": F("string"), "task": {"type": "string"}, "status": F("string"),
    "due": F("string"), "kind": F("string"), "evidence": {"type": "string"}, "slack_link": {"type": "string"}, "task_id": F("string"), "created_at": F("integer", **EPOCH)})}
ENG_FIELDS = {"assigned_30d": F("integer"), "assigned_w1": F("integer"), "assigned_w2": F("integer"), "assigned_w3": F("integer"), "assigned_w4": F("integer"),
              "weeks_assigned": F("integer"), "open_n": F("integer"), "done_n": F("integer"), "recent_work": {"type": "string"}, "last_assigned_at": F("integer", **EPOCH),
              "assigned_7d": F("integer"), "days_7d": F("integer"), "daily_7d": F("string"), "open_7d": F("integer"), "done_7d": F("integer"), "recent_7d": {"type": "string"}, "band_7d": F("string")}

def ensure_objects():
    SE.OBJECTS.update(OBJ); SE.OBJECTS.pop('db_slack_channel_activity', None)
    SE.OBJECTS["db_fdse_slack_engagement"][1].update(ENG_FIELDS)
    SE.ensure_objects()

PLAN = r"""
import java.time.*
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def norm = { v -> S(v).toLowerCase().replaceAll(/[^a-z0-9]+/, ' ').trim() }
int days = (S(binding.hasVariable('days') ? days : '') ==~ /\d+/) ? (days as int) : 30
int cap = (S(binding.hasVariable('max_batches') ? max_batches : '') ==~ /\d+/) ? (max_batches as int) : 40
def since = Instant.now().minusSeconds(days * 86400L)
def BV = { String n -> binding.hasVariable(n) ? S(binding.getVariable(n)) : '' }
int part = BV('part') ==~ /\d+/ ? (BV('part') as int) : 0
int parts = BV('parts') ==~ /\d+/ ? Math.max(1, BV('parts') as int) : 1
// roster: everyone in Sumeet Nandal's reporting tree (all roles, not just FDSEs)
def UMP = L('um').collect { it.properties ?: [:] }.findAll { S(it.emp_email).contains('@') }
def umMgr = UMP.collectEntries { [S(it.emp_email).toLowerCase(), S(it.manager_email).toLowerCase()] }
def umKids = umMgr.groupBy { k, v -> v }.collectEntries { k, v -> [k, v.keySet() as List] }
def tree = ['sumeet@unifyapps.com'] as Set; def stk = ['sumeet@unifyapps.com']
while (stk) { def x = stk.pop(); (umKids[x] ?: []).each { c -> if (tree.add(c)) stk << c } }
def roster = UMP.findAll { tree.contains(S(it.emp_email).toLowerCase()) }.unique { S(it.emp_email).toLowerCase() }
def fdse = UMP.findAll { S(it.role).toLowerCase().contains('forward deployed') }.collect { S(it.emp_email).toLowerCase() }.unique()
def rosterText = roster.collect { S(it.emp_name) + ' | ' + S(it.emp_email).toLowerCase() }.join('\n')
def A0 = L('asg').collect { it.properties ?: [:] }
def checked = A0.findAll { it.row_kind == 'checked' }.collect { S(it.source_id) } as Set     // read with the FDSE-only roster
def checked2 = A0.findAll { it.row_kind == 'checked2' }.collect { S(it.source_id) } as Set   // read with the everyone roster
def seen = [] as Set; int unreadAll = 0
def convs = L('conv').collect { it.properties ?: [:] }.findAll { c ->
  def sid = S(c.source_id); if (!sid || !seen.add(sid) || checked2.contains(sid)) return false
  def t = null; try { t = Instant.parse(S(c.message_datetime)) } catch (e) { }
  def txt = S(c.conversation_text) ?: S(c.message_text)
  def ok = t != null && t.isAfter(since) && !(c.is_bot in [true, 'true']) && (txt.contains('@') || txt.toUpperCase().contains('POC'))
  if (ok) unreadAll++
  ok && (parts <= 1 || Math.abs(sid.hashCode() % parts) == part) }   // parallel runs each take one partition
  .sort { a, b -> S(b.message_datetime) <=> S(a.message_datetime) }
def batches = []; def cur = [], curLen = 0
def flush = { if (cur) { batches << [ids: cur.collect { it.sid }, message: 'ROSTER\n' + rosterText + '\n\nCONVERSATIONS\n' + cur.collect { it.block }.join('\n')]; cur = []; curLen = 0 } }
convs.each { c ->
  def txt = S(c.conversation_text) ?: ('[' + S(c.message_datetime) + '] ' + S(c.sender_name) + ': ' + S(c.message_text))
  if (txt.length() > 3500) txt = txt.substring(0, 3500) + ' …'
  def block = '### ' + S(c.source_id) + ' | ' + S(c.account_name) + ' | ' + S(c.channel_name) + ' | ' + S(c.message_datetime).take(10) + '\n' + txt
  if (cur && (cur.size() >= 8 || curLen + block.length() > 16000)) flush()
  cur << [sid: S(c.source_id), block: block]; curLen += block.length() }
flush()
def ctx = convs.collectEntries { c -> [S(c.source_id), [account_id: S(c.account_id), account_name: S(c.account_name), channel_id: S(c.channel_id), channel_name: S(c.channel_name),
                                                     message_datetime: S(c.message_datetime), message_ts: S(c.message_ts), phase1: checked.contains(S(c.source_id)) ? 'yes' : 'no']] }
def tk = L('tasks').collect { it.properties ?: [:] }
def keys = [] as Set
tk.each { p -> def own = ((p.Owners_List instanceof List ? p.Owners_List : []) + [S(p.ownerMail)]).collect { S(it).toLowerCase() }.findAll { it }
  own.each { keys << (norm(p.account) + '|' + it + '|' + norm(p.task)) } }
def general = [:]; tk.findAll { S(it.usecasestage) == 'General' && S(it.usecaseId) }.each { general[S(it.account)] = [S(it.usecase), S(it.usecaseId)] }
return [batches: batches.take(cap), ctx: ctx, keys: keys as List, general: general, roster: roster.collectEntries { [S(it.emp_email).toLowerCase(), S(it.emp_name)] }, fdse: fdse,
        counts: [conversations_to_read: unreadAll, this_partition: convs.size(), batches_total: batches.size(), batches_this_run: Math.min(cap, batches.size())]]
"""

PARSE = r"""
import groovy.json.JsonSlurper
import java.time.*
def S = { v -> v == null ? '' : v.toString().trim() }
def norm = { v -> S(v).toLowerCase().replaceAll(/[^a-z0-9]+/, ' ').trim() }
def out = null
(binding.hasVariable('responses') && responses instanceof List ? responses : []).collect { it?.text }.findAll { it }.reverse().each { t -> if (out != null) return
  def s = t.toString().trim().replaceAll(/^```(?:json)?\s*/, '').replaceAll(/\s*```$/, ''); def i = s.indexOf('{'); def j = s.lastIndexOf('}')
  if (i >= 0 && j > i) { try { def o = new JsonSlurper().parseText(s.substring(i, j + 1)); if (o instanceof Map) out = o } catch (e) { } } }
def C = ctx instanceof Map ? ctx : [:]; def R = roster instanceof Map ? roster : [:]; def G = general instanceof Map ? general : [:]
def K = (keys instanceof List ? keys : []) as Set
def FD = ((binding.hasVariable('fdse') && fdse instanceof List) ? fdse : []).collect { S(it).toLowerCase() } as Set
int known = 0
def ids = (batch_ids instanceof List ? batch_ids : []).collect { S(it) }
def now = System.currentTimeMillis()
def rows = [], tasks = []; int dup = 0, bad = 0
def STATUS = [open: 'Not Started', in_progress: 'In Progress', done: 'Completed', blocked: 'Blocked']
def per = [:].withDefault { 0 }
((out?.items instanceof List) ? out.items : []).each { it ->
  def sid = S(it.conversation_id); def email = S(it.person_email).toLowerCase()
  if (!C[sid] || !R[email] || !S(it.task)) { bad++; return }
  if (C[sid].phase1 == 'yes' && FD.contains(email)) { known++; return }   // FDSE work in this conversation was recorded on the first read
  def c = C[sid]; def n = ++per[sid + '|' + email]
  def local = email.split('@')[0].replaceAll(/[^a-z0-9]/, '')
  def tid = 'slka_' + sid.replaceAll(/[^A-Za-z0-9]/, '_') + '_' + local + (n > 1 ? '_' + n : '')
  def parts = sid.split(':'); def link = parts.size() == 2 ? ('https://unifyapps.slack.com/archives/' + parts[0] + '/p' + parts[1].replace('.', '')) : ''
  def st = S(it.status) in STATUS ? S(it.status) : 'open'
  def due = ''; if (S(it.due) ==~ /\d{4}-\d{2}-\d{2}/) { try { due = LocalDate.parse(S(it.due)).atStartOfDay(ZoneId.of('Asia/Kolkata')).toInstant().toEpochMilli().toString() } catch (e) { } }
  def an = S(c.account_name); def key = norm(an) + '|' + email + '|' + norm(it.task)
  def isDup = K.contains(key); if (isDup) dup++ else K << key
  rows << [id: sid + '|' + email + '|' + n, payload: [row_kind: 'item', source_id: sid, account_id: c.account_id, account_name: an, channel_id: c.channel_id, channel_name: c.channel_name,
           message_datetime: c.message_datetime, message_ts: c.message_ts, person_email: email, person_name: R[email], task: S(it.task), status: st, due: S(it.due),
           kind: S(it.kind), evidence: S(it.evidence).take(300), slack_link: link, task_id: isDup ? '' : tid, created_at: now]]
  if (!isDup) {
    def g = G[an] ?: ['General Tasks ' + an, 'GeneralTasks' + an.replaceAll(/[^A-Za-z0-9]/, '')]
    tasks << [id: tid, payload: [task: S(it.task), account: an, usecase: g[0], usecaseId: g[1], usecasestage: 'General', status: STATUS[st], priority: 'Medium',
              owner: R[email], Owners_List: [email], ownerMail: email, eta: due, created_from: 'Slack assignment', source_record_id: sid, slack_link: link,
              comment: ('Assigned in Slack (#' + S(c.channel_name) + ', ' + S(c.message_datetime).take(10) + '): ' + S(it.evidence)).take(500)]] } }
def done = out ? (out.checked_ids instanceof List ? out.checked_ids : []).collect { S(it) }.unique().findAll { ids.contains(it) } : []   // only what the agent confirms it read; the rest is retried
done.each { sid -> rows << [id: 'chk2|' + sid, payload: [row_kind: 'checked2', source_id: sid, account_name: S(C[sid]?.account_name), message_datetime: S(C[sid]?.message_datetime), created_at: now]]
  if (C[sid]?.phase1 != 'yes') rows << [id: 'chk|' + sid, payload: [row_kind: 'checked', source_id: sid, account_name: S(C[sid]?.account_name), message_datetime: S(C[sid]?.message_datetime), created_at: now]] }
return [rows: rows, tasks: tasks, counts: [parsed: out != null, items: rows.count { it.payload.row_kind == 'item' }, new_tasks: tasks.size(), duplicates: dup, dropped: bad, already_recorded: known, checked: done.size()]]
"""

def lp(nid, title, src, idx, group=W.G):
    return W.node(nid, "LOOP", title, "loop", "loop_for_each", {"repeatMode": "SINGLE", "listSource": src, "captureIterations": False}, idx, group)

def extract_wf():
    it = lambda k: "{{ n_lb.outputs.item.%s }}" % k
    LB = f"n_lb@{W.G}@l"; LW = f"n_lw@{LB}@l"; LT = f"n_lt@{LB}@l"
    ROWS = {"type": "array", "items": W.ROW}
    nodes = [W.start({"max_batches": {"type": "string"}, "days": {"type": "string"}, "part": {"type": "string"}, "parts": {"type": "string"}}, []),
             SE.fetch("n_conv", "Slack conversations", "db_slack_conversations", 2), SE.fetch("n_asg", "Assignments read so far", "db_slack_assignments", 3),
             SE.fetch("n_um", "People", "db_user_management", 4), SE.fetch("n_tk", "Task tracker", "db_task_tracker", 5),
             W.groovy("n_plan", "Conversations to read, in batches", PLAN, {"conv": W.arr("n_conv.outputs.objects"), "asg": W.arr("n_asg.outputs.objects"), "um": W.arr("n_um.outputs.objects"),
                      "tasks": W.arr("n_tk.outputs.objects"), "max_batches": "{{ n_in.outputs.max_batches }}", "days": "{{ n_in.outputs.days }}", "part": "{{ n_in.outputs.part }}", "parts": "{{ n_in.outputs.parts }}"},
                      {"conv": "array", "asg": "array", "um": "array", "tasks": "array"},
                      {"batches": ROWS, "ctx": {"type": "object"}, "keys": {"type": "array", "items": {"type": "string"}}, "general": {"type": "object"}, "roster": {"type": "object"}, "fdse": {"type": "array", "items": {"type": "string"}}, "counts": {"type": "object"}}, 6),
             lp("n_lb", "For each batch", "{{ n_plan.outputs.result.batches }}", 7),
             W.invoke_agent("n_ag", "Slack Task Assignment agent", AGENT, it("message"), 8, group=LB, fallback="CONTINUE"),
             W.groovy("n_pa", "Check the agent's answer, plan writes", PARSE, {"responses": W.arr("n_ag.outputs.agentResponses"), "ctx": "{{ n_plan.outputs.result.ctx }}",
                      "roster": "{{ n_plan.outputs.result.roster }}", "general": "{{ n_plan.outputs.result.general }}", "keys": "{{ n_plan.outputs.result.keys }}", "batch_ids": it("ids"), "fdse": "{{ n_plan.outputs.result.fdse }}"},
                      {"responses": "array", "ctx": "object", "roster": "object", "general": "object", "keys": "array", "batch_ids": "array", "fdse": "array"},
                      {"rows": ROWS, "tasks": ROWS, "counts": {"type": "object"}}, 9, group=LB),
             lp("n_lw", "For each assignment row", "{{ n_pa.outputs.result.rows }}", 10, LB),
             SE.upsert("n_w", "db_slack_assignments", None, 11, group=LW, id_expr="{{ n_lw.outputs.item.id }}", row_expr="{{ n_lw.outputs.item.payload }}"),
             lp("n_lt", "For each new task", "{{ n_pa.outputs.result.tasks }}", 12, LB),
             SE.upsert("n_t", "db_task_tracker", None, 13, group=LT, id_expr="{{ n_lt.outputs.item.id }}", row_expr="{{ n_lt.outputs.item.payload }}"),
             W.stop("{{ n_plan.outputs.result.counts }}", 14)]
    E = W.e
    edges = [E("n_in", "n_conv"), E("n_conv", "n_asg"), E("n_asg", "n_um"), E("n_um", "n_tk"), E("n_tk", "n_plan"), E("n_plan", "n_lb"),
             E("n_lb", "n_ag", "loop"), E("n_ag", "n_pa"), E("n_pa", "n_lw"), E("n_lw", "n_w", "loop"), E("n_w", "n_lw", "next", name="loopback"),
             E("n_lw", "n_lt"), E("n_lt", "n_t", "loop"), E("n_t", "n_lt", "next", name="loopback"), E("n_lt", "n_lb", "next", name="loopback"), E("n_lb", "n_out")]
    return nodes, edges

if __name__ == "__main__":
    ua.ensure_session()
    a = sys.argv[1:]
    if "objects" in a: ensure_objects()
    if "extract" in a:
        nodes, edges = extract_wf()
        wid, ver, viol = W.save("DB | Slack assignments | Extract", "Reads Slack conversations not read yet (newest first, in batches), asks the Slack Task Assignment agent who was given work, records each assignment and adds new ones to the task tracker.",
                                nodes, edges, wid=SE.reg().get("slack_asg_extract"))
        SE.reg_set("slack_asg_extract", wid); print("extract:", wid, ver, viol)
        if not viol: print("  deployed", W.deploy(wid, "Slack assignments extract"))

SCORE2 = r"""
import groovy.json.JsonOutput
import java.time.*
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def ZONE = ZoneId.of('Asia/Kolkata'); def now = System.currentTimeMillis(); def nowI = Instant.ofEpochMilli(now); def since = nowI.minusSeconds(30L * 86400L)
def MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
def A = L('asg').collect { it.properties ?: [:] }
def items = [:].withDefault { [] }; int read = 0
A.each { a ->
  def t = null; try { t = Instant.parse(S(a.message_datetime)) } catch (e) { }
  if (t == null || t.isBefore(since)) return
  if (a.row_kind == 'checked') read++
  else if (a.row_kind == 'item' && S(a.person_email)) items[S(a.person_email).toLowerCase()] << (a + [t: t]) }
def prog = A.find { it.row_kind == 'progress' }
def E = L('eng').collectEntries { [S(it.id).toLowerCase(), it.properties ?: [:]] }
def people = L('um').collect { it.properties ?: [:] }.findAll { S(it.role).toLowerCase().contains('forward deployed') && S(it.emp_email).contains('@') }.collectEntries { [S(it.emp_email).toLowerCase(), it] }
def writes = []; def cnt = [:].withDefault { 0 }; int total = 0
people.each { email, u ->
  // one piece of work per source conversation + task text
  def its = items[email].unique { S(it.source_id) + '|' + S(it.task).toLowerCase() }
  total += its.size()
  def w = [0, 0, 0, 0]
  its.each { def age = (nowI.epochSecond - it.t.epochSecond) / 86400; w[age < 7 ? 3 : age < 14 ? 2 : age < 21 ? 1 : 0]++ }
  def weeks = w.count { it > 0 }
  def band = its.isEmpty() ? 'Zero' : (weeks >= 3 ? 'Engaged' : 'Low')
  cnt[band]++
  def accs = its.countBy { S(it.account_name) }.sort { -it.value }.keySet().findAll { it }.toList()
  def recent = its.sort { a, b -> b.t <=> a.t }.take(3).collect { def d = it.t.atZone(ZONE).toLocalDate(); S(it.task) + ' (' + S(it.account_name) + ', ' + d.dayOfMonth + ' ' + MON[d.monthValue] + ')' }
  def p = new LinkedHashMap(E[email] ?: [:])
  p.putAll([email: email, name: S(u.emp_name), role: S(u.role), manager_email: S(u.manager_email).toLowerCase(),
            assigned_30d: its.size(), assigned_w1: w[0], assigned_w2: w[1], assigned_w3: w[2], assigned_w4: w[3], weeks_assigned: weeks,
            open_n: its.count { S(it.status) != 'done' }, done_n: its.count { S(it.status) == 'done' }, accounts: accs.take(6).join(', '), accounts_n: accs.size(),
            recent_work: recent.join(' · '), last_assigned_at: its ? its.collect { it.t.toEpochMilli() }.max() : null, band: band, updated_at: now])
  writes << [id: email, payload: p] }
def summary = [fdse: people.size(), engaged: cnt['Engaged'], low: cnt['Low'], zero: cnt['Zero'], assignments: total, conversations_read: read,
               conversations_pending: prog ? S(prog.task) : '']
writes << [id: '__summary__', payload: [email: '__summary__', band: '__summary__', name: JsonOutput.toJson(summary), updated_at: now]]
return [writes: writes, summary: summary]
"""

def score_wf():
    LW = f"n_lw@{W.G}@l"
    nodes = [W.start({}, []),
             SE.fetch("n_asg", "Assignments", "db_slack_assignments", 2, limit=20000), SE.fetch("n_um", "People", "db_user_management", 3),
             SE.fetch("n_eng", "Engagement rows", "db_fdse_slack_engagement", 4),
             W.groovy("n_s", "Work given per FDSE (30 days)", SCORE2, {"asg": W.arr("n_asg.outputs.objects"), "um": W.arr("n_um.outputs.objects"), "eng": W.arr("n_eng.outputs.objects")},
                      {"asg": "array", "um": "array", "eng": "array"}, {"writes": {"type": "array", "items": W.ROW}, "summary": {"type": "object"}}, 5),
             lp("n_lw", "For each FDSE", "{{ n_s.outputs.result.writes }}", 6),
             SE.upsert("n_w", "db_fdse_slack_engagement", None, 7, group=LW, id_expr="{{ n_lw.outputs.item.id }}", row_expr="{{ n_lw.outputs.item.payload }}"),
             W.stop("{{ n_s.outputs.result.summary }}", 8)]
    E = W.e
    return nodes, [E("n_in", "n_asg"), E("n_asg", "n_um"), E("n_um", "n_eng"), E("n_eng", "n_s"), E("n_s", "n_lw"), E("n_lw", "n_w", "loop"), E("n_w", "n_lw", "next", name="loopback"), E("n_lw", "n_out")]

def add_progress(nodes, edges):
    """extract: after planning, save how many conversations are still to read (row_kind 'progress')."""
    n = W.node("n_prog", "ACTION", "Save progress", "storage_by_unifyapps", "storage_by_unifyapps_update_record_by_id",
               {"object_type": "db_slack_assignments", "recordId": "__progress__", "useRawPayload": True, "upsert": True, "writeThroughSessionVariables": False,
                "rawPayload": {"row_kind": "progress", "source_id": "__progress__", "task": "{{ n_plan.outputs.result.counts.conversations_to_read }}",
                               "message_datetime": "2100-01-01T00:00:00Z"}}, 6)
    nodes.append(n)
    for e in edges:
        if e["fromNodeId"] == "n_plan" and e["toNodeId"] == "n_lb": e["toNodeId"] = "n_prog"; e["id"] = "next@n_plan@n_prog"
    edges.append(W.e("n_prog", "n_lb"))
    return nodes, edges

if __name__ == "__main__" and "score" in sys.argv[1:]:
    nodes, edges = score_wf()
    wid, ver, viol = W.save("DB | FDSE | Slack engagement | Score", "Per FDSE: work given in Slack (from db_slack_assignments) over the last 30 days by week, open/done, recent work, and the band (Engaged / Low / Zero).",
                            nodes, edges, wid=SE.reg().get("slack_eng_score"))
    print("score:", wid, ver, viol, W.deploy(wid, "work given in Slack") if not viol else "")
if __name__ == "__main__" and "extract2" in sys.argv[1:]:
    nodes, edges = add_progress(*extract_wf())
    wid, ver, viol = W.save("DB | Slack assignments | Extract", "Reads Slack conversations not read yet (newest first, in batches), asks the Slack Task Assignment agent who was given work, records each assignment and adds new ones to the task tracker.",
                            nodes, edges, wid=SE.reg().get("slack_asg_extract"))
    print("extract:", wid, ver, viol, W.deploy(wid, "Slack assignments extract + progress") if not viol else "")

SCORE3 = r"""
import groovy.json.JsonOutput
import java.time.*
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def ZONE = ZoneId.of('Asia/Kolkata'); def now = System.currentTimeMillis(); def nowI = Instant.ofEpochMilli(now); def since = nowI.minusSeconds(30L * 86400L)
def MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
def DONE = ['done', 'completed', 'closed', 'archive'] as Set
def SRC = { String cf -> cf == 'Slack assignment' ? 'asg' : (cf == 'Slack' ? 'cxo' : 'tracker') }
// when the work was given: the Slack message time for Slack tasks, otherwise when the task was created
def givenAt = { Map r, Map p ->
  def m = (S(p.slack_link) =~ /\/p(\d{10})\d{6}/); if (m.find()) return Instant.ofEpochSecond(m.group(1) as long)
  def m2 = (S(p.source_record_id) =~ /:(\d{10})\./); if (S(p.created_from) == 'Slack assignment' && m2.find()) return Instant.ofEpochSecond(m2.group(1) as long)
  def c = r.createdTime ?: p.createdTime; try { return c ? Instant.ofEpochMilli(c as long) : null } catch (e) { return null } }
def items = [:].withDefault { [] }; def bySrc = [:].withDefault { 0 }
L('tasks').each { r ->
  def p = r.properties ?: [:]
  def t = givenAt(r, p); if (t == null || t.isBefore(since) || t.isAfter(nowI.plusSeconds(86400L))) return
  def owners = ((S(p.ownerMail).split(/[,;\s]+/) as List) + ((p.Owners_List instanceof List) ? p.Owners_List : [])).collect { S(it).toLowerCase() }.findAll { it.contains('@') }.unique()
  def lt = (S(p.slack_link) =~ /archives\/([A-Z0-9]+)\/p(\d{16})/); def link = lt.find() ? lt.group(1) + ':' + lt.group(2) : ''
  owners.each { o -> items[o] << [task: S(p.task) ?: S(p.usecase), account: S(p.account), status: S(p.status), done: DONE.contains(S(p.status).toLowerCase()), t: t,
                                  src: SRC(S(p.created_from)), link: link, sid: S(p.source_record_id), id: S(r.id)] } }
def A = L('asg').collect { it.properties ?: [:] }
int read = A.count { a -> def t = null; try { t = Instant.parse(S(a.message_datetime)) } catch (e) { }; a.row_kind == 'checked' && t != null && !t.isBefore(since) }
def prog = A.find { it.row_kind == 'progress' }
def E = L('eng').collectEntries { [S(it.id).toLowerCase(), it.properties ?: [:]] }
def UMP = L('um').collect { it.properties ?: [:] }.findAll { S(it.emp_email).contains('@') }
def umMgr = UMP.collectEntries { [S(it.emp_email).toLowerCase(), S(it.manager_email).toLowerCase()] }
def umKids = umMgr.groupBy { k, v -> v }.collectEntries { k, v -> [k, v.keySet() as List] }
def tree = ['sumeet@unifyapps.com'] as Set; def stk = ['sumeet@unifyapps.com']
while (stk) { def x = stk.pop(); (umKids[x] ?: []).each { c -> if (tree.add(c)) stk << c } }
def people = UMP.findAll { tree.contains(S(it.emp_email).toLowerCase()) }.collectEntries { [S(it.emp_email).toLowerCase(), it] }   // everyone in Sumeet Nandal's tree, all roles
def writes = []; def cnt = [:].withDefault { 0 }; int total = 0; def cnt7 = [:].withDefault { 0 }; int total7 = 0; def since7 = nowI.minusSeconds(7L * 86400L)
people.each { email, u ->
  def all = items[email]
  // one piece of work per Slack conversation + task text; a CXO Slack task on the same message as a Slack assignment is the same work
  def asgLinks = all.findAll { it.src == 'asg' && it.link }.collect { it.link } as Set
  def its = all.findAll { !(it.src == 'cxo' && it.link && asgLinks.contains(it.link)) }.unique { it.src == 'tracker' ? it.id : (it.link ?: it.sid) + '|' + it.task.toLowerCase() }
  total += its.size(); its.each { bySrc[it.src]++ }
  def w = [0, 0, 0, 0]
  its.each { def age = (nowI.epochSecond - it.t.epochSecond) / 86400; w[age < 7 ? 3 : age < 14 ? 2 : age < 21 ? 1 : 0]++ }
  def weeks = w.count { it > 0 }
  def band = its.isEmpty() ? 'Zero' : (weeks >= 3 ? 'Engaged' : 'Low')
  cnt[band]++
  def accs = its.countBy { it.account }.sort { -it.value }.keySet().findAll { it }.toList()
  def recent = its.sort { a, b -> b.t <=> a.t }.take(3).collect { def d = it.t.atZone(ZONE).toLocalDate(); it.task + ' (' + it.account + ', ' + d.dayOfMonth + ' ' + MON[d.monthValue] + ')' }
  // past 7 days: work per day (oldest first), days with work, band by days (3+ days engaged, 1-2 low, none zero)
  def it7 = its.findAll { !it.t.isBefore(since7) }
  def dd = [0] * 7; it7.each { int age = (int) ((nowI.epochSecond - it.t.epochSecond) / 86400); dd[6 - Math.min(6, Math.max(0, age))]++ }
  int days7 = dd.count { it > 0 }; def band7 = it7.isEmpty() ? 'Zero' : (days7 >= 3 ? 'Engaged' : 'Low'); cnt7[band7]++; total7 += it7.size()
  def recent7 = it7.sort(false) { a, b -> b.t <=> a.t }.take(3).collect { def d = it.t.atZone(ZONE).toLocalDate(); it.task + ' (' + it.account + ', ' + d.dayOfMonth + ' ' + MON[d.monthValue] + ')' }
  def p = new LinkedHashMap(E[email] ?: [:])
  p.putAll([email: email, name: S(u.emp_name), role: S(u.role), manager_email: S(u.manager_email).toLowerCase(),
            assigned_30d: its.size(), assigned_w1: w[0], assigned_w2: w[1], assigned_w3: w[2], assigned_w4: w[3], weeks_assigned: weeks,
            open_n: its.count { !it.done }, done_n: its.count { it.done }, accounts: accs.take(6).join(', '), accounts_n: accs.size(),
            recent_work: recent.join(' · '), last_assigned_at: its ? its.collect { it.t.toEpochMilli() }.max() : null, band: band, updated_at: now,
            assigned_7d: it7.size(), days_7d: days7, daily_7d: dd.join(','), open_7d: it7.count { !it.done }, done_7d: it7.count { it.done }, recent_7d: recent7.join(' · '), band_7d: band7])
  writes << [id: email, payload: p] }
def summary = [fdse: people.size(), engaged: cnt['Engaged'], low: cnt['Low'], zero: cnt['Zero'], assignments: total, conversations_read: read,
               conversations_pending: prog ? S(prog.task) : '', source: 'task_tracker', from_slack_asg: bySrc['asg'], from_slack_cxo: bySrc['cxo'], from_tracker: bySrc['tracker'],
               engaged7: cnt7['Engaged'], low7: cnt7['Low'], zero7: cnt7['Zero'], assignments7: total7]
writes << [id: '__summary__', payload: [email: '__summary__', band: '__summary__', name: JsonOutput.toJson(summary), updated_at: now]]
return [writes: writes, summary: summary]
"""

def score3_wf():
    LW = f"n_lw@{W.G}@l"
    nodes = [W.start({}, []),
             SE.fetch("n_tk", "Task tracker", "db_task_tracker", 2, limit=20000), SE.fetch("n_asg", "Slack conversations read", "db_slack_assignments", 3, limit=20000),
             SE.fetch("n_um", "People", "db_user_management", 4), SE.fetch("n_eng", "Engagement rows", "db_fdse_slack_engagement", 5),
             W.groovy("n_s", "Work given per FDSE (30 days, from the task tracker)", SCORE3, {"tasks": W.arr("n_tk.outputs.objects"), "asg": W.arr("n_asg.outputs.objects"),
                      "um": W.arr("n_um.outputs.objects"), "eng": W.arr("n_eng.outputs.objects")},
                      {"tasks": "array", "asg": "array", "um": "array", "eng": "array"}, {"writes": {"type": "array", "items": W.ROW}, "summary": {"type": "object"}}, 6),
             lp("n_lw", "For each FDSE", "{{ n_s.outputs.result.writes }}", 7),
             SE.upsert("n_w", "db_fdse_slack_engagement", None, 8, group=LW, id_expr="{{ n_lw.outputs.item.id }}", row_expr="{{ n_lw.outputs.item.payload }}"),
             W.stop("{{ n_s.outputs.result.summary }}", 9)]
    E = W.e
    return nodes, [E("n_in", "n_tk"), E("n_tk", "n_asg"), E("n_asg", "n_um"), E("n_um", "n_eng"), E("n_eng", "n_s"), E("n_s", "n_lw"), E("n_lw", "n_w", "loop"), E("n_w", "n_lw", "next", name="loopback"), E("n_lw", "n_out")]

if __name__ == "__main__" and "score3" in sys.argv[1:]:
    nodes, edges = score3_wf()
    wid, ver, viol = W.save("DB | FDSE | Slack engagement | Score", "Per FDSE: work given over the last 30 days from db_task_tracker (Slack assignment tasks, Slack CXO tasks and tasks logged in the tracker), by week, open/done from the tracker status, recent work, and the band (Engaged / Low / Zero).",
                            nodes, edges, wid=SE.reg().get("slack_eng_score"))
    print("score3:", wid, ver, viol, W.deploy(wid, "work given, from the task tracker") if not viol else "")
