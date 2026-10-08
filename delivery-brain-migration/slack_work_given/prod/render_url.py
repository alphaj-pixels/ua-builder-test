"""Render app pages to PDF/PNG via the platform export (temporary workflow; delete with --cleanup)."""
import sys, json, urllib.request, urllib.parse; sys.path.insert(0,'.')
import sales, ua, db_wf as W, pymupdf
ua.ensure_session()
reg = json.load(open("db_automations.json"))
if "--cleanup" in sys.argv:
    if reg.get("tmp_render"): ua.call("POST", f"/api/workflow-definition/delete/{reg.pop('tmp_render')}"); json.dump(reg, open("db_automations.json", "w"), indent=1); print("deleted tmp render")
    sys.exit()
nodes = [W.start({"url": {"type": "string"}}, []),
    W.node("n_pdf", "ACTION", "Export page to PDF", "utility_by_unifyapps", "utility_by_unifyapps_export_unifyapps_pages_to_pdf",
           {"page": {"format": "a4", "layout": "portrait", "scale": 0.6, "timeout": 30000},
            "pdfPages": [{"url": "{{ n_in.outputs.url }}", "fileName": "check", "externalPage": False}], "exportType": "PDF", "useCustomFonts": False}, 2),
    W.node("n_pub", "ACTION", "Download URL", "utility_by_unifyapps", "utility_by_unifyapps_generate_public_url",
           {"file": "{{ n_pdf.outputs.file[0] }}", "expiryTime": 1, "preview": False}, 3),
    W.stop({"url": "{{ n_pub.outputs.url }}"}, 4)]
wid, _, _ = W.save("TMP | page render check", "temporary, deleted after the check", nodes, [W.e("n_in", "n_pdf"), W.e("n_pdf", "n_pub"), W.e("n_pub", "n_out")], reg.get("tmp_render"), tags=("TMP",))
reg["tmp_render"] = wid; json.dump(reg, open("db_automations.json", "w"), indent=1)
for arg in sys.argv[1:]:
    path, out = arg.split("|")
    r = W.test(wid, {"url": f"{ua.BASE}/p/0/interfaces/e-69f9786e285b7c092e6d2749/preview/{path}"}, nodes=("n_out",), timeout_s=200)
    link = ((r["nodes"].get("n_out") or {}).get("outputs") or {}).get("url")
    if not link: print(out, r["status"], r.get("failed")); continue
    with urllib.request.urlopen(link, timeout=60) as resp: open(out + ".pdf", "wb").write(resp.read())
    d = pymupdf.open(out + ".pdf"); t = " ".join(p.get_text() for p in d)
    for i, p in enumerate(d): p.get_pixmap(dpi=80).save(f"{out}_p{i+1}.png")
    print(out, "pages", len(d), "raw {{:", t.count("{{"))
