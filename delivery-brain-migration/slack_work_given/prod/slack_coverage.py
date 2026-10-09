"""DB | Slack coverage | Daily: which accounts have no Slack channel mapped, and which mapped channels had no messages fetched in the past 30 days.
Writes one row, '__coverage__', in db_fdse_slack_engagement (JSON in recent_work); the FDSE page's Slack coverage card reads it."""
import sys, json; sys.path.insert(0, '.')
import ua, db_wf as W
import slack_eng as SE

COV = r"""
import groovy.json.JsonOutput
import java.time.*
def S = { v -> v == null ? '' : v.toString().trim() }
def L = { String n -> binding.hasVariable(n) && binding.getVariable(n) instanceof List ? binding.getVariable(n) : [] }
def now = System.currentTimeMillis(); def since = Instant.ofEpochMilli(now).minusSeconds(30L * 86400L)
def acc = L('acc').collect { [id: S(it.id), p: it.properties ?: [:]] }
def ids = acc.collect { it.id } as Set
def nameOf = acc.collectEntries { [it.id, S(it.p.account_name)] }
def byName = acc.collectEntries { [S(it.p.account_name).toLowerCase(), it.id] }
def withCh = [] as Set; def chans = [:]
L('ch').each { r -> def p = r.properties ?: [:]; def cid = S(p.channel_id)
  def aid = [S(p.acc_id), S(p.account_id)].find { ids.contains(it) } ?: byName[S(p.account_name).toLowerCase()]
  if (aid) withCh << aid
  if (cid && !chans.containsKey(cid)) chans[cid] = [channel: S(p.channel_name) ?: cid, account: aid ? nameOf[aid] : S(p.account_name)] }
// messages fetched per channel in the past 30 days, and the latest one
def msgs = [:].withDefault { 0 }; def last = [:]
L('conv').each { r -> def p = r.properties ?: [:]; def t = null; try { t = Instant.parse(S(p.message_datetime)) } catch (e) { }
  if (t != null && t.isAfter(since)) { def c = S(p.channel_id); msgs[c] = msgs[c] + 1; if (S(p.message_datetime) > S(last[c])) last[c] = S(p.message_datetime) } }
// churned accounts are left out: status 'churned' or churn_flag set on any row with that name (account_db holds some accounts twice)
def isChurn = { Map p -> S(p.status).toLowerCase() == 'churned' || S(p.churn_flag).toLowerCase() in ['true', 'yes', '1'] }
def churned = acc.findAll { isChurn(it.p) }.collect { S(it.p.account_name).toLowerCase() } as Set
def live = acc.findAll { !churned.contains(S(it.p.account_name).toLowerCase()) }.unique { S(it.p.account_name).toLowerCase() }
// channels of churned accounts are left out too; channels with no account stay
def chList = chans.findAll { k, v -> !churned.contains(S(v.account).toLowerCase()) }.collect { k, v -> [channel: v.channel, account: S(v.account), msgs: msgs.containsKey(k) ? msgs[k] : 0, last: S(last[k])] }
  .sort { a, b -> ((a.msgs > 0 ? 1 : 0) <=> (b.msgs > 0 ? 1 : 0)) ?: (a.account.toLowerCase() <=> b.account.toLowerCase()) ?: (a.channel <=> b.channel) }
def chByAcc = [:].withDefault { [] as LinkedHashSet }
chans.each { k, v -> if (S(v.account)) chByAcc[S(v.account).toLowerCase()] << k }
// accounts are matched by name, so a channel on either copy of a duplicated account covers it
def accList = live.collect { a -> def nm = S(a.p.account_name); def cs = (chByAcc.containsKey(nm.toLowerCase()) ? chByAcc[nm.toLowerCase()] : []) as List
  [name: nm, status: S(a.p.status), channels: cs.collect { chans[it].channel }.join(', '), n_ch: cs.size(), msgs: cs.sum { msgs.containsKey(it) ? msgs[it] : 0 } ?: 0,
   last: cs.collect { S(last[it]) }.max() ?: ''] }
  .sort { a, b -> ((a.n_ch > 0 ? 1 : 0) <=> (b.n_ch > 0 ? 1 : 0)) ?: ((a.msgs > 0 ? 1 : 0) <=> (b.msgs > 0 ? 1 : 0)) ?: (a.name.toLowerCase() <=> b.name.toLowerCase()) }
def noCh = accList.findAll { it.n_ch == 0 }.collect { [name: it.name, status: it.status] }.sort { a, b -> (a.status <=> b.status) ?: (a.name.toLowerCase() <=> b.name.toLowerCase()) }
def quiet = chList.findAll { it.msgs == 0 }.collect { [channel: it.channel, account: it.account] }
def cov = [accounts: live.size(), accounts_with: live.size() - noCh.size(), churned_left_out: churned.size(), no_channel: noCh, channels: chList.size(), quiet: quiet,
           acc_list: accList, ch_list: chList, updated_at: now]
return [row: [email: '__coverage__', band: '__coverage__', name: 'Slack coverage', recent_work: JsonOutput.toJson(cov), updated_at: now],
        summary: [accounts: live.size(), no_channel: noCh.size(), channels: chList.size(), quiet: quiet.size()]]
"""

def wf(cron):
    st = W.schedule_start(cron); st["inputs"]["timezone"] = "Asia/Kolkata"
    nodes = [st, SE.fetch("n_acc", "Accounts", "account_db", 2), SE.fetch("n_ch", "Slack channels", "slack_channel", 3),
             SE.fetch("n_conv", "Slack conversations", "db_slack_conversations", 4),
             W.groovy("n_cov", "Accounts without channels, channels without messages", COV,
                      {"acc": W.arr("n_acc.outputs.objects"), "ch": W.arr("n_ch.outputs.objects"), "conv": W.arr("n_conv.outputs.objects")},
                      {"acc": "array", "ch": "array", "conv": "array"}, {"row": {"type": "object"}, "summary": {"type": "object"}}, 5),
             SE.upsert("n_w", "db_fdse_slack_engagement", None, 6, id_expr="__coverage__", row_expr="{{ n_cov.outputs.result.row }}"),
             W.stop("{{ n_cov.outputs.result.summary }}", 7)]
    order = ["n_in", "n_acc", "n_ch", "n_conv", "n_cov", "n_w", "n_out"]
    return nodes, [W.e(a, b) for a, b in zip(order, order[1:])]

if __name__ == "__main__":
    ua.ensure_session()
    nodes, edges = wf("35 7 * * *")
    wid, ver, viol = W.save("DB | Slack coverage | Daily", "Daily 07:35 IST: accounts with no Slack channel mapped (churned accounts left out) and mapped channels with no messages in the past 30 days, for the FDSE page's Slack coverage card.",
                            nodes, edges, wid=SE.reg().get("slack_coverage"))
    SE.reg_set("slack_coverage", wid); print("saved", wid, ver, viol)
    if not viol: print("deployed", W.deploy(wid, "Slack coverage"))
    if "--run" in sys.argv:
        r = W.test(wid, {}, nodes=("n_cov",), timeout_s=200)
        print(r.get("status"), r.get("failed"), json.dumps((((r.get("nodes") or {}).get("n_cov") or {}).get("outputs") or {}).get("result", {}).get("summary")))
