"""new-account-360: data-bound Account 360 page (page inputs account_id / account_name).

Data: account_db, db_account_daily_report, db_usecase_daily_report, db_team_members,
each read by one page-level storage fetch data source with a JS transformer.
Type scale: four theme variants only (text-xs, text-sm, text-md, display-xs); no font-size CSS.
"""
import sys, json, re, random, string; sys.path.insert(0, '.')
import sales, ua, db_wf as W

APP = "e-69f9786e285b7c092e6d2749"
PAGE_ID = "e_6abb7c4c26a1877b272b26fd"
REG = "a360_ds.json"

# ---------------------------------------------------------------- data sources
JS_ROWS = """const rows = Array.isArray(data) ? data
  : (data && Array.isArray(data.objects)) ? data.objects
  : (data && data.properties) ? [data] : [];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const fmtD = e => {
  if (e === null || e === undefined || e === '') return '';
  const d = new Date(Number(e) + 19800000);   // IST
  return d.getUTCDate() + ' ' + MON[d.getUTCMonth()] + ' ' + d.getUTCFullYear();
};
const tone = s => ({green: 'G', g: 'G', amber: 'A', a: 'A', yellow: 'A', red: 'R', r: 'R'})[String(s || '').trim().toLowerCase()] || 'N';
const cap = s => s ? String(s).charAt(0).toUpperCase() + String(s).slice(1) : '';
"""

