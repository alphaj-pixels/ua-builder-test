# Sources, sync and enrichment - verified payloads

Everything here was captured from live calls on `tool.prod-aps1` (2026-09-19/20).
Companion to `ecg-api.md` (graph/node/edge/record APIs) and `ingestion-and-agents.md`
(the conceptual pipeline).

---

## 1. Registering a source

```http
POST /api/context-graph/sources
{"graphId":"<graphId>","appName":"slack","connectionId":"<connId>","name":"Slack (Read Only)"}
```

The response auto-populates `destinationConnectionId` with the graph's own
`mdm_by_unifyapps` UDM connection. A registered source appears in the Sources tab as
**Draft** and syncs nothing until published.

## 2. Scoping a source  ✅ verified

```http
POST /api/context-graph/sources/{sourceId}/object-discoveries/scope-configs/bulk-save
{"objectDiscoveryConfigEntries":[
  {"objectId":"Message","displayName":"Message",
   "scopeConfig":{"scopeActionId":"slack_index_channels_and_chat",
     "actionInputs":{"token_type":"user_token","channelList":["C0BD6AWDTLH"]}}},
  {"objectId":"File","displayName":"File",
   "scopeConfig":{"scopeActionId":"slack_index_channels_and_chat",
     "actionInputs":{"token_type":"user_token","channelList":["C0BD6AWDTLH"]}}}]}
```

Read it back with `GET /api/context-graph/sources/{sourceId}/object-discoveries`.

> **An empty `channelList` means every public and private channel.** Always set it
> explicitly, even in Draft, so a stray publish can't sweep the workspace.

**Scope support differs per connector.** Slack exposes Visibility, Token type, Channels,
attachments and a date range. HubSpot's only scope option is *"Import companies in
HubSpot"* - wholesale, no record filter. That single fact decides whether a source or an
automation is correct for a given connector.

## 3. Discovery + enrichment config  (shape known, binding unverified)

From the reference SharePoint source:

```json
{"objectId":"File","discoveryEnabled":true,
 "discoveryConfig":{
   "discovererId":"e_...","discovererName":"Discovery Agent","discoveryMethod":"AGENT","version":0,
   "discoveredTypes":[
     {"id":"SOW","displayName":"SOW",
      "filter":{"operator":"AND","filters":[
        {"property":"documentType","filter":{"operator":"ICONTAINS","value":"SOW"}}]}}]},
 "enrichmentConfigsByConnectionObjectId":{
   "SOW":[{"enricherId":"e_...","enricherName":"ECG Enrichment Agent",
           "enrichmentMethod":"AGENT","index":0,"version":13}]}}
```

Posting this to `.../object-discoveries/discovery-configs/bulk-save` returns 200 but the
**enrichment binding did not persist**. Treat the enricher binding as wizard-only until
proven otherwise.

## 4. The Map step - wizard only ⚠

All of these fail:

| Call | Result |
|---|---|
| `POST /sources/{id}/schema-mappings` | 405 |
| `PUT` / `PATCH` same path | 405 |
| `POST /sources/{id}/schema-mapping/automap` | 405 |
| `POST /sources/{id}/objects/bulkUpdate` | 200 but `{"data":0}` - writes nothing |

`GET /sources/{id}/schema-mappings` works and returns `{"objects":[]}`.

