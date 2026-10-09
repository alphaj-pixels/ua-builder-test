"""FDSE utilisation, week-based (spec: FDSE_Utilisation_Week-Based_Scoring_Logic.pdf, 4 Oct 2026).

Utilisation % = (owned load + reviewer load) / weekly capacity x 100, over the rolling next 7 days (IST).
  status (normalised: lower-case, hyphens -> spaces, spaces collapsed):
    completed  done, completed, closed, resolved                                   -> 0
    active     in progress, pending, in review, testing, in testing, dev           -> 1
    not started  yet to start, not started, tbd, blank   (the five-status dropdown: Yet to Start / In Progress / On Hold / Blocked / Resolved)                                            -> 1
    waiting    on hold, hold, blocked, awaiting client response, client dependency, client pending -> 0.5
    anything else (one-off statuses) -> treated as active (1)
  timing share: overdue x1.25 | due within 7 days x1 | later x 7/days-until-ETA | no ETA x1
  story points: taskStoryPoints, or 1 when blank / 0
  owners split the load equally (Owners_List, else ownerMail); reviewers share 20% equally (Reviewers_List, else reviewerMail);
  someone who is owner and reviewer counts once, as owner. Matching on lower-cased trimmed email.
  capacity: db_fdse.weeklyCapacity, else 60. Bands: Overloaded >= 100, A 70-99, B 60-69, C < 60. Two decimals. No tasks -> 0%.
DB | FDSE | Utilisation (week-based) scores every db_fdse person and writes the results back (daily 06:00 IST via its schedule).
"""
import sys, json; sys.path.insert(0, '.')
import sales, ua, db_wf as W
from db_classify import fetch_all, foreach

