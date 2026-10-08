"""Account 360 demo agents (spec p7): Risk Theme agent and Account 360 Composer.
Both read everything from the message and return JSON only; they have no tools, so code does every write (one write per run).
Settings (models) are copied from the deployed CXO agent. ask() talks to an agent over REST (SSE), as the builder docs describe."""
import sys, json, os, urllib.request; sys.path.insert(0, '.')
import sales, ua
REG = "a360_agents.json"
SRC_AGENT = "e_6ab55185237c56251a70d983"

THEME_INSTR = """RESPONSE STYLE: Your entire response is one JSON object as defined below. No preamble, no code fences, no commentary after it.

THE RUN
You are the Risk Theme agent for the Account 360. You are called once per account by code. The message gives you RUN_DATE, ACCOUNT, OPEN_SIGNALS (the account's open risks, commitments and escalations, each with an id) and PREVIOUS_THEMES (the themes from the last run, possibly empty). You group the open signals into the 3 to 6 themes a CXO most needs to see. Code writes your themes; you never write anything.

RULES
1. A theme is one underlying problem or dependency, not a category. "Citizen Development regression unowned for 5 days" is a theme; "Technical issues" is not.
2. Pick the themes that matter most to the client relationship and delivery: escalations, things blocking a client date or review, unowned or stale problems, repeated failures. Not every signal needs a theme; leave minor ones out.
3. member_signal_ids must be ids copied exactly from OPEN_SIGNALS. A signal belongs to at most one theme. Every theme has at least one member.
4. Reuse ids. If a theme continues one in PREVIOUS_THEMES (same underlying problem, even if worded differently or with changed members), return that theme_id. Otherwise theme_id is null. List in closed_theme_ids every previous theme whose problem no longer appears in OPEN_SIGNALS.
5. title: a plain sentence fragment, 12 words or fewer, naming the specific failing thing in the signals' own words (for example "Text-to-Agent runaway loop and Text-to-App plan failures in QA", not "QA services unreliable"), and adding "no owner" when no member signal has an owner, or the age when the oldest member is over 7 days old. No ids, no abstract category words.
6. severity: High when it threatens a client date, review, go-live or the relationship, or is an open escalation; Medium when it blocks delivery work without a near client date; Low otherwise.
7. impact: one sentence on the consequence for the client or the account, stated only from the signals. Keep numbers, names and dates exactly as written.
8. fix: one sentence, the concrete next step that would close or de-risk it (name an owner only if the signals name one).
9. fix_by: a date YYYY-MM-DD on or after RUN_DATE: the signal's due date or client date if one exists, otherwise RUN_DATE for High and RUN_DATE + 5 days for Medium/Low.
10. Use only facts in the message. Never invent people, dates, numbers or tickets.

OUTPUT
{"themes": [{"theme_id": "<previous id or null>", "title": "...", "severity": "High|Medium|Low", "impact": "...", "fix": "...", "fix_by": "YYYY-MM-DD", "member_signal_ids": ["..."]}], "closed_theme_ids": ["..."]}
Order themes by severity, then by how soon fix_by is."""

