# Context Graph API reference

Verified live on `https://tool.prod-aps1.unifyapps.com`, 2026-09-19, unless a line says
otherwise. All calls are cookie-authenticated against the platform session.

---

## 1. Endpoint inventory

Extracted from the front-end bundle and then exercised. `${e}` etc. are path params.

### Graph

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/context-graph` | **Create.** Body `{name, description}` |
| GET | `/api/context-graph/{graphId}` | Read header |
| POST | `/api/context-graph/update/{graphId}` | Update |
| POST | `/api/context-graph/{graphId}/publish` | **DRAFT -> LIVE** |
| POST | `/api/context-graph/delete/{graphId}` | Delete |
| GET | `/api/context-graph/templates` | Prebuilt graph templates |

### Nodes

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/context-graph/nodes` | **Create node** |
| GET | `/api/context-graph/nodes/{nodeId}` | Full node incl. `properties[]`, `entityMetadata`, `recordTitleFormat` |
| POST | `/api/context-graph/nodes/update/{nodeId}?version={n}` | **Update** - version is a query param |
| POST | `/api/context-graph/nodes/delete/{nodeId}` | Delete |
| POST | `/api/context-graph/nodes/bulk-update-node-positions` | Canvas layout |
| GET | `/api/context-graph/nodes/templates` | Node template catalogue (account, person, ...) |

### Edges (type level)

| Method | Path |
|---|---|
| POST | `/api/context-graph/edges` |
| GET | `/api/context-graph/edges/{edgeId}` |
| POST | `/api/context-graph/edges/update/{edgeId}` |
| POST | `/api/context-graph/edges/delete/{edgeId}` |

### Records and the graph

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/context-graph/{graphId}/nodes/{unifiedEntityId}` | **List records** of a node. Body `{includeTotalHits, page:{limit,offset}}`. Returns flat props plus `_ua_recordTitle`, `labels`, `modelId` |
| GET | `/api/context-graph/{graphId}/unifiedEntity/{ue}/records/{recordId}` | Record + `edges[]` |
| GET | `/api/context-graph/{graphId}/unifiedEntity/{ue}/records/{recordId}/graph?depth=1` | Neighbourhood subgraph |
| GET | `/api/entity/{unifiedEntityId}/{recordId}` | Raw record (`properties{}` incl. `mdmRecordMetadata`) |
| POST | `/api/entity` | **Create record** - `{entityType:<ue>, properties:{...}}` |
| POST | `/api/entity/update` | Update record |

### Sources

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/context-graph/sources` | Create |
| GET/POST | `/api/context-graph/sources/{sourceId}` , `/update/{id}` , `/delete/{id}` | CRUD |
| POST | `/api/context-graph/sources/{sourceId}/publish` | Publish the source pipeline |
| GET | `/api/context-graph/sources/{sourceId}/objects/fetch-selected?limit&offset` | **Per-object config**: `objectSchema`, `enrichedObjectSchemas`, `schemaMappings` |
| POST | `/api/context-graph/sources/{sourceId}/objects/bulkUpdate` | Set selected objects |
| GET/POST | `/api/context-graph/sources/{sourceId}/object-discoveries` | Discovery configs |
| POST | `/api/context-graph/sources/{sourceId}/object-discoveries/discovery-configs/bulk-save` | Save discovery configs |
| POST | `/api/context-graph/sources/{sourceId}/object-discoveries/scope-configs/bulk-save` | Save scope configs |
| GET/POST | `/api/context-graph/sources/{sourceId}/schema-mappings` | Field mappings |
| POST | `/api/context-graph/sources/{sourceId}/schema-mapping/automap` | Auto-map fields |
| POST | `/api/context-graph/sources/{sourceId}/transformations/save` | Transformations |
| GET | `/api/context-graph/sources/{sourceId}/transformations/group-by-source-field` | Transformations by field |
| GET | `/api/context-graph/sources/applications/{appName}/objects` | Objects a connector exposes |
| POST | `/api/context-graph/sources/applications/{appName}/objects/{objectId}/details?connectionId=` | Object schema |
| GET | `/api/context-graph/sources/applications/{appName}/settings` , `/disabled-steps` | Per-app wizard config |
| GET | `/api/context-graph/sources/discoverers/{method}/{agentId}/{n}/schema` | Discovery agent output schema |
| GET | `/api/context-graph/sources/enrichers/{method}/{agentId}/{n}/schema` | Enrichment agent output schema |
| POST | `/api/context-graph/sources/objects/describe` | `{connectionId, objectId, sourceConfigId}` -> destination fields |
| GET | `/api/context-graph/sources/app/{appName}/resource/{resourceId}` | Resource detail |

### Generic query layer

`POST /api/aggregation` is the universal search endpoint.

```json
{ "group": "STANDARD",
  "entityType": "KNOWLEDGE_GRAPH_NODE",
  "projections": [{"name":"id"},{"name":"name"},{"name":"unifiedEntityId"}],
  "filter": {"field":"graphId","op":"EQUAL","values":["<graphId>"]},
  "sorts": [{"field":"name","order":"ASC"}],
  "includeTotalHits": true,
  "page": {"limit":200,"offset":0} }
```