JS = {
"account": JS_ROWS + """
const p = (rows[0] && rows[0].properties) || {};
const money = v => {
  const n = Number(v);
  if (!n) return '—';
  return n >= 1e6 ? '$' + parseFloat((n / 1e6).toFixed(2)) + 'M' : n >= 1e5 ? '$' + Math.round(n / 1e3) + 'K' : '$' + parseFloat((n / 1e3).toFixed(1)) + 'K';
};
const rag = tone(p.rag_status || p.ahd_rag_status);
const days = p.renewalDate ? Math.round((Number(p.renewalDate) - Date.now()) / 86400000) : null;
return {
  found: rows.length ? 'yes' : 'no',
  name: p.account_name || '',
  meta: [p.industry || p.vertical, p.region, p.stage].filter(Boolean).join(' · '),
  people: [p.accountOwner ? 'Owner ' + p.accountOwner : '', p.programManager ? 'PM ' + p.programManager : ''].filter(Boolean).join(' · '),
  arr: money(p.arr || p.hs_arr),
  renewal: p.renewalDate ? 'Renews ' + fmtD(p.renewalDate) : 'No renewal date',
  days: days === null ? '—' : String(days),
  days_tone: days === null ? 'N' : days < 90 ? 'R' : days < 180 ? 'A' : 'G',
  rag: rag,
  rag_label: {G: 'Green', A: 'Amber', R: 'Red', N: 'Not set'}[rag],
  status: cap(p.status || '')
};""",

"report": JS_ROWS + """
let best = null;
rows.forEach(r => {
  const d = Number((r.properties || {}).report_date || 0);
  if (!best || d > Number(best.properties.report_date || 0)) best = r;
});
const p = best ? best.properties : {};
const lines = String(p.account_summary || '').split('\\n').map(s => s.trim()).filter(Boolean).map((s, i) => {
  const m = s.match(/^(Critical|New|Stuck|Decision):\\s*(.*)$/i);
  return {id: 'l' + i, label: m ? cap(m[1].toLowerCase()) : '', text: m ? m[2] : s};
});
const stageTone = {Escalation: 'R', Risk: 'A', Commitment: 'N'};
const items = (p.top_items || []).map((t, i) => ({
  id: 'i' + i,
  stage: t.current_stage || '',
  tone: stageTone[t.current_stage] || 'N',
  meta: [t.cxo_record_id, (t.signal_score === null || t.signal_score === undefined) ? '' : 'score ' + t.signal_score].filter(Boolean).join(' · '),
  desc: t.description || ''
}));
const num = v => String(Number(v || 0));
return {
  found: best ? 'yes' : 'no',
  date: best ? 'Report ' + fmtD(p.report_date) : 'No report yet',
  headline: p.headline || '',
  lines: lines,
  health: (p.health_score === null || p.health_score === undefined) ? '—' : 'Score ' + Number(p.health_score).toFixed(1),
  rag: tone(p.health_rag),
  rag_label: cap(p.health_rag) || '—',
  override: p.rag_override_reason ? 'Raised to amber: ' + p.rag_override_reason : '',
  esc: num(p.open_escalations), risks: num(p.open_risks), comms: num(p.open_commitments),
  new_count: num(p.new_since_yesterday),
  sentiment: (p.sentiment_score === null || p.sentiment_score === undefined || p.sentiment_score === '') ? '—' : String(Math.round(Number(p.sentiment_score))),
  items: items,
  item_count: String(items.length),
  version: p.scoring_version || ''
};""",

"usecases": JS_ROWS + """
let max = 0;
rows.forEach(r => { const d = Number((r.properties || {}).report_date || 0); if (d > max) max = d; });
const rank = {R: 0, A: 1, G: 2, N: 3};
const plural = (n, w) => n ? n + ' ' + w + (n > 1 ? 's' : '') : '';
const list = rows.filter(r => Number((r.properties || {}).report_date || 0) === max).map(r => {
  const p = r.properties || {};
  const f = tone(p.health_flag);
  return {
    id: r.id,
    name: p.usecase_name || p.usecase_id || '',
    stage: p.stage || '',
    flag: f,
    flag_label: cap(p.health_flag) || '—',
    health: (p.health_score === null || p.health_score === undefined) ? '' : 'Score ' + Number(p.health_score).toFixed(1),
    counts: [plural(Number(p.escalations || 0), 'escalation'), plural(Number(p.risks || 0), 'risk'), plural(Number(p.commitments || 0), 'commitment')].filter(Boolean).join(' · '),
    summary: p.usecase_summary || '',
    _r: rank[f], _h: Number(p.health_score || 0)
  };
}).sort((a, b) => (a._r - b._r) || (a._h - b._h)).map((x, i) => Object.assign(x, {id: 'u' + i}));
const c = k => list.filter(x => x.flag === k).length;
return {
  found: list.length ? 'yes' : 'no',
  list: list,
  sub: list.length ? list.length + ' with open signals · ' + c('R') + ' red · ' + c('A') + ' amber · ' + c('G') + ' green' : 'No use case has an open signal'
};""",

"resolve": JS_ROWS + """
const p = (rows[0] && rows[0].properties) || {};
return {account_id: p.account_id || ''};""",

"team": JS_ROWS + """
const pretty = s => String(s || '').replace(/_/g, ' ');
const isExt = p => p.is_external === true || String(p.is_external).toLowerCase() === 'true';
const seen = {};
const people = [];
rows.map(r => r.properties || {}).forEach(p => {
  const name = String(p.name || '').trim();
  if (!name || /^test\\d*$/i.test(name)) return;
  const key = (isExt(p) ? 'x:' : 'i:') + name.toLowerCase();
  const role = [p.role, pretty(p.persona)].filter(s => s && !/^\\d+$/.test(String(s))).join(' · ');
  if (seen[key]) { if (role && seen[key].role.indexOf(role) < 0) seen[key].role = [seen[key].role, role].filter(Boolean).join(' · '); return; }
  seen[key] = {name: name, role: role, ext: isExt(p)};
  people.push(seen[key]);
});
const client = people.filter(p => p.ext).sort((a, b) => a.name.localeCompare(b.name)).map((x, i) => Object.assign({}, x, {id: 'c' + i}));
const internal = people.filter(p => !p.ext).sort((a, b) => a.name.localeCompare(b.name)).map((x, i) => Object.assign({}, x, {id: 'p' + i}));
return {
  client: client, internal: internal,
  client_count: String(client.length), internal_count: String(internal.length),
  has_client: client.length ? 'yes' : 'no', has_internal: internal.length ? 'yes' : 'no'
};""",
}

