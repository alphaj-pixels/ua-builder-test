"""Accounts needing attention: a page listing every red account (health v2) as a card; a card click opens account-detail.
Also adds an 'Accounts needing attention' KPI card to the CXO dashboard (cloned from its 'Use cases under development' card).
"""
import sys, json, os, re, copy, time; sys.path.insert(0, '.')
import sales, ua, db_wf as W
import a360_ref as R
R.REF = re.compile(r"(e_[0-9a-f]{24}|b_[A-Za-z0-9]{5}|pageInputs|var_[A-Za-z0-9]+)((?:\['[^']*'\])+)")
from a360_ref import P, LAB, MUTE, CARD, cond

APP, DETAIL = R.APP, R.DETAIL
DASH = "e_6a89562d92a5fd1fe3080da3"
SLUG, TITLE = "accounts-needing-attention", "Accounts needing attention"
REG = "attn_page.json"
WF = json.load(open("a360_wf.json"))["attn"]

def reg(): return json.load(open(REG)) if os.path.exists(REG) else {}
def save_reg(r): json.dump(r, open(REG, "w"), indent=1)

def fixed_blocks():
    out = {}
    for fixed in ("root_id", "header_id", "footer_id"):
        out[fixed] = {"id": fixed, "displayName": {"root_id": "body", "header_id": "header", "footer_id": "footer"}[fixed],
            "component": {"componentType": "Stack", "appearance": {"direction": "column", "alignItems": "stretch", "justifyContent": "flex-start",
            "wrapContent": False, "reverseOrder": False, "theme": "inherit", "styles": {"gap": {"all": "gap-none"}, "padding": {"all": "p-0"},
            "width": "w-full"}}, "content": {"blockIds": ["__PLACEHOLDER__"]}}, "additional": {"isRootBlock": True},
            "visibility": {"value": True}, "dpOn": [], "dataSourceIds": []}
    return out

def ensure_page():
    r = reg()
    if r.get("page"): return r["page"]
    props = {"componentType": "PAGE", "interfaceId": APP, "name": TITLE, "slug": SLUG, "publicAccess": False, "interfaceType": "application",
             "documentTitle": TITLE, "layout": {"body": "root_id", "header": "header_id", "footer": "footer_id"}, "blocks": fixed_blocks(),
             "pageVariables": {}, "dataSources": {}, "flags": {"shouldUseBuiltDependencies": True}, "eligibleOverrides": [],
             "inputSchema": {"schema": {"additionalProperties": False, "type": "object", "properties": {}, "required": []},
                             "layout": {"ui:order": [], "ua:valueSemanticsVersion": 2}, "dynamic": False, "type": "SCHEMA_AND_LAYOUT"},
             "outputSchema": {"type": "SCHEMA_AND_LAYOUT", "dynamic": False}, "metadata": {"_version": 2}}
    app = ua.call("GET", f"/api/entity/e_interface/{APP}")
    app["properties"]["entityDetailsMap"] = {**(app["properties"].get("entityDetailsMap") or {}),
        "NEW_ENTITY_ID": {"slug": SLUG, "isPublic": False, "type": "PAGE", "name": TITLE}}
    res = ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
                  {"entity": {"entityType": "e_component", "properties": props}, "requestType": "CREATED",
                   "parentEntities": [{"type": "e_interface", "id": APP}], "postUpdateEntities": [app]})
    res = res if isinstance(res, list) else [res]
    pid = next(x["id"] for x in res if x.get("entityType", "e_component") == "e_component" and x.get("id", "").startswith("e_") and x["id"] != APP)
    r["page"] = pid; save_reg(r)
    return pid