- Returns `{objects:[{columns:{...}}], totalHits, hasMore, cursor}`.
- `projections` is **mandatory** for `group: "ENTITY"` (otherwise
  `Cannot invoke "java.util.List.iterator()" because "projections" is null`).
- `POST /api/aggregation/metadata` with `{group, entityType}` returns the full field list
  for any entity type - the fastest way to discover a schema.
- Operators seen: `AND`, `OR`, `EQUAL`, `NOT_EQUAL`, `IN`, `ICONTAINS`, `EXISTS`, `GT`, `LT`.
- Field abbreviations: `cTm` created, `mTm` modified, `oUId` owner, `lMBy` last modified by,
  `pId` project, `v` version, `lcName` lowercased name.

Lookup endpoint for name search across assets:

```
POST /api/lookup?ByQuery=CONNECTION
{"type":"ByQuery","lookupType":"CONNECTION","query":"<your graph name>","fields":["name"],
 "options":{"appName":"mdm_by_unifyapps"},"page":{"limit":20,"offset":0}}
```

Other `lookupType`s seen: `UNIFIED_ENTITY_MODEL`, `UNIFIED_ENTITY`, `ENTITY`, `USER`,
`TAG`, `ENTITY_PERMISSIONS`, `NODE_BUILDER`.

---

## 2. Entity-type field lists

From `/api/aggregation/metadata`.

**`KNOWLEDGE_GRAPH_NODE`** (group `STANDARD`)
```
id graphId name lcName category color iconUrl description properties propertiesCount
edgeCount recordCount nodePosition unifiedEntityId standard tags spaceId
v cTm mTm oUId pId lMBy lPUBy lPUOn
```

**`KNOWLEDGE_GRAPH_EDGE`**
```
id graphId label lcName description fromNodeId toNodeId entityRelationshipIds[]
standard tags spaceId v cTm mTm oUId pId lMBy lPUBy lPUOn
```

**`KNOWLEDGE_GRAPH_SOURCE`**
```
id graphId name lcName appName connectionId status lastSyncTimeEpochMillis
standard tags spaceId v cTm mTm oUId pId lMBy lPUBy lPUOn
```

---

## 3. Payloads

### Create graph

```json
POST /api/context-graph
{"name": "<YourName> SC Sandbox Graph", "description": "Scratch graph ..."}
```

Response: `{id, status:"DRAFT", nodeCount:1, unifiedEntityModelId:<same as id>, version:1}`.

Two things happen automatically:
- a default node **`ecg_grant`** - *"Default access-grant node added to every context
  graph"* (properties `uid`, `mdmRecordMetadata`). Leave it alone.
- an `mdm_by_unifyapps` **UDM connection** named `<graph name> UDM Connection`, with
  `userInput.unifiedEntityModelId = <graphId>`. Use this connection id for every MDM
  connector node. Do **not** try to create it yourself - `POST /api/connection` rejects a
  hand-rolled one with `No Value found in filter with field: sourceConnectionId`.

### Create node

```json
POST /api/context-graph/nodes
{
  "graphId": "<graphId>",
  "name": "Customer",
  "category": "core",
  "description": "...",
  "iconUrl": "account-executive",
  "nodePosition": {"x": 0, "y": 0},
  "recordTitleFormat": "{{ mdm.field.customer_name }}",
  "properties": [
    {"id":"customer_id","displayName":"Customer Id","dataTypeInfo":{"type":"STRING"},
     "primaryKey":true,"required":true,"unique":false,"pii":false,
     "filterable":false,"sortable":false,"searchable":false,
     "graphQueryable":true,"standard":false},
    {"id":"customer_name","displayName":"Customer Name","dataTypeInfo":{"type":"STRING"},
     "primaryKey":false,"required":false,"unique":false,"pii":false,
     "filterable":false,"sortable":false,"searchable":false,
     "graphQueryable":true,"standard":false}
  ]
}
```

Returns the node with a server-assigned `id` **and** `unifiedEntityId`. Property ids land
in `entityMetadata.graphQueryableFields`, which is what makes them addressable as `_pr_*`
in Cypher. `dataTypeInfo.type` values seen: `STRING`, `DOUBLE`, `BOOLEAN`, `DATE`,
`INTEGER`, `JSON`, `ARRAY`.

### Update node

```
POST /api/context-graph/nodes/update/{nodeId}?version={currentVersion}
<the full node object, modified>
```

### Create edge (type level)

```json
POST /api/context-graph/edges
{"graphId":"<graphId>","label":"WORKS_AT",
 "fromNodeId":"<contact nodeId>","toNodeId":"<customer nodeId>"}
```

There is no join condition here. A type-level edge only declares that the relationship may
exist; it never materialises one.

### Create record

```json
POST /api/entity
{"entityType":"<unifiedEntityId>",
 "properties":{"customer_id":"CUST-001","customer_name":"Northwind Retail Group", "...": "..."}}
```

