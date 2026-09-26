---
name: unifyapps-apps
description: Build and change UnifyApps Applications — config-based (no-code pages, blocks, data sources) and code-based (React/Vite code apps with Git/GitHub branches) — plus Data Objects in the Objects Manager and Connections in the Connections Manager, all over the platform REST API. Use whenever the user wants to create or edit a UnifyApps app/interface/page, wire an app to an automation or object, work on a code app's source (including from a linked GitHub repo), create or change an object schema or records, or create/test/find a connection.
metadata:
  author: Maher
---

# UnifyApps apps, objects and connections

> **Created by Maher.** Contains no credentials. Each user signs in with their own UnifyApps
> account — read `references/connect-and-call.md` first (tenant, sign-in, finding connections,
> API conventions). Never ask for a password.

Everything here was captured from the live UI's own traffic and then **re-executed over plain
REST** on `orbit.uat.unifyapps.com` on 2026-09-21 unless marked otherwise. Evidence marks:
✅ verified · 👁 observed in UI traffic, not re-executed · 📦 seen only in the JS bundle.

Sister skills: `unifyapps-builder` (workflows + agents), `unifyapps-context-graph` (ECG).
Master API record: `API-SPEC.md` at the root of the `unifyapps-helper` repo these skills ship
from (optional — carry on without it if you only have the skill).

## The one idea to hold on to

**An app never calls an automation or an object directly. It executes a registered
`e_data_source`.** Config apps and code apps both do this, through the same endpoint:

```
POST /api/workflow/execute/node?name=<dsName>&requestId=<dsId>
{ "context": {appName, resourceName, resourceVersion},   // must match the data source
  "id": "<dsId>",                                         // the e_data_source id
  "inputs": { ...the data source's stored inputs, with only {{templated}} fields changed } }
```

- No data source → `500 forbidden datasource: not found`.
- Any non-templated input differs (e.g. a different `automationId`), or a stored input is
  omitted → `500 forbidden datasource : invalid input`.
- A data source is an ordinary entity — **you can create it yourself with `POST /api/entity`**
  (✅). This is what the platform's own code agent does with its `create_datasource` /
  `provision_data_sources` tools, and it is how you let a hand-written (or GitHub-edited) code
  app call a new automation.

## Module map

| UI module | Route | Stored as | Reference |
|---|---|---|---|
| Applications (config) | `/p/0/interfaces/{appId}/builder/{slug}` | `e_interface` + `e_component` pages + `e_data_source` | `references/config-apps.md` |
| Applications (code) | `/p/0/interfaces/code-builder/{appId}?sessionId=` | `e_interface` (`manifest.mode:"code"`) + files behind `/agent-api` | `references/code-apps.md` |
| Objects Manager | `/p/0/objects/{objectId}/records` · `/schema` | `EntityType` (group `STANDARD`); records are entities of that type | `references/objects-and-connections.md` |
| Connections Manager | `/p/0/connections/all` · `/create/{appName}` | `Connection` (group `STANDARD`) | `references/objects-and-connections.md` |

User-context module ids: Applications `e_interface`, Objects Manager `ENTITY_TYPE`,
Connections Manager `CONNECTION`, Code Functions `e_code_snippet`, Connector SDK
`CONNECTOR_DEFINITION`.

## Config vs code — which one

| | Config app | Code app |
|---|---|---|
| Created by | *New Application → Create Manually*, or prompt with **Config** | prompt with **Code** (the platform agent `text_to_ui_tensor` writes it) |
| Source of truth | page JSON (`e_component.properties.blocks`) | a Git repo of React 19 + Vite + TS + Tailwind 4 + TanStack Query |
| Claude edits it by | `POST /api/entity/create-update-or-delete/hierarchical` | editing files — via GitHub (linked repo) or `PUT /agent-api/sessions/{s}/files/contents` |
| Talks to the platform via | `e_data_source` entities bound in blocks with `{{ dsId['data'][...] }}` | the same `e_data_source` entities, called with `@unifyapps/app-builder-sdk/hooks/workflow` |
| Published by | `POST /api/entity/e_interface/{appId}/deploy` ✅ | `POST /agent-api/apps/{appId}/publish {versionTag, versionNote}` ✅ (default branch only) |
| Hosted at | `https://{appId}-orbit.matrix-uat.unifyapps.com` | `https://{appId}-orbit.tensor-uat.unifyapps.com` |

