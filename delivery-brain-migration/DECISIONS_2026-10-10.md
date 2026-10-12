# Decisions, 9-10 Oct 2026 (asked one by one; work runs after all are answered)

Status: **D** = decided, not yet done · **Done** = applied and verified.

## Round 1 — handover "Known limits"

| # | Item | Decision | Status |
|---|------|----------|--------|
| 1.1 | 26306's unpublished prod drafts (Customer Hub, Project Related Assets, Account Detail, 7 data-source field-list refreshes) | Publish them with the next publish | Done (published with prod v150) |
| 1.2 | Phone menu (4 dead buttons, 2 mock-ups) | Real pages: Health (Portfolio Dashboard), VOC, Accounts (Customer Hub), Tasks (Task Management), Risks (Escalations), CXO (admins only) | Done (prod v150; UAT draft) |
| 1.3 | Medium screens: custom top bar with its links hidden, dead CXO link | Use the standard menu (same as wide screens) | Done (prod v150; UAT draft) |
| 1.4 | Mock-ups: Head of Delivery, PM Control Tower | Leave them out of menus; pages untouched | Done (out of every menu) |
| 1.5 | 17 data sources filter by account name | Switch to account id (plan to be shown and asked first) | D |
| 1.6 | Atlas sync (Issues tab empty) | Copy the same setup as UAT to prod and make it work | Done (prod: atlas_project_ created, first run 10 Oct 00:19Z: 125 projects, 1000+ issues; every 6 h) |
| 1.7 | DB \| Connection Confirmation via Slack Notification | Leave it (not a test edit: 26306's on-demand DM to 12 people) | Done (no change) |
| 1.8 | VOC "No sentiment" pill % shows Red % | Fix the label, prod and UAT | Done (prod v150; UAT draft) |
| 1.9 | UAT behind prod | Everything: admin gate on 8 workflows, VOC Slack agent + its 2 pipeline workflows, Email ingestion scheduler + Index Emails | Done 12 Oct (gate x8 = prod; Slack fetch = prod; write merged; email scheduler prod logic + UAT connections; Index Emails rolling; agent merged) |

## Round 2 — review list (10 Oct)

| # | Item | Decision | Status |
|---|------|----------|--------|
| — | Name filters, dead links, mock-ups, Atlas sync, prod-only admin bypass | Covered by round 1 (1.2-1.6, 1.9) | D |
| 2.1 | Admin decided by role name containing "admin"/"owner" | Admin only when a role name is exactly "Admin" (trimmed, any case); "Owner" and "... Owner" roles are not admins. Same rule in the RBAC workflow, menus and pages, UAT and prod | Done (prod v150; UAT draft). Prod: 41 admins; Sarthak (Owner only) loses admin |
| 2.2 | Settings (RAG Config) open to everyone | Admins only: hidden from the menu for non-admins and blocked by page permission, UAT and prod | Done (page guard + Settings button on CXO Dashboard; out of the menu) |
| 2.3 | ARR and renewal dates editable inline by anyone who sees the account | Admins only: read-only for non-admins, admins keep inline editing, UAT and prod | Done (columns admin-only + save backstop) |
| 2.4 | Two ARR figures (manual and HubSpot) | Fine as is; no change | D (no action) |
| 2.5 | No audit trail for Customer Hub edits | Log every edit to a new object (who, when, field, old value, new value), written by the save path; admins can read it; no page change | Done (db_account_edit_log + DB | Customer Hub | Log edit; tested in UAT) |
| 2.6 | Attention page and FDSE utilisation limited to hard-coded names | Create a Super Admin group; start it with everyone on both current lists (Attention: Sumeet, Jay, Alpha; FDSE: its 5 names); both pages and their menu items check the group, no names in code | Done (group 'Delivery Brain Super Admins': prod 5, UAT 4; superAdmin data source; Attention card/page, FDSE page/menu) |
| 2.7 | 67 sub-stages copied from UAT | Keep them; the nightly extractor overwrites them as new evidence comes in (none locked) | D (no action) |
| 2.8 | Load Last Week save logic was fragile (19 RAGs wiped, since fixed and restored) | Nothing more; the fix is enough | D (no action) |
| 2.9 | Three health models | Account 360 rubric (/12) is the official account health. Record only: noted in the handover, no app changes now | D (record) |
| 2.10 | Attention Accounts to Slack (red/amber top 10, 23:15 IST) off in prod | Turn on in prod with a prod Slack connection; user picks the channel from a list I provide (asked during execution) | Kept off (decision 12 Oct: no channel yet) |
| 2.11 | HubSpot approval sync and weekly Account 360 rebuild never run in prod | Run both now as real runs, check records and errors; Monday schedules carry on | Partly: weekly Account 360 run done 10 Oct; HubSpot sync blocked (owner ishan.savaliya removed edit access) - first run on its Monday schedule |
| 2.12 | "Account 360 (old)" tab on Account Detail | Hide it (visibility switch), UAT and prod; data and page stay | Done (already hidden in both; handover corrected) |
| 2.13 | Create Slack Channels only in prod (UAT has an older page) | Leave it; note that this path can only be tested in prod | D (no action) |
| 2.14 | No bake time for the 9 Oct fixes | Daily health check for 7 days (each nightly/weekly job ran and wrote records, failed runs), short pass/fail summary each morning | D |
| 2.15 | FDSE people sync (05:30) runs before the Google Workspace user sync (09:00) | Move FDSE people sync to 09:30 IST; rename the Workspace sync from "Weekly" to "Daily" | Partly: FDSE sync at 09:30 done; rename blocked (harshit's workflow, no edit access) |
| 2.16 | Slack coverage depends on a manual channel-linking form | Leave it as is | D (no action) |
| 1.5a | Account-id switch: filter strictness | ID or name: a record shows if its account id OR its account name is in the user's scope | D |
| 1.5b | Tasks have no account-id field | Add account_id to db_task_tracker, backfill all rows from the account name, set it in the task-creating workflows that can be changed, plus a nightly filler for tasks created without it (Bulk Task Add Sheet stays untouched); UAT and prod | D |
| 1.5c | Signal alerts list accounts by AI-written name | Keep names; only use cases and tasks move to ID-or-name | D |
| 3.1 | readings_db and submission_db reads not account-filtered everywhere | Add the RBAC account filter (ID or name, admins open) wherever pages or workflows read readings_db and submission_db; no schema change to either object | Done in UAT; prod data sources done (v150); prod DB | Portfolio Dashboard blocked (owner Ishan, no edit access) |
| 3.2 | DB \| Index Emails hard-coded to 5-6 Oct (no client emails since 5 Oct 21:02 UTC); UAT stuck on 15-16 Sep | Fix + backfill: rolling window (yesterday to today, IST) in prod and UAT, then backfill 6-10 Oct in prod day by day | Done 12 Oct: prod rolling (v156), 6-12 Oct backfilled (9,244 -> 9,511 emails); UAT rolling (v109, stale Gmail default fixed) |
| 3.3 | UAT VOC Slack agent: prod's prompt drops UAT's 12 signal fields that Classify CXO Signals reads | Merge: UAT gets prod's ledger rules, duplicate guard and pagination, and keeps its signal fields in the prompt and the write workflow | Done 12 Oct (agent v20, write workflow v11, fetch v3) |
| 3.4 | Dana: super admin | Application level: already in 'Delivery Brain Super Admins' (prod and UAT, verified). A platform-role call was also made before this was clarified; its effect could not be read back reliably (see handover open items) | Done (app level) |

## Run order (one by one, each verified before the next)

1. Round 1 quick fixes: VOC % label, phone menu, standard menu on medium screens (prod + UAT drafts).
2. Access: admin = exactly "Admin" (2.1), RAG Config admins only (2.2), ARR / renewal date admins only (2.3), Super Admin group (2.6).
3. Account 360 (old) tab hidden (2.12).
4. One prod publish (includes 26306's drafts, 1.1); prepublish check first.
5. Audit trail for Customer Hub edits (2.5).
6. FDSE people sync to 09:30, Workspace sync renamed Daily (2.15).
7. Atlas sync in prod (1.6); Attention Accounts to Slack on, channel picked by user (2.10).
8. First runs now: HubSpot approval sync, weekly Account 360 (2.11).
9. UAT parity: admin gate x8, VOC Slack agent pipeline, 2 email workflows (1.9).
10. Account-id switch (1.5a-c).
10b. RBAC filter on readings_db and submission_db reads (3.1).
11. Daily health check for 7 days (2.14); handover doc + MIGRATION_LOG; push.
