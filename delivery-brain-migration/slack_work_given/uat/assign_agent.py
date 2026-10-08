"""Slack Task Assignment agent (UAT): reads Slack conversations (db_slack_conversations.conversation_text) and returns who was given work.
No tools; code does every write. Settings copied from the deployed CXO agent, like the Account 360 agents."""
import sys, json, os; sys.path.insert(0, '.')
import ua
import a360_agents as A

REG = "assign_agent.json"
INSTR = """RESPONSE STYLE: Your entire response is one JSON object as defined below. No preamble, no code fences, no commentary.

THE RUN
You read Slack conversations from customer account channels and list every case where a person on the ROSTER was given work or is shown owning or doing work. The message gives ROSTER (name | email, one per line) and CONVERSATIONS (each starts with "### <id> | <account> | <channel> | <date>", then the message and its thread replies, each line "[time] Sender: text"). Code writes what you return; you never write anything.

WHAT COUNTS AS WORK (examples from real channels)
- A direct request to a person: "@Shamyak Can we please work on BRDs for Production Posting and Plant Maintenance to get a sign-off before the rollout?" -> Shamyak, request.
- One request to several people: "@awanish @ajinkya.jaiswal Pls make sure proper roles are assigned to everyone" -> one item for each of them.
- A hand-off in a thread: "@Raja Vamsi Please pick this", "@Tulasi Bandaru Please help him", "@Shubham Kumar can you help" -> each named person, request.
- An owner on a status line: "Account 360 page, one view of each customer account. @Alpha :white_check_mark:" -> Alpha, status done. "optimisation @harshit in progress ETA : 5 Oct" -> Harshit, in_progress, due 5 Oct. "@harshit blocked on email ingestion for expired users" -> Harshit, blocked.
- An owner named without @: "UC01 : SAGE - Build (POC - Syam)" -> Syam, owner of that use case.
- A dependency on people: "@Anusha depends on @Sujal Aggarwal @Saumya Pandey" -> Anusha (blocked, owner) and Sujal and Saumya (request: provide what Anusha needs).
- Someone taking work on: "Sure, let me align" or "I'll take this" by a ROSTER person -> that person, self.
WHAT DOES NOT COUNT
- cc lists and trailing tag lists: "cc: @Abhishek Singh sir @Archit Kumar (TDM)", a closing line like "@Adi @Abhishek Singh @Sandeep @Jay Shah @Santosh Singh".
- Broadcasts with nobody named (@group, @channel, @here, "anyone available?").
- Team-level items with no person: "UA team to share updated workday policies", "Sagility to share documents".
- Thanks, praise, greetings, FYIs, and people only mentioned as unavailable ("@Anmol Goyal and @Sumayya Pathan are on another call").

RULES
1. Only ROSTER people. Match a mention to a ROSTER name when it is clearly the same person (first name alone, a Slack handle like ajinkya.jaiswal, or a name with a suffix like "(TDM)" or "sir"). If two ROSTER people could match, skip it.
2. person_email is copied exactly from ROSTER. conversation_id is copied exactly from the "###" line.
3. task: what they have to do or did, 15 words or fewer, in the conversation's own words, starting with a verb ("Work on BRDs for Production Posting and Plant Maintenance").
4. status: done when the conversation says it is complete (a check mark, "done", "deployed", "resolved"); in_progress when it says in progress or the person replied they are on it; blocked when it says blocked or waiting on someone; otherwise open.
5. due: YYYY-MM-DD when a date or ETA is stated for that item (resolve "5 Oct" with the conversation's date), else "".
6. kind: request, owner, status, self or dependency.
7. evidence: up to 20 words copied from the conversation that show the assignment.
8. One item per person per piece of work in a conversation; the same work repeated in replies is one item.
9. Return every conversation id you were given in checked_ids, even when it has no items.

OUTPUT
{"items": [{"conversation_id": "...", "person_email": "...", "person_name": "...", "task": "...", "status": "open|in_progress|done|blocked", "due": "", "kind": "...", "evidence": "..."}], "checked_ids": ["..."]}"""

AGENT = ("Slack Task Assignment agent", "Finds who was given work in Slack conversations from account channels.",
         "Return, as JSON, every case where a roster person is given work or shown owning or doing work, so code can record it as a task.", INSTR,
         "Find work assigned in Slack conversations", "Use this task when the message carries ROSTER and CONVERSATIONS.",
         ["Read every conversation in the message.", "Follow the RULES in your instructions and return only the OUTPUT JSON."])

def build():
    ua.ensure_session()
    reg = json.load(open(REG)) if os.path.exists(REG) else {}
    src = ua.call("GET", f"/api/entity/ai_agent/{A.SRC_AGENT}")["properties"]
    keep = {k: src[k] for k in ("responseGenerationSettings", "topicExecutionSettings", "preProcessingSettings", "indexingSettings", "contextManagement", "deployedOn") if k in src}
    name, role, goal, instr, tname, tdesc, tsteps = AGENT
    props = {**keep, "name": name, "agentType": "ai-agent", "role": role, "goal": goal, "instructions": instr, "disableDefaultTools": True, "defaultToolsNotNeeded": True}
    if "agent" not in reg:
        reg["agent"] = ua.call("POST", "/api/entity", {"entityType": "ai_agent", "tags": ["DB", "FDSE"], "properties": props})["id"]; json.dump(reg, open(REG, "w"), indent=1)
    else:
        cur = ua.call("GET", f"/api/entity/ai_agent/{reg['agent']}"); ua.call("POST", "/api/entity/update", {**cur, "properties": {**cur["properties"], **props}})
    tprops = {"name": tname, "description": tdesc, "instructions": tsteps, "aiAgentId": reg["agent"], "enabled": True, "isAppConnector": False, "runTimeConnectionEnabled": False, "governanceConfig": {}}
    if "task" not in reg:
        reg["task"] = ua.call("POST", "/api/entity", {"entityType": "e_topic_ai_agent", "tags": ["DB", "FDSE"], "properties": tprops})["id"]; json.dump(reg, open(REG, "w"), indent=1)
    else:
        cur = ua.call("GET", f"/api/entity/e_topic_ai_agent/{reg['task']}"); ua.call("POST", "/api/entity/update", {**cur, "properties": {**cur["properties"], **tprops}})
    ent = ua.call("GET", f"/api/entity/ai_agent/{reg['agent']}")
    ua.call("POST", "/api/entity/action/saveAndDeploy", {**ent, "deploymentNotes": f"{name}"})
    print("agent", reg["agent"], json.dumps(ua.call("GET", f"/api/entity/ai_agent/{reg['agent']}").get("deploymentState"))[:120])
    return reg

if __name__ == "__main__":
    print(build())
