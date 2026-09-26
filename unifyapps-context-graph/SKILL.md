---
name: unifyapps-context-graph
description: Build, populate and query a UnifyApps Enterprise Context Graph (ECG) - node/edge schema, records, record-level edges, OpenCypher retrieval, enricher agents, connector-driven ingestion, and wiring an AI agent that answers from the graph. Use whenever the user wants to create or inspect a context graph, load records or relationships into one, connect HubSpot/Slack/Drive/Gmail sources to one, write an enrichment agent, or build an agent that answers questions about customers and deals.
metadata:
  author: Maher
---

# UnifyApps Enterprise Context Graph

> **Created by Maher.** Contains no credentials. Each user signs in with their own UnifyApps
> account — read `references/connect-and-call.md` first (tenant, sign-in, finding connections,
> API conventions). Never ask for a password.

Create, populate and query a **context graph** over the platform REST API. Everything here
was verified live on `tool.prod-aps1` across three full graph builds (2026-09-19/20),
ending in a working customer-context graph with 15 node types, 211 records, ~300 edges and
an agent that answers real questions correctly.

## What is in this skill

| Path | Contents |
|---|---|
| `references/connect-and-call.md` | **Sign in with your own account, find connections, API conventions** |
| `references/ecg-api.md` | Graph / node / edge / record endpoints, id formats, MDM metadata, UI routes |
| `references/sources-and-sync.md` | **Verified source payloads**, MDM + storage connector patterns, HubSpot and Slack specifics, reading run output |
| `references/ingestion-and-agents.md` | The discovery → enrichment → map pipeline, and the retrieval-prompt pattern worth copying |
| `scripts/ecg_builder.py` | Spec-driven builder that encodes the correct build order - **start here** |

## The living API spec - master reference

`API-SPEC.md`, at the root of the `unifyapps-helper` repo these skills ship from (two levels
above `.claude/skills/`), is the **master record of every UnifyApps endpoint
discovered** - 126 paths, of which this skill's Context Graph surface is §12. Every entry
carries an evidence level (✅ verified · 👁 observed · 📦 bundle-only · ⚠️ partial ·
⛔ does not work), a tenant and a date.

It is **additive, not required**: this skill's own references are enough to build and query
a graph. If you received this skill without the repo, carry on without it.

**Read it when:**
- a graph build needs something from **outside** this skill - workflow creation, deploy and
  run (§4-6), agent/tool entities (§8-9), connection lookup (§7). This skill uses those
  constantly (edge-writing and Cypher automations, the retrieval agent) but only summarises them;
- an endpoint looks plausible but is untested - check **§15 Confirmed dead ends** first;
- you hit an error you don't recognise - **§17 Error catalogue**;
- a behaviour differs between tenants - **§18 Discrepancies**. Two involve this skill directly:
  **D1** (reading node outputs: `TEST_WORKFLOW_VARIABLE` works on UAT, so the debug-node pattern
  below may be unnecessary) and **D3** (run-status filter field);
- you need a connector action's full input/output contract - **§16 Node action contracts**.

**Where this skill and the spec disagree, the spec wins** - it is the master and is updated first.

**Write to it** whenever you verify or disprove anything about the API, in the same session:
use the entry template in its §1, give the entry a status mark plus tenant and date, put
contradictions in §18 instead of overwriting, add a §21 changelog line, bump the version -
then update this skill if its guidance changed. **Never paste passwords, cookies, tokens or
`connection.userInput` contents into it.**

## Read this first - the five rules that cost the most to learn

**1. Publish the graph BEFORE loading any records.**
Records written while a graph is `DRAFT` land in the entity store and are **never projected
into the Cypher layer**. `GET /api/entity/...` finds them; `MATCH (n)` does not. There is no
error. Create graph → create nodes → create edge types → **publish** → then load.

**2. Make every property `STRING`.**
Typed properties (`DATE`, `DOUBLE`, `INTEGER`, `BOOLEAN`) store correctly in the entity
store but the node then projects **zero vertices** into the graph. Proven by isolation: a
string-only Deal projected, an otherwise identical typed Deal did not. Use STRING and
convert in Cypher: `toFloat(d.` + "`_pr_amount`" + `) > 100000`,
`toInteger(d.` + "`_pr_days_in_stage`" + `) > 45`. Store dates as `YYYY-MM-DD` so string
comparison and ordering behave.

**3. Verify projection after the first insert of each node type.**
```cypher
MATCH (n) RETURN DISTINCT labels(n) AS labels
```
A node type missing from that list has records that will never be queryable. Catch it at
record 1, not record 200.

**4. Records never link themselves.**
A matching `customer_id` property creates no relationship. Edges are written with
`mdm_by_unifyapps_add_edge_to_graph` from inside an automation.