def ensure_ds(page_id, key, name):
    r = reg(); rk = f"{page_id}:{key}"
    props = {"name": name, "type": "APPLICATION", "target": "page", "interfaceId": APP, "interfacePageId": page_id,
             "context": {"appName": "callables", "resourceName": "callables_call_automation", "resourceVersion": W.V("callables", "callables_call_automation")},
             "inputs": {"automationId": WF, "runtimeConnections": {}, "version": "-1", "parameters": {}, "synchronous": True, "executeOnSameVM": False},
             "dP": [], "dpOn": [], "metadata": {"isManuallyRenamed": True}, "options": {}, "callbacks": {"successEvents": [], "failureEvents": []},
             "advancedOptions": {"refetchOnWindowFocus": False, "timing": {"runQueryOnPageLoad": True, "runQueryPeriodically": False}, "runBehaviour": "automatic"}}
    if rk not in r:
        r[rk] = ua.call("POST", "/api/entity", {"entityType": "e_data_source", "properties": props})["id"]; save_reg(r)
    cur = ua.call("GET", f"/api/entity/e_data_source/{r[rk]}")
    ua.call("POST", "/api/entity/update", {**cur, "properties": props})
    return r[rk]

def nav_detail(acc_id, acc_name, eid):
    return [{"id": "evt_" + eid, "eventType": "onClick", "action": {"id": "act_" + eid, "actionType": "navigateToPage", "executionType": "delay",
             "payload": {"history": "push", "target": "_self", "pageId": DETAIL, "pageInputs": {"account_id": acc_id, "account_name": acc_name},
                         "overridePageAnimation": False}}}]

