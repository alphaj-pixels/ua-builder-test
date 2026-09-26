# Connecting to UnifyApps with your own account, and calling the API

Author: **Maher**. This file ships in every UnifyApps skill (`unifyapps-builder`, `unifyapps-apps`,
`unifyapps-context-graph`) so each skill works when shared on its own.

**This skill contains no credentials.** No passwords, tokens, cookies, API keys or personal
accounts are stored anywhere in it. Everyone who uses it signs in with **their own** UnifyApps
account, and every call runs with that account's permissions.

---

## 1. Pick the tenant

Ask the user which tenant to use before calling anything. Hostnames the skills were verified on:

| Tenant | Base URL | Used by |
|---|---|---|
| UAT sandbox | `https://orbit.uat.unifyapps.com` | workflows, agents, apps, objects, connections |
| APS1 tool | `https://tool.prod-aps1.unifyapps.com` | Context Graph |

A different tenant has a different hostname, a different login provider id, and **different
connection, workflow and object ids**. Never reuse an id from one tenant on another.

## 2. Sign in — two options

### Option A — the user's own browser session (recommended; works with SSO)

1. Open the tenant in a browser tool (Claude's built-in browser, or Claude in Chrome) and let
   **the user sign in themselves** (Google / Okta SSO or username + password). Never type a
   password or complete an SSO prompt on the user's behalf.
2. Run every API call **same-origin from that tab** with the JavaScript tool. The session cookie
   is `httpOnly`: the browser attaches it automatically, and no credential ever enters the
   conversation.

```js
// mcp__Claude_Browser__javascript_tool — the active tab must be on the tenant origin
await (async () => {
  const ua = async (method, path, body) => {
    const r = await fetch(path, { method, credentials: 'include',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body) });
    const ct = r.headers.get('content-type') || '';
    if (!ct.includes('json')) throw new Error(`HTTP ${r.status} non-JSON: session expired? sign in again`);
    const data = await r.json();
    if (!r.ok) throw new Error(`HTTP ${r.status} ${JSON.stringify(data).slice(0, 400)}`);
    return data;
  };
  return await ua('GET', '/api/user-context?includeRoles=true');   // who am I?
})()
```

- A **401**, or an HTML response instead of JSON, means the session has expired. Ask the user to
  sign in again. Do not retry in a loop.
- Do not read or print `document.cookie`, local storage or request headers. You don't need them.

### Option B — scripts with a local (non-SSO) account

The Python scripts in these skills log in with a username and password over
`POST /auth/workflow/execute/node?name=emailAndPassLoginRequest` (note `/auth/`, not `/api/`).
That works only for a **local** account. SSO accounts can't log in this way, so ask an admin
for a local account or use Option A.

**The user runs the script in their own terminal.** It reads everything from environment
variables and prompts for the password with hidden input (`getpass`). The password is never
echoed, logged, written to disk or passed as an argument.

```bash
export UA_BASE_URL=https://orbit.uat.unifyapps.com
export UA_USERNAME=<your local username>
export UA_IDP_ID=<the tenant's local identityProviderId>
python scripts/<script>.py          # prompts: Password for <you>:
```

PowerShell: `$env:UA_USERNAME = "<your local username>"` and so on.

**Finding `UA_IDP_ID`.** This is the tenant's local-login provider id. It's the same for everyone
on the tenant and it isn't a secret, but it does differ between tenants.
- UAT (`orbit.uat`): `65d2f4cf672d16da08efc3d0`.
- Any other tenant: open the login page, open DevTools → Network, sign in with username and
  password, and read `inputs.identityProviderId` from the `emailAndPassLoginRequest` request
  payload. Or ask a tenant admin.

A 401 at login means one of: wrong username or password, the wrong `UA_IDP_ID`, the account
still has **First Login** set (sign in once in a browser to clear it), or MFA is enforced.

Claude must **never ask for the password in chat** and must never put it in a command line, a file
or an env var it writes itself. If the session is non-interactive, `getpass` cannot run, so use
Option A.

## 3. Confirm who you are

```
GET /api/user-context?includeRoles=true      → 200 with the signed-in user; 401 = not signed in
```

Note the user's name and email from the response, and the owner id that appears as `oUId` (in
aggregation rows) or `ownerUserId` (in entities). You'll use it to find **your own** objects.