DS = {  # key: (name, object, limit, filter field) -- "resolve" must stay first
    "resolve": ("a360_resolve_account", "db_account_usecase", 1, "properties_account"),
    "account": ("a360_account", "account_db", 1, "properties_company_id"),
    "report": ("a360_account_report", "db_account_daily_report", 400, "properties_account_id"),
    "usecases": ("a360_usecase_reports", "db_usecase_daily_report", 1000, "properties_account_id"),
    "team": ("a360_team_members", "db_team_members", 500, "properties_account_id"),
}

def ds_props(key, version, page_id, res_id, prefix=""):
    name, obj, limit, field = DS[key]
    if key == "resolve":
        value, dpon = "{{ pageInputs['account_name'] }}", [{"id": "pageInputs", "p": ["pageInputs['account_name']"]}]
    else:   # account_id from the page input, else resolved from the account name
        value = "{{ pageInputs['account_id'] || " + res_id + "['data']['account_id'] }}"
        dpon = [{"id": "pageInputs", "p": ["pageInputs['account_id']"]}, {"id": res_id, "p": [res_id + "['data']['account_id']"]}]
    return {
        "name": prefix + name, "type": "APPLICATION", "target": "page", "interfaceId": APP, "interfacePageId": page_id,
        "context": {"appName": "storage_by_unifyapps", "resourceName": "storage_by_unifyapps_fetch_records", "resourceVersion": version},
        "inputs": {"triggerInputCondition": {"filters": [{"property": field, "filter": {"operator": "EQUAL", "value": value}}], "operator": "AND"},
                   "shouldSearchInAnalyticsStore": False, "object_type": obj, "includeRoleMappings": False, "includeCurrentUserPermissions": False,
                   "translationsOption": "DEFAULT", "page": {"paginateBy": "OFFSET", "limit": limit}, "numberOfRecordsToFetch": "MULTIPLE",
                   "readThroughSessionVariables": False, "includeTotalCount": False},
        "dP": [{"p": "inputs.triggerInputCondition.filters[0].filter.value"}],
        "dpOn": dpon,
        "metadata": {"isManuallyRenamed": True},
        "callbacks": {"successEvents": [], "failureEvents": []},
        "advancedOptions": {"refetchOnWindowFocus": True, "timing": {"runQueryOnPageLoad": False, "runQueryPeriodically": False}, "runBehaviour": "automatic"},
        "options": {"transformerConfig": {"enabled": True, "includeOriginalOutput": True, "inputs": {"code": JS[key], "compile_static": False},
                    "context": {"type": "APPLICATION", "appName": "code_by_unifyapps", "resourceName": "code_by_unifyapps_javascript"},
                    "fallbackMode": "FAIL", "id": "transformer", "type": "javascript"}},
    }

def upsert_datasources(page_id=PAGE_ID, reg_path=REG, prefix=""):
    reg = json.load(open(reg_path)) if __import__("os").path.exists(reg_path) else {}
    version = W.V("storage_by_unifyapps", "storage_by_unifyapps_fetch_records")
    for key in DS:
        props = ds_props(key, version, page_id, reg.get("resolve"), prefix)
        if key in reg:
            cur = ua.call("GET", f"/api/entity/e_data_source/{reg[key]}")
            ua.call("POST", "/api/entity/update", {**cur, "properties": props})
        else:
            reg[key] = ua.call("POST", "/api/entity", {"entityType": "e_data_source", "properties": props})["id"]
        json.dump(reg, open(reg_path, "w"), indent=1)
    return reg