CTX = "var_attnctx"
def build_page(pg, ds, dash_id):
    D = lambda k: "{{ " + ds + "['data']['" + k + "'] }}"
    it = lambda rep, k: "{{ " + rep + "['context']['item']['" + k + "'] }}"
    SERIF = "font-family:'Spectral',serif;"
    root = pg.box("root_id", "padding:32px 48px 48px; gap:24px; min-height:100vh; max-width:1200px; margin:0 auto; width:100%;", name="page")
    back = pg.add(root, "Button", {"color": "brand", "size": "sm", "variant": "link", "styles": {"width": "w-fit"}},
                  {"contentMode": "text", "value": "← CXO dashboard", "type": "default"}, "padding:0 !important; color:var(--a3-ink) !important;", name="back")
    pg.blocks[back]["component"]["slots"] = {}
    pg.blocks[back]["events"] = [{"id": "evt_attnback", "eventType": "onClick", "action": {"id": "act_attnback", "actionType": "navigateToPage", "executionType": "delay",
        "payload": {"history": "push", "target": "_self", "pageId": dash_id, "overridePageAnimation": False}}}]
    top = pg.box(root, "justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap; margin-top:-8px;", direction="row", name="title_row")
    tl = pg.box(top, "gap:4px;")
    pg.text(tl, "CXO CONTROL TOWER", css=LAB + " color:var(--a3-r) !important;")
    pg.text(tl, TITLE, "display-xs", "medium", SERIF)
    pg.text(top, D("as_of"), "text-sm", css=MUTE)
    # page KPI strip
    kr = pg.repeat(root, D("kpis").replace("'] }}", "'] }}"), "page_kpis", grid=4, gap="gap-none")
    kc = pg.box(kr, "padding:18px 24px; gap:4px; background:var(--a3-card); height:100%;", name="page_kpi")
    pg.text(kc, it(kr, "label"), css=LAB)
    kv = pg.box(kc, "align-items:baseline; gap:6px;", direction="row")
    pg.text(kv, it(kr, "v"), "display-xs", "medium", SERIF, attrs={"data-a3-fg": it(kr, "tone")})
    pg.text(kv, it(kr, "unit"), "text-sm", css=MUTE)
    pg.text(kc, it(kr, "note"), css=MUTE)
    hdr = pg.box(root, "justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap; border-bottom:1px solid var(--a3-line); padding-bottom:10px; margin-top:8px;", direction="row")
    pg.text(hdr, "Ranked by ARR at risk", "text-sm", "semi-bold")
    pg.text(hdr, "Red = health below 50, or an overdue escalation raised by the client by email", css=MUTE)
    pg.text(root, "No account is red today.", "text-md", css=CARD, name="empty", visible={"value": "conditions", "conditions": cond(D("empty"), "yes")})
    # account cards
    rp = pg.repeat(root, "{{ " + ds + "['data']['accounts'] }}", "cards", gap="gap-xl")
    card = pg.box(rp, "background:var(--a3-card); border-radius:14px; padding:28px; gap:24px; margin-bottom:8px;", name="card")
    h = pg.box(card, "justify-content:space-between; align-items:flex-start; gap:16px;", direction="row")
    hl = pg.box(h, "align-items:baseline; gap:20px;", direction="row")
    pg.text(hl, it(rp, "rank"), css=MUTE)
    hn = pg.box(hl, "gap:4px;")
    nm = pg.text(hn, it(rp, "account_name"), "display-xs", "medium", SERIF + " cursor:pointer;")
    pg.blocks[nm]["events"] = nav_detail(it(rp, "account_id"), it(rp, "account_name"), "attnname")
    pg.text(hn, it(rp, "meta"), "text-sm", css=MUTE)
    hr = pg.box(h, "align-items:center; gap:14px; flex:none;", direction="row")
    pg.pill(hr, "Red", "R")
    hs = pg.box(hr, "align-items:flex-end; gap:0;")
    pg.text(hs, it(rp, "score"), "display-xs", "medium", SERIF + " text-align:right;", attrs={"data-a3-fg": "R"})
    pg.text(hs, "health / 100", css=MUTE + " text-align:right;")
    body = pg.box(card, "display:grid !important; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:32px; align-items:start;", direction="row", name="card_body")
    left = pg.box(body, "gap:10px; min-width:0;")
    pg.text(left, "THE BLOCKER", css=LAB + " color:var(--a3-r) !important;")
    pg.text(left, it(rp, "blocker"), "text-sm", "semi-bold")
    cr = pg.repeat(left, it(rp, "chips"), "chips", grid=3, gap="gap-sm")
    pg.text(cr, it(cr, "t"), css="border:1px solid var(--a3-line); border-radius:999px; padding:3px 10px !important; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%; width:fit-content;", name="chip")
    al = pg.box(left, "gap:6px; border-top:1px solid var(--a3-line); padding-top:14px; margin-top:6px;", name="also",
                visible={"value": "conditions", "conditions": cond(it(rp, "has_also"), "yes")})
    pg.text(al, "ALSO OVERDUE", css=LAB)
    ar = pg.repeat(al, it(rp, "also"), "also_rows", gap="gap-xs")
    pg.text(ar, it(ar, "t"), "text-sm")
    right = pg.box(body, "gap:12px; min-width:0;")
    pg.text(right, "WHERE THE HEALTH WENT", css=LAB)
    br = pg.box(right, "height:22px; border-radius:4px; overflow:hidden; border:1px solid var(--a3-line); background:var(--a3-card);", direction="row", name="bar")
    for i in range(4):
        pg.box(br, "height:100%;", {"data-attn-sw": str(i), "data-a3-grow": "{{ " + rp + "['context']['item']['bar'][" + str(i) + "]['grow'] }}"})
    lg = pg.repeat(right, it(rp, "bar"), "legend", grid=2, gap="gap-sm")
    li = pg.box(lg, "justify-content:space-between; align-items:center; gap:8px; padding-right:24px;", direction="row")
    lk = pg.box(li, "align-items:center; gap:8px;", direction="row")
    pg.box(lk, "width:10px; height:10px; border-radius:2px; flex:none;", {"data-attn-sw": it(lg, "sw")})
    pg.text(lk, it(lg, "k"))
    pg.text(li, it(lg, "v"))
    ks = pg.repeat(card, it(rp, "kpi"), "kpis", grid=5, gap="gap-none")
    kk = pg.box(ks, "padding:16px 18px; gap:4px; background:var(--a3-bg); height:100%;", name="kpi_cell")
    pg.text(kk, it(ks, "label"), css=LAB)
    pg.text(kk, it(ks, "v"), "display-xs", "medium", SERIF, attrs={"data-a3-fg": it(ks, "tone")})
    pg.text(kk, it(ks, "note"), css=MUTE)
    sel = "{{ " + CTX + "['value'] === " + rp + "['context']['item']['id'] ? 'yes' : 'no' }}"
    pg.text(card, it(rp, "context"), "text-sm", css=MUTE + " background:var(--a3-bg); border-radius:10px; padding:14px 18px !important;", name="context",
            visible={"value": "conditions", "conditions": cond(sel, "yes")})
    ft = pg.box(card, "justify-content:space-between; align-items:center;", direction="row")
    tg = pg.add(ft, "Button", {"color": "brand", "size": "sm", "variant": "link", "styles": {"width": "w-fit"}},
                {"contentMode": "text", "value": "{{ " + CTX + "['value'] === " + rp + "['context']['item']['id'] ? 'Hide context' : 'Show context' }}", "type": "default"},
                "padding:0 !important; color:var(--a3-ink) !important; text-decoration:underline;", name="ctx_btn")
    pg.blocks[tg]["component"]["slots"] = {}
    pg.blocks[tg]["events"] = [{"id": "evt_attnctx", "eventType": "onClick", "action": {"id": "act_attnctx", "actionType": "setPageVariable", "executionType": "delay",
        "payload": {"variableId": CTX, "method": "setPageVariable", "operationDetails": {"operation": "SET",
                    "value": "{{ " + CTX + "['value'] === " + rp + "['context']['item']['id'] ? '' : " + rp + "['context']['item']['id'] }}"}}}}]
    op = pg.add(ft, "Button", {"color": "brand", "size": "sm", "variant": "link", "styles": {"width": "w-fit"}},
                {"contentMode": "text", "value": "Open account →", "type": "default"}, "padding:0 !important; color:var(--a3-r) !important;", name="open_btn")
    pg.blocks[op]["component"]["slots"] = {}
    pg.blocks[op]["events"] = nav_detail(it(rp, "account_id"), it(rp, "account_name"), "attnopen")
    pg.text(root, "Health (v4) = 40% issue health + 40% client sentiment (14-day mean) + 20% delivery (weekly manual RAG); missing sub-scores are dropped and the weights rescaled.", css=MUTE + " border-top:1px solid var(--a3-line); padding-top:14px !important; margin-top:16px;")
    R.wire({b: pg.blocks[b] for b in pg.new}, {ds})