## Code apps + GitHub — what is and isn't established

- ✅ A code app is a real repo: `.agents/` (the platform agent's own skills + rules),
  `.githooks/pre-push`, `app/` (Vite project), `PLAN.md`, `PRODUCT.md`, `theme.json`.
  **Read `.agents/skills/*/SKILL.md` in the repo before changing app code** — they are the
  platform's own verified contracts (object-data, automation-integration, backend-integration,
  workflow-authoring, authentication, roles-and-permissions, copilot, …).
- ✅ **Create a code app over the API:** `POST /agent-api/sessions {target:"code-builder", input:<brief>, userName, userEmail}`
  → `{appId, sessionId}`, **then create the `e_interface` entity and the domain mapping yourself**
  (the session does not). Recipe in `references/code-apps.md`.
- ✅ **Link GitHub over the API:** `POST /agent-api/sessions/{s}/git` with `organizationName:"username:<login>"`
  (personal) or the org; owners from `lookup?ByQuery=APPROVED_GITHUB_ORG`. Creates a new private
  repo. Personal accounts allowed unless the tenant flag "Code app repositories under
  organizations only" is on (off on UAT). The connection's token must be able to **push** to the
  new repo — a fine-grained PAT on "Only select repositories" creates the repo but the push fails.
- ✅ **Two-way sync:** agent commits are pushed to GitHub (same SHAs). A branch pushed from a
  Claude session appears in UnifyApps and `POST /agent-api/sessions/{s}/branch {branch}` pulls it
  into the Code Builder; merges to `main` on GitHub are picked up too. Published v1 of our app from a merged commit.
- ✅ **Privacy for code apps is set by the builder agent** (ask it), not Settings → Privacy (refused for code apps).
- ✅ Direct edit without Git: `PUT /agent-api/sessions/{s}/files/contents {edits:[{path,content}]}`,
  then ask the builder agent to commit.
- Platform assets the code needs (objects, automations, agents, data sources, connections) are
  **not** in the repo — create them over REST (this skill, `unifyapps-builder`), then reference
  their ids from `app/src/data/`.

## Maher's code-app methodology (the required flow) ✅ agreed 2026-09-21

Follow this order exactly. Do **not** shortcut it (no pasting code into the builder working tree
with `PUT /files/contents`, no asking the builder agent to write the real app):

1. **UnifyApps creates the app.** Code-mode prompt (console *New Application → Code*, or
   `POST /agent-api/sessions`) with a brief that asks for a **minimal starter only** — no objects,
   data sources, automations or seed data. Name it as the user wants it shown (never "Maher" in the UI).
2. **UnifyApps creates and links the GitHub repo** (*More → Git → GitHub*, or
   `POST /agent-api/sessions/{s}/git`) using the user's own GitHub connection.
3. **Stop and tell the user** to add the new repo to the fine-grained PAT behind that connection
   (Repository access → the repo, **Contents: Read and write**). Until then the repo is empty.
4. **Trigger the first push** — the engine only pushes on its next commit: ask the builder chat to
   "commit the current working tree as it is". Confirm `GET /agent-api/sessions/{s}/git` →
   `sync.state: "synced"` and `gh api repos/<owner>/<repo>/commits` shows the commit.
5. **Develop locally.** `gh repo clone`, `cd app && bun install && bun run build`. Run the dev
   server with `bun --cwd=<repo>/app run dev --port 5173` (a `.claude/launch.json` entry for the
   browser pane). The engine-managed `app/.env` carries `API_PROXY_TARGET` (the tenant),
   `VITE_APPLICATION_ID` and `APP_AUTH_TOKEN`, so `/api` and `/auth` proxy to the real backend.
   A PRIVATE app shows its login page first — **the user signs in**, never Claude.
