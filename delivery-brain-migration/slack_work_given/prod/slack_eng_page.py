"""Data for the FDSE page's 'Slack engagement' view: DB | FDSE Slack Engagement Page | Data -> {eng: {...}}.
Same scoping as the utilisation view: admins land on Sumeet Nandal's whole team, everyone else on their own; 'View team' (var_fumgr) drills down."""
import sys, json; sys.path.insert(0, '.')
import ua, db_wf as W
from db_classify import fetch_all
import slack_eng as SE

VIEW = r"""
import groovy.json.JsonSlurper
import java.time.*
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def N = { v -> try { (S(v) ?: '0') as int } catch (e) { 0 } }
def ZONE = ZoneId.of('Asia/Kolkata'); def today = LocalDate.now(ZONE)
def MON = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
def fmt = { LocalDate d -> d.dayOfMonth + ' ' + MON[d.monthValue] }
def rng = { LocalDate a, LocalDate b -> a.monthValue == b.monthValue ? (a.dayOfMonth + '–' + fmt(b)) : (fmt(a) + ' – ' + fmt(b)) }
def me = S(binding.hasVariable('viewer') ? viewer : '').toLowerCase()
def isAdmin = S(binding.hasVariable('admin') ? admin : '').toLowerCase() == 'true'
def ROOT = 'sumeet@unifyapps.com'
def UM = L('um').collect { it.properties ?: [:] }.findAll { S(it.emp_email).contains('@') }
def mgr = UM.collectEntries { [S(it.emp_email).toLowerCase(), S(it.manager_email).toLowerCase()] }
def nameOf = UM.collectEntries { [S(it.emp_email).toLowerCase(), S(it.emp_name)] }
def roleOf = UM.collectEntries { [S(it.emp_email).toLowerCase(), S(it.role)] }
def kids = mgr.groupBy { k, v -> v }.collectEntries { k, v -> [k, v.keySet() as List] }
def descMemo = [:]
def desc = { String m -> descMemo[m] ?: (descMemo[m] = { def out = [] as LinkedHashSet; def st = [m]; while (st) { def x = st.pop(); (kids[x] ?: []).each { c -> if (out.add(c)) st << c } }; out }()) }
def SCOPE_TEAMS = ['shivam@unifyapps.com', 'sandeep.sharma@unifyapps.com']   // for now: only Shivam Satrawal's and Sandeep Sharma's teams (product and project management)
def inRoot = ([ROOT] + SCOPE_TEAMS + SCOPE_TEAMS.collectMany { desc(it) as List }) as Set
def top = isAdmin ? ROOT : me
def want = S(binding.hasVariable('focus') ? focus : '').toLowerCase()
def allowed = { String m -> m && inRoot.contains(m) && (isAdmin || m == me || desc(me).contains(m)) }
def F = (want && allowed(want)) ? want : top
def crumbs = []; def cur = F; int g = 0
while (cur && g++ < 12) { crumbs.add(0, cur); if (cur == top) break; def up = mgr[cur]; if (!up || !allowed(up)) break; cur = up }
def E = L('eng').collect { it.properties ?: [:] }.findAll { S(it.email) }.collectEntries { [S(it.email).toLowerCase(), it] }
def sum = [:]; try { sum = new JsonSlurper().parseText(S(E['__summary__']?.name) ?: '{}') } catch (e) { }
def updated = (E['__summary__']?.updated_at ?: 0) as long
def scope = desc(F).findAll { inRoot.contains(it) && E.containsKey(it) && !it.startsWith('__') }
def BK = ['Engaged': 'engaged', 'Low': 'low', 'Zero': 'zero']
def TONE = [engaged: 'G', low: 'A', zero: 'R', none: 'X']
def ago = { long ms -> if (!ms) return '—'; def d = (int) ((System.currentTimeMillis() - ms) / 86400000L); d <= 0 ? 'today' : (d == 1 ? 'yesterday' : d + ' days ago') }
def people = scope.collect { e -> def r = E[e]; def bk = BK[S(r.band)] ?: 'none'
  [band_key: bk, band_tone: TONE[bk], name: S(r.name) ?: (nameOf[e] ?: e), email: e, designation: S(r.role) ?: (roleOf[e] ?: ''), leader: nameOf[mgr[e]] ?: '–',
   manager_email: mgr[e] ?: '', w1: N(r.assigned_w1).toString(), w2: N(r.assigned_w2).toString(), w3: N(r.assigned_w3).toString(), w4: N(r.assigned_w4).toString(),
   w1t: N(r.assigned_w1) > 0 ? 'on' : 'off', w2t: N(r.assigned_w2) > 0 ? 'on' : 'off', w3t: N(r.assigned_w3) > 0 ? 'on' : 'off', w4t: N(r.assigned_w4) > 0 ? 'on' : 'off',
   given: N(r.assigned_30d).toString(), open: N(r.open_n).toString(), done: N(r.done_n).toString(), accounts: S(r.accounts) ?: '–', recent: S(r.recent_work) ?: '–',
   last: ago((r.last_assigned_at ?: 0) as long), has_team: kids[e] ? 'yes' : 'no', note: ''] }
def BO = [zero: 0, low: 1, engaged: 2, none: 3]
def ORD = { a, b -> ((BO[a.band_key] ?: 9) <=> (BO[b.band_key] ?: 9)) ?: (a.band_key == 'zero' ? ((S(a.leader) <=> S(b.leader)) ?: (S(a.name) <=> S(b.name))) : ((N(b.given) <=> N(a.given)) ?: (S(a.name) <=> S(b.name)))) }   // band first, so the order is consistent
people = people.sort(false, ORD)
def cnt = people.countBy { it.band_key }
def n = people.size()
def fname = nameOf[F] ?: F
def fd = { int k -> k == 1 ? '1 person' : (k + ' people') }
def tabs = [[id: 'zero', l: 'Zero engagement', n: (cnt['zero'] ?: 0).toString(), tone: 'R'], [id: 'low', l: 'Low', n: (cnt['low'] ?: 0).toString(), tone: 'A'],
            [id: 'engaged', l: 'Engaged', n: (cnt['engaged'] ?: 0).toString(), tone: 'G']]
def pct = { int a, int b -> b ? Math.round(a * 100.0 / b) + '%' : '0%' }
def weeks = [[today.minusDays(29), today.minusDays(21)], [today.minusDays(20), today.minusDays(14)], [today.minusDays(13), today.minusDays(7)], [today.minusDays(6), today]].collect { [l: rng(it[0], it[1])] }
def leaders = (kids[F] ?: []).findAll { d -> desc(d).any { scope.contains(it) } }.collect { d ->
  def team = desc(d).findAll { scope.contains(it) }; def tp = people.findAll { team.contains(it.email) }; def c = tp.countBy { it.band_key }
  def on = tp.size(); def z = c['zero'] ?: 0; def share = on ? z * 100.0 / on : 0
  [name: nameOf[d] ?: d, email: d, designation: roleOf[d] ?: '', team_n: tp.size().toString(), engaged_n: (c['engaged'] ?: 0).toString(), low_n: (c['low'] ?: 0).toString(),
   zero_n: z.toString(), zero_s: pct(z, on), status: share >= 40 ? 'R' : (share >= 20 ? 'A' : 'G'), sk: share] }
  .sort { a, b -> (b.sk <=> a.sk) ?: (a.name <=> b.name) }.collect { it.findAll { k, v -> k != 'sk' } }
def rd = N(sum.conversations_read); def pend = N(sum.conversations_pending); def tot = N(sum.assignments)
def fromAsg = N(sum.from_slack_asg); def fromCxo = N(sum.from_slack_cxo); def fromTrk = N(sum.from_tracker)
def win = rng(today.minusDays(29), today)
// scatter: one dot per person. Across: work given in the past 30 days (0 to 50+). Up: weeks with work given (1 to 4). No work given sits in its own lane.
def jit = { String m, int salt -> def rnd = new Random(m.hashCode() * 1000003L + salt * 7919L); rnd.nextInt(50); rnd.nextDouble() * 2 - 1 }
def clamp = { double x -> Math.max(0, Math.min(100, Math.round(x) as int)) }
def WY = [1: 12.5, 2: 37.5, 3: 62.5, 4: 87.5]
def scatter = people.collect { p -> int gv = N(p.given); int wk = [p.w1, p.w2, p.w3, p.w4].count { N(it) > 0 }; def lane = gv == 0
  def sx = lane ? 10 + Math.abs(jit(p.email, 1)) * 80 : Math.min(gv, 50) / 50.0 * 100 + jit(p.email, 3) * 1.2
  def sy = lane ? 3 + Math.abs(jit(p.email, 2)) * 94 : (WY[wk] ?: 12.5) + jit(p.email, 4) * 9
  [id: p.email, lane: lane ? 'yes' : 'no', tone: TONE[p.band_key] ?: 'X', sx: clamp(sx), sy: clamp(sy),
   tip: p.name + ' · ' + gv + ' given · ' + wk + (wk == 1 ? ' week' : ' weeks') + ' · ' + p.leader] }
// Slack coverage card (from the daily DB | Slack coverage run)
def cov = [:]; try { cov = new JsonSlurper().parseText(S(E['__coverage__']?.recent_work) ?: '{}') } catch (e) { }
def NC = (cov.no_channel instanceof List) ? cov.no_channel : []; def QC = (cov.quiet instanceof List) ? cov.quiet : []
def ncA = NC.findAll { S(it.status) == 'active' }; def ncN = NC.findAll { S(it.status) != 'active' }
def covUpd = cov.updated_at ? Instant.ofEpochMilli(cov.updated_at as long).atZone(ZONE).toLocalDate() : null
def covCard = [has: cov ? 'yes' : 'no', nc_n: NC.size().toString(), accounts: N(cov.accounts).toString(), nc_active_n: ncA.size().toString(), nc_ns_n: ncN.size().toString(),
  nc_active: ncA.collect { S(it.name) }.join(' · ') ?: 'None', nc_ns: ncN.collect { S(it.name) }.join(' · ') ?: 'None',
  q_n: QC.size().toString(), channels: N(cov.channels).toString(), quiet: QC.collect { '#' + S(it.channel) + (S(it.account) ? ' (' + S(it.account) + ')' : ' (no account)') }.join(' · ') ?: 'None',
  updated: covUpd ? 'Updated ' + fmt(covUpd) + '.' : '']
def shortL = { List xs, int k -> xs.size() <= k ? (xs.join(' · ') ?: 'None') : (xs.take(k).join(' · ') + ' … and ' + (xs.size() - k) + ' more') }
covCard.nc_active_s = shortL(ncA.collect { S(it.name) }, 12); covCard.nc_ns_s = shortL(ncN.collect { S(it.name) }, 8)
covCard.quiet_s = shortL(QC.collect { '#' + S(it.channel) + (S(it.account) ? ' (' + S(it.account) + ')' : ' (no account)') }, 14)
covCard.more = (ncA.size() > 12 || ncN.size() > 8 || QC.size() > 14) ? 'yes' : 'no'
def upd = updated ? Instant.ofEpochMilli(updated).atZone(ZONE) : null
def leadTxt = n == 0 ? ('No FDSEs report into ' + fname + '.') : ((cnt['zero'] ?: 0) + ' of ' + fd(n) + ' in ' + fname + "'s team " + ((cnt['zero'] ?: 0) == 1 ? 'was' : 'were') + ' given no work in the past 30 days.')
if (rd == 0 && tot == 0) leadTxt = 'Still reading Slack conversations for work given to people. Check back in an hour.'
else if (pend > 0) leadTxt = 'So far, ' + leadTxt.substring(0, 1).toLowerCase() + leadTxt.substring(1)
def eng = [asof: 'Slack engagement, past 30 days ' + win + '. ' + fd(n) + ' in ' + fname + "'s team" + (upd ? ' · updated ' + fmt(upd.toLocalDate()) + ' ' + String.format('%02d:%02d', upd.hour, upd.minute) : ''),
  label: 'Slack engagement · past 30 days · ' + fname + "'s team",
  lead: leadTxt,
  rest: n == 0 ? '' : ((cnt['engaged'] ?: 0) + ' were given work in 3 or 4 of the last 4 weeks, and ' + (cnt['low'] ?: 0) + ' in only 1 or 2 weeks.'),
  coverage: S(sum.source) == 'task_tracker' ? ('From the task tracker: ' + tot + " tasks given to people in Sumeet Nandal's tree in the past 30 days, " + fromAsg + ' found in Slack conversations by the Slack Task Assignment agent, ' + fromCxo + ' from Slack CXO records and ' + (fromTrk ? fromTrk + ' logged directly in the tracker.' : 'none logged directly in the tracker.') + ' ' + rd + ' Slack conversations read.' + (pend ? ' ' + pend + ' more are still being read, so counts will rise.' : ''))
    : ('Read from ' + rd + ' Slack conversations in mapped account channels: ' + tot + ' pieces of work given to FDSEs.' + (pend ? ' ' + pend + ' more conversations are still being read (newest first), so counts will rise.' : '')),
  has_data: updated ? 'yes' : 'no', tabs: tabs, people: people, weeks: weeks, leaders: leaders, has_leaders: leaders ? 'yes' : 'no',
  no_leaders: 'Nobody reporting to ' + fname + ' leads a team.',
  scatter: scatter, lane_n: (cnt['zero'] ?: 0).toString(), cov: covCard]
return [eng: eng, tier: [crumbs: crumbs.withIndex().collect { m, i -> [id: 'c' + i, email: m, name: nameOf[m] ?: m, last: i == crumbs.size() - 1 ? 'yes' : 'no'] }, focus: [email: F, name: fname]]]
"""

