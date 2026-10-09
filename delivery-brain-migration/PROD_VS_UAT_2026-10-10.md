# Delivery Brain: prod vs UAT, full comparison (10 Oct 2026, ~03:30 IST)

Scope: app e-69f9786e285b7c092e6d2749 in both environments: every page (current draft), every page data source, every
workflow those data sources call (and everything they call in turn), every workflow named DB / Delivery Brain / Task
Management, the objects and AI agents those use, and the app settings. Compared after removing noise (CSS whitespace,
empty lists, path ordering, builder-only flags). Snapshot and scripts: scratchpad fulldiff_fetch.py / fulldiff_analyze.py.

## Totals

| | Same | Differ | Prod only | UAT only |
|---|---|---|---|---|
| Pages | 30 | 7 | 4 | 5 |
| Page data sources | 287 | 13 | 48 | 21 |
| Workflows | 171 (+2 differ only by connection id) | 33 | 78 (+17 same name, different id) | 6 |
| Objects used | 48 | 3 | 11 | 1 |
| AI agents used | 2 | 4 | 4 (+1 same name, different id) | 1 |

## Needs attention

1. **Unpublished edits in prod by user 26306 (9 Oct 21:10-21:43Z).** They go live with the next app publish (by anyone):
   - Customer Hub (account-directory): hides the "Add New Account" button, several table columns and the Accounts / Approval
     Required toggle.
   - Project Related Assets: hides two tabs.
   - Account Detail: alignment and padding on 4 text blocks.