**5. Never judge a deal's state from its stage id.**
In real portals stage ids are recycled: `closedwon` can be an **open** 70% stage called
"Business Win". Always traverse `(Deal)-[AT_STAGE]->(Stage)` and read `label` and
`is_terminal`. See *The stage trap* below.

## Build order (verified end to end)

```
1. POST /api/context-graph                    {name, description}      -> graphId
   (a matching mdm_by_unifyapps UDM connection is auto-created)
2. POST /api/context-graph/{graphId}/publish  DRAFT -> LIVE   <-- BEFORE loading
3. POST /api/context-graph/nodes              one per node type, all STRING properties
4. POST /api/context-graph/edges              {graphId,label,fromNodeId,toNodeId}
5. POST /api/entity                           {entityType:<ue>, properties:{...}} per record
6. Verify: MATCH (n) RETURN DISTINCT labels(n)
7. Workflow: mdm_by_unifyapps_add_edge_to_graph   one node per record edge, then run
8. Workflow: mdm_by_unifyapps_execute_opencypher_query, deploy it
9. POST /api/entity  e_action_ai_agent        tool -> that workflow, enabled:true
10. POST /api/entity/action/saveAndDeploy     publish the agent
```

Steps 7 and 8 need the graph's UDM connection id. Find it with
`POST /api/lookup?ByQuery=CONNECTION` and `{"type":"ByQuery","lookupType":"CONNECTION","query":"<graph name>"}`.

Nodes can be created before or after publish; **records must come after**.

## Two ingestion mechanisms - pick per source

The platform supports both. Neither is a workaround; they fit different jobs.

| | Source pipeline (wizard) | Connector actions + automation |
|---|---|---|
| Configured via | Objects → Discover & Enrich → Map → Publish | Workflow definition API |
| Good for | Continuous broad sync, unstructured content | Scoped, controlled, per-record sync |
| Scoping | Per connector. **Slack: yes** (`channelList`). **HubSpot: no** - only "import all companies/deals/contacts" | Exact records you name |
| Blocker | The **Map** step cannot be written via API - POST/PUT/PATCH all return 405. Wizard only | None |

**Consequence:** if the user wants one account only, HubSpot *must* be automation-driven -
the native source has no record-level filter. Say that explicitly rather than appearing to
take a shortcut.

Also: the HubSpot source exposes only Company, Deal, Contact, Ticket. **Engagements
(emails, calls, meetings, notes, tasks) are not source objects at all** and always need
automations.

## Querying: OpenCypher conventions

Node label = the `unifiedEntityId`. Property names are prefixed `_pr_`.

```cypher
MATCH (c:`<customer_ue>`)
WHERE toLower(coalesce(c.`_pr_name`, '')) CONTAINS 'presidential'
MATCH (c)-[:HAS_DEAL]->(d:`<deal_ue>`)-[:AT_STAGE]->(s:`<stage_ue>`)
RETURN d.`_pr_deal_name` AS deal, s.`_pr_label` AS stage,
       s.`_pr_is_terminal` AS terminal,
       labels(d) AS labels, d.modelId AS modelId
LIMIT 50
```

Two rules to put in every agent prompt:
1. Every `RETURN` must include `labels(v) AS labels` and `v.modelId AS modelId`.
2. Never bind with an inline `{prop: value}` map - match the bare label, then filter with
   `WHERE toLower(coalesce(...)) CONTAINS`.

## The stage trap

Real portals recycle stage ids and mis-set the closed flag. Observed live:

| Pipeline | Stage id | Label | isClosed | Truth |
|---|---|---|---|---|
| `default` | `closedwon` | Business Win | false | **OPEN**, 70% |
| `default` | `closedlost` | Paper Win | false | **OPEN**, 90% |
| `default` | `appointmentscheduled` | Engage | **true** | OPEN, earliest stage |
| VEP | `5901834432` | Submitted for Closure | false | OPEN *(terminal in `default`)* |

Classification must be computed per pipeline at sync time:

```text
openMax  = max(displayOrder) where isClosed == false
TERMINAL = isClosed == true AND displayOrder > openMax
```

The `displayOrder > openMax` clause is what rescues early stages wrongly flagged closed.
Model `Stage` keyed on `pipeline_id::stage_id` - **the same label means different things in
different pipelines**. Also: labels can carry trailing spaces (`"Closed Lost "`), so trim.

## Enricher agents

An enricher is an `ai_agent` with `role: "Enricher"` whose **output schema is the contract**:

