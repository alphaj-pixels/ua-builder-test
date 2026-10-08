"""Delivery Brain RBAC, step 1 (page level).
- Admin = the signed-in user has a role whose name contains "admin", or "owner" (userContext.roles).
- CXO dashboard: admins only (its content and the CXO nav item on desktop and mobile); others see a short notice.
- "Accounts needing attention" card and page: Sumeet, Jay and Alpha only.
Edits fresh copies of each page, touching only the blocks named here.
"""
import sys, json, re; sys.path.insert(0, '.')
import sales, ua
from a360_bound import cond, Page

APP = "e-69f9786e285b7c092e6d2749"
DASH = "e_6a89562d92a5fd1fe3080da3"
HUB = "e_6a830a0e4b316420e0deb4fd"          # Customer Hub (account-directory)
NAV_DESKTOP, NAV_MOBILE = "e_69f979151dfa014b39659988", "e_69f979151dfa014b3965998a"
ADM = "(userContext['roles'] || []).some(r => /admin|owner/i.test(String((r && r['name']) || '')))"
TRIO_EMAILS = ["sumeet@unifyapps.com", "jay.shah@unifyapps.com", "alpha.jose@unifyapps.com"]
TRIO = json.dumps(TRIO_EMAILS).replace('"', "'") + ".includes(String(userContext['email'] || '').toLowerCase())"

def deps(b):
    """Make the block re-evaluate when userContext changes."""
    d = [x for x in (b.get("dpOn") or []) if x.get("id") != "userContext"]
    d.append({"id": "userContext", "p": ["userContext['roles']", "userContext['email']"]})
    b["dpOn"] = d

def gate(b, expr, show=True):
    b["visibility"] = {"value": "conditions", "conditions": cond("{{ (" + expr + ") ? 'yes' : 'no' }}", "yes" if show else "no")}
    cp = [x for x in (b.get("cP") or []) if x.get("p") != "visibility.conditions"] + [{"p": "visibility.conditions"}]
    dp = [x for x in (b.get("dP") or []) if not x.get("p", "").startswith("visibility.")] + [{"p": "visibility.conditions.payload.filters[0].property"}]
    b["cP"], b["dP"] = cp, dp
    deps(b)

def load(eid):
    return ua.call("POST", "/api/entity/embedded-entities/e_component", {"entityId": eid, "allowedEntityTypes": ["e_component"]})["entity"]

def save(ent):
    r = ua.call("POST", "/api/entity/create-update-or-delete/hierarchical",
                {"entity": ent, "requestType": "UPDATED", "parentEntities": [{"type": "e_interface", "id": APP}]})
    r = r if isinstance(r, list) else [r]
    return [(x.get("id"), x.get("version")) for x in r]

def dashboard(card_id):
    ent = load(DASH); B = ent["properties"]["blocks"]
    json.dump(ent, open("rbac_before_dash.json", "w"))
    main = [x for x in B["root_id"]["component"]["content"]["blockIds"] if x in B and B[x].get("visibility") != {"value": False}]
    for x in main: gate(B[x], ADM)
    gate(B[card_id], TRIO)
    pg = Page(existing=B, prefix="rbac_")
    if not any(b.get("displayName") == "rbac_notice" for b in B.values()):
        box = pg.stack("root_id", css="padding:64px 24px; gap:12px; align-items:center;", name="notice", align="center")
        pg.text(box, "The CXO dashboard is available to admins only.", "text-md", "semi-bold", css="text-align:center;")
        pg.text(box, "Your accounts are in the Customer Hub.", "text-sm", css="text-align:center; color:var(--text-secondary) !important;")
        btn = pg.add(box, "Button", {"color": "brand", "size": "md", "variant": "solid", "styles": {"width": "w-fit"}},
                     {"contentMode": "text", "value": "Go to Customer Hub", "type": "default"}, None, name="notice_btn")
        pg.blocks[btn]["component"]["slots"] = {}
        pg.blocks[btn]["events"] = [{"id": "evt_rbachub", "eventType": "onClick", "action": {"id": "act_rbachub", "actionType": "navigateToPage",
            "executionType": "delay", "payload": {"history": "push", "target": "_self", "pageId": HUB, "overridePageAnimation": False}}}]
        gate(pg.blocks[box], ADM, show=False)
        counter = dict(ent["properties"].get("metadata", {}).get("_blockCounter", {}))
        for b in pg.new:
            t = pg.blocks[b]["component"]["componentType"]; counter[t] = counter.get(t, 0) + 1
        ent["properties"]["metadata"] = {**ent["properties"].get("metadata", {}), "_blockCounter": counter}
    ent["properties"]["blocks"] = pg.blocks
    return save(ent)

def nav(eid, bid):
    ent = load(eid); json.dump(ent, open(f"rbac_before_{eid}.json", "w"))
    gate(ent["properties"]["blocks"][bid], ADM)
    return save(ent)

if __name__ == "__main__":
    ua.ensure_session()
    card = json.load(open("attn_page.json"))["dash_card"]
    print("dashboard", dashboard(card))
    print("desktop nav", nav(NAV_DESKTOP, "b_nav_cxo_item"))
    print("mobile nav", nav(NAV_MOBILE, "b_nav_cxo"))
