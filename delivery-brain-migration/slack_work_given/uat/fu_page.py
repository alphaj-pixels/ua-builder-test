"""FDSE utilisation page for leaders (Delivery Brain app). Data: DB | FDSE Utilisation Page | Data.
A leader sees the people below them in the manager chain; admins see everyone. Click a leader to filter to their direct reports.
"""
import sys, json, os, re, time, copy; sys.path.insert(0, '.')
import sales, ua, db_wf as W
import a360_ref as R
R.REF = re.compile(r"(e_[0-9a-f]{24}|b_[A-Za-z0-9]{5}|pageInputs|var_[A-Za-z0-9]+)((?:\['[^']*'\])+)")
from a360_ref import P, cond
import attn_page as AP, rbac

APP = R.APP
REG = "fu_page.json"
TITLE, SLUG = "FDSE utilisation", "fdse-utilisation"
WF = json.load(open("db_automations.json"))["fdse_page"]
V_MGR = "var_fumgr"
V_VIEW = "var_fuview"
DUO = "['sumeet@unifyapps.com', 'alpha.jose@unifyapps.com'].includes(String(userContext['email'] || '').toLowerCase())"
LAB = "font-size:12px !important; letter-spacing:.2em; text-transform:uppercase; color:var(--fu-muted) !important;"
MUTE = "color:var(--fu-muted) !important;"
SERIF = "font-family:'Spectral',Georgia,serif !important;"

def reg(): return json.load(open(REG)) if os.path.exists(REG) else {}
def save_reg(r): json.dump(r, open(REG, "w"), indent=1)

def ensure_page():
    r = reg()
    if r.get("page"): return r["page"]
    props = {"componentType": "PAGE", "interfaceId": APP, "name": TITLE, "slug": SLUG, "publicAccess": False, "interfaceType": "application",
             "documentTitle": TITLE, "layout": {"body": "root_id", "header": "header_id", "footer": "footer_id"}, "blocks": AP.fixed_blocks(),
             "pageVariables": {}, "dataSources": {}, "flags": {"shouldUseBuiltDependencies": True}, "eligibleOverrides": [],
             "inputSchema": {"schema": {"additionalProperties": False, "type": "object", "properties": {}, "required": []},
                             "layout": {"ui:order": [], "ua:valueSemanticsVersion": 2}, "dynamic": False, "type": "SCHEMA_AND_LAYOUT"},
             "outputSchema": {"type": "SCHEMA_AND_LAYOUT", "dynamic": False}, "metadata": {"_version": 2}}
    app = ua.call("GET", f"/api/entity/e_interface/{APP}")
    app["properties"]["entityDetailsMap"] = {**(app["properties"].get("entityDetailsMap") or {}), "NEW_ENTITY_ID": {"slug": SLUG, "isPublic": False, "type": "PAGE", "name": TITLE}}
    res = ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
                  {"entity": {"entityType": "e_component", "properties": props}, "requestType": "CREATED",
                   "parentEntities": [{"type": "e_interface", "id": APP}], "postUpdateEntities": [app]})
    res = res if isinstance(res, list) else [res]
    pid = next(x["id"] for x in res if x.get("id", "").startswith("e_") and x["id"] != APP)
    # the placeholder key must become the real page id (seen before with the attention page)
    app = ua.call("GET", f"/api/entity/e_interface/{APP}"); edm = app["properties"].get("entityDetailsMap") or {}
    if "NEW_ENTITY_ID" in edm:
        edm[pid] = edm.pop("NEW_ENTITY_ID"); ua.call("POST", "/api/entity/update", app)
    r["page"] = pid; save_reg(r)
    return pid

def ensure_ds(pid):
    r = reg(); rk = "ds"
    props = {"name": "fu_view", "type": "APPLICATION", "target": "page", "interfaceId": APP, "interfacePageId": pid,
             "context": {"appName": "callables", "resourceName": "callables_call_automation", "resourceVersion": W.V("callables", "callables_call_automation")},
             "inputs": {"automationId": WF, "runtimeConnections": {}, "version": "-1", "synchronous": True, "executeOnSameVM": False,
                        "parameters": {"viewer": "{{ String(userContext['email'] || '').toLowerCase() }}", "admin": "{{ (" + rbac.ADM + ") ? 'true' : 'false' }}",
                                       "manager": "", "focus": "{{ " + V_MGR + "['value'] || '' }}"}},
             "dP": [{"p": "inputs.parameters.viewer"}, {"p": "inputs.parameters.admin"}, {"p": "inputs.parameters.manager"}, {"p": "inputs.parameters.focus"}],
             "dpOn": [{"id": "userContext", "p": ["userContext['email']", "userContext['roles']"]}, {"id": V_MGR, "p": [V_MGR + "['value']"]}],
             "metadata": {"isManuallyRenamed": True}, "options": {}, "callbacks": {"successEvents": [], "failureEvents": []},
             "advancedOptions": {"refetchOnWindowFocus": False, "timing": {"runQueryOnPageLoad": True, "runQueryPeriodically": False}, "runBehaviour": "automatic"}}
    if rk not in r:
        r[rk] = ua.call("POST", "/api/entity", {"entityType": "e_data_source", "properties": props})["id"]; save_reg(r)
    cur = ua.call("GET", f"/api/entity/e_data_source/{r[rk]}")
    ua.call("POST", "/api/entity/update", {**cur, "properties": props})
    return r[rk]

