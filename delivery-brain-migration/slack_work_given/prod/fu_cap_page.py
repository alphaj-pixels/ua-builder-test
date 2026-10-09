"""FDSE utilisation page in the 'Delivery capacity' layout (design reference: Delivery_capacity_1.html), adapted to the data we have.
Data: DB | FDSE Utilisation Page | Data -> data['cap'] (brief, grid, tabs, people, leaders) and data['tier'] (crumbs, focus).
Sections: title row with the team path; brief; everyone by load (this week's band across, overdue work down; click a cell to filter);
people by band (tabs, Show all); by leader (status, four bands, no tasks, team average, data quality, View team / Task Management); notes.
Reuses fu_page for the page, its data source, the Task Management links and the access gate (Sumeet and Alpha)."""
import sys, json, time, re; sys.path.insert(0, '.')
import ua, a360_ref as R
R.REF = re.compile(r"(e_[0-9a-f]{24}|b_[A-Za-z0-9]{5}|pageInputs|userContext|var_[A-Za-z0-9]+)((?:\['[^']*'\])+)")
from a360_ref import P, cond
import attn_page as AP, rbac
import fu_page as FU

LOAD_DEFAULT = "grid" if "--grid" in __import__("sys").argv else "scatter"
WIN_DEFAULT = "30" if "--month" in __import__("sys").argv else "7"
V_MGR, V_TAB, V_CELL, V_LIM, V_LOAD, V_WIN = FU.V_MGR, "var_futab", "var_fucell", "var_fulim", "var_fuload", "var_fuwin"
V_MODE, V_ETAB, V_ELIM = "var_fumode", "var_fuetab", "var_fuelim"   # load (This week / Next 30 days) or slack (Past 30 days); engagement tab and list limit
MODE_DEFAULT = "slack" if "--slack" in __import__("sys").argv else "load"
MODE = "(" + V_MODE + "['value'] || 'load')"
CAP = "font-size:12px !important; letter-spacing:.12em; text-transform:uppercase; color:var(--fu-muted) !important;"
MUTE = "color:var(--fu-muted) !important;"
CARD = "background:var(--fu-card); border:1px solid var(--fu-line); border-radius:14px; padding:24px; gap:12px; min-width:0; box-shadow:0 1px 2px rgba(31,50,38,.04);"
ROW = "padding:12px 0; border-top:1px solid var(--fu-line);"

def show(expr, value="yes"): return {"value": "conditions", "conditions": cond(expr, value)}
def ev(eid, action): return {"id": "evt_" + eid, "eventType": "onClick", "action": dict(action, id="act_" + eid)}
def setv(var, value, eid): return ev(eid, {"actionType": "setPageVariable", "executionType": "delay", "payload": {"variableId": var, "method": "setPageVariable", "operationDetails": {"operation": "SET", "value": value}}})
def tm(item, eid):
    a = FU.go_tm(item, eid); return {"id": "evt_" + eid, "eventType": "onClick", "action": a}

