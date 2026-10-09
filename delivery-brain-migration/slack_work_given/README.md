# FDSE "Slack engagement (past 30 days)" — work given in Slack

Builder scripts for the FDSE utilisation page's Slack engagement view. `prod/` and `uat/` hold the same scripts with each
environment's id files (`db_automations.json`, `fu_page.json`, `assign_agent.json`). Run a folder's scripts from inside that folder with
that environment's `UA_BASE_URL`, `UA_USERNAME`, `UA_IDP_ID`, `UA_PASSWORD` (and `UA2_*` for `prod_client.py`) in the environment.

Pipeline: `db_slack_conversations` (raw Slack, Harshit's object; filled by `DB | Slack conversations | Fetch`, a copy of his workflow)
-> Slack Task Assignment agent (`assign_agent.py`) -> `DB | Slack assignments | Extract` (`assign_wf.py extract2`) writes
`db_slack_assignments` and 'Slack assignment' tasks in `db_task_tracker` -> `DB | FDSE | Slack engagement | Score` (`assign_wf.py score`)
writes `db_fdse_slack_engagement` -> page data `slack_eng_page.py` -> page `fu_cap_page.py` (Upcoming load | Slack engagement switch).

State on 9 Oct 2026: the agent runs in prod only (hourly at :05 IST); UAT's agent, hourly job and Slack fetch are paused, and UAT
gets copies of prod's results. Prod's Slack fetch was a one-off 30-day backfill.

UAT copy, 9 Oct 05:20 IST: prod's `db_slack_assignments` (4,422 rows), `db_fdse_slack_engagement` (336) and 'Slack assignment'
tasks in `db_task_tracker` (1,788) were copied into UAT under the same ids, and UAT-only leftovers removed, so the counts match.
Page totals differ slightly (prod 159 zero / 76 low / 80 engaged of 315; UAT 156 / 76 / 82 of 314) because UAT's
`db_user_management` reporting tree differs. The page-data sort now orders by band first (the old comparator broke Java's sort
contract on UAT); deployed in both. The prod one-off backfill wrapper (`slack_conv_daily`) was deleted after it finished.
