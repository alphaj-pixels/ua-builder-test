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
  if (cid && !chans.containsKey(cid)) chans[cid] = [channel: S(p.channel_name) ?: cid, account: S(p.account_name) ?: (aid ? nameOf[aid] : '')] }
def seen = [] as Set
L('conv').each { r -> def p = r.properties ?: [:]; def t = null; try { t = Instant.parse(S(p.message_datetime)) } catch (e) { }; if (t != null && t.isAfter(since)) seen << S(p.channel_id) }
// accounts are matched by name too: account_db holds some accounts twice, and a channel on either copy covers the account
def withName = acc.findAll { withCh.contains(it.id) }.collect { S(it.p.account_name).toLowerCase() } as Set
// churned accounts are left out: status 'churned' or churn_flag set on any row with that name
def isChurn = { Map p -> S(p.status).toLowerCase() == 'churned' || S(p.churn_flag).toLowerCase() in ['true', 'yes', '1'] }
def churned = acc.findAll { isChurn(it.p) }.collect { S(it.p.account_name).toLowerCase() } as Set
def live = acc.findAll { !churned.contains(S(it.p.account_name).toLowerCase()) }.unique { S(it.p.account_name).toLowerCase() }
def noCh = live.findAll { !withName.contains(S(it.p.account_name).toLowerCase()) }.collect { [name: S(it.p.account_name), status: S(it.p.status)] }
  .sort { a, b -> (a.status <=> b.status) ?: (a.name.toLowerCase() <=> b.name.toLowerCase()) }
def quiet = chans.findAll { k, v -> !seen.contains(k) }.collect { k, v -> v }.sort { a, b -> (a.account.toLowerCase() <=> b.account.toLowerCase()) ?: (a.channel <=> b.channel) }
def cov = [accounts: live.size(), accounts_with: live.size() - noCh.size(), churned_left_out: churned.size(), no_channel: noCh, channels: chans.size(), quiet: quiet, updated_at: now]
return [row: [email: '__coverage__', band: '__coverage__', name: 'Slack coverage', recent_work: JsonOutput.toJson(cov), updated_at: now],
        summary: [no_channel: noCh.size(), channels: chans.size(), quiet: quiet.size()]]
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