# ---------------------------------------------------------------- blocks
TONE_TAG = [("R", "error"), ("A", "warning"), ("G", "success")]
TONE_HEX = {"R": "#AC3D3DFF", "A": "#C88724FF", "G": "#28734AFF"}
LAB = "color:var(--a3-mute) !important; letter-spacing:.12em; text-transform:uppercase; margin:0;"
MUTE = "color:var(--a3-mute) !important;"
CARD = "background:var(--a3-card); border:1px solid var(--a3-line); border-radius:12px; padding:16px 24px; min-width:0;"
REF = re.compile(r"(e_[0-9a-f]{24}|b_[A-Za-z0-9]{5}|pageInputs)((?:\['[^']*'\])+)")

def cond(expr, value, op="EQUAL"):
    return {"type": "filter", "payload": {"filters": [{"property": expr, "filter": {"operator": op, "value": value}}], "operator": "AND"}}

class Page:
    def __init__(self, existing=None, prefix=""):
        self.blocks = dict(existing or {})
        self.counter, self.prefix, self.new = {}, prefix, []
        self.names = {b.get("displayName") for b in self.blocks.values()}
    def _id(self):
        while True:
            i = "b_" + "".join(random.choices(string.ascii_letters + string.digits, k=5))
            if i not in self.blocks: return i
    def add(self, parent, ctype, appearance, content, css=None, name=None, visible=None):
        bid = self._id()
        self.counter[ctype] = self.counter.get(ctype, 0) + 1
        dn = self.prefix + (name or f"{ctype.lower()}{self.counter[ctype]}")
        while dn in self.names: dn += "_"
        self.names.add(dn)
        b = {"id": bid, "displayName": dn, "parentId": parent, "component": {"componentType": ctype, "appearance": appearance, "content": content},
             "visibility": visible or {"value": True}, "v": 0, "dpOn": [], "dataSourceIds": []}
        if css: b["additional"] = {"customCSS": f"[data-block-id='{bid}'] {{ {css} }}", "isCustomCSSValid": True}
        self.blocks[bid] = b; self.new.append(bid)
        if parent:
            p = self.blocks[parent]["component"]["content"]
            if "blockIds" in p: p["blockIds"].insert(len(p["blockIds"]) - 1, bid)
            elif self.blocks[parent]["component"]["componentType"] == "Repeatable": p["blockId"] = bid   # its single template
        return bid
    def stack(self, parent, direction="column", css=None, name=None, align="stretch", justify="flex-start", visible=None):
        return self.add(parent, "Stack", {"direction": direction, "alignItems": align, "justifyContent": justify, "wrapContent": False,
            "reverseOrder": False, "theme": "inherit", "styles": {"gap": {"all": "gap-none"}, "padding": {"all": "p-0"}, "backgroundColor": "bg-transparent"}},
            {"blockIds": ["__PLACEHOLDER__"]}, css, name, visible)
    def text(self, parent, value, variant="text-sm", weight="regular", css="", name=None, color=None, visible=None):
        assert variant in ("text-xs", "text-sm", "text-md", "display-xs")
        return self.add(parent, "Typography", {"variant": variant, "weight": weight, "color": color or "text-primary", "align": "left"},
                        {"type": "PLAIN_TEXT", "value": value}, "margin:0; color:var(--a3-ink); " + css, name, visible)
    def tag(self, parent, label, tone_expr, visible=None):
        color = {"conditionalValueFilters": [{"propertyValue": pv, "conditions": cond(tone_expr, k)} for k, pv in TONE_TAG], "defaultValue": "gray"}
        return self.add(parent, "Tag", {"color": color, "size": "sm", "variant": "subtle", "shape": "rounded", "decorators": {}},
                        {"label": label}, "width:fit-content; letter-spacing:.08em; text-transform:uppercase;", visible=visible)
    def repeat(self, parent, data_expr, name, gap="gap-xs"):
        rid = self.add(parent, "Repeatable", {"layout": "list", "direction": "vertical", "styles": {"gap": {"all": gap}},
                       "separator": {"enabled": False, "appearance": {"styles": {"backgroundColor": "bg-quaternary", "width": {"custom": "1px"}}}}},
                       {"data": data_expr, "autoSelect": "none", "blockId": None, "scrollable": False, "primaryKey": {"key": "id", "path": "id"}}, None, name)
        return rid

