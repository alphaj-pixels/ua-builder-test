---
name: oracle-ebs-apis
description: Call vanilla Oracle E-Business Suite 12.2 seeded public APIs (HR, Payroll, OTA, AP) and query its schema safely from an integration layer. Use whenever writing to or reading from Oracle EBS — resolving an API signature, building a PL/SQL block for an integration tool, debugging ORA errors from HR APIs, or working with date-tracked HR tables.
metadata:
  author: Maher
---

# Oracle EBS 12.2 — seeded APIs and schema

> **Created by Maher.** Contains no credentials — connect with your own EBS / UnifyApps accounts.

Method and hard-won gotchas for driving **vanilla** EBS from outside (integration platform, agent
tool, script). Everything marked ✅ was executed against a live EBS 12.2.13 instance.

---

## Method — do these in order, every time

1. **Resolve the real signature from the database. Never from memory.**

```sql
SELECT NVL(overload,'-') ovl, position, argument_name, data_type, in_out, defaulted
FROM   all_arguments
WHERE  package_name = 'HR_PHONE_API' AND object_name = 'CREATE_PHONE'
ORDER  BY NVL(overload,'0'), position;
```

2. **Judge effort by `defaulted='N'`, not by the argument count.** Huge APIs are mostly optional or
   OUT. ✅ `HR_ASSIGNMENT_API.UPDATE_EMP_ASG` has **496 arguments** but only **4 real inputs**
   (`p_effective_date`, `p_datetrack_update_mode`, `p_assignment_id`, `p_object_version_number`) —
   the rest of the "mandatory" ones are OUT/IN-OUT variables you simply declare as locals.

3. **Test the block in SQL*Plus with `ROLLBACK` before wiring it anywhere.** HR APIs do **not**
   commit; the caller does. So a real call followed by `ROLLBACK` is a perfectly safe rehearsal.
   Prefer this over `p_validate => TRUE`, which some APIs fail differently (see IRC geocoding).

4. **Initialise the apps context before any write**, or rows are stamped `CREATED_BY = -1`:

```sql
FND_GLOBAL.APPS_INITIALIZE(:user_id, :resp_id, :resp_appl_id);   -- 800 = HR
MO_GLOBAL.SET_POLICY_CONTEXT('S', :org_id);                      -- AP/PO only
```

5. **Capture the full stack when something fails** — `SQLERRM` alone hides the real cause:

```sql
EXCEPTION WHEN OTHERS THEN
  dbms_output.put_line(DBMS_UTILITY.FORMAT_ERROR_STACK);
  dbms_output.put_line(DBMS_UTILITY.FORMAT_ERROR_BACKTRACE);
```
✅ This is what turned a meaningless `ORA-29273` into `IRC_LOCATION_UTILITY → UTL_HTTP →
ORA-29024 certificate failure` and made the fix obvious.

---

## Gotchas that cost real time

### Overloaded APIs
`all_arguments` shows repeated `position` numbers when a procedure is overloaded. Use **named
parameter notation** and supply exactly one overload's mandatory set so PL/SQL can resolve it.
Seen on `CREATE_POSITION` (2 overloads), `UPDATE_EMP_ASG` (4), `DELETE_POSITION` (2),
`DELETE_CONTACT_RELATIONSHIP`.

### PL/SQL `BOOLEAN` cannot cross JDBC
Many HR APIs return `BOOLEAN` warning flags (`p_no_managers_warning`, …) and take
`p_validate BOOLEAN`. JDBC cannot bind these. **Always wrap the call in an anonymous block** and
declare the booleans as locals; convert any incoming flag with
`CASE :v WHEN 1 THEN TRUE ELSE FALSE END`.

### Date-tracked tables
`PER_ALL_PEOPLE_F`, `PER_ALL_ASSIGNMENTS_F`, `HR_ALL_POSITIONS_F`, `PAY_ELEMENT_ENTRIES_F` all
need `TRUNC(SYSDATE) BETWEEN effective_start_date AND effective_end_date`.
✅ Omitting it in a `CONNECT BY` produced **13 duplicate rows** for a 4-level hierarchy. Deduplicate
with `ROW_NUMBER() OVER (PARTITION BY person_id ORDER BY effective_end_date DESC)` inside a CTE,
then run the hierarchy over that.