2. **Prod is ahead of UAT (UAT never got these):**
   - The RBAC admin gate (admins skip the account filter) on 8 workflows: Fetch Account Directory, get pmpl (copy), patches and
     regions, cohort-0, Cohort 2, cohort-3, Accounts region wise, fetch use cases. UAT still has the plain filter.
   - voc_slack_agent (26306, 8 Oct: "ladder records and General records" ledger) and its pipeline DB | Fetch CXO slack
     Intelligence / DB | write CXO slack records (26306, 8 Oct; 7 and 2 extra steps in prod).
   - DB | Email ingestion scheduler and DB | Index Emails (26306, 6 Oct; one extra step each).
   - delivery brain | user ingestion one time (sets role), Leads / SubLeads Utilisation (prod's versions kept, newer node versions).
3. **Changed on both sides, still different:**
   - DB | write CXO records (UAT newer, 7 Oct) and DB | Fetch CXO Intelligence (UAT newer by a day: its filter code uses
     `property:` where prod's uses `field:`). Both sit on db_cxo_intelligence_slack, which is frozen in prod (UAT has 16 extra fields).
   - db | update account id: prod reads slack_channel, UAT reads db_risk_summary.
   - Delivery Brain | Usecase Timeline: prod reads db_account_usecase, UAT task_management_account_usecase.
4. **Looks like a test edit live in prod:** DB | Connection Confirmation via Slack Notification (26306, 9 Oct) now filters on
   emp_email = aditya.gupta1@unifyapps.com instead of department = Product Management.
5. **UAT only (never moved):** DB | Classify CXO Signals and its Run step (writes the frozen object's new fields), DB | Free-Email
   Signal | Create (with object db_sentiment_free_email), DB | HubSpot Company Merge, DB | STC Tickets | Data (not deployed),
   Delivery Brain - Get New User from Google Workspace (paused), agent DB | Use Case Classifier, pages add_channels (x2) and
   user management - Clone (x2).

## Intended or environment-specific (no action)

- **Built separately per environment (same name, different id):** FDSE utilisation page and its 9 workflows, the Slack work-given
  workflows, the Account 360 / Daily Account Report batch runners and weekly job, Slack Task Assignment agent. The FDSE and Slack
  ones differ in detail (prod page ids, connections, the 5-person menu allowlist).
- **Merges done on 9 Oct, prod keeps its own parts:** Module 2 (Vertical dropdown, use-case count, Go Live filter), Customer Hub
  (inline editing), Desktop Navigation (FDSE item, 5 people), CXO_dashboard's "task management use cases" source.
- **Prod wins by plan:** DB | Portfolio Dashboard; get-meetings (paused in prod, 3 extra steps); Task Management | Task UCwise /
  Task NameWise (prod's task_management_task_tracker object); Bulk Task Add Sheet (excluded).
- **Host and connection ids:** Account 360 | PDF and two Delivery Brain notifications use the prod host; Use case new's deep link
  uses each environment's Task Management URL; DB | Add Account Id to transcripts and DB-login-slack-notification differ only in
  the Slack connection id; agents differ only in indexingSettings (each environment's knowledge index).
- **Objects:** db_cxo_intelligence_slack (frozen; UAT +16 fields, prod +session_id), db_user_management (frozen; prod +emp_id),
  db_project_activity (id type), prod-only task_management_* objects (Task Management app, kept as prod's), knowledge_log, testghn.
- **Data sources:** 13 differ, mostly cached output schemas (no runtime effect) plus the Module 2 merge. Prod-only
  sources are on prod-only pages (Module 2 clones 38, FDSE, add_slack_channels) and Module 2 / Customer Hub merge parts.
- **Account Health Dashboard:** each side has one unused page variable the other lacks.

## Prod-only workflows (78, not in UAT under any id)

These are prod's own pipelines and helpers. The scheduled, deployed ones run every day in prod and have no UAT equivalent.

- **DEPLOYED, called by pages/workflows** (34): DB | Create Action Items; DB | Extract excel data; DB | Extract excel data (Account DB); DB | Fetch RAG transition analytics; DB | Fetch client sentiment overview; DB | Granola-ingestion; DB | Granola-ingestion (Manual Time ingestion); DB | Granola-ingestion (missing run); DB | Post slack message for unknown meetings; DB | Steerco Checker; DB | Task Management | Bulk Task Add Sheet; DB | Task Management | Task UCwise; DB | Update Account Status; DB | VoC | Inner | High Sentiment Notification; DB | VoC | Inner | Low Sentiment Notification; DB | delivery pulse sentiment tool; DB | download page; DB | fetch lastweek sentiments; DB | improving-declining-accounts-list-day; DB | sentiment alert; DB | weekly summary; Task Management | Acitivity Audit Fetch; Task Management | Activity Audit; Task Management | Edit usecase in tags; Task Management | Fetch Account Directory; Task Management | Fetch New Tasks; Task Management | Task Email Updator; Task Management | Teams Accounts; Task Management | Update New Tasks Approved; Task Management | Update New Tasks Rejected; Task Management | Update StageTag from FORM; VoC Agent Invoker; db | insert risk summary; delivery brain | slack | brown uni enrich
- **DEPLOYED, google_workspace_on_new_user** (2): DB - Get New Users from Google Workspace; delivery brain | new user
- **DEPLOYED, google_workspace_on_updated_user** (1): DB | get user updates via Gworkspace
- **DEPLOYED, scheduled** (9): DB | Alerts; DB | Cleanup Inactive Google Workspace Connections; DB | Deactivated User Cleanup; DB | Granola Scheduler; DB | Slack coverage | Daily; DB | Unidentified meetings scheduler; DB | Use Case Stage Extractor | Nightly; DB | VoC | Sentiment Notification; DB | Weekly Google Workspace User Sync
- **DEPLOYED, storage_by_unifyapps_on_create_record** (1): DB | VoC | Outer | Low Sentiment Notification
- **DEPLOYED, webhooks_default** (4): Delivery Brain Login Reminder; db pop account usecase; db pop accounts; db | task management name ingestion
- **not deployed, ** (4): DB | delete-connections-gmail; Task Management | Account Owner; Task Management | update usecaseid; db | fetch sentiment signals (agent)
- **not deployed, called by pages/workflows** (18): DB | Email VoC | Low Sentiment Notif; DB | Fetch Executive Dashboard Stats (copy); DB | Fetch Portfolio Trend Chart (copy); DB | Fetch duplicate meetings; DB | My Workllist (copy); DB | Portfolio Dashboard (copy); DB | Task Management | Account Documents (Final); DB | Update Submissions; DB | Update account owners in account_db; DB | Update readings; DB | get processed meetings; DB | rag config bar html; DB | status change; Task Management | fetch new usecases from another object; Task Management | make general usecase for new; db | fetch Risk | Escalation | Commitment; db | fetch usecases; db | get pmpl (copy) (copy)
- **not deployed, scheduled** (2): DB | Create rec weekly (copy); DB | risk summary schedular
- **PAUSED, scheduled** (1): DB | Email Scheduler
- **PAUSED, storage_by_unifyapps_on_create_record** (1): DB | Task Management | New Tasks
- **not deployed, webhooks_default** (1): db pop accounts (copy)

## Unpublished drafts

- Prod: Account Detail, Project Related Assets, account-directory (all 26306, see above). App live version 149.
- UAT: 11 pages differ from UAT's published app (live v19); UAT is used through drafts, so this is normal there.