```json
"responseGenerationSettings": {
  "outputSchema": {
    "type": "object",
    "properties": {
      "results": { "type": "array", "items": { "type": "object",
        "properties": { "field_a": {"type":"string"}, "field_b": {"type":"string"} } } }
    } } }
```

The platform reads it at
`GET /api/context-graph/sources/enrichers/AGENT/{agentId}/{n}/schema` and flattens
`results[].items.properties` into the mappable field list.

Prompt discipline that matters (copied from the platform's own reference enrichers):
- **Multiple entity output** - one input yields one row per extracted entity.
- **No Cartesian product** - 2 commitments + 1 blocker is 3 rows, not 6.
- **Deterministic ids** - derive from the source record id, never invent.
- **ID reuse** - fetch existing records before assigning ids, or every run creates duplicates.

**Name enricher output fields to match the destination node's property ids.** The reference
SharePoint source maps a 92-field enriched schema with **one** fieldMapping, because
same-named fields ride along. Prefixing every field (`interaction_subject` vs `subject`)
manufactures mapping work that shouldn't exist.

**Don't use an LLM for pure capture.** A Slack message already has `ts`, `text`, `user`.
Enrich where meaning is added - commitments, blockers, use cases, sizing - and map the
structured parts directly.

## Platform gotchas

| Symptom | Cause / fix |
|---|---|
| Cypher returns `objects: []` but records exist | graph was DRAFT when records were written, or properties aren't STRING |
| A node type is missing from `labels(n)` | same - reload that type's records after publishing |
| `500 Please delete data before updating entity schema` | property **type** changes need zero records; metadata flags (e.g. `scdType2Enabled`) can change with data present |
| `500 version is required for node update` | version goes in the **query string**: `/nodes/update/{id}?version={n}` |
| Workflow node fails but run keeps going… it doesn't | `fallbackMode: CONTINUE` does **not** continue - one failed node fails the run |
| `storage_by_unifyapps_create_record` writes nothing | record fields go under **`record`**, not at input top level |
| Run status query returns `{}` | projections are **UPPERCASE** (`STATUS`, `FAILED_NODES`, `RUN_ID`); filter on `fields.id` |
| Log record empty after a big payload | the storage text field silently truncates to empty - page smaller or project fewer fields |
| `forbidden datasource: not found` | connector action called via `/api/workflow/execute/node`; use a real workflow |
| HubSpot search 400s | `CONTAINS` is invalid - use `CONTAINS_TOKEN` |
| `405` on schema-mappings / automap | Map step is wizard-only; don't burn attempts guessing payloads |
| Record titles show raw ids | `recordTitleFormat` must be `{{ mdm.field.<prop> }}` |
| `Validation failed ... sourceConnectionId` | don't hand-create the UDM connection - the graph made one |

## Reading run output

There is no supported "get node outputs" API that worked. The reliable pattern is a
**debug node**: add a scratch node type with `log_id` + `payload`, append a
`storage_by_unifyapps_create_record` step after the action you want to inspect, then read
it with `GET /api/entity/{ue}/{log_id}`. Keep payloads small - the field truncates silently.

## Wiring an agent to the graph

The built-in `search_knowledge_graph` default tool did **not** activate from
`graphModelId` + `defaultTools` alone, even copying a working agent's entire property set.
It is server-gated and on the reference agent it runs as an internal automation. **Build the
tool explicitly** instead:

1. CALLABLE workflow: `START(cypherQuery) -> mdm_by_unifyapps_execute_opencypher_query -> STOP`
2. Deploy it
3. `e_action_ai_agent` with `callables_call_automation`, `inputs.automationId`,
   `topicId: "GLOBAL"`, **`enabled: true`** (defaults to false)
4. Put the label ids, `_pr_` names, edge list and the Cypher rules in the agent instructions
5. `saveAndDeploy`

## Verified example - tool.prod-aps1

Built by the skill author; ids exist only on that tenant. **Read-only for everyone else** - build
your own graph rather than writing to it.

**SC Customer Context (Live)** `6aaf77ef12a16316109f378f` - 15 node types, 32 edge types,
211 records. Agent `e_6aaf734612a16316109f0ba3` answers correctly, including the stage trap
(*"it is open, even though 'Business Win' sounds closed"*), a people-by-message ranking, a
23-document inventory grouped by type, and an honest "none are recorded" for empty node types.

Read-only reference built by the product team: *Enterprise Context Graph*
`6a8583af13a9131516e287ac` plus its retrieval and enrichment agents. Study it; never write to it.

## Still unproven

- Writing schema mappings / publishing a source without the wizard.
- What server-side condition enables the built-in `search_knowledge_graph` tool.
- `associatedEdgeMappings` payload shape - every live source had it empty.
- Whether typed properties ever project (they did not in this build, at any point).
