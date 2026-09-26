# Ingestion, enrichment and retrieval agents

How real systems (SharePoint, Outlook, Gmail, and by the same mechanism Slack, HubSpot,
calendars) become records and relationships in a context graph - and how an agent reads
them back.

Observed on the product team's reference graph *Enterprise Context Graph*
`6a8583af13a9131516e287ac` on `tool.prod-aps1`. **That graph is read-only for us**; the
source wizard was opened to study it and closed with the X, never saved.

---

## 1. The pipeline

```
Source            = connector connection + the graph as destination
  |                 (appName, connectionId, destinationConnectionId -> mdm_by_unifyapps)
  v
Object            = what the connector exposes: File, Mail, Message, Event, ...
  |
  v
Discover & Enrich
  |  Discovery Agent    classifies a raw record          -> e.g. {documentType: "SOW"}
  |  Entities           one per discovered kind (SOW, MeetingTranscript, ...)
  |     Classify When   condition on the raw record, e.g. document name CONTAINS "SOW"
  |  Enrichment Agent   extracts a rich flat schema for that entity
  v
Map               schemaMappings: discovered entity -> graph node
                    fieldMappings[{sourceField, destinationField}]
                    associatedEdgeMappings  -> record-level edges at ingest time
  v
Settings          knowledge retention, permission checks, sync schedule
```

The wizard steps in the UI are exactly these: **Source -> Connection -> Objects ->
Discover & Enrich -> Map -> Settings**.

## 2. Source object

```json
GET /api/context-graph/sources/{sourceId}
{
  "id": "6a959a6481f2004762359f33",
  "graphId": "6a8583af13a9131516e287ac",
  "appName": "gmail",
  "connectionId": "69da20efa1e1eb4d2d0a2620",
  "destinationConnectionId": "6a959a640de89f4fbd2e91ce",
  "objectDiscoveryConfigRefs": [
    {"objectId": "Mail", "displayName": "Mail", "objectDiscoveryConfigId": "6a959a6da397f67f704fc9a1"},
    {"objectId": "File", "displayName": "File", "objectDiscoveryConfigId": "6a98b9987bf9455c5329f620"}
  ],
  "lastSyncTimeEpochMillis": 0,
  "version": 3
}
```

`destinationConnectionId` is an `mdm_by_unifyapps` connection whose
`userInput.unifiedEntityModelId` is the graph id - the graph acting as a write target.

`objectDiscoveryConfigId` has **no direct GET**; read the per-object config through
`fetch-selected` instead.

## 3. Per-object config

```
GET /api/context-graph/sources/{sourceId}/objects/fetch-selected?limit=200&offset=0
```

Each object returns:

| Field | Meaning |
|---|---|
| `connectionObjectId`, `name` | the discovered entity, e.g. `SOW`, `MeetingTranscript` |
| `objectSchema` | raw connector fields (`fileObj`, `fileDetails`, `author`, `modifiedBy`, `sharedWithIds`, `referenceUrl`, `activity`) + `fieldIdVsPaths` |
| `enrichedObjectSchemas[]` | `{enricherId, enricherName, method:"AGENT", objectSchema:{fields:[...]}}` |
| `schemaMappings[]` | see below |
| `status` | `ACTIVE` |

The SOW example's enrichment schema had **92 fields** covering several entity families at
once - `agreement_*` (34), `approval_*`, `budget_*`, `person_*` and more. An enrichment
agent is expected to emit a wide, flat superset; the mapping step decides what lands where.

### schemaMappings

```json
{
  "sourceObjectId": "SOW",
  "destinationNodeId": "6a85986b13a9131516ed20c5",
  "destinationObjectId": "6a85986b13a9131516ed20c2",
  "fieldMappings": [
    {"sourceField": {"id":"agreement_id","dataTypeInfo":{"type":"STRING"}, "...": "..."},
     "destinationField": {"id":"account_id","primary":true, "...": "..."}}
  ],
  "associatedEdgeMappings": []
}
```

`destinationNodeId` is the graph node, `destinationObjectId` its unifiedEntityId.
`associatedEdgeMappings` is where record-level edges would be declared at ingest time -
**every live source we inspected had it empty**, so its payload shape is unverified. When
it is empty, edges have to be written by an automation instead (see SKILL.md).

Helper endpoints used by the Map step:

```
POST /api/context-graph/sources/objects/describe
{"connectionId":"<graph UDM connection>","objectId":"<unifiedEntityId>","sourceConfigId":"<sourceId>"}
-> {"fields":[{id, name, dataTypeInfo, primary, nullable, unique}, ...]}

POST /api/context-graph/sources/{sourceId}/schema-mapping/automap
GET  /api/context-graph/sources/{sourceId}/transformations/group-by-source-field
```

## 4. Discovery agent

An ordinary `ai_agent` whose output schema is read by:

```
GET /api/context-graph/sources/discoverers/AGENT/{agentId}/0/schema
-> {"outputSchema":{"type":"SCHEMA","schema":{"properties":{"documentType":{"type":"string"}}}}}
```

