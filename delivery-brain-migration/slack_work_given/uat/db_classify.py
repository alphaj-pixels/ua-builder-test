import sys, json; sys.path.insert(0, '.')
import sales, ua, db_wf as W
A = json.load(open("db_agents.json"))
CLASSIFIER = A["DB | Use Case Classifier"]["agent"]
O_CXO, O_UC, O_TM = "db_cxo_intelligence", "db_account_usecase", "db_external_team_member"

COMMON = r"""
import groovy.json.JsonSlurper
import groovy.json.JsonOutput
def ZONE = java.time.ZoneId.of('Asia/Kolkata')
def TODAY = java.time.LocalDate.now(ZONE)
def oid = { String rid -> try { Long.parseLong(rid.replaceFirst('^e_', '').substring(0, 8), 16) } catch (e) { 0L } }
def dueDate = { d ->
  if (d == null) return null
  def s = d.toString().trim()
  if (s ==~ /\d{12,14}/) return java.time.Instant.ofEpochMilli(Long.parseLong(s)).atZone(ZONE).toLocalDate()
  if (s ==~ /\d{4}-\d{2}-\d{2}.*/) return java.time.LocalDate.parse(s.substring(0, 10))
  return null
}
def MONTHS3 = [jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12]
// a due date stated in the text: "overdue since 21 Sep", "due 30 Sep", "due by 2026-10-04", "deadline of 3 Oct", "target date 12 Oct"
def dueFromText = { String text, java.time.LocalDate ref ->
  if (!text) return null
  def t = text.toLowerCase()
  def m = (t =~ /(?:overdue since|overdue from|due (?:on |by |date (?:of |is )?)?|deadline (?:of |on |is )?|target(?:ed)? (?:date )?(?:of |for |is )?|committed (?:for|by) )(\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)? (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?:,? \d{4})?|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?(?:,? \d{4})?)/)
  if (!m.find()) return null
  def s = m.group(1)
  try {
    if (s ==~ /\d{4}-\d{2}-\d{2}/) return java.time.LocalDate.parse(s)
    def dm = (s =~ /(\d{1,2})(?:st|nd|rd|th)? ([a-z]{3})[a-z]*(?:,? (\d{4}))?/); def md = (s =~ /([a-z]{3})[a-z]* (\d{1,2})(?:st|nd|rd|th)?(?:,? (\d{4}))?/)
    def d, mo, y
    if (dm.matches()) { d = dm.group(1) as int; mo = MONTHS3[dm.group(2)]; y = dm.group(3) }
    else if (md.matches()) { d = md.group(2) as int; mo = MONTHS3[md.group(1)]; y = md.group(3) }
    else return null
    def x = java.time.LocalDate.of(y ? (y as int) : ref.year, mo, d)
    if (!y && x.isAfter(ref.plusDays(183))) x = x.minusYears(1)   // "21 Dec" read in January means last December
    return x
  } catch (e) { return null }
}
def EXEC = /(?i)\b(ceo|cfo|cio|cto|coo|cdo|cxo|chro|ciso|cpo|cmo|md|managing director|(?:senior |executive )?vice president|svp|evp|vp|president|founder|co-founder|head of [a-z]+|director|chief [a-z]+ officer|leadership team|senior leadership|steer(?:ing)?[ -]?co(?:mmittee)?)\b/
def CLIENT = /(?i)\b(client|customer)s?\b[^.]{0,60}\b(raised|asked|requested|escalat\w*|flagged|complain\w*|demanded|pushed|insisted|reported|expressed|frustrat\w*|concern\w*)/
def roleOf = { Map p, List members ->
  def text = ((p.description ?: '') + ' ' + (p.owner ?: '')).toString()
  def low = text.toLowerCase()
  def found = (members ?: []).findAll { m -> def mp = m.properties ?: [:]
      mp.account_id == p.account_id && (mp.persona in ['client_cxo', 'client_pm']) && mp.name && (
        low.contains(mp.name.toString().toLowerCase().trim()) ||
        (mp.email && low.contains(mp.email.toString().toLowerCase().trim())) ||
        { def first = mp.name.toString().trim().split(/\s+/)[0].toLowerCase(); first.size() >= 3 && (low =~ ('\\b' + java.util.regex.Pattern.quote(first) + '\\b')).find() }()) }
    .collect { it.properties.persona }
  if ('client_cxo' in found) return 'client_cxo'
  if ('client_pm' in found) return 'client_pm'
  if ((text =~ EXEC).find()) return 'client_cxo'
  if ((text =~ CLIENT).find() || p.current_stage == 'Escalation') return 'client_pm'
  return 'internal'
}
def issueScore = { Map p, String role, java.time.LocalDate ref, java.time.LocalDate raised ->
  def t = [Escalation: 40, Risk: 20, Commitment: 10][p.current_stage]
  if (t == null) return null
  def dd = dueDate(p.due_date) ?: dueFromText(p.description?.toString(), ref)
  def age = raised ? java.time.temporal.ChronoUnit.DAYS.between(raised, ref) : 0
  t + ([client_cxo: 30, client_pm: 15][role] ?: 0) + ((dd != null && dd.isBefore(ref)) ? 30 : 0) + (age >= 60 ? 20 : (age >= 30 ? 10 : 0))
}
def roleFor = { Map p, List members -> roleOf(p, members) }
def scoreFor = { Map p, String role -> issueScore(p, role, TODAY, null) }   // stored signal_score: no age term; the daily report adds age live
"""