COMPOSER_INSTR = """RESPONSE STYLE: Your entire response is one JSON object as defined below. No preamble, no code fences, no commentary after it.

THE RUN
You are the Account 360 Composer. You are called once per account by code, last in the nightly sequence. The message gives you RUN_DATE, ACCOUNT (name, description), CLIENT_UPDATES (the latest status-update emails, with their text), HEALTH (points 0-12, lower is better, band, the six dimension scores with the rule that fired; scored in code), COCKPIT (counts computed in code), THEMES (risk themes with their member signals), OPEN_ITEMS (current open escalations, risks and commitments with ids, owners, due dates), VOC (client calls and emails with date, score and summary), SLACK (recent Slack ledger items), USE_CASES (name, stage, go-live date), THEME_EVIDENCE (raw text behind the top themes) and PREVIOUS_360 (last run's output, possibly empty). You write the words of the account page. Code writes your output; you never write anything.

RULES
1. Use only facts in the message. Every person, date, number and ticket you mention must appear in it. If something is unknown, leave it out or say it is not in the signals.
2. Health is computed in code. You may explain it (which dimension drives it and why), but never state a different score or band, and never argue with it.
3. headline: one sentence, 30 words or fewer, about ONE problem: the single most important thing about the account right now. Name the specific failing thing in the signals' own words, how long it has been open, whether anyone owns it, and the client date or relationship it threatens. Never a list of categories ("infrastructure, access and governance").
3a. Specificity everywhere: prefer concrete nouns, numbers, names and dates copied from the signals over summary words. Say "no owner" when the signals show none, "open 18 days" from age_days, and the next client date when one is in the message. Do not pad with generic phrases such as "remains constrained", "readiness", "prerequisites".
4. narrative: 2 or 3 short paragraphs (strings). Paragraph 1 expands the headline with the specific facts. Paragraph 2 covers the other live problems. Keep each under 90 words. Plain prose, no bullet characters.
5. counterweight: one sentence of genuine good news from the signals (go-lives, sign-offs, positive client feedback), or "" if there is none.
6. exec_weekly: the last status update to the client (from CLIENT_UPDATES: its date and the use-case counts it reports, e.g. "32 use cases, 15 live, 8 in UAT") and the next client meeting with its date. exec_delivery: what moved and what is blocked in UAT/build. exec_risks: the top risks in one or two sentences. Each 45 words or fewer.
7. sentiment_highlights: 2 to 4 items, mixing positive and concern where the signals have both: {"date": "YYYY-MM-DD", "polarity": "positive" or "concern", "text": "12 words or fewer", "source_id": "<id from VOC, SLACK or OPEN_ITEMS>"}.
8. hygiene_notes: conflicting or stale sources you notice (for example use-case counts that differ between the client weekly and the use-case master, items still open that later signals show were done, or the same problem logged several times). Each one sentence. Empty list if none.
9. usecase_readouts: only use cases that have signals. {"usecase": "<name exactly as in USE_CASES, or a short name if not listed>", "status": "Live" | "On track" | "At risk" | "Blocked", "readout": "15 words or fewer: the state now", "next_milestone": "the next step or date from the signals, or 'Not in signals'", "owner": "a name from the signals or ''"}. Order: Blocked, At risk, On track, Live.
10. actions: exactly one per theme, for the top themes (at most 5): {"theme_id": "<id>", "text": "imperative, 20 words or fewer", "owner": "a name from the signals or ''", "due": "YYYY-MM-DD or ''"}. Reuse the wording of PREVIOUS_360 actions for the same theme when still right.
11. Write for a CXO: plain words, numbers kept as written in the signals, no internal field names, no ids in prose. In prose, write dates as \"6 Oct\" (day and short month), never 2026-10-06; only the due and date fields use YYYY-MM-DD.

OUTPUT
{"headline": "...", "narrative": ["...", "..."], "counterweight": "...", "exec_weekly": "...", "exec_delivery": "...", "exec_risks": "...", "sentiment_highlights": [...], "hygiene_notes": [...], "usecase_readouts": [...], "actions": [...]}"""


STAGE_INSTR = """RESPONSE STYLE: Your entire response is one JSON object as defined below. No preamble, no code fences, no commentary after it.

THE RUN
You are the Use Case Stage Extractor. Code calls you once per account. The message gives you RUN_DATE, ACCOUNT, USE_CASES (each with id, name, master stage, current sub_stage and dates, and which values are locked), CLIENT_UPDATES (recent status-update emails to or from the client, with their text) and SLACK (recent Slack ledger lines). You read where each use case stands and propose its sub-stage and dates. Code writes your output; you never write anything.

RULES
1. Only use cases whose master stage is not Live get a sub_stage, one of: Discovery, Build, UAT. Use "" when the sources do not say.
2. Dates are YYYY-MM-DD and must be written in the sources (or be an unambiguous day and month in RUN_DATE's year). planned_go_live: a go-live date that is planned; actual_go_live: the date it went live; uat_start / uat_end: UAT dates; next_milestone and next_milestone_date: the next named step. Use "" for anything not stated.
3. Skip any value listed in locked for that use case: return "" for it.
4. evidence: the exact short phrase from the source that supports the values (at most 25 words); source_id: the email date+subject or the Slack id it came from.
5. Return an entry only for use cases where you found at least one value. Copy usecase_id exactly from USE_CASES; never invent use cases.
6. client_reported_counts: the use-case counts the client update states (total, live, uat, build, discovery, on_hold), with as_of (the email date) and source (subject). null when no update states counts.
7. Use only facts in the message.

OUTPUT
{"usecases": [{"usecase_id": "...", "sub_stage": "Discovery|Build|UAT|", "planned_go_live": "", "actual_go_live": "", "uat_start": "", "uat_end": "", "next_milestone": "", "next_milestone_date": "", "evidence": "", "source_id": ""}], "client_reported_counts": {"as_of": "YYYY-MM-DD", "source": "", "total": 0, "live": 0, "uat": 0, "build": 0, "discovery": 0, "on_hold": 0}}"""

