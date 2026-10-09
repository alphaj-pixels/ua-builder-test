# FDSE "Slack engagement (past 30 days)" — work given in Slack

Builder scripts for the FDSE utilisation page's Slack engagement view. `prod/` and `uat/` hold the same scripts with each
environment's id files (`db_automations.json`, `fu_page.json`, `assign_agent.json`). Run a folder's scripts from inside that folder with
that environment's `UA_BASE_URL`, `UA_USERNAME`, `UA_IDP_ID`, `UA_PASSWORD` (and `UA2_*` for `prod_client.py`) in the environment.

Pipeline: `db_slack_conversations` (raw Slack, Harshit's object; filled by `DB | Slack conversations | Fetch`, a copy of his workflow)
-> Slack Task Assignment agent (`assign_agent.py`) -> `DB | Slack assignments | Extract` (`assign_wf.py extract2`) writes
`db_slack_assignments` and 'Slack assignment' tasks in `db_task_tracker` -> `DB | FDSE | Slack engagement | Score` (`assign_wf.py score`)
writes `db_fdse_slack_engagement` -> page data `slack_eng_page.py` -> page `fu_cap_page.py` (Upcoming load | Slack engagement switch).

State on 9 Oct 2026: the agent runs in prod only (hourly at :05 IST); UAT's agent, hourly job and Slack fetch are paused, and UAT
gets copies of prod's results. Prod's Slack fetch was a 30-day backfill, then daily from 10 Oct (below).

UAT copy, 9 Oct 05:20 IST: prod's `db_slack_assignments` (4,422 rows), `db_fdse_slack_engagement` (336) and 'Slack assignment'
tasks in `db_task_tracker` (1,788) were copied into UAT under the same ids, and UAT-only leftovers removed, so the counts match.
Page totals differ slightly (prod 159 zero / 76 low / 80 engaged of 315; UAT 156 / 76 / 82 of 314) because UAT's
`db_user_management` reporting tree differs. The page-data sort now orders by band first (the old comparator broke Java's sort
contract on UAT); deployed in both. The prod one-off backfill wrapper was deleted after it finished.

Daily fetch, 9 Oct 12:30 IST: `DB | Slack conversations | Daily` (`slack_conv_daily`, prod only) runs at 05:45 IST and fetches the
previous full UTC day from every mapped account channel (VoC agent calls stay skipped, since they would write `db_sentiment_score`).
The backfill covered 9 Sep to 8 Oct 23:59 UTC, so the first run (10 Oct) starts at 9 Oct with no gap or overlap. The hourly agent reads the
new conversations from 06:05 IST. Replies added to a thread whose first message is older than the previous day are not picked up.
Built with `CONV_CRON="45 5 * * *" CONV_DAYS=1 CONV_RUN_DATE="" CONV_NAME="DB | Slack conversations | Daily" python3 slack_conv_uat.py daily`.

Past 30 days from the task tracker, 9 Oct 13:10 IST: the page's toggle is now `Past 30 days | This week | Next 30 days` (the separate
"Upcoming load | Slack engagement" switch is gone). The score (`assign_wf.py score3`) counts work given from `db_task_tracker`: tasks
owned by an FDSE (`ownerMail` / `Owners_List`) dated in the past 30 days, using the Slack message time for Slack tasks and the
creation time otherwise. That covers 'Slack assignment' tasks, Slack CXO tasks (counted once when they're on the same message as a
Slack assignment) and tasks logged in the tracker. Open and done come from the tracker status (Done / Completed / Closed = done).
Prod: 1,829 tasks (1,767 Slack assignment, 62 Slack CXO, 0 logged directly), Sumeet's team 160 zero / 73 low / 82 engaged of 315.
App republished (version 133).

Four buttons, 9 Oct 13:30 IST: `Slack engagement | Past 30 days | This week | Next 30 days`. Slack engagement is the view above
(work given per week, Engaged / Low / Zero). Past 30 days is the utilisation view (same layout and bands as This week / Next 30 days)
over the tasks assigned to each person in the last 30 days: `fdse_score.py` takes `window_days=past30`, counts every task in the
tracker assigned in the window, done or not (Slack tasks dated by the Slack message, others by when they were added), each at its story
points (1 when blank, waiting ×0.5), against 30/7 of weekly capacity; a Slack CXO task on the same message as a Slack assignment for
the same person counts once. Built by `fdse_page_wf.py` (page data, `fdse_page`) and `fu_cap_page.py`. Prod app published (version 134).

Scope for now, 9 Oct 13:50 IST: every view shows only Shivam Satrawal's (`shivam@unifyapps.com`) and Sandeep Sharma's
(`sandeep.sharma@unifyapps.com`) teams under Sumeet Nandal (`SCOPE_TEAMS` in `fdse_page_wf.py` and `slack_eng_page.py`); the other
direct reports' teams (Aman Agarwal, Sudhir Yadav, Rahul Sethi, Yatendra Singh, Kuntal Beniwal) are hidden. No records were changed.
To show everyone again, start the scope walk from `SCOPE_ROOT` instead of `SCOPE_TEAMS` and redeploy both data workflows.

Access, 9 Oct 14:00 IST (prod): Dana Sabbagh (`dana.sabbagh@partner.unifyapps.com`) and Jay Shah (`jay.shah@unifyapps.com`) added
to Sumeet, Alpha and Naman (`DUO` in `fu_page.py`: page gates, the nav card and the data sources' full-team `admin` flag). App
published (version 135). UAT's list is unchanged (Sumeet and Alpha).

Past 7 days, 9 Oct 14:20 IST: a fifth button, `Slack engagement | Past 30 days | Past 7 days | This week | Next 30 days`.
`fdse_score.py` now takes any `window_days=pastN` (past7, past30): tasks assigned in the last N days against N/7 of weekly capacity.
Prod (Shivam's and Sandeep's teams): 421 of 569 people were assigned no tasks in the past 7 days. App published (version 136).
