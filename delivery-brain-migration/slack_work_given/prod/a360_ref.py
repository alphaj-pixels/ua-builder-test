"""Account 360 in the reference layout (the attached Assurant HTML), bound to live data.

One callable data source (DB | Account 360 | Data) feeds every block. Colours that depend on data are
set through htmlAttributes (data-a3-*) and header CSS. Type scale: text-xs, text-sm, text-md, display-xs.
Targets: the standalone page new-account-360 (also what the PDF export renders) and the Account 360 tab
in account-detail's tabs2 (with an Export PDF button).
"""
import sys, json, re, os; sys.path.insert(0, '.')
import sales, ua, db_wf as W
from a360_bound import Page, cond

APP = "e-69f9786e285b7c092e6d2749"
STANDALONE = "e_6abb7c4c26a1877b272b26fd"
DETAIL = "e_6a8967af7d2a63661b1ae68b"
TABS = "b_ck1Ez"
TAB_LABEL = "Account 360"
WF = json.load(open("a360_wf.json"))
REG = "a360_ref_ds.json"

LAB = "color:var(--a3-mute) !important; letter-spacing:.12em; text-transform:uppercase;"
MUTE = "color:var(--a3-mute) !important;"
CARD = "background:var(--a3-card); border:1px solid var(--a3-line); border-radius:12px; padding:16px 24px; min-width:0;"
VARIANTS = ("text-xs", "text-sm", "text-md", "display-xs")
REF = re.compile(r"(e_[0-9a-f]{24}|b_[A-Za-z0-9]{5}|pageInputs)((?:\['[^']*'\])+)")

# ------------------------------------------------------------------ data sources
def ds_props(key, page_id):
    ver = W.V("callables", "callables_call_automation")
    params = {"accountId": "{{ pageInputs['account_id'] }}", "accountName": "{{ pageInputs['account_name'] }}"}
    p = {"name": {"data": "a360_view", "pdf": "a360_export_pdf"}[key] + ("" if page_id == STANDALONE else "_tab"),
         "type": "APPLICATION", "target": "page", "interfaceId": APP, "interfacePageId": page_id,
         "context": {"appName": "callables", "resourceName": "callables_call_automation", "resourceVersion": ver},
         "inputs": {"automationId": WF[key], "runtimeConnections": {}, "version": "-1", "parameters": params, "synchronous": True, "executeOnSameVM": False},
         "dP": [{"p": "inputs.parameters.accountId"}, {"p": "inputs.parameters.accountName"}],
         "dpOn": [{"id": "pageInputs", "p": ["pageInputs['account_id']", "pageInputs['account_name']"]}],
         "metadata": {"isManuallyRenamed": True}, "options": {},
         "callbacks": {"successEvents": [], "failureEvents": []},
         "advancedOptions": {"refetchOnWindowFocus": False, "timing": {"runQueryOnPageLoad": False, "runQueryPeriodically": False},
                             "runBehaviour": "automatic" if key == "data" else "manual"}}
    return p

def upsert_ds(page_id, keys):
    reg = json.load(open(REG)) if os.path.exists(REG) else {}
    out = {}
    for key in keys:
        rk = f"{page_id}:{key}"
        props = ds_props(key, page_id)
        if rk not in reg:
            reg[rk] = ua.call("POST", "/api/entity", {"entityType": "e_data_source", "properties": props})["id"]
            json.dump(reg, open(REG, "w"), indent=1)
        if key == "pdf":   # opens the PDF link (an attachment, so the browser downloads it)
            me = reg[rk]
            props["callbacks"] = {
                "successEvents": [{"id": "evt_a3pdfok", "eventType": "onSuccess", "action": {"id": "act_a3pdfok", "actionType": "navigate", "executionType": "delay",
                    "payload": {"path": "{{ " + me + "['data']['url'] }}", "history": "push", "preserveSearchParams": False, "target": "_blank"}}}],
                "failureEvents": [{"id": "evt_a3pdfko", "eventType": "onFailure", "action": {"id": "act_a3pdfko", "actionType": "showNotification", "executionType": "delay",
                    "payload": {"title": "The PDF export failed. Please try again.", "type": "error", "autoHideDuration": 6000}}}]}
        cur = ua.call("GET", f"/api/entity/e_data_source/{reg[rk]}")
        ua.call("POST", "/api/entity/update", {**cur, "properties": props})
        out[key] = reg[rk]
    return out

