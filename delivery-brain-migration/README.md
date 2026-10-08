# Moving the FDSE utilisation page to another UnifyApps environment

`bundle.json` is a read-only export from sales.uat-us-east-1 (8 Oct 2026): object schemas, 9 workflows, the FDSE utilisation page,
its data source and its navigation item. `migrate.py` recreates them in a target environment. It needs only `bundle.json`.

1. Add the target login to the cloud environment as variables: `UA2_BASE_URL`, `UA2_USERNAME`, `UA2_IDP_ID`, `UA2_PASSWORD`
   (a local, non-SSO account). Allow the target host in the environment's network settings if it is a different domain.
2. Dry run, which only reads: `python3 migrate.py` (add `--groups fdse,slack_sync` for the Slack -> task tracker flow).
3. Apply: `python3 migrate.py --apply --app <target app id> --conn google_workspace=<connection id>`.

Groups: `fdse` = the page, its data workflow, scoring and people sync (daily), the new-user trigger, the leaver archive.
`slack_sync` = DB | write CXO slack records and DB | Slack tasks | Sync to task tracker (the Slack agent itself is not included).
Check in the target: the page is limited to sumeet@ and alpha.jose@; its team tree starts at sumeet@ (`--scope-root` changes it);
Task Management links use the app slug task-management-application-clone (`--tm-slug` changes it).
