import json, re, collections, datetime, hashlib
S = json.load(open("fd/snap.json"))
RB = "e_6ac14d1c1924167ba878f874"
C = lambda x: json.dumps(x, sort_keys=True, separators=(",", ":"))
ts = lambda ms: datetime.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d") if ms else "-"
def norm(x):
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if k in ("debug", "dirty"): continue
            if k in ("dataSourceIds", "dpOn", "cP") and not v: continue
            if k == "customCSS" and isinstance(v, str): v = re.sub(r"\s+", "", v); out[k] = v; continue
            if k == "dP" and isinstance(v, list): out[k] = sorted({C(i) for i in v}); continue
            if k == "dpOn" and isinstance(v, list): out[k] = sorted(C(norm(i)) for i in v); continue
            if k == "initialValue" and isinstance(v, str): v = re.sub(r"\{\{\s*\{", "{{{", re.sub(r"\}\s*\}\}", "}}}", v)).replace(" ", "")
            out[k] = norm(v)
        return out
    if isinstance(x, list): return [norm(i) for i in x]
    return x
def leaves(x, p=""):
    if isinstance(x, dict):
        for k, v in x.items(): yield from leaves(v, f"{p}.{k}")
    elif isinstance(x, list) and x and all(isinstance(i, dict) and "id" in i for i in x):
        for i in x: yield from leaves(i, f"{p}[{i['id']}]")
    elif isinstance(x, list) and any(isinstance(i, (dict, list)) for i in x):
        for n, i in enumerate(x): yield from leaves(i, f"{p}[{n}]")
    else: yield p, x
def ldiff(a, b):
    la, lb = dict(leaves(a)), dict(leaves(b))
    return [(k, la.get(k, "<absent>"), lb.get(k, "<absent>")) for k in sorted(set(la) | set(lb)) if C(la.get(k)) != C(lb.get(k))]
PAGE_KEYS = ("blocks", "pageVariables", "pageFunctions", "interactions", "layout", "inputSchema", "outputSchema", "dataSources", "flags", "customCode", "name", "slug", "publicAccess")
rep = {"pages": [], "ds": [], "wfs": [], "objects": [], "agents": [], "app": {}, "unpublished": {}}
# ---------- pages
P, U = S["prod"]["pages"], S["uat"]["pages"]
pname = lambda p: p["properties"].get("name")
for pid in sorted(set(P) | set(U), key=lambda i: (pname(P.get(i) or U.get(i)) or "")):
    row = {"id": pid, "name": pname(P.get(pid) or U.get(pid))}
    if pid not in U: row["status"] = "prod only"
    elif pid not in P: row["status"] = "UAT only"
    else:
        pp, up = P[pid]["properties"], U[pid]["properties"]
        bp, bu = {k: norm(v) for k, v in (pp.get("blocks") or {}).items()}, {k: norm(v) for k, v in (up.get("blocks") or {}).items()}
        ch = [k for k in bp if k in bu and C(bp[k]) != C(bu[k])]
        other = [k for k in PAGE_KEYS if k != "blocks" and C(norm(pp.get(k))) != C(norm(up.get(k)))]
        row.update({"p_blocks": len(bp), "u_blocks": len(bu), "prod_only_blocks": len(set(bp) - set(bu)), "uat_only_blocks": len(set(bu) - set(bp)), "changed_blocks": len(ch), "other_keys": other,
                    "changed_names": [f"{bu[k]['component'].get('componentType')}:{bu[k].get('displayName')}" for k in ch][:8]})
        row["status"] = "same" if not (ch or other or row["prod_only_blocks"] or row["uat_only_blocks"]) else "differs"
    rep["pages"].append(row)
# ---------- data sources
for pid in sorted(set(P) | set(U), key=lambda i: (pname(P.get(i) or U.get(i)) or "")):
    dp = {d["id"]: d for d in S["prod"]["ds"].get(pid, [])}; du = {d["id"]: d for d in S["uat"]["ds"].get(pid, [])}
    for did in sorted(set(dp) | set(du)):
        d = dp.get(did) or du.get(did); row = {"page": pname(P.get(pid) or U.get(pid)), "id": did, "name": d["properties"].get("name"), "wf": (d["properties"].get("inputs") or {}).get("automationId")}
        if did not in du: row["status"] = "prod only"
        elif did not in dp: row["status"] = "UAT only"
        else:
            a, b = norm(dp[did]["properties"]), norm(du[did]["properties"])
            if C(a) == C(b): row["status"] = "same"
            else:
                dd = ldiff(a, b)
                kinds = set()
                for k, x, y in dd:
                    if RB in C([x, y]) or "rbac" in k: kinds.add("rbac")
                    elif "automationId" in k: kinds.add("workflow binding")
                    elif k.startswith(".dP") or k.startswith(".dpOn"): kinds.add("paths")
                    else: kinds.add("other")
                row.update({"status": "differs", "kinds": sorted(kinds), "n": len(dd), "sample": [(k, str(x)[:70], str(y)[:70]) for k, x, y in dd if not k.startswith(".dP")][:3]})
        rep["ds"].append(row)