## 4. Find a connection to use

A *connection* is an authenticated instance of a connector (Oracle DB, GitHub, Slack, HubSpot, a
custom HTTP API). Workflow steps reference it by id in `node.context.connectionId`. Tenants hold
thousands of them, so **search server-side**:

```http
POST /api/aggregation?entityType=Connection&group=STANDARD
{ "entityType": "Connection", "group": "STANDARD",
  "filter": { "op": "AND", "values": [
      { "field": "appName", "op": "EQUAL", "values": ["oracledb"] },
      { "field": "active",  "op": "EQUAL", "values": [true] } ] },
  "sorts": [{ "field": "cTm", "order": "DESC" }],
  "projections": [{"name":"id"},{"name":"name"},{"name":"appName"},{"name":"oUId"}],
  "page": { "limit": 50, "offset": 0 } }
```

Rows come back as `{ objects: [{ columns: { id, name, appName, oUId } }] }`. No secrets are
returned. Typical `appName` values: `oracledb`, `github`, `slack`, `hubspot`, `custom_http_endpoint`.

Rules:
- **Prefer connections the user owns** (`oUId` = their id), or ones they have been explicitly told
  to use. Names are arbitrary and often duplicated, so confirm the choice with the user.
- Never use or edit a connection whose name contains **DND** or **DONT TOUCH**, or one that belongs
  to someone else, without that person's permission.
- `GET /api/connection/{id}` returns `userInput` **with passwords and tokens in clear**. Read it
  only when you must check a host or service name, and **redact** it before showing or saving
  anything.
- **If no suitable connection exists, the user creates one** in the Connections Manager
  (`/p/0/connections/all` → New connection) and enters the secrets or clicks Authorize themselves.
  Then find it with the query above. Connections without secrets (for example a public Custom
  HTTP endpoint) can be created over the API: `POST /api/connection/input?appName=` (see the
  `unifyapps-apps` skill).
- HTTP calls to public APIs don't need a connection at all (`custom_http_endpoint_execute`).

## 5. Calling the API — conventions

| Convention | Detail |
|---|---|
| Base | `{BASE}/api/...`. Login is the one exception: `/auth/...` |
| Format | JSON in and out: `Content-Type: application/json`, `Accept: application/json` |
| Search anything | `POST /api/aggregation?entityType=<Type>&group=STANDARD` (workflows, connections) or `group=ENTITY` (agents, tasks, tools). Send the **full** body (`entityType`, `group`, `filter`, `sorts`, `projections`, `page`) or it returns 500 |
| Entities | create `POST /api/entity` · read `GET /api/entity/{type}/{id}` · update `POST /api/entity/update` (send the full object) · list `POST /api/entity/{type}` |
| Workflows | create `POST /api/workflow-definition` · save `.../saveAndReturnViolations` · deploy `.../{id}/deploy?version={n}` · test run `POST /api/test-workflow/initiate-test/{id}` |
| Action versions | resolve at runtime: `GET /api/workflow-builder/node/{app}/resources`. Never hardcode them |
| Paging | offset-based: `page: {limit, offset}` |

The full endpoint list is in each skill's own references, and in `API-SPEC.md` if you have the
repo.

## 6. Sharing-safety rules (apply always)

1. Never paste passwords, cookies, session tokens, API keys or `connection.userInput` contents
   into chat, a file, a commit, the API spec or a skill.
2. Write only to objects **you** created. The tenants are shared: read colleagues' work to learn,
   but don't change it.
3. Tag and name what you create so it's findable and safe to clean up: put your name in the object
   name (`<yourname>_scratch_...`) and in `tags` (e.g. `["<YOURNAME>_DEMO"]`).
4. Ids in these skills' "verified examples" belong to the author's test objects. Treat them as
   **read-only references**. Build your own rather than editing them.
