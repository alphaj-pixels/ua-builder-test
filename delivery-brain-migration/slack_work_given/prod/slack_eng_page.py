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
def BO = [zero: 0, low: 1, engaged: 2, none: 3]
def fname = nameOf[F] ?: F
def fd = { int k -> k == 1 ? '1 person' : (k + ' people') }
def pct = { int a, int b -> b ? Math.round(a * 100.0 / b) + '%' : '0%' }
def rd = N(sum.conversations_read); def pend = N(sum.conversations_pending); def tot = N(sum.assignments); def tot7 = N(sum.assignments7)
def fromAsg = N(sum.from_slack_asg); def fromCxo = N(sum.from_slack_cxo); def fromTrk = N(sum.from_tracker)
def upd = updated ? Instant.ofEpochMilli(updated).atZone(ZONE) : null
def jit = { String m, int salt -> def rnd = new Random(m.hashCode() * 1000003L + salt * 7919L); rnd.nextInt(50); rnd.nextDouble() * 2 - 1 }
def clamp = { double x -> Math.max(0, Math.min(100, Math.round(x) as int)) }
def DOW = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
// one view per window: '30' = past 30 days by week (bands by weeks with work), '7' = past 7 days by day (bands by days with work)
def build = { String M ->
  def is7 = M == '7'
  def people = scope.collect { e -> def r = E[e]; def bk = BK[S(is7 ? r.band_7d : r.band)] ?: 'none'
    def dd = S(r.daily_7d).split(',').collect { N(it) }; while (dd.size() < 7) dd.add(0, 0)
    def row = [band_key: bk, band_tone: TONE[bk], name: S(r.name) ?: (nameOf[e] ?: e), email: e, designation: S(r.role) ?: (roleOf[e] ?: ''), leader: nameOf[mgr[e]] ?: '–',
     manager_email: mgr[e] ?: '', given: N(is7 ? r.assigned_7d : r.assigned_30d).toString(), open: N(is7 ? r.open_7d : r.open_n).toString(), done: N(is7 ? r.done_7d : r.done_n).toString(),
     accounts: S(r.accounts) ?: '–', recent: S(is7 ? r.recent_7d : r.recent_work) ?: '–', last: ago((r.last_assigned_at ?: 0) as long), has_team: kids[e] ? 'yes' : 'no', note: '',
     active: is7 ? dd.count { it > 0 } : [r.assigned_w1, r.assigned_w2, r.assigned_w3, r.assigned_w4].count { N(it) > 0 }]
    (1..4).each { k -> def x = N(r['assigned_w' + k]); row['w' + k] = x.toString(); row['w' + k + 't'] = x > 0 ? 'on' : 'off' }
    (1..7).each { k -> def x = dd[k - 1]; row['d' + k] = x.toString(); row['d' + k + 't'] = x > 0 ? 'on' : 'off' }
    row }
  def ORD = { a, b -> ((BO[a.band_key] ?: 9) <=> (BO[b.band_key] ?: 9)) ?: (a.band_key == 'zero' ? ((S(a.leader) <=> S(b.leader)) ?: (S(a.name) <=> S(b.name))) : ((N(b.given) <=> N(a.given)) ?: (S(a.name) <=> S(b.name)))) }   // band first, so the order is consistent
  people = people.sort(false, ORD)
  def cnt = people.countBy { it.band_key }; def n = people.size()
  def tabs = [[id: 'zero', l: 'Zero engagement', n: (cnt['zero'] ?: 0).toString(), tone: 'R'], [id: 'low', l: 'Low', n: (cnt['low'] ?: 0).toString(), tone: 'A'],
              [id: 'engaged', l: 'Engaged', n: (cnt['engaged'] ?: 0).toString(), tone: 'G']]
  def weeks = [[today.minusDays(29), today.minusDays(21)], [today.minusDays(20), today.minusDays(14)], [today.minusDays(13), today.minusDays(7)], [today.minusDays(6), today]].withIndex().collect { x, k -> [id: 'w' + k, l: rng(x[0], x[1])] }
  def days = (6..0).collect { k -> def d = today.minusDays(k); [id: 'd' + k, l: DOW[d.dayOfWeek.value] + ' ' + d.dayOfMonth] }
  def leaders = (kids[F] ?: []).findAll { d -> desc(d).any { scope.contains(it) } }.collect { d ->
    def team = desc(d).findAll { scope.contains(it) }; def tp = people.findAll { team.contains(it.email) }; def c = tp.countBy { it.band_key }
    def on = tp.size(); def z = c['zero'] ?: 0; def share = on ? z * 100.0 / on : 0
    [name: nameOf[d] ?: d, email: d, designation: roleOf[d] ?: '', team_n: tp.size().toString(), engaged_n: (c['engaged'] ?: 0).toString(), low_n: (c['low'] ?: 0).toString(),
     zero_n: z.toString(), zero_s: pct(z, on), status: share >= 40 ? 'R' : (share >= 20 ? 'A' : 'G'), sk: share] }
    .sort { a, b -> (b.sk <=> a.sk) ?: (a.name <=> b.name) }.collect { it.findAll { k, v -> k != 'sk' } }
  def win = is7 ? rng(today.minusDays(6), today) : rng(today.minusDays(29), today)
  // scatter: across = work given in the window, up = weeks (30 days) or days (7 days) with work; no work given sits in its own lane
  int XM = is7 ? 15 : 50; int YN = is7 ? 7 : 4
  def scatter = people.collect { p -> int gv = N(p.given); int act = p.active as int; def lane = gv == 0
    def sx = lane ? 10 + Math.abs(jit(p.email, 1)) * 80 : Math.min(gv, XM) / (double) XM * 100 + jit(p.email, 3) * 1.2
    def sy = lane ? 3 + Math.abs(jit(p.email, 2)) * 94 : ((Math.max(1, act) - 0.5) / YN * 100) + jit(p.email, 4) * (is7 ? 4.5 : 9)
    [id: p.email, lane: lane ? 'yes' : 'no', tone: TONE[p.band_key] ?: 'X', sx: clamp(sx), sy: clamp(sy),
     tip: p.name + ' · ' + gv + ' given · ' + act + (is7 ? (act == 1 ? ' day' : ' days') : (act == 1 ? ' week' : ' weeks')) + ' · ' + p.leader] }
  def yTicks = (1..YN).collect { k -> [id: 'y' + k, v: k + (is7 ? (k == 1 ? ' day' : ' days') : (k == 1 ? ' week' : ' weeks')), pos: (Math.round((k - 0.5) / YN * 100) as int).toString()] }
  def xLabels = (0..5).collect { k -> k == 5 ? XM + '+' : ((XM * k / 5) as int).toString() }
  def period = is7 ? 'past 7 days' : 'past 30 days'
  def leadTxt = n == 0 ? ('No one reports into ' + fname + '.') : ((cnt['zero'] ?: 0) + ' of ' + fd(n) + ' in ' + fname + "'s team " + ((cnt['zero'] ?: 0) == 1 ? 'was' : 'were') + ' given no work in the ' + period + '.')
  if (rd == 0 && tot == 0) leadTxt = 'Still reading Slack conversations for work given to people. Check back in an hour.'
  else if (pend > 0) leadTxt = 'So far, ' + leadTxt.substring(0, 1).toLowerCase() + leadTxt.substring(1)
  def readTxt = ' ' + rd + ' Slack conversations read.' + (pend ? ' ' + pend + ' more are still being read, so counts will rise.' : '')
  [asof: 'Slack engagement, ' + period + ' ' + win + '. ' + fd(n) + ' in ' + fname + "'s team" + (upd ? ' · updated ' + fmt(upd.toLocalDate()) + ' ' + String.format('%02d:%02d', upd.hour, upd.minute) : ''),
   label: 'Slack engagement · ' + period + ' · ' + fname + "'s team", lead: leadTxt, mode: M,
   rest: n == 0 ? '' : (is7 ? ((cnt['engaged'] ?: 0) + ' were given work on 3 or more of the last 7 days, and ' + (cnt['low'] ?: 0) + ' on only 1 or 2 days.')
                            : ((cnt['engaged'] ?: 0) + ' were given work in 3 or 4 of the last 4 weeks, and ' + (cnt['low'] ?: 0) + ' in only 1 or 2 weeks.')),
   coverage: is7 ? ('From the task tracker: ' + tot7 + " tasks given to people in Sumeet Nandal's tree in the past 7 days." + readTxt)
     : ('From the task tracker: ' + tot + " tasks given to people in Sumeet Nandal's tree in the past 30 days, " + fromAsg + ' found in Slack conversations by the Slack Task Assignment agent, ' + fromCxo + ' from Slack CXO records and ' + (fromTrk ? fromTrk + ' logged directly in the tracker.' : 'none logged directly in the tracker.') + readTxt),
   people_sub: is7 ? 'Tasks given each day, oldest day first. Zero means no task in the task tracker was given to them in the past 7 days.' : 'Tasks given each week, oldest week first. Zero means no task in the task tracker was given to them in the past 30 days.',
   sc_sub: 'Each dot is one person. Across: pieces of work given in the ' + period + '. Up: how many of the last ' + (is7 ? '7 days' : '4 weeks') + ' they were given work. People given no work sit in the left lane. Hover a dot for the name.',
   note_top: is7 ? 'Engaged: work on 3 or more days' : 'Engaged: work in 3 or 4 weeks', note_bottom: is7 ? 'Low: work on 1 or 2 days' : 'Low: work in 1 or 2 weeks',
   y_axis: is7 ? '↑ Days with work given' : '↑ Weeks with work given', x_axis: 'Work given in the ' + period + ' →',
   has_data: updated ? 'yes' : 'no', tabs: tabs, people: people, weeks: weeks, days: days, leaders: leaders, has_leaders: leaders ? 'yes' : 'no',
   no_leaders: 'Nobody reporting to ' + fname + ' leads a team.', scatter: scatter, y_ticks: yTicks, x_labels: xLabels, lane_n: (cnt['zero'] ?: 0).toString()] }