def toned(expr):   # Typography colour driven by a G/A/R tone field
    return {"conditionalValueFilters": [{"propertyValue": {"custom": TONE_HEX[k]}, "conditions": cond(expr, k)} for k in "RAG"], "defaultValue": "text-primary"}

def show_if(expr, value="yes", op="EQUAL"):
    return {"value": "conditions", "conditions": cond(expr, value, op)}

def wire(blocks, ds_ids):
    """Fill dP / cP / dpOn / dataSourceIds from the {{ }} expressions each block holds."""
    def walk(x, path, out):
        if isinstance(x, dict):
            for k, v in x.items(): walk(v, f"{path}.{k}" if path else k, out)
        elif isinstance(x, list):
            for i, v in enumerate(x): walk(v, f"{path}[{i}]", out)
        elif isinstance(x, str) and "{{" in x: out.append((path, x))
    for b in blocks.values():
        found = []
        walk({"component": b["component"], "visibility": b["visibility"]}, "", found)
        if not found: continue
        dp, cp, deps = [], [], {}
        for path, s in found:
            p = path.split(".", 1)[1] if path.startswith("component.") else path
            dp.append({"p": p})
            m = re.search(r"^(.*conditionalValueFilters\[\d+\]\.conditions|visibility\.conditions)\.", p)
            if m and {"p": m.group(1)} not in cp: cp.append({"p": m.group(1)})
            for ref, tail in REF.findall(s):
                deps.setdefault(ref, [])
                if ref + tail not in deps[ref]: deps[ref].append(ref + tail)
        b["dP"] = dp
        if cp: b["cP"] = cp
        b["dpOn"] = [{"id": k, "p": v} for k, v in deps.items()]
        b["dataSourceIds"] = [k for k in deps if k in ds_ids]

def build(ds, pg=None, panel=None, export_ds=None):
    """Standalone page (pg None) or, with pg/panel, the same content inside an existing tab panel."""
    A, R, U, T = (f"{ds[k]}['data']" for k in ("account", "report", "usecases", "team"))
    e = lambda base, *keys: "{{ " + base + "".join(f"['{k}']" for k in keys) + " }}"
    if pg is not None:
        return build_body(pg, panel, A, R, U, T, e, ds, export_ds)
    pg = Page()
    for fixed in ("root_id", "header_id", "footer_id"):
        pg.blocks[fixed] = {"id": fixed, "displayName": {"root_id": "body", "header_id": "header", "footer_id": "footer"}[fixed],
            "component": {"componentType": "Stack", "appearance": {"direction": "column", "alignItems": "stretch", "justifyContent": "flex-start",
            "wrapContent": False, "reverseOrder": False, "theme": "inherit", "styles": {"gap": {"all": "gap-none"}, "padding": {"all": "p-0"},
            "width": "w-full"}}, "content": {"blockIds": ["__PLACEHOLDER__"]}}, "additional": {"isRootBlock": True},
            "visibility": {"value": True}, "dpOn": [], "dataSourceIds": []}
    pg.blocks["root_id"]["additional"].update(customCSS="[data-block-id='root_id'] { background:var(--a3-bg); min-height:100%; }", isCustomCSSValid=True)

    # ---- header bar
    hdr = pg.stack("root_id", "row", "background:var(--a3-bar); flex-wrap:wrap; align-items:baseline; gap:4px 16px; padding:12px 24px;", "header_bar", align="baseline")
    BAR = "color:var(--a3-barink) !important;"
    pg.text(hdr, "{{ " + f"{A}['name'] || pageInputs['account_name'] || pageInputs['account_id']" + " }}", "text-md", "semi-bold", BAR, "account_name")
    pg.text(hdr, e(A, "meta"), "text-xs", css=BAR + " opacity:.8;")
    pg.text(hdr, e(A, "people"), "text-xs", css=BAR + " opacity:.8;")
    pg.text(hdr, e(R, "date"), "text-xs", css=BAR + " opacity:.8; margin-left:auto;", name="report_date")

    main = pg.stack("root_id", "column", "padding:24px; gap:16px; width:100%;", "main")
    return build_body(pg, main, A, R, U, T, e, ds, None)