### Preserve values you are not changing
Update APIs take the *new* value for every parameter you pass — passing NULL **blanks the column**.
Read the current row first and pass `NVL(:p_new, l_current)`. Same for IN/OUT ids such as
`p_soft_coding_keyflex_id` and `p_cagr_grade_def_id`, which must be seeded from the current row.

---

## Specific APIs — verified calls

| API | Notes |
|---|---|
| `HR_PERSON_ABSENCE_API.CREATE_PERSON_ABSENCE` | ✅ Hours-based types (Vacation, Sick) **require** `p_time_start`/`p_time_end` + `p_absence_hours`, else `ORA-20001 Actual Start/End Date and Time`. The API **overwrites the IN/OUT duration**; keep originals in locals and re-`UPDATE PER_ABSENCE_ATTENDANCES` after. |
| `HR_PHONE_API.UPDATE_PHONE` | ✅ Trivial: `p_phone_id`, `p_phone_number`, `p_object_version_number`, `p_effective_date`. |
| `HR_PERSON_ADDRESS_API.UPDATE_PERSON_ADDRESS` | ✅ Simple, **but see the IRC geocoding trap below.** |
| `HR_CONTACT_REL_API.CREATE_CONTACT` | ✅ Needs **both** `p_start_date` *and* `p_date_start` — omitting the latter gives `ORA-20001: Start date cannot be NULL when the dynamic trigger PER_CONTACT_RELATIONSHIPS_ARI is enabled`. Also needs `p_personal_flag => 'Y'` for child/parent/spouse types. |
| `HR_ASSIGNMENT_API.UPDATE_EMP_ASG` | ✅ Supervisor change: `p_datetrack_update_mode => 'CORRECTION'`, seed `p_soft_coding_keyflex_id` and `p_cagr_grade_def_id` from the current row, declare the rest as locals. |
| `HR_POSITION_API.CREATE_POSITION` | ✅ **`p_name` is ignored.** The name is built from the Position Name key flexfield. Passing nothing yields a name of `"."` (empty segments joined by the delimiter). |
| `HR_MAINTAIN_PROPOSAL_API.INSERT_SALARY_PROPOSAL` | ✅ `all_arguments` marks only 3 IN args mandatory, but the **business rules demand two more**: `p_multiple_components => 'N'` and `p_approved => 'N'`. Omitting either throws `ORA-20001: The mandatory argument <name> value cannot be null` from `per_pyp_bus`. |
| `PAY_ELEMENT_ENTRY_API.CREATE_ELEMENT_ENTRY` | ✅ Needs `p_effective_date`, `p_business_group_id`, `p_assignment_id`, `p_element_link_id` (from `PAY_ELEMENT_LINKS_F`, **not** `element_type_id`) and `p_entry_type => 'E'`. |
| `OTA_DELEGATE_BOOKING_API.CREATE_DELEGATE_BOOKING` | ✅ `p_contact_id` is **mandatory** even when it must be NULL — omit it and you get `PLS-00306: wrong number or types of arguments`. There is **no** `p_tfl_object_version_number`; passing it fails the same way. Booking lands as `Employee Request`. |
| `OTA_EVENT_API.CREATE_CLASS` / `UPDATE_CLASS` | ✅ In OTA the bookable thing is a **class** (row in `OTA_EVENTS`), but the package procedures are named `*_CLASS`, not `*_EVENT`. `UPDATE_CLASS` is how you move an enrolment window (`enrolment_start_date` / `enrolment_end_date`) or class dates. |
| `AP_VENDOR_PUB_PKG.CREATE_VENDOR` | ✅ Surprisingly easy: `p_api_version => 1.0` plus a record with only `vendor_name` and `vendor_type_lookup_code`. Signature is `(p_api_version, x_return_status, x_msg_count, x_msg_data, p_vendor_rec, x_vendor_id, x_party_id)`. `vendor_name` must be **unique instance-wide**. Check `x_return_status <> 'S'` and raise — it does *not* throw on failure. |
| `AP_VENDOR_PUB_PKG.UPDATE_VENDOR` | ✅ Takes `p_vendor_id` **separately** from the record, plus `p_init_msg_list`, `p_commit`, `p_validation_level`. Setting only `end_date_active` on the record is how you retire a supplier — **there is no delete API**, so end-dating is the correct disposal for test data. |
| `DELETE_CONTACT_RELATIONSHIP` / `DELETE_POSITION` | Simplest overload is just the id + `p_object_version_number`. |

