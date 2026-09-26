# UnifyApps — AI Agents, Tasks and Tools via API

Reverse-engineered from the `orbit.uat.unifyapps.com` sandbox on 2026-09-19.
Companion to `unifyapps-automation-api.md`. **VERIFIED** = executed successfully.

Auth is identical to workflows — see section 2 of the automation doc.

---

## 1. The mental model

| UnifyApps concept | UI label | Entity type | What it is |
|---|---|---|---|
| Agent | Agents | `ai_agent` | The agent itself: system prompt, models, guardrails |
| Task | Tasks | `e_topic_ai_agent` | A journey/flow — *when* to act and *how* |
| Tool | Tools | `e_action_ai_agent` | A callable function, usually **a workflow** |
| Prerequisite Action | Tasks → Prerequisite Actions | `e_prerequisite_task_ai_agent` | Runs before the agent acts |
| Capability | Capabilities | (inline `properties.defaultTools`) | Built-ins: web search, todo, code, charts |
| Team | — | `e_ai_agent_team`, `e_ai_team_task` | Multi-agent orchestration |
| Knowledge | Knowledge | `knowledge_set`, `knowledge`, `knowledge_source` | RAG corpora |
| Deployment | Deployments | `ai_agent_deployment` | Channel bindings (web, Slack, …) |
| Prompt | — | `prompt` | Reusable prompt objects |

**The key insight:** a tool is just a call into a workflow. Same
`callables_call_automation` shape as a `CALL_WORKFLOW` node. So every workflow you build
is a potential agent tool, with no extra machinery.

---

## 2. Generic entity CRUD — **VERIFIED**

All agent objects are "entities" and share one CRUD surface.

| Operation | Call |
|---|---|
| **Create** | `POST /api/entity` with `{entityType, properties}` |
| **Read** | `GET /api/entity/{entityType}/{id}` |
| **List / search** | `POST /api/entity/{entityType}` (query body) |
| **Update** | `POST /api/entity/update` with `{id, entityType, properties, version}` |
| **Publish** | `POST /api/entity/action/saveAndDeploy` with the **full entity** + `deploymentNotes` |
| **Aggregate / filter** | `POST /api/aggregation?entityType={t}&group=ENTITY` |

Gotchas:

- `POST /api/entity/{entityType}` is **list**, not create. Creating there returns a page
  of existing entities and silently does nothing.
- Update is *not* `POST /api/entity` with an id — that returns a Mongo duplicate-key 500.
- `saveAndDeploy` validates the whole entity; a missing `properties.name` fails with
  *"Non Empty Validations ... required name"*. Read the entity, modify, send it all back.
- Entities use `group=ENTITY` in aggregation. `group=STANDARD` (used by workflows) errors
  with *"Invalid group: STANDARD and type: e_topic_ai_agent"*.

Entity response envelope:

```json
{ "id": "e_6aae34ad3c95b76375e8dce2", "entityType": "ai_agent", "version": 1,
  "createdTime": 0, "modifiedTime": 0, "ownerUserId": 12345, "deleted": false,
  "deploymentState": { "deployedAt": 0, "deployedBy": 12345, "entityVersion": 1, "version": 1 },
  "properties": { }, "grants": { }, "tags": [] }
```

Everything real lives in `properties`.

---

## 3. Agent — `ai_agent`

### Create (**VERIFIED**)

```http
POST /api/entity
{ "entityType": "ai_agent",
  "properties": { "name": "Support Agent",
                  "agentType": "CONVERSATIONAL",
                  "instructions": "You are a support agent. Be concise." } }
```

`properties.name` is effectively required — without it publish fails later.

### Key properties