def build_body(pg, main, A, R, U, T, e, ds, export_ds):
    if export_ds:   # tab: toolbar with account line, report date and the export button
        tb = pg.stack(main, "row", "flex-wrap:wrap; align-items:center; gap:4px 16px;", "toolbar", align="center")
        pg.text(tb, "{{ " + f"{A}['name'] || pageInputs['account_name']" + " }}", "text-md", "semi-bold")
        pg.text(tb, e(A, "meta"), "text-xs", css=MUTE)
        pg.text(tb, e(A, "people"), "text-xs", css=MUTE)
        pg.text(tb, e(R, "date"), "text-xs", css=MUTE + " margin-left:auto;")
        btn = pg.add(tb, "Button", {"color": "brand", "size": "sm", "variant": "outline", "styles": {"width": "w-fit"}},
                     {"contentMode": "text", "value": "Export PDF", "type": "default"}, name="export_button")
        pg.blocks[btn]["component"]["slots"] = {}
        pg.blocks[btn]["events"] = [{"eventType": "onClick", "id": "evt_" + pg._id()[2:],
            "action": {"actionType": "controlDataSource", "executionType": "delay", "id": "act_" + pg._id()[2:],
                       "payload": {"dataSourceId": export_ds, "method": "trigger"}}}]
    note = pg.stack(main, "column", CARD, "no_report", visible=show_if(e(R, "found"), "no"))
    pg.text(note, "No daily report for this account yet. DB | Daily Account Report writes one at 23:00 IST for every account with at least one open signal.", "text-sm", css=MUTE)

    # ---- KPI strip
    kpi = pg.stack(main, "row", CARD + " display:grid !important; grid-template-columns:repeat(6,minmax(0,1fr)); padding:16px 0;", "kpi")
    def cell(i, label):
        c = pg.stack(kpi, "column", "padding:0 24px; gap:4px; align-items:flex-start;" + ("" if i == 0 else " border-left:1px solid var(--a3-line);"), f"kpi_{i}", align="flex-start")
        pg.text(c, label, "text-xs", css=LAB); return c
    c = cell(0, "Delivery health"); pg.tag(c, e(R, "rag_label"), e(R, "rag")); pg.text(c, e(R, "health"), "text-xs", css=MUTE)
    c = cell(1, "Account RAG"); pg.tag(c, e(A, "rag_label"), e(A, "rag")); pg.text(c, e(A, "status"), "text-xs", css=MUTE)
    c = cell(2, "ARR"); pg.text(c, e(A, "arr"), "display-xs", "medium")
    c = cell(3, "Days to renewal"); pg.text(c, e(A, "days"), "display-xs", "medium", color=toned(e(A, "days_tone"))); pg.text(c, e(A, "renewal"), "text-xs", css=MUTE)
    c = cell(4, "Sentiment"); pg.text(c, e(R, "sentiment"), "display-xs", "medium"); pg.text(c, "Latest score", "text-xs", css=MUTE)
    c = cell(5, "New since yesterday"); pg.text(c, e(R, "new_count"), "display-xs", "medium"); pg.text(c, "signals", "text-xs", css=MUTE)

    # ---- row 1: where it stands / open signals
    r1 = pg.stack(main, "row", "display:grid !important; grid-template-columns:minmax(0,2fr) minmax(0,1fr); gap:16px;", "row1")
    st = pg.stack(r1, "column", CARD + " gap:8px;", "status")
    pg.text(st, "Where it stands", "text-xs", css=LAB)
    pg.text(st, e(R, "headline"), "text-md", "semi-bold")
    rl = pg.repeat(st, e(R, "lines"), "summary_lines", "gap-sm")
    line = pg.stack(rl, "row", "display:grid !important; grid-template-columns:80px minmax(0,1fr); gap:8px; align-items:baseline;", "summary_line", align="baseline")
    pg.text(line, "{{ " + rl + "['context']['item']['label'] }}", "text-xs", "semi-bold", LAB)
    pg.text(line, "{{ " + rl + "['context']['item']['text'] }}", "text-sm")

    sg = pg.stack(r1, "column", CARD + " gap:8px;", "open_signals")
    pg.text(sg, "Open signals", "text-xs", css=LAB)
    g = pg.stack(sg, "row", "display:grid !important; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px;", "signal_counts")
    for key, label in (("esc", "escalations"), ("risks", "risks"), ("comms", "commitments")):
        c = pg.stack(g, "column", "gap:2px;")
        pg.text(c, e(R, key), "display-xs", "medium")
        pg.text(c, label, "text-xs", css=MUTE)
    pg.text(sg, e(R, "override"), "text-xs", css="color:var(--a3-a) !important;", visible=show_if(e(R, "override"), "", "NOT_EQUAL"))

    # ---- use cases
    uc = pg.stack(main, "column", CARD, "use_cases")
    h = pg.stack(uc, "row", "justify-content:space-between; flex-wrap:wrap; gap:8px; margin-bottom:8px;", justify="space-between")
    pg.text(h, "Use cases", "text-xs", css=LAB); pg.text(h, e(U, "sub"), "text-xs", css=MUTE)
    GRID = "display:grid !important; grid-template-columns:minmax(0,1.3fr) 110px minmax(0,1fr) minmax(0,2.2fr); gap:16px; align-items:start;"
    hd = pg.stack(uc, "row", GRID + " padding:8px 0; border-bottom:1px solid var(--a3-line);", "uc_head", visible=show_if(e(U, "found")))
    for x in ("Use case", "Health", "Open signals", "Summary"): pg.text(hd, x, "text-xs", css=LAB)
    ru = pg.repeat(uc, e(U, "list"), "uc_rows")
    it = lambda k: "{{ " + ru + "['context']['item']['" + k + "'] }}"
    row = pg.stack(ru, "row", GRID + " padding:12px 0; border-bottom:1px solid var(--a3-line);", "uc_row")
    c = pg.stack(row, "column", "gap:2px; min-width:0;"); pg.text(c, it("name"), "text-sm", "medium"); pg.text(c, it("stage"), "text-xs", css=MUTE)
    c = pg.stack(row, "column", "gap:4px; align-items:flex-start;", align="flex-start"); pg.tag(c, it("flag_label"), it("flag")); pg.text(c, it("health"), "text-xs", css=MUTE)
    pg.text(row, it("counts"), "text-xs", css=MUTE)
    pg.text(row, it("summary"), "text-sm", css="white-space:pre-line;")

    # ---- row 3: top items / team
    r3 = pg.stack(main, "row", "display:grid !important; grid-template-columns:minmax(0,3fr) minmax(0,2fr); gap:16px; align-items:start;", "row3")
    ti = pg.stack(r3, "column", CARD, "top_items")
    h = pg.stack(ti, "row", "justify-content:space-between; gap:8px; margin-bottom:8px;", justify="space-between")
    pg.text(h, "Top open items", "text-xs", css=LAB); pg.text(h, e(R, "item_count"), "text-xs", css=MUTE)
    rt = pg.repeat(ti, e(R, "items"), "item_rows")
    it = lambda k: "{{ " + rt + "['context']['item']['" + k + "'] }}"
    row = pg.stack(rt, "row", "display:grid !important; grid-template-columns:110px minmax(0,1fr); gap:16px; padding:12px 0; border-top:1px solid var(--a3-line); align-items:start;", "item_row")
    pg.tag(row, it("stage"), it("tone"))
    c = pg.stack(row, "column", "gap:2px; min-width:0;"); pg.text(c, it("desc"), "text-sm"); pg.text(c, it("meta"), "text-xs", css=MUTE)

    tm = pg.stack(r3, "column", CARD + " gap:8px;", "team")
    pg.text(tm, "Team", "text-xs", css=LAB)
    for key, label in (("client", "Client"), ("internal", "UnifyApps")):
        h = pg.stack(tm, "row", "gap:8px; align-items:baseline; margin-top:8px;", align="baseline")
        pg.text(h, label, "text-sm", "semi-bold"); pg.text(h, e(T, f"{key}_count"), "text-xs", css=MUTE)
        pg.text(tm, "No one listed in db_team_members", "text-xs", css=MUTE, visible=show_if(e(T, f"has_{key}"), "no"))
        rp = pg.repeat(tm, e(T, key), f"team_{key}")
        it = lambda k, rp=rp: "{{ " + rp + "['context']['item']['" + k + "'] }}"
        p = pg.stack(rp, "column", "gap:0; padding:6px 0; border-top:1px solid var(--a3-line);", f"person_{key}")
        pg.text(p, it("name"), "text-sm", "medium"); pg.text(p, it("role"), "text-xs", css=MUTE, visible=show_if(it("role"), "", "NOT_EQUAL"))

    pg.text(main, "Sources: DB Account Daily Report, DB Usecase Daily Report, account_db, db_team_members.", "text-xs", css=MUTE, name="sources")
    wire({k: pg.blocks[k] for k in pg.new}, set(ds.values()))
    return pg