# ------------------------------------------------------------------ block helpers
class P(Page):
    def text(self, parent, value, variant="text-xs", weight="regular", css="", name=None, attrs=None, visible=None):
        assert variant in VARIANTS
        b = self.add(parent, "Typography", {"variant": variant, "weight": weight, "color": "text-primary", "align": "left"},
                     {"type": "PLAIN_TEXT", "value": value}, "margin:0; color:var(--a3-ink); " + css, name, visible)
        if attrs: self.attrs(b, attrs)
        return b
    def attrs(self, bid, attrs):
        add = self.blocks[bid].setdefault("additional", {})
        add["htmlAttributes"] = [{"key": k, "value": v} for k, v in attrs.items()]
    def box(self, parent, css, attrs=None, name=None, direction="column", visible=None):
        if parent in self.blocks and self.blocks[parent]["component"]["componentType"] == "Repeatable": css = "width:100%; " + css
        b = self.stack(parent, direction, css, name, visible=visible)
        if attrs: self.attrs(b, attrs)
        return b
    def pill(self, parent, label, tone, big=False):
        return self.text(parent, label, "text-md" if big else "text-xs", "medium",
                         "padding:2px %dpx !important;" % (14 if big else 10), attrs={"data-a3-pill": tone})
    def repeat(self, parent, data, name, grid=None, gap="gap-none"):
        app = {"layout": "grid", "columns": grid, "styles": {"gap": {"all": gap}}} if grid else \
              {"layout": "list", "direction": "vertical", "styles": {"gap": {"all": gap}},
               "separator": {"enabled": False, "appearance": {"styles": {"backgroundColor": "bg-quaternary", "width": {"custom": "1px"}}}}}
        return self.add(parent, "Repeatable", app, {"data": data, "autoSelect": "none", "blockId": None, "scrollable": False,
                        "primaryKey": {"key": "id", "path": "id"}}, "width:100%;", name)

def wire(blocks, ds_ids):
    def walk(x, path, out):
        if isinstance(x, dict):
            for k, v in x.items(): walk(v, f"{path}.{k}" if path else k, out)
        elif isinstance(x, list):
            for i, v in enumerate(x): walk(v, f"{path}[{i}]", out)
        elif isinstance(x, str) and "{{" in x: out.append((path, x))
    for b in blocks.values():
        found = []
        walk({"component": b["component"], "visibility": b["visibility"],
              "additional": {"htmlAttributes": (b.get("additional") or {}).get("htmlAttributes", [])}}, "", found)
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

