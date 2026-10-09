# UAT → prod sync, slice by slice (from 9 Oct 2026)

Plan: Migration_Execution_Plan.pdf (order VOC → Use Case Hub → Account Health → CXO Dashboard → Account Detail).
Do-not-change-schema objects: db_cxo_intelligence_slack, db_user_management, submission_db, readings_db. No records in
db_sentiment_score are changed. Agents are handled by hand. `slice_mig.py` holds the helpers (UAT via UA_*, prod via UA2_*).
Prod definitions are saved to `prod_backups/slices/` (gzip JSON, named by id and the prod version they replaced) before every overwrite.

## Slice 1 — VOC

### Step 1.1 — workflows: done (9 Oct, ~15:00Z)

Canary (another session): DB | VoC Escalations Drill-Through `6aa868528301093ee4df5c0d`, prod identical to UAT.

The other 7 were promoted with prod's envelope and UAT's content (name, description, settings, tags, nodes, edges):

| Workflow | id | prod draft | prod deployed | nodes |
|---|---|---|---|---|
| DB \| Fetch Executive Dashboard Stats | 6a6d060ca36c357436252758 | v65 → v66 | v65 → v66 | 11 → 13 |
| DB \| Fetch Portfolio Trend Chart | 6a6cfe20a36c357436246b8e | v21 → v22 | v21 → v22 | 5 → 7 |
| DB \| accounts-without-sentiments-list-day | 6a7b206bf938b82042eed593 | v21 → v22 | v21 → v22 | 6 → 8 |
| DB \| declining-accounts-list | 6a82b156235cd70e174d2ff6 | v11 → v12 | v11 → v12 | 9 → 11 |
| DB \| fetch executive dashboard data | 6a69f0dba36c357436da3922 | v173 → v174 | v173 → v174 | 11 → 13 |
| DB \| improving-accounts-list | 6a82b1408d0db120388479bf | v28 → v29 | v28 → v29 | 9 → 11 |
| DB \| improving-declining-accounts-list-week | 6a6a05573b208605c137aebc | v60 → v61 | v60 → v61 | 6 → 8 |

- What UAT adds in all 7: two steps, "RBAC: all accounts" and "RBAC: accounts this user may see", optional `rbac_scope` /
  `rbac_names` inputs, and the record fetches narrowed to those accounts. With no scope passed (prod's pages pass none)
  every account is allowed, so behaviour is unchanged. Prod had no nodes or edges of its own that UAT lacks.
- Proof before saving: each workflow was test-run on prod twice with the same inputs, once as the prod definition and
  once as the UAT definition (nothing saved). All 7 gave byte-identical outputs on prod's data.
- After deploying: node/edge hash equals UAT's for all 7, no violations. The 5 without a time window were re-run and
  matched their pre-promotion output exactly.
- Run-status projections do work on prod with this session (`slice_mig.prod_test`), so test runs can be checked.
- Rollback: save the matching file from `prod_backups/slices/` back with saveAndReturnViolations and deploy it.

### Step 1.2 — data sources: on hold (decision needed)

All 21 data sources of Voice Of Customer Dashboard (19) and escalations (2) exist in prod under the same ids. 17 differ,
and every difference is the same thing: UAT passes the signed-in user's account scope from a global data source
`rbacScope` (`e_6ac14d1c1924167ba878f874`, global page) that calls `DB | RBAC | My accounts` (`6ac14cfce7e1e627524c771a`).
Neither exists in prod. The UAT expressions fall back to `'__pending__'`, so copying them without rbacScope would
show no accounts at all.

RBAC rule in UAT: a user whose role name contains "admin" or "owner" sees every account; anyone else sees the accounts
where their email is on db_team_members. Prod has the data (642 team rows with email, 224 people, 106 accounts).

The same dependency runs through 27 UAT pages' data sources (e.g. Account Detail 41/65, Project Related Assets 20/31,
Voice Of Customer Dashboard 15/19, Account Health Dashboard 12/42, CXO_dashboard 6/14, global page 3/5). The plan's
"identical → skip" checks compared page blocks only, so Account Health Dashboard, Signal Details and others are not
identical once data sources are counted.