# ---------- workflows
def wnorm(w): return {"nodes": sorted((norm(n) for n in w.get("nodes") or []), key=lambda n: n["id"]), "edges": sorted((norm(e) for e in w.get("edges") or []), key=lambda e: e.get("id") or C(e))}
for wid, r in S["wfs"].items():
    p, u = r["prod"], r["uat"]
    name = (p.get("name") if "_err" not in p else None) or (u.get("name") if "_err" not in u else None) or wid
    row = {"id": wid, "name": name.strip()}
    if "_err" in p and "_err" in u: continue
    if "_err" in u: row["status"] = "prod only"; row["p_state"] = (p.get("deploymentState") or {}).get("status")
    elif "_err" in p: row["status"] = "UAT only"; row["u_state"] = (u.get("deploymentState") or {}).get("status")
    else:
        a, b = wnorm(p), wnorm(u)
        row.update({"p_state": (p.get("deploymentState") or {}).get("status"), "u_state": (u.get("deploymentState") or {}).get("status"), "p_mod": ts(p.get("modifiedTime")), "u_mod": ts(u.get("modifiedTime"))})
        if C(a) == C(b): row["status"] = "same"
        else:
            pn, un = {n["id"]: n for n in a["nodes"]}, {n["id"]: n for n in b["nodes"]}
            chg = [k for k in un if k in pn and C(pn[k]) != C(un[k])]
            conn_only = chg and all(all("connectionId" in k for k, _, _ in ldiff(pn[c], un[c])) for c in chg) and set(pn) == set(un)
            row.update({"status": "connection id only" if conn_only else "differs", "prod_only_nodes": [pn[k].get("title") for k in pn if k not in un], "uat_only_nodes": [un[k].get("title") for k in un if k not in pn],
                        "changed_nodes": [un[k].get("title") or k for k in chg][:6], "edges_same": C(a["edges"]) == C(b["edges"])})
    rep["wfs"].append(row)
# ---------- objects
def fields(t):
    if not isinstance(t, dict) or "_err" in t: return None
    props = ((t.get("schema") or {}).get("schema") or {}).get("properties") or (t.get("schema") or {}).get("properties") or {}
    return {k: (v.get("type"), v.get("format")) for k, v in props.items()} if props else {k: None for k in re.findall(r'"name":\s*"([a-zA-Z_0-9]+)"', json.dumps(t))}
for o, r in S["objects"].items():
    fp, fu = fields(r["prod"]), fields(r["uat"])
    row = {"object": o}
    if fp is None and fu is None: continue
    if fu is None: row["status"] = "prod only"
    elif fp is None: row["status"] = "UAT only"
    else:
        row.update({"p_fields": len(fp), "u_fields": len(fu), "uat_only_fields": sorted(set(fu) - set(fp)), "prod_only_fields": sorted(set(fp) - set(fu)),
                    "type_diffs": sorted(k for k in set(fp) & set(fu) if fp[k] != fu[k])})
        row["status"] = "same" if not (row["uat_only_fields"] or row["prod_only_fields"] or row["type_diffs"]) else "differs"
    rep["objects"].append(row)
# ---------- agents
VOL = ("createdTime", "modifiedTime", "version", "lastModifiedBy", "lastPlatformUpdateBy", "lastPlatformUpdateOn", "ownerUserId", "deploymentState", "deployedVersion")
for a, r in S["agents"].items():
    p, u = r["prod"], r["uat"]
    name = ((p.get("properties") or {}).get("name") if "_err" not in p else None) or ((u.get("properties") or {}).get("name") if "_err" not in u else None) or a
    row = {"id": a, "name": name}
    if "_err" in p and "_err" in u: continue
    if "_err" in u: row["status"] = "prod only"
    elif "_err" in p: row["status"] = "UAT only"
    else:
        dd = ldiff(norm(p.get("properties")), norm(u.get("properties")))
        row["status"] = "same" if not dd else "differs"; row["diff_keys"] = sorted({k.split(".")[1] if k.count(".") else k for k, _, _ in dd})[:8]
    rep["agents"].append(row)
# ---------- app + unpublished
ap, au = (S["prod"]["app"].get("properties") or {}), (S["uat"]["app"].get("properties") or {})
rep["app"] = {"differing_keys": sorted(k for k in set(ap) | set(au) if C(norm(ap.get(k))) != C(norm(au.get(k))))}
for env in ("prod", "uat"):
    rep["unpublished"][env] = sorted(pname(S[env]["pages"][pid]) for pid, l in S[env]["live"].items()
                                    if isinstance(l, dict) and "_err" not in l and C(norm(l.get("properties"))) != C(norm(S[env]["pages"][pid]["properties"])))
    al = S[env]["app_live"]
    rep["unpublished"][env + "_app_version"] = {"draft": (S[env]["app"].get("deploymentState") or {}).get("version"), "live": al.get("version") if isinstance(al, dict) else None}
json.dump(rep, open("fd/report.json", "w"), indent=1, default=str)
cnt = lambda lst: dict(collections.Counter(r["status"] for r in lst))
print("PAGES", cnt(rep["pages"])); print("DATA SOURCES", cnt(rep["ds"])); print("WORKFLOWS", cnt(rep["wfs"])); print("OBJECTS", cnt(rep["objects"])); print("AGENTS", cnt(rep["agents"]))
print("APP keys differing:", rep["app"]["differing_keys"]); print("UNPUBLISHED:", rep["unpublished"])
