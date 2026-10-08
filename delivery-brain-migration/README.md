# Moving the FDSE utilisation page to another UnifyApps environment

`bundle.json` is a read-only export from sales.uat-us-east-1 (8 Oct 2026): object schemas, 9 workflows, the FDSE utilisation page,
its data source and its navigation item. `migrate.py` recreates them in a target environment. It needs only `bundle.json`.

1. Allow the target host (e.g. sales.prod.unifyapps.com) under Network access in the cloud environment settings. The script signs in
   with the environment's existing UA_ login; set UA2_USERNAME / UA2_IDP_ID / UA2_PASSWORD only if the target needs a different one.
2. Dry run, which only reads: `python3 migrate.py --target https://sales.prod.unifyapps.com` (add `--groups fdse,slack_sync` for the Slack flow).
3. Apply: add `--apply --app <target app id> --conn google_workspace=<connection id>`.

In your browser (for Google / SSO accounts; no password or identity provider id needed): `migrate_console.js` is the same
migration with bundle.json inlined. It runs on the tab's own signed-in session.

1. Sign in to the target (e.g. https://sales.prod.unifyapps.com) and open DevTools (F12) → Sources → Snippets → New snippet.
2. Paste all of `migrate_console.js`, run it (Ctrl/Cmd+Enter), then in the Console: `await fdseMigrate()` for the dry run.
3. Apply: `await fdseMigrate({ apply: true, app: '<interface id>', conn: { google_workspace: '<connection id>' } })`.
   Other options: `groups: 'fdse,slack_sync'`, `tmSlug`, `scopeRoot`, `navModule`, `reuseExisting: true`.
   Ids it creates are kept in that browser per host, so reruns update; `fdseMigrate.state()` lists them.

After editing console_runner.js or bundle.json, rebuild with `python3 build_console.py`.

From your own machine with a local (non-SSO) account: Python 3.8+ with no extra packages.
Copy this folder, then set the target's login in your shell and run the same commands:

    export UA2_USERNAME=you@unifyapps.com UA2_IDP_ID=<target tenant's identity provider id>
    read -s UA2_PASSWORD && export UA2_PASSWORD
    python3 migrate.py --target https://sales.prod.unifyapps.com

The identity provider id is per tenant, so the one the UAT login uses will not work on another environment.

Groups: `fdse` = the page, its data workflow, scoring and people sync (daily), the new-user trigger, the leaver archive.
`slack_sync` = DB | write CXO slack records and DB | Slack tasks | Sync to task tracker (the Slack agent itself is not included).
Check in the target: the page is limited to sumeet@ and alpha.jose@; its team tree starts at sumeet@ (`--scope-root` changes it);
Task Management links use the app slug task-management-application-clone (`--tm-slug` changes it).

## Deployed to prod (sales.prod.unifyapps.com), 8 Oct 2026

- **Objects:** db_fdse +11 fields, db_task_tracker +4 fields, new fdse_archive, record webhooks on for db_user_management.
- **New workflows:** DB | FDSE Utilisation Page | Data `6ac7d2a8a28e363678239862`, DB | FDSE | Utilisation (week-based) `6ac7d2aa1340983bcc0fd56c`,
  Utilisation daily `6ac7d2ad55f7914af4b75c42` (06:00 IST), Sync people `6ac7d2af131eb342769ecdde`, Sync people daily `6ac7d2b0d2e90d47faa01a49` (05:30 IST),
  Add new user `6ac7d2b255f7914af4b75c59`, DB | Slack tasks | Sync to task tracker `6ac7d2d91340983bcc0fd732`.
- **Page:** FDSE utilisation `e_6ac7d2b475dffa07574b3452` (data source `e_6ac7d2b52073570d456c9d9d`) in Delivery Brain — CXO Dashboard, with its nav item.
- **Changed existing workflows** (originals in `prod_backups/`):
  - Task Management | SubLeads Utilisation `6a79f529ad075e71cf23ffca`: v75 -> v76, the UAT version (week-based score).
  - DB | Task Management | Leads Utilisation `6a9faceef985714a326a25f3`: v3 -> v4, the UAT version (week-based score).
  - DB | write CXO slack records `6aba455da3760e42b2b7b888`: v7 -> v8, only the "Sync Slack tasks to the task tracker" step added before Respond.
- **Left as is:** Delivery Brain - Archive Deleted Google Workspace Users (already identical in prod).
- **First runs:** the people sync archived 88 leavers and 13 duplicates into fdse_archive (db_fdse 538 -> 437 rows); scoring ran for 437 people.