PLAN = COMMON + r"""
def now = System.currentTimeMillis()
def rows = binding.hasVariable('rows') && rows ? rows : []
def ucs = (binding.hasVariable('ucs') && ucs ? ucs : []).findAll { it.properties?.is_archived?.toString() != 'true' }
def members = binding.hasVariable('members') && members ? members : []
def only = (binding.hasVariable('accountIds') && accountIds) ? (accountIds instanceof List ? accountIds : accountIds.toString().split(',').collect { it.trim() }).findAll { it } as Set : null
def maxSignals = (binding.hasVariable('maxSignals') && maxSignals?.toString()?.trim()) ? (maxSignals as BigDecimal).intValue() : 500
def bySig = rows.groupBy { it.properties?.cxo_record_id }.findAll { k, v -> k }
def latest = bySig.collectEntries { k, v -> [k, v.max { oid(it.id) }] }
def needs = latest.findAll { k, r ->
  def p = r.properties
  if (only != null && !(p.account_id in only)) return false
  def ca = p.classified_at
  return ca == null || ca.toString().trim() == '' || ((r.modifiedTime ?: 0) as Long) > (ca as Long) + 120000L
}.keySet().toList().sort().take(maxSignals)
def needSet = needs as Set
def ucByAcct = ucs.groupBy { it.properties?.account_id }
def acctName = ucs.findAll { it.properties?.account }.collectEntries { [it.properties.account_id, it.properties.account] }
def ucEntry = { u -> [id: (u.properties?.usecaseId?.toString()?.trim() ?: u.id), name: u.properties?.usecase ?: '', stage: u.properties?.stage ?: ''] }
def writes = []; def batches = []
def cnt = [signals: needs.size(), auto: 0, account_level_auto: 0, sent_to_agent: 0, rescored: 0, unscorable: 0]
def payloadRows = { String sig, Map extra ->
  bySig[sig].each { r -> writes << [id: r.id, payload: (new LinkedHashMap(r.properties)) + extra] }
}
needs.groupBy { latest[it].properties.account_id }.each { acct, sigs ->
  def list = (ucByAcct[acct] ?: []).collect(ucEntry)
  if (list.size() <= 1) {
    sigs.each { s ->
      def p = latest[s].properties
      def ext = list.size() == 1 ? [use_case_ids: [list[0].id], use_case_names: [list[0].name], classification_confidence: 0.9, classification_reason: 'only use case on this account']
                                 : [use_case_ids: [], use_case_names: [], classification_confidence: 0.9, classification_reason: 'account has no use cases in db_account_usecase']
      ext.classified_at = now
      if (p.current_stage in ['Escalation', 'Risk', 'Commitment']) { def role = roleFor(p, members); ext += [raised_by_role: role, signal_score: scoreFor(p, role), scored_at: now] } else cnt.unscorable++
      payloadRows(s, ext); cnt.auto++; if (list.isEmpty()) cnt.account_level_auto++
    }
  } else {
    sigs.collate(6).each { chunk ->
      def q = [account_name: acctName[acct] ?: acct, use_cases: list, signals: chunk.collect { s -> def p = latest[s].properties; [id: s, stage: p.current_stage ?: '', description: p.description ?: ''] }]
      def sigRows = chunk.collectEntries { s -> [s, bySig[s].collect { r -> [id: r.id, props: r.properties] }] }
      batches << [account_id: acct, query: JsonOutput.toJson(q), signal_ids: chunk, use_cases: list, rows: sigRows]
      cnt.sent_to_agent += chunk.size()
    }
  }
}
// re-score signals not being classified this run, so overdue stays current
latest.each { s, r ->
  if (s in needSet) return
  def p = r.properties
  if (only != null && !(p.account_id in only)) return
  if (!(p.classified_at)) return
  if (!(p.current_stage in ['Escalation', 'Risk', 'Commitment'])) { cnt.unscorable++; return }
  def role = roleFor(p, members); def sc = scoreFor(p, role)
  if (p.raised_by_role != role || (p.signal_score as Integer) != sc) { payloadRows(s, [raised_by_role: role, signal_score: sc, scored_at: now]); cnt.rescored++ }
}
return [runStart: now, writes: writes, batches: batches, counts: cnt, members: members]
"""