> `all_arguments` **flattens PL/SQL record types into the same `position` sequence** as the real
> procedure arguments. For `CREATE_VENDOR` that yields 136 "arguments" when the procedure has 7 —
> the rest are fields of `r_vendor_rec_type` and of `ext_payee_rec`. Filter with `data_level = 0`
> to see the actual parameter list.

> ⚠️ **`defaulted='Y'` does not mean optional.** HR APIs enforce a second layer of business rules in
> their `_bus` packages. An argument can have a PL/SQL default and still be rejected as "mandatory"
> at runtime. Treat `all_arguments` as the *shape*, and the rollback test as the *truth* — add
> arguments one at a time as each `ORA-20001 ... cannot be null` names the next one.

### Finding which key flexfield segments build a name
`"."` as a generated name means *N* enabled segments, all empty. Find the real ones from an
existing record rather than assuming 1 and 2:

```sql
SELECT pd.segment1, pd.segment2, pd.segment3, pd.segment6
FROM   hr_all_positions_f p
JOIN   per_position_definitions pd ON pd.position_definition_id = p.position_definition_id
WHERE  p.position_id = <a position that already has a good name>;

SELECT id_flex_num, application_column_name, segment_name
FROM   fnd_id_flex_segments WHERE id_flex_code='POS' AND enabled_flag='Y';
```
✅ On this instance positions use **SEGMENT3 (code) + SEGMENT6 (name)** → `SR999.Senior Analyst`.

---

## 🔴 The IRC geocoding trap — breaks ALL address writes

`PER_ADD_UPD` calls iRecruitment geocoding on **every** address insert/update:

```sql
if( fnd_profile.value('IRC_INSTALLED_FLAG') in ('Y','D')
    and fnd_profile.value('IRC_GEOCODE_HOST') is not null ) then
      p_rec.geometry := irc_location_utility.address2geometry(...)
```

That makes a `UTL_HTTP` call. Many instances still ship the default
`http://elocation.oracle.com/elocation/lbs` — Oracle's **retired** eLocation service — so the call
dies with `ORA-29273: HTTP request failed` / `ORA-29024: Certificate validation failure`, and
**address updates fail through every channel**, including with `p_validate => TRUE`.

**Fix (reversible):**
```sql
fnd_profile.save('IRC_GEOCODE_HOST', NULL, 'SITE');   -- geocoding skipped, only geometry unset
```
Always record the old value first so it can be restored.

---

## OTA (Learning) — why an enrolment gets rejected

Two rejections account for almost every failed `CREATE_DELEGATE_BOOKING`, and **both are data
conditions you can test for in SQL before offering the class to a user**:

| Error | Cause | Pre-check |
|---|---|---|
| `OTA_13583_TDB_NO_ENROLL_DATE` | `SYSDATE` is outside the class's enrolment window | `SYSDATE BETWEEN e.enrolment_start_date AND NVL(e.enrolment_end_date, e.course_start_date)` |
| `OTA_443729_PREREQ_NOT_COMPLETE` | The activity version has prerequisites the delegate has not completed | `NOT EXISTS (SELECT 1 FROM ota_act_prerequisites p WHERE p.activity_version_id = av.activity_version_id)` — or verify completion per person |

> ✅ **Filter the search tool, not the write tool.** Putting both conditions into the *course search*
> query means the model can only ever offer a class that will actually book. Validating inside the
> write and returning an Oracle error code to the user is a far worse experience.

⚠️ **Vision's OTA catalogue is expired.** On this instance every class in BG 202 ended **2013-12-04**,
so a correctly-written search returns **zero rows** and the enrolment path looks broken when it is
not. Confirm with `SELECT MAX(course_end_date) FROM ota_events WHERE business_group_id = :bg` before
concluding your query is wrong.

## Calling EBS through a UnifyApps workflow

When the integration layer is UnifyApps (an `oracledb_execute_sql` node, or an agent tool
backed by one), the platform side has traps of its own that sit on top of the EBS ones here.
They are recorded in the living API spec, `API-SPEC.md` at the root of the `unifyapps-helper`
repo these skills ship from (and in the `unifyapps-builder` skill):