def wf():
    P = {k: {"type": "string"} for k in ("viewer", "admin", "focus")}
    nodes = [W.start(P, []),
             SE.fetch("n_um", "People", "db_user_management", 2), SE.fetch("n_eng", "Engagement rows", "db_fdse_slack_engagement", 3),
             W.groovy("n_view", "Engagement view", VIEW, {"um": W.arr("n_um.outputs.objects"), "eng": W.arr("n_eng.outputs.objects"),
                      "viewer": "{{ n_in.outputs.viewer }}", "admin": "{{ n_in.outputs.admin }}", "focus": "{{ n_in.outputs.focus }}"},
                      {"um": "array", "eng": "array"}, {"eng": {"type": "object"}, "tier": {"type": "object"}}, 4),
             W.stop({"eng": "{{ n_view.outputs.result.eng }}", "tier": "{{ n_view.outputs.result.tier }}"}, 5)]
    return nodes, [W.e("n_in", "n_um"), W.e("n_um", "n_eng"), W.e("n_eng", "n_view"), W.e("n_view", "n_out")]

if __name__ == "__main__":
    ua.ensure_session()
    nodes, edges = wf()
    wid, ver, viol = W.save("DB | FDSE Slack Engagement Page | Data", "Data for the FDSE page's Slack engagement view: work given per person (all roles) (from the task tracker, via the score) in the viewer's scope, bands, by-leader counts.",
                            nodes, edges, wid=SE.reg().get("slack_eng_page"))
    SE.reg_set("slack_eng_page", wid); print("saved", wid, ver, viol)
    if not viol: print("deployed", W.deploy(wid, "FDSE Slack engagement page data"))