PARSE = COMMON + r"""
def now = System.currentTimeMillis()
def b = binding.hasVariable('batch') ? batch : [:]
def members = binding.hasVariable('members') && members ? members : []
def texts = (binding.hasVariable('responses') && responses ? responses : []).collect { it?.text }.findAll { it }
def parsed = null
for (t in texts.reverse()) {
  def s = t.toString().trim().replaceAll(/^```(?:json)?\s*/, '').replaceAll(/\s*```$/, '')
  def i = s.indexOf('['); def j = s.lastIndexOf(']')
  if (i >= 0 && j > i) { try { parsed = new JsonSlurper().parseText(s.substring(i, j + 1)); break } catch (e) { } }
}
def ucIds = (b.use_cases ?: []).collectEntries { [it.id, it.name] }
def ans = (parsed instanceof List ? parsed : []).findAll { it instanceof Map && it.id }.collectEntries { [it.id.toString(), it] }
def writes = []; def tagged = 0, acctLevel = 0, noOutput = 0
(b.signal_ids ?: []).each { sig ->
  def rows = (b.rows ?: [:])[sig] ?: []
  def a = ans[sig]
  def latestP = rows ? rows.max { oid(it.id) }.props : [:]
  def ext
  if (a == null) { ext = [classification_reason: 'no output']; noOutput++ }
  else {
    def conf = (a.confidence ?: 0) as BigDecimal
    def ids = (a.use_case_ids ?: []).collect { it.toString() }.findAll { ucIds.containsKey(it) }.unique().take(2)
    if (conf < 0.5) ids = []
    ext = [use_case_ids: ids, use_case_names: ids.collect { ucIds[it] }, classification_confidence: conf, classification_reason: (a.reason ?: '').toString(), classified_at: now]
    if (ids) tagged++ else acctLevel++
    if (latestP.current_stage in ['Escalation', 'Risk', 'Commitment']) { def role = roleFor(latestP, members); ext += [raised_by_role: role, signal_score: scoreFor(latestP, role), scored_at: now] }
  }
  rows.each { r -> writes << [id: r.id, payload: (new LinkedHashMap(r.props)) + ext] }
}
return [writes: writes, tagged: tagged, account_level: acctLevel, no_output: noOutput, answered: ans.size()]
"""

FINAL = r"""
def rows = binding.hasVariable('rows') && rows ? rows : []
def start = (runStart as Long)
def oid = { String rid -> try { Long.parseLong(rid.replaceFirst('^e_', '').substring(0, 8), 16) } catch (e) { 0L } }
def latest = rows.groupBy { it.properties?.cxo_record_id }.findAll { k, v -> k }.collectEntries { k, v -> [k, v.max { oid(it.id) }.properties] }
def thisRun = latest.values().findAll { it.classified_at && (it.classified_at as Long) >= start }
def sent = (sentIds instanceof List ? sentIds.collectMany { (it instanceof Map ? it.signal_ids : null) ?: [] } : []) as Set
def c = counts instanceof Map ? counts : [:]
return [signals: c.signals ?: 0, tagged: thisRun.count { it.use_case_ids }, account_level: thisRun.count { !it.use_case_ids }, auto: c.auto ?: 0,
        scored: latest.values().count { it.scored_at && (it.scored_at as Long) >= start }, unscorable: c.unscorable ?: 0,
        errors: latest.findAll { k, v -> k in sent && !(v.classified_at && (v.classified_at as Long) >= start) }.size()]
"""

def fetch_all(nid, title, obj, idx, group=W.G):
    return W.node(nid, "ACTION", title, "storage_by_unifyapps", "storage_by_unifyapps_fetch_records",
                  {"object_type": obj, "numberOfRecordsToFetch": "MULTIPLE", "triggerInputCondition": {}, "shouldSearchInAnalyticsStore": False,
                   "includeCurrentUserPermissions": False, "includeRoleMappings": False, "readThroughSessionVariables": False,
                   "translationsOption": "DEFAULT", "page": {"paginateBy": "OFFSET", "limit": 1000, "offset": 0}, "includeTotalCount": True}, idx, group)
def write(nid, loop_id, idx, group):
    return W.node(nid, "ACTION", "Write row", "storage_by_unifyapps", "storage_by_unifyapps_update_record_by_id",
                  {"object_type": O_CXO, "recordId": "{{ %s.outputs.item.id }}" % loop_id, "useRawPayload": True, "upsert": False,
                   "writeThroughSessionVariables": False, "rawPayload": "{{ %s.outputs.item.payload }}" % loop_id}, idx, group)