SCORE = r"""
def ZONE = java.time.ZoneId.of('Asia/Kolkata')
def today = java.time.LocalDate.now(ZONE)
def S = { v -> v == null ? '' : v.toString().trim() }
def PAST = binding.hasVariable('window_days') && S(binding.getVariable('window_days')).toLowerCase() == 'past30'   // past 30 days: tasks assigned to the person in the last 30 days
def WIN = PAST ? 30.0 : (binding.hasVariable('window_days') && S(binding.getVariable('window_days')) ==~ /\d+/) ? new BigDecimal(S(binding.getVariable('window_days'))) : 7.0   // scoring window in days (7 = the week-based score)
def START = today.minusDays(29)   // past 30 days = today and the 29 days before
// when a task was assigned: the Slack message date for tasks from Slack, otherwise the day it was added to the tracker
def givenOf = { r, t ->
  def m = (S(t.slack_link) =~ /\/p(\d{10})\d{6}/); if (m.find()) return java.time.Instant.ofEpochSecond(m.group(1) as long).atZone(ZONE).toLocalDate()
  def m2 = (S(t.source_record_id) =~ /^[A-Z0-9]+:(\d{10})\./); if (m2.find()) return java.time.Instant.ofEpochSecond(m2.group(1) as long).atZone(ZONE).toLocalDate()
  def c = r.createdTime ?: t.createdTime; try { return c ? java.time.Instant.ofEpochMilli(c as long).atZone(ZONE).toLocalDate() : null } catch (e) { return null } }
def inPast = { r, t -> def g = givenOf(r, t); g != null && !g.isBefore(START) && !g.isAfter(today) }
def linkOf = { t -> def m = (S(t.slack_link) =~ /archives\/([A-Z0-9]+)\/p(\d{16})/); m.find() ? m.group(1) + ':' + m.group(2) : '' }
def norm = { v -> S(v).toLowerCase().replace('-', ' ').replaceAll(/\s+/, ' ').trim() }
def COMPLETED = ['done', 'completed', 'closed', 'resolved'] as Set
def ACTIVE = ['in progress', 'pending', 'in review', 'testing', 'in testing', 'dev'] as Set
def NOTSTARTED = ['yet to start', 'not started', 'tbd', '', 'none', 'null'] as Set
def WAITING = ['on hold', 'hold', 'blocked', 'awaiting client response', 'client dependency', 'client pending'] as Set
def classOf = { st -> def s = norm(st); COMPLETED.contains(s) ? 'completed' : (ACTIVE.contains(s) ? 'active' : (NOTSTARTED.contains(s) ? 'notStarted' : (WAITING.contains(s) ? 'waiting' : 'active'))) }
def WEIGHT = [completed: 0.0, active: 1.0, notStarted: 1.0, waiting: 0.5]
def MON = [jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12]
def etaOf = { v ->
  def s = S(v); if (!s) return null
  try {
    if (s ==~ /\d{12,14}/) return java.time.Instant.ofEpochMilli(Long.parseLong(s)).atZone(ZONE).toLocalDate()
    if (s ==~ /\d{4}-\d{2}-\d{2}.*/) return java.time.LocalDate.parse(s.substring(0, 10))
    def m = (s =~ /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/); if (m.matches()) return java.time.LocalDate.of(m.group(3) as int, m.group(1) as int, m.group(2) as int)
    m = (s =~ /^(\d{1,2})\s+([A-Za-z]{3})[a-z]*,?\s+(\d{4})$/); if (m.matches() && MON[m.group(2).toLowerCase()]) return java.time.LocalDate.of(m.group(3) as int, MON[m.group(2).toLowerCase()], m.group(1) as int)
  } catch (e) { }
  null }
def pointsOf = { v -> def d = 0.0; try { d = S(v) ? S(v).toBigDecimal() : 0.0 } catch (e) { d = 0.0 }; d > 0 ? d : 1.0 }
def mails = { list, single -> def xs = (list instanceof List ? list : (S(list) ? S(list).split(',') as List : [])).collect { S(it).toLowerCase() }.findAll { it && it != '-' && it.contains('@') }
  if (!xs) { def m = S(single).toLowerCase(); if (m && m != '-' && m.contains('@')) xs = [m] }
  xs.unique() }
def stats = [:].withDefault { [owned: 0.0, reviewer: 0.0, thisWeek: 0, waiting: 0, notStarted: 0, active: 0, overdue: 0, completed: 0, total: 0] }
// past 30 days: a Slack CXO task on the same Slack message as a Slack assignment for the same person is the same work, counted once
def asgOwners = [:].withDefault { [] as Set }
if (PAST) L('tasks').each { r -> def t = r.properties ?: [:]; def k = linkOf(t); if (S(t.created_from) == 'Slack assignment' && k) asgOwners[k].addAll(mails(t.Owners_List, t.ownerMail)) }
L('tasks').each { r ->
  def t = r.properties ?: [:]
  if (PAST && !inPast(r, t)) return
  def cls = classOf(t.status)
  def owners = mails(t.Owners_List, t.ownerMail)
  if (PAST && S(t.created_from) == 'Slack' && linkOf(t)) owners = owners.findAll { !asgOwners[linkOf(t)].contains(it) }
  def reviewers = mails(t.Reviewers_List, t.reviewerMail).findAll { !(it in owners) }
  if (!owners && !reviewers) return
  def eta = etaOf(t.eta); def days = eta != null ? java.time.temporal.ChronoUnit.DAYS.between(today, eta) : null
  owners.each { o -> def s = stats[o]; s.total++; if (cls == 'completed') s.completed++ else { s[cls == 'waiting' ? 'waiting' : (cls == 'notStarted' ? 'notStarted' : 'active')]++; if (days != null && days < 0) s.overdue++ } }
  if (cls == 'completed' && !PAST) return
  // forward: weighted by when it lands; past 30 days: every task assigned in the window counts in full, done ones included (waiting ×0.5)
  def share = PAST ? 1.0 : (days == null ? 1.0 : (days < 0 ? 1.25 : (days <= WIN ? 1.0 : WIN / days)))
  def load = pointsOf(t.taskStoryPoints) * share * (PAST ? (cls == 'waiting' ? 0.5 : 1.0) : WEIGHT[cls])
  owners.each { o -> stats[o].owned += load / owners.size(); stats[o].thisWeek++ }
  reviewers.each { v -> stats[v].reviewer += load * 0.2 / reviewers.size(); stats[v].thisWeek++ }
}
def r2 = { x -> (x as BigDecimal).setScale(2, java.math.RoundingMode.HALF_UP) }
def band = { p -> p >= 100 ? 'Overloaded' : (p >= 70 ? 'A' : (p >= 60 ? 'B' : 'C')) }
def scoreOf = { String email, cap ->
  def c = 60.0; try { if (S(cap) && S(cap).toBigDecimal() > 0) c = S(cap).toBigDecimal() } catch (e) { }
  def s = stats.containsKey(email) ? stats[email] : [owned: 0.0, reviewer: 0.0, thisWeek: 0, waiting: 0, notStarted: 0, active: 0, overdue: 0, completed: 0, total: 0]
  def pct = r2((s.owned + s.reviewer) / (c * WIN / 7.0) * 100)
  [ownedLoad: r2(s.owned), reviewerLoad: r2(s.reviewer), weeklyLoad: r2(s.owned + s.reviewer), weeklyCapacity: c, utilisation: pct,
   utilisationFormatted: String.format('%.2f%%', pct as double), utilisationBand: band(pct), tasksThisWeek: s.thisWeek, waitingTasks: s.waiting,
   notStarted: s.notStarted, InProgress: s.active, Active: s.active + s.waiting + s.notStarted, overdue: s.overdue, Completed: s.completed, totalTasks: s.total] }
"""