def setvar(var, value, eid):
    return {"id": "act_" + eid, "actionType": "setPageVariable", "executionType": "delay",
            "payload": {"variableId": var, "method": "setPageVariable", "operationDetails": {"operation": "SET", "value": value}}}

TM_BASE = "/p/0/interfaces/task-management-application-clone/preview/"

def tm_link(rp_item):
    """URL of the person's page in the Task Management app: Lead Detail when they have a team, FDSE Detail otherwise."""
    q = lambda k: "encodeURIComponent(String(" + rp_item + "['" + k + "'] || ''))"
    return ("{{ (location['origin'] || '') + '" + TM_BASE + "' + (" + rp_item + "['has_team'] === 'yes' ? 'lead-detail' : 'lead-detail-_O0WDw') + '?tabNo=0&fdeName=' + " + q("name") +
            " + '&fdeMail=' + " + q("email") + " + '&managerMail=' + " + q("manager_email") + " + '&designation=' + " + q("designation") +
            " + '&utlisation=' + " + q("pct_s") + " + '&accounts=' + " + q("accounts") + " + '&accountsNo=' + " + q("accounts_n") + " + '&fdes=' + " + q("directs_n") + " }}")

def go_tm(rp_item, eid):
    return {"id": "act_" + eid, "actionType": "navigate", "executionType": "delay",
            "payload": {"path": tm_link(rp_item), "history": "push", "preserveSearchParams": False, "target": "_self"}}

def _acts(x): return x if isinstance(x, list) else [x]