def build(pg, ds, eds):
    C = ds + "['data']['cap']"
    D = lambda *k: "{{ " + C + "".join(f"['{x}']" for x in k) + " }}"
    E = lambda js: "{{ " + js.replace("$C", C) + " }}"
    it = lambda rep, k: "{{ " + rep + "['context']['item']['" + k + "'] }}"
    ix = lambda rep, js: "{{ " + js.replace("$I", rep + "['context']['item']") + " }}"
    t, box, pill = pg.text, pg.box, pg.pill
    TAB = "(" + V_TAB + "['value'] || ((" + C + "?.['tabs'] || []).find(x => Number(x['n']) > 0) || {})['id'] || 'over')"; CELL = "(" + V_CELL + "['value'] || '')"; LIM = "(" + V_LIM + "['value'] || '25')"
    def grid(parent, cols, name=None, extra=""):
        return box(parent, f"display:grid !important; grid-template-columns:{cols}; gap:16px; align-items:center; {extra}", direction="row", name=name)
    def button(parent, label, events, name=None, visible=None):
        b = pg.add(parent, "Button", {"color": "brand", "size": "sm", "variant": "outline", "styles": {"width": "w-fit"}}, {"contentMode": "text", "value": label, "type": "default"}, None, name)
        pg.blocks[b]["component"]["slots"] = {}; pg.blocks[b]["events"] = events
        if visible: pg.blocks[b]["visibility"] = visible
        return b
    def chead(card, title, sub):
        h = box(card, "justify-content:space-between; align-items:baseline; gap:16px; flex-wrap:wrap; margin-bottom:8px;", direction="row")
        t(h, title, css=CAP); t(h, sub, css=MUTE + " max-width:70ch;")
        return h
    def dot(parent, tone_expr): box(parent, "width:9px; height:9px; border-radius:50%; flex:none;", {"data-fu-dot": tone_expr})

    root = box("root_id", "padding:24px 24px 48px; gap:0; min-height:100vh; align-items:center;", name="page")
    main = box(root, "max-width:1180px; width:100%; gap:16px;", name="inner")

    # ---------------- title row
    tr = box(main, "justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap;", direction="row", name="titlerow")
    tl = box(tr, "gap:2px;")
    t(tl, "FDSE utilisation", "text-md", "semi-bold")
    t(tl, "{{ " + MODE + " === 'slack' ? (" + eds + "['data']?.['eng']?.['asof'] || 'Loading…') : (" + C + "?.['asof'] || 'Loading…') }}", css=MUTE)
    trr = box(tr, "gap:12px; align-items:center; flex-wrap:wrap;", direction="row")
    cr = pg.repeat(trr, "{{ " + ds + "['data']['tier']?.['crumbs'] || [] }}", "crumbs", gap="gap-xs")
    pg.blocks[cr]["component"]["appearance"].update({"layout": "list", "direction": "horizontal"})
    cb = box(cr, "align-items:center; gap:6px; cursor:pointer; width:auto !important;", direction="row", name="crumb")
    pg.blocks[cb]["events"] = [setv(V_MGR, it(cr, "email"), "fucrumb"), setv(V_CELL, "", "fucrumb2"), setv(V_LIM, "25", "fucrumb3"), setv(V_TAB, "", "fucrumb4")]
    t(cb, it(cr, "name"), weight="medium", css="white-space:nowrap;", attrs={"data-fu-crumb": it(cr, "last")})
    t(cb, "›", css=MUTE, visible=show(it(cr, "last"), "no"))
    WINX = "(" + V_WIN + "['value'] || '7')"
    pc_ = box(trr, "gap:0; border:1px solid var(--fu-line); border-radius:999px; background:var(--fu-hover); padding:3px;", direction="row", name="period_toggle")
    for key, lab in (("past", "Past 30 days"), ("7", "This week"), ("30", "Next 30 days")):   # past 30 days = work given (task tracker); the others = upcoming load
        on = (MODE + " === 'slack'") if key == "past" else ("(" + MODE + " === 'load' && " + WINX + " === '" + key + "')")
        b = box(pc_, "padding:4px 14px; border-radius:999px; cursor:pointer;", {"data-fu-on": "{{ " + on + " ? 'yes' : 'no' }}"}, name="period_" + key)
        t(b, lab, css="white-space:nowrap;")
        pg.blocks[b]["events"] = ([setv(V_MODE, "slack", "fumodepast"), setv(V_ETAB, "", "fuetabpast"), setv(V_ELIM, "25", "fuelimpast")] if key == "past" else
                                  [setv(V_MODE, "load", "fumode" + key), setv(V_WIN, key, "fuwin" + key), setv(V_CELL, "", "fuwinc" + key), setv(V_LIM, "25", "fuwinl" + key), setv(V_TAB, "", "fuwint" + key)])

    body = box(main, "gap:16px;", name="body", visible=show("{{ (" + C + " && " + MODE + " === 'load') ? 'yes' : 'no' }}"))
    build_eng(pg, eds, main, grid, button, chead, dot)

    # ---------------- brief
    br = box(body, CARD + " padding:32px 32px 24px;", name="brief")
    t(br, D("label"), css=CAP)
    t(br, D("lead"), "display-xs", css="font-size:28px !important; line-height:1.25 !important; font-weight:400 !important; max-width:38ch; margin:8px 0 !important;")
    t(br, D("money"), css=MUTE + " margin-bottom:12px !important;")
    t(br, D("horizon_note"), css="color:var(--fu-link) !important; margin-bottom:12px !important; max-width:72ch;", visible=show(D("has_horizon")))
    t(br, D("rest"), "text-md", css="line-height:1.65 !important; max-width:72ch;")
    cf = box(br, "gap:8px 16px; align-items:center; flex-wrap:wrap; margin-top:12px; padding-top:16px; border-top:1px solid var(--fu-line);", direction="row")
    cq = box(cf, "gap:6px; align-items:center;", direction="row"); dot(cq, D("conf_tone")); t(cq, D("conf"), css=MUTE)
    t(cf, D("caution"), css=MUTE, visible=show(D("has_caution")))

    # ---------------- everyone, by load: Scatter / Grid toggle
    LOAD = "(" + V_LOAD + "['value'] || 'scatter')"
    gc = box(body, CARD, name="loadmap")
    gh = box(gc, "justify-content:space-between; align-items:center; gap:16px; flex-wrap:wrap; margin-bottom:8px;", direction="row")
    t(gh, "Everyone, by load", css=CAP)
    tg = box(gh, "gap:0; border:1px solid var(--fu-line); border-radius:999px; background:var(--fu-hover); padding:3px;", direction="row", name="load_toggle")
    for key, lab in (("scatter", "Scatter"), ("grid", "Grid")):
        b = box(tg, "padding:4px 14px; border-radius:999px; cursor:pointer;", {"data-fu-on": "{{ " + LOAD + " === '" + key + "' ? 'yes' : 'no' }}"}, name="load_" + key)
        t(b, lab, css="white-space:nowrap;"); pg.blocks[b]["events"] = [setv(V_LOAD, key, "fuload" + key)]
    t(gc, "{{ " + LOAD + " === 'grid' ? 'Each cell counts people. Across: utilisation ' + ((var_fuwin['value'] || '7') === '30' ? 'over the next 30 days' : 'this week') + '. Down: overdue tasks. Click a cell to list those people below.' : 'Each dot is one person. Across: utilisation ' + ((var_fuwin['value'] || '7') === '30' ? 'over the next 30 days' : 'this week') + '. Up: overdue tasks. People with no tasks sit in the left lane. Hover a dot for the name; click it to open their tasks.' }}", css=MUTE)
    lg = pg.repeat(gc, D("grid_cols"), "legend", gap="gap-lg")
    pg.blocks[lg]["component"]["appearance"].update({"layout": "list", "direction": "horizontal"})
    li = box(lg, "gap:6px; align-items:center; width:auto !important;", direction="row")
    dot(li, it(lg, "tone")); t(li, it(lg, "l"), css=MUTE + " white-space:nowrap;"); t(li, it(lg, "n"), weight="medium", css="white-space:nowrap;")

    # scatter view
    sv = box(gc, "gap:0; margin-top:8px;", name="scatter_view", visible=show("{{ " + LOAD + " === 'scatter' ? 'yes' : 'no' }}"))
    LANE_W, YAX_W = 84, 44
    bandrow = box(sv, f"gap:0; margin-left:{LANE_W + YAX_W + 24}px; margin-bottom:6px;", direction="row")
    for lab, w, tone in (("Under-used", 37.5, "U"), ("Medium", 6.25, "A"), ("Optimal", 18.75, "G"), ("Overloaded", 37.5, "R")):
        bb = box(bandrow, f"flex:0 0 {w}% !important; width:{w}%; padding:0 2px; gap:4px; align-items:center;")
        t(bb, lab, css="text-align:center; white-space:nowrap; font-size:12px !important;", attrs={"data-fu-fg": tone})
        box(bb, "height:2px; width:100%; border-radius:2px;", {"data-fu-dot": tone})
    area = box(sv, "gap:12px; align-items:stretch;", direction="row", name="scatter_area")
    lane = box(area, f"flex:0 0 {LANE_W}px; width:{LANE_W}px; height:380px; border:1px solid var(--fu-line); border-radius:8px; position:relative;", name="sc_lane")
    ld = pg.repeat(lane, E("($C['scatter'] || []).filter(p => p['lane'] === 'yes')"), "sc_lane_dots", gap="gap-none")
    yax = box(area, f"flex:0 0 {YAX_W}px; width:{YAX_W}px; height:380px; position:relative;", name="sc_yaxis")
    yt = pg.repeat(yax, D("y_ticks"), "sc_yticks", gap="gap-none")
    t(yt, it(yt, "v"), css=MUTE + " position:absolute; right:6px; transform:translateY(50%); white-space:nowrap;", attrs={"data-sy": it(yt, "pos")}, name="sc_ytick")
    plot = box(area, "flex:1 1 auto; height:380px; position:relative; border-left:1px solid var(--fu-line); border-bottom:1px solid var(--fu-line);", name="sc_plot")
    for xv in (37.5, 43.75, 62.5):
        box(plot, f"position:absolute; top:0; bottom:0; left:{xv}%; width:0; border-left:1px dashed var(--fu-line);")
    yl = pg.repeat(plot, D("y_ticks"), "sc_ygrid", gap="gap-none")
    box(yl, "position:absolute; left:0; right:0; height:0; border-top:1px solid var(--fu-hover);", {"data-sy": it(yl, "pos")}, name="sc_yline")
    for txt, pos in (("Under-used and behind", "top:8px; left:10px;"), ("Free capacity", "bottom:10px; left:10px;"), ("Overloaded and behind", "top:8px; right:10px;"), ("Busy, on track", "bottom:10px; right:10px;")):
        t(plot, txt, css=MUTE + f" position:absolute; {pos} font-style:italic; white-space:nowrap;")
    dts = pg.repeat(plot, E("($C['scatter'] || []).filter(p => p['lane'] === 'no')"), "sc_dots", gap="gap-none")
    for rep, nm in ((ld, "sc_lane_dot"), (dts, "sc_dot")):
        dt = box(rep, "position:absolute; width:10px; height:10px; margin-left:-5px; margin-bottom:-5px; border-radius:50%; cursor:pointer;",
                 {"data-fu-pt": it(rep, "tone"), "data-sx": it(rep, "sx"), "data-sy": it(rep, "sy"), "data-tip": it(rep, "tip")}, name=nm)
        pg.blocks[dt]["events"] = [tm("(($C['people'] || []).find(x => x['id'] === " + rep + "['context']['item']['id']) || {})".replace("$C", C), "fudot" + nm[-3:])]
    xax = box(sv, f"gap:0; margin-left:{LANE_W + YAX_W + 24}px; height:22px; position:relative; margin-top:4px;", name="sc_xaxis")
    t(xax, "No tasks", css=MUTE + f" position:absolute; left:-{LANE_W + YAX_W + 24}px; width:{LANE_W}px; text-align:center;")
    for lab, xv in (("0%", 0), ("60%", 37.5), ("70%", 43.75), ("100%", 62.5), ("160%+", 100)):
        t(xax, lab, css=MUTE + f" position:absolute; left:{xv}%; transform:translateX(-50%); white-space:nowrap;")
    axl = box(sv, f"gap:0; margin-left:{LANE_W + YAX_W + 24}px; justify-content:space-between;", direction="row")
    t(axl, "↑ Overdue tasks", css=MUTE)
    t(axl, "{{ 'Utilisation ' + ((var_fuwin['value'] || '7') === '30' ? 'over the next 30 days' : 'this week') + ' →' }}", css=MUTE)

    # grid view
    gv = box(gc, "gap:8px;", name="grid_view", visible=show("{{ " + LOAD + " === 'grid' ? 'yes' : 'no' }}"))
    G = "200px repeat(5,minmax(0,1fr))"
    hd = grid(gv, G, extra="margin-top:12px;")
    t(hd, "", css=MUTE)
    hc = pg.repeat(hd, D("grid_cols"), "grid_head", grid=5, gap="gap-sm")
    pg.blocks[hd]["additional"]["customCSS"] = pg.blocks[hd]["additional"]["customCSS"].replace("grid-template-columns:" + G, "grid-template-columns:200px minmax(0,1fr)")
    hcc = box(hc, "gap:2px; align-items:center;")
    t(hcc, it(hc, "l"), css=CAP + " text-align:center;", attrs={"data-fu-fg": it(hc, "tone")}); t(hcc, ix(hc, "$I['share'] + ' of the team'"), css=MUTE + " text-align:center;")
    gr = pg.repeat(gv, D("grid"), "grid_rows", gap="gap-sm")
    grw = grid(gr, "200px minmax(0,1fr)", name="grid_row")
    t(grw, it(gr, "l"), css=MUTE)
    cells = pg.repeat(grw, "{{ " + gr + "['context']['item']['cells'] }}", "grid_cells", grid=5, gap="gap-sm")
    cel = box(cells, "height:56px; border-radius:10px; align-items:center; justify-content:center; cursor:pointer; border:1px solid var(--fu-line);",
              {"data-fu-cell": ix(cells, "$I['key'].split('|')[0] + '-' + $I['lvl']"), "data-fu-sel": ix(cells, CELL + " === $I['key'] ? 'yes' : 'no'")}, name="grid_cell")
    pg.blocks[cel]["events"] = [setv(V_CELL, ix(cells, CELL + " === $I['key'] ? '' : $I['key']"), "fucell1"), setv(V_TAB, ix(cells, "$I['key'].split('|')[0]"), "fucell2"), setv(V_LIM, "25", "fucell3")]
    t(cel, it(cells, "n"), "text-md", "medium", "text-align:center;")
    t(gv, "Most people with tasks are under 60%. Their tasks often carry no story points, and a task without points counts as 1 point.", css=MUTE + " margin-top:8px !important;")

    # ---------------- people
    pc = box(body, CARD, name="people")
    chead(pc, "People", "Overloaded highest first, under-used lowest first. Task Management opens that person's tasks; View team goes one level down.")
    tb = pg.repeat(pc, D("tabs"), "tabs", gap="gap-none")
    pg.blocks[tb]["component"]["appearance"].update({"layout": "list", "direction": "horizontal"})
    tbi = box(tb, "gap:6px; align-items:center; padding:8px 16px 8px 0; margin-right:16px; border-bottom:2px solid transparent; cursor:pointer; width:auto !important;",
              {"data-fu-tab": ix(tb, TAB + " === $I['id'] ? 'yes' : 'no'")}, direction="row", name="tab")
    pg.blocks[tbi]["events"] = [setv(V_TAB, it(tb, "id"), "futab1"), setv(V_CELL, "", "futab2"), setv(V_LIM, "25", "futab3")]
    dot(tbi, it(tb, "tone")); t(tbi, it(tb, "l"), "text-md", css="white-space:nowrap;"); t(tbi, it(tb, "n"), css="white-space:nowrap;")
    t(pc, "", css="height:0; border-top:1px solid var(--fu-line); margin-top:-12px !important;")
    fchip = box(pc, "gap:8px; align-items:center; cursor:pointer; width:fit-content; border:1px solid var(--fu-line); border-radius:999px; padding:2px 12px; background:var(--fu-hover);",
                direction="row", name="cell_chip", visible=show("{{ " + CELL + " ? 'yes' : 'no' }}"))
    pg.blocks[fchip]["events"] = [setv(V_CELL, "", "fuchip")]
    t(fchip, E("'Showing: ' + ((($C['grid'] || []).flatMap(r => r['cells']).find(c => c['key'] === " + CELL + ") || {})['title'] || '')"), css=MUTE)
    t(fchip, "✕", css=MUTE)
    LIST = "(($C['people'] || []).filter(p => p['band_key'] === " + TAB + " && (!" + CELL + " || p['cell'] === " + CELL + ")))"
    PG = "200px minmax(0,1fr) 110px 80px minmax(0,1fr) 60px 240px"
    h = grid(pc, "minmax(0,1.4fr) minmax(0,1fr) 100px 70px minmax(0,1fr) 50px 220px", extra="padding-bottom:6px;")
    for x in ("Name", "Leader", "Utilisation", "Overdue", "Top account", "Tasks", ""): t(h, x, css=CAP)
    pr = pg.repeat(pc, E(LIST + ".slice(0, " + LIM + " === 'all' ? 100000 : 25)"), "people_rows", gap="gap-none")
    prw = grid(pr, "minmax(0,1.4fr) minmax(0,1fr) 100px 70px minmax(0,1fr) 50px 220px", name="person_row", extra="padding:8px 0; border-top:1px solid var(--fu-line);")
    nm = box(prw, "gap:2px; min-width:0;")
    nl = box(nm, "gap:6px; align-items:center; min-width:0;", direction="row"); dot(nl, it(pr, "band_tone")); t(nl, it(pr, "name"), "text-sm", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(nm, it(pr, "designation"), css=MUTE + " padding-left:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(prw, it(pr, "leader"), "text-sm", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(prw, it(pr, "util_s"), "text-sm", css="text-align:right;")
    t(prw, it(pr, "overdue"), "text-sm", css="text-align:right;", attrs={"data-fu-fg": it(pr, "od_tone")})
    t(prw, it(pr, "top_acct"), "text-sm", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(prw, it(pr, "tasks"), "text-sm", css="text-align:right;")
    bx = box(prw, "gap:8px; justify-content:flex-end;", direction="row")
    button(bx, "View team ›", [setv(V_MGR, it(pr, "email"), "fupteam"), setv(V_CELL, "", "fupteam2"), setv(V_LIM, "25", "fupteam3"), setv(V_TAB, "", "fupteam4")], name="person_team", visible=show(it(pr, "has_team")))
    button(bx, "Task Management ↗", [tm(pr + "['context']['item']", "fuptm")], name="person_tm")
    pgr = box(pc, "gap:8px; align-items:baseline; padding-top:8px;", direction="row")
    t(pgr, E("(" + LIST + ".length > 25 && " + LIM + " !== 'all') ? ('Showing 25 of ' + " + LIST + ".length + '.') : (" + LIST + ".length + (" + LIST + ".length === 1 ? ' person.' : ' people.'))"), css=MUTE)
    sa = t(pgr, "Show all", css="color:var(--fu-link) !important; cursor:pointer;", visible=show(E("(" + LIST + ".length > 25 && " + LIM + " !== 'all') ? 'yes' : 'no'")))
    pg.blocks[sa]["events"] = [setv(V_LIM, "all", "fushowall")]

    # ---------------- by leader
    lc = box(body, CARD, name="leaders")
    chead(lc, "By leader", E("'People reporting to ' + (" + ds + "['data']['tier']?.['focus']?.['name'] || '') + ' who lead a team, worst first by the share of people with tasks who need action.'"))
    LG = "120px minmax(0,1.3fr) repeat(4,minmax(0,.8fr)) minmax(0,.8fr) 70px 90px 230px"
    h = grid(lc, LG, extra="padding-bottom:6px;")
    for x in ("Status", "Leader", "Under 60%", "60–69%", "70–99%", "100%+", "No tasks", "Avg", "Estimated", ""): t(h, x, css=CAP + " white-space:nowrap;")
    lr = pg.repeat(lc, D("leaders"), "leader_rows", gap="gap-none")
    lrw = grid(lr, LG, name="leader_row", extra="padding:10px 0; border-top:1px solid var(--fu-line);")
    st = box(lrw, "gap:2px;")
    sl = box(st, "gap:6px; align-items:center;", direction="row"); dot(sl, it(lr, "status")); t(sl, it(lr, "action_s"), "text-sm", "medium")
    t(st, it(lr, "status_note"), css=MUTE)
    ln = box(lrw, "gap:2px; min-width:0;")
    t(ln, it(lr, "name"), "text-sm", "medium", "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"); t(ln, ix(lr, "$I['team_n'] + ' people · ' + $I['designation']"), css=MUTE + " white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    for k, tone in (("under", "U"), ("medium", "A"), ("optimal", "G"), ("over", "R")):
        c = box(lrw, "gap:2px;")
        t(c, it(lr, k + "_n"), "text-sm", "medium", attrs={"data-fu-fg": ix(lr, "Number($I['" + k + "_n']) > 0 ? '" + tone + "' : 'X'")})
        t(c, it(lr, k + "_s"), css=MUTE)
    c = box(lrw, "gap:2px;"); t(c, it(lr, "notask_n"), "text-sm", "medium"); t(c, ix(lr, "$I['logged_s'] + ' logged'"), css=MUTE)
    t(lrw, it(lr, "team_avg"), "text-sm")
    dq = box(lrw, "gap:6px; align-items:center;", direction="row"); dot(dq, it(lr, "dq_tone")); t(dq, it(lr, "dq"), "text-sm")
    bx = box(lrw, "gap:8px; justify-content:flex-end;", direction="row")
    button(bx, "View team ›", [setv(V_MGR, it(lr, "email"), "fulteam"), setv(V_CELL, "", "fulteam2"), setv(V_LIM, "25", "fulteam3"), setv(V_TAB, "", "fulteam4")], name="leader_team")
    button(bx, "Task Management ↗", [tm(lr + "['context']['item']", "fultm")], name="leader_tm")
    t(lc, D("no_leaders"), css=MUTE, visible=show(D("has_leaders"), "no"))

    # ---------------- notes
    nt = box(body, "gap:4px; max-width:90ch; padding:0 4px;", name="notes")
    for line in ("Utilisation is the load landing in the window against capacity for the window: this week uses 7 days and weekly capacity (60 story points unless set); next 30 days uses 30 days and 30/7 of weekly capacity, with tasks due inside 30 days counting in full. Each task counts its story points (1 when blank), weighted by timing (overdue ×1.25) and status (waiting ×0.5). Owners split a task; reviewers share 20%.",
                 "Under-used is below 60%, medium 60 to 69%, optimal 70 to 99%, overloaded 100% or more. No tasks means nothing open is assigned to the person in Task Management this week; those people are kept apart because it usually means work isn't logged.",
                 "Status is the share of a team's people with tasks who are under-used or overloaded: red at 30% or more, amber 20 to 29%, green below 20%. Data quality is the share of the team's open tasks with story points and a due date: green at 80% or more, amber 60 to 79%, red below 60%.",
                 "There is no look-back view: task records carry no completion dates and scores aren't stored over time, so the last 30 days can't be rebuilt. Very few open tasks have a future due date, which is why the next-30-days view runs low."):
        t(nt, line, css=MUTE + " line-height:1.6;")
    R.wire({b: pg.blocks[b] for b in pg.new}, {ds, eds})
    return root

def build_eng(pg, eds, main, grid, button, chead, dot):
    """Past 30 days view: work given to each FDSE over the past 30 days, from the task tracker (Engaged / Low / Zero)."""
    EC = eds + "['data']?.['eng']"
    D = lambda *k: "{{ " + EC + "?." + "?.".join(f"['{x}']" for x in k) + " }}"
    E = lambda js: "{{ " + js.replace("$E", EC) + " }}"
    it = lambda rep, k: "{{ " + rep + "['context']['item']['" + k + "'] }}"
    ix = lambda rep, js: "{{ " + js.replace("$I", rep + "['context']['item']") + " }}"
    t, box = pg.text, pg.box
    ETAB = "(" + V_ETAB + "['value'] || ((" + EC + "?.['tabs'] || []).find(x => Number(x['n']) > 0) || {})['id'] || 'zero')"; ELIM = "(" + V_ELIM + "['value'] || '25')"
    eb = box(main, "gap:16px;", name="eng_body", visible=show("{{ (" + MODE + " === 'slack' && " + EC + ") ? 'yes' : 'no' }}"))
    # brief
    br = box(eb, CARD + " padding:32px 32px 24px;", name="eng_brief")
    t(br, D("label"), css=CAP)
    t(br, D("lead"), "display-xs", css="font-size:28px !important; line-height:1.25 !important; font-weight:400 !important; max-width:40ch; margin:8px 0 !important;")
    t(br, D("rest"), "text-md", css="line-height:1.65 !important; max-width:72ch;")
    t(br, D("coverage"), css=MUTE + " margin-top:12px !important; padding-top:16px; border-top:1px solid var(--fu-line); max-width:80ch;")
    # people
    pc = box(eb, CARD, name="eng_people")
    chead(pc, "People", "Tasks given each week, oldest week first. Zero means no task in the task tracker was given to them in the past 30 days.")
    tb = pg.repeat(pc, D("tabs"), "eng_tabs", gap="gap-none")
    pg.blocks[tb]["component"]["appearance"].update({"layout": "list", "direction": "horizontal"})
    tbi = box(tb, "gap:6px; align-items:center; padding:8px 16px 8px 0; margin-right:16px; border-bottom:2px solid transparent; cursor:pointer; width:auto !important;",
              {"data-fu-tab": ix(tb, ETAB + " === $I['id'] ? 'yes' : 'no'")}, direction="row", name="eng_tab")
    pg.blocks[tbi]["events"] = [setv(V_ETAB, it(tb, "id"), "fuetab1"), setv(V_ELIM, "25", "fuetab2")]
    dot(tbi, it(tb, "tone")); t(tbi, it(tb, "l"), "text-md", css="white-space:nowrap;"); t(tbi, it(tb, "n"), css="white-space:nowrap;")
    t(pc, "", css="height:0; border-top:1px solid var(--fu-line); margin-top:-12px !important;")
    COLS = "minmax(0,1.3fr) minmax(0,1fr) 220px 56px 56px 56px 96px minmax(0,1.8fr) 110px"
    WK = "repeat(4,minmax(0,1fr))"
    h = grid(pc, COLS, extra="padding-bottom:6px; align-items:end;")
    for x in ("Name", "Leader"): t(h, x, css=CAP)
    wh = pg.repeat(h, D("weeks"), "eng_week_head", grid=4, gap="gap-xs")
    t(wh, it(wh, "l"), css=MUTE + " font-size:11px !important; text-align:center; white-space:nowrap;")
    for x in ("Given", "Open", "Done", "Last given", "Recent work", ""): t(h, x, css=CAP + " white-space:nowrap;")
    LIST = "((" + EC + "?.['people'] || []).filter(p => p['band_key'] === " + ETAB + "))"
    pr = pg.repeat(pc, E(LIST + ".slice(0, " + ELIM + " === 'all' ? 100000 : 25)"), "eng_rows", gap="gap-none")
    prw = grid(pr, COLS, name="eng_row", extra="padding:8px 0; border-top:1px solid var(--fu-line);")
    nm = box(prw, "gap:2px; min-width:0;")
    nl = box(nm, "gap:6px; align-items:center; min-width:0;", direction="row"); dot(nl, it(pr, "band_tone")); t(nl, it(pr, "name"), "text-sm", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(nm, ix(pr, "$I['note'] || $I['designation']"), css=MUTE + " padding-left:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(prw, it(pr, "leader"), "text-sm", css="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    wk = grid(prw, WK, extra="gap:4px !important;")
    for i in (1, 2, 3, 4):
        c = box(wk, "height:28px; border-radius:6px; align-items:center; justify-content:center;", {"data-fu-wk": it(pr, f"w{i}t")})
        t(c, it(pr, f"w{i}"), "text-sm", css="text-align:center;")
    t(prw, it(pr, "given"), "text-sm", "medium", css="text-align:right;")
    t(prw, it(pr, "open"), "text-sm", css="text-align:right;")
    t(prw, it(pr, "done"), "text-sm", css="text-align:right;")
    t(prw, it(pr, "last"), "text-sm", css="white-space:nowrap;")
    t(prw, it(pr, "recent"), "text-sm", css="overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;")
    bx = box(prw, "gap:8px; justify-content:flex-end;", direction="row")
    button(bx, "View team ›", [setv(V_MGR, it(pr, "email"), "fuepteam"), setv(V_ETAB, "", "fuepteam2"), setv(V_ELIM, "25", "fuepteam3"), setv(V_TAB, "", "fuepteam4")], name="eng_person_team", visible=show(it(pr, "has_team")))
    pgr = box(pc, "gap:8px; align-items:baseline; padding-top:8px;", direction="row")
    t(pgr, E("(" + LIST + ".length > 25 && " + ELIM + " !== 'all') ? ('Showing 25 of ' + " + LIST + ".length + '.') : (" + LIST + ".length + (" + LIST + ".length === 1 ? ' person.' : ' people.'))"), css=MUTE)
    sa = t(pgr, "Show all", css="color:var(--fu-link) !important; cursor:pointer;", visible=show(E("(" + LIST + ".length > 25 && " + ELIM + " !== 'all') ? 'yes' : 'no'")))
    pg.blocks[sa]["events"] = [setv(V_ELIM, "all", "fueshowall")]
    # by leader
    lc = box(eb, CARD, name="eng_leaders")
    chead(lc, "By leader", E("'People reporting to ' + (" + eds + "['data']?.['tier']?.['focus']?.['name'] || '') + ' who lead FDSEs, highest share given no work first.'"))
    LG = "120px minmax(0,1.4fr) 70px repeat(3,minmax(0,.7fr)) 110px 110px"
    h = grid(lc, LG, extra="padding-bottom:6px;")
    for x in ("Status", "Leader", "FDSEs", "Engaged", "Low", "Zero", "No work given", ""): t(h, x, css=CAP + " white-space:nowrap;")
    lr = pg.repeat(lc, D("leaders"), "eng_leader_rows", gap="gap-none")
    lrw = grid(lr, LG, name="eng_leader_row", extra="padding:10px 0; border-top:1px solid var(--fu-line);")
    sl = box(lrw, "gap:6px; align-items:center;", direction="row"); dot(sl, it(lr, "status"))
    t(sl, ix(lr, "$I['status'] === 'R' ? 'Look into' : ($I['status'] === 'A' ? 'Watch' : 'Fine')"), "text-sm", "medium")
    ln = box(lrw, "gap:2px; min-width:0;")
    t(ln, it(lr, "name"), "text-sm", "medium", "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"); t(ln, it(lr, "designation"), css=MUTE + " white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    t(lrw, it(lr, "team_n"), "text-sm")
    for k, tone in (("engaged", "G"), ("low", "A"), ("zero", "R")):
        t(lrw, it(lr, k + "_n"), "text-sm", "medium", attrs={"data-fu-fg": ix(lr, "Number($I['" + k + "_n']) > 0 ? '" + tone + "' : 'X'")})
    t(lrw, it(lr, "zero_s"), "text-sm")
    bx = box(lrw, "gap:8px; justify-content:flex-end;", direction="row")
    button(bx, "View team ›", [setv(V_MGR, it(lr, "email"), "fuelteam"), setv(V_ETAB, "", "fuelteam2"), setv(V_ELIM, "25", "fuelteam3"), setv(V_TAB, "", "fuelteam4")], name="eng_leader_team")
    t(lc, D("no_leaders"), css=MUTE, visible=show(D("has_leaders"), "no"))
    # notes
    nt = box(eb, "gap:4px; max-width:90ch; padding:0 4px;", name="eng_notes")
    for line in ("Work given means a task in the task tracker owned by the person and given in the past 30 days. Most come from Slack: the Slack Task Assignment agent reads every mapped account channel and adds a 'Slack assignment' task whenever someone is asked to do something, handed an item or shown owning one ('@name can you…', 'please pick this', 'POC - name', '@name in progress ETA…'); a tag on its own, cc lists, FYIs, thanks and @group broadcasts don't count. Tasks from the Slack CXO records and tasks logged directly in the tracker count too.",
                 "The date a task was given is its Slack message date for Slack tasks, otherwise the date it was added to the tracker. A Slack CXO task on the same message as a Slack assignment counts once. Open and done come from the task's status in the tracker.",
                 "Engaged means work was given in 3 or 4 of the last 4 weeks, low in 1 or 2 weeks, zero in none. FDSEs are people whose role in user management says Forward Deployed Engineer. Slack is fetched daily for the previous day and read every hour. Status is the share of a leader's FDSEs given no work: red at 40% or more, amber 20 to 39%, green below 20%."):
        t(nt, line, css=MUTE + " line-height:1.6;")
    return eb

def css(pg):
    rules = []
    for b in pg.new:
        a = pg.blocks[b].get("additional")
        if a and a.get("customCSS"):
            rules.append(a.pop("customCSS")); a.pop("isCustomCSSValid", None)
            if not a: pg.blocks[b].pop("additional")
    COL = {"U": "#7A5230", "A": "#C88724", "G": "#28734A", "R": "#AC3D3D", "X": "#8C877C"}
    toneR = "".join(f"[data-fu-dot='{k}']{{background:{c} !important;}}[data-fu-fg='{k}'],[data-fu-fg='{k}'] *{{color:{c} !important;}}" for k, c in COL.items() if k != "X")
    toneR += "[data-fu-dot='X']{background:transparent !important; box-shadow:inset 0 0 0 1.5px #8C877C;}[data-fu-fg='X'],[data-fu-fg='X'] *{color:var(--fu-ink) !important;}"
    cellC = {"notask": "140,135,124", "under": "122,82,48", "medium": "200,135,36", "optimal": "40,115,74", "over": "172,61,61"}
    alpha = {1: .10, 2: .22, 3: .38, 4: .6, 5: .82}
    cells = "".join(f"[data-fu-cell='{k}-0']{{background:var(--fu-hover) !important;}}[data-fu-cell='{k}-0'] *{{color:#B9B4AA !important;}}"
                    + "".join(f"[data-fu-cell='{k}-{l}']{{background:rgba({rgb},{a}) !important;}}" + (f"[data-fu-cell='{k}-{l}'] *{{color:#FFFFFF !important;}}" if l >= 4 else "")
                              for l, a in alpha.items()) for k, rgb in cellC.items())
    return ("<style>\n@import url('https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,400;0,500;0,600;1,400&display=swap');\n"
            ":root{--fu-bg:#FFFFFF;--fu-card:#FFFFFF;--fu-line:#E8E6E1;--fu-hover:#F7F6F2;--fu-ink:#2A2620;--fu-muted:#6F685C;--fu-link:#7A5230;--a3-ink:#2A2620;}\n"
            "[data-block-id='root_id'],[data-block-id='root_id'] *{font-family:'Spectral',Georgia,serif;}[data-block-id='root_id']{background:var(--fu-bg);}\n"
            + toneR + cells +
            "[data-fu-sel='yes']{outline:2px solid var(--fu-ink); outline-offset:-2px;}"
            + "".join(f"[data-sx='{i}']{{left:{i}% !important;}}[data-sy='{i}']{{bottom:{i}% !important;}}" for i in range(0, 101))
            + "".join(f"[data-fu-pt='{k}']{{background:{c}; opacity:.85; border:1px solid #FFFFFF;}}" for k, c in COL.items() if k != "X")
            + "[data-fu-pt='X']{background:#FFFFFF; border:1.5px solid #8C877C; opacity:.9;}[data-fu-pt]:hover{opacity:1; border-color:var(--fu-ink); z-index:5;}"
            "[data-tip]:hover::after{content:attr(data-tip); position:absolute; left:50%; bottom:16px; transform:translateX(-50%); background:#1F3226; color:#F5F3EE; font-size:12px; line-height:1.3; padding:6px 8px; border-radius:8px; white-space:nowrap; z-index:10; pointer-events:none;}"
            + "".join(f"[data-block-id='{b}']{{position:absolute !important; inset:0; display:block !important; height:100%; overflow:visible !important;}}[data-block-id='{b}'] *:not([data-fu-pt]){{position:static !important; transform:none !important;}}[data-block-id='{b}'] [data-fu-pt]{{position:absolute !important;}}"
                      for b in [x for x, y in pg.blocks.items() if y.get("displayName") in ("fu_sc_dots", "fu_sc_lane_dots", "fu_sc_yticks", "fu_sc_ygrid")])
            + "".join(f"[data-block-id='{b}'] [data-sy]{{position:absolute !important;}}" for b in [x for x, y in pg.blocks.items() if y.get("displayName") in ("fu_sc_yticks", "fu_sc_ygrid")])
            + "[data-fu-on='yes']{background:#1F3226 !important;}[data-fu-on='yes'] *{color:#F5F3EE !important;}[data-fu-on='no'] *{color:var(--fu-muted) !important;}"
            "[data-fu-wk='on']{background:rgba(40,115,74,.16) !important;}[data-fu-wk='on'] *{color:#1F5A39 !important; font-weight:600 !important;}"
            "[data-fu-wk='off']{background:var(--fu-hover) !important;}[data-fu-wk='off'] *{color:#B9B4AA !important;}"
            "[data-fu-tab='yes']{border-bottom-color:var(--fu-ink) !important;}[data-fu-tab='no'] *{color:var(--fu-muted) !important;}"
            "[data-fu-crumb='yes'],[data-fu-crumb='yes'] *{color:var(--fu-ink) !important;}[data-fu-crumb='no'],[data-fu-crumb='no'] *{color:var(--fu-link) !important;}\n"
            + "\n".join(rules) + "\n</style>")

def ensure_eng_ds(pid):
    """Second data source on the page: DB | FDSE Slack Engagement Page | Data (same viewer / admin / focus inputs as the utilisation one)."""
    r = FU.reg(); src = ua.call("GET", f"/api/entity/e_data_source/{FU.ensure_ds(pid)}")["properties"]
    props = json.loads(json.dumps(src)); props["name"] = "fu_eng"
    props["inputs"]["automationId"] = json.load(open("db_automations.json"))["slack_eng_page"]
    props["inputs"]["parameters"] = {k: v for k, v in props["inputs"]["parameters"].items() if k in ("viewer", "admin", "focus")}
    props["dP"] = [x for x in props["dP"] if x["p"] in ("inputs.parameters.viewer", "inputs.parameters.admin", "inputs.parameters.focus")]
    props["dpOn"] = [x for x in props["dpOn"] if x.get("id") != V_WIN]
    if "eng_ds" not in r:
        r["eng_ds"] = ua.call("POST", "/api/entity", {"entityType": "e_data_source", "properties": props})["id"]; FU.save_reg(r)
    cur = ua.call("GET", f"/api/entity/e_data_source/{r['eng_ds']}")
    ua.call("POST", "/api/entity/update", {**cur, "properties": props})
    return r["eng_ds"]

def push():
    pid = FU.ensure_page(); ds = FU.ensure_ds(pid); eds = ensure_eng_ds(pid)
    d = ua.call("GET", f"/api/entity/e_data_source/{ds}"); dp = d["properties"]   # the period switch feeds the data workflow
    dp["inputs"]["parameters"]["window_days"] = "{{ " + V_WIN + "['value'] || '7' }}"
    if {"p": "inputs.parameters.window_days"} not in dp["dP"]: dp["dP"].append({"p": "inputs.parameters.window_days"})
    dp["dpOn"] = [x for x in dp["dpOn"] if x.get("id") != V_WIN] + [{"id": V_WIN, "p": [V_WIN + "['value']"]}]
    ua.call("POST", "/api/entity/update", d)
    cur = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": pid, "allowedEntityTypes": ["e_component"]})["entity"]
    json.dump(cur, open(f"fu_page_before_capacity_v{cur['version']}.json", "w"))
    pg = P(existing=AP.fixed_blocks(), prefix="fu_")
    root = build(pg, ds, eds)
    inner = next(b for b in pg.new if pg.blocks[b].get("displayName") == "fu_inner")
    rbac.gate(pg.blocks[inner], FU.DUO)
    nb = pg.box(root, "max-width:1180px; width:100%; gap:12px; padding:64px 0; align-items:center;", name="noaccess")
    pg.text(nb, "This page is unavailable.", "text-md", "semi-bold", "text-align:center;")
    rbac.gate(pg.blocks[nb], FU.DUO, show=False)
    props = dict(cur["properties"]); now = int(time.time() * 1000)
    props["pageVariables"] = {V_MGR: {"name": "focusPerson", "type": "string", "id": V_MGR, "createdTime": now, "initialValue": ""},
                              V_TAB: {"name": "peopleTab", "type": "string", "id": V_TAB, "createdTime": now, "initialValue": ""},
                              V_CELL: {"name": "loadCell", "type": "string", "id": V_CELL, "createdTime": now, "initialValue": ""},
                              V_LIM: {"name": "peopleLimit", "type": "string", "id": V_LIM, "createdTime": now, "initialValue": "25"},
                              V_LOAD: {"name": "loadView", "type": "string", "id": V_LOAD, "createdTime": now, "initialValue": LOAD_DEFAULT},
                              V_WIN: {"name": "periodDays", "type": "string", "id": V_WIN, "createdTime": now, "initialValue": WIN_DEFAULT},
                              V_MODE: {"name": "viewMode", "type": "string", "id": V_MODE, "createdTime": now, "initialValue": MODE_DEFAULT},
                              V_ETAB: {"name": "engagementTab", "type": "string", "id": V_ETAB, "createdTime": now, "initialValue": ""},
                              V_ELIM: {"name": "engagementLimit", "type": "string", "id": V_ELIM, "createdTime": now, "initialValue": "25"}}
    props["blocks"] = pg.blocks
    props["customCode"] = {**(props.get("customCode") or {}), "header": css(pg)}
    props["metadata"] = {**props.get("metadata", {}), "_blockCounter": pg.counter}
    r = ua.call("POST", "/api/entity/create-update-or-delete/hierarchical", {"entity": {**cur, "properties": props}, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": FU.APP}]})
    return pid, ds, len(pg.new), [(x.get("id"), x.get("version")) for x in (r if isinstance(r, list) else [r])]

if __name__ == "__main__":
    ua.ensure_session()
    print(push())
