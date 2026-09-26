# Code-based applications (Code Builder)

Observed on UAT 2026-09-21 on our own scratch code app `app-3dfc7c54e504` ("maher scratch code
app") and from the builder's JS bundle. The data-source contract underneath was **re-executed** on our own
config app — it is the same endpoint and the same governance.

## What a code app is

`e_interface` with `properties.manifest = {type:"WEB", mode:"code"}` and almost nothing else —
the app lives in a Git working tree managed by the **Code Builder agent API** (`/agent-api`,
same origin, cookie auth). The platform agent that writes it is `aiAgentId: "text_to_ui_tensor"`.
Preview/deploy host: `https://{appId}-orbit.tensor-uat.unifyapps.com`.

### Repo layout (template, 2026-09)

```
.agents/rules/project-guidelines.md          the agent's coding rules
.agents/skills/<name>/SKILL.md               28 platform skills, versions in .agents/skills/.engine-skills.json
   object-data v6, backend-integration v8, automation-integration v1, workflow-authoring v9,
   authentication v3, app-users v2, roles-and-permissions v6, copilot v6, file-upload v4,
   analytics v4, localization v18, theming v8, maps v8, content-security-policy v2, ...
.githooks/pre-push                           runs app/scripts/check-core-stack.mjs on each pushed commit
PLAN.md  PRODUCT.md  README.md  theme.json
app/package.json      React 19, Vite 8, TS 7 rc, Tailwind 4, TanStack Query 5, react-router 7,
                      zustand, radix-ui, recharts, i18next;  "@unifyapps/app-builder-sdk": "^0.4.0"
app/vite.config.ts  app/vite/uaSdkRuntime.ts  app/vite/sdkImportMapBlock.ts
app/src/main.tsx      wraps the app in <AppBuilderProvider> (mounts TanStack Query) — don't add another
app/src/data/         ALL platform calls: bindings.ts (generated), refresh.ts, one wrapper per object/automation
app/src/lib/data.ts   useData(id, 'seed'|'storage'|'callable', config) — reads go through this so the Data tab sees them
app/src/routes/ app/src/components/ (shadcn/ui in components/ui)
```

The SDK is **not installed from npm** (it isn't public). `app/.ua-sdk-config.json` maps each
subpath to a tenant CDN build through an import map (`app/vite/sdkImportMapBlock.ts`):
`hooks/object`, `hooks/workflow`, `hooks/user`, `hooks/upload`, `hooks/permissions`, … →
`https://cdn.unifyapps.com/lib/app-builder-sdk/uat/hooks/<name>-<hash>.js`, with peers
`react`, `react/jsx-runtime`, `@tanstack/react-query`. Always import via the package specifier
(`@unifyapps/app-builder-sdk/hooks/workflow`). `VITE_APPLICATION_ID` is set by the engine.
(The agent's `backend-integration` skill text still says "vendored under src/" — our app,
built 2026-09-21, uses the CDN import map.) A local `bun run build` works — the agent ran it.

## How app code reaches the platform

Only through `e_data_source` entities, executed with the SDK hooks:

```ts
import { useExecuteWorkflowNode, useExecuteWorkflowNodeMutation,
         getExecuteWorkflowNodeQueryKey } from '@unifyapps/app-builder-sdk/hooks/workflow'
```

- `useExecuteWorkflowNode({id, context, inputs, options})` — query (reads, runs on mount, cached).
- `useExecuteWorkflowNodeMutation().mutateAsync({ data: {id, context, inputs, options} })` — writes / button actions.
- Both put the `x-ua-app` header on the request. **Never** use the bare `executeWorkflowNode`
  (no header → rejected) or the deprecated `useTriggerWorkflow`. Never pass your own `meta`.
- The app must **never** call `/api/entity` or `/api/aggregation` — those are build-time only.

### Object CRUD — five object-agnostic bindings (`src/data/bindings.ts`)

Minted once per app (the agent's `provision_data_sources`), anchored to `e_global_<appId>`:

| export | action (`storage_by_unifyapps_…`) | overridable inputs |
|---|---|---|
| `FETCH` | `fetch_records` MULTIPLE | `object_type`, `triggerInputCondition`, `page`, `sortBy` |
| `FETCH_ONE` | `fetch_records` SINGLE | `object_type`, `triggerInputCondition` |
| `CREATE` | `create_record` (`useRawPayload:true`) | `object_type`, `rawPayload` |
| `UPDATE` | `update_record_by_id` (`upsert:false`) | `object_type`, `recordId`, `rawPayload` |
| `DELETE` | `delete_record_by_id` | `object_type`, `entityId` |

`ENTITY = { task: 'maher_scratch_task', ... }` maps names to object ids. Rules: spread the **whole**
`storedInputs` and change only overridable fields; filter shape
`{operator:'AND', filters:[{property:'properties.status', filter:{operator:'EQUAL', value:'open'}}]}`
(record id is `id`; `value` singular except `IN`); response `data.response.objects[]` with
fields nested under `properties` (the helpers flatten); UPDATE replaces the whole record; every
write must invalidate reads of that `object_type` (`useRefresh`).

### Calling an automation — one data source per automation

```ts
const AUTOMATION_ID = '6aae3aab0900af6ee3a552c0'       // our Fleet - Vehicle Telemetry workflow
const DATA_SOURCE_ID = 'e_...'                          // the e_data_source you created for it
const RESOURCE_VERSION = 3124                           // callables_call_automation version it was created with
const PAGE_SLUG = `global-page-of-${import.meta.env.VITE_APPLICATION_ID}`

mutateAsync({ data: {
  context: { appName: 'callables', resourceName: 'callables_call_automation', resourceVersion: RESOURCE_VERSION },
  id: DATA_SOURCE_ID,
  inputs: { automationId: AUTOMATION_ID, version: '-1', runtimeConnections: {},
            parameters: { __internals__: { m: 'BUILDER', s: PAGE_SLUG, c: 'PLATFORM', p: 'browser' }, vehicleId },
            synchronous: true },
  options: {} } })
// output = res.response  (the STOP node's result; no `body` wrapper)
```

The matching data source (created with `POST /api/entity`, ✅ verified mechanism):
`properties: {name, type:"APPLICATION", interfaceId:<appId>, interfacePageId:"e_global_<appId>",
context:{appName:"callables", resourceName:"callables_call_automation", resourceVersion},
inputs:{automationId, version:"-1", runtimeConnections:{}, parameters:{vehicleId:"{{vehicleId}}"}, synchronous:true},
dP:[{p:"inputs.parameters.vehicleId"}], advancedOptions:{...}}`.

**So when Claude adds a feature to a code app that needs a new automation:** build + deploy the
workflow (`unifyapps-builder`), create its `e_data_source` over REST, then write the wrapper in
`app/src/data/` using the returned id. Objects: create with `POST /api/entity-type`
(`objects-and-connections.md`) and add to `ENTITY` — the five bindings already cover them.

## Agent API (`/agent-api`)

`s` = a Code Builder session id (an `e_...` case id). Opening the builder creates one
(`POST /agent-api/sessions`) and puts it in the URL `?sessionId=`.

| Method · path | Purpose | |
|---|---|---|
| `GET /sessions/{s}/files` | `{files:[{path,size}]}` whole tree | ✅ read |
| `GET /sessions/{s}/files/content?path=&v=` | raw file text | ✅ read |
| `POST /sessions` `{target:"code-builder", input, userName, userEmail, appId?, branch?}` | create app / new chat → `{appId, sessionId}` | ✅ |
| `PUT /sessions/{s}/files/contents` `{edits:[{path,content}]}` | save files (no commit) → `{filesVersion}` | ✅ |
| `POST /sessions/{s}/files/{op}` | file operation (create/rename/delete) | 📦 |
| `GET /sessions/{s}/branches` | `{current, default, linked, remoteError, branches:[{name,local,remote}], previewVersion, filesVersion}` | ✅ read |
| `POST /sessions/{s}/branches` `{branch, base, description}` | create branch | 📦 |
| `POST /sessions/{s}/branch` `{branch}` | switch branch — pulls remote commits | ✅ |
| `DELETE /sessions/{s}/branches/{name}` | delete branch (local **and remote**) | 📦 |
| `GET` · `POST` · `DELETE /sessions/{s}/git` | Git status · link · unlink | ✅ GET/POST |
| `GET /sessions/{s}/changes` | commit list of the current branch `{branch, changes:[{sha, message, date, published}]}` | ✅ |
| `POST /sessions/{s}/restore` `{sha}` | restore a snapshot | 📦 |
| `POST /sessions/{s}/edits` | apply visual edits (180 s timeout) | 📦 |
| `POST /sessions/{s}/styles` `{file, loc, styles}` | style edit | 📦 |
| `GET /sessions/{s}/manifest` · `/routes` · `/data-model` · `/query-plan` | app metadata | 📦 |
| `GET /sessions/{s}/download` | zip of the source | 📦 |
| `POST /sessions/{s}/events?since=` | agent event stream | 👁 |
| `POST /sessions/{s}/stop` · `/retry` · `/queue/...` | agent control | 📦 |
| `POST /apps/{appId}/publish` `{versionTag, versionNote}` | publish (default branch only) | ✅ |
| `GET /apps/{appId}/branches?offset&limit&detail=basic` | branches incl. remote, ahead/behind, PR, `remoteError` | ✅ |
| `GET /apps/{appId}/deployed/routes` · `/apps/{appId}/branches/{b}/files/content` · `/branches/{b}/manifest` | read a branch without a session | 📦 |
| `GET /system-health` | engine health (`{pvc}`) | ✅ (503 during an outage) |

Chat with the builder agent goes through `POST /api/workflow/execute/node?name=call_automation`
(automation `66ab98083d73300e63962287`, `copilotType:"AI_AGENT"`, `caseId:<session>`); session
lists via automation `6a7c42a1eddf8930c2ffe6af` (`fetchType: SESSION_HISTORY | QUEUE_AND_LOCK_STATUS`).
A branch is locked while someone's agent run is active ("<name> is editing — this branch is busy").

## Create a code app over the API ✅ 2026-09-21

Verified by creating `app-282f2c90f0fd` with no UI at all:

```js
// 1. start the build — the Code Builder agent writes the app from the prompt
POST /agent-api/sessions
{ "target": "code-builder", "input": "<the app brief>",
  "userName": "<me.name>", "userEmail": "<me.email>"
  // optional: "appId" (continue an existing app in a new chat), "branch",
  //           "planner": {model, connectionId, provider, vertexProject, modelEntityId}
  //           (from text_to_ui_code_models; empty on UAT → omit), "attachments": [...]
}
→ 200 { "appId": "app-282f2c90f0fd", "sessionId": "e_6ab0fd75f843281fda600744" }

// 2. REQUIRED — the session does NOT create the application entity. Without it the app is
//    invisible in Applications and GET /api/entity/e_interface/{appId} is 404 (checked after 60 s).
POST /api/entity/create-update-or-delete/hierarchical
{ "entity": { "id": "<appId>", "entityType": "e_interface", "tags": [],
    "properties": { "type": "application", "name": "...", "description": "...", "standard": false,
      "manifest": {"type":"WEB","mode":"code"}, "deviceDetails": {"base":"desktop"},
      "metadata": {"logo": {...}, "_counter": {"_pageCount":0,"_moduleCount":0,"_mqttTopicCounter":0,"_templateComponentCount":0}},
      "navigation": {"primary":[],"secondary":[],"defaultPageId":""},
      "locale": {"defaultLocale":"en-US"}, "theme": {"defaultThemeId":"<an e_theme id>"},
      "flags": {"shouldReEvaluateUsingEntityIds": true}, "chatSessionId": "<sessionId>" } },
  "requestType": "CREATED", "ignoreVersion": true }

// 3. host
POST /api/domain-mapping/interface
{ "domain": "<appId>-orbit.tensor-uat.unifyapps.com", "module": "INTERFACE", "applicationId": "<appId>" }  → 204
```

Result (checked after the build): `app-282f2c90f0fd` appeared in the Applications list (`e_interface` aggregation), status `done`, preview built, bound to `maher_scratch_task` verbatim, and `security.type: PRIVATE` because the brief asked for login — the agent sets privacy from the brief onto the entity we created. **API-only creation is fully verified.**

Progress: read the session case — `POST /api/workflow/execute/node?name=fetch_records` on
`object_type: "service_hub_case"`, `id` = sessionId → `properties.customProperties.enginePayload`
`{status: "running"|"done", model, routing, preview_version, files_version, ...}`. The UI shows a
branch as busy while `status` is running; file edits and Git setup are refused until it is done.
A finished app's entity gains `interfacePageIdVsSlugMap`/`entityDetailsMap` for `e_global_<appId>`,
`security` (`PUBLIC` if the brief said "no login"), `integrations.appAnalytics`.

## Editing code over the API ✅ 2026-09-21

```
PUT /agent-api/sessions/{s}/files/contents   {"edits":[{"path":"README.md","content":"<whole file>"}]}
→ 200 {"filesVersion": 2}
```

That writes the working tree only — **it does not commit**. The UI then asks the agent to
commit with a fixed message (strings from the bundle):
`"I made some changes to <path> (modified). No rebuild needed — commit these changes."` or
`"… Rebuild the preview with these changes, fix any code errors they introduce, and commit the result."`
Sent in the builder chat, the agent shows it as *Manual edit* and commits (verified: commit
`b903fd8`, then pushed to GitHub). The chat-send request itself travels over the streaming
channel and was not captured — until it is, send it from the builder chat, or prefer the Git
route below (no chat needed). Other file ops: `POST /agent-api/sessions/{s}/files/rename`
`{from_path, to_path}` 📦 (and create/delete by the same pattern).

## Privacy and publishing ✅ 2026-09-21

- **Private vs public is `e_interface.properties.security.type`** (`PUBLIC` | `PRIVATE`), read by
  the SDK at runtime — not a code toggle. For a **code** app the platform **refuses** changing it
  from *Settings → Security → Privacy Settings* (client-side `RefusalError: '<appId>' is a
  code-builder app … Change it in the code builder instead`). Ask the builder agent instead
  ("Make this app PRIVATE (sign-in required) using the app security setting…") — it calls its
  `update_app_security` tool; verified `security.type` flipped to `PRIVATE` within a minute.
  A brief that says "no login page" makes the agent set `PUBLIC`.
- A private app redirects to `/login?returnTo=/` on its host (verified on the published URL).
  Users must be granted in the app's *Settings → Users* (empty by default).
- **Publish:** `POST /agent-api/apps/{appId}/publish {"versionTag":"v1","versionNote":"..."}`
  (tag: starts with a letter, no spaces, only `-`/`_`). Default branch only. Result on the entity:
  `deploymentState {deployedAt, deployedBy, deploymentNotes, deploymentTag, version,
  additionalDetails:{sourceCommitHash}}` — the published commit is recorded; `/changes` marks it
  `published: true`. Published v1 of `app-3dfc7c54e504` from `3d2aadd`.
- **Merge-to-`main` pickup ✅:** after merging PR #1 on GitHub, the builder's `main` contained the
  merge (`9ea3734`). The engine added two merge commits of its own (`4d87e3e`, `3d2aadd`) that were
  not on GitHub yet — it reconciles local and remote `main` rather than fast-forwarding.
- Sending a builder chat message did not appear on any page-level fetch/XHR/WebSocket hook (only
  121-byte MQTT frames). To instruct the agent over the API, start a new session on the app:
  `POST /agent-api/sessions {target:"code-builder", appId, branch:"main", input:"<instruction>", userName, userEmail}`
  (same call the builder's "new chat" uses — the new-app form of it is verified; the existing-app
  form is 📦 from the bundle).

## Git / GitHub ✅ two-way, verified 2026-09-21

Link (captured from the UI, then used): Code Builder → **More → Git → Continue to Git setup →
GitHub → pick connection → Owner / Repository name / Description → Create repository**.

```
POST /api/lookup?ByQuery=APPROVED_GITHUB_ORG
{ "type":"ByQuery","lookupType":"APPROVED_GITHUB_ORG",
  "options":{"connectionId":"<github connection>","skipApprovalCheck":true,"source_resource_name":"github_fetch_organizations"},
  "query":"","page":{"limit":1000,"offset":0} }
→ objects [{ "id":"username:<your-github-login>", "name":"Your Repository" }, ...orgs]

POST /agent-api/sessions/{s}/git
{ "provider":"GITHUB", "connectionId":"<your own github connection id>",
  "repositoryName":"<yourname>-scratch-code-app", "projectName":"<yourname>-scratch-code-app",
  "organizationName":"username:<your-github-login>",
  "createOptions":{"autoCreate":true,"payload":{"visibility":"private","newRepoName":"<yourname>-scratch-code-app",
                   "org":"username:<your-github-login>","description":"..."}} }
→ 200 { provider, connectionId, repositoryName, repositoryUrl, remoteUrl, linkedAt, branch:"main", branchUrl }
```

- `GET /agent-api/sessions/{s}/git` → `{linked, config, sync:{state:"syncing"|"error"|…, ts, detail}}`;
  `DELETE` the same path unlinks (repo kept). The app entity records it in
  `properties.additional.gitDetails {provider, connectionId, organizationName, repositoryName, projectId, branch, linked, repositoryUrl}`.
- Personal account vs org: tenant flag **"Code app repositories under organizations only"**
  (`/settings/feature-flags`), **off on UAT** → personal accounts work.
- **Token trap (hit and fixed):** the repo is created through GitHub's API, then the engine
  pushes with the same token. A **fine-grained PAT limited to "Only select repositories"** can
  create the repo but cannot push to it → repo exists but is empty, `sync.detail: "push failed —
  see engine logs"`, branches `remoteError: "could not reach the remote repository"`. Fix: add the
  new repo to the token (Contents: read & write), or use "All repositories". There is no retry
  call — the push happens on the **next saved change** (a commit).
- **UnifyApps → GitHub:** every agent commit is pushed; SHAs are identical on both sides
  (`00e743b`, `b903fd8`), commits co-authored by the UnifyApps user.
- **GitHub → UnifyApps:** a branch pushed from outside appears within seconds in
  `GET /agent-api/apps/{appId}/branches?offset=0&limit=10&detail=basic` and in the session's
  branches as `{local:false, remote:true}`. `POST /agent-api/sessions/{s}/branch {"branch":"claude/pull-test"}`
  checks it out and the Code Builder serves the pushed commit (`051e482`) — verified by reading
  the file back through `/files/content`.
- ✅ Merged-to-`main` commits are picked up too (PR #1, `9ea3734`) — see *Privacy and publishing*.
  (`/agent-api` can return 503 cluster-wide during engine outages — wait, don't retry in a loop.)
- Branch rows show *Check status*, *Behind | Ahead*, *Pull request*. Publishing is allowed only
  from the default branch (`POST /agent-api/apps/{appId}/publish` 📦).

### Working on a code app from a Claude session — the loop

1. Create the app (`POST /agent-api/sessions` + entity + domain) or use an existing one; wait
   for `enginePayload.status == "done"`.
2. Link Git (`POST /agent-api/sessions/{s}/git`) with the user's GitHub connection — the token
   must be able to push to the new repo.
3. `gh repo clone <owner>/<repo>`; read `.agents/rules` and `.agents/skills` first; `bun install`
   (installs the pre-push hook) and `bun run build` before pushing.
4. Create platform assets over REST (objects, workflows, `e_data_source`s, agents); reference
   their ids in `app/src/data/`.
5. Push a branch, open a PR, merge to `main`.
6. In UnifyApps, switch the session to the branch/`main` (`POST /agent-api/sessions/{s}/branch`)
   to pull it in, check the preview, then publish from `main`.

## Findings from building "GSPC Agentic Assistant" (`app-60a767dfb0bb`) ✅ 2026-09-21

### A code app created over the API has no global page — data sources need one
**Symptom:** `POST /api/entity` for an `e_data_source` with `interfacePageId: "e_global_<appId>"`
→ `500 {errorCode: 5011, "Parent e_component:e_global_<appId> not found while resolving
permissioned ancestor of e_data_source"}`. The session + `e_interface` + domain mapping recipe
above does **not** create the app's global page, and the builder agent only mints it when it
provisions data sources itself (a brief that says "create no data sources" never gets one).

**Fix (verified):** create the page yourself, then the data sources succeed:
```
POST /api/entity/create-update-or-delete/hierarchical
{ "entity": { "id": "e_global_<appId>", "entityType": "e_component", "tags": [],
    "properties": { "layout": {"body":"root_id","header":"header_id","footer":"footer_id"},
      "interfaceType": "application", "componentType": "PAGE", "metadata": {"_version": 2},
      "blocks": { ...header_id / root_id / footer_id Stack blocks, copied from any app's global page... },
      "flags": {"shouldUseBuiltDependencies": true}, "name": "global-page-of-<appId>",
      "slug": "global-page-of-<appId>", "interfaceId": "<appId>", "useAsync": true,
      "dataSources": {}, "pageVariables": {} } },
  "requestType": "CREATED", "ignoreVersion": true }
```
Then 57 automation data sources were created in one pass (8 in parallel, zero errors) and
executed through `POST /api/workflow/execute/node?name=<any>&requestId=<dsId>` from a logged-in
platform tab — 200 with `response.rows` straight from Oracle EBS.

### Data source shape that works for a CALLABLE workflow with N inputs
`properties.inputs.parameters` = every START-schema property as `"{{name}}"`, and `dP` = one
`{p:"inputs.parameters.<name>"}` per property. Tag the entity (`tags:["..."]`) — it is accepted.

### Git link with a fine-grained PAT limited to selected repositories
`POST /agent-api/sessions/{s}/git` → **200** with `repositoryUrl`; the GitHub repo exists but is
**empty**, and a later `GET /agent-api/sessions/{s}/git` returns `{"linked": false}` — the link
did not persist because the first push failed. The user must add the repo to the token
(Contents: read & write) before the link/push can succeed.

## Findings from building "Standup Board" (`app-7e15a9fb98dd`) ✅ 2026-09-26

- **An errored first turn is recoverable.** `enginePayload.status: "error"` with `recoverable: true` (one LLM call,
  0 tokens) → `POST /agent-api/sessions/{s}/retry` `{}` → `{"ok": true}`; the build finished ~80 s later.
- **Linking Git pushes straight away** when the token can push (PAT on all repositories): `sync.state` was `synced`
  seconds after `POST …/git`, and GitHub had the builder's commit. Check `GET …/git` and the GitHub commits before
  asking the builder to "commit the working tree" — it may be unnecessary.
- **Privacy from the brief is not reliable** (API-SPEC §18 D4): "Require sign-in" produced login routes but no
  `security.type`. Read it back.
- **Cloud (Claude Code on the web) sessions:** the session's git/GitHub proxy only allows repos attached to the
  session, even with a personal token — attach the new repo (`add_repo`, push access) before cloning. Don't push with
  `git push -u <url-with-token>`: `-u` writes that URL into `.git/config`.
- **Data layer by REST** (instead of the builder's `provision_data_sources`): create `e_global_<appId>`, then the five
  storage data sources with exactly the `storedInputs` in the template's `bindings.ts`, `dP` = one
  `inputs.<field>` per `{{field}}`; one `callables_call_automation` data source per workflow with
  `parameters.<p>: "{{p}}"` and `dP` `inputs.parameters.<p>`. Write the ids into `bindings.ts` (`ENTITY` + five ids)
  and an `automations.ts`; `bun run build` type-checks them against the SDK. Searching data sources needs a
  `properties.interfacePageId` filter.