PLAN = r"""
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) ? binding.getVariable(n) : [] }
""" + SCORE + r"""
def now = System.currentTimeMillis()
def writes = L('fd').findAll { S(it.properties?.mail_id) }.collect { r -> def p = new LinkedHashMap(r.properties ?: [:])
  p.putAll(scoreOf(S(p.mail_id).toLowerCase(), p.weeklyCapacity)); p.utilisationUpdatedAt = now; [id: r.id, payload: p] }
def pcts = writes.collect { it.payload.utilisation as BigDecimal }
return [writes: writes, summary: [people: writes.size(), withTasks: writes.count { (it.payload.tasksThisWeek ?: 0) > 0 },
        teamAverage: pcts ? r2(pcts.sum() / pcts.size()) : 0, overloaded: writes.count { it.payload.utilisationBand == 'Overloaded' },
        A: writes.count { it.payload.utilisationBand == 'A' }, B: writes.count { it.payload.utilisationBand == 'B' }, C: writes.count { it.payload.utilisationBand == 'C' }, runDate: today.toString()]]
"""

NAME = "DB | FDSE | Utilisation (week-based)"

def definition():
    fd, tk = fetch_all("n_fd", "FDSE rows", "db_fdse", 2), fetch_all("n_tk", "Tasks", "db_task_tracker", 3)
    fd["inputs"]["page"]["limit"] = tk["inputs"]["page"]["limit"] = 10000
    plan = W.groovy("n_score", "Score everyone (week-based)", PLAN, {"fd": W.arr("n_fd.outputs.objects"), "tasks": W.arr("n_tk.outputs.objects")},
                    {"fd": "array", "tasks": "array"}, {"writes": {"type": "array", "items": W.ROW}, "summary": "object"}, 4)
    loop = foreach("n_each", "For each person", "n_score.outputs.result.writes", 5)
    up = W.node("n_up", "ACTION", "Write utilisation", "storage_by_unifyapps", "storage_by_unifyapps_update_record_by_id",
                {"object_type": "db_fdse", "recordId": "{{ n_each.outputs.item.id }}", "useRawPayload": True, "upsert": False,
                 "writeThroughSessionVariables": False, "rawPayload": "{{ n_each.outputs.item.payload }}"}, 6, f"n_each@{W.G}@l")
    nodes = [W.start({}, []), fd, tk, plan, loop, up, W.stop("{{ n_score.outputs.result.summary }}", 7)]
    edges = [W.e("n_in", "n_fd"), W.e("n_fd", "n_tk"), W.e("n_tk", "n_score"), W.e("n_score", "n_each"), W.e("n_each", "n_up", "loop"),
             W.e("n_up", "n_each", "next", "loopback"), W.e("n_each", "n_out")]
    return nodes, edges

def schedule(reg, target):
    stn = W.node("n_in", "START", "Schedule", "schedule", "schedule_default", {"cron": "EXPRESSION", "expression": "0 6 * * *", "timezone": "Asia/Kolkata", "sequential": True}, 1, ctype=False)
    stn["trigger"] = {"type": "SCHEDULED"}
    call = W.node("n_call", "CALL_WORKFLOW", "Score everyone", "callables", "callables_call_automation",
                  {"automationId": target, "version": "-1", "synchronous": True, "runtimeConnections": {}, "parameters": {}}, 2)
    return W.save("DB | FDSE | Utilisation daily", "Daily 06:00 IST (after the people sync): week-based utilisation for everyone in db_fdse.",
                  [stn, call, W.stop("{{ n_call.outputs }}", 3)], [W.e("n_in", "n_call"), W.e("n_call", "n_out")], reg.get("fdse_score_daily"), tags=("DB", "FDSE"))

if __name__ == "__main__":
    ua.ensure_session()
    reg = json.load(open("db_automations.json"))
    nodes, edges = definition()
    wid, ver, viol = W.save(NAME, "Week-based FDSE utilisation (rolling next 7 days, ETA proximity x status weight, owner/reviewer split) for everyone in db_fdse.",
                            nodes, edges, reg.get("fdse_score"), tags=("DB", "FDSE"))
    reg["fdse_score"] = wid; json.dump(reg, open("db_automations.json", "w"), indent=1)
    print("saved", wid, ver, viol)
    if "--deploy" in sys.argv:
        print("deployed", W.deploy(wid, "week-based utilisation v1"))
        sw, sv, sviol = schedule(reg, wid); reg["fdse_score_daily"] = sw; json.dump(reg, open("db_automations.json", "w"), indent=1)
        print("schedule", sw, sviol, W.deploy(sw, "daily 06:00 IST"))