def page_css(pg):
    rules = []
    for b in pg.new:
        a = pg.blocks[b].get("additional")
        if a:
            rules.append(a.pop("customCSS", "")); a.pop("isCustomCSSValid", None)
            if not a: pg.blocks[b].pop("additional")
    by = {b["displayName"]: bid for bid, b in pg.blocks.items() if bid in pg.new}
    s = lambda n: f"[data-block-id='{by['attn_' + n]}']"
    sw = "".join(f"[data-attn-sw='{i}']{{background:{c} !important;}}" for i, c in enumerate(("#AC3D3D", "#C9958B", "#DDB9B1", "#EBD6D0", "#F3E9E5")))
    grow = "".join(f"[data-a3-grow='{i}']{{flex:{i} 1 0 !important; width:auto !important;}}" for i in range(1, 101))
    return ("<style>\n:root{--a3-bg:#F5F3EE;--a3-card:#FFFFFF;--a3-nt:#EEECE7;--a3-line:#E8E4DC;--a3-ink:#1E1E1B;--a3-mute:#6E6A61;"
            "--a3-g:#28734A;--a3-a:#C88724;--a3-r:#AC3D3D;--a3-n:#8C877C;--a3-rt:#F4E4E4;}\n"
            "[data-block-id='root_id']{background:var(--a3-bg);}\n"
            "[data-a3-fg='R'],[data-a3-fg='R'] *{color:var(--a3-r) !important;}"
            "[data-a3-pill]{border-radius:999px; letter-spacing:.14em; text-transform:uppercase; width:fit-content; display:inline-block;}"
            "[data-a3-pill='R']{background:var(--a3-rt) !important;}[data-a3-pill='R'],[data-a3-pill='R'] *{color:var(--a3-r) !important;}\n"
            "[data-a3-grow]{flex:0 0 0 !important; width:0;}" + grow + sw + "\n"
            f"{s('page_kpis')}{{background:var(--a3-card); border-radius:14px; overflow:hidden;}}"
            f"{s('page_kpi')}{{border-left:1px solid var(--a3-line);}}"
            f"{s('kpis')}{{border-radius:10px; overflow:hidden;}}{s('kpi_cell')}{{border-left:1px solid var(--a3-card);}}"
            "\n"
            + "\n".join(r for r in rules if r) +
            f"\n@media (max-width:900px){{{s('page')}{{padding:16px !important;}}{s('card_body')}{{grid-template-columns:1fr !important;}}}}\n</style>")