6. **Platform assets over REST** (workflows, `e_data_source`s, agents) — then reference their ids
   in `app/src/data/`. A code app created over the API may lack `e_global_<appId>`; create it first.
7. **Commit and push to GitHub from the local clone**; UnifyApps picks it up (switch the session to
   the branch / `main`), rebuilds the preview, and is published from `main`.
8. Keep this skill and `API-SPEC.md` updated in the same turn as any new finding.

## Golden rules

1. **Shared tenant.** Read anything; write only objects you created. Name scratch objects
   `<yourname>_scratch_*` (the signed-in user's name) and list them in your report. Never type into another person's code-builder
   chat, never link Git on an app you don't own, never publish someone else's app.
2. **Never enter credentials.** Connections needing OAuth or secrets are created by the user
   with their own account; you find them (`aggregation` on `Connection`, see
   `references/connect-and-call.md` §4) and reference the id. For GitHub, the user connects
   **their own** GitHub account — never reuse someone else's GitHub connection.
3. **Send full bodies on update.** `POST /api/entity/update` and `/api/entity-type/update`
   replace `properties`/schema wholesale — a partial body fails `required` or drops fields.
4. **Every app→platform call goes through an `e_data_source`.** Never "fix" a
   `forbidden datasource` error by trying another endpoint — fix the data source or the inputs.
5. **Filters differ by surface.** Entity/aggregation API: `{op, field, values}` with field
   `properties.x` (entity) or `properties_x` (aggregation). Storage node / data sources:
   `{operator, filters:[{property, filter:{operator, value}}]}`. The wrong shape is often
   accepted with 200 and ignored.
6. **Verify by reading back**, and for apps by loading the page — a 200 from the hierarchical
   endpoint does not prove the page renders.

## Auth

Full walkthrough: `references/connect-and-call.md`. In short: session cookie from the
user's own local-account login, or run calls
same-origin from a logged-in browser tab (`fetch('/api/...')`) — which is how everything here
was verified. `scripts/ua_apps.js` wraps the verified calls for a logged-in tab: its read,
update, search and run helpers were exercised as written on 2026-09-21; the create helpers
(`createObject`, `createConnection`, `createAutomationDataSource`, `updatePage` for new blocks,
`deployApp`) send the exact bodies verified by hand but were not re-run through the helper.
Never ask for or handle the password.

## Verified scratch objects (UAT, built by the skill author)

Read-only references for the known-good shapes — **do not edit, publish or link Git on them**;
build your own. The ids exist only on UAT.

| What | Id |
|---|---|
| Object `maher_scratch_task` (6 fields, 2 records `T-001`, `T-002`) | `maher_scratch_task` |
| Connection `maher_scratch_http (Claude API learning)` (Custom HTTP, jsonplaceholder) | `6ab0ea7a5459f4370f0c1f3f` |
| Config app `maher scratch config app` (published v1) | `maher-scratch-cfg` |
| Its Homepage / global page | `e_6ab0ebb7f843281fda5f5fa3` / `e_global_maher-scratch-cfg` |
| Data source → workflow `6aae3aab0900af6ee3a552c0` (Fleet telemetry) | `e_6ab0ebe6f843281fda5f6032` |
| **Code app "Task Scratchpad"** (built by the Code prompt on `maher_scratch_task`, no new objects) | `app-3dfc7c54e504` |
| Its builder session | `e_6ab0f9b9fbe116271240c547` |
| Its five storage bindings (FETCH, FETCH_ONE, CREATE, UPDATE, DELETE) | `e_6ab0fa3efbe116271240cdb8` `…cdbc` `e_6ab0fa3ef843281fda5fe694` `e_6ab0fa3efbe116271240cdbf` `e_6ab0fa3ff843281fda5fe697` |
| Code app created purely via API | `app-282f2c90f0fd` (session `e_6ab0fd75f843281fda600744`) |

The code app's linked GitHub repo and GitHub connection are the author's personal ones and are
deliberately not listed. Use a GitHub connection made with **your own** GitHub account.