| Property | Meaning |
|---|---|
| `name` | Agent name (required for publish) |
| `instructions` | **The system prompt** (string) |
| `agentType` | e.g. `CONVERSATIONAL` |
| `defaultTools` | Built-in capabilities, a flat map of booleans |
| `disableDefaultTools` | Turn the whole built-in set off |
| `visibility.type` | Who can see it |
| `responseGenerationSettings.answerGenerationModel` | Answer model |
| `responseGenerationSettings.{tone,style,format,outputSchema}` | Response shaping |
| `preProcessingSettings.{queryRephrasingModel,rankingModel,hybridSearch,useHyDE}` | RAG pre-processing |
| `indexingSettings.{embeddingModel,chunkingSettings,graphRAGSettings,piiMasking}` | Knowledge indexing |
| `longTermMemorySettings.enabled` | Memory |
| `contextManagement.{compressionEnabled,compactionSettings}` | Context window handling |
| `topicExecutionSettings.{topicSelectionModel,topicExecutionModel,topicAsTool}` | How Tasks are chosen/run |
| `multiAgentConfig`, `teamManagerSettings.agentsAsTools` | Multi-agent |
| `textToSQLSettings` | Text-to-SQL behaviour |
| `websearchSettings`, `voiceSettings`, `dictationSettings` | Channel features |
| `evalSettings.isEnabled`, `loggingSettings`, `promptCachingSettings` | Ops |
| `mcpEnabled` | Expose agent over MCP |

`defaultTools` keys observed: `deepResearch`, `executeCodeTool`, `executeCodeInSandbox`,
`generateChartTool`, `generateImageTool`, `createDocx`, `createPDF`, `createPPTX`,
`createExcel`, `createFile`, `analyseFile`, `documentVision`, `companyKnowledge`,
`ingestKnowledge`, `search_knowledge_graph`, `todo_tool`, `planTool`, `summaryTool`,
`requestClarification`, `clarifyFromUser`, `clarifyConnection`, `loadSkill`,
`saveInstantMemoryTool`, `informationNotFoundTool`, `generatePublicFileUrl`,
`allowKnowledgeControl`, `CompleteDocumentContext`.

### Publish (**VERIFIED**)

```http
POST /api/entity/action/saveAndDeploy
{ ...the entire entity object..., "deploymentNotes": "V1 via API" }
```

Response carries `deploymentState.version`, which increments per publish.

---

## 4. Task — `e_topic_ai_agent`

A Task is a journey: **`description` says when to use it, `instructions` says how.**

```http
POST /api/entity
{ "entityType": "e_topic_ai_agent",
  "properties": {
    "name": "Customer Lookup",
    "description": "Use this task when the user asks to look up a customer by id.",
    "instructions": [
      "Ask the user for the customer id if not provided.",
      "Call the LookupCustomer tool with that id.",
      "Summarise the returned rows and the http status in plain English."
    ],
    "aiAgentId": "e_6aae34ad3c95b76375e8dce2",
    "enabled": true,
    "isAppConnector": false,
    "runTimeConnectionEnabled": false,
    "governanceConfig": {}
  } }
```

- `instructions` is an **array of strings**, not a single string.
- `description` is what the router matches on — write it as a trigger condition.
- `aiAgentId` links it to the agent.
- `modelSelectionConfig` optionally overrides the model for this task.

Verified: created via API, appears immediately in the agent's **Tasks** tab.

---

## 5. Tool — `e_action_ai_agent`

A tool that calls one of your workflows:

```http
POST /api/entity
{ "entityType": "e_action_ai_agent",
  "properties": {
    "name": "LookupCustomer",
    "description": "Look up a customer by id. Returns oracle rows and an http payload.",
    "aiAgentId": "e_6aae34ad3c95b76375e8dce2",
    "topicId": "GLOBAL",
    "context": { "appName": "callables", "resourceName": "callables_call_automation" },
    "inputs": { "automationId": "6aae21e07c95610571778cb5",
                "version": "-1", "synchronous": true,
                "runtimeConnections": {}, "parameters": {} },
    "enabled": true
  } }
```

### Scoping — **VERIFIED**

| `topicId` | Effect |
|---|---|
| `"GLOBAL"` | Agent-level tool; appears in the **Tools** tab, available to every task |
| `"<topic entity id>"` | Scoped to that Task only; does **not** appear in the Tools tab |

### Critical defaults

`enabled` defaults to **`false`** when omitted — the tool exists but the agent will never
call it. Always set `enabled: true`.