Reference: *Discovery Agent* `e_6a95aadf7bf9455c531938eb`, output `{documentType}`.
The wizard notes *"Full record passed to the agent - no input mapping needed."*
Discovered entities then carry a **Classify When** condition (e.g. document name
`CONTAINS` "SOW") that routes a record to the right entity and enrichment agent.

## 5. Enrichment agents

Reference agents (read-only):

| Agent | Id | Instructions |
|---|---|---|
| ECG Document Enrichment Agent | `e_6a85ddcf13a9131516f3580f` | 39,056 chars |
| ECG Mail Enrichment Agent | `e_6a86e8742bf7a907e5ff0d7d` | 45,709 chars |
| ECG Enrichment Agent (used by the SharePoint source) | `e_6a8963e81530455b53a133a7` | - |

They set `role: "Enricher"` and `goal: "Convert Unstructured data to structured data"`,
and their prompts are long and highly prescriptive. The load-bearing sections:

- **MULTIPLE ENTITY OUTPUT RULE** - one document yields many records across many entity
  types; the output is always a flat array, each object one extracted entity context.
- **ENTITY CARDINALITY** - 1 Account + 2 Use Cases, 1 Account + 2 Deals, etc., with an
  explicit prohibition on emitting the **Cartesian product** of unrelated entities. This
  is the failure mode that quietly triples a graph's record count.
- **ENTITY RELATIONSHIP AWARENESS** - for every extracted entity, answer "which Account /
  Use Case / Deal / Product does this belong to, and which Document describes it?" This is
  what lets edges be derived rather than guessed.
- **REPEATED FIELDS** - how to repeat parent attributes across child rows.
- **ID REUSE** - *"You MUST use the fetch existing records tool before assigning IDs"*,
  for every entity type. This is the entity-resolution step: without it, every ingest run
  mints new ids and the graph fills with duplicates instead of enriching existing records.

Copy this structure when writing your own enricher. The expensive lessons encoded there
are: emit many entities, do not cross-product them, state the relationships explicitly,
and resolve ids against what already exists.

## 6. Retrieval agent

Reference: *Enterprise Context Graph Data Retrieval Agent* `e_6a87218e2bf7a907e5058ef1`
(13,493-char prompt, `graphModelId` set, default tools `search_knowledge_graph`,
`ingestKnowledge`, `analyseFile`, `generateChartTool`, `clarifyFromUser`,
`generatePublicFileUrl`). It has **no custom tools and no Tasks** -
`e_action_ai_agent` and `e_topic_ai_agent` both return zero rows for it.

Its trace shows two retrieval paths per question:

```
Agentic Workflow
  Search knowledge base      Retriever -> Fetch Embeddings -> Semantic Search -> Reranker
  Search Knowledge Graph     385ms   "An automation was executed as a tool"  input {cypherQuery}
```

So the built-in graph tool is itself an automation the platform wires up. We could not
reproduce that binding from the entity alone (see SKILL.md, *Wiring an agent to the
graph*); use an explicit `e_action_ai_agent` tool instead.

### The prompt pattern worth stealing

The reference prompt is a corrective for one specific failure: **answering from whichever
source replies first**. Its structure:

1. **Core principle** - no single source is complete; graph and knowledge base capture
   different, non-overlapping slices. A summary field is "a compression of reality written
   by someone deciding what mattered at the time", never an exhaustive record.
2. **Step 1 - search the graph exhaustively.** Resolve identity first; then query *every*
   relevant relationship type, not just the first one that returns rows. A summary field
   and structured nodes are both queried; neither substitutes for the other.
3. **Cypher construction rules** - mandatory `labels(v) AS labels` and `v.modelId AS
   modelId`; never bind with an inline `{prop: value}` map; always
   `WHERE toLower(coalesce(v.` + "`_pr_x`" + `, '')) CONTAINS '...'`.
4. **Step 2 - search the knowledge base independently**, with multiple phrasings:
   the literal term, synonyms, and commitment patterns ("X will...", "X to...", "plans
   to") - which catch the facts nobody ever wrote as a labelled list.
5. **Step 3 - merge, deduplicate conservatively, never truncate.** If the graph returns 10
   items and the knowledge base adds 10 distinct ones, the answer has 20. "A shorter,
   tidier answer that omits real items is a worse answer."
6. **Silent self-check** before answering, and an explicit **anti-patterns** list.
7. **Formatting** - lead with the direct answer, then full detail; never narrate which
   tool produced what; ground every fact in tool results.

For a solution-consulting "customer context" agent this is the right shape: structured
graph facts for who/what/when/owner, unstructured retrieval for what was actually said,
merged into one answer.

## 7. Connector inventory for a customer-context graph

Sources live on the reference graph today:

| appName | Objects |
|---|---|
| `microsoft_sharepoint` | File (SOW, MeetingTranscript) |
| `microsoft_outlook` | Mail |
| `gmail` | Mail, File |

Discover what any connector exposes before designing a node:

```
GET  /api/context-graph/sources/applications/{appName}/objects
POST /api/context-graph/sources/applications/{appName}/objects/{objectId}/details?connectionId={id}
```

For Slack, HubSpot or calendars, use the same two calls with that connector's `appName` to
see its object list and schema before deciding what becomes a node and what becomes a
property.
