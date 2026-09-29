# UnifyApps Platform API — Living Specification

> **Living document.** This is the master record of every UnifyApps REST endpoint we have
> discovered, how we call it, and what comes back. It is reverse-engineered — UnifyApps does
> not publish these APIs — so every entry carries its evidence level. Update it whenever you
> learn something, including when something turns out **not** to work.

| | |
|---|---|
| **Spec version** | 0.4.5 |
| **Last updated** | 2026-09-29 |
| **Tenants covered** | `UAT` = `https://orbit.uat.unifyapps.com` · `APS1` = `https://tool.prod-aps1.unifyapps.com` |
| **Endpoints catalogued** | ~175 unique paths, including confirmed-dead ones (§15) |
| **Companion skills** | `unifyapps-builder` (workflows + agents), `unifyapps-context-graph` (ECG), `unifyapps-apps` (applications, objects, connections) |
| **Repository** | `github.com/mmaheranwar/unifyapps-helper` — **private** |

---

## Contents

1. [How to maintain this document](#1-how-to-maintain-this-document)
2. [Conventions](#2-conventions) — base URLs, auth, headers, envelopes, errors, ids
3. [Authentication & session](#3-authentication--session)
4. [Workflow definitions](#4-workflow-definitions)
5. [Workflow builder — node catalog & schemas](#5-workflow-builder--node-catalog--schemas)
6. [Workflow execution & runs](#6-workflow-execution--runs)
7. [Connections](#7-connections)
8. [Entities (generic CRUD)](#8-entities-generic-crud)
9. [AI agents, tasks, tools](#9-ai-agents-tasks-tools)
10. [Search: aggregation & lookup](#10-search-aggregation--lookup)
11. [Observability & traces](#11-observability--traces)
12. [Enterprise Context Graph](#12-enterprise-context-graph)
13. [Files](#13-files)
14. [Other observed platform endpoints](#14-other-observed-platform-endpoints)
15. [Confirmed dead ends](#15-confirmed-dead-ends)
16. [Node action contracts](#16-node-action-contracts) — workflow step inputs/outputs
17. [Error catalogue](#17-error-catalogue)
18. [Discrepancies to resolve](#18-discrepancies-to-resolve)
19. [Open questions / backlog](#19-open-questions--backlog)
20. [UI routes](#20-ui-routes)
21. [Changelog](#21-changelog)
22. [Applications — config-based](#22-applications--config-based) — `e_interface`, pages, blocks, data sources, publish
23. [Applications — code-based & the agent API](#23-applications--code-based--the-agent-api) — `/agent-api`, SDK, Git
24. [Objects Manager](#24-objects-manager) — `EntityType` schema + records

---

## 1. How to maintain this document

### Status legend — every entry must carry one

| Mark | Meaning |
|---|---|
| ✅ | **Verified** — we called it directly and confirmed the result |
| 👁 | **Observed** — seen succeeding in live UI traffic; we did not call it ourselves |
| 📦 | **Bundle-only** — path found in the front-end JavaScript; never exercised |
| ⚠️ | **Partial** — works, but with a caveat that matters (stated inline) |
| ⛔ | **Does not work** — tested; 404 / 405 / silent no-op. Kept so nobody retests it |

Each entry also names the **tenant** and **date** it was established. A ✅ on `UAT` is not
a ✅ on `APS1` — platform versions differ.

### Entry template

```markdown
### `METHOD /path/{param}` — Short name
✅ UAT · 2026-09-19

What it does, in one or two sentences.

**Request** — query params, body fields (table), then a minimal real example.
**Response** — status, shape, the fields that matter.
**Errors** — status + message + cause.
**Notes** — gotchas, ordering constraints, related endpoints.
```

### Rules

1. **Record what you observed, not what you expect.** If you only saw it in the bundle,
   it is 📦, however obvious it looks.
2. **Negative results are first-class.** A 405 you hit is worth an entry in §15.
3. **Contradictions go in §18**, not silently overwritten. Two tenants disagreeing is data.
4. **Never paste secrets.** No passwords, cookies, tokens, or `connection.userInput`
   contents. Redact to `<redacted>`.
5. **Bump the changelog** (§21) and the spec version with every substantive change.
6. **Skills keep curated copies.** This file is the master; when an entry changes in a way
   that affects a skill's instructions, update the skill too.

---

## 2. Conventions

### Base URL and paths

All endpoints are relative to the tenant origin. Two prefixes exist:

- `/api/...` — everything except login
- `/auth/...` — the login executor only. **`/api/login`-style paths do not exist** (§15).

### Authentication

Session cookie, **httpOnly**, set by the login call (§3). Every `/api/*` call requires it.
Clients must use a cookie jar; the value cannot be read from page JavaScript.

When the session expires:
- `GET /api/user-context` returns **401**, and/or
- the call is **redirected to the HTML login page** — check `content-type` before parsing
  JSON, or you will parse HTML.

Alternative for non-interactive work: call the API **same-origin from an already
logged-in browser tab** (`fetch('/api/...', {credentials:'include'})`); the cookie rides
along and no credential enters the conversation. ✅ UAT

### Headers

| Header | Value | Required |
|---|---|---|
| `Content-Type` | `application/json` | on bodies |
| `Accept` | `application/json` | recommended |
| `x-ua-timestamp`, `x-ua-timezone`, `x-ua-trace-id` | set by the web UI | no — calls succeed without them ✅ |

### Methods

The platform is **POST-heavy**. Updates and deletes are usually `POST .../update/...` or
`POST .../delete/...`, not `PUT`/`PATCH`/`DELETE`. Assume POST unless an entry says otherwise.

### Standard response envelopes

**Aggregation** (`/api/aggregation`):
```json
{ "objects": [ { "columns": { "id": "...", "name": "..." } } ],
  "totalHits": 123, "hasMore": false, "cursor": { "next": "<base64>" },
  "type": "AGGREGATION_RESPONSE" }
```
Read `o.columns`, not `o`. Column names are often abbreviated (see *Field abbreviations*).

**Entity** (`/api/entity/...`):
```json
{ "id": "e_6aae34ad3c95b76375e8dce2", "entityType": "ai_agent", "version": 1,
  "createdTime": 1789801645357, "modifiedTime": 1789801645357,
  "ownerUserId": 82118, "lastModifiedBy": 82118, "deleted": false, "standard": false,
  "deploymentState": { "deployedAt": 0, "deployedBy": 0, "entityVersion": 1, "version": 1 },
  "properties": { }, "grants": { "configs": [] }, "tags": [] }
```
Everything meaningful lives in `properties`.

**Entity list** (`POST /api/entity/{type}`):
```json
{ "objects": [ ...entities ], "hasMore": true, "cursor": { "next": "..." }, "type": "HITS" }
```

**Lookup** (`/api/lookup`):
```json
{ "response": { "objects": { "<key>": {...} }, "inaccessibleObjects": [], "type": "MAPPED_HITS" } }
{ "response": { "objects": [ ... ], "hasMore": false, "cursor": {...}, "type": "HITS" } }
```
`ByKeys` returns `MAPPED_HITS` (keyed map); `ByQuery` returns `HITS` (array).

### Error envelope

```json
// 404 / 405 — terse
{ "errorCode": -1, "errorId": "5b583ca8-6ca3-4ee1-84ed-cc273aad2851" }

// 500 — descriptive
{ "rootCauseMessage": "...", "message": "...", "errorCode": -1,
  "errorId": "<uuid>", "serviceName": "WorkflowDefinitionService" }

// 500 — asset not found
{ "rootCauseMessage": "CONNECTION with id oracledb not found",
  "assetClass": "CONNECTION", "assetId": "oracledb", "errorCode": 5002, ... }
```

Known `errorCode` values: `-1` generic · `5002` asset not found · `5004` invalid
group/type for aggregation. Full list in §17.

> ⚠️ **A 200 does not mean success.** Several endpoints return 200 while doing nothing
> (`objects/bulkUpdate` → `{"data":0}`), and `saveAndReturnViolations` returns 200 *and
> persists* a graph that has violations. Always check the body.

### Id formats

| Thing | Format | Example |
|---|---|---|
| Workflow | 24 hex | `6aae3aaa0900af6ee3a552b8` |
| Deployed workflow snapshot | `s_{workflowId}/{version}/{hash}` | `s_6aae21e0.../3/Khf8HC...=` |
| Entity (agent, task, tool, ...) | `e_` + 24 hex | `e_6aae3af83c95b76375e9046c` |
| Workflow node | author-chosen; UI uses `n_` + 5 chars | `n_sql`, `n_7M2BR` |
| Workflow edge | `{type}@{fromNodeId}@{toNodeId}` | `next@n_in@n_sql` |
| Run / execution | 24 hex | `6aae266715ef207b242e9026` |
| Node-output key | `{rootExecutionId}.{executionInstanceId}.{nodeId}` | `6aae26...026.6aae26...026.n_out` |
| User | integer | `82118` |
| ECG vertex | `{spaceId}::{unifiedEntityId}::{recordId}` | `90::6aae7f3c...::CON-001` |
| ECG record edge | `{fromVertex}::{toVertex}` | |

### Field abbreviations (aggregation)

| Abbrev | Field | Abbrev | Field |
|---|---|---|---|
| `cTm` | created time | `mTm` | modified time |
| `oUId` | owner user id | `lMBy` | last modified by |
| `d` | deleted | `pId` | project id |
| `v` | version | `lcName` | lower-cased name |
| `lPUBy` / `lPUOn` | last platform update by / on | | |

### Templating (inside workflow node inputs)

`{{ n_<nodeId>.outputs.<path> }}` — spaces inside the braces. A value starting with `=` is a
formula: `"=SUM({{ n_v.outputs.i }},1)"`, `"=LEN({{ n_x.outputs.items }})"`.
**An unresolved template silently drops the key** — no error, no violation.

---

## 3. Authentication & session

### `POST /auth/workflow/execute/node?name=emailAndPassLoginRequest` — Log in
✅ UAT · 2026-09-19

Credential login for a **local (non-SSO)** account. Sets the httpOnly session cookie.
Runs through the same node-executor as `/api/workflow/execute/node`, but under `/auth/`.

**Request**

| Field | Type | Req | Notes |
|---|---|---|---|
| `id` | string | ✅ | literally `"emailAndPassLoginRequest"` |
| `context.appName` | string | ✅ | `"auth_by_unifyapps"` |
| `context.resourceName` | string | ✅ | `"auth_by_unifyapps_login"` |
| `inputs.formData.username` | string | ✅ | |
| `inputs.formData.password` | string | ✅ | never log it |
| `inputs.formData.rememberMe` | boolean | | `true` |
| `inputs.identityProviderId` | string | ✅ | tenant's **local** IdP. UAT: `65d2f4cf672d16da08efc3d0` |
| `inputs.returnTo` | string | | `"/"` |
| `inputs.failureReturnTo` | string | | `"{BASE}/login"` |
| `options.cacheConfig` | object | | `{}` |

```json
{ "id": "emailAndPassLoginRequest",
  "context": { "appName": "auth_by_unifyapps", "resourceName": "auth_by_unifyapps_login" },
  "inputs": { "returnTo": "/", "failureReturnTo": "https://orbit.uat.unifyapps.com/login",
              "formData": { "username": "maheragent", "password": "<redacted>", "rememberMe": true },
              "identityProviderId": "65d2f4cf672d16da08efc3d0" },
  "options": { "cacheConfig": {} } }
```

**Response** — 200 + `Set-Cookie` session cookie.

**Errors**

| Status | Body | Cause |
|---|---|---|
| 401 | `{"message":"Invalid username or password"}` | bad credentials, **or** wrong `identityProviderId`, **or** `firstLogin` still set, **or** MFA enforced |

**Notes**
- SSO accounts cannot use this. Google SAML rejects non-provisioned accounts with
  `app_not_configured_for_user`. Use a local account with a password set.
- `identityProviderId` is tenant-specific — read it from the login request on a new tenant.
- Finding it without DevTools â uat-us-east-1 · 2026-09-29: the tenant's `/login` HTML embeds its identity providers;
  the local one has `"type":"PASSWORD"`. `GET /auth/identity-providers` (no auth) lists all providers including
  per-app ones, without a type — not enough to choose from.
- A `/mfa-verification` route exists in the UI; an MFA-enforced account needs a step not
  yet documented.
- Verified from outside a browser (Python `urllib`): no CORS or referer requirement.

### `GET /api/user-context?includeRoles=true` — Current user
✅ UAT · 2026-09-19

Session check and current-user details. Returns **401** when the session is invalid — the
cheapest liveness probe.

**Response** — 200, user object. `customer.id` is the tenant **`spaceId`** used in ECG
vertex ids (APS1 = `90`). Top-level keys ✅ UAT 2026-09-26: `assumeContextAllowed, customer, environment,
isImpersonatedSession, modules, notificationMqttTopics, user`; `user` carries `id` (the value that appears as
`oUId` in aggregation rows), `name`, `email`, `username`, `firstLogin`, `ssoLogin`, `roles`, `userGroups`.
(`user.ownerUserId` is `-1` — it is not the user's own id.)

⚠️ **Forced password reset** ✅ UAT 2026-09-26. When an account is flagged for a password reset, the login call
returns **200** (not 401) with `response.resetPassword: true` and `response.redirectUrl: "/update-password"`, and
sets the session cookie — but every `/api/*` call then returns **204 with an empty body** (`user-context`,
`getLoggedInUser`, aggregation alike). Check `resetPassword` in the login response; the user must finish the reset
in a browser. After the reset, the old password gets **401**.

### OAuth surface (UI routes, not REST)
📦 UAT · 2026-09-19

`/ui/auth/oauth/authorize`, `/oauth-consent`, `/complete/oauth/`, `/runtime-auth/new/`
exist in the login bundle — the platform can act as an OAuth authorization server. **No token
endpoint has been found**; see §19.

---

## 4. Workflow definitions

A workflow ("automation") is a `WorkflowDefinition`: `nodes[]` + `edges[]` + settings.
Node/edge model is in §16.

### `POST /api/workflow-definition` — Create
✅ UAT · 2026-09-19

**Request**

| Field | Type | Req | Notes |
|---|---|---|---|
| `name` | string | ✅ | not unique — track ids |
| `description` | string | | |
| `nodes` | array | ✅ | **must be non-null**, even for a stub (see Errors) |
| `edges` | array | | `[]` allowed |
| `tags` | string[] | | top-level; the supported ownership marker in shared tenants |
| `settings` | object | | defaults applied if omitted |

Minimal stub (then fill it via `saveAndReturnViolations`):
```json
{ "name": "My Automation", "description": "created via API",
  "nodes": [ { "id": "n_seed", "type": "START", "title": "seed",
               "trigger": { "type": "EVENT" }, "index": 0, "groupId": "n_seed-1",
               "fallbackMode": "STOP", "skip": false } ],
  "edges": [] }
```

**Response** — 200, the full `WorkflowDefinition`:
```json
{ "id": "6aae21e07c95610571778cb5", "name": "My Automation", "lcName": "my automation",
  "description": "...", "version": 0, "standard": false, "deleted": false,
  "appsUsed": [], "ownerUserId": 82118, "createdTime": 1789796832014, "modifiedTime": 1789796832014,
  "settings": { "enableNodeLevelLogging": true, "enableRunLogging": true,
                "enableVariableLogging": true, "route": { "default": false, "tierName": "global" } },
  "nodes": [ ... ], "edges": [ ... ] }
```
`lcName`, `appsUsed`, timestamps and ownership are server-assigned.

**Errors**

| Status | Message | Cause |
|---|---|---|
| 500 | `Cannot invoke "java.util.List.iterator()" because the return value of "...WorkflowDefinition.getNodes()" is null` | `nodes` omitted |

### `GET /api/workflow-definition/{id}` — Read
✅ UAT · 2026-09-19

Returns the full definition (same shape as create).

⚠️ **Does not return `tags`.** Read tags back only via aggregation projection
`[{"name":"tags"}]` (§10).

### `POST /api/workflow-definition/saveAndReturnViolations` — Save / update
✅ UAT · 2026-09-19

The real "save". Send the **complete** definition.

**Request** — full `WorkflowDefinition` including `id` and the **current** `version`,
`nodes`, `edges`, `settings`, `schemaReferences: []`, `standard: false`.

**Response** — 200:
```json
{ "workflowDefinition": { ...saved, "version": 1 },
  "violations": [ { "id": "n_brk", "type": "NODE",
                    "innerViolations": [ { "id": "Outgoing", "type": "next",
                      "message": "This automation has a trigger which expects response. Please add a step to send a response{{stepLabel}}." } ] } ] }
```
`violations` is `null` (or absent) when valid. `version` increments per save.
`appsUsed` is recomputed server-side from node `context.appName`.

**Notes**
- ⚠️ **HTTP 200 and persisted even with violations.** Always check `violations`.
- The UI calls this for Save; the UI never uses the bare `update/` endpoint.

### `POST /api/workflow-definition/{id}/deploy?version={n}` — Deploy
✅ UAT · 2026-09-19

**Request**

| Where | Field | Notes |
|---|---|---|
| query | `version` | the draft version to deploy (from the last save) |
| body | `deploymentNotes` | free text |
| body | `_type` | literally `"WORKFLOW_DEPLOY_OPTIONS"` |

```json
{ "deploymentNotes": "API-built callable workflow", "_type": "WORKFLOW_DEPLOY_OPTIONS" }
```

**Response** — 200:
```json
{ "workflowDefinition": { "id": "6aae2626ae96dd56dff79733",
    "deployedWorkflowVersion": 1, "deployedWorkflowNotes": "API-built callable workflow", ... } }
```
⚠️ The returned `id` is a **deployed snapshot id**, distinct from the draft id. The draft
and deployed copies version independently.

**Notes**
- Deploying a `SCHEDULED` workflow activates a live recurring job. `CALLABLE` workflows only
  run when invoked.
- ⛔ `/api/entity/action/saveAndDeploy` is **not** the workflow deploy — that is for entities (§8).

### `POST /api/workflow-definition/reachableFromNodeIds` — Graph reachability
👁 UAT · 2026-09-19

Builder helper, called while editing.

```json
{ "nodeId": "n_ahrd9",
  "workflowDefinition": { "name": "", "version": 0, "nodes": [ ... ], "edges": [ ... ] } }
```

### Other workflow-definition endpoints

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/api/workflow-definition/validate` | 👁 UAT | called by the UI before a test run; body not captured |
| POST | `/api/workflow-definition/executedWorkflowDefinition` | 👁 UAT | body `{"deployedWorkflowId":"s_{id}/{ver}/{hash}","test":true}` → the definition a run used |
| POST | `/api/workflow-definition/update/` | 📦 | partial update; unused by the UI |
| POST | `/api/workflow-definition/clone/` | 📦 | |
| POST | `/api/workflow-definition/delete/` | 📦 | referenced in our notes but **never exercised** |
| GET | `/api/workflow-definition/deployed-workflow/` | 📦 | |
| GET | `/api/workflow-definition/node-dependency/` | 📦 | |
| GET | `/api/workflow-definition/global-settings` | 📦 | |
| GET | `/api/workflow-definition` | ⛔ 405 | there is **no list GET** — use aggregation (§10) |

---

## 5. Workflow builder — node catalog & schemas

How to discover which actions exist, their versions, and their input/output schemas.
**Resolve `resourceVersion` from here at runtime** — it drifts (e.g. `oracledb_execute_sql`
16522 → 16523, `if_else_condition` 11 → 204).

### `GET /api/workflow-builder/nodes` — Node catalog
✅ UAT · 2026-09-19

**Query params**

| Param | Notes |
|---|---|
| `fields` | comma list, e.g. `name,displayName,iconUrl,tags,type,needsAuthentication,custom,hidden` |
| `resourceType` | e.g. `ACTION` (👁) |
| `name` | ⛔ ignored — returns the full list |

**Response** — 200:
```json
{ "objects": [ { "id": "6a1b657d7dc7176bfe64f52e", "name": "formbuilder_123",
                 "displayName": "123FormBuilder", "type": "ACTION", "tags": ["Applications"],
                 "needsAuthentication": true, "custom": false, "hidden": false,
                 "standard": false, "iconUrl": "https://...", "lcName": "...", "version": 0,
                 "hasOverriddenDetails": false, "deleted": false } ],
  "totalHits": 1210, "hasMore": false, "type": "HITS" }
```
1,210 nodes on UAT. `type` values: `ACTION`, `IF_ELSE`, `LOOP`, `DELAY`, `BRANCH_CONDITION`.
Custom connectors have `custom: true` and a hex id as `name`.

### `GET /api/workflow-builder/node/{nodeName}` — Node detail
✅ UAT · 2026-09-19

Node metadata plus a large `grants` block.

### `GET /api/workflow-builder/node/{nodeName}/resources` — A node's actions
✅ UAT · 2026-09-19

**Response** — 200:
```json
{ "objects": [ { "name": "oracledb_execute_sql", "displayName": "Execute a SQL statement",
                 "version": 16523, "nodeName": "oracledb", "resourceType": "ACTION",
                 "async": false, "hidden": false, "custom": false, "standard": false,
                 "passNodeSchema": false, "nodeTestDisabled": false, "description": "..." } ],
  "hasMore": false }
```
`version` here is the value to put in a node's `context.resourceVersion`.

### `GET /api/workflow-builder/node/{nodeName}/resource/{resourceName}` — Action schema
✅ UAT · 2026-09-19

The input and output contract for one action. ~15 KB typical.

**Response** — 200:
```json
{ "name": "oracledb_execute_sql", "version": 16523, "resourceType": "ACTION",
  "input":  { "type": "SCHEMA_AND_LAYOUT", "dynamic": false,
              "schema": { "type": "object", "required": ["sql"], "properties": { ... }, "definitions": { } },
              "layout": { "ui:order": [...], "sql": { "ui:widget": "..." } } },
  "output": { "type": "SCHEMA_AND_LAYOUT",
              "schema": { "type": "object", "properties": { "rows": {...}, "rowsCount": {...}, "rowsAffected": {...} } } },
  "groupDetails": { } }
```
- Generate node `inputs` against `input.schema`. `input.layout` is UI-only.
- `input.dynamic: true` means the schema depends on runtime lookups — not yet exercised (§19).
- Some outputs are `SCHEMA_AND_LAYOUT` with no properties (e.g. callables) — they are
  dynamic, derived from the node's own config.

### `GET /api/workflow-builder/find-nodes-with-connections` — Nodes with a connection
✅ UAT · 2026-09-19

Same `fields` param as `/nodes`. Returns a **plain JSON array** (not the `objects` envelope)
of nodes that have at least one configured connection. 299 on UAT.

### Other builder endpoints

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/api/workflow-builder/search-nodes-and-resources` | 👁 UAT | → `{nodeBuilders:{...}, nodeBuilderResources:{...}}` |
| GET | `/api/workflow-builder/env-variables` | 👁 UAT | |
| GET | `/api/workflow-builder/node/resource/entity-search-enabled` | 👁 UAT | |
| POST | `/api/workflow-builder/lookup/output-schema` | 👁 UAT | called before a test run |
| POST | `/api/workflow-builder/lookup/input-schema` | 📦 | |
| POST | `/api/workflow-builder/lookup/output-schema/with-errors` | 📦 | |
| POST | `/api/workflow-builder/lookup/nodes/output-schema/with-errors` | 📦 | |
| POST | `/api/workflow-builder/lookup/node/output-schema` | 📦 | |
| POST | `/api/workflow-builder/lookup/node/aggregation-metadata` | 📦 | |
| POST | `/api/workflow-builder/lookup/resources` | 📦 | |
| POST | `/api/workflow-builder/lookup/start-schema/` | 📦 | |
| POST | `/api/workflow-builder/lookup/runtime-connections-schema/` | 📦 | |
| POST | `/api/workflow-builder/lookup/{run,user,env,alert}-variables-schema` | 📦 | four variants |
| POST | `/api/workflow-builder/lookup/error-schema` | 📦 | |
| POST | `/api/workflow-builder/lookup/applications/` | 📦 | |
| POST | `/api/workflow-builder/collect-slot-schema` | 📦 | |
| POST | `/api/workflow-builder/node/automap` | 📦 | auto-map fields between steps |
| POST | `/api/workflow-builder/node/suggestions` | 📦 | next-node suggestions |
| GET | `/api/workflow-builder/node/resources` | 📦 | |
| GET | `/api/workflow-builder/webhook-url` | 📦 | |
| GET | `/api/workflow-builder/webhook-trigger-url` | 📦 | likely the URL for a `WEBHOOK` trigger — see §19 |

---

## 6. Workflow execution & runs

### `POST /api/test-workflow/initiate-test/{workflowId}` — Run a workflow
✅ UAT · 2026-09-19

Starts a run with an input payload. Despite the name, **it executes against real systems** —
the Oracle and HTTP calls in verified runs were genuine round trips.

**Request**

| Field | Type | Req | Notes |
|---|---|---|---|
| `payload` | object | ✅ | inputs matching the START node's `inputs.setup` schema |
| `type` | string | ✅ | `"MOCK"` |
| `workflowDefinition` | object | ✅ | the full definition **without `id`** — can be unsaved |

```json
{ "payload": { "customerId": "CUST-12345", "maxRows": 10 },
  "type": "MOCK",
  "workflowDefinition": { "name": "...", "version": 3, "nodes": [...], "edges": [...], "settings": {...} } }
```

**Response** — 200 `{ "runId": "6aae266715ef207b242e9026" }`. The run is asynchronous; poll
status next.

**Notes**
- Because the definition travels inline, you can test a graph you have not saved.
- Very large graphs (~60+ heavy nodes) can **time out the HTTP call** while the run still
  starts. Verify by reading results, not by the response. (APS1)
- This is the **test** runner. How to invoke a *deployed* workflow from outside is open (§19).

### `POST /api/aggregation?entityType=WORKFLOW_EXECUTION&group=TEST_WORKFLOW_EXECUTION` — Run status
✅ UAT · 2026-09-19 · ✅ APS1 · 2026-09-20

**Request**
```json
{ "entityType": "WORKFLOW_EXECUTION", "group": "TEST_WORKFLOW_EXECUTION",
  "projections": [ {"name":"ID"}, {"name":"STATUS"}, {"name":"EXECUTION_TIME"},
                   {"name":"START_TIME"}, {"name":"END_TIME"}, {"name":"FAILED_NODES"},
                   {"name":"START_NODE_OUTPUT"} ],
  "filter": { "op": "IN", "field": "ID", "values": ["<runId>"] },
  "page": { "limit": 5, "offset": 0 } }
```
To list runs of one workflow: filter `{"op":"IN","field":"WORKFLOW_ID","values":["<wfId>"]}`
and sort `[{"field":"START_TIME","order":"DESC"}]`. The UI also filters
`CONCURRENT_EXECUTION IN [false]`.

**Response**
```json
{ "objects": [ { "columns": {
    "ID": "6aae266715ef207b242e9026", "STATUS": "COMPLETED", "EXECUTION_TIME": 395,
    "START_TIME": 1789797991130, "END_TIME": 1789797991525,
    "START_NODE_OUTPUT": { "customerId": "CUST-12345", "maxRows": 10 },
    "DEPLOYED_WORKFLOW_ID": "s_6aae21e0.../3/Khf8HC...=",
    "ROOT_EXECUTION_INSTANCE_ID": "...", "PARENT_EXECUTION_INSTANCE_ID": "...",
    "OTEL_TRACE_ID": "9e6bb8b5db1aa6d60f103176d3441eba", "RUN_TIME_TYPE": "TEST",
    "FAILED_NODES": ["n_code"], "DEBUGGED": false } } ],
  "type": "AGGREGATION_RESPONSE" }
```

| Projection | Meaning |
|---|---|
| `STATUS` | `COMPLETED`, `FAILED` observed. `CANCELLED` / `TIMED_OUT` **assumed**, not seen |
| `FAILED_NODES` | node ids that failed — present on `FAILED` |
| `START_NODE_OUTPUT` | echoes the input payload |
| `DEPLOYED_WORKFLOW_ID` | the snapshot actually run |
| `OTEL_TRACE_ID` | OpenTelemetry trace id |

**Notes**
- Projection names are **UPPERCASE**.
- ⚠️ The id filter differs by tenant — see §18: `field:"ID"` (UAT) vs `field:"fields.id"` (APS1).
- A `COMPLETED` status only means no node threw. Assert on the output payload.

### `POST /api/lookup?ByKeys=TEST_WORKFLOW_VARIABLE` — Node inputs/outputs of a run
✅ UAT · 2026-09-19 · ⚠️ see §18 for APS1

Reads what a node actually received and produced. **This is how you verify a run.**

**Request**
```json
{ "type": "ByKeys", "lookupType": "TEST_WORKFLOW_VARIABLE",
  "keys": [ "<runId>.<runId>.n_out", "<runId>.<runId>.n_sql" ],
  "options": { "startTime": <START_TIME - 10000>, "endTime": <END_TIME + 10000>,
               "workflowId": "<workflowId>" } }
```
Key = `{rootExecutionId}.{executionInstanceId}.{nodeId}`; for a top-level run both ids
equal the `runId`. `startTime`/`endTime` are epoch ms bracketing the run.

**Response**
```json
{ "response": { "objects": {
    "<runId>.<runId>.n_sql": [
      { "type": "inputs",  "nodeId": "n_sql",
        "payload": { "sql": "SELECT 'CUST-12345' AS CUSTOMER_ID, SYSDATE AS AS_OF FROM DUAL" } },
      { "type": "outputs", "nodeId": "n_sql",
        "id": "<runId>/<runId>/n_sql/outputs",
        "payload": { "rows": [ { "CUSTOMER_ID": "CUST-12345", "AS_OF": "2026-09-19 06:54:34" } ],
                     "rowsCount": 1, "rowsAffected": 0 } } ] },
  "type": "MAPPED_HITS" } }
```

| Entry `type` | Contains |
|---|---|
| `inputs` | node inputs **with templates already resolved** — shows exactly what ran |
| `outputs` | node outputs, or an error object `{errorCode, cause:{...}, message}` on failure |
| `state` | runtime state, e.g. `{ "iteration": 3 }` on a `LOOP` |

### `POST /api/workflow-runs/node-executions` — Per-node timings
👁 UAT · 2026-09-19

Grouped per node: `STATUS`, `ENTRY_TIME`, `EXIT_TIME`, `EXECUTION_TIME`, `SKIPPED`,
`EXECUTION_INSTANCE_ID`, `ROOT_EXECUTION_INSTANCE_ID`, `PARENT_EXECUTION_INSTANCE_ID`.
Body wraps an aggregation query:
```json
{ "aggregationQuery": { "entityType": "WORKFLOW_NODE_EXECUTION", "group": "TEST_WORKFLOW_EXECUTION",
    "projections": [ { "name": "CURRENT_NODE_ID", "projections": [
        { "name": "CURRENT_NODE_ID", "aggregationFunction": "GROUP" },
        { "name": "ENTRY_TIME", "aggregationFunction": "MAX" },
        { "name": "STATUS", "aggregationFunction": "MAX_BY", "additional": { "AGGREGATE_BY": "ENTRY_TIME" } } ] } ] } }
```

### `POST /api/workflow/execute/node?name={registeredName}` — Named internal automation
⚠️ UAT · APS1 · 2026-09-19

Executes a **registered internal automation by name**. It is **not** a generic "run any
connector action" endpoint.

```json
{ "id": "getIndexRecommendationsForWorkflow",
  "context": { "appName": "standard_entities",
               "resourceName": "standard_entities_get_index_recommendations_for_workflow" },
  "inputs": { "includeOnlyMissingIndexes": true, "workflowId": "6aae21e07c95610571778cb5" } }
```

Calling it with an arbitrary connector action returns **500 `forbidden datasource: not
found`**. Use a real workflow + `initiate-test` for connector actions.

Registered names observed in UI traffic:

| Name | Purpose | Status |
|---|---|---|
| `fetchUserPreferences` | UI preferences | 👁 |
| `fetch_records` | generic record fetch (saved views, etc.) | 👁 |
| `WorkflowScore` | best-practice score → `{score, totalChecks, passedChecks, success}` | 👁 |
| `getIndexRecommendationsForWorkflow` | index hints → `{result:{workflowIndexRecommendations:[]}}` | 👁 |
| `call_automation` | starts the prompt-to-automation copilot | 👁 |
| `fetch_ai_workflow_case_id`, `CopilotLookup`, `fetch_current_case`, `update_case_additional` | copilot internals | 👁 |
| `GetAllSessions`, `GetTraceTimeline`, `TraceTimelineDetails` | observability — see §11 | ✅ |

### Other execution endpoints

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/api/workflow/execute/node/sse` | 👁 UAT | server-sent-events stream used by the copilot. **Do not** clone/buffer the stream client-side — it stalls the session ("lost track of your active connection session") |
| POST | `/api/workflow/cancel/execution/` | 📦 | |
| POST | `/api/workflow/re-trigger-execution` | 📦 | |

---

## 7. Connections

### `GET /api/connection` — List all connections
✅ UAT · 2026-09-19

**Response** — 200 `{ "objects": [ ... ], "hasMore": false }`. **Every** connection in the
tenant (7,775–7,787 on UAT).

```json
{ "id": "6971155898773c08b865cacb", "appName": "oracledb", "name": "OracleDB Server",
  "active": true, "projectId": "...", "options": {}, "userInput": { "<redacted>": "..." },
  "captureFailures": false, "standard": false, "version": 0,
  "ownerUserId": 0, "createdTime": 0, "modifiedTime": 0, "lcName": "..." }
```

**Notes**
- ⛔ **No server-side filter on this endpoint.** `?appName=`, `?app=`, `?appNames=`, `?filter=`,
  `?active=` are all ignored, and it is slow enough to exceed a 45 s client timeout.
  **Use `POST /api/aggregation?entityType=Connection&group=STANDARD` instead** (below) — it
  filters server-side in ~50 ms and does not return secrets.
- 🔴 **`userInput` contains secrets in clear** (`password`, `authToken`). Redact before
  logging or returning anywhere.
- **Names are not unique** (three different connections are all `RDQA-OracleDB-PRY`). Find a
  connection by the host/service in `userInput`, not by name.
- Match `appName` to the node name; prefer `active: true`.

### `GET /api/connection/{connectionId}` — One connection
✅ UAT · 2026-09-19

**Errors** — 500 `{"rootCauseMessage":"CONNECTION with id X not found","assetClass":"CONNECTION","errorCode":5002}`.

### `POST /api/lookup?ByQuery=CONNECTION` — Search connections by name
✅ APS1 · 2026-09-19

The fast alternative to pulling all connections.
```json
{ "type": "ByQuery", "lookupType": "CONNECTION", "query": "Maher", "fields": ["name"],
  "options": { "appName": "mdm_by_unifyapps" }, "page": { "limit": 20, "offset": 0 } }
```

### `POST /api/aggregation?entityType=Connection&group=STANDARD` — Find connections (server-side)
✅ UAT · 2026-09-21

The Connections Manager list uses this. Filters on `appName`, `active`, `oUId`, `name`, `tags`.
```json
{ "entityType": "Connection", "group": "STANDARD", "includeTotalHits": true,
  "filter": { "op": "AND", "values": [
      { "field": "appName", "op": "EQUAL", "values": ["github"] },
      { "field": "active", "op": "EQUAL", "values": [true] } ] },
  "projections": [{"name":"id"},{"name":"name"},{"name":"appName"},{"name":"oUId"},{"name":"cTm"}],
  "sorts": [{"field":"cTm","order":"DESC"}], "page": { "limit": 30, "offset": 0 } }
```
**Response** — aggregation envelope; `totalHits` 56 for `github` on UAT; ~50 ms. No `userInput`.

### `GET /api/applications/{appName}?fields=authSpec,iconUrl,displayName,name,refreshable,includeOptions` — Connector auth form
✅ UAT · 2026-09-21

`authSpec.input` is a `SCHEMA_AND_LAYOUT` JSON Schema describing the connection `inputs`
(Custom HTTP: `name, requestType, authType, baseUrl, headersList, sslVerify,
requestTimeoutInSecs, connectionType, groupId, …`). Auth-type options come from
`POST /api/lookup?ByQuery=CUSTOMER_AUTH` `{options:{appName, auths:[{type,label}]}}` 👁.

### `POST /api/connection/input/test?appName={appName}` — Test connection inputs
✅ UAT · 2026-09-21

Same body as create (below). **204** = success; the UI shows *Test connection successful*.

### `POST /api/connection/input?appName={appName}` — Create connection
✅ UAT · 2026-09-21

```json
{ "name": "maher_scratch_http (Claude API learning)", "authType": "CUSTOM",
  "inputs": { "name": "maher_scratch_http (Claude API learning)", "requestType": "HTTP",
              "authType": "CUSTOM", "baseUrl": "https://jsonplaceholder.typicode.com",
              "headersList": [], "sslVerify": true, "requestTimeoutInSecs": -1,
              "connectionType": "DIRECT", "tags": [],
              "rateLimitConfig": {"enabled": false}, "circuitBreakerConfig": {"enabled": false} },
  "options": { "rateLimitConfig": {"enabled": false}, "circuitBreakerConfig": {"enabled": false} },
  "tags": [] }
```
**Response** — 200, the connection (`id` 24 hex, `active: true`, `userInput` echoed). Created
`6ab0ea7a5459f4370f0c1f3f` on UAT. `inputs` follow the app's `authSpec`. OAuth apps need the
user to click *Authorize* in the UI — do not attempt to script it.

### `POST /api/connection` — Create connection (bare)
⚠️ APS1 · 2026-09-19

Creating an `mdm_by_unifyapps` UDM connection by hand fails with
`No Value found in filter with field: sourceConnectionId` — a context graph creates its own
(§12). For ordinary connectors use `POST /api/connection/input?appName=` above.

**Connection config notes**
- Oracle **EBS**: `appName: "oracledb"`, `serviceName` = the **PDB**,
  `isCDBDatabase: false`. Pointing at the CDB gives `ORA-01017` (APPS is PDB-local).

---

## 8. Entities (generic CRUD)

Agents, tasks, tools, prompts, context-graph records and more are all **entities**, sharing
one CRUD surface keyed by `entityType`.

### `POST /api/entity` — Create
✅ UAT · APS1 · 2026-09-19

**Request**

| Field | Type | Req | Notes |
|---|---|---|---|
| `entityType` | string | ✅ | e.g. `ai_agent`, `e_action_ai_agent`, or an ECG `unifiedEntityId` |
| `properties` | object | ✅ | the entity's content |
| `tags` | string[] | | ⚠️ **top level only** — inside `properties` it 500s |

```json
{ "entityType": "e_topic_ai_agent", "tags": ["MAHER"],
  "properties": { "name": "Customer Lookup", "aiAgentId": "e_...", "enabled": true } }
```

**Response** — 200, entity envelope with a new `e_...` id (ECG records use the primary-key
value as id). Server fills defaults (e.g. tools get `enabled: false` unless set).

**Errors**

| Status | Message | Cause |
|---|---|---|
| 500 | `Non Empty Validations ... add additionalProperties tags` | `tags` placed inside `properties` |

### `GET /api/entity/{entityType}/{id}` — Read
✅ UAT · APS1 · 2026-09-19

`GET /api/entity/{id}` without the type is ⛔ 405. Some types are singletons readable
without an id: `GET /api/entity/e_ai_agent_settings` ✅ returns the settings entity.

### `POST /api/entity/{entityType}` — List
✅ UAT · 2026-09-19

⚠️ **This lists — it does not create.** Posting a create body here returns a page of
existing entities and writes nothing.

**Request** — `{ "page": { "limit": 50, "offset": 0 } }`

**Response** — `{ objects, hasMore, cursor, type }`.

**Paging:** ⚠️ **offset-based.** Feeding `cursor` back silently re-returns page 1, so a
cursor loop yields duplicates. Increment `offset`; stop on `hasMore === false`.

### `POST /api/entity/update` — Update
✅ UAT · 2026-09-19

```json
{ "id": "e_6aae34db6a7a1a6dffbce1b5", "entityType": "e_action_ai_agent",
  "properties": { ...full properties, modified... }, "version": 0 }
```
Send the **full** `properties` and the **current** `version`. Response: entity, version +1.

### `POST /api/entity/action/saveAndDeploy` — Publish
✅ UAT · 2026-09-19

Publishes an entity (used for agents). Send the **whole entity object** as read, plus notes.

```json
{ ...entity from GET /api/entity/ai_agent/{id}..., "deploymentNotes": "V1 via API" }
```

**Response** — entity with `deploymentState: { deployedAt, deployedBy, entityVersion, version }`.

**Errors**

| Status | Message | Cause |
|---|---|---|
| 500 | `Non Empty Validations in Validating entity ai_agent with validationResult required name` | sent a partial body (e.g. `{id, entityType}`) or `properties.name` missing |

### Entity types reference

| entityType | What | Aggregation group |
|---|---|---|
| `ai_agent` | agent | ENTITY |
| `e_topic_ai_agent` | agent **Task** | ENTITY |
| `e_action_ai_agent` | agent **Tool** / capability | ENTITY |
| `e_prerequisite_task_ai_agent` | prerequisite action | ENTITY |
| `e_ai_agent_settings` | tenant agent settings (singleton) | ENTITY |
| `ai_agent_deployment` | channel deployment | ENTITY |
| `ai_agent_llm_model` | model registry | ENTITY |
| `e_ai_agent_team`, `e_ai_team_task` | multi-agent teams | ENTITY |
| `prompt` | reusable prompts (26 on UAT) | ENTITY |
| `knowledge_set`, `knowledge`, `knowledge_source` | RAG | ENTITY |
| `EntityType` | the type registry itself (17,791 on UAT) | STANDARD |
| `WorkflowDefinition` | workflows | STANDARD |
| `KNOWLEDGE_GRAPH_NODE` / `_EDGE` / `_SOURCE` | ECG schema | STANDARD |
| `<unifiedEntityId>` | an ECG node's records | — |
| `e_interface` | application (config or code) — id is a slug | ENTITY (§22) |
| `e_component` | app page / module / template component | ENTITY (§22) |
| `e_data_source` | app data source (authorises execute-node) | ENTITY (§22) |
| `e_theme`, `e_page_template`, `e_custom_component`, `e_i18n_namespace` | app theme / page templates / custom React components / translations | ENTITY |
| `EntityType` (`ENTITY_TYPE` in lookups) | Objects Manager objects | STANDARD (§24) |
| `Connection` | connections | STANDARD (§7) |
| `<objectId>` (e.g. `maher_scratch_task`, or `obj_<5 chars>` when generated) | an object's records | ENTITY (§24) |

Discover any type's fields with `POST /api/aggregation/metadata` (§10).

---

## 9. AI agents, tasks, tools

Built entirely on §8's entity CRUD. **A tool is a call into a workflow** — the same
`callables_call_automation` contract as a `CALL_WORKFLOW` node.

### Agent — `ai_agent`
✅ UAT · 2026-09-19

**Create** via `POST /api/entity`:
```json
{ "entityType": "ai_agent",
  "properties": { "name": "Fleet Operations Assistant", "agentType": "CONVERSATIONAL",
                  "instructions": "You help fleet operators ..." } }
```
`properties.name` is required for publish. Publish with `saveAndDeploy` (§8).

**Key properties**

| Property | Meaning |
|---|---|
| `name` | required |
| `instructions` | the system prompt (string) |
| `agentType` | `CONVERSATIONAL` |
| `role`, `goal` | shown in the UI Instructions tab; enrichers use `role: "Enricher"` |
| `responseGenerationSettings.answerGenerationModel` | answer model |
| `responseGenerationSettings.outputSchema` | structured output — the contract for enricher agents |
| `responseGenerationSettings.{tone,style,format}` | response shaping |
| `topicExecutionSettings.{topicSelectionModel,topicExecutionModel,topicAsTool}` | task routing |
| `preProcessingSettings`, `indexingSettings` | RAG behaviour |
| `longTermMemorySettings.enabled`, `contextManagement.*` | memory / context |
| `graphModelId` | links a context graph (does **not** by itself enable graph search — §12) |
| `defaultTools` | map of booleans; ⚠️ capabilities are really tool rows — see below |
| `mcpEnabled`, `visibility.type`, `evalSettings`, `loggingSettings` | misc |

### Task — `e_topic_ai_agent`
✅ UAT · 2026-09-19

```json
{ "entityType": "e_topic_ai_agent",
  "properties": {
    "name": "Vehicle Status",
    "description": "Use this task when the user asks about a vehicle's status or telemetry.",
    "instructions": [ "Confirm the vehicle id.", "Call VehicleLookup.", "Summarise in plain English." ],
    "aiAgentId": "e_6aae3af83c95b76375e9046c",
    "enabled": true, "isAppConnector": false, "runTimeConnectionEnabled": false,
    "governanceConfig": {} } }
```
- `description` = **when** (what the router matches on). `instructions` = **how** — an
  **array of strings**, rendered as numbered steps.
- Optional `modelSelectionConfig` overrides the model per task.
- At runtime `SetTopic` is a real tool call; the task's `instructions[]` arrive as its
  tool result (visible in traces, §11).

### Tool — `e_action_ai_agent` (workflow-backed)
✅ UAT · 2026-09-19

```json
{ "entityType": "e_action_ai_agent",
  "properties": {
    "name": "VehicleLookup",
    "description": "Look up a vehicle record by vehicle id.",
    "aiAgentId": "e_6aae3af83c95b76375e9046c",
    "topicId": "GLOBAL",
    "context": { "appName": "callables", "resourceName": "callables_call_automation" },
    "inputs": { "automationId": "6aae3aaa0900af6ee3a552b8", "version": "-1",
                "synchronous": true, "runtimeConnections": {}, "parameters": {} },
    "enabled": true,
    "approvalConfig": { "enabled": true, "storeUserApprovalPreference": false } } }
```

| Field | Notes |
|---|---|
| `topicId` | `"GLOBAL"` = agent-wide (Tools tab); a task id = scoped to that task only |
| `inputs.automationId` | the workflow to call — must be **deployed** |
| `inputs.version` | `"-1"` = latest deployed |
| `inputs.parameters` | `{}` lets the model fill args from the workflow's `inputs.setup` schema |
| `enabled` | ⚠️ **defaults to `false`** — the tool silently never fires |
| `approvalConfig` | human-in-the-loop gate; shows real parameter values + Deny / Approve Once. **Deny genuinely blocks the write** ✅. Put it on every write tool; republish after changing |

Server-applied defaults also seen: `deferToolLoading`, `enableToolSearch`,
`excludeInputOutputFromTrace`, `isStandardAction`, `runTimeConnectionEnabled`.

### Capability — `e_action_ai_agent` with `isStandardAction: true`
✅ UAT · 2026-09-19

Built-in capabilities are **tool rows**, not agent fields:
```json
{ "entityType": "e_action_ai_agent",
  "properties": { "name": "generateChartTool", "aiAgentId": "<agent>",
                  "isStandardAction": true, "enabled": true, "topicId": "GLOBAL" } }
```
Standard names seen: `generateChartTool`, `renderArtifact`, `loadSkill`, `webSearch`,
`createExcel`, `createDocx`, `createDocxOrPdf`, `createPDF`, `createPPTX`,
`createFlowDiagram`, `createFile`, `analyseFile`, `documentVision`, `deepResearch`,
`generateImageTool`, `executeCodeTool`, `ingestKnowledge`, `companyKnowledge`, `planTool`,
`todo_tool`, `summaryTool`, `requestClarification`, `clarifyFromUser`, `qa`,
`informationNotFoundTool`, `generatePublicFileUrl`, `allowKnowledgeControl`,
`CompleteDocumentContext`, `generateAndEditEmail`, `Build_App`.

⚠️ **`generateChartTool` needs `renderArtifact` too**, or the agent prints a table while
claiming it drew a chart. Charting is expensive (one request measured ~291 K tokens, ~$0.94).

### Recipe — agent with workflow-backed tools
✅ UAT · 2026-09-19 (Fleet Operations Assistant `e_6aae3af83c95b76375e9046c`)

1. Build → save → check violations → **deploy** each workflow (§4). CALLABLE trigger with a
   clear `inputs.setup` — that schema becomes the tool's argument contract.
2. Smoke-test each with `initiate-test`; assert on the `n_out` payload (§6).
3. `POST /api/entity` → `ai_agent`.
4. `POST /api/entity` → one `e_topic_ai_agent` per journey.
5. `POST /api/entity` → one `e_action_ai_agent` per workflow, `enabled: true`, right `topicId`.
6. `POST /api/entity/action/saveAndDeploy` with the full agent entity.

---

## 10. Search: aggregation & lookup

### `POST /api/aggregation?entityType={t}&group={g}` — Universal query
✅ UAT · APS1 · 2026-09-19

The platform's general search. `entityType` and `group` go in **both** the query string and
the body. Optional query param `name=table_block` (👁, used by list screens).

**Request** — send the **complete** body; partial bodies 500 with no useful message.
```json
{ "entityType": "WorkflowDefinition", "group": "STANDARD", "includeTotalHits": true,
  "filter": { "op": "AND", "values": [
      { "op": "EQUAL", "field": "d", "values": [false] },
      { "op": "ICONTAINS", "field": "lcName", "values": ["fleet"] } ] },
  "sorts": [ { "field": "cTm", "order": "DESC" } ],
  "projections": [ {"name":"id"}, {"name":"name"}, {"name":"trigger"}, {"name":"deployed"},
                   {"name":"appsUsed"}, {"name":"tags"}, {"name":"oUId"}, {"name":"cTm"} ],
  "page": { "limit": 30, "offset": 0 } }
```
A filter may also be a single flat condition: `{"field":"graphId","op":"EQUAL","values":["..."]}`.

**Groups**

| group | entityTypes |
|---|---|
| `STANDARD` | `WorkflowDefinition`, `EntityType`, `KNOWLEDGE_GRAPH_NODE/EDGE/SOURCE` |
| `ENTITY` | `e_*` entity types, `ai_agent_deployment`, `e_platform_asset_settings`, ... |
| `TEST_WORKFLOW_EXECUTION` | `WORKFLOW_EXECUTION`, `WORKFLOW_NODE_EXECUTION` |

**Operators seen:** `AND`, `OR`, `EQUAL`, `NOT_EQUAL`, `IN`, `ICONTAINS`, `EXISTS`,
`MISSING`, `GT`, `GTE`, `LT`, `LTE`.

**WorkflowDefinition projections:** `id`, `name`, `trigger` (`CALLABLE`, `SCHEDULED`,
`Application`, ...), `deployed`, `appsUsed`, `tags`, `standard`, `pId`, `oUId`, `cTm`,
`mTm`, `lMBy`. Filter fields: `d`, `standard`, `lcName`.

**Errors / gotchas**

| Symptom | Cause |
|---|---|
| 500, no message | body incomplete — send all of entityType, group, filter, sorts, projections, page |
| 500 `projections is null` | `projections` is **mandatory** for `group: ENTITY` |
| 500 `Invalid group: STANDARD and type: e_topic_ai_agent` (5004) | wrong group for the type |
| unrelated rows returned | ⚠️ `ICONTAINS` on `lcName` does **not** filter entity types — list and filter client-side |
| no `name` column | entity projections return only `id` / `tags` — read names via entity list |

Scale on UAT (2026-09-19): 31,703 workflows · 28,994 tools · 2,872 tasks.

### `POST /api/aggregation/metadata` — Field list for any type
✅ APS1 · 👁 UAT · 2026-09-19

```json
{ "group": "ENTITY", "entityType": "ai_agent_deployment" }
```
Returns every field for the type. **The fastest way to learn an unknown schema.**

### `POST /api/lookup?ByKeys={TYPE}` / `?ByQuery={TYPE}` — Keyed / text lookup
✅ UAT · APS1 · 2026-09-19

```json
// by keys
{ "type": "ByKeys", "lookupType": "USER", "keys": ["82118"] }
// by query
{ "type": "ByQuery", "lookupType": "CONNECTION", "query": "Maher", "fields": ["name"],
  "options": { "appName": "mdm_by_unifyapps" }, "page": { "limit": 20, "offset": 0 } }
```

| lookupType | Status | Use |
|---|---|---|
| `TEST_WORKFLOW_VARIABLE` | ✅ UAT | node inputs/outputs of a run (§6) |
| `CONNECTION` | ✅ APS1 | find a connection by name |
| `USER` | 👁 | user records (`email`, `name`, `userGroups`, `ssoLogin`, `state`, `userSessionType`) |
| `ENTITY_PERMISSIONS` | 👁 | `options: {entityType}`, `keys: [id]` |
| `ENTITY`, `UNIFIED_ENTITY`, `UNIFIED_ENTITY_MODEL` | 👁 APS1 | ECG and entity lookups |
| `TAG`, `NODE_BUILDER`, `TRIGGER_TYPE`, `s_project` | 👁 | UI list rendering |
| `WorkflowDefinition` | ⛔ | 500 — use aggregation instead |

`POST /api/lookup/bulk` is also used by the UI (👁).

### `POST /api/global-search` — Global search
⚠️ UAT · 2026-09-19

`{ "query": "user role matrix" }` → `{"hasMore":false}` with no results. Body shape not
understood yet. `/api/global-search/recent-searches` is 👁.

---

## 11. Observability & traces

Reads an agent's sessions and the **exact message array sent to the model**. Called through
the named-automation executor.

| Call | Returns | Status |
|---|---|---|
| `POST /api/workflow/execute/node?name=GetAllSessions` | sessions | ✅ UAT |
| `POST /api/workflow/execute/node?name=GetTraceTimeline&fetchTraceDetail={traceId}` | span tree | ✅ UAT |
| `POST /api/workflow/execute/node?name=TraceTimelineDetails&fetchTimelineDetails={spanId}` | span input/output incl. full `message[]` | ✅ UAT |

Request bodies are not yet recorded in full — the reliable method so far is to drive the UI
(`/p/0/ai-agents/{id}/observability`) and read the `TraceTimelineDetails` response from
network capture.

What traces reveal:
- Tool results verbatim — an empty `""` result is immediately visible.
- `SetTopic` is a real tool call carrying the task instructions.
- The platform appends a synthetic user turn `"Lets continue.."` after an assistant turn,
  causing an extra generation (the source of trailing "anything else?" filler).

---

## 12. Enterprise Context Graph

Verified on **APS1** across three graph builds (2026-09-19/20) unless marked. Deep detail
lives in the `unifyapps-context-graph` skill.

### Critical ordering rules

1. **Publish the graph before loading records.** Records written to a `DRAFT` graph go to
   the entity store and are **never projected** into the Cypher layer — no error.
2. **Make every property `STRING`.** Typed properties store fine but the node projects
   **zero vertices**. Convert in Cypher (`toFloat(...)`).
3. **Records never link themselves.** Record edges are written only by the MDM connector
   inside a workflow (§16).

### Graph

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/api/context-graph` | ✅ | create — body `{name, description}` |
| GET | `/api/context-graph/{graphId}` | ✅ | header |
| POST | `/api/context-graph/update/{graphId}` | ✅ | |
| POST | `/api/context-graph/{graphId}/publish` | ✅ | `DRAFT` → `LIVE` |
| POST | `/api/context-graph/delete/{graphId}` | ✅ | |
| GET | `/api/context-graph/templates` | ✅ | prebuilt templates |

**Create response:** `{ id, status: "DRAFT", nodeCount: 1, unifiedEntityModelId: <same as id>, version: 1 }`.
Side effects: a default **`ecg_grant`** node (leave it), and an `mdm_by_unifyapps` **UDM
connection** named `<graph name> UDM Connection` with `userInput.unifiedEntityModelId =
<graphId>`. Use that connection for every MDM step; never hand-create one.

### Nodes (types)

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/api/context-graph/nodes` | ✅ | create |
| GET | `/api/context-graph/nodes/{nodeId}` | ✅ | incl. `properties[]`, `entityMetadata`, `recordTitleFormat` |
| POST | `/api/context-graph/nodes/update/{nodeId}?version={n}` | ✅ | ⚠️ version in the **query string**; body = full node |
| POST | `/api/context-graph/nodes/delete/{nodeId}` | ✅ | |
| POST | `/api/context-graph/nodes/bulk-update-node-positions` | ✅ | canvas layout |
| GET | `/api/context-graph/nodes/templates` | ✅ | node templates |

**Create node request**
```json
{ "graphId": "<graphId>", "name": "Customer", "category": "core", "description": "...",
  "iconUrl": "account-executive", "nodePosition": { "x": 0, "y": 0 },
  "recordTitleFormat": "{{ mdm.field.customer_name }}",
  "properties": [
    { "id": "customer_id", "displayName": "Customer Id", "dataTypeInfo": { "type": "STRING" },
      "primaryKey": true, "required": true, "unique": false, "pii": false,
      "filterable": false, "sortable": false, "searchable": false,
      "graphQueryable": true, "standard": false } ] }
```
**Response:** node with server `id` **and** `unifiedEntityId` (the Cypher label and the
record `entityType`). `dataTypeInfo.type` values: `STRING`, `DOUBLE`, `BOOLEAN`, `DATE`,
`INTEGER`, `JSON`, `ARRAY` — **use STRING only** (rule 2).

**Errors:** `500 version is required for node update` → version belongs in the query string.
`500 Please delete data before updating entity schema` → type changes need zero records.

### Edges (types)

| Method | Path | Status |
|---|---|---|
| POST | `/api/context-graph/edges` | ✅ |
| GET | `/api/context-graph/edges/{edgeId}` | ✅ |
| POST | `/api/context-graph/edges/update/{edgeId}` | ✅ |
| POST | `/api/context-graph/edges/delete/{edgeId}` | ✅ |

```json
{ "graphId": "<graphId>", "label": "WORKS_AT", "fromNodeId": "<nodeId>", "toNodeId": "<nodeId>" }
```
A type-level edge only **declares** a relationship may exist; it materialises nothing.

### Records

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/api/entity` | ✅ | create — `{entityType: <unifiedEntityId>, properties:{...}}`; id = primary-key value |
| POST | `/api/entity/update` | ✅ | |
| GET | `/api/entity/{unifiedEntityId}/{recordId}` | ✅ | raw record incl. `mdmRecordMetadata` |
| POST | `/api/context-graph/{graphId}/nodes/{unifiedEntityId}` | ✅ | list — `{includeTotalHits, page:{limit,offset}}`; flat props + `_ua_recordTitle`, `labels`, `modelId` |
| GET | `/api/context-graph/{graphId}/unifiedEntity/{ue}/records/{recordId}` | ✅ | record + `edges[]` |
| GET | `/api/context-graph/{graphId}/unifiedEntity/{ue}/records/{recordId}/graph?depth=1` | ✅ | neighbourhood |
| DELETE | `/api/entity/{ue}/{id}` | ⛔ 405 | delete via `storage_by_unifyapps_delete_records` in a workflow |
| POST | `/api/entity/action/delete` | ⛔ 405 | same |

Record edge shape (on read):
```json
{ "direction": "OUTGOING", "entityType": "<other ue>", "isDangling": true,
  "recordId": "TKT-002", "recordTitle": "AXN-256 - Duplicate Customer Profiles",
  "relationshipId": "HAS_TICKET", "relationshipLabel": "HAS_TICKET",
  "properties": { "edgeLabel": "HAS_TICKET", "id": "90::ueA::ACC-001::90::ueB::TKT-002" } }
```
`isDangling: true` = no matching type-level edge; still traverses normally.

`mdmRecordMetadata` carries field-level lineage: `sourceDetails[{fieldName, sourceAppName,
sourceId, stageRecordId, modifiedTime}]`, `contributingSources[]`,
`associatedStagingRecordIds[]`, `dataQualityResult`, `modelId`, `stagingMetadata`.

### Querying (OpenCypher)

Queried through the `mdm_by_unifyapps_execute_opencypher_query` workflow action (§16), not a
REST endpoint. Node label = `unifiedEntityId` (backticked); properties prefixed `_pr_`.
```cypher
MATCH (c:`<customer_ue>`)
WHERE toLower(coalesce(c.`_pr_name`, '')) CONTAINS 'presidential'
MATCH (c)-[:HAS_DEAL]->(d:`<deal_ue>`)
RETURN d.`_pr_deal_name` AS deal, labels(d) AS labels, d.modelId AS modelId LIMIT 50
```
Verify projection after the first record of each type: `MATCH (n) RETURN DISTINCT labels(n)`.

### Sources (connector ingestion)

| Method | Path | Status | Notes |
|---|---|---|---|
| POST | `/api/context-graph/sources` | ✅ | `{graphId, appName, connectionId, name}`; auto-fills `destinationConnectionId`; starts Draft |
| GET | `/api/context-graph/sources/{sourceId}` | ✅ | incl. `objectDiscoveryConfigRefs[]` |
| POST | `/api/context-graph/sources/update/{id}` · `/delete/{id}` | ✅ | |
| POST | `/api/context-graph/sources/{sourceId}/publish` | 📦 | |
| GET | `/api/context-graph/sources/{sourceId}/objects/fetch-selected?limit=200&offset=0` | ✅ | per-object `objectSchema`, `enrichedObjectSchemas[]`, `schemaMappings[]` |
| POST | `/api/context-graph/sources/{sourceId}/objects/bulkUpdate` | ⛔ | 200 but `{"data":0}` — writes nothing |
| GET | `/api/context-graph/sources/{sourceId}/object-discoveries` | ✅ | |
| POST | `.../object-discoveries/scope-configs/bulk-save` | ✅ | scope (e.g. Slack `channelList`) |
| POST | `.../object-discoveries/discovery-configs/bulk-save` | ⚠️ | 200, but the **enricher binding does not persist** |
| GET | `/api/context-graph/sources/{sourceId}/schema-mappings` | ✅ | returns `{"objects":[]}` |
| POST · PUT · PATCH | `/api/context-graph/sources/{sourceId}/schema-mappings` | ⛔ 405 | **Map step is wizard-only** |
| POST | `/api/context-graph/sources/{sourceId}/schema-mapping/automap` | ⛔ 405 | |
| POST | `/api/context-graph/sources/{sourceId}/transformations/save` | 📦 | |
| GET | `/api/context-graph/sources/{sourceId}/transformations/group-by-source-field` | 📦 | |
| GET | `/api/context-graph/sources/applications/{appName}/objects` | ✅ | objects a connector exposes |
| POST | `/api/context-graph/sources/applications/{appName}/objects/{objectId}/details?connectionId=` | ✅ | body `{}`; object schema (nested for raw, flat for enriched) |
| GET | `/api/context-graph/sources/applications/{appName}/settings` · `/disabled-steps` | 📦 | |
| POST | `/api/context-graph/sources/objects/describe` | ✅ | `{connectionId, objectId, sourceConfigId}` → destination `fields[]` |
| GET | `/api/context-graph/sources/discoverers/{method}/{agentId}/{n}/schema` | ✅ | e.g. `AGENT/.../0` → `{outputSchema:{...}}` |
| GET | `/api/context-graph/sources/enrichers/{method}/{agentId}/{n}/schema` | ✅ | flattens `results[].items.properties` |
| GET | `/api/context-graph/sources/app/{appName}/resource/{resourceId}` | 📦 | |

**Scope config (Slack) request**
```json
{ "objectDiscoveryConfigEntries": [
    { "objectId": "Message", "displayName": "Message",
      "scopeConfig": { "scopeActionId": "slack_index_channels_and_chat",
                       "actionInputs": { "token_type": "user_token", "channelList": ["C0BD6AWDTLH"] } } } ] }
```
⚠️ An **empty `channelList` means every channel**. Always set it. HubSpot has no
record-level scope at all.

### ECG entity-type fields (from `/api/aggregation/metadata`)

- **`KNOWLEDGE_GRAPH_NODE`**: `id graphId name lcName category color iconUrl description
  properties propertiesCount edgeCount recordCount nodePosition unifiedEntityId standard tags
  spaceId v cTm mTm oUId pId lMBy lPUBy lPUOn`
- **`KNOWLEDGE_GRAPH_EDGE`**: `id graphId label lcName description fromNodeId toNodeId
  entityRelationshipIds[] standard tags spaceId v cTm mTm oUId pId lMBy lPUBy lPUOn`
- **`KNOWLEDGE_GRAPH_SOURCE`**: `id graphId name lcName appName connectionId status
  lastSyncTimeEpochMillis standard tags spaceId v cTm mTm oUId pId lMBy lPUBy lPUOn`

---

## 13. Files

### `POST /api/file/signed-url?preview=true&expiryTime=1` — Signed download URL
✅ APS1 · 2026-09-19

```json
{ "fileDetails": { "fileType": "application/pdf", "name": "AXN-MSA.pdf", "size": 54396,
    "source": "connector_streaming_uploads/90/6/<uuid>_AXN-MSA.pdf",
    "sourceType": "CLOUD_STORAGE", "ua:type": "FILE" } }
```
**Response:** `{ "url": "/api/file/download/__UNIFY_ENCR_AWS__V0__..." }`.

### `GET /api/file/download/{encryptedRef}&isPublic=false&preview=true` — Download
✅ APS1 · 2026-09-19

Returns the file bytes. Use the `url` from `signed-url` verbatim and append the flags.

---

## 14. Other observed platform endpoints

UI plumbing seen in live traffic. Not needed for building, recorded for completeness.

| Method | Path | Status | Notes |
|---|---|---|---|
| GET | `/api/mqtt/connectionDetails?resourceTypes=PLATFORM` | 👁 | realtime channel (MQTT over WebSocket) — needed by the copilot |
| GET | `/api/notification/unopenedCount` | 👁 | |
| POST | `/api/collaborators/connect` | 👁 | 204 — builder presence |
| POST | `/api/collaborators/active-users` | 👁 | → `{activeSessions:[{sessionId, userId}]}` |
| GET | `/api/entity/deployed/e_interface/{id}` | 👁 | deployed UI interface |
| POST | `/api/entity/deployed/embedded-entities/e_component` | 👁 | UI components |
| GET/POST | `/api/entity/deployed/...` (`bulk-fetch-snapshots`, `child-entities`, `snapshot/`, `entity-dependency`) | 📦 | deployed-entity family |
| POST | `/api/entity/restore/deployed/` | 📦 | |

---

## 15. Confirmed dead ends

Tested and **do not work**. Do not retest without a reason.

| Method | Path | Result | Use instead |
|---|---|---|---|
| any | `/api/login`, `/api/auth/login`, `/api/user/login`, `/api/v1/auth/login` | 404 | `/auth/workflow/execute/node?name=emailAndPassLoginRequest` |
| any | `/api/authenticate`, `/api/auth/token`, `/api/oauth/token`, `/api/session`, `/api/auth/me` | 404 | — |
| GET | `/api/workflow-definition` | 405 | aggregation, group `STANDARD` |
| GET | `/api/entity/{id}` (no type) | 405 | `/api/entity/{type}/{id}` |
| GET | `/api/entity/ai_agent` (no id) | 405 | `POST /api/entity/ai_agent` to list |
| POST | `/api/entity` with an existing `id` | 500 Mongo `E11000 duplicate key` | `POST /api/entity/update` |
| PUT · POST | `/api/entity/{type}/{id}` | 405 | `POST /api/entity/update` |
| PUT | `/api/entity/{type}` | 405 | |
| POST | `/api/entity/action/save`, `/api/entity/action/update` | 405 | `POST /api/entity/update` |
| POST | `/api/entity/save` | 500 `ENTITY_TYPE with id save not found` | |
| DELETE | `/api/entity/{ue}/{id}` | 405 | `storage_by_unifyapps_delete_records` in a workflow |
| POST | `/api/entity/action/delete` | 405 | same |
| any | `/api/connections` | 404 | `/api/connection` |
| GET | `/api/connection?appName=` (and `app`, `appNames`, `filter`, `active`) | filter ignored | client-side filter / `lookup?ByQuery=CONNECTION` |
| any | `/api/tag`, `/api/tags`, `/api/entity-tag` | 404 | top-level `tags` on create; read via aggregation projection |
| GET | `/api/workflow-builder/nodes/{name}` | 404 | `/api/workflow-builder/node/{name}` |
| GET | `/api/workflow-builder/node/{n}/resource` | 404 | `/node/{n}/resources` |
| GET | `/api/workflow-builder/node/{n}/resources/{r}` | 404 | `/node/{n}/resource/{r}` |
| GET | `/api/workflow-builder/node/{n}/resource/{r}/schema` · `/input-schema` | 404 | `/node/{n}/resource/{r}` → `input.schema` |
| GET | `/api/workflow-builder/resource/{r}`, `/node-resource/{r}`, `/resources?nodeName=` | 404 | |
| GET | `/api/workflow-builder/node/resource?nodeName=` | 200 empty body | |
| POST | `/api/workflow/execute/node?name=<connector action>` | 500 `forbidden datasource: not found` | a real workflow + `initiate-test` |
| POST | `/api/lookup?ByQuery=WorkflowDefinition` | 500 | aggregation |
| POST | `/api/global-search/search` | 404 | |
| POST · PUT · PATCH | `/api/context-graph/sources/{id}/schema-mappings`, `.../schema-mapping/automap` | 405 | the UI wizard |
| POST | `/api/context-graph/sources/{id}/objects/bulkUpdate` | 200 `{"data":0}` — no-op | the UI wizard |
| POST | `/api/connection` for an `mdm_by_unifyapps` UDM connection | 500 `No Value found in filter with field: sourceConnectionId` | the graph creates it |
| GET | `/api/entity-type/{id}`, `/api/entity-type/find/{id}`, `/api/entity-type/by-id/{id}` | 404 | `GET /api/entity-type?entityType={id}` |
| GET | `/api/entity-type?id={id}` | 500 | same |
| POST | `/api/lookup?ByKeys=EntityType` | 500 5004 `Lookup type not supported` | `lookup?ByKeys=ENTITY_TYPE` |
| POST | `/api/aggregation/metadata?entityType=e_interface&group=ENTITY` with `{}` | 204 empty | read the entity itself |
| POST | `/api/workflow/execute/node` calling a CALLABLE with no `id` | 500 `forbidden datasource: not found` | register an `e_data_source` (§22) |
| fetch | `http://127.0.0.1` from a UnifyApps page | blocked by CSP `connect-src` | read data through the browser tool, not out of the page |

---

## 16. Node action contracts

Workflow steps are not REST endpoints, but they are the API surface you actually program
against. Each is identified by `context.{appName, resourceName, resourceVersion}`, configured
by `inputs`, and read back as `{{ n_<id>.outputs.<field> }}`.

### Node / edge model
✅ UAT · 2026-09-19

```json
{ "id": "n_sql", "type": "ACTION", "title": "Execute a SQL statement", "subTitle": "Oracle DB",
  "context": { "appName": "oracledb", "resourceName": "oracledb_execute_sql",
               "resourceVersion": 16523, "connectionId": "<id>", "type": "APPLICATION" },
  "inputs": { ... }, "groupId": "g1", "index": 2, "fallbackMode": "STOP", "skip": false }
```

| Field | Notes |
|---|---|
| `type` | `START`, `ACTION`, `STOP`, `IF_ELSE`, `LOOP`, `BREAK`, `DELAY`, `CALL_WORKFLOW` |
| `context.connectionId` | **inside `context`**, never at node level |
| `context.type` | `"APPLICATION"` on non-trigger nodes |
| `groupId` | scope: `{ownerNodeId}@{parentGroupId}@{y\|n\|l\|error}`, concatenating as it nests |
| `fallbackMode` | `STOP` (fail run) · `MANUAL` (take the `error` edge) · `CONTINUE` (⚠️ see §18) |

Edges: `{ fromNodeId, toNodeId, type, id: "{type}@{from}@{to}", name? }`.

| Edge type | `name` | Meaning |
|---|---|---|
| `next` | — / `"no"` / `"loopback"` | normal flow / else / back to loop |
| `if` | `"yes"` | true branch of `IF_ELSE` |
| `loop` | — | into a `LOOP` body |
| `error` | `"error"` | failure path (needs `fallbackMode: MANUAL`) |

### Triggers (START nodes)

| resource | `trigger.type` | inputs | Status |
|---|---|---|---|
| `callables` / `callables_from_automation` | `CALLABLE` | `setup` = JSON Schema of the workflow's **input parameters** | ✅ UAT |
| `schedule` / `schedule_default` | `SCHEDULED` | `cron: "INTERVAL"\|"CRON"`, `interval`, `frequency: MINUTES\|HOURS\|DAYS`, `sequential` | ✅ UAT |
| (event) | `EVENT` | app event triggers, e.g. `oracledb_on_new_event` | 📦 |
| (webhook) | `WEBHOOK` | | 📦 |

CALLABLE outputs mirror `setup`: `{{ n_in.outputs.customerId }}`. Trigger `context` carries no
`type` field.

### Response — `callables_return_to_automation` (type `STOP`)
✅ UAT · 2026-09-19

`inputs.result` = any scalar or nested object, returned verbatim with templates resolved.
Every path of a CALLABLE workflow must end in one — the validator enforces it.

### Sub-workflow / agent tool — `callables_call_automation`
✅ UAT · 2026-09-19

| Input | Notes |
|---|---|
| `automationId` | target workflow id (deployed) |
| `version` | `"-1"` = latest deployed |
| `synchronous` | `true` waits for the result |
| `parameters` | must match the target's `inputs.setup` |
| `runtimeConnections` | `{}` |

Used by `CALL_WORKFLOW` nodes and by `e_action_ai_agent` tools alike.

### Oracle — `oracledb_execute_sql`
✅ UAT · 2026-09-19

| Input | Req | Notes |
|---|---|---|
| `sql` | ✅ | may contain templates and `:binds` |
| `params` | with binds | JSON Schema declaring each bind (name + type) |
| `record` | with binds | the bind **values**, as templates |
| `objectSourceResourceName` | | `"oracledb_execute_sql_metadata"` — enables typed `rows` |
| `response_schema` | | column schema matching the SELECT |
| `performAsync`, `record_loader` | | |

**Outputs:** `rows[]`, `rowsCount`, `rowsAffected`.

⚠️ Bind traps (the most expensive gotchas found):
- `params` **and** `record` are both required; missing either → `ORA-17041: Missing IN or OUT parameter`.
- `record` templates must reference **this** workflow's START node id — copied nodes carry
  a foreign id that silently resolves to nothing.
- A `record` **missing one key binds NULL silently** — diff SQL `:binds` against `record` keys.
- **OUT binds (`o_*`) must not be in `record`.**
- 🔴 **PL/SQL OUT binds are never returned** — an anonymous block returns
  `{"rows":[],"rowsCount":0,"rowsAffected":0}`. Follow every write with a verification
  `SELECT` node and return that.

23 `oracledb` actions exist, incl. `oracledb_select_rows_using_custom_sql`,
`oracledb_insert_record`, `oracledb_update_rows`, `oracledb_upsert_row`,
`oracledb_delete_rows_in_batch`, `oracledb_execute_stored_procedure`,
`oracledb_list_schemas`, `oracledb_list_tables_from_schema`, and CDC triggers
`oracledb_on_new_event` / `_on_update_event` / `_on_delete_event`.

### HTTP — `custom_http_endpoint_execute`
✅ UAT · 2026-09-19

Needs **no connection**.

| Input | Notes |
|---|---|
| `baseUrl`, `path`, `httpMethod` | required in practice |
| `headersList`, `queryParamsList`, `pathParamsList` | arrays |
| `bodySchema`, `body_loader` | request body |
| `authType`, `connectionType` | |
| `requestTimeoutInSecs`, `sslVerify`, `enableProxy`, `httpVersion` | |
| `responseSchema`, `errorResponseSchemas` | |

**Outputs:** `status` (int), `result` (parsed body).
Variants: `_execute_graphql`, `_execute_soap`, `_execute_multipart`, `_execute_streaming`.

### Code — `code_by_unifyapps_groovy`
✅ UAT · 2026-09-19

```json
{ "input":  { "type":"object", "required":["km"], "properties": { "km": {"type":"string","title":"km"} } },
  "output": { "type":"object", "required":["recommendation"], "properties": { "recommendation": {"type":"string","title":"recommendation"} } },
  "code": "return [\"recommendation\": \"Service now - odometer at \" + km + \" km\"];",
  "parameters": { "km": "{{ n_in.outputs.mileage }}" },
  "compile_static": false, "captureStdOutput": false }
```
- `input` declares names; `parameters` binds values; code reads them as bare variables.
- **Outputs nest under `result`**: `{{ n_code.outputs.result.recommendation }}`.

⚠️ `code_by_unifyapps_javascript`: a top-level `return` is rejected with *"Script rejected by
sandbox validation: Line 1, column 1: Invalid return statement"*. Correct JS form unknown
(§19). Other code actions: `_python`, `_java`, `_csharp`, `_execute_code_snippets`,
`_bubblewrap` (sandbox), `_playwright`.

### Control flow

| resource | type | inputs | Status |
|---|---|---|---|
| `if_else` / `if_else_condition` | `IF_ELSE` | `operator`, `filters: [{property, filter:{operator, value}}]` | ✅ |
| `loop` / `loop_while` | `LOOP` | `condition: {operator, filters}`, `captureIterations` | ✅ |
| `break` / `break` | `BREAK` | `loop: "<loop node id>"` | ✅ |

- `IF_ELSE` wiring: `if` edge (`yes`) into the body; `next` edge (`no`) to the rejoin node;
  the body's last node also points at the rejoin node.
- `LOOP` wiring: `loop` edge in; `next` (`loopback`) from the body's last node back; `next` out.
  Outputs `{result, index}`, state `{iteration}`.
- `BREAK` **still needs an outgoing `next` edge** to the enclosing condition's rejoin node,
  or validation fails.

### Variables

| resource | inputs |
|---|---|
| `variable_by_unifyapps_create_variables` | flat map `{ "counter": "0" }` → `{{ n_v.outputs.counter }}` |
| `variable_by_unifyapps_update_variables` | `{ "variables": [ { "source": "{{ n_v.outputs.counter }}", "value": "=SUM({{ n_v.outputs.counter }},1)" } ] }` |

### MDM — `mdm_by_unifyapps` (context graph write/read)
✅ APS1 · 2026-09-19/20

All steps use the graph's UDM connection as `context.connectionId`.

| Action | Inputs | Outputs |
|---|---|---|
| `add_edge_to_graph` | `modelId` (graphId), `primaryEntityType`, `primaryEntityId`, `associatedEntityType`, `associatedEntityId`, `label`, `updateIfPresent` | `{success, fromNodeId, toNodeId}` |
| `execute_opencypher_query` | `modelId`, `query`, `limit` (1–1000, default 100), `offset`, `skipRBAC`, `outputSchema` | query rows |
| `execute_opencypher_update` | Cypher write | 📦 |
| `create_staging_records`, `apply_data_matching_rules`, `apply_data_quality_rules`, `find_by_sql` | MDM golden-record pipeline | 📦 |

Entity types are `unifiedEntityId`s; entity ids are primary-key values. ~60–70 edge nodes per
workflow run reliably in 25–40 s.

### Storage — `storage_by_unifyapps`
✅ APS1 · 2026-09-19

| Action | Inputs |
|---|---|
| `create_record` | `object_type: <ue>`, `record: {...}` — ⚠️ fields under **`record`**, not top level |
| `delete_records` | `object_type`, `numberOfRecordsToDelete: "SINGLE"`, `triggerInputCondition: {operator, filters}` |
| `fetch_records` | `object_type`, `triggerInputCondition` (👁) |

**Inside a workflow** ✅ UAT 2026-09-26 (Standup Board build, versions `fetch_records` 16421, `create_record` /
`update_record_by_id` 16420):
- **A `SINGLE` fetch returns the record itself at the top of `outputs`** — `{{ n.outputs.id }}`,
  `{{ n.outputs.properties.x }}` — **not** `objects[0]` as the output schema advertises. `objects[0]` templates
  resolve to nothing and are silently dropped. A `MULTIPLE` fetch returns `outputs.objects[]`.
- Filters use the **flat** spelling `properties_<field>`: `EQUAL`, `IN` (value is an array), `CONTAINS`, and
  `operator: "OR"` all verified. (App data sources use `properties.<field>` instead — see §23.)
- ⚠️ A filter leaf whose `value` template resolves to nothing is not "no match" — the run **fails** with
  `5004 Validation failed … No Value found in filter with field: properties.<x>`. Guard with an `IF_ELSE` first.
- `update_record_by_id` with `useRawPayload: true, upsert: true, rawPayload: {…}` creates or replaces by
  `recordId`. `upsert: false` replaces the whole properties map (send the full record).
- `create_record` with `useRawPayload: true, rawPayload: {…}` works; an integer Groovy output templated into an
  integer field stays an integer.
- `loop_for_each` (v214): `listSource: "{{ n_code.outputs.result.list }}"`, `repeatMode: "SINGLE"`; body group
  `{loopId}@g1@l`; edges `loop@loop@first`, `next@last@loop` (`name: "loopback"`), `next@loop@after`. A whole-object
  template `rawPayload: "{{ n_loop.outputs.item.payload }}"` passes the map through.

### ECG pipeline — `ecg_by_unifyapps`
📦 APS1 · 2026-09-20

`run_discovery`, `translate_raw_record`, `apply_enrichment`, `publish_record` — **all require a
published source config**, so they do not bypass the wizard.

### Connector specifics
✅ APS1 · 2026-09-20

- **HubSpot:** search operator `CONTAINS` is rejected → use `CONTAINS_TOKEN`. Always request
  `hs_object_id`. `hubspot_get_deal` supports `propertiesWithHistory: ["dealstage"]`. No
  "record updated" trigger — poll `hs_lastmodifieddate`.
- **Slack:** bot tokens read only joined channels; `token_type: "user_token"` reads what the
  user sees. `slack_list_conversation_history` = top-level only; replies need
  `slack_list_conversations_replies`. `slack_get_user_info_by_id` takes **`user`**;
  `slack_get_conversation` takes **`channelId`**; history takes **`channel`**.

---

## 17. Error catalogue

| Message (substring) | Where | Cause → fix |
|---|---|---|
| `Invalid username or password` (401) | login | bad creds, wrong IdP id, `firstLogin` set, or MFA |
| `app_not_configured_for_user` | Google SAML | account not in the SSO app → use a local account |
| `getNodes() is null` | create workflow | send `nodes` (a stub is fine) |
| `This automation has a trigger which expects response` | save violation | a path lacks a `STOP`; a `BREAK` lacks an outgoing edge |
| `forbidden datasource: not found` | `execute/node` | not a registered automation → use a workflow |
| `Script rejected by sandbox validation: Invalid return statement` | JS code node | use Groovy |
| `ORA-17041: Missing IN or OUT parameter at index` | Oracle node | `record` missing, or its templates reference a foreign START id |
| `ORA-01017` | Oracle connection | pointed at the CDB; EBS APPS is PDB-local |
| `Non Empty Validations ... required name` | saveAndDeploy | send the full entity; set `properties.name` |
| `Non Empty Validations ... add additionalProperties tags` | create entity | move `tags` to the top level |
| `E11000 duplicate key error` | `POST /api/entity` | you sent an existing id → use `/api/entity/update` |
| `ENTITY_TYPE with id save not found` | `/api/entity/save` | not an endpoint |
| `CONNECTION with id X not found` (5002) | connection | bad id |
| `Invalid group: STANDARD and type: e_topic_ai_agent` (5004) | aggregation | entities use `group: ENTITY` |
| `projections is null` | aggregation | `projections` mandatory for `ENTITY` |
| `version is required for node update` | ECG node update | version in the query string |
| `Please delete data before updating entity schema` | ECG node update | type changes need zero records |
| `No Value found in filter with field: sourceConnectionId` | create connection | don't hand-create the UDM connection |
| `The system lost track of your active connection session` | copilot | realtime channel broken — don't buffer the SSE stream; the in-app browser may block MQTT |
| `forbidden datasource : invalid input` | `execute/node` with an `id` | an input differs from the data source's stored value where it is not `{{templated}}`, or a stored input was omitted → send the full stored inputs, change only templated fields |
| `Non Empty Validations ... property X invalid; oneOf fail` | record create/update | value not in the field's `oneOf` |
| `Non Empty Validations ... required X` | record create/update | missing required field — updates replace the whole record, send all fields |
| `Non Empty Validations ... add additionalProperties X` | record create | field not in the object schema |
| `E11000 duplicate key ... CUSTOMER_ENTITY_<n>.<object>` | record create | primary-key value already used (record id = PK) |
| `Lookup type not supported: EntityType` (5004) | lookup | use `ENTITY_TYPE` |
| `e_component with id e_global_<app> not found` (5002) | embedded-entities | app has no global page yet — it is created with the first page |
| login 200 with `resetPassword: true`, then every `/api/*` → 204 empty | login | account flagged for password reset → user resets in a browser (§3) |
| `No Value found in filter with field: properties.x` (5004) | workflow storage step | a filter value template resolved to nothing → guard with IF_ELSE before the fetch |
| `No signature of method: java.util.Date.format()` | Groovy node | Groovy date extensions are not on the sandbox classpath → use `java.time` |
| `Search on e_data_source requires a properties.interfacePageId filter` (5011) | `POST /api/entity/e_data_source` | add `properties.interfacePageId` (e.g. `e_global_<appId>`) to the filter |
| HTML instead of JSON | any | session expired → re-login |

---

## 18. Discrepancies to resolve

Places where two sessions/tenants recorded conflicting facts. **Do not pick one silently** —
resolve by testing, then update both the entry and the affected skill.

### D1 — Reading node outputs
- **UAT (builder):** `POST /api/lookup?ByKeys=TEST_WORKFLOW_VARIABLE` ✅ returns node
  inputs/outputs — used successfully in dozens of runs.
- **APS1 (context-graph):** *"There is no supported get-node-outputs API that worked"* — a
  debug node writing to storage was used instead.
- **To resolve:** try `TEST_WORKFLOW_VARIABLE` on APS1 with the exact UAT body (§6),
  including `options.startTime/endTime/workflowId`. If it works, retire the debug-node pattern.

### D2 — `fallbackMode: CONTINUE`
- **Builder skill** says `CONTINUE` *"ignores the failure and carries on"* — ⚠️ this was
  **inferred, never tested**. Every verified UAT run using `CONTINUE` succeeded, so the
  failure path was never exercised.
- **APS1 (context-graph):** observed that *"`fallbackMode: CONTINUE` does not continue — one
  failed node fails the run."* This is the only direct evidence.
- **Current best knowledge:** assume `CONTINUE` does **not** continue. Use `MANUAL` + an
  `error` edge for failure handling (✅ verified).
- **To resolve:** a two-node workflow on UAT with a deliberately failing `CONTINUE` node,
  then check `STATUS` and whether the next node ran.

### D3 — Run-status filter field
- **UAT:** `filter: {"op":"IN","field":"ID","values":[runId]}` ✅
- **APS1:** `filter: {"op":"AND","values":[{"field":"fields.id","op":"EQUAL","values":[runId]}]}` ✅,
  with projection `RUN_ID`.
- Possibly both work on both. **To resolve:** try each form on the other tenant.

---

### D4 — Does the code builder set app privacy from the brief?
- **0.3.2 (app-282f2c90f0fd):** a brief asking for login produced `security.type: PRIVATE`.
- **UAT 2026-09-26 (app-7e15a9fb98dd):** a brief saying "Require sign-in (private app)" produced login pages in
  the code but **no `security.type`** on the entity (only `cspData`).
- **Current best knowledge:** not reliable — read `security.type` back after the build and ask the builder agent
  explicitly if it is missing.

## 19. Open questions / backlog

Ordered roughly by value to the "build agents and workflows in bulk" goal.

| # | Question | Notes |
|---|---|---|
| 1 | ~~Invoke a deployed CALLABLE workflow from outside~~ | ✅ 2026-09-21: register an `e_data_source` and call `execute/node` with its `id` (§22). API Manager endpoints (docs) are the external route — untested |
| 2 | **Converse with an agent over API** | start a session, send a message, read the reply |
| 3 | **Dynamic-schema connectors** | `input.dynamic: true` actions (Salesforce objects, picklists) — what extra lookup runs? |
| 4 | ~~Create a connection~~ | ✅ 2026-09-21: `POST /api/connection/input?appName=` (§7). OAuth still needs the user |
| 5 | **Correct JavaScript code-node form** | top-level `return` rejected |
| 6 | Resolve D1–D3 (§18) | cheap, high value |
| 7 | **Webhook trigger** end to end | `/api/workflow-builder/webhook-trigger-url` |
| 8 | **OAuth token endpoint** | authorize/consent routes exist; no token endpoint found |
| 9 | **MFA login step** | `/mfa-verification` |
| 10 | Workflow **delete / clone** | 📦 only |
| 11 | Observability **request bodies** | currently captured from UI traffic |
| 12 | ECG **Map step via API** | 405 everywhere; capture the wizard's real payload once |
| 13 | ECG `associatedEdgeMappings` shape | every live source had it empty |
| 14 | What enables built-in `search_knowledge_graph` | `graphModelId` + `defaultTools` insufficient |
| 15 | Knowledge / RAG, guardrails, multi-agent teams, channel deployments | entity types known, payloads not |
| 16 | `/api/user-context` full response | only `customer.id` recorded |
| 17 | `/api/global-search` request shape | returns empty |
| 18 | ~~Does a commit pushed to GitHub flow back?~~ | ✅ 2026-09-21 — branches and merged `main` both pulled |
| 19 | Code-builder chat-send request | not on page fetch/XHR/WS hooks; use `POST /agent-api/sessions` with `appId` (📦) instead. Publish ✅ `{versionTag, versionNote}`. Code-app privacy: Settings → Privacy refuses (`RefusalError … is a code-builder app`); ask the agent ✅ |
| 20 | Delete an object / record over REST | records: `DELETE` 405; object delete not yet tried |
| 21 | Config-app event action that triggers a data source | `navigateToPage` / `showNotification` captured; run-data-source action not |
| 22 | Change Sets (Move/Export between environments) API | docs describe it; not captured |

---

## 20. UI routes

Useful for eyeballing what the API built.

| Route | Screen |
|---|---|
| `/p/0/automations` | automation list |
| `/p/0/automations/ai-create` | prompt-to-automation |
| `/p/0/automations/{id}/builder` | builder canvas |
| `/p/0/automations/{id}/test` · `/test/{runId}` | test runs |
| `/p/0/ai-agents/custom` | agent list |
| `/p/0/ai-agents/{id}/configuration/instructions` | system prompt |
| `/p/0/ai-agents/{id}/configuration/topics` | **Tasks** (label ≠ path) |
| `/p/0/ai-agents/{id}/configuration/actions` | **Tools** |
| `/p/0/ai-agents/{id}/configuration/tasks` | **Prerequisite Actions** |
| `/p/0/ai-agents/{id}/configuration/capabilities` | capabilities |
| `/p/0/ai-agents/{id}/configuration/{knowledge,skills,memory,ai-models}` | |
| `/p/0/ai-agents/{id}/configuration/{sensitive-information,hallucinations,content-filter,word-filter,denied-topics,blocked-messaging}` | guardrails |
| `/p/0/ai-agents/{id}/deployments` · `/observability` | channels · traces |
| `/p/0/context-graphs` · `/{graphId}?tab=nodes\|edges\|sources\|records` | context graphs |
| `/p/0/objects/custom` · `/p/0/objects/{objectId}/records` · `/schema` · `/activity` · `/settings` | Objects Manager |
| `/p/0/connections/all` · `/p/0/connections/create/{appName}` | Connections Manager |
| `/p/0/interfaces` · `/p/0/interfaces/{appId}/overview` · `/builder/{pageSlug}` · `/settings/users` | Applications |
| `/p/0/interfaces/code-builder/{appId}?sessionId={s}` | Code Builder |
| `/p/0/interfaces/custom-components` · `/template-components` · `/p/0/design-system` | app assets |
| `/p/0/solutions` | AI Solutions (groups assets per use case) |
| `/p/0/agent-governance/*` | governance, model registry, monitoring |
| `/settings/users` · `/settings/users/create/details` | user admin |

---

## 21. Changelog

| Version | Date | Change |
|---|---|---|
| 0.4.5 | 2026-09-29 | §3: find a tenant's local IdP id from the `/login` page (`type: PASSWORD`); `/auth/identity-providers` is public but untyped. |
| 0.4.4 | 2026-09-26 | Forced-password-reset login behaviour (§3, §17); in-workflow storage contract — SINGLE fetch returns the record at top level, flat filter spelling, empty-filter-value failure, upsert, `loop_for_each` (§16); Groovy has no `Date.format` (§17); builder `/retry`, push-on-link, local-branch pickup, all five storage data sources + delete verified (§23); agent chat body verified (§25); D4 privacy-from-brief. Built Standup Board on UAT. Header version corrected (was 0.3.2). |
| 0.4.3 | 2026-09-21 | Agent chat over REST (send via SSE, read conversation, trace timeline + span I/O); generate-chart silent-end defect; HubSpot search/owners/pipelines output quirks. |
| 0.4.2 | 2026-09-21 | Agent skills (`e_skill_ai_agent`, `accessibleTo` link, attach over REST, draft-publish side effect); agent clone via console; copying connector tools between agents. |
| 0.4.1 | 2026-09-21 | §25 Connectors SDK: create/auth/action/request endpoints, `{{ rawPayload.x }}` templates, create-vs-update request paths, publish → node resources. Verified by building `SC Native - Fireflies` on UAT. Agents: console *⋯ → Clone* duplicates an agent **with its skills and knowledge** (used for SC Copilot v2 `e_6ab1375cf843281fda63184d`). |
| 0.4.0 | 2026-09-21 | ✅ LLM step in a workflow: `conv_ai_by_unifyapps_call_llm_model_with_options` must be node type `CALL_INTERFACE_WORKFLOW` (as `ACTION` → *No config found for resource … ConnectionService remote call failure*); inputs via callable interface `__ua__call_ai_agent_llm_model`; `initiate-test` cancels at ~26 s, execute via data source instead. ✅ API-created code app lacks `e_global_<appId>` → data source create fails `5011 Parent e_component … not found`; create the page first. Fine-grained-PAT Git link leaves `linked:false`. Details: `unifyapps-builder/references/workflows.md`, `unifyapps-apps/references/code-apps.md`. |
| 0.3.2 | 2026-09-21 | API-only code app `app-282f2c90f0fd` confirmed: listed in Applications, built, private per brief, renders live object data. |
| 0.3.1 | 2026-09-21 | Code app published over `POST /agent-api/apps/{id}/publish` ✅; privacy via builder agent; merge-to-main pickup ✅. |
| 0.3.0 | 2026-09-21 | §23: code app created over the API, file edits, Git link captured and two-way sync verified on our own app/repo; token trap; org-only is a feature flag. Colleague app references removed. |
| 0.2.0 | 2026-09-21 | Added §22 config apps, §23 code apps + `/agent-api` + Git, §24 Objects Manager; §7 connection create/test/auth-spec and server-side search (aggregation); new dead ends and errors; backlog #1 and #4 closed, #18–22 opened. ✅ items verified on UAT by building scratch objects `maher_scratch_task`, connection `6ab0ea7a5459f4370f0c1f3f`, app `maher-scratch-cfg`, data source `e_6ab0ebe6f843281fda5f6032`. |
| 0.1.0 | 2026-09-21 | Initial consolidation of everything discovered 2026-09-19/20 across the `unifyapps-builder` (UAT) and `unifyapps-context-graph` (APS1) work: 126 endpoint paths with evidence levels, node action contracts, error catalogue, dead ends, and three cross-tenant discrepancies (§18). |

---

## 22. Applications — config-based

Module id `e_interface` (*Applications*). An app is an `e_interface` entity whose id is a slug;
its pages/modules are `e_component` entities; every data call is an `e_data_source` entity.
`properties.manifest = {type:"WEB", mode:"config"|"code"}` — `mode` distinguishes the two
builders (older config apps omit it). 9,416 apps on UAT. Full field-level reference:
`unifyapps-apps/references/config-apps.md`.

### `POST /api/entity/create-update-or-delete/hierarchical` — Create / update app, page, module
✅ UAT · 2026-09-21

| Field | Notes |
|---|---|
| `entity` | the full entity (`entityType` `e_interface` or `e_component`) |
| `requestType` | `CREATED` \| `UPDATED` (\| `DELETED` presumably — untested) |
| `ignoreVersion` | `true` on app create |
| `parentEntities` | `[{type:"e_interface", id:<appId>}]` for pages |
| `postUpdateEntities` | the app entity with its maps updated (UI sends it; `NEW_ENTITY_ID` placeholder for the new page id) |

**Response** — 200, an **array** of saved entities. Creating the first page also creates the
global page `e_global_<appId>` (name/slug `global-page-of-<appId>`), which anchors app-wide
data sources. ✅ App create (UI) · ✅ page update (REST) · 👁 page create (UI).

### `POST /api/domain-mapping/interface` — Map the app's host
✅ UAT · 2026-09-21 — `{domain:"<appId>-orbit.matrix-uat.unifyapps.com", module:"INTERFACE", applicationId}` → 204.
Read back with `POST /api/lookup?ByQuery=DOMAIN_MAPPING` `{options:{applicationId}}`.

### `POST /api/entity/e_component` — List an app's pages/modules
✅ UAT · 2026-09-21 — filter `properties.interfaceId` EQUAL appId, optionally
`properties.componentType` EQUAL `PAGE` / IN `[MODULE, TEMPLATE_COMPONENTS]`. The global page
is returned as a `PAGE`.

### `POST /api/entity/embedded-entities/e_component` — A page with its data sources
✅ UAT · 2026-09-21 — `{entityId, allowedEntityTypes:["e_component","e_data_source","e_interface"]}`.
Deployed variant: `/api/entity/deployed/embedded-entities/e_component` (+ `excludeFields`), types `e_component_deployed`.

### `e_data_source` — create with `POST /api/entity`, run with `execute/node`
✅ UAT · 2026-09-21

```json
{ "entityType": "e_data_source", "properties": {
  "name": "ds_vehicle_telemetry", "type": "APPLICATION",
  "interfaceId": "<appId>", "interfacePageId": "e_global_<appId>",
  "context": {"appName":"callables","resourceName":"callables_call_automation","resourceVersion":3124},
  "inputs": {"automationId":"<deployed CALLABLE id>","version":"-1","runtimeConnections":{},
             "parameters":{"vehicleId":"{{vehicleId}}"},"synchronous":true},
  "dP": [{"p":"inputs.parameters.vehicleId"}], "dpOn": [],
  "advancedOptions": {"runBehaviour":"automatic","refetchOnWindowFocus":true,
                      "timing":{"runQueryOnPageLoad":false,"runQueryPeriodically":false}} } }
```

```json
POST /api/workflow/execute/node?name=ds_vehicle_telemetry&requestId=<dsId>
{ "context": {...same...}, "id": "<dsId>",
  "inputs": {"automationId":"...","version":"-1","runtimeConnections":{},
             "parameters":{"__internals__":{"m":"PREVIEW","s":"global-page-of-<appId>","c":"PLATFORM","p":"browser"},"vehicleId":"V-100"},
             "synchronous":true},
  "options": {} }
→ 200 { "executionInstanceId", "id", "lookupReferences": {}, "response": <STOP result> }
```

**Governance (✅ verified):** no `id` → `forbidden datasource: not found`; a changed
non-templated input (e.g. `automationId`) or an omitted stored input →
`forbidden datasource : invalid input`. `context` may be any workflow action — storage
(`storage_by_unifyapps_fetch_records`, `_create_record`, `_update_record_by_id`,
`_delete_record_by_id`) is common. Blocks bind with `{{ <dsId>['data'][...] }}`.

### `POST /api/entity/e_interface/{appId}/deploy` — Publish
✅ UAT · 2026-09-21 (captured from the UI's Publish click) — `{deploymentNotes}` → the app with
`deploymentState {deployedAt, deployedBy, deploymentNotes, entityVersion, version}`. The UI
first calls `POST /api/entity/entity-dependency` and `/api/entity/deployed/entity-dependency`
`{entityType:"e_interface", entityId}` 👁. Versions: `aggregation` on `EntitySnapshot` (STANDARD)
with `additional:{entityType, entityId}` 👁.

### Other app endpoints
👁 `GET /api/entity/e_theme/{id}` · `POST /api/entity/e_theme/find-by-ids {ids}` ·
`POST /api/entity/e_page_template` · `POST /api/entity/e_custom_component` ·
`POST /api/entity/e_i18n_namespace {interfaceIds, locale}` · `GET /api/collab/connectionDetails` ·
`POST /api/workflow/execute/node?name=NoCodePageScore` (page quality score, automation
`68fcad84dede0b5c299e1cc8`) · `GET /api/entity-type/getLoggedInUser` (the `s_user` schema).

---

## 23. Applications — code-based & the agent API

A code app is an `e_interface` with `manifest.mode: "code"`; its source is a Git working tree
behind the **Code Builder agent API** at `/agent-api` (same origin, cookie auth). Written by the
platform agent `text_to_ui_tensor`. Hosted at `<appId>-orbit.tensor-uat.unifyapps.com`. Stack:
React 19, Vite 8, TypeScript 7 rc, Tailwind 4, TanStack Query 5, `@unifyapps/app-builder-sdk`
0.4 (vendored). Full reference: `unifyapps-apps/references/code-apps.md`.

**Runtime contract** (✅ via the same endpoint on a config app; 👁 in code-app source): app code
calls `useExecuteWorkflowNode` / `useExecuteWorkflowNodeMutation` from
`@unifyapps/app-builder-sdk/hooks/workflow` → `POST /api/workflow/execute/node` with an
`e_data_source` id, anchored `interfacePageId: "e_global_<appId>"`. Objects use five
object-agnostic storage bindings (FETCH, FETCH_ONE, CREATE, UPDATE, DELETE); each automation
gets its own `callables_call_automation` data source. App code must never call `/api/entity`
or `/api/aggregation`.

| Method · path (prefix `/agent-api`) | Purpose | Status |
|---|---|---|
| `POST /sessions` `{target:"code-builder", input, userName, userEmail, appId?, branch?, planner?}` | new app or new chat → `{appId, sessionId}` | ✅ |
| `GET /sessions/{s}/files` | `{files:[{path,size}]}` | ✅ |
| `GET /sessions/{s}/files/content?path=&v=` | raw text | ✅ |
| `PUT /sessions/{s}/files/contents` `{edits:[{path,content}]}` | save files (no commit) → `{filesVersion}` | ✅ |
| `POST /sessions/{s}/files/{op}` | file op | 📦 |
| `GET /sessions/{s}/branches` | `{current, default, linked, remoteError, branches[], previewVersion, filesVersion}` | ✅ |
| `POST /sessions/{s}/branches` `{branch, base, description}` · `POST /sessions/{s}/branch` `{branch}` · `DELETE /sessions/{s}/branches/{b}` | create / switch / delete (remote too) | 📦 |
| `GET` · `POST /sessions/{s}/git` | link status · link repo | 📦 |
| `GET /sessions/{s}/changes` · `POST /sessions/{s}/restore {sha}` | diff · restore | 📦 |
| `POST /sessions/{s}/edits` · `/styles {file,loc,styles}` · `/bindings/seed {id,seed}` | visual edits | 📦 |
| `GET /sessions/{s}/manifest` · `/routes` · `/data-model` · `/query-plan` · `/download` | metadata / zip | 📦 |
| `POST /sessions/{s}/events?since=` · `/stop` · `/retry` · `/queue/…` | agent control | 👁/📦 |
| `POST /apps/{appId}/publish` `{versionTag, versionNote}` | publish (default branch only) → entity `deploymentState.additionalDetails.sourceCommitHash` | ✅ |
| `GET /apps/{appId}/deployed/routes` · `/apps/{appId}/branches/{b}/files/content` · `/branches/{b}/manifest` | read without a session | 📦 |
| `GET /preview/b/{appId}/{branch}` | branch preview | 👁 (404 while not built) |

**Git link body** 📦: `{provider:"GITHUB"|"GITLAB", connectionId, repositoryName, projectName,
organizationName, createOptions:{autoCreate:true, payload:{visibility:"private", description}}}`.
✅ **Verified two-way 2026-09-21** on `app-3dfc7c54e504` ↔ `mmaheranwar/maher-scratch-code-app`: agent commits push with identical SHAs; a branch pushed from outside appears in `GET /agent-api/apps/{appId}/branches` and `POST /agent-api/sessions/{s}/branch {branch}` pulls it into the builder. Personal owner id format: `organizationName: "username:<login>"` (owners from `lookup?ByQuery=APPROVED_GITHUB_ORG`). A fine-grained PAT limited to selected repos creates the repo but fails the push (`sync.detail: push failed`, `remoteError: could not reach the remote repository`) — add the repo to the token; the push retries on the next commit. **Create a code app over the API** ✅: `POST /agent-api/sessions {target:"code-builder", input, userName, userEmail}` → `{appId, sessionId}`, then create the `e_interface` (`manifest.mode:"code"`, `chatSessionId`) and `POST /api/domain-mapping/interface` yourself — the session does not create the entity. Always creates a **new private** repo. Personal account vs organization is governed by the
tenant feature flag *Code app repositories under organizations only* (`/settings/feature-flags`)
— **off on UAT 2026-09-21, so personal accounts are allowed**; when on, the UI shows "No
organization available … personal accounts aren't supported". Sync: push on save ("Code will sync with the first saved change");
Branches view shows check status, *Behind | Ahead*, pull requests. Pull-back from the remote is
**unverified** (§19 #18).

**Builder chat** 👁: `POST /api/workflow/execute/node?name=call_automation` → automation
`66ab98083d73300e63962287` (`copilotType:"AI_AGENT"`, `caseId`); sessions/locks via automation
`6a7c42a1eddf8930c2ffe6af` (`fetchType: SESSION_HISTORY | QUEUE_AND_LOCK_STATUS`, `appId`,
`branchKey`). Entities `tensor_agent_queue_entry`, `session_task_tracker`, `text_to_ui_code_models`.

---

**Findings from Standup Board** (`app-7e15a9fb98dd`) ✅ UAT 2026-09-26:
- `POST /agent-api/sessions/{s}/retry` with `{}` → `{"ok": true}` recovers a builder session whose first turn
  errored (`enginePayload.status: "error"`, `recoverable: true`, 1 LLM call, 0 tokens); it finished ~80 s later.
- `GET /agent-api/sessions/{s}/branches` ✅, `GET /agent-api/sessions/{s}/changes` ✅, `GET /agent-api/sessions/{s}/git` ✅.
- **Linking Git pushes the existing working tree immediately** when the connection's token can push: `sync.state`
  went `syncing` → `synced` within seconds and GitHub had the builder's commit, so no "commit the working tree"
  instruction was needed. The GitHub SHA (`25cf495`) differed from the SHA `/changes` listed before the link
  (`6d63595`) — same message and tree; treat SHAs as re-written by the push.
- A branch pushed from a local clone appears in `GET /agent-api/apps/{appId}/branches` (`base: "main"`) ✅.
- Five storage data sources + one `callables_call_automation` data source per workflow, created with
  `POST /api/entity` against a self-created `e_global_<appId>`, all executed ✅. `FETCH_ONE` responds with the
  record itself (not `objects`). `storage_by_unifyapps_delete_record_by_id` (v16345) via data source →
  `{"success": {"t1": true, "t2": false}}` and the record is gone (404). Optional workflow parameters must still
  be sent (as `""`); an empty string for a `number` input reaches Groovy as unbound.

## 24. Objects Manager

Module id `ENTITY_TYPE`. An object is an `EntityType` (STANDARD); its records are entities of
that type. ~18,300 custom objects on UAT. Full reference:
`unifyapps-apps/references/objects-and-connections.md`.

### `POST /api/entity-type` — Create object
✅ UAT · 2026-09-21 — `{id, name, pluralName, description, metadata:{storeDetails:{store:"MONGO"}}, tags}`
→ the EntityType with defaulted `metadata`. UI store options: JSON (MONGO), Blob, Key Value,
Event, Vector, Analytics.

### `GET /api/entity-type?entityType={id}` — Read object
✅ UAT · 2026-09-21. Bulk: `POST /api/lookup?ByKeys=ENTITY_TYPE {type:"ByKeys", lookupType:"ENTITY_TYPE", keys}` ✅.

### `POST /api/entity-type/update` — Update schema / settings
✅ UAT · 2026-09-21 — send the **full** object as read, with
`input: {type:"SCHEMA_AND_LAYOUT", schema:<S>, layout:{"ui:order":[...]}}` and
`schema: {dynamic:false, type:"SCHEMA", schema:<S>}`. `<S>` is JSON Schema; per-field flags
`primaryKey, uniqueKey, nameField, searchable, sortable, filterable`; formats `text, email,
date-time (+dateFormat:"epoch"), single-select (+oneOf | foreignKey:{reference:"ENTITY_ID:<obj>"}),
auto-generate (+autoGeneratedFieldDefinition:{prefix,startFrom})`. The server derives
`metadata.primaryKeyField / nameField / filterableFields / searchableFields / dateFields /
referenceKeys / autoGeneratedFields` from the flags. `version` increments.

### Records
✅ UAT · 2026-09-21 — create `POST /api/entity {entityType:<obj>, properties}` (record id = PK
value); read `GET /api/entity/{obj}/{id}`; list `POST /api/entity/{obj}` with
`{filter:{op,field:"properties.x",values}, sorts, page}` (EQUAL, GT, IN verified); aggregate
`POST /api/aggregation?entityType={obj}&group=ENTITY` (fields `properties_x`); update
`POST /api/entity/update` with the **full** properties (partial → `required` error). Schema
validation enforces `required`, `oneOf`, `additionalProperties:false`.

### Listing objects
✅ `POST /api/aggregation?entityType=EntityType&group=STANDARD` with projections
`name, id, columns, tags, oUId, cTm, mTm, description, packaged, standard`; custom objects:
filter `standard` EQUAL false OR MISSING. Fields of one object:
`POST /api/lookup?ByQuery=ENTITY_FIELD {options:{group:"ENTITY", entityType}}` ✅.

---

## 25. Connectors SDK (custom connectors)
✅ UAT · 2026-09-21 — built `SC Native - Fireflies` (`6ab1385f5459f4370f0d1499`, 5 GraphQL actions, published).
UI route: **`/connectors/custom`** (sidebar *Enterprise Systems → Connectors SDK*), connector at
`/connectors/{defId}/{authentications|triggers|actions|settings}`. Aggregation entity type: `ConnectorDefinition` (group `STANDARD`).

| Step | Call | |
|---|---|---|
| Create connector | `POST /api/connector-builder/definition/basic` `{name, description, baseUrl, logo, categories}` | 👁 (UI) |
| Read connector | `GET /api/connector-builder/definition/{defId}` → `{auths[], baseUrl, enabled, version, …}` (no tags field) | ✅ |
| Add auth | `POST /api/connector-builder/definition/{defId}/auth?type=TOKEN` (`TOKEN`, `JWT`, `OAUTH`, `OAUTH1`, `BASIC`, `CUSTOM`, `AWS`) | 👁 (UI) |
| Update auth input schema | `POST /api/connector-builder/definition/update/{defId}/auth?type=TOKEN` | 👁 (UI) |
| Auth request (headers) | read `GET /api/connector-builder/request/{defId}/{TYPE}/auth` · update `POST /api/connector-builder/request/update/{defId}/{TYPE}/auth?version={v}` with the full object | ✅ |
| Create action | `POST /api/connector-builder/definition/{defId}` `{name, description, type:"ACTION"}` → `{definition:{id…}, violations}` | ✅ |
| Action definition | read `GET /api/connector-builder/definition/{defId}/{actionId}` · update `POST /api/connector-builder/definition/{defId}/update/{actionId}?version={v}` (full object; set `enabled:true`, `input`/`output` `{type:"SCHEMA_AND_LAYOUT",dynamic:false,layout:{},schema}`) | ✅ |
| Action HTTP request | read `GET /api/connector-builder/request/{defId}/{actionId}/action` (`""` until first save) · **create** `POST` same path · **update** `POST /api/connector-builder/request/{defId}/update/{actionId}/action?version={v}` | ✅ |
| Publish | UI *Publish* button; then the connector's `enabled:true` and actions appear in `GET /api/workflow-builder/node/{defId}/resources` as `{defId}:{actionId}` | ✅ |

- **Templates:** connection inputs and action inputs are both `{{ rawPayload.<field> }}` (scan of 486
  connectors: TOKEN/CUSTOM/BASIC all use `rawPayload.*`; CUSTOM auth outputs use `{{ auth.<field> }}`).
  Auth header for a personal API key: auth input schema `{properties:{api_key:{type:"string",format:"password"}},required:["api_key"]}`
  + `actionAuthHeaders:{"Authorization":"Bearer {{ rawPayload.api_key }}"}`.
- **Action request shape:** `{type:"ACTION", method, url, headers, queryParams, body:{type:"JSON", formEncode:false, payload:{…}}, sslVerify, enableRetry}`.
  Templates may sit inside a larger string (e.g. a GraphQL query `transcripts(limit: {{rawPayload.limit}})`).
- ⛔ `POST …/request/{defId}/{actionId}/action` on an action that already has a request → 500 Mongo `E11000 duplicate key`; use the `/update/` path.
  ⛔ `PUT`/`PATCH` on that path → 405. `/request/update/{defId}/{actionId}/action` → 404 (the `update` segment goes **after** `{defId}` for actions, **before** it for auth).
- UI gotcha: the Value field of the auth header editor is a template editor; synthetic typing leaves React state at `Bearer {{` — set it over the API instead.

### Agent skills — `e_skill_ai_agent`
✅ UAT · 2026-09-21 — link lives on the skill: `properties.accessibleTo: ["ai_agent/<id>"]`. Attach = update
`accessibleTo` + `saveAndDeploy` the skill + republish the agent. Find an agent's skills with aggregation
`group=ENTITY`, filter `properties_accessibleTo IN ["ai_agent/<id>"]`. ⚠️ deploying a skill also publishes any
unpublished draft (`version` > `deploymentState.entityVersion`). Details: `unifyapps-builder/references/agents.md`.

### Agent conversation over REST
✅ UAT · 2026-09-21 — send: `POST /api/workflow/execute/node/sse` (`callables_call_automation_streaming`,
automation `67dcfe388445037d9b0662c0`, params `{copilotType:"AI_AGENT_TEST", message, messageContentType:"MARKDOWN", aiAgentId, timezoneId}`);
read: `…?name=call_automation&fetchConversation=66ab98083d73300e63962287` (params `{copilotType, caseId, userId, aiAgentId, until}`);
traces: `GetTraceTimeline` (automation `680cdbcaa3741471fc7c22e9`, `{traceId}`) and `TraceTimelineDetails`
(automation `6943f1be474ba4398bf4201c`, `{id, type}`). Full bodies: `unifyapps-builder/references/agents.md`.
⚠️ `loadSkill(generate-chart)` silently ends the turn on UAT (no further LLM span).

**Verified request body** ✅ UAT 2026-09-26 (Standup Summariser `e_6ab80ca405e65b5f9282fd45`):
```json
POST /api/workflow/execute/node/sse?name=callables_call_automation_streaming   (Accept: text/event-stream)
{ "id": "callables_call_automation_streaming",
  "context": { "appName": "callables", "resourceName": "callables_call_automation_streaming" },
  "inputs": { "automationId": "67dcfe388445037d9b0662c0", "version": "-1", "runtimeConnections": {}, "synchronous": true,
              "parameters": { "copilotType": "AI_AGENT_TEST", "message": "<user message>", "messageContentType": "MARKDOWN",
                              "aiAgentId": "<agent id>", "timezoneId": "Europe/London" } },
  "options": {} }
```
The stream is `event:message` / `data:{…}` lines; `response.result.delta.data` carries `Fan` (user) and `Bot`
messages (`additional.internalMessageType: "THOUGHT"` for task-selection notes), the final answer as a
`Typography` block (`data.type: "MARKDOWN"`), then `responseGenerationStatus: "completed"` and `{"completed": true}`.
Read it line by line without buffering the whole stream. Publishing an agent bumps its entity version several
times (6 → 12, deployed `entityVersion` 7); verify with `GET /api/entity/deployed/ai_agent/{id}` ✅.

### HubSpot search notes
✅ UAT · 2026-09-21 — `hubspot_search_records_batch` operators: EQ NEQ LT LTE GT GTE CONTAINS NOT_CONTAINS
HAS_PROPERTY NOT_HAS_PROPERTY BETWEEN IN NOT_IN (no CONTAINS_TOKEN); multi-owner field
`hs_all_collaborator_owner_ids` **IN [ownerId]** matches deals where the owner is one of several collaborators.
`hubspot_get_owners` returns `results[]` (schema says `owners`) incl. `teams[]`. `hubspot_get_pipelines`
returns `metadata.isClosed` as the **string** "true"/"false". `hubspot_get_association_batch` → `results[{from:{id}, to:[{toObjectId}]}]`.