- **§16 Oracle node contract** - binds need **both** `params` (schema) and `record` (values);
  a `record` missing one key **binds NULL silently**; OUT binds (`o_*`) must stay out of
  `record`; and **PL/SQL OUT binds are never returned** - follow every write with a
  verification `SELECT` node.
- **§17 Error catalogue** - e.g. `ORA-17041` is almost always a missing `record` value, not
  bad SQL; `ORA-01017` on an EBS connection means it points at the CDB instead of the PDB.

The spec is additive: everything in this skill works without it.

## Useful schema facts

- **Hire date:** `original_date_of_hire` is often NULL. Use
  `(SELECT MIN(date_start) FROM per_periods_of_service WHERE person_id = ...)`.
- **Phones** live in `PER_PHONES` keyed by `parent_id` + `parent_table='PER_ALL_PEOPLE_F'`,
  not `person_id`. Types: `W1` work, `M` mobile, `H` home.
- **Employee number is not person_id**, and it is only unique **within a business group** — never
  match on it alone across BGs.
- **Vacant position** = a position with no current primary `assignment_type='E'` row.
- Write paths in finance (**AP invoices, GL journals, PO requisitions**) have **no PL/SQL API** —
  they are *interface table + concurrent program* (`FND_REQUEST.SUBMIT_REQUEST`) and therefore
  **asynchronous**. Return the `request_id` and poll `FND_CONCURRENT_REQUESTS`; never model them
  as synchronous writes.

- **Timecards** (`HXC_TIME_BUILDING_BLOCKS`) are a hierarchy, not a flat table: the `DAY` block
  carries the date, its `DETAIL` children carry the hours. Sum the children, joined on
  `parent_building_block_id` + `parent_building_block_ovn`, and filter `date_to = hr_general.end_of_time`
  to get only the latest version of each block.