// Slack coverage card (from the daily DB | Slack coverage run), with the rows for its two drawers
def cov = [:]; try { cov = new JsonSlurper().parseText(S(E['__coverage__']?.recent_work) ?: '{}') } catch (e) { }
def NC = (cov.no_channel instanceof List) ? cov.no_channel : []; def QC = (cov.quiet instanceof List) ? cov.quiet : []
def ncA = NC.findAll { S(it.status) == 'active' }; def ncN = NC.findAll { S(it.status) != 'active' }
def covUpd = cov.updated_at ? Instant.ofEpochMilli(cov.updated_at as long).atZone(ZONE).toLocalDate() : null
def dayOf = { String iso -> try { iso ? fmt(Instant.parse(iso).atZone(ZONE).toLocalDate()) : '—' } catch (e) { '—' } }
def SL = [active: 'Active', not_started: 'Awaiting kickoff']   // account_db status 'not_started' = signed, delivery not kicked off yet
def accRows = ((cov.acc_list instanceof List) ? cov.acc_list : []).withIndex().collect { a, k -> int nch = N(a.n_ch); int ms = N(a.msgs)
  [id: 'a' + k, name: S(a.name), status: SL[S(a.status)] ?: S(a.status), channels: nch ? S(a.channels) : 'No Slack channel added', n_ch: nch.toString(), msgs: ms.toString(),
   last: dayOf(S(a.last)), tone: nch == 0 ? 'R' : (ms == 0 ? 'A' : 'G')] }
