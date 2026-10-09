"""DB | FDSE Utilisation Page | Data (callable): the leaders' FDSE utilisation page.
Inputs: viewer (email), admin ('true'/'false'), manager (optional filter: a direct manager's email).
Scope: admins see everyone in db_fdse; anyone else sees the people below them in the manager chain
(updatedManagerEmail / managerEmail, lvlTwo/Three/FourManagerMail). Scores are computed live with fdse_score.SCORE.
"""
import sys, json; sys.path.insert(0, '.')
import sales, ua, db_wf as W, fdse_score as F
from db_classify import fetch_all

NAME = "DB | FDSE Utilisation Page | Data"
CODE = r"""
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) ? binding.getVariable(n) : [] }
""" + F.SCORE + r"""
def me = S(binding.hasVariable('viewer') ? viewer : '').toLowerCase()
def isAdmin = S(binding.hasVariable('admin') ? admin : '').toLowerCase() == 'true'
def mgrFilter = S(binding.hasVariable('manager') ? manager : '').toLowerCase()
// people and reporting lines from db_user_management; weekly capacity from db_fdse when set
def FD = L('fd').collect { it.properties ?: [:] }.findAll { S(it.mail_id) }.collectEntries { [S(it.mail_id).toLowerCase(), it] }
def UM = L('um').collect { it.properties ?: [:] }.findAll { S(it.emp_email).contains('@') }
def umMgr = UM.collectEntries { [S(it.emp_email).toLowerCase(), S(it.manager_email).toLowerCase()] }
def upN = { String m, int k -> def x = m; k.times { x = x ? (umMgr[x] ?: '') : '' }; x }
def people = UM.collect { u -> def m = S(u.emp_email).toLowerCase(); def f = FD[m] ?: [:]
  [mail_id: m, fde: S(u.emp_name) ?: (S(f.fde) ?: m), designation: S(u.role) ?: S(f.designation), managerEmail: umMgr[m] ?: '', Manager: S(u.manager_name),
   lvlTwoManagerMail: upN(m, 2), lvlThreeManagerMail: upN(m, 3), lvlFourManagerMail: upN(m, 4), weeklyCapacity: f.weeklyCapacity] }.unique { it.mail_id }
// scope: Sumeet Nandal and, for now, only Shivam Satrawal's and Sandeep Sharma's teams below him
def SCOPE_ROOT = 'sumeet@unifyapps.com'
def umKids = umMgr.groupBy { k, v -> v }.collectEntries { k, v -> [k, v.keySet() as List] }
def SCOPE_TEAMS = ['shivam@unifyapps.com', 'sandeep.sharma@unifyapps.com']   // for now: only Shivam Satrawal's and Sandeep Sharma's teams (product and project management)
def inTeam = [SCOPE_ROOT] as Set; def stk = SCOPE_TEAMS.findAll { umMgr.containsKey(it) }; inTeam.addAll(stk)
while (stk) { def x = stk.pop(); (umKids[x] ?: []).each { c -> if (inTeam.add(c)) stk << c } }
people = people.findAll { inTeam.contains(S(it.mail_id).toLowerCase()) }
def nameOf = people.collectEntries { [S(it.mail_id).toLowerCase(), S(it.fde)] }
def chainOf = { Map p -> [(S(p.updatedManagerEmail) ?: S(p.managerEmail)), S(p.lvlTwoManagerMail), S(p.lvlThreeManagerMail), S(p.lvlFourManagerMail)].collect { it.toLowerCase() } }
def inScope = people.collect { p -> def ch = chainOf(p); def lvl = ch.indexOf(me)
  (isAdmin || lvl >= 0) && S(p.mail_id).toLowerCase() != me ? [p: p, level: lvl >= 0 ? lvl + 1 : null, mgr: ch[0]] : null }.findAll { it }
def rows = inScope.collect { x -> def p = x.p; def mail = S(p.mail_id).toLowerCase(); def sc = scoreOf(mail, p.weeklyCapacity)
  [id: mail, name: S(p.fde) ?: mail, email: mail, designation: S(p.designation) ?: '–', manager: nameOf[x.mgr] ?: (S(p.Manager) ?: '–'), manager_email: x.mgr,
   relation: x.level == 1 ? 'Direct' : (x.level ? "Level ${x.level}".toString() : ''), capacity: (sc.weeklyCapacity as BigDecimal).stripTrailingZeros().toPlainString(),
   owned: sc.ownedLoad.toString(), reviewer: sc.reviewerLoad.toString(), load: sc.weeklyLoad.toString(), tasks: sc.tasksThisWeek.toString(),
   overdue: sc.overdue.toString(), waiting: sc.waitingTasks.toString(), pct: sc.utilisation, pct_s: sc.utilisationFormatted, band: sc.utilisationBand,
   tone: sc.utilisationBand == 'Overloaded' ? 'R' : (sc.utilisationBand == 'A' ? 'G' : (sc.utilisationBand == 'B' ? 'A' : 'X')),
   od_tone: sc.overdue > 0 ? 'R' : 'X', cap_n: sc.weeklyCapacity as BigDecimal, load_n: sc.weeklyLoad as BigDecimal] }.sort { a, b -> (b.pct <=> a.pct) ?: (a.name <=> b.name) }
def shown = mgrFilter ? rows.findAll { it.manager_email == mgrFilter } : rows
def avgOf = { List xs -> xs ? r2(xs.sum { it.pct as BigDecimal } / xs.size()) : 0 }
def cnt = { List xs, String b -> xs.count { it.band == b } }
def BUCKETS = [['h0', 'Idle (0%)', { p -> p == 0 }], ['h1', 'Under 60%', { p -> p > 0 && p < 60 }], ['h2', '60–69%', { p -> p >= 60 && p < 70 }],
               ['h3', '70–99%', { p -> p >= 70 && p < 100 }], ['h4', '100%+', { p -> p >= 100 }]]
def heatOf = { List xs -> [cells: BUCKETS.collect { b -> def n = xs.count { b[2](it.pct as BigDecimal) }; def share = xs ? n / xs.size() : 0
  [id: b[0], k: b[1], n: n.toString(), lvl: n == 0 ? '0' : Math.max(1, Math.ceil(share * 5) as int).toString(), share: xs ? String.format('%.0f%%', share * 100 as double) : '0%'] }] }
def idleOf = { List xs -> def cap = xs.sum { it.cap_n } ?: 0; def spare = xs.sum { [it.cap_n - it.load_n, 0].max() } ?: 0
  [idle_pts: r2(spare).toString(), idle_pct: cap ? String.format('%.0f%%', spare / cap * 100 as double) : '–', idle_people: xs.count { (it.load_n ?: 0) == 0 }.toString(),
   idle_tone: cap && spare / cap >= 0.5 ? 'A' : 'X'] }
def leaders = rows.groupBy { it.manager_email }.collect { m, xs -> [id: m ?: 'none', email: m, name: nameOf[m] ?: (xs[0].manager ?: 'No manager'), team: xs.size().toString(),
   avg: String.format('%.2f%%', avgOf(xs) as double), avg_n: avgOf(xs), over: cnt(xs, 'Overloaded').toString(), over_tone: cnt(xs, 'Overloaded') ? 'R' : 'X',
   a: cnt(xs, 'A').toString(), b: cnt(xs, 'B').toString(), c: cnt(xs, 'C').toString(), active: xs.count { (it.tasks as int) > 0 }.toString(),
   load: r2(xs.sum { it.load as BigDecimal }).toString(), on: m == mgrFilter ? 'yes' : 'no'] + heatOf(xs) + idleOf(xs) }.sort { a, b -> (b.avg_n <=> a.avg_n) ?: (a.name <=> b.name) }
// ---------------- tiers: the focus person, the path to them, and their direct reports with team roll-ups
def mgrOf = { Map p -> (S(p.updatedManagerEmail) ?: S(p.managerEmail)).toLowerCase() }
def byMail = people.collectEntries { [S(it.mail_id).toLowerCase(), it] }
def kids = people.groupBy { mgrOf(it) }.collectEntries { k, v -> [k, v.collect { S(it.mail_id).toLowerCase() }.findAll { it != k }] }
def desc = { String m -> def out = [] as LinkedHashSet; def stack = [m]
  while (stack) { def x = stack.pop(); (kids[x] ?: []).each { if (out.add(it)) stack << it } }; out }
def roots = people.collect { S(it.mail_id).toLowerCase() }.findAll { !byMail.containsKey(mgrOf(byMail[it])) }
def top = isAdmin ? roots.max { desc(it).size() } : me   // admins land on the top leader; everyone else on their own team
def want = S(binding.hasVariable('focus') ? focus : '').toLowerCase()
def allowed = { String m -> m && (isAdmin || m == me || desc(me).contains(m)) }
def F = (want && byMail[want] && allowed(want)) ? want : top
def path = []; def cur = F; def guard = 0
while (cur && guard++ < 12) { path.add(0, cur); if (cur == top || !(isAdmin || desc(me).contains(cur))) break; def up = mgrOf(byMail[cur] ?: [:]); if (!byMail[up] || (!isAdmin && !allowed(up))) break; cur = up }
def accountsOf = [:].withDefault { [] as LinkedHashSet }
L('tasks').each { r -> def t = r.properties ?: [:]; def st = S(t.status).toLowerCase(); if (st in ['done', 'completed', 'closed', 'resolved']) return
  def a = S(t.account); if (!a) return
  mails(t.Owners_List, t.ownerMail).each { accountsOf[it] << a } }
def personOf = { String m -> def p = byMail[m] ?: [:]; def sc = scoreOf(m, p.weeklyCapacity)
  [email: m, name: S(p.fde) ?: m, designation: S(p.designation) ?: '–', pct: sc.utilisation, pct_s: sc.utilisationFormatted, band: sc.utilisationBand,
   tone: sc.utilisationBand == 'Overloaded' ? 'R' : (sc.utilisationBand == 'A' ? 'G' : (sc.utilisationBand == 'B' ? 'A' : 'X')), tasks: sc.tasksThisWeek.toString(),
   overdue: sc.overdue.toString(), load: sc.weeklyLoad.toString(), cap_n: sc.weeklyCapacity as BigDecimal, load_n: sc.weeklyLoad as BigDecimal,
   accounts: (accountsOf[m] ?: []).join(', '), accounts_n: (accountsOf[m] ?: []).size().toString()] }
def teamOf = { String m -> def ds = desc(m).collect { personOf(it) }
  [team_n: ds.size().toString(), team_avg: ds ? String.format('%.2f%%', avgOf(ds) as double) : '–', team_over: cnt(ds, 'Overloaded').toString(),
   team_over_tone: cnt(ds, 'Overloaded') ? 'R' : 'X', directs_n: (kids[m] ?: []).size().toString(),
   directs: (kids[m] ?: []).collect { S(byMail[it]?.fde) ?: it }.join(', '), has_team: (kids[m] ?: []) ? 'yes' : 'no'] }
def focusP = personOf(F) + teamOf(F) + [manager_email: mgrOf(byMail[F] ?: [:])]
// RAG per person: utilisation G 60-99% / A under 60% / R 100%+; overdue G 0 / A 1-2 / R 3+; team average same as utilisation; overall = the worst
def ragU = { p -> p == null ? 'X' : (p >= 100 ? 'R' : (p >= 60 ? 'G' : 'A')) }
def ragO = { int n -> n >= 3 ? 'R' : (n >= 1 ? 'A' : 'G') }
def worst = { List xs -> xs.contains('R') ? 'R' : (xs.contains('A') ? 'A' : 'G') }
def RT = [R: 'Red', A: 'Amber', G: 'Green', X: '–']
def ragOf = { Map r -> def ds = r.has_team == 'yes' ? desc(r.email).collect { personOf(it) } : []
  def tu = ds ? ragU(avgOf(ds)) : 'X'; def u = ragU(r.pct as BigDecimal); def o = ragO((r.overdue ?: '0') as int)
  def all = worst([u, o] + (tu == 'X' ? [] : [tu]))
  // blue scale (same shades as the heatmap): utilisation 0% -> 0, under 60 -> 1, 60-69 -> 2, 70-99 -> 4, 100%+ -> 5; overdue 0 -> 0, 1-2 -> 3, 3+ -> 5
  def lvlU = { p -> p == null ? '0' : (p >= 100 ? '5' : (p >= 70 ? '4' : (p >= 60 ? '2' : (p > 0 ? '1' : '0')))) }
  def pv = r.pct as BigDecimal; def od = (r.overdue ?: '0') as int; def ta = ds ? avgOf(ds) : null
  def flags = []
  if (pv >= 100) flags << 'Overloaded'
  if (pv < 60) flags << 'Under 60%'
  if (od >= 1) flags << "${od} overdue".toString()
  if (ta != null && ta < 60) flags << 'Team under 60%'
  if (ta != null && ta >= 100) flags << 'Team overloaded'
  [rag_util: u, rag_util_t: RT[u], rag_overdue: o, rag_overdue_t: RT[o], rag_team: tu, rag_team_t: RT[tu], rag: all, rag_t: RT[all], rag_rank: [R: 0, A: 1, G: 2][all],
   lvl_util: lvlU(pv), lvl_overdue: od >= 3 ? '5' : (od >= 1 ? '3' : '0'), lvl_team: ta == null ? '0' : lvlU(ta),
   flag: flags ? 'yes' : 'no', flag_t: flags ? flags.join(' · ') : 'On target', flag_rank: pv >= 100 ? 0 : (pv < 60 ? 1 : (od >= 1 ? 2 : 3))] }
// 4 bands over the person's whole team (everyone below them; just the person when they have no team): people and share in each band
def B4 = [['b1', 'Under 60%', { p -> p < 60 }], ['b2', '60–69%', { p -> p >= 60 && p < 70 }], ['b3', '70–99%', { p -> p >= 70 && p < 100 }], ['b4', '100%+', { p -> p >= 100 }]]
def bandsOf = { String m -> def xs = desc(m).collect { personOf(it) }; if (!xs) xs = [personOf(m)]
  [band_base: xs.size().toString(), band_cells: B4.collect { b -> def n = xs.count { b[2](it.pct as BigDecimal) }; def share = n / xs.size()
    [id: b[0], k: b[1], n: n.toString(), pct: String.format('%.0f%%', share * 100 as double), lvl: n == 0 ? '0' : Math.max(1, Math.ceil(share * 5) as int).toString()] }] }
def tierRows = (kids[F] ?: []).collect { def r = personOf(it) + teamOf(it) + [manager_email: F, id: it]
  // heatmap cells for the RAG view: everyone below the person (or just the person when they have no team)
  def grp = r.has_team == 'yes' ? desc(it).collect { personOf(it) } : [personOf(it)]
  r + ragOf(r) + bandsOf(it) + heatOf(grp) + idleOf(grp) + [heat_team: grp.size().toString(), heat_avg: String.format('%.2f%%', avgOf(grp) as double)] }
  .sort { a, b -> ((b.has_team == 'yes' ? 1 : 0) <=> (a.has_team == 'yes' ? 1 : 0)) ?: ((b.team_n as int) <=> (a.team_n as int)) ?: (a.name <=> b.name) }
def tierAll = desc(F).collect { personOf(it) }
def everyone = isAdmin ? people.collect { S(it.mail_id).toLowerCase() }.collect { m -> personOf(m) + [manager: S(byMail[mgrOf(byMail[m])]?.fde) ?: (mgrOf(byMail[m]) ?: '–'),
    manager_email: mgrOf(byMail[m]), has_team: (kids[m] ?: []) ? 'yes' : 'no', team_n: desc(m).size().toString(), directs_n: (kids[m] ?: []).size().toString(), id: m] }
  .sort { a, b -> (b.pct <=> a.pct) ?: (a.name <=> b.name) } : []
// heatmap (RAG by leader): every leader inside the focus person's tree (the focus person included), each over their direct reports
def inTree = ([F] + (desc(F) as List)) as Set
def heatRows = leaders.findAll { inTree.contains(S(it.email).toLowerCase()) }
def tier = [admin: isAdmin ? 'yes' : 'no', heat: heatRows, heat_n: heatRows.size().toString(), rag: [R: tierRows.count { it.rag == 'R' }, A: tierRows.count { it.rag == 'A' }, G: tierRows.count { it.rag == 'G' },
        over: tierRows.count { (it.pct as BigDecimal) >= 100 }, under: tierRows.count { (it.pct as BigDecimal) < 60 }, od: tierRows.count { ((it.overdue ?: '0') as int) >= 1 }, ok: tierRows.count { it.flag == 'no' }],
  rag_focus: bandsOf(F), rag_rows: tierRows.sort(false) { a, b -> (a.flag_rank <=> b.flag_rank) ?: ((b.pct as BigDecimal) <=> (a.pct as BigDecimal)) ?: (a.name <=> b.name) }, everyone: everyone, everyone_n: everyone.size().toString(), focus: focusP, crumbs: path.withIndex().collect { m, k -> [id: 'c' + k, email: m, name: S(byMail[m]?.fde) ?: m, last: k == path.size() - 1 ? 'yes' : 'no'] },
  rows: tierRows, empty: tierRows ? 'no' : 'yes', empty_text: (S(byMail[F]?.fde) ?: F) + ' has no one reporting to them in db_user_management.',
  strip: [[id: 't0', l: 'Team', v: tierAll.size().toString(), n: "${(kids[F] ?: []).size()} direct, ${tierAll.size() - (kids[F] ?: []).size()} below them".toString(), c: 'X'],
          [id: 't1', l: 'Average utilisation', v: String.format('%.2f%%', avgOf(tierAll) as double), n: 'everyone in the team, 0% for no tasks', c: 'X'],
          [id: 't2', l: 'Overloaded', v: cnt(tierAll, 'Overloaded').toString(), n: '100% or more of capacity', c: cnt(tierAll, 'Overloaded') ? 'R' : 'X'],
          [id: 't3', l: 'No work this week', v: idleOf(tierAll).idle_people, n: 'people in the team with no tasks landing', c: 'X'],
          [id: 't4', l: 'Bands A · B · C', v: "${cnt(tierAll, 'A')} · ${cnt(tierAll, 'B')} · ${cnt(tierAll, 'C')}".toString(), n: 'A 70–99%, B 60–69%, C under 60%', c: 'X']]]
def fmtDay = { d -> d.format(java.time.format.DateTimeFormatter.ofPattern('d MMM')) }
def isM = (WIN as int) == 30
def isP = PAST
def PD = 'past ' + PDAYS + ' days'
def PER = isP ? 'Over the ' + PD : (isM ? 'Over the next 30 days' : 'This week')
// ---------------- delivery capacity view (layout from the Delivery capacity reference, adapted to this week's data)
def fwdPts = [:].withDefault { 0.0 }; def openN = [:].withDefault { 0 }; def goodN = [:].withDefault { 0 }; def noEtaN = [:].withDefault { 0 }; def acctN = [:].withDefault { [:].withDefault { 0 } }
L('tasks').each { r -> def t = r.properties ?: [:]; def cls = classOf(t.status); if (PAST ? !inPast(r, t) : cls == 'completed') return   // past N days: every task assigned in the window
  def owners = mails(t.Owners_List, t.ownerMail); if (!owners) return
  def eta = etaOf(t.eta); def days = eta != null ? java.time.temporal.ChronoUnit.DAYS.between(today, eta) : null
  def sp = 0.0; try { sp = S(t.taskStoryPoints) ? S(t.taskStoryPoints).toBigDecimal() : 0.0 } catch (e) { sp = 0.0 }
  def good = PAST ? sp > 0 : (sp > 0 && eta != null); def a = S(t.account)
  owners.each { o -> openN[o] = openN[o] + 1; if (good) goodN[o] = goodN[o] + 1; if (eta == null) noEtaN[o] = noEtaN[o] + 1; if (a) acctN[o][a] = acctN[o][a] + 1
    if (days != null && days >= 0 && days <= 28) fwdPts[o] = fwdPts[o] + pointsOf(t.taskStoryPoints) * WEIGHT[cls] / owners.size() } }
def capOf = { String m -> def c = 60.0; try { def v = S(byMail[m]?.weeklyCapacity); if (v && v.toBigDecimal() > 0) c = v.toBigDecimal() } catch (e) { }; c }
def BK = { BigDecimal p, int tasks -> p >= 100 ? 'over' : (p >= 70 ? 'optimal' : (p >= 60 ? 'medium' : (p == 0 && tasks == 0 ? 'notask' : 'under'))) }
def BL = [under: 'Under-used', medium: 'Medium', optimal: 'Optimal', over: 'Overloaded', notask: 'No tasks']
def BT = [under: 'U', medium: 'A', optimal: 'G', over: 'R', notask: 'X']
def AK = { int od -> od >= 3 ? 'behind' : (od >= 1 ? 'some' : 'clear') }
def AL = [behind: '3+ tasks overdue', some: '1–2 tasks overdue', clear: 'Nothing overdue']
def pctS = { x -> def v = ((x ?: 0) * 100) as double; v > 0 && v < 1 ? '<1%' : String.format('%.0f%%', v) }
def capCache = [:]
def capPerson = { String m -> if (capCache[m]) return capCache[m]
  def p = personOf(m); def tasks = (p.tasks ?: '0') as int; def pv = p.pct as BigDecimal
  def f = r2(fwdPts[m] / (capOf(m) * 4) * 100); def bk = BK(pv, tasks); def topA = acctN[m] ? acctN[m].max { it.value }.key : ''
  def out = p + [id: m, band_key: bk, band_l: BL[bk], band_tone: BT[bk], fwd: f, fwd_s: String.format('%.0f%%', f as double), ahead: AK((p.overdue ?: '0') as int), cell: bk + '|' + AK((p.overdue ?: '0') as int),
       top_acct: topA ?: '–', leader: S(byMail[mgrOf(byMail[m] ?: [:])]?.fde) ?: '–', manager_email: mgrOf(byMail[m] ?: [:]),
       has_team: (kids[m] ?: []) ? 'yes' : 'no', directs_n: (kids[m] ?: []).size().toString(), open_n: openN[m], good_n: goodN[m], noeta_n: noEtaN[m],
       util_s: (tasks == 0 && pv == 0) ? 'No tasks' : p.pct_s, od_tone: ((p.overdue ?: '0') as int) > 0 ? 'R' : 'X']
  capCache[m] = out; out }
def SORTS = [over: { a, b -> ((b.pct as BigDecimal) <=> (a.pct as BigDecimal)) ?: (a.name <=> b.name) }, under: { a, b -> ((a.pct as BigDecimal) <=> (b.pct as BigDecimal)) ?: (a.name <=> b.name) },
             medium: { a, b -> ((b.pct as BigDecimal) <=> (a.pct as BigDecimal)) ?: (a.name <=> b.name) }, optimal: { a, b -> ((b.pct as BigDecimal) <=> (a.pct as BigDecimal)) ?: (a.name <=> b.name) },
             notask: { a, b -> ((b.fwd as BigDecimal) <=> (a.fwd as BigDecimal)) ?: (a.name <=> b.name) }]
def KEYS = ['over', 'under', 'medium', 'optimal', 'notask']
def everyoneC = desc(F).collect { capPerson(it) }
def peopleC = KEYS.collectMany { k -> everyoneC.findAll { it.band_key == k }.sort(false, SORTS[k]) }
def NC = everyoneC.size()
def COLS = ['notask', 'under', 'medium', 'optimal', 'over']; def ROWS = ['behind', 'some', 'clear']
def cellN = { String ck, String rk -> everyoneC.count { it.band_key == ck && it.ahead == rk } }
def maxCell = (COLS.collectMany { ck -> ROWS.collect { rk -> cellN(ck, rk) } }.max() ?: 0)
def grid = ROWS.collect { rk -> [id: rk, l: AL[rk], cells: COLS.collect { ck -> def n = cellN(ck, rk)
   [id: rk + '_' + ck, key: ck + '|' + rk, n: n.toString(), lvl: n == 0 ? '0' : Math.max(1, Math.min(5, Math.ceil(n * 5.0 / Math.max(1, maxCell)) as int)).toString(), title: BL[ck] + ', ' + AL[rk].toLowerCase()] }] }
def gridCols = COLS.collect { ck -> def n = everyoneC.count { it.band_key == ck }; [id: 'gc_' + ck, key: ck, l: BL[ck], n: n.toString(), tone: BT[ck], share: NC ? pctS(n / NC) : '0%'] }
def statusOf = { s -> s >= 0.30 ? 'R' : (s >= 0.20 ? 'A' : 'G') }
def qualOf = { q -> q >= 0.80 ? 'G' : (q >= 0.60 ? 'A' : 'R') }
def capLeaders = (kids[F] ?: []).findAll { (kids[it] ?: []) }.collect { m -> def team = desc(m).collect { capPerson(it) }; def n = team.size()
  def c = { k -> team.count { it.band_key == k } }
  def wt = n - c('notask'); def act = wt ? (c('under') + c('over')) / wt : null
  def on = team.sum { it.open_n } ?: 0; def gd = team.sum { it.good_n } ?: 0; def q = on ? gd / on : 0
  capPerson(m) + [id: m, team_n: n.toString(), status: act == null ? 'X' : statusOf(act), action_s: act == null ? '–' : pctS(act), action_n: act == null ? -1 : act,
    logged_s: pctS(n ? wt / n : 0), with_tasks_n: wt.toString(), status_note: act == null ? 'no tasks logged' : 'of ' + wt + ' with tasks',
    under_n: c('under').toString(), under_s: pctS(n ? c('under') / n : 0), notask_n: c('notask').toString(), notask_s: pctS(n ? c('notask') / n : 0),
    medium_n: c('medium').toString(), medium_s: pctS(n ? c('medium') / n : 0), optimal_n: c('optimal').toString(), optimal_s: pctS(n ? c('optimal') / n : 0),
    over_n: c('over').toString(), over_s: pctS(n ? c('over') / n : 0), over_tone: c('over') ? 'R' : 'X',
    team_avg: String.format('%.0f%%', avgOf(team) as double), dq: on ? pctS(q) : '–', dq_tone: on ? qualOf(q) : 'X', open_tasks: on.toString()] }
  .sort { a, b -> ((b.action_n as BigDecimal) <=> (a.action_n as BigDecimal)) ?: ((b.team_n as int) <=> (a.team_n as int)) ?: (a.name <=> b.name) }
def focusName = S(byMail[F]?.fde) ?: F
def noT = everyoneC.count { it.band_key == 'notask' }
def underT = everyoneC.findAll { it.band_key == 'under' }
def fte = Math.round((underT.sum { 1 - (it.pct as BigDecimal) / 100 } ?: 0) as double)
def spareC = r2(everyoneC.findAll { it.band_key != 'notask' }.sum { [it.cap_n * WIN / 7.0 - it.load_n, 0].max() } ?: 0)
def overC = everyoneC.findAll { it.band_key == 'over' }
def bigL = capLeaders.findAll { (it.team_n as int) >= 5 }
def byOver = bigL.sort(false) { a, b -> (b.over_n as int) <=> (a.over_n as int) }
def idleShare = { x -> (x.under_n as int) / (x.team_n as int) }
def idleL = bigL ? bigL.max { idleShare(it) } : null
def hotL = bigL ? bigL.max { (it.over_n as int) / (it.team_n as int) } : null
def openAll = everyoneC.sum { it.open_n } ?: 0; def goodAll = everyoneC.sum { it.good_n } ?: 0; def qAll = openAll ? goodAll / openAll : 0
def lowQ = capLeaders.findAll { it.dq_tone == 'R' }.collect { it.name }
def withT = NC - noT
def noEtaAll = everyoneC.sum { it.noeta_n } ?: 0
def lead = (!NC ? "No one reports into ${focusName}." :
  "${PER}, ${noT} of ${NC} people in ${focusName}'s team ${isP ? 'were assigned no tasks' : 'have no tasks logged'}" + (withT ? ", and among the ${withT} with tasks the equivalent of ${fte} FDSE${fte == 1 ? '' : 's'} ${isP ? 'had no real work' : (isM ? 'has no work lined up' : 'had no real work')}." : '.')).toString()
def overLeaders = byOver.findAll { (it.over_n as int) > 0 }
def overWhere = !overC ? '' : (overLeaders.size() >= 2 ? ", and ${(overLeaders[0].over_n as int) + (overLeaders[1].over_n as int)} of them sit under ${overLeaders[0].name} and ${overLeaders[1].name}" :
  (overLeaders.size() == 1 ? ((overLeaders[0].over_n as int) == overC.size() ? ", all of them in ${overLeaders[0].name}'s team" : ", ${overLeaders[0].over_n} of them in ${overLeaders[0].name}'s team") : ''))
def rest = ((overC ? "${overC.size()} ${overC.size() == 1 ? 'person is' : 'people are'} above 100% of capacity${overWhere}. " : 'No one is above 100% of capacity. ') +
  (idleL && (idleL.under_n as int) > 0 ? "The biggest single lever is ${idleL.name}'s team, where ${pctS(idleShare(idleL))} of people have tasks but are under 60%" +
    (hotL && (hotL.over_n as int) > 0 && hotL.id != idleL.id ? ", while ${hotL.name}'s team has ${hotL.over_s} overloaded." : '.') : '')).toString()
// scatter: one dot per person. Across: utilisation this week (0-160%+). Up: overdue tasks (0 to YMAX+). No-task people sit in their own lane.
def jit = { String m, int salt -> def rnd = new Random(m.hashCode() * 1000003L + salt * 7919L); rnd.nextInt(50); rnd.nextDouble() * 2 - 1 }   // stable per person, independent per salt
def maxOd = everyoneC.collect { (it.overdue ?: '0') as int }.max() ?: 0
def YMAX = Math.min(30, Math.max(5, (Math.ceil(maxOd / 5.0) as int) * 5))
def clamp = { double v -> Math.max(0, Math.min(100, Math.round(v) as int)) }
def scatter = everyoneC.collect { p -> def pv = (p.pct as BigDecimal) as double; def od = (p.overdue ?: '0') as int; def lane = p.band_key == 'notask'
  def sx = lane ? 10 + Math.abs(jit(p.id, 1)) * 80 : Math.min(pv, 160.0) / 160.0 * 100 + jit(p.id, 3) * 1.2
  def sy = lane ? 3 + Math.abs(jit(p.id, 2)) * 94 : Math.min(od, YMAX) / (double) YMAX * 100 + 2 + jit(p.id, 4) * 2
  [id: p.id, lane: lane ? 'yes' : 'no', tone: p.band_tone, sx: clamp(sx), sy: clamp(sy),
   tip: "${p.name} · ${p.util_s} · ${od} overdue · ${p.leader}".toString()] }
def NT = YMAX % 4 == 0 ? 4 : (YMAX % 3 == 0 ? 3 : 5)
def yTicks = (0..NT).collect { k -> [id: 'y' + k, v: (k == NT ? "${YMAX}+" : "${(YMAX * k / NT) as int}").toString(), pos: (Math.round(k * 100.0 / NT) as int).toString()] }
def cap = [asof: (isP ? "FDSE utilisation, ${PD} ${fmtDay(START)} to ${fmtDay(today)}. ${NC} people in ${focusName}'s team." : "FDSE utilisation, ${isM ? 'next 30 days' : 'week of'} ${fmtDay(today)} to ${fmtDay(today.plusDays((WIN as int) - 1))}. ${NC} people in ${focusName}'s team.").toString(),
  label: "${isP ? 'Past ' + PDAYS + ' days' : (isM ? 'Next 30 days' : 'This week')} · ${focusName}'s team".toString(), lead: lead, period: isP ? 'past' + PDAYS : (isM ? '30' : '7'),
  money: "${String.format('%,d', Math.round(spareC as double))} story points of capacity unused ${isP ? 'over the ' + PD : (isM ? 'over the next 30 days' : 'this week')} across the ${withT} people with tasks, at 60 points per person per week unless a capacity is set${isM ? ', so about 257 points each over 30 days' : ''}.".toString(),
  horizon_note: isP ? 'Every task assigned to the person in the ' + PD + ' counts, done or not: tasks from Slack are dated by the Slack message, the rest by the day they were added to the task tracker. Each counts its story points (1 when blank), waiting tasks half. Overdue means still open and past its due date.'
    : (isM ? 'Only work already assigned counts. New work that arrives during the month is not known yet, so 30-day figures run low; read them as how much of the month is already spoken for.' : ''), has_horizon: (isP || isM) ? 'yes' : 'no',
  rest: rest, conf: (isP ? "${pctS(qAll)} of the ${openAll} tasks assigned in this team in the ${PD} have story points; the rest count as 1 point." : "${pctS(qAll)} of open tasks in this team have story points and a due date; ${noEtaAll} have no due date at all.").toString(), conf_tone: openAll ? qualOf(qAll) : 'X',
  caution: lowQ ? ("Treat the figures for " + (lowQ.size() == 1 ? lowQ[0] : (lowQ.size() <= 3 ? lowQ.take(lowQ.size() - 1).join(', ') + ' and ' + lowQ[-1] : lowQ.take(3).join(', ') + " and ${lowQ.size() - 3} other teams")) + " with caution: under 60% of their team's ${isP ? 'tasks from the ' + PD : 'open tasks'} are estimated.").toString() : '',
  has_caution: lowQ ? 'yes' : 'no', total: NC.toString(),
  grid: grid, grid_cols: gridCols,
  tabs: KEYS.collect { k -> [id: k, l: BL[k], n: everyoneC.count { it.band_key == k }.toString(), tone: BT[k]] },
  scatter: scatter, y_ticks: yTicks, y_max: YMAX.toString(), lane_n: noT.toString(),
  people: peopleC.collect { it.subMap(['id', 'name', 'designation', 'email', 'manager_email', 'has_team', 'accounts', 'accounts_n', 'directs_n', 'pct_s', 'band_key', 'band_l', 'band_tone', 'util_s', 'cell', 'top_acct', 'leader', 'tasks', 'overdue', 'od_tone']) }, leaders: capLeaders.collect { it.findAll { k, v -> !(k in ['cap_n', 'load_n', 'pct', 'fwd', 'action_n', 'open_n', 'good_n', 'noeta_n']) } }, leaders_n: capLeaders.size().toString(), has_leaders: capLeaders ? 'yes' : 'no',
  no_leaders: "No one reporting to ${focusName} has a team of their own. Everyone is listed under People above.".toString()]
return [cap: cap, tier: [admin: tier.admin, crumbs: tier.crumbs, focus: tier.focus], scope: isAdmin ? 'everyone' : 'your team', viewer: me,
  window: isP ? fmtDay(START) + ' to ' + fmtDay(today) : fmtDay(today) + ' to ' + fmtDay(today.plusDays((WIN as int) - 1))]
"""