# ------------------------------------------------------------------ layout (mirrors a360_build.py)
def build(pg, root, ds, pdf_ds=None):
    V = f"{ds}['data']['view']"
    v = lambda *k: "{{ " + V + "".join(f"['{x}']" for x in k) + " }}"
    it = lambda rep, k: "{{ " + rep + "['context']['item']['" + k + "'] }}"
    def lab(parent, left, right=None, right_attrs=None):
        row = pg.box(parent, "justify-content:space-between; gap:8px; flex-wrap:wrap; margin-bottom:8px;", direction="row")
        pg.text(row, left, css=LAB)
        if right: pg.text(row, right, css="letter-spacing:.04em; " + ("" if right_attrs else MUTE), attrs=right_attrs)
        return row

    # header bar
    hdr = pg.box(root, "background:var(--a3-bar); flex-wrap:wrap; align-items:center; gap:8px 24px; padding:8px 24px;", name="header_bar", direction="row")
    BAR = "color:var(--a3-barink) !important;"
    pg.text(hdr, v("header", "name"), "text-md", "semi-bold", BAR)
    pg.text(hdr, v("header", "sub"), css=BAR + " opacity:.75;")
    right = pg.box(hdr, "margin-left:auto; gap:16px; align-items:center;", direction="row")
    pg.text(right, v("header", "asof"), css=BAR + " opacity:.75;")
    if pdf_ds:
        btn = pg.add(right, "Button", {"color": "brand", "size": "sm", "variant": "outline", "styles": {"width": "w-fit"}},
                     {"contentMode": "text", "value": "Export PDF", "type": "default"}, "background:var(--a3-card) !important;", name="export_pdf")
        pg.blocks[btn]["component"]["slots"] = {}
        pg.blocks[btn]["events"] = [
            {"id": "evt_a3pdf1", "eventType": "onClick", "action": {"id": "act_a3pdf1", "actionType": "showNotification", "executionType": "delay",
             "payload": {"title": "Preparing the PDF. It downloads in about 30 seconds.", "type": "info", "autoHideDuration": 6000}}},
            {"id": "evt_a3pdf2", "eventType": "onClick", "action": {"id": "act_a3pdf2", "actionType": "controlDataSource", "executionType": "delay",
             "payload": {"dataSourceId": pdf_ds, "method": "trigger"}}}]

    main = pg.box(root, "padding:24px; gap:16px; width:100%;", name="main")

    # KPI strip
    kpi = pg.box(main, CARD + " display:grid !important; grid-template-columns:repeat(5,minmax(0,1fr)); padding:16px 0;", name="kpi", direction="row")
    def cell(i, label):
        c = pg.box(kpi, "padding:0 24px; gap:4px; align-items:flex-start;" + ("" if i == 0 else " border-left:1px solid var(--a3-line);"))
        pg.text(c, label, css=LAB); return c
    pg.pill(cell(0, "Delivery health"), v("kpi", "delivery"), v("kpi", "delivery_tone"), big=True)
    pg.pill(cell(1, "Renewal health"), v("kpi", "renewal"), v("kpi", "renewal_tone"), big=True)
    pg.text(cell(2, "ARR"), v("kpi", "arr"), "display-xs", "medium")
    c = cell(3, "Days to renewal"); pg.text(c, v("kpi", "days"), "display-xs", "medium", attrs={"data-a3-fg": v("kpi", "days_tone")}); pg.text(c, v("kpi", "renew_date"), css=MUTE)
    pg.pill(cell(4, "Client sentiment"), v("kpi", "sentiment"), v("kpi", "sentiment_tone"), big=True)

    # summary
    sb = pg.box(main, CARD + " border-left:6px solid var(--a3-n);", {"data-a3-bl": v("status", "tone")}, name="summary")
    lab(sb, "Summary")
    pg.text(sb, v("summary"), "text-md", css="white-space:pre-line;")

    # row 1: status / value / voice
    r1 = pg.box(main, "display:grid !important; grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr); gap:16px;", name="row1", direction="row")
    st = pg.box(r1, CARD + " border-left:6px solid var(--a3-n);", {"data-a3-bl": v("status", "tone")}, name="status")
    lab(st, "Where it stands")
    pg.text(st, v("status", "sub"), css=MUTE)
    pg.text(st, v("status", "headline"), "text-md", "semi-bold", "margin:8px 0 4px !important;")
    pg.text(st, v("status", "line"), "text-sm", css=MUTE + " white-space:pre-line;")
    vc = pg.box(r1, CARD, name="value")
    lab(vc, "Value")
    kv = pg.box(vc, "align-items:baseline; gap:8px; margin:4px 0 8px;", direction="row")
    pg.text(kv, v("value", "big"), "display-xs", "medium"); pg.text(kv, v("value", "lab"), css=MUTE)
    pg.text(vc, v("value", "note"), "text-sm")
    pg.text(vc, v("value", "pipeLab"), css=MUTE + " margin-top:8px !important;")
    vo = pg.box(r1, CARD, name="voice")
    lab(vo, "Voice of customer", v("voice", "band_label"), {"data-a3-fg": v("voice", "tone")})
    seg = pg.box(vo, "display:grid !important; grid-template-columns:repeat(5,1fr); gap:3px; margin-top:4px;", direction="row")
    for i in range(5): pg.box(seg, "height:8px; border-radius:4px; background:var(--a3-nt); flex:none;", {"data-a3-bg": v("voice", f"seg{i}")})
    ends = pg.box(vo, "justify-content:space-between; margin:4px 0 16px;", direction="row")
    pg.text(ends, "Very negative", css=MUTE); pg.text(ends, "Very positive", css=MUTE)
    pg.text(vo, v("voice", "q"), "text-sm", css="font-style:italic;")
    pg.text(vo, v("voice", "by"), css=MUTE + " margin-top:4px !important;")

    # use cases
    uc = pg.box(main, CARD, name="use_cases")
    lab(uc, "Use cases", v("uc", "sub"))
    pg.text(uc, v("uc", "line"), "text-sm", css="margin:0 0 8px !important;")
    fr = pg.repeat(uc, v("uc", "funnel"), "funnel", grid=4, gap="gap-lg")
    stg = pg.box(fr, "padding:8px 16px; border-radius:10px; border:1px solid var(--a3-line); margin:8px 0 16px;")
    top = pg.box(stg, "justify-content:space-between; align-items:baseline;", direction="row")
    pg.text(top, it(fr, "name"), css=LAB); pg.text(top, it(fr, "count"), "display-xs", "medium")
    bar = pg.box(stg, "height:6px; border-radius:3px; overflow:hidden; background:var(--a3-nt); margin-top:8px;", direction="row")
    for k, t in (("g", "G"), ("a", "A"), ("r", "R"), ("n", "N")):
        pg.box(bar, "height:100%;", {"data-a3-bg": t, "data-a3-grow": it(fr, k)})
    pg.text(stg, it(fr, "flag_text"), css="margin-top:4px !important; min-height:18px;", attrs={"data-a3-fg": it(fr, "flag_tone")})
    lst = pg.box(uc, "border-top:1px solid var(--a3-line); padding-top:16px;", name="uc_list")
    ur = pg.repeat(lst, v("uc", "rows"), "uc_rows")
    row = pg.box(ur, "display:grid !important; grid-template-columns:minmax(0,1.3fr) 72px 84px minmax(0,1.6fr); gap:8px; align-items:center; padding:6px 0; border-bottom:1px solid var(--a3-line);", name="uc_row", direction="row")
    n = pg.box(row, "align-items:center; gap:6px; min-width:0;", direction="row")
    pg.box(n, "width:8px; height:8px; border-radius:50%; flex:none;", {"data-a3-bg": it(ur, "st")})
    pg.text(n, it(ur, "n"), "text-sm", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    trk = pg.box(row, "display:grid !important; grid-template-columns:repeat(4,1fr); gap:2px;", direction="row")
    for i in range(4): pg.box(trk, "height:5px; border-radius:3px; flex:none;", {"data-a3-bg": it(ur, f"t{i}")})
    pg.text(row, it(ur, "lbl"), css="letter-spacing:.08em; text-transform:uppercase;", attrs={"data-a3-fg": it(ur, "st")})
    pg.text(row, it(ur, "p"), css=MUTE + " white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")

    # row 3: escalations, risks, commitments / since last update
    r3 = pg.box(main, "display:grid !important; grid-template-columns:minmax(0,3fr) minmax(0,2fr); gap:16px; align-items:start;", name="row3", direction="row")
    left = pg.box(r3, CARD, name="escalations_card")
    lab(left, "Escalations, risks and commitments")
    sm = pg.box(left, "background:var(--a3-bg); border-radius:10px; padding:16px; margin:0 0 16px;")
    pg.text(sm, v("esc", "line"), "text-sm", css="margin:0 0 16px !important;")
    sr = pg.repeat(sm, v("esc", "stats"), "esc_stats", grid=4, gap="gap-lg")
    cst = pg.box(sr, "gap:2px;")
    b = pg.box(cst, "align-items:baseline; gap:4px;", direction="row")
    pg.text(b, it(sr, "val"), "display-xs", "medium", attrs={"data-a3-fg": it(sr, "tone")})
    pg.text(b, it(sr, "of"), "text-sm", css=MUTE)
    pg.text(cst, it(sr, "label"), css=MUTE)

    def section(title, count_key, note, head, cols, rows_key, cells):
        sec = pg.box(left, "margin-top:24px;")
        h = pg.box(sec, "align-items:baseline; gap:8px; margin:0 0 4px;", direction="row")
        pg.text(h, title, "text-md", "semi-bold")
        pg.text(h, v("esc", count_key), css="padding:0 8px; border-radius:999px; background:var(--a3-nt);")
        pg.text(h, note, css=MUTE)
        grid = f"display:grid !important; grid-template-columns:{cols}; align-items:start;"
        hd = pg.box(sec, grid, direction="row")
        for i, x in enumerate(head):
            pg.text(hd, x, css=LAB + " padding:8px 8px 8px 0; border-bottom:1px solid var(--a3-line);" + (" text-align:right; padding-right:0;" if i == len(head) - 1 else ""))
        pg.text(sec, "None open.", css=MUTE + " padding-top:12px;", visible={"value": "conditions", "conditions": cond(v("esc", count_key), "0")})
        rp = pg.repeat(sec, v("esc", rows_key), f"{rows_key}_rows")
        rg = pg.box(rp, grid, direction="row")
        for i, fn in enumerate(cells):
            last = i == len(cells) - 1
            td = pg.box(rg, "padding:16px 8px 16px 0; border-bottom:1px solid var(--a3-line); height:100%;" + (" align-items:flex-end; padding-right:0; text-align:right;" if last else ""))
            if last: pg.blocks[td]["component"]["appearance"]["alignItems"] = "flex-end"
            fn(td, lambda k, rp=rp: it(rp, k))
    def e1(td, g):
        t = pg.box(td, "align-items:center; gap:6px;", direction="row")
        pg.box(t, "width:8px; height:8px; border-radius:50%; flex:none;", {"data-a3-bg": g("tone")}); pg.text(t, g("h"), "text-sm", "medium")
        pg.text(td, g("p"), css=MUTE + " margin-top:2px !important;")
        pg.text(td, g("ch"), css=MUTE + " margin-top:4px !important;")
    def e3(td, g):
        pg.text(td, g("days"), "display-xs", "medium", "text-align:right;", attrs={"data-a3-fg": g("tone")})
        pg.text(td, g("dnote"), css=MUTE + " text-align:right; margin-top:2px !important;")
    section("Escalations", "n_esc", "Stuck now, need a push", ["Escalation", "Waiting on", "Days stuck"], "minmax(0,1fr) 120px 110px", "escalations",
            [e1, lambda td, g: pg.text(td, g("wait")), e3])
    def rk1(td, g): pg.text(td, g("h"), "text-sm", "medium"); pg.text(td, g("p"), css=MUTE + " margin-top:2px !important;")
    section("Risks", "n_risk", "Could hurt later", ["Risk", "Level", "Depends on", "Open since"], "minmax(0,1fr) 90px 120px 100px", "risks",
            [rk1, lambda td, g: pg.pill(td, g("lvl_label"), g("lvl")), lambda td, g: pg.text(td, g("wait")), lambda td, g: pg.text(td, g("since"), css="text-align:right;")])
    def c1(td, g): pg.text(td, g("h"), "text-sm", "medium"); pg.text(td, g("note"), css=MUTE + " margin-top:2px !important;")
    def c4(td, g): pg.pill(td, g("st_label"), g("st")); pg.text(td, g("late"), css=MUTE + " text-align:right; margin-top:2px !important;")
    section("Commitments", "n_comm", v("esc", "comm_note"), ["Commitment", "Owner", "Due", "Status"], "minmax(0,1fr) 110px 90px 100px", "commitments",
            [c1, lambda td, g: pg.text(td, g("by")), lambda td, g: pg.text(td, g("due")), c4])

    rc = pg.box(r3, CARD, name="since_last_update")
    lab(rc, "Since last update")
    pg.text(rc, v("chg", "sum"), "text-sm", css="margin:0 0 8px !important;")
    cr = pg.repeat(rc, v("chg", "items"), "chg_rows")
    li = pg.box(cr, "display:grid !important; grid-template-columns:56px 1fr; gap:8px; padding:8px 0; border-top:1px solid var(--a3-line);", direction="row")
    pg.text(li, it(cr, "d"), css=MUTE + " padding-top:2px;")
    tl = pg.box(li, "gap:6px; align-items:baseline;", direction="row")
    pg.text(tl, it(cr, "sym"), "text-sm", attrs={"data-a3-fg": it(cr, "tone")})
    pg.text(tl, it(cr, "t"), "text-sm")
    pg.text(main, v("src"), css=MUTE + " padding:0 0 8px;", name="sources")
    wire({k: pg.blocks[k] for k in pg.new}, {ds} | ({pdf_ds} if pdf_ds else set()))

def header_css(pg, root_sel):
    by = {b["displayName"]: bid for bid, b in pg.blocks.items() if bid in pg.new}
    s = lambda n: f"[data-block-id='{by[pg.prefix + n]}']"
    tones = "".join(
        f"[data-a3-bg='{t}']{{background:var(--a3-{c}) !important;}}"
        f"[data-a3-fg='{t}'],[data-a3-fg='{t}'] *{{color:var(--a3-{c}) !important;}}"
        f"[data-a3-bl='{t}']{{border-left-color:var(--a3-{c}) !important;}}"
        f"[data-a3-pill='{t}']{{background:var(--a3-{c}t) !important;}}[data-a3-pill='{t}'],[data-a3-pill='{t}'] *{{color:var(--a3-{c}) !important;}}"
        for t, c in (("G", "g"), ("A", "a"), ("R", "r"), ("N", "n")))
    grow = "".join(f"[data-a3-grow='{i}']{{flex:{i} 1 0 !important; width:auto !important;}}" for i in range(1, 121))
    rules = []
    for b in pg.new:
        a = pg.blocks[b].get("additional")
        if a:
            rules.append(a.pop("customCSS", "")); a.pop("isCustomCSSValid", None)
            if not a: pg.blocks[b].pop("additional")
    rules = "\n".join(r for r in rules if r)
    return ("<style>\n:root{--a3-bg:var(--bg-workspace,#F5F3EE);--a3-card:var(--bg-primary,#FFFFFF);--a3-bar:var(--bg-brand-solid,#1F3226);"
            "--a3-barink:var(--text-primary_on-brand,#F5F3EE);--a3-nt:var(--bg-secondary,#EEECE7);--a3-line:var(--border-tertiary,#E5E2DB);"
            "--a3-ink:var(--text-primary,#1E1E1B);--a3-mute:var(--text-secondary,#6E6A61);"
            "--a3-g:#28734A;--a3-a:#C88724;--a3-r:#AC3D3D;--a3-n:#8C877C;--a3-gt:#E6F0EA;--a3-at:#F7EEDD;--a3-rt:#F4E4E4;}\n"
            f"{root_sel}{{background:var(--a3-bg);}}\n"
            "[data-a3-bg='X']{background:var(--a3-nt) !important;}[data-a3-fg='M'],[data-a3-fg='M'] *{color:var(--a3-mute) !important;}"
            "[data-a3-pill]{border-radius:999px; letter-spacing:.1em; text-transform:uppercase; width:fit-content; display:inline-block;}"
            "[data-a3-grow]{flex:0 0 0 !important; width:0;}" + tones + grow + "\n"
            + rules + "\n"
            f"@media (max-width:900px){{{s('row1')},{s('row3')}{{grid-template-columns:minmax(0,1fr) !important;}}"
            f"{s('kpi')}{{grid-template-columns:repeat(3,1fr) !important; row-gap:16px;}}}}\n"
            f"@media (max-width:560px){{{s('kpi')}{{grid-template-columns:1fr 1fr !important;}}}}\n</style>")

PUSHED = "a360_pushed_versions.json"
def push(page_id, props, cur):
    seen = json.load(open(PUSHED)) if os.path.exists(PUSHED) else {}
    if page_id in seen and cur.get("version") != seen[page_id] and "--force" not in sys.argv:
        raise SystemExit(f"{page_id} changed since my last save (v{seen[page_id]} -> v{cur.get('version')}); not overwriting. Re-run with --force once checked.")
    r = _push(page_id, props, cur)
    seen[page_id] = max(x.get("version", 0) for x in r if x.get("id") == page_id); json.dump(seen, open(PUSHED, "w"))
    return r
def _push(page_id, props, cur):
    return ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
                   {"entity": {**cur, "properties": props}, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": APP}]})

def standalone():
    ds = upsert_ds(STANDALONE, ["data"])
    cur = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": STANDALONE, "allowedEntityTypes": ["e_component"]})["entity"]
    pg = P()
    for fixed in ("root_id", "header_id", "footer_id"):
        pg.blocks[fixed] = {"id": fixed, "displayName": {"root_id": "body", "header_id": "header", "footer_id": "footer"}[fixed],
            "component": {"componentType": "Stack", "appearance": {"direction": "column", "alignItems": "stretch", "justifyContent": "flex-start",
            "wrapContent": False, "reverseOrder": False, "theme": "inherit", "styles": {"gap": {"all": "gap-none"}, "padding": {"all": "p-0"},
            "width": "w-full"}}, "content": {"blockIds": ["__PLACEHOLDER__"]}}, "additional": {"isRootBlock": True},
            "visibility": {"value": True}, "dpOn": [], "dataSourceIds": []}
    build(pg, "root_id", ds["data"])
    props = dict(cur["properties"])
    props["customCode"] = {**(props.get("customCode") or {}), "header": header_css(pg, "[data-block-id='root_id']")}
    props["blocks"] = pg.blocks
    props["metadata"] = {**props.get("metadata", {}), "_blockCounter": pg.counter}
    r = push(STANDALONE, props, cur)
    return ds, len(pg.new), [(x.get("id"), x.get("version")) for x in r]

def tab():
    ds = upsert_ds(DETAIL, ["data", "pdf"])
    cur = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": DETAIL, "allowedEntityTypes": ["e_component"]})["entity"]
    props = dict(cur["properties"]); blocks = props["blocks"]
    tabs = blocks[TABS]["component"]["content"]
    pos = next((i for i, x in enumerate(tabs["items"]) if x.get("label") == TAB_LABEL), None)
    old = tabs["items"][pos] if pos is not None else None
    if old:   # replace the earlier Account 360 tab in place
        gone, stack = set(), [old["blockId"]]
        while stack:
            b = stack.pop()
            if b in blocks and b not in gone:
                gone.add(b); c = blocks[b]["component"].get("content") or {}
                stack += [x for x in c.get("blockIds", []) if x != "__PLACEHOLDER__"] + ([c["blockId"]] if c.get("blockId") else [])
        for b in gone: blocks.pop(b)
    pg = P(existing=blocks, prefix="a360_")
    panel = pg.box(TABS, "gap:0;", name="tab_panel")
    build(pg, panel, ds["data"], ds["pdf"])
    item = dict(old) if old else {"__id": "item_uid_" + pg._id()[2:], "label": TAB_LABEL}
    tid = item.get("value") or "tab_" + pg._id()[2:]
    item.update({"value": tid, "id": tid, "blockId": panel})
    if pos is not None: tabs["items"][pos] = item
    else: tabs["items"].append(item)
    keep = re.findall(r"<!-- w360:start -->.*?<!-- w360:end -->", (props.get("customCode") or {}).get("header") or "", flags=re.S)   # Weekly 360 tab's CSS
    props["customCode"] = {**(props.get("customCode") or {}), "header": header_css(pg, f"[data-block-id='{panel}']") + "".join("\n" + k for k in keep)}
    props["blocks"] = pg.blocks
    counter = dict(props.get("metadata", {}).get("_blockCounter", {}))
    for k, c in pg.counter.items(): counter[k] = counter.get(k, 0) + c
    props["metadata"] = {**props.get("metadata", {}), "_blockCounter": counter}
    r = push(DETAIL, props, cur)
    json.dump({"panel": panel, "tab": tid, "new_blocks": pg.new, "ds": ds}, open("a360_ref_tab_state.json", "w"), indent=1)
    return ds, tid, len(pg.new), [(x.get("id"), x.get("version")) for x in r]

if __name__ == "__main__":
    ua.ensure_session()
    if "standalone" in sys.argv: print("standalone:", standalone())
    if "tab" in sys.argv: print("tab:", tab())