The mapping shape itself (from the reference source's `fetch-selected`) is:

```json
{"sourceObjectId":"SOW",
 "destinationNodeId":"<node id>","destinationObjectId":"<unifiedEntityId>",
 "fieldMappings":[{"sourceField":{...},"destinationField":{...}}],
 "associatedEdgeMappings":[]}
```

Note the reference maps 92 enriched fields with **one** fieldMapping - same-named fields
ride along. Name enricher outputs to match node property ids and this step becomes trivial.

**Recommended:** have a human walk the wizard once with a request recorder installed, and
capture the real payload. One pass buys the whole API.

## 5. Field descriptors

Destination fields in the exact shape the mapper expects:

```http
POST /api/context-graph/sources/objects/describe
{"connectionId":"<graph UDM connection>","objectId":"<unifiedEntityId>","sourceConfigId":"<sourceId>"}
-> {"fields":[{autoIncrement,dataTypeInfo,hasDefaultValue,id,name,newField,nullable,primary,unique}]}
```

Source object schema:

```http
POST /api/context-graph/sources/applications/{appName}/objects/{objectId}/details?connectionId=...
{}
```

Raw connector objects return a **nested JSON schema** (`objectSchema.schema.schema.properties`)
plus `fieldsMetadata` with `fieldPaths` like `sourceResponse.response.message.ts`.
Discovered/enriched entities return a **flat `objectSchema.fields` array**. The mapper
consumes the flat form - which is why Discover & Enrich is a prerequisite for Map.

## 6. The ECG connector - pipeline as automation steps

`ecg_by_unifyapps` exposes the pipeline itself:

| Action | Required inputs |
|---|---|
| `run_discovery` | `publishedObjectDiscoveryConfigId`, `rawRecord`, `files[]` |
| `translate_raw_record` | `publishedObjectDiscoveryConfigId`, `rawRecord` |
| `apply_enrichment` | `publishedObjectDiscoveryConfigId`, `objectId`, `rawRecord`, `files[]` |
| `publish_record` | `graphId`, `publishedSourceConfigId`, `objectId`, `rawRecord`, `fileDetails`, `enrichments[]` |

**All four require a published source config**, so they do not bypass the wizard.

## 7. MDM connector - the write path

`mdm_by_unifyapps` (`GET /api/workflow-builder/node/mdm_by_unifyapps/resources`):

| Action | Use |
|---|---|
| `add_edge_to_graph` | **the** way to write a record edge - `{modelId, primaryEntityType, primaryEntityId, associatedEntityType, associatedEntityId, label, updateIfPresent}` |
| `execute_opencypher_query` | read - `{modelId, query, limit (1-1000), offset, skipRBAC}` |
| `execute_opencypher_update` | write via Cypher |
| `create_staging_records`, `apply_data_matching_rules`, `apply_data_quality_rules` | MDM golden-record pipeline |
| `find_by_sql` | SQL over the model |

`primaryEntityType`/`associatedEntityType` are **unifiedEntityIds**; the ids are
**primary-key values** (e.g. `CUST-001`).

Batch size: ~60-70 edge nodes per workflow runs reliably in 25-40s. Larger batches time out
the `initiate-test` HTTP call (the run usually still starts - verify by reading the graph,
not the response).

## 8. Storage connector - records and cleanup

```json
// create - fields go under `record`
{"object_type":"<unifiedEntityId>","record":{"log_id":"x","payload":"..."}}

// delete
{"object_type":"<unifiedEntityId>","numberOfRecordsToDelete":"SINGLE",
 "triggerInputCondition":{"operator":"AND",
   "filters":[{"property":"deal_id","filter":{"operator":"EQUAL","value":"X"}}]}}
```

`DELETE /api/entity/{ue}/{id}` and `POST /api/entity/action/delete` both return 405 -
**use `storage_by_unifyapps_delete_records` in a workflow**.

## 9. Reading workflow results

```http
POST /api/aggregation
{"group":"TEST_WORKFLOW_EXECUTION","entityType":"WORKFLOW_EXECUTION",
 "projections":[{"name":"STATUS"},{"name":"FAILED_NODES"},{"name":"RUN_ID"},
                {"name":"START_NODE_OUTPUT"},{"name":"WORKFLOW_ID"}],
 "filter":{"op":"AND","values":[{"field":"fields.id","op":"EQUAL","values":["<runId>"]}]},
 "page":{"limit":1,"offset":0}}
```

Projection names are **UPPERCASE**; the filter field is **lowercase `fields.id`**. Node
outputs are not exposed here - use the debug-node pattern in `SKILL.md`.

## 10. HubSpot specifics

- Search operator `CONTAINS` is rejected; use **`CONTAINS_TOKEN`**.
- Always request `hs_object_id` explicitly or your primary key is empty and the record
  silently fails to write.
- `hubspot_get_deal` supports **`propertiesWithHistory: ["dealstage"]`** - the only way to
  get stage history, and the basis for a real deal timeline.
- Incremental sync: there is **no "record updated" trigger**. Poll
  `hs_lastmodifieddate > watermark` via `search_records_batch`.
- Custom properties seen in a real portal: `sc_on_this_deal`, `uc_template`,
  `deal_source_new`, `partner_name_new`, `hs_all_collaborator_owner_ids`,
  `hs_v2_date_entered_current_stage`.

## 11. Slack specifics

- Bot token reads **only channels the bot has joined**; private channels need an invite.
  A **user token** reads everything that user can see - set `token_type: "user_token"`.
- `slack_list_conversation_history` returns **top-level messages only**. Thread replies
  need `slack_list_conversations_replies` per `thread_ts` - that is where the decisions are.
- Paging returns far fewer than `limit` (~15-25/page); plan many pages.
- Files carry `external_type: "gdrive"` and `external_id` - **the Drive file id**, so
  Document records can be keyed on it before Drive is even connected.
- `slack_get_user_info_by_id` takes **`user`**, not `userId`. Resolve ids to names or the
  graph is full of `U08FV1BB18R`.
- `slack_get_conversation` takes **`channelId`**; history takes **`channel`**.
- Channels get renamed - key on the channel **id**, never the name.
