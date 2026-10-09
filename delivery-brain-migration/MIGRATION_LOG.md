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

### RBAC base in prod: done (9 Oct, ~15:30Z, on request)

- `DB | RBAC | My accounts` created in prod under UAT's id `6ac14cfce7e1e627524c771a` (v1, deployed, node hash equals UAT).
- Global data source `rbacScope` created in prod under UAT's id `e_6ac14d1c1924167ba878f874` on the global page, identical
  to UAT. It runs on page load with the signed-in user's email and an admin flag (a role whose name contains "admin" or "owner").
- Rule: admins see every account (scope `*`); anyone else sees the accounts where their email is on db_team_members;
  until the scope has loaded, pages show nothing (`'__pending__'`).
- Tests on prod: admin → all 134 accounts; a team member → their accounts (32 and 10 for two people); an email with no
  team rows → none. The prod account used for this work has Owner / Admin / Super Admin roles.
- The other two RBAC-aware global data sources (dbGetPmpl, dbSteerCallsThisWeek) move with their workflows in slices 2 and 4.

### Step 1.2 — data sources: done

All 21 data sources of Voice Of Customer Dashboard (19) and escalations (2) exist in prod under the same ids. 16 differed
(15 + 1), each only by the RBAC scope (filters / `rbac_scope`, `rbac_names` parameters reading rbacScope). All 16 now
equal UAT; the other 5 were already identical. Prod copies are in `prod_backups/slices/prod_ds_*`.

### Step 1.3 — pages: done

- Voice Of Customer Dashboard `e_6a61aec66454dc4d222120c8`: v10919 → v10920, 372 → 381 blocks. UAT was strictly ahead
  (9 new blocks, 7 changed, none only in prod).
- escalations `e_6aa7f95e282c94597434a1fb`: v821 → v822, 69 → 138 blocks. The page was created in prod on 14 Sep and copied
  to UAT on 23 Sep; UAT rebuilt it (Escalations / Risks / Commitments). The 45 blocks only in prod are the old layout.
  Since the canary deploy of the drill-through workflow, the live prod page had been reading fields the new output no
  longer has (`escalation_count`, `rows`), so its counts and rows were blank until this publish.
- Every UAT page reference (data sources, pages) resolves in prod.

### Publish: app v141 → v142 (9 Oct, ~15:45Z)

Checked first that no other page, data source or app setting had unpublished changes. One did: FDSE utilisation, whose
11:38Z draft (shared prod account) replaced the two drawers' "Close ✕" texts with icon buttons; that went live with this
publish. Its previous live copy is `prod_backups/slices/prod_live_page_e_6ac7d2b475dffa07574b3452_app141.json.gz`.
After publishing: both live pages equal UAT; all 17 data sources (16 + rbacScope) are live and equal their drafts.

### Step 1.4 — verify: done

1. All 8 workflows: node/edge hash equals UAT, deployed, no violations.
2. Test runs on prod with RBAC scopes: VoC Escalations Drill-Through admin 60 accounts affected / team member 5 / no scope 0;
   improving-declining-week 100 / 8 / 0; fetch executive dashboard data admin 100 / no scope 0.