def chRows = ((cov.ch_list instanceof List) ? cov.ch_list : []).withIndex().collect { c, k -> int ms = N(c.msgs)
  [id: 'c' + k, channel: '#' + S(c.channel), account: S(c.account) ?: 'No account', msgs: ms.toString(), last: dayOf(S(c.last)), tone: ms == 0 ? 'A' : 'G'] }
def covCard = [has: cov ? 'yes' : 'no', nc_n: NC.size().toString(), accounts: N(cov.accounts).toString(), nc_active_n: ncA.size().toString(), nc_ns_n: ncN.size().toString(),
  nc_active: ncA.collect { S(it.name) }.join(' · ') ?: 'None', nc_ns: ncN.collect { S(it.name) }.join(' · ') ?: 'None',
  q_n: QC.size().toString(), channels: N(cov.channels).toString(), quiet: QC.collect { '#' + S(it.channel) + (S(it.account) ? ' (' + S(it.account) + ')' : ' (no account)') }.join(' · ') ?: 'None',
  updated: covUpd ? 'Updated ' + fmt(covUpd) + '.' : '', acc_rows: accRows, ch_rows: chRows,
  acc_sub: accRows.count { it.tone == 'R' } + ' with no Slack channel, ' + accRows.count { it.tone == 'A' } + ' with channels but no messages in the past 30 days, ' + accRows.count { it.tone == 'G' } + ' with messages. Churned accounts are left out.',
  ch_sub: chRows.count { it.tone == 'A' } + ' with no messages in the past 30 days, ' + chRows.count { it.tone == 'G' } + ' with messages. Channels of churned accounts are left out.']