def definition():
    fd, tk, um = fetch_all("n_fd", "FDSE rows", "db_fdse", 2), fetch_all("n_tk", "Tasks", "db_task_tracker", 3), fetch_all("n_um", "People", "db_user_management", 4)
    fd["inputs"]["page"]["limit"] = tk["inputs"]["page"]["limit"] = um["inputs"]["page"]["limit"] = 10000
    view = W.groovy("n_view", "Utilisation view", CODE,
                    {"fd": W.arr("n_fd.outputs.objects"), "tasks": W.arr("n_tk.outputs.objects"), "um": W.arr("n_um.outputs.objects"), "viewer": "{{ n_in.outputs.viewer }}",
                     "admin": "{{ n_in.outputs.admin }}", "manager": "{{ n_in.outputs.manager }}", "focus": "{{ n_in.outputs.focus }}", "window_days": "{{ n_in.outputs.window_days }}"},
                    {"fd": "array", "tasks": "array", "um": "array"},
                    {"cap": "object", "scope": "string", "viewer": "string", "window": "string", "tier": "object", "strip": {"type": "array", "items": W.ROW}, "leaders": {"type": "array", "items": W.ROW},
                     "rows": {"type": "array", "items": W.ROW}, "manager": "string", "manager_name": "string", "filtered": "string", "empty": "string",
                     "empty_text": "string", "foot": "string"}, 5)
    nodes = [W.start({"viewer": {"type": "string"}, "admin": {"type": "string"}, "manager": {"type": "string"}, "focus": {"type": "string"}, "window_days": {"type": "string"}}, []), fd, tk, um, view,
             W.stop("{{ n_view.outputs.result }}", 6)]
    order = ["n_in", "n_fd", "n_tk", "n_um", "n_view", "n_out"]
    return nodes, [W.e(a, b) for a, b in zip(order, order[1:])]