3. Pages could not be opened here (the app's CDN is blocked from this environment); render check is for a person.
4. db_sentiment_score is still being written (newest row 14:04Z on 9 Oct, 2,779 rows); none were changed.

Rollback for Slice 1: restore files from `prod_backups/slices/` (workflows via saveAndReturnViolations + deploy, data sources
via /api/entity/update, pages via the hierarchical update), delete rbacScope and the RBAC workflow, then publish.

### Follow-up: Signal Alerts card empty in prod (fixed 9 Oct, ~16:20Z)

The VOC Signals tab showed "0 Critical / 0 open". UAT's alert data sources keep alerts whose `accounts_mentioned` is in the
user's RBAC account names. Prod's 10 alerts (seed rows from 3 Sep; nothing writes db_singal_alerts in either environment)
had the account only in `alerts_accounts_affected`, which is not searchable, so the filter dropped all of them; before the
promotion prod's data sources had no filter. UAT's rows carry both fields with the same value (6 of 6), so prod's 10 rows
got `accounts_mentioned` copied from `alerts_accounts_affected`, using the account_db name where it differed
("KPMG" -> "KPMG India", "Ministry of Defense (MODHS)" -> "Ministry of Defense Health Services (MODHS) KSA"). The page's
query now returns all 10 for an admin and none before the scope loads. No publish needed (data only). Rollback: unset
`accounts_mentioned` on alert_101 … alert_110.
Other RBAC-filtered VOC sources checked on prod data: meetings analysed 2,648 -> 2,647 (one row for C_350, which is not
in account_db); the Program Lead filter list 135 -> 122 rows (team rows for accounts no longer in account_db).

## Batch 2 — slices 2-4 and the other non-merge pages (9 Oct, ~15:00-15:50Z), app published v142 -> v143

Inventory of the whole app (77 workflows reached from data sources, incl. nested calls; 331 / 321 data sources; 38 / 42 pages):
42 workflows identical, 12 UAT-ahead (promote), 11 new in UAT, 10 changed on both sides, 2 prod-only (the prod FDSE builds).

RBAC fixes found on the way (applied in UAT and prod, so both stay identical):
- Admin gate. A fetch filter with an empty or missing list matches nothing, so "all accounts" for admins was passed as every
  account name / id, and records whose account name did not match account_db exactly disappeared (db | task list showed 147 of
  243 use cases). The RBAC step now also returns `f_op` / `f_ids` / `f_names`: admins (scope `*`) get `NOT_IN ['__never__']`
  (no filtering at all), everyone else `IN` their list. Every RBAC filter in the promoted workflows uses them (`rbac_gate.py`).
- DB | fetch all accounts: UAT's RBAC change had replaced prod's sentiment filters (call transcripts, new interactions, date)
  instead of adding to them; restored.
- Use Case Hub accounts data source keeps prod's not-churned filter next to RBAC.

Workflows (prod backups in prod_backups/slices, UAT backups in uat_backups): fetch-acc-stats, db | get pmpl, Get Projects and
Use Cases, steer calls this week, Cohort 1, fetch all accounts, pm-account-details, db | task list (all gated), My Workllist,
Trend table, Update use case fields (adds the stage rules). Each read-only one was run on prod before saving, prod version vs
the new one, same inputs: identical outputs for admins. Non-admin check (task list): admin 243 use cases, a team member 48,
before the scope loads 0. The 8 VOC workflows from slice 1 got the same gate (identical to their pre-RBAC prod output).

Data sources: RBAC on 20 pages (CXO_dashboard, Use Case Hub, Use case new, Project Related Assets, All_use_case, Accounts,
All Projects - Clone, PM Control Tower, Projects, Signal Details, Steer calls, Task Management, Use Cases, cohort-dashboard,
unidentified-meetings, Module 1, global page, VOC - Clone, account-directory, Account Health Dashboard) and Module 2's
update-use-case source (failure message). Kept prod's: CXO "task management use cases" (prod's newer db_account_usecase
version) and VOC meetings_analyzed (edited in prod at 14:27Z). Data-source filters themselves still use the plain RBAC lists
(94 by account id, 17 by account name): an admin can miss records whose account name does not match account_db.
Prod accepts the RBAC parameters on workflows that do not declare them (checked), so out-of-scope merges are unaffected.

Pages: Use Case Hub (whitespace), Project Related Assets (two tab settings normalised), Use case new (Task Management link
function; prod points at task-management-application-clone-unifyapps-sales.matrix-prod.unifyapps.com/account-details, UAT at
UAT). Left as they are: account-directory (changed on both sides), Account Health Dashboard (blocks identical), Module 2 and
the navigation pages (out-of-scope merges). CXO_dashboard moves with slice 5 (its new card needs the Account 360 workflows).

FDSE utilisation navigation: removed from the app's built-in menu (it showed for everyone); the Desktop Navigation card stays,
visible only to Sumeet, Alpha, Naman, Dana and Jay (UAT: Sumeet and Alpha).

## Next: slice 2 onward

The RBAC scope also runs through the data sources of 27 UAT pages (e.g. Account Detail 41/65, Project Related Assets 20/31,
Account Health Dashboard 12/42, CXO_dashboard 6/14). The plan's "identical → skip" checks compared page blocks only, so
pages such as Account Health Dashboard and Signal Details still need their data sources synced even where blocks match.