Other server-applied defaults: `deferToolLoading`, `enableToolSearch`,
`excludeInputOutputFromTrace`, `isStandardAction`, `runTimeConnectionEnabled`.

### Parameters

`inputs.parameters` maps to the target workflow's `inputs.setup` JSON Schema. Left as
`{}`, the model fills arguments from the schema. `version: "-1"` = latest deployed.
`synchronous: true` waits for the result.

### Real-world reference

The platform's own prompt-to-automation copilot (`text_to_automation_ai_agent_v2`) is
built exactly this way — tools named `FetchActions`, `UpdateWorkflow`, `RebuildWorkflow`,
`FillInput`, each a `callables_call_automation` into an internal workflow, all with
`topicId: "GLOBAL"`. Worth reading as a design reference.

---

## 6. Recipe — agent with a workflow-backed tool (**VERIFIED**)

1. Build and **deploy** the workflow (automation doc §6). Give it a `CALLABLE` trigger
   with a clear `inputs.setup` schema — that schema becomes the tool's argument contract.
2. `POST /api/entity` → `ai_agent` with `name` + `instructions`.
3. `POST /api/entity` → `e_topic_ai_agent` with `aiAgentId`, `description`, `instructions[]`.
4. `POST /api/entity` → `e_action_ai_agent` with `aiAgentId`, `topicId`,
   `context.resourceName = callables_call_automation`,
   `inputs.automationId = <workflow id>`, **`enabled: true`**.
5. `POST /api/entity/action/saveAndDeploy` with the full agent entity.

Naming matters more than usual: the agent picks tools from `name` + `description`, so
write them as instructions to a model, not as internal identifiers.

---

## 7. UI routes (useful for eyeballing what the API built)

```
/p/0/ai-agents/custom                                   list
/p/0/ai-agents/{id}/configuration/instructions          system prompt
/p/0/ai-agents/{id}/configuration/topics                Tasks
/p/0/ai-agents/{id}/configuration/actions               Tools
/p/0/ai-agents/{id}/configuration/tasks                 Prerequisite Actions
/p/0/ai-agents/{id}/configuration/capabilities          built-in defaultTools
/p/0/ai-agents/{id}/configuration/knowledge             knowledge
/p/0/ai-agents/{id}/configuration/skills                skills
/p/0/ai-agents/{id}/configuration/ai-models             models
/p/0/ai-agents/{id}/deployments                         channels
/p/0/ai-agents/{id}/observability                       traces
```

Note the mismatch: the tab **labelled** "Tasks" is `/configuration/topics`, while
`/configuration/tasks` is **Prerequisite Actions**.

---

## 8. Scale in this tenant (context for what is normal)

31,703 workflows · 28,994 tools · 2,872 tasks · 7,775 connections · 1,210 node types ·
17,791 entity types.

---

## 9. Not yet covered

Honest list of what this study did **not** establish:

1. **Invoking an agent** — how to start a conversation and read a reply over the API
2. **Knowledge** — creating `knowledge_set` / ingesting sources
3. **Skills** entity shape
4. **Guardrails** — the sensitive-information / hallucination / content-filter configs
5. **Deployments** (`ai_agent_deployment`) — binding an agent to a channel
6. **Multi-agent teams** — `e_ai_agent_team`, `e_ai_team_task`
7. **Model selection** — valid values for `answerGenerationModel` (see `ai_agent_llm_model`)
8. **Prerequisite actions** — `e_prerequisite_task_ai_agent` shape

---

## 10. Scratch objects created (delete when done)

| Entity type | id | name |
|---|---|---|
| `ai_agent` | `e_6aae34ad3c95b76375e8dce2` | ZZ Api Test Agent (published v1) |
| `e_topic_ai_agent` | `e_6aae34db5f977a32333e7090` | Customer Lookup |
| `e_action_ai_agent` | `e_6aae34db6a7a1a6dffbce1b5` | LookupCustomer (task-scoped) |
| `e_action_ai_agent` | `e_6aae36065f977a32333e77bb` | LookupCustomerGlobal |