- **Appraisals** have two sides — `appraiser_person_id` (my team's) and `appraisee_person_id`
  (my own). "Pending" means `PLANNED`. Always join `PER_APPRAISAL_PERIODS`: Vision data spans several
  cycles, and a flat list hides multi-year carry-overs.

## Procurement and Payables (PO / AP / GL)

- **Everything is scoped by operating unit (`org_id`)**, not business group. Vision's main OU is
  **204 = Vision Operations**; GL ledger **1 = Vision Operations (USA)**. Always filter by it, or
  you sum across dozens of unrelated OUs. ✅ This instance has invoices in **38 different org_ids**.
- **Write paths barely exist.** ✅ Verified present: `AP_VENDOR_PUB_PKG` only.
  `PO_REQUISITION_PUB` and `PO_DOCUMENT_APPROVE_PUB` are **not installed**. Requisitions, POs and
  invoices go through interface tables + concurrent programs — `PO_REQUISITIONS_INTERFACE_ALL`
  (`REQIMPORT`), `AP_INVOICES_INTERFACE` + `AP_INVOICE_LINES_INTERFACE` (`APXIIMPT`),
  `POXPOPDOI` — all **asynchronous**. Model them as "submit and poll", never as a synchronous tool.
- **Invoice status is three independent things**, so never infer one from another:
  `payment_status_flag` (`Y` paid / `P` partial / `N` unpaid), `wfapproval_status`, and
  `cancelled_date`. There is **no `approval_status_lookup_code`** column despite the name existing
  elsewhere. An unpaid invoice may simply be **on hold** — join `AP_HOLDS_ALL` where
  `release_lookup_code IS NULL` to find live holds; `hold_reason` carries the human explanation
  (`Invoice amount exceeded limit`, `Total of Invoice Lines does not match`).
- **Line amounts:** `unit_price * quantity` is NULL on service/amount-based lines. Use
  `NVL(unit_price * quantity, amount)` on both `PO_LINES_ALL` and `PO_REQUISITION_LINES_ALL`, or
  large POs silently total zero.
- **A PO is live** when `authorization_status = 'APPROVED'` **and** `NVL(closed_code,'OPEN') = 'OPEN'`.
- **Due dates** live in `AP_PAYMENT_SCHEDULES_ALL`, not on the invoice.
- **Requisition → PO link:** a requisition line with a non-null `line_location_id` has become a PO.
- Vision's transactional data **stops in 2010**, so any "days overdue" calculation returns
  thousands of days. Compute it honestly and label the vintage rather than hiding it.

## Service, letters and end of service

- 🔴 **Never report a salary without its pay basis.** `PER_PAY_PROPOSALS.proposed_salary_n` is an
  amount in the period named by `PER_PAY_BASES.pay_basis` (`MONTHLY`, `ANNUAL`, `HOURLY`…).
  ✅ Vision's Casey Brown is **MONTHLY 13,656.25** — calling that an annual salary in an employment
  or bank letter is a material error. Always return `pay_basis` next to the amount.
- **Salary currency is not on the pay basis.** `PER_PAY_BASES` has **no `currency_code`**. Take it
  from the business group:
  ```sql
  SELECT org_information10 FROM hr_organization_information
   WHERE organization_id = :business_group_id
     AND org_information_context = 'Business Group Information';   -- 'USD'
  ```
- **Length of service:** `MONTHS_BETWEEN(NVL(actual_termination_date, SYSDATE), date_start)/12` over
  `PER_PERIODS_OF_SERVICE`. A person can have several periods — order by `date_start DESC`.
- **Leaving reason** is a code; decode via `HR_LOOKUPS` `lookup_type='LEAV_REAS'`
  (`COMP` Compensation, `BOP` Better Opportunity, `CR` Compulsory Redundancy, `DEATH`, …).
  Values include sensitive ones such as Gross Misconduct and Deceased — report factually.
- **Termination:** `HR_EX_EMPLOYEE_API.ACTUAL_TERMINATION_EMP` needs `p_period_of_service_id` and its
  `p_object_version_number` (derive both from `person_id` inside the block so callers pass only a
  person). All the `p_*_warning` arguments are **PL/SQL BOOLEAN OUT** — declare them as locals, they
  cannot cross JDBC. It is **reversible** via `REVERSE_TERMINATE_EMPLOYEE`, and
  `FINAL_PROCESS_EMP` closes the period afterwards.

## Cash, expenses and corporate cards

- **iExpense claims** are `AP_EXPENSE_REPORT_HEADERS_ALL` / `..._LINES_ALL`, keyed by
  `report_header_id` and scoped by `org_id`. Status `PAID` = reimbursed, `INVOICED` = approved and
  awaiting payment, `NA`/`RESOLUTN`/`ERROR` also occur. The claimant is `employee_id` = `person_id`.
  Line detail (`item_description`, `amount`, `justification`) is what makes a "what did this trip
  cost" answer good.
- **Bank accounts** are `CE_BANK_ACCOUNTS`; the bank name comes from `CE_BANKS_V` joined on
  `bank_party_id = bank_id` (a TCA party, not a bank id). Statements are `CE_STATEMENT_HEADERS` /
  `CE_STATEMENT_LINES`.
- **Corporate cards** are `AP_CARDS_ALL`. There is **no `card_status` column** — derive it from
  `inactive_date`. Programme name is on `AP_CARD_PROGRAMS_ALL`. Never surface `card_number`.

## Vision demo data (this instance)
Ken Walker `person_id 5`, `employee_number 4`, BG **202**, assignment 5, dept 239.
Rob O'Malley `person_id 4` is his supervisor but is a **terminated employee** (assignment ended
1999-09-30) with exactly one direct report — expect thin "team" results and `Ex-employee` in chains.

**Terry Bennett `TBENNETT`, person 166, assignment 165**, BG 202, Recruiting-East — the *manager*
persona, and the only account with data across performance, learning and time: **107 direct reports,
140 appraisals as appraiser, 15 course bookings, 113 timecards** (timecards are dated **2006**).
Use this one for anything hierarchical; Ken Walker has no team and no Phase 4 data at all.

**Casey Brown `CBROWN`, person 31** — the *procurement* persona: **648 requisitions** in org 204.
Vision's biggest preparers are generic accounts (`MFG` person 57 with 10,296 reqs, `OPERATIONS`
person 25); CBROWN is the largest **named** user. Neither KWALKER nor TBENNETT has any.

> **Find the persona before building the tool.** A read tool proven only against a person with no
> rows tells you nothing. Query for the account with the most rows in the target table first —
> `SELECT appraiser_person_id, COUNT(*) FROM per_appraisals GROUP BY … ORDER BY 2 DESC` — and build
> against that. This is the cheapest way to avoid shipping a tool that silently returns `[]`.