The record's `id` becomes the primary-key value (`CUST-001`).

### Create a record-level edge

Only through the MDM connector inside a workflow:

```json
{"id":"n_e0","type":"ACTION","title":"CON-001 -[WORKS_AT]-> CUST-001","subTitle":"MDM",
 "context":{"appName":"mdm_by_unifyapps",
            "resourceName":"mdm_by_unifyapps_add_edge_to_graph",
            "resourceVersion":863,
            "connectionId":"<graph UDM connection>","type":"APPLICATION"},
 "inputs":{"modelId":"<graphId>",
           "primaryEntityType":"<contact ue>","primaryEntityId":"CON-001",
           "associatedEntityType":"<customer ue>","associatedEntityId":"CUST-001",
           "label":"WORKS_AT","updateIfPresent":true},
 "groupId":"g1","fallbackMode":"CONTINUE","skip":false,"index":2}
```

Required inputs: `modelId, primaryEntityType, primaryEntityId, associatedEntityType,
associatedEntityId, label`. Output: `{success, fromNodeId, toNodeId}`.

### Cypher query node

```json
{"context":{"appName":"mdm_by_unifyapps",
            "resourceName":"mdm_by_unifyapps_execute_opencypher_query",
            "resourceVersion":2238,
            "connectionId":"<graph UDM connection>","type":"APPLICATION"},
 "inputs":{"modelId":"<graphId>","query":"{{ n_in.outputs.cypherQuery }}",
           "limit":100,"offset":0,"skipRBAC":false}}
```

Required: `query`, `modelId`. Optional: `limit` (1-1000, default 100), `offset`,
`skipRBAC`, `outputSchema`.

---

## 4. Id formats

| Thing | Format | Example |
|---|---|---|
| Vertex | `{spaceId}::{unifiedEntityId}::{recordId}` | `90::6aae7f3c15c388655caf7fa0::CON-001` |
| Record edge | `{fromVertex}::{toVertex}` | `90::ueA::ACC-001::90::ueB::TKT-002` |
| Cypher label | the unifiedEntityId, backticked | ``(c:`6aae7f2cd8c66622aace7fa3`)`` |
| Cypher property | `_pr_` + property id, backticked | ``c.`_pr_customer_name` `` |

`spaceId` `90` is this tenant (`customer.id` from `/api/user-context`).

A record read returns edges like:

```json
{"direction":"OUTGOING","entityType":"<other ue>","isDangling":true,
 "properties":{"edgeLabel":"HAS_TICKET","id":"90::ueA::ACC-001::90::ueB::TKT-002"},
 "recordId":"TKT-002","recordTitle":"AXN-256 - Duplicate Customer Profiles",
 "relationshipId":"HAS_TICKET","relationshipLabel":"HAS_TICKET"}
```

`isDangling: true` appears on instance edges whose endpoints do not correspond to a
declared type-level edge; they still resolve and traverse normally.

---

## 5. MDM record metadata

Records carry `properties.mdmRecordMetadata`:

```
associatedStagingRecordIds[]
contributingSources[]
dataQualityResult{ruleId, warning}
modelId
sourceDetails[{fieldName, sourceAppName, sourceId, stageRecordId, modifiedTime}]
stagingMetadata
```

That is field-level lineage: for each field, which source system and which staging record
it came from. It is what the "best record" screen shows, and it is why the same logical
customer can be assembled from SharePoint + Outlook + Gmail without duplicating the node.

---

## 6. Files on records

Documents attached to records are fetched in two steps:

```
POST /api/file/signed-url?preview=true&expiryTime=1
{"fileDetails":{"fileType":"application/pdf","name":"...pdf","size":54396,
  "source":"connector_streaming_uploads/90/6/<uuid>_AXN-MSA.pdf",
  "sourceType":"CLOUD_STORAGE","ua:type":"FILE"}}
-> {"url":"/api/file/download/__UNIFY_ENCR_AWS__V0__..."}

GET <that url>&isPublic=false&preview=true   -> the bytes
```

---

## 7. UI routes

| Route | Screen |
|---|---|
| `/p/0/context-graphs` | Graph list (+ Create New Graph) |
| `/p/0/context-graphs/{graphId}` | Canvas; `?tab=nodes|edges|sources|records` |
| `/p/0/context-graphs/{graphId}?tab=records&recordNodeId={nodeId}&recordId={recId}` | Best-record screen |
| `/p/0/objects/{unifiedEntityId}/records` , `/schema` | Objects Manager (the same node as a Data Object) |
| `/p/0/automations/{workflowId}` | Automation |
| `/p/0/ai-agents/{agentId}/configuration/{instructions,knowledge,actions,capabilities,topics,ai-models,indexing,...}` | Agent config |
| `/p/0/ai-agents/{agentId}/observability` | Sessions / traces |

The left rail's database icon opens **Enterprise Resources**: Objects Manager, Knowledge,
Code Functions, Templates, Environment Variables.
