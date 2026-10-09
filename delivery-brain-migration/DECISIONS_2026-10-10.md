# Decisions, 9-10 Oct 2026 (asked one by one; work runs after all are answered)

Status: **D** = decided, not yet done · **Done** = applied and verified.

## Round 1 — handover "Known limits"

| # | Item | Decision | Status |
|---|------|----------|--------|
| 1.1 | 26306's unpublished prod drafts (Customer Hub, Project Related Assets, Account Detail, 7 data-source field-list refreshes) | Publish them with the next publish | D |
| 1.2 | Phone menu (4 dead buttons, 2 mock-ups) | Real pages: Health (Portfolio Dashboard), VOC, Accounts (Customer Hub), Tasks (Task Management), Risks (Escalations), CXO (admins only) | D (dry run OK) |
| 1.3 | Medium screens: custom top bar with its links hidden, dead CXO link | Use the standard menu (same as wide screens) | D (dry run OK) |
| 1.4 | Mock-ups: Head of Delivery, PM Control Tower | Leave them out of menus; pages untouched | D |
| 1.5 | 17 data sources filter by account name | Switch to account id (plan to be shown and asked first) | D |
| 1.6 | Atlas sync (Issues tab empty) | Copy the same setup as UAT to prod and make it work | D |
| 1.7 | DB \| Connection Confirmation via Slack Notification | Leave it (not a test edit: 26306's on-demand DM to 12 people) | D |
| 1.8 | VOC "No sentiment" pill % shows Red % | Fix the label, prod and UAT | D (dry run OK) |
| 1.9 | UAT behind prod | Everything: admin gate on 8 workflows, VOC Slack agent + its 2 pipeline workflows, Email ingestion scheduler + Index Emails | D |

## Round 2 — review list (10 Oct)

| # | Item | Decision | Status |
|---|------|----------|--------|
| — | Name filters, dead links, mock-ups, Atlas sync, prod-only admin bypass | Covered by round 1 (1.2-1.6, 1.9) | D |
| 2.1 | Admin decided by role name containing "admin"/"owner" | Admin only when a role name is exactly "Admin" (trimmed, any case); "Owner" and "... Owner" roles are not admins. Same rule in the RBAC workflow, menus and pages, UAT and prod | D |
| 2.2 | Settings (RAG Config) open to everyone | Admins only: hidden from the menu for non-admins and blocked by page permission, UAT and prod | D |
| 2.3 | ARR and renewal dates editable inline by anyone who sees the account | Admins only: read-only for non-admins, admins keep inline editing, UAT and prod | D |
| 2.4 | Two ARR figures (manual and HubSpot) | Fine as is; no change | D (no action) |
| 2.5 | No audit trail for Customer Hub edits | Log every edit to a new object (who, when, field, old value, new value), written by the save path; admins can read it; no page change | D |
| 2.6 | Attention page and FDSE utilisation limited to hard-coded names | Create a Super Admin group; start it with everyone on both current lists (Attention: Sumeet, Jay, Alpha; FDSE: its 5 names); both pages and their menu items check the group, no names in code | D |
| 2.7 | 67 sub-stages copied from UAT | Keep them; the nightly extractor overwrites them as new evidence comes in (none locked) | D (no action) |
| 2.8 | Load Last Week save logic was fragile (19 RAGs wiped, since fixed and restored) | Nothing more; the fix is enough | D (no action) |
| 2.9 | Three health models | Account 360 rubric (/12) is the official account health. Record only: noted in the handover, no app changes now | D (record) |
| 2.10 | Attention Accounts to Slack (red/amber top 10, 23:15 IST) off in prod | Turn on in prod with a prod Slack connection; user picks the channel from a list I provide (asked during execution) | D (needs channel pick) |
| 2.11 | HubSpot approval sync and weekly Account 360 rebuild never run in prod | Run both now as real runs, check records and errors; Monday schedules carry on | D |
| 2.12 | "Account 360 (old)" tab on Account Detail | Hide it (visibility switch), UAT and prod; data and page stay | D |
| 2.13 | Create Slack Channels only in prod (UAT has an older page) | Leave it; note that this path can only be tested in prod | D (no action) |
| 2.14 | No bake time for the 9 Oct fixes | Daily health check for 7 days (each nightly/weekly job ran and wrote records, failed runs), short pass/fail summary each morning | D |
| 2.15 | FDSE people sync (05:30) runs before the Google Workspace user sync (09:00) | Move FDSE people sync to 09:30 IST; rename the Workspace sync from "Weekly" to "Daily" | D |
| 2.16 | Slack coverage depends on a manual channel-linking form | Leave it as is | D (no action) |
| 1.5a | Account-id switch: filter strictness | ID or name: a record shows if its account id OR its account name is in the user's scope | D |
| 1.5b | Tasks have no account-id field | Add account_id to db_task_tracker, backfill all rows from the account name, set it in the task-creating workflows that can be changed, plus a nightly filler for tasks created without it (Bulk Task Add Sheet stays untouched); UAT and prod | D |
| 1.5c | Signal alerts list accounts by AI-written name | Keep names; only use cases and tasks move to ID-or-name | D |

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
11. Daily health check for 7 days (2.14); handover doc + MIGRATION_LOG; push.