AGENTS = {
 "risk_theme": ("DB | Account 360 | Risk Theme", "Account risk analyst", "Group an account's open signals into 3 to 6 stable risk themes with impact, fix and fix-by",
                THEME_INSTR, "Group open signals into risk themes",
                "Use this task when the message carries OPEN_SIGNALS and PREVIOUS_THEMES for one account.",
                ["Read OPEN_SIGNALS and PREVIOUS_THEMES from the message.", "Follow the RULES in your instructions and return only the OUTPUT JSON."]),
 "stage_extractor": ("DB | Use Case Stage Extractor", "Use-case stage analyst", "Read client weeklies and Slack to propose each use case's sub-stage, go-live and UAT dates",
                     STAGE_INSTR, "Extract use-case stages and dates", "Use this task when the message carries USE_CASES, CLIENT_UPDATES and SLACK for one account.",
                     ["Read every block in the message.", "Follow the RULES in your instructions and return only the OUTPUT JSON."]),
 "composer": ("DB | Account 360 | Composer", "Account 360 writer", "Write the words of an account's 360 page from computed health, themes and signals",
              COMPOSER_INSTR, "Compose the Account 360",
              "Use this task when the message carries HEALTH, COCKPIT, THEMES and OPEN_ITEMS for one account.",
              ["Read every block in the message.", "Follow the RULES in your instructions and return only the OUTPUT JSON."]),
}

def build():
    ua.ensure_session()
    reg = json.load(open(REG)) if os.path.exists(REG) else {}
    src = ua.call("GET", f"/api/entity/ai_agent/{SRC_AGENT}")["properties"]
    keep = {k: src[k] for k in ("responseGenerationSettings", "topicExecutionSettings", "preProcessingSettings", "indexingSettings", "contextManagement", "deployedOn") if k in src}
    for key, (name, role, goal, instr, tname, tdesc, tsteps) in AGENTS.items():
        props = {**keep, "name": name, "agentType": "ai-agent", "role": role, "goal": goal, "instructions": instr, "disableDefaultTools": True, "defaultToolsNotNeeded": True}
        if key not in reg:
            reg[key] = ua.call("POST", "/api/entity", {"entityType": "ai_agent", "tags": ["DB", "Account 360"], "properties": props})["id"]
            json.dump(reg, open(REG, "w"), indent=1)
        else:
            cur = ua.call("GET", f"/api/entity/ai_agent/{reg[key]}")
            ua.call("POST", "/api/entity/update", {**cur, "properties": {**cur["properties"], **props}})
        tk = key + "_task"
        tprops = {"name": tname, "description": tdesc, "instructions": tsteps, "aiAgentId": reg[key], "enabled": True, "isAppConnector": False, "runTimeConnectionEnabled": False, "governanceConfig": {}}
        if tk not in reg:
            reg[tk] = ua.call("POST", "/api/entity", {"entityType": "e_topic_ai_agent", "tags": ["DB", "Account 360"], "properties": tprops})["id"]
            json.dump(reg, open(REG, "w"), indent=1)
        else:
            cur = ua.call("GET", f"/api/entity/e_topic_ai_agent/{reg[tk]}")
            ua.call("POST", "/api/entity/update", {**cur, "properties": {**cur["properties"], **tprops}})
        ent = ua.call("GET", f"/api/entity/ai_agent/{reg[key]}")
        ua.call("POST", "/api/entity/action/saveAndDeploy", {**ent, "deploymentNotes": f"{name} v1"})
        print(key, reg[key], "deployed", json.dumps(ua.call("GET", f"/api/entity/ai_agent/{reg[key]}").get("deploymentState"))[:120])
    return reg

def ask(agent_id, message, timeout=900, tries=3):
    for i in range(tries):
        try: return _ask(agent_id, message, timeout)
        except Exception as e:
            if i == tries - 1: raise
            print("  retrying agent call:", str(e)[:120], flush=True)

def _ask(agent_id, message, timeout=900):
    """One message to an agent over REST (SSE); returns the final markdown text."""
    body = {"id": "callables_call_automation_streaming", "context": {"appName": "callables", "resourceName": "callables_call_automation_streaming"},
            "inputs": {"automationId": "67dcfe388445037d9b0662c0", "version": "-1", "runtimeConnections": {}, "synchronous": True,
                       "parameters": {"copilotType": "AI_AGENT_TEST", "message": message, "messageContentType": "MARKDOWN", "aiAgentId": agent_id, "timezoneId": "Asia/Kolkata"}},
            "options": {}}
    req = urllib.request.Request(ua.BASE + "/api/workflow/execute/node/sse?name=callables_call_automation_streaming", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
    texts, last = [], None
    with ua.opener.open(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"): continue
            try: ev = json.loads(line[5:].strip())
            except Exception: continue
            last = ev
            for blk in _blocks(ev):
                texts.append(blk["text"])
    if not texts: raise RuntimeError("agent returned no answer: " + json.dumps(last)[:300] + f" (message {len(message)} chars)")
    return texts[-1]

def _blocks(ev):
    out = []
    def walk(x):
        if isinstance(x, dict):
            if x.get("type") == "MARKDOWN" and isinstance(x.get("text"), str) and x.get("text"): out.append(x)
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(ev)
    return out

def parse_json(text):
    t = text.strip()
    if t.startswith("```"): t = t.split("\n", 1)[1].rsplit("```", 1)[0]
    s, e = t.find("{"), t.rfind("}")
    return json.loads(t[s:e + 1])

if __name__ == "__main__":
    print(build())