if __name__ == "__main__":
    ua.ensure_session()
    reg = json.load(open("db_automations.json"))
    nodes, edges = definition()
    wid, ver, viol = W.save(NAME, "View model for the leaders' FDSE utilisation page (week-based, scoped to the viewer's reporting line; admins see all).",
                            nodes, edges, reg.get("fdse_page"), tags=("DB", "FDSE"))
    reg["fdse_page"] = wid; json.dump(reg, open("db_automations.json", "w"), indent=1)
    print("saved", wid, ver, viol)
    if "--deploy" in sys.argv: print("deployed", W.deploy(wid, "FDSE utilisation page v1"))
    for p in ([{"viewer": "sumeet@unifyapps.com", "admin": "true"}, {"viewer": "sumeet@unifyapps.com", "admin": "true", "focus": "shivam@unifyapps.com"},
               {"viewer": "pratik.singh@unifyapps.com", "admin": "false", "focus": "sumeet@unifyapps.com"}] if "--test" in sys.argv else []):
        r = W.test(wid, p, nodes=("n_out",), timeout_s=300); o = (r["nodes"].get("n_out") or {}).get("outputs") or {}
        T = o.get("tier") or {}; print("  TIER", [c["name"] for c in T.get("crumbs", [])], (T.get("focus") or {}).get("name"), [(x["name"], x["pct_s"], x["team_n"], x["team_avg"]) for x in T.get("rows", [])][:6])
        print(p, r["status"], r.get("failed"), o.get("scope"), o.get("window"), [(s["l"], s["v"]) for s in o.get("strip", [])], "leaders", len(o.get("leaders", [])), "rows", len(o.get("rows", [])))
        for x in (o.get("leaders") or [])[:3]: print("   L", x["name"], x["team"], x["avg"], x["over"])
        for x in (o.get("rows") or [])[:3]: print("   R", x["name"], x["relation"], x["manager"], x["pct_s"], x["band"], x["tasks"])