def foreach(nid, title, ref, idx, group=W.G):
    return W.node(nid, "LOOP", title, "loop", "loop_for_each", {"listSource": "{{ %s }}" % ref, "repeatMode": "SINGLE", "captureIterations": False}, idx, group)

def definition():
    G = W.G; g1 = f"n_wl1@{G}@l"; gb = f"n_bl@{G}@l"; gw = f"n_wl2@{gb}@l"; ge = f"n_ag@{gb}@error"
    ARR = {"type": "array", "items": W.ROW}
    nodes = [
      W.start({"accountIds": {"type": "array", "items": {"type": "string"}}, "maxSignals": {"type": "number"}}, []),
      fetch_all("n_cxo", "Read signals", O_CXO, 2), fetch_all("n_uc", "Read use cases", O_UC, 3), fetch_all("n_tm", "Read team members", O_TM, 4),
      W.groovy("n_plan", "Plan: pick signals, tag 0/1-use-case accounts, re-score", PLAN,
               {"rows": W.arr("n_cxo.outputs.objects"), "ucs": W.arr("n_uc.outputs.objects"), "members": W.arr("n_tm.outputs.objects"),
                "accountIds": "{{ n_in.outputs.accountIds }}", "maxSignals": "{{ n_in.outputs.maxSignals }}"},
               {"rows": "array", "ucs": "array", "members": "array", "accountIds": "array", "maxSignals": "number"},
               {"runStart": "integer", "writes": ARR, "batches": ARR, "counts": W.ROW, "members": ARR}, 5),
      foreach("n_wl1", "Write auto-tagged and re-scored rows", "n_plan.outputs.result.writes", 6),
      write("n_w1", "n_wl1", 7, g1),
      foreach("n_bl", "For each classifier batch", "n_plan.outputs.result.batches", 8),
      W.invoke_agent("n_ag", "DB | Use Case Classifier", CLASSIFIER, "{{ n_bl.outputs.item.query }}", 9, group=gb, fallback="MANUAL"),
      W.groovy("n_agerr", "Agent call failed: leave batch for next run", "return [skipped: true]", {}, {}, {"skipped": "boolean"}, 10, group=ge),
      W.groovy("n_parse", "Parse answer, apply rules, score", PARSE,
               {"responses": W.arr("n_ag.outputs.agentResponses"), "batch": "{{ n_bl.outputs.item }}", "members": W.arr("n_plan.outputs.result.members")},
               {"responses": "array", "batch": "object", "members": "array"},
               {"writes": ARR, "tagged": "integer", "account_level": "integer", "no_output": "integer", "answered": "integer"}, 11, group=gb),
      foreach("n_wl2", "Write classified rows", "n_parse.outputs.result.writes", 12, group=gb),
      write("n_w2", "n_wl2", 13, gw),
      fetch_all("n_fin", "Re-read signals", O_CXO, 14),
      W.groovy("n_count", "Counts", FINAL,
               {"rows": W.arr("n_fin.outputs.objects"), "runStart": "{{ n_plan.outputs.result.runStart }}", "counts": "{{ n_plan.outputs.result.counts }}",
                "sentIds": "{{ n_plan.outputs.result.batches }}"},
               {"rows": "array", "runStart": "integer", "counts": "object", "sentIds": "array"},
               {k: "integer" for k in ("signals", "tagged", "account_level", "auto", "scored", "unscorable", "errors")}, 15),
      W.stop({"counts": "{{ n_count.outputs.result }}", "plan": "{{ n_plan.outputs.result.counts }}"}, 16),
    ]
    edges = [W.e("n_in", "n_cxo"), W.e("n_cxo", "n_uc"), W.e("n_uc", "n_tm"), W.e("n_tm", "n_plan"), W.e("n_plan", "n_wl1"),
             W.e("n_wl1", "n_w1", "loop"), W.e("n_w1", "n_wl1", "next", "loopback"), W.e("n_wl1", "n_bl"),
             W.e("n_bl", "n_ag", "loop"), W.e("n_ag", "n_agerr", "error", "error"), W.e("n_agerr", "n_bl", "next", "loopback"),
             W.e("n_ag", "n_parse"), W.e("n_parse", "n_wl2"), W.e("n_wl2", "n_w2", "loop"), W.e("n_w2", "n_wl2", "next", "loopback"),
             W.e("n_wl2", "n_bl", "next", "loopback"), W.e("n_bl", "n_fin"), W.e("n_fin", "n_count"), W.e("n_count", "n_out")]
    return nodes, edges
