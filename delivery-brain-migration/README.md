# Moving the FDSE utilisation page to another UnifyApps environment

`bundle.json` is a read-only export from sales.uat-us-east-1 (8 Oct 2026): object schemas, 9 workflows, the FDSE utilisation page,
its data source and its navigation item. `migrate.py` recreates them in a target environment. It needs only `bundle.json`.

1. Allow the target host (e.g. sales.unifyapps.com) under Network access in the cloud environment settings. The script signs in
   with the environment's existing UA_ login; set UA2_USERNAME / UA2_IDP_ID / UA2_PASSWORD only if the target needs a different one.
2. Dry run, which only reads: `python3 migrate.py --target https://sales.unifyapps.com` (add `--groups fdse,slack_sync` for the Slack flow).
3. Apply: add `--apply --app <target app id> --conn google_workspace=<connection id>`.

In your browser (for Google / SSO accounts; no password or identity provider id needed): `migrate_console.js` is the same
migration with bundle.json inlined. It runs on the tab's own signed-in session.

1. Sign in to the target (e.g. https://sales.unifyapps.com) and open DevTools (F12) → Sources → Snippets → New snippet.
2. Paste all of `migrate_console.js`, run it (Ctrl/Cmd+Enter), then in the Console: `await fdseMigrate()` for the dry run.
3. Apply: `await fdseMigrate({ apply: true, app: '<interface id>', conn: { google_workspace: '<connection id>' } })`.
   Other options: `groups: 'fdse,slack_sync'`, `tmSlug`, `scopeRoot`, `navModule`, `reuseExisting: true`.
   Ids it creates are kept in that browser per host, so reruns update; `fdseMigrate.state()` lists them.

After editing console_runner.js or bundle.json, rebuild with `python3 build_console.py`.

From your own machine with a local (non-SSO) account: Python 3.8+ with no extra packages.
Copy this folder, then set the target's login in your shell and run the same commands:

    export UA2_USERNAME=you@unifyapps.com UA2_IDP_ID=<target tenant's identity provider id>
    read -s UA2_PASSWORD && export UA2_PASSWORD
    python3 migrate.py --target https://sales.unifyapps.com

The identity provider id is per tenant, so the one the UAT login uses will not work on another environment.

Groups: `fdse` = the page, its data workflow, scoring and people sync (daily), the new-user trigger, the leaver archive.
`slack_sync` = DB | write CXO slack records and DB | Slack tasks | Sync to task tracker (the Slack agent itself is not included).
Check in the target: the page is limited to sumeet@ and alpha.jose@; its team tree starts at sumeet@ (`--scope-root` changes it);
Task Management links use the app slug task-management-application-clone (`--tm-slug` changes it).