def build(pg, ds, tm_nav=None):
    """tm_nav(item_expr, eid) -> action opening the person's page; default: the Task Management app in a new tab."""
    tm_nav = tm_nav or go_tm
    D = lambda *k: "{{ " + ds + "['data']" + "".join(f"['{x}']" for x in k) + " }}"
    it = lambda rep, k: "{{ " + rep + "['context']['item']['" + k + "'] }}"
    t = lambda parent, value, variant="text-sm", weight="regular", css="", **kw: pg.text(parent, value, variant, weight, css, **kw)
    FOC = ds + "['data']['tier']['focus']"
    root = pg.box("root_id", "padding:32px 64px 48px; gap:0; min-height:100vh;", name="page")
    inner = pg.box(root, "max-width:1240px; width:100%; gap:0;", name="inner")
    t(inner, "DELIVERY CONTROL TOWER", "text-xs", css="letter-spacing:.24em; color:var(--fu-red) !important; margin:8px 0 4px !important;")
    t(inner, "FDSE utilisation, this week", "display-xs", "medium", SERIF + " font-size:32px !important;")
    t(inner, "{{ " + ds + "['data']['window'] ? (" + ds + "['data']['window'] + ' · one level at a time: open a person to see the people under them') : 'Loading…' }}", "text-md", css=MUTE + " margin-top:4px !important;")
    # breadcrumb
    cr = pg.repeat(inner, D("tier", "crumbs"), "crumbs", gap="gap-xs")
    pg.blocks[cr]["component"]["appearance"].update({"layout": "list", "direction": "horizontal"})
    cb = pg.box(cr, "align-items:center; gap:6px; cursor:pointer;", direction="row", name="crumb")
    pg.blocks[cb]["events"] = [{"id": "evt_fucrumb", "eventType": "onClick", "action": setvar(V_MGR, it(cr, "email"), "fucrumb")}]
    t(cb, it(cr, "name"), "text-sm", "semi-bold", "white-space:nowrap;", attrs={"data-fu-crumb": it(cr, "last")})
    t(cb, "›", "text-sm", css=MUTE, visible={"value": "conditions", "conditions": cond(it(cr, "last"), "no")})
    # focus card
    fc = pg.box(inner, "background:var(--fu-card); border:1px solid var(--fu-line); border-radius:16px; padding:24px 32px; gap:16px; margin-top:16px; justify-content:space-between; align-items:flex-start; flex-wrap:wrap;", direction="row", name="focus")
    fl = pg.box(fc, "gap:4px; min-width:0;")
    t(fl, "{{ " + FOC + "['name'] }}", "display-xs", "medium", SERIF + " font-size:28px !important;")
    t(fl, "{{ " + FOC + "['designation'] + (" + FOC + "['accounts'] ? ' · ' + " + FOC + "['accounts'] : '') }}", "text-sm", css=MUTE)
    fr = pg.box(fc, "gap:12px; align-items:flex-end;")
    fv = pg.box(fr, "align-items:baseline; gap:8px;", direction="row")
    t(fv, "{{ " + FOC + "['pct_s'] }}", "display-xs", css="font-size:28px !important;", attrs={"data-fu-fg": "{{ " + FOC + "['tone'] }}"})
    t(fv, "own utilisation", "text-xs", css=MUTE)
    lk = pg.add(fr, "Button", {"color": "brand", "size": "sm", "variant": "outline", "styles": {"width": "w-fit"}}, {"contentMode": "text", "value": "Allocation in Task Management ↗", "type": "default"}, "", name="focus_tm")
    pg.blocks[lk]["component"]["slots"] = {}
    pg.blocks[lk]["events"] = [{"id": f"evt_fufocustm{k}", "eventType": "onClick", "action": a} for k, a in enumerate(_acts(tm_nav(FOC, "fufocustm")))]
    # team strip (the focus person's whole team)
    sr = pg.repeat(inner, D("tier", "strip"), "strip", grid=4, gap="gap-none")
    sc = pg.box(sr, "padding:20px 28px; gap:6px; height:100%;", name="strip_cell")
    t(sc, it(sr, "l"), "text-xs", css=LAB)
    t(sc, it(sr, "v"), "display-xs", css="font-size:28px !important; line-height:1.15;", attrs={"data-fu-fg": it(sr, "c")})
    t(sc, it(sr, "n"), "text-xs", css=MUTE)
    # direct reports, one row each
    hd = pg.box(inner, "justify-content:space-between; align-items:baseline; gap:16px; flex-wrap:wrap; margin:32px 0 16px; padding-bottom:12px; border-bottom:1px solid var(--fu-line2);", direction="row")
    t(hd, "{{ 'Reporting to ' + (" + FOC + "['name'] || '') }}", "text-md", "semi-bold")
    t(hd, "Click a person with a team to go one level down · team columns cover everyone below them", "text-xs", css=MUTE)
    # Table / RAG view toggle
    grp = pg.add(hd, "ButtonGroup", {"color": "brand", "size": "sm", "variant": "solid", "styles": {"height": "h-fit"},
                 "popup": {"styles": {"overflow": {"y": "overflow-y-auto"}, "maxHeight": "max-h-[400px]"}}},
                 {"mode": "manual", "type": "toggle", "options": {"data": [{"__id": "item_uid_futbl", "label": "Table", "id": "table"},
                  {"__id": "item_uid_furag", "label": "RAG view", "id": "rag"}]}, "initialSelectedItemId": "table"},
                 "background:#F3F1EC !important; border:1px solid #E3E0D9 !important; border-radius:10px !important; padding:3px !important; display:inline-flex !important; gap:0 !important; box-shadow:none !important; margin-left:auto;",
                 name="view_toggle")
    gsel = f"[data-block-id='{grp}']"
    pg.blocks[grp].setdefault("additional", {})["customCSS"] = (pg.blocks[grp].get("additional", {}).get("customCSS", "") +
        f" {gsel} button {{ background:transparent !important; color:#6E6A62 !important; border:none !important; border-radius:8px !important; box-shadow:none !important; padding:4px 14px !important; font-weight:500 !important; }}"
        f" {gsel} button[aria-pressed='true'], {gsel} [aria-checked='true'], {gsel} [data-state='on'] {{ background:#1E1E1C !important; color:#FFFFFF !important; }}")
    pg.blocks[grp]["events"] = [{"id": f"evt_fuview_{v}", "eventType": "onClick", "targetId": v,
                                 "action": {"id": f"act_fuview_{v}", "actionType": "setPageVariable", "executionType": "delay",
                                            "payload": {"variableId": V_VIEW, "method": "setPageVariable", "operationDetails": {"operation": "SET", "value": v}}}} for v in ("table", "rag")]
    view = lambda v: {"value": "conditions", "conditions": cond("{{ " + V_VIEW + "['value'] === 'rag' ? 'rag' : 'table' }}", v)}
    # RAG view: the same direct reports as the table, one RAG card each
    ragv = pg.box(inner, "gap:14px;", name="rag_view", visible=view("rag"))
    rs = pg.box(ragv, "align-items:center; gap:10px; flex-wrap:wrap;", direction="row", name="rag_summary")
    RF = ds + "['data']['tier']['rag_focus']"
    t(rs, "{{ ((" + RF + " || {})['band_base'] || 0) + ' people under ' + ((" + FOC + " || {})['name'] || '') + ': ' + (((" + RF + " || {})['band_cells'] || []).map(function(c){ return c['k'] + ' ' + c['n'] + ' (' + c['pct'] + ')'; }).join(' · ')) }}", "text-sm", "medium")
    lg = pg.box(rs, "align-items:center; gap:6px; margin-left:auto;", direction="row", name="heat_legend")
    t(lg, "Share of team in band: 0%", "text-xs", css=MUTE)
    for k in range(1, 6): pg.box(lg, "width:22px; height:14px; border-radius:3px;", {"data-fu-heat": str(k)})
    t(lg, "100%", "text-xs", css=MUTE)
    rcols = [("Name", "minmax(170px,1.4fr)", "left"), ("People", "64px", "right"), ("Under 60%", "120px", "center"), ("60–69%", "120px", "center"), ("70–99%", "120px", "center"),
             ("100%+", "120px", "center"), ("Team average", "104px", "right"), ("", "250px", "right")]
    RG = "display:grid !important; grid-template-columns:" + " ".join(c[1] for c in rcols) + "; gap:10px; align-items:center; min-width:1200px;"
    rtb = pg.box(ragv, "background:var(--fu-card); border:1px solid var(--fu-line); border-radius:16px; overflow-x:auto; gap:0;", name="tbl_rag")
    rh = pg.box(rtb, RG + " padding:14px 24px; border-bottom:1px solid var(--fu-line);", direction="row")
    for c in rcols: t(rh, c[0], "text-xs", css="letter-spacing:.12em; text-transform:uppercase; white-space:nowrap; text-align:" + c[2] + "; " + MUTE)
    rg = pg.repeat(rtb, D("tier", "rag_rows"), "rows_rag", gap="gap-none")
    rrow = pg.box(rg, RG + " padding:6px 24px; border-bottom:1px solid var(--fu-line);", direction="row", name="row_rag")
    pg.attrs(rrow, {"data-fu-team": it(rg, "has_team")})
    pg.blocks[rrow]["events"] = [{"id": "evt_furagrow", "eventType": "onClick", "action": {**setvar(V_MGR, it(rg, "email"), "furagrow"),
        "runCondition": {"type": "filter", "payload": {"operator": "AND", "filters": [{"property": it(rg, "has_team"), "filter": {"operator": "EQUAL", "value": "yes"}}]}}}}]
    rn = pg.box(rrow, "gap:0; min-width:0;")
    t(rn, it(rg, "name"), "text-sm", "semi-bold", "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(rn, "{{ " + rg + "['context']['item']['has_team'] === 'yes' ? (" + rg + "['context']['item']['designation'] + ' · team of ' + " + rg + "['context']['item']['band_base']) : (" + rg + "['context']['item']['designation'] + ' · own utilisation ' + " + rg + "['context']['item']['pct_s']) }}", "text-xs", css=MUTE + " white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(rrow, it(rg, "band_base"), "text-sm", css="text-align:right;")
    cells = pg.repeat(rrow, "{{ " + rg + "['context']['item']['band_cells'] }}", "rag_cells", grid=4, gap="gap-sm")
    pg.blocks[cells]["additional"] = {"customCSS": f"[data-block-id='{cells}']{{grid-column: span 4;}}", "isCustomCSSValid": True}
    cell = pg.box(cells, "height:44px; border-radius:6px; align-items:center; justify-content:center; gap:0;", {"data-fu-heat": it(cells, "lvl")}, name="rag_cell")
    t(cell, it(cells, "n"), "text-sm", "semi-bold", "text-align:center; line-height:1.1;", attrs={"data-fu-heat-ink": it(cells, "lvl")})
    t(cell, it(cells, "pct"), "text-xs", css="text-align:center; line-height:1.1;", attrs={"data-fu-heat-ink": it(cells, "lvl")})
    t(rrow, "{{ " + rg + "['context']['item']['has_team'] === 'yes' ? " + rg + "['context']['item']['team_avg'] : " + rg + "['context']['item']['pct_s'] }}", "text-sm", "semi-bold", "text-align:right; white-space:nowrap;")
    cb = pg.box(rrow, "gap:8px; justify-content:flex-end; align-items:center;", direction="row")
    vt = pg.add(cb, "Button", {"color": "neutral", "size": "sm", "variant": "outline", "styles": {"width": "w-fit"}}, {"contentMode": "text", "value": "View team ›", "type": "default"}, "padding:2px 10px !important; min-width:0 !important;", name="rag_team_btn",
                visible={"value": "conditions", "conditions": cond(it(rg, "has_team"), "yes")})
    pg.blocks[vt]["component"]["slots"] = {}
    pg.blocks[vt]["events"] = [{"id": "evt_furagteam", "eventType": "onClick", "action": setvar(V_MGR, it(rg, "email"), "furagteam")}]
    rtm = pg.add(cb, "Button", {"color": "brand", "size": "sm", "variant": "outline", "styles": {"width": "w-fit"}}, {"contentMode": "text", "value": "Task Management ↗", "type": "default"}, "padding:2px 10px !important; min-width:0 !important;", name="rag_tm")
    pg.blocks[rtm]["component"]["slots"] = {}
    pg.blocks[rtm]["events"] = [{"id": f"evt_furagtm{k}", "eventType": "onClick", "action": a} for k, a in enumerate(_acts(tm_nav(rg + "['context']['item']", "furagtm")))]
    t(ragv, D("tier", "empty_text"), "text-md", css="text-align:center; padding:32px; " + MUTE, visible={"value": "conditions", "conditions": cond(D("tier", "empty"), "yes")})
    cols = [("Name", "minmax(170px,1.4fr)", "left"), ("Utilisation", "96px", "right"), ("Band", "110px", "right"), ("Tasks", "56px", "right"), ("Overdue", "68px", "right"),
            ("Team", "60px", "right"), ("Team average", "104px", "right"), ("Overloaded", "92px", "right"), ("Accounts", "minmax(140px,1fr)", "left"), ("", "190px", "right")]
    G = "display:grid !important; grid-template-columns:" + " ".join(c[1] for c in cols) + "; gap:12px; align-items:center; min-width:1180px;"
    tblv = pg.box(inner, "gap:0;", name="table_view", visible=view("table"))
    tb = pg.box(tblv, "background:var(--fu-card); border:1px solid var(--fu-line); border-radius:16px; overflow-x:auto; gap:0;", name="tbl_tier")
    h = pg.box(tb, G + " padding:14px 24px; border-bottom:1px solid var(--fu-line);", direction="row")
    for c in cols: t(h, c[0], "text-xs", css="letter-spacing:.12em; text-transform:uppercase; white-space:nowrap; text-align:" + c[2] + "; " + MUTE)
    rp = pg.repeat(tb, D("tier", "rows"), "rows_tier", gap="gap-none")
    row = pg.box(rp, G + " padding:12px 24px; border-bottom:1px solid var(--fu-line);", direction="row", name="row_tier")
    pg.attrs(row, {"data-fu-team": it(rp, "has_team")})
    pg.blocks[row]["events"] = [{"id": "evt_furow", "eventType": "onClick", "action": {**setvar(V_MGR, it(rp, "email"), "furow"),
        "runCondition": {"type": "filter", "payload": {"operator": "AND", "filters": [{"property": it(rp, "has_team"), "filter": {"operator": "EQUAL", "value": "yes"}}]}}}}]
    nc = pg.box(row, "gap:0; min-width:0;")
    t(nc, it(rp, "name"), "text-sm", "semi-bold", "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(nc, it(rp, "designation"), "text-xs", css=MUTE + " white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    E = "white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:right;"
    t(row, it(rp, "pct_s"), "text-sm", "semi-bold", E, attrs={"data-fu-fg": it(rp, "tone")})
    t(row, it(rp, "band"), "text-xs", "medium", "letter-spacing:.12em; text-transform:uppercase; border-radius:999px; padding:3px 10px !important; width:fit-content; justify-self:end;", attrs={"data-fu-pill": it(rp, "tone")})
    t(row, it(rp, "tasks"), "text-sm", css=E)
    t(row, it(rp, "overdue"), "text-sm", css=E)
    t(row, "{{ " + rp + "['context']['item']['has_team'] === 'yes' ? " + rp + "['context']['item']['team_n'] : '–' }}", "text-sm", css=E)
    t(row, "{{ " + rp + "['context']['item']['has_team'] === 'yes' ? " + rp + "['context']['item']['team_avg'] : '–' }}", "text-sm", css=E)
    t(row, "{{ " + rp + "['context']['item']['has_team'] === 'yes' ? " + rp + "['context']['item']['team_over'] : '–' }}", "text-sm", css=E, attrs={"data-fu-fg": it(rp, "team_over_tone")})
    t(row, "{{ " + rp + "['context']['item']['accounts'] || '–' }}", "text-xs", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; " + MUTE)
    ac = pg.box(row, "gap:12px; justify-content:flex-end; align-items:center;", direction="row")
    t(ac, "{{ " + rp + "['context']['item']['has_team'] === 'yes' ? 'Open team ›' : '' }}", "text-xs", "semi-bold", "white-space:nowrap;")
    tm = pg.add(ac, "Button", {"color": "brand", "size": "sm", "variant": "outline", "styles": {"width": "w-fit"}}, {"contentMode": "text", "value": "Tasks ↗", "type": "default"}, "padding:2px 10px !important; min-width:0 !important;", name="tier_tm")
    pg.blocks[tm]["component"]["slots"] = {}
    pg.blocks[tm]["events"] = [{"id": f"evt_furowtm{k}", "eventType": "onClick", "action": a} for k, a in enumerate(_acts(tm_nav(rp + "['context']['item']", "furowtm")))]
    t(tblv, D("tier", "empty_text"), "text-md", css="text-align:center; padding:32px; " + MUTE, visible={"value": "conditions", "conditions": cond(D("tier", "empty"), "yes")})
    # ---------------- admins: everyone in db_fdse
    adm = {"value": "conditions", "conditions": cond("{{ " + ds + "['data']['tier']['admin'] === 'yes' && " + V_VIEW + "['value'] !== 'rag' ? 'yes' : 'no' }}", "yes")}
    eh = pg.box(inner, "justify-content:space-between; align-items:baseline; gap:16px; flex-wrap:wrap; margin:40px 0 16px; padding-bottom:12px; border-bottom:1px solid var(--fu-line2);", direction="row", visible=adm)
    t(eh, "{{ 'Everyone (' + (" + ds + "['data']['tier']['everyone_n'] || '0') + ')' }}", "text-md", "semi-bold")
    t(eh, "Admin view · sorted by utilisation · click someone with a team to open their level above", "text-xs", css=MUTE)
    ecols = [("Name", "minmax(170px,1.3fr)", "left"), ("Manager", "minmax(140px,1fr)", "left"), ("Utilisation", "96px", "right"), ("Band", "110px", "right"),
             ("Tasks", "56px", "right"), ("Overdue", "68px", "right"), ("Team", "60px", "right"), ("Accounts", "minmax(140px,1fr)", "left"), ("", "80px", "right")]
    EG = "display:grid !important; grid-template-columns:" + " ".join(c[1] for c in ecols) + "; gap:12px; align-items:center; min-width:1060px;"
    et = pg.box(inner, "background:var(--fu-card); border:1px solid var(--fu-line); border-radius:16px; overflow-x:auto; gap:0;", name="tbl_everyone", visible=adm)
    eh2 = pg.box(et, EG + " padding:14px 24px; border-bottom:1px solid var(--fu-line);", direction="row")
    for c in ecols: t(eh2, c[0], "text-xs", css="letter-spacing:.12em; text-transform:uppercase; white-space:nowrap; text-align:" + c[2] + "; " + MUTE)
    er = pg.repeat(et, D("tier", "everyone"), "rows_everyone", gap="gap-none")
    erow = pg.box(er, EG + " padding:10px 24px; border-bottom:1px solid var(--fu-line);", direction="row", name="row_everyone")
    pg.attrs(erow, {"data-fu-team": it(er, "has_team")})
    pg.blocks[erow]["events"] = [{"id": "evt_fueveryone", "eventType": "onClick", "action": {**setvar(V_MGR, it(er, "email"), "fueveryone"),
        "runCondition": {"type": "filter", "payload": {"operator": "AND", "filters": [{"property": it(er, "has_team"), "filter": {"operator": "EQUAL", "value": "yes"}}]}}}}]
    en = pg.box(erow, "gap:0; min-width:0;")
    t(en, it(er, "name"), "text-sm", "semi-bold", "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(en, it(er, "designation"), "text-xs", css=MUTE + " white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(erow, it(er, "manager"), "text-sm", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(erow, it(er, "pct_s"), "text-sm", "semi-bold", E, attrs={"data-fu-fg": it(er, "tone")})
    t(erow, it(er, "band"), "text-xs", "medium", "letter-spacing:.12em; text-transform:uppercase; border-radius:999px; padding:3px 10px !important; width:fit-content; justify-self:end;", attrs={"data-fu-pill": it(er, "tone")})
    t(erow, it(er, "tasks"), "text-sm", css=E)
    t(erow, it(er, "overdue"), "text-sm", css=E)
    t(erow, "{{ " + er + "['context']['item']['has_team'] === 'yes' ? " + er + "['context']['item']['team_n'] : '–' }}", "text-sm", css=E)
    t(erow, "{{ " + er + "['context']['item']['accounts'] || '–' }}", "text-xs", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; " + MUTE)
    etm = pg.add(erow, "Button", {"color": "brand", "size": "sm", "variant": "outline", "styles": {"width": "w-fit"}}, {"contentMode": "text", "value": "Tasks ↗", "type": "default"}, "padding:2px 10px !important; min-width:0 !important; justify-self:end;", name="every_tm")
    pg.blocks[etm]["component"]["slots"] = {}
    pg.blocks[etm]["events"] = [{"id": f"evt_fueverytm{k}", "eventType": "onClick", "action": a} for k, a in enumerate(_acts(tm_nav(er + "['context']['item']", "fueverytm")))]
    ft = pg.box(inner, "margin-top:32px; padding-top:16px; border-top:1px solid var(--fu-line2);")
    t(ft, "Utilisation = work landing in the next 7 days ÷ weekly capacity. Each task counts its story points (1 if blank), weighted by timing (overdue ×1.25, due within 7 days ×1, later ×7 ÷ days to ETA, no ETA ×1) and status (waiting ×0.5, done 0). Owners split a task; reviewers share 20%. Team columns average everyone below the person, 0% for no tasks.", "text-xs", css=MUTE)
    R.wire({b: pg.blocks[b] for b in pg.new}, {ds})
    return root

def css(pg):
    rules = []
    for b in pg.new:
        a = pg.blocks[b].get("additional")
        if a:
            rules.append(a.pop("customCSS", "")); a.pop("isCustomCSSValid", None)
            if not a: pg.blocks[b].pop("additional")
    by = {b["displayName"]: bid for bid, b in pg.blocks.items() if bid in pg.new}
    s = lambda n: f"[data-block-id='{by['fu_' + n]}']"
    tone = "".join(f"[data-fu-fg='{k}'],[data-fu-fg='{k}'] *{{color:var(--fu-{c}) !important;}}"
                   f"[data-fu-pill='{k}']{{background:var(--fu-{c}Bg) !important;}}[data-fu-pill='{k}'],[data-fu-pill='{k}'] *{{color:var(--fu-{c}) !important;}}" for k, c in (("R", "red"), ("A", "amber"), ("G", "green")))
    return ("<style>\n@import url('https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600&display=swap');\n"
            ":root{--fu-bg:#FFFFFF;--fu-card:#FFFFFF;--fu-line:#ECEAE5;--fu-line2:#E3E0D9;--fu-inset:#F8F7F4;--fu-ink:#1E1E1C;--fu-muted:#6E6A62;"
            "--fu-red:#AC3D3D;--fu-amber:#C88724;--fu-green:#28734A;--fu-redBg:#F6E4E2;--fu-amberBg:#F7ECD9;--fu-greenBg:#E3EFE7;}\n"
            "[data-block-id='root_id'],[data-block-id='root_id'] *{font-family:'Spectral',Georgia,serif;}[data-block-id='root_id']{background:var(--fu-bg);}\n"
            + tone + "[data-fu-pill='X']{background:var(--fu-inset) !important;}[data-fu-pill='X'],[data-fu-pill='X'] *{color:var(--fu-muted) !important;}"
            "[data-fu-on='yes']{background:var(--fu-inset) !important;}"
            "[data-fu-heat='0']{background:var(--fu-inset) !important;}[data-fu-heat='1']{background:#E1EAF3 !important;}[data-fu-heat='2']{background:#BFD3E6 !important;}"
            "[data-fu-heat='3']{background:#8EB0D3 !important;}[data-fu-heat='4']{background:#5A88B8 !important;}[data-fu-heat='5']{background:#2E5E8E !important;}"
            "[data-fu-heat-ink='0'],[data-fu-heat-ink='0'] *{color:#B9B4AA !important;}[data-fu-heat-ink='4'],[data-fu-heat-ink='4'] *,[data-fu-heat-ink='5'],[data-fu-heat-ink='5'] *{color:#FFFFFF !important;}"
            f"{s('strip')}{{background:var(--fu-card); border:1px solid var(--fu-line); border-radius:16px; margin-top:24px; overflow:hidden;}}"
            f"{s('strip_cell')}{{border-left:1px solid var(--fu-line);}}[data-fu-team='yes']{{cursor:pointer;}}[data-fu-flag='yes']{{box-shadow:inset 4px 0 0 #2E5E8E;}}[data-fu-flagtxt='yes'],[data-fu-flagtxt='yes'] *{{color:#2E5E8E !important;}}[data-fu-flagtxt='no'],[data-fu-flagtxt='no'] *{{color:var(--fu-muted) !important;}}[data-fu-team='yes']:hover{{background:var(--fu-inset);}}"
            "[data-fu-crumb='yes'],[data-fu-crumb='yes'] *{color:var(--fu-ink) !important;}[data-fu-crumb='no'],[data-fu-crumb='no'] *{color:var(--fu-muted) !important; text-decoration:underline; text-underline-offset:3px;}\n"
            + "\n".join(r for r in rules if r) +
            f"\n@media (max-width:1000px){{{s('page')}{{padding:24px !important;}}}}\n</style>")

def push():
    pid = ensure_page(); ds = ensure_ds(pid)
    cur = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": pid, "allowedEntityTypes": ["e_component"]})["entity"]
    pg = P(existing=AP.fixed_blocks(), prefix="fu_")
    root = build(pg, ds)
    # only Sumeet and Alpha see this page; anyone else opening the link gets a short notice
    inner = next(b for b in pg.new if pg.blocks[b].get("displayName") == "fu_inner")
    rbac.gate(pg.blocks[inner], DUO)
    nb = pg.box(root, "max-width:1240px; width:100%; gap:12px; padding:64px 0; align-items:center;", name="noaccess")
    pg.text(nb, "This page is unavailable.", "text-md", "semi-bold", "text-align:center;")
    rbac.gate(pg.blocks[nb], DUO, show=False)
    props = dict(cur["properties"])
    props["pageVariables"] = {V_MGR: {"name": "focusPerson", "type": "string", "id": V_MGR, "createdTime": int(time.time() * 1000), "initialValue": ""},
                              V_VIEW: {"name": "reportsView", "type": "string", "id": V_VIEW, "createdTime": int(time.time() * 1000), "initialValue": "table"}}
    props["blocks"] = pg.blocks
    props["customCode"] = {**(props.get("customCode") or {}), "header": css(pg)}
    props["metadata"] = {**props.get("metadata", {}), "_blockCounter": pg.counter}
    r = ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
                {"entity": {**cur, "properties": props}, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": APP}]})
    return pid, ds, len(pg.new), [(x.get("id"), x.get("version")) for x in (r if isinstance(r, list) else [r])]

def nav_item(pid):
    """Desktop nav: a card like PM Control Tower that opens this page (added once)."""
    mid = "e_69f979151dfa014b39659988"
    m = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": mid, "allowedEntityTypes": ["e_component"]})["entity"]
    B = m["properties"]["blocks"]
    if "b_nav_fu_item" in B: return "already there"
    json.dump(m, open("nav_desktop_before_fu.json", "w"))
    item, body, label = copy.deepcopy(B["b_nav_pm_item"]), copy.deepcopy(B["b_nav_pm_body_wrapper"]), copy.deepcopy(B["b_nav_pm_label"])
    item["id"], body["id"], label["id"] = "b_nav_fu_item", "b_nav_fu_body_wrapper", "b_nav_fu_label"
    item["displayName"], body["displayName"], label["displayName"] = "navFuItem", "navFuBodyWrapper", "navFuLabel"
    item["component"]["slots"]["body"]["blockId"] = "b_nav_fu_body_wrapper"; body["parentId"] = "b_nav_fu_item"; label["parentId"] = "b_nav_fu_body_wrapper"
    body["component"]["content"]["blockIds"] = ["b_nav_fu_label", "__PLACEHOLDER__"]
    label["component"]["content"]["value"] = "FDSE Utilisation"
    js = lambda x: json.loads(json.dumps(x).replace("b_nav_pm_item", "b_nav_fu_item").replace("b_nav_pm_body_wrapper", "b_nav_fu_body_wrapper").replace("b_nav_pm_label", "b_nav_fu_label"))
    item, body, label = js(item), js(body), js(label)
    item["events"] = [{"id": "evt_nav_to_fu", "eventType": "onClick", "action": {"id": "act_nav_to_fu", "actionType": "navigateToPage", "payload": {"pageId": pid, "history": "push"}}}]
    for h in item.get("additional", {}).get("htmlAttributes", []):
        if h.get("key") == "data-is-selected": h["value"] = "{{ location['pathname']?.includes('" + SLUG + "')?.toString() }}"
    B.update({item["id"]: item, body["id"]: body, label["id"]: label})
    right = B["b_nav_right"]["component"]["content"]["blockIds"]
    right.insert(right.index("b_nav_pm_item") + 1, "b_nav_fu_item")
    ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
            {"entity": m, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": APP}]})
    return "added"

if __name__ == "__main__":
    ua.ensure_session()
    print(push())
    if "--nav" in sys.argv: print("nav:", nav_item(reg()["page"]))