def shortL = { List xs, int k -> xs.size() <= k ? (xs.join(' · ') ?: 'None') : (xs.take(k).join(' · ') + ' … and ' + (xs.size() - k) + ' more') }
covCard.nc_active_s = shortL(ncA.collect { S(it.name) }, 12); covCard.nc_ns_s = shortL(ncN.collect { S(it.name) }, 8)
covCard.quiet_s = shortL(QC.collect { '#' + S(it.channel) + (S(it.account) ? ' (' + S(it.account) + ')' : ' (no account)') }, 14)
covCard.more = (ncA.size() > 12 || ncN.size() > 8 || QC.size() > 14) ? 'yes' : 'no'
def eng = build('30') + [cov: covCard]
def eng7 = build('7')
return [eng: eng, eng7: eng7, tier: [crumbs: crumbs.withIndex().collect { m, i -> [id: 'c' + i, email: m, name: nameOf[m] ?: m, last: i == crumbs.size() - 1 ? 'yes' : 'no'] }, focus: [email: F, name: fname]]]
"""

def wf():
    P = {k: {"type": "string"} for k in ("viewer", "admin", "focus")}
    nodes = [W.start(P, []),
             SE.fetch("n_um", "People", "db_user_management", 2), SE.fetch("n_eng", "Engagement rows", "db_fdse_slack_engagement", 3),
             W.groovy("n_view", "Engagement view", VIEW, {"um": W.arr("n_um.outputs.objects"), "eng": W.arr("n_eng.outputs.objects"),
                      "viewer": "{{ n_in.outputs.viewer }}", "admin": "{{ n_in.outputs.admin }}", "focus": "{{ n_in.outputs.focus }}"},
                      {"um": "array", "eng": "array"}, {"eng": {"type": "object"}, "eng7": {"type": "object"}, "tier": {"type": "object"}}, 4),
             W.stop({"eng": "{{ n_view.outputs.result.eng }}", "eng7": "{{ n_view.outputs.result.eng7 }}", "tier": "{{ n_view.outputs.result.tier }}"}, 5)]
    return nodes, [W.e("n_in", "n_um"), W.e("n_um", "n_eng"), W.e("n_eng", "n_view"), W.e("n_view", "n_out")]

if __name__ == "__main__":
    ua.ensure_session()
    nodes, edges = wf()
    wid, ver, viol = W.save("DB | FDSE Slack Engagement Page | Data", "Data for the FDSE page's Slack engagement view: work given per person (all roles) (from the task tracker, via the score) in the viewer's scope, bands, by-leader counts.",
                            nodes, edges, wid=SE.reg().get("slack_eng_page"))
    SE.reg_set("slack_eng_page", wid); print("saved", wid, ver, viol)
    if not viol: print("deployed", W.deploy(wid, "FDSE Slack engagement page data"))