def push_page():
    pid = ensure_page()
    ds = ensure_ds(pid, "data", "attn_accounts")
    cur = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": pid, "allowedEntityTypes": ["e_component"]})["entity"]
    pg = P(existing=fixed_blocks(), prefix="attn_")
    build_page(pg, ds, DASH)
    props = dict(cur["properties"])
    props["pageVariables"] = {**(props.get("pageVariables") or {}), CTX: {"name": "contextOpenFor", "type": "string", "id": CTX, "createdTime": int(time.time() * 1000), "initialValue": ""}}
    props["blocks"] = pg.blocks
    props["customCode"] = {**(props.get("customCode") or {}), "header": page_css(pg)}
    props["metadata"] = {**props.get("metadata", {}), "_blockCounter": pg.counter}
    r = ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
                {"entity": {**cur, "properties": props}, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": APP}]})
    return pid, ds, len(pg.new), [(x.get("id"), x.get("version")) for x in (r if isinstance(r, list) else [r])]

# ---------------------------------------------------------------- CXO dashboard card
SRC_CARD, ROW = "b_GgDxl", "b_mNZdc"     # 'Use cases under development' card, second KPI row
def dash_card(page_id):
    ds = ensure_ds(DASH, "card", "attn_accounts_card")
    cur = ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": DASH, "allowedEntityTypes": ["e_component"]})["entity"]
    r = reg()
    if r.get("dash_seen_version") and cur.get("version") != r["dash_seen_version"] and "--force" not in sys.argv:
        raise SystemExit(f"CXO dashboard changed since my last save (v{r['dash_seen_version']} -> v{cur.get('version')}); not overwriting.")
    props = dict(cur["properties"]); B = props["blocks"]
    if r.get("dash_card") and r["dash_card"] in B:   # replace my earlier copy
        gone, stack = set(), [r["dash_card"]]
        while stack:
            b = stack.pop()
            if b in B and b not in gone:
                gone.add(b); stack += [x for x in (B[b]["component"].get("content") or {}).get("blockIds", []) if x != "__PLACEHOLDER__"]
                stack += [sl["blockId"] for sl in (B[b]["component"].get("slots") or {}).values() if isinstance(sl, dict) and sl.get("blockId")]
        for b in gone: B.pop(b)
        B[ROW]["component"]["content"]["blockIds"] = [x for x in B[ROW]["component"]["content"]["blockIds"] if x not in gone]
    pg = P(existing=B, prefix="attn_")
    idmap = {}
    def clone(bid, parent):
        nb = copy.deepcopy(B[bid]); new = pg._id(); idmap[bid] = new
        nb["id"] = new; nb["parentId"] = parent; nb["displayName"] = "attn_" + nb.get("displayName", "block")
        pg.blocks[new] = nb; pg.new.append(new)
        c = nb["component"].get("content") or {}
        if "blockIds" in c: c["blockIds"] = [clone(x, new) if x != "__PLACEHOLDER__" else x for x in c["blockIds"]]
        for sl in (nb["component"].get("slots") or {}).values():
            if isinstance(sl, dict) and sl.get("blockId") in B: sl["blockId"] = clone(sl["blockId"], new)
        css = (nb.get("additional") or {}).get("customCSS")
        if css: nb["additional"]["customCSS"] = css.replace(bid, new)
        return new
    card = clone(SRC_CARD, ROW)
    rowc = B[ROW]["component"]["content"]["blockIds"]; rowc.insert(len(rowc) - 1, card)
    kids = [x for x in pg.blocks[card]["component"]["content"]["blockIds"] if x != "__PLACEHOLDER__"]
    lab_, big, sub, link = kids
    D = lambda k: "{{ " + ds + "['data']['" + k + "'] }}"
    pg.blocks[lab_]["component"]["content"]["value"] = "ACCOUNTS THAT NEED ATTENTION"
    oldv = pg.blocks[big]["component"]["content"]["value"]
    pg.blocks[big]["component"]["content"]["value"] = re.sub(r"\{\{.*?\}\}", D("rub_count"), oldv)
    pg.blocks[sub]["component"]["content"]["value"] = D("rub_names_line")
    # link card: relabel and point it at the new page; the whole card is clickable too
    lk = pg.blocks[link]
    for b in pg.new:
        c = pg.blocks[b]["component"].get("content") or {}
        if b not in (lab_, big, sub) and isinstance(c.get("value"), str) and "→" in c["value"]: c["value"] = "view accounts that need attention →"
    tip = ((pg.blocks[link]["component"]["content"].get("addOns") or {}).get("tooltip") or {})
    if tip: tip["content"] = "view accounts that need attention →"
    go = {"id": "act_attngo", "actionType": "navigateToPage", "executionType": "delay",
          "payload": {"history": "push", "target": "_self", "pageId": page_id, "overridePageAnimation": False}}
    pg.blocks[link]["events"] = [{"id": "evt_attngo", "eventType": "onClick", "action": go}]
    pg.blocks[card]["events"] = [{"id": "evt_attngo2", "eventType": "onClick", "action": {**go, "id": "act_attngo2"}}]
    pg.blocks[card].setdefault("additional", {})["customCSS"] = (pg.blocks[card]["additional"].get("customCSS", "") +
        f"\n[data-block-id='{card}'] {{ cursor:pointer; border-top:3px solid #AC3D3D; }}")
    # rebuild bindings for the cloned blocks: drop the source card's data source, depend on mine
    for b in pg.new:
        blk = pg.blocks[b]
        if blk.get("dataSourceIds") or blk.get("dpOn"):
            blk["dataSourceIds"], blk["dpOn"] = [], []
    for b in (big, sub): pg.blocks[b].setdefault("visibility", {"value": True})
    R.wire({b: pg.blocks[b] for b in pg.new if b in (big, sub)}, {ds})
    props["blocks"] = pg.blocks
    counter = dict(props.get("metadata", {}).get("_blockCounter", {}))
    for b in pg.new:
        t = pg.blocks[b]["component"]["componentType"]; counter[t] = counter.get(t, 0) + 1
    props["metadata"] = {**props.get("metadata", {}), "_blockCounter": counter}
    res = ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
                  {"entity": {**cur, "properties": props}, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": APP}]})
    res = res if isinstance(res, list) else [res]
    r = reg(); r["dash_card"] = card; r["dash_seen_version"] = max(x.get("version", 0) for x in res if x.get("id") == DASH); save_reg(r)
    return ds, card, len(pg.new), r["dash_seen_version"]

if __name__ == "__main__":
    ua.ensure_session()
    if "page" in sys.argv: print("page:", push_page())
    if "dash" in sys.argv: print("dash card:", dash_card(reg()["page"]))