def header_css(pg):
    by = {b["displayName"]: bid for bid, b in pg.blocks.items() if bid in pg.new}
    s = lambda n: f"[data-block-id='{by[pg.prefix + n]}']"
    return ("<style>\n:root{--a3-bg:var(--bg-workspace,#F5F3EE);--a3-card:var(--bg-primary,#FFFFFF);--a3-bar:var(--bg-brand-solid,#1F3226);"
            "--a3-barink:var(--text-primary_on-brand,#F5F3EE);--a3-nt:var(--bg-secondary,#EEECE7);--a3-line:var(--border-tertiary,#E5E2DB);"
            "--a3-ink:var(--text-primary,#1E1E1B);--a3-mute:var(--text-secondary,#6E6A61);--a3-g:#28734A;--a3-a:#C88724;--a3-r:#AC3D3D;--a3-n:#8C877C;}\n"
            f"@media (max-width:900px){{{s('row1')},{s('row3')}{{grid-template-columns:minmax(0,1fr) !important;}}"
            f"{s('kpi')}{{grid-template-columns:repeat(3,1fr) !important; row-gap:16px;}}"
            f"{s('uc_head')}{{display:none !important;}}{s('uc_row')}{{grid-template-columns:1fr 1fr !important;}}}}\n"
            f"@media (max-width:560px){{{s('kpi')}{{grid-template-columns:1fr 1fr !important;}}}}\n</style>")

def push(pg):
    cur = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": PAGE_ID, "allowedEntityTypes": ["e_component"]})["entity"]
    props = dict(cur["properties"])
    props["blocks"] = pg.blocks
    props["name"] = props["documentTitle"] = "Account 360 · Daily Report"
    props["customCode"] = {**(props.get("customCode") or {}), "header": header_css(pg)}
    props["metadata"] = {**props.get("metadata", {}), "_blockCounter": pg.counter}
    ent = {**cur, "properties": props}
    r = ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
                {"entity": ent, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": APP}]})
    return r

if __name__ == "__main__":
    ua.ensure_session()
    ds = upsert_datasources()
    print("data sources:", ds)
    pg = build(ds)
    json.dump({"blocks": pg.blocks, "header": header_css(pg)}, open("a360_bound_page.json", "w"), indent=1)
    if "--push" in sys.argv:
        r = push(pg)
        print("pushed:", [(x.get("id"), x.get("version")) for x in (r if isinstance(r, list) else [r])])
    print("blocks:", len(pg.blocks), pg.counter)
