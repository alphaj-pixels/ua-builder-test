import sys, json, time; sys.path.insert(0, '.')
import ua, a360_agents as A
ua.ensure_session()
aid = json.load(open("assign_agent.json"))["agent"]
def fetch(t):
    out, off = [], 0
    while True:
        r = ua.call("POST", f"/api/entity/{t}", {"page": {"limit": 200, "offset": off}}); out += r.get("objects") or []
        if not r.get("hasMore"): return out
        off += 200
um = [x["properties"] for x in fetch("db_user_management")]
roster = [p for p in um if "forward deployed" in str(p.get("role", "")).lower() and "@" in str(p.get("emp_email", ""))]
print("FDSE roster:", len(roster))
names = ["Alpha", "harshit", "Anusha", "prabhanshu", "Sujal", "Saumya", "Shamyak", "awanish", "ajinkya", "Syam", "Pranathi", "Abhishek Kumar", "Avinish", "Lavanya", "Vijaykumar", "Zetendra", "Raja Vamsi", "Tulasi", "Samridhi", "Archit"]
print("example people who are FDSEs:", [n for n in names if any(n.lower() in str(p.get("emp_name","")).lower() or n.lower() in str(p.get("emp_email","")).lower() for p in roster)])
msg = "ROSTER\n" + "\n".join(f"{p['emp_name']} | {p['emp_email'].lower()}" for p in roster) + "\n\nCONVERSATIONS\n" + open("assign_test_examples.txt").read()
t0 = time.time(); out = A.parse_json(A.ask(aid, msg)); print(f"agent {int(time.time()-t0)}s, message {len(msg)} chars")
for it in out.get("items", []): print(f"  {it['conversation_id']} {it['person_name']:24} {it['status']:11} {it.get('due',''):10} {it['kind']:10} {it['task']}")
print("checked:", out.get("checked_ids"))
