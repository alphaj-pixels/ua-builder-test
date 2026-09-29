# Config-based applications (no-code builder)

Verified on UAT 2026-09-21 by building `maher-scratch-cfg` end to end: app → page → data
source → data-bound block → publish, with the page rendering live automation output.

## Object model

```
e_interface  (id = the app slug, e.g. "maher-scratch-cfg"; code apps get "app-<hex>")
 ├─ properties.manifest        {type:"WEB", mode:"config"|"code"}   (mode may be absent on older config apps)
 ├─ properties.navigation      {primary, secondary, defaultPageId, appearance:{SM,MD,LG,XL}}
 ├─ properties.entityDetailsMap {<componentId>: {slug, isPublic, type:"PAGE"|"MODULE", name}}
 ├─ properties.interfacePageIdVsSlugMap, paths.f_root.children[], pagePermissions, publicPageIds
 ├─ properties.security        {type:"PRIVATE"|..., cspData, cspDetails, passwordRestrictions}
 ├─ properties.theme.defaultThemeId → e_theme ;  locale.defaultLocale
 └─ properties.metadata._counter {_pageCount, _moduleCount, _dataSourceCounter, _variableCounter, _functionCounter}

e_component  (one per PAGE / MODULE / TEMPLATE_COMPONENTS)
 ├─ properties.componentType   "PAGE" | "MODULE" | "TEMPLATE_COMPONENTS"
 ├─ properties.interfaceId, name, slug, publicAccess, interfaceType:"application"
 ├─ properties.layout          {header:"header_id", body:"root_id", footer:"footer_id"}
 ├─ properties.blocks          FLAT map blockId → block (tree via parentId + content.blockIds)
 ├─ properties.pageVariables   {var_xxxxx: {id, name, type}}
 ├─ properties.inputSchema / outputSchema  (page inputs, e.g. pageInputs['projectId'])
 └─ properties.customCode, flags, metadata._blockCounter
   special page: e_global_<appId>  (name "global-page-of-<appId>") — app-wide data sources live here

e_data_source  (one per query/mutation)
 ├─ properties.name            used as ?name= on execute
 ├─ properties.context         {appName, resourceName, resourceVersion} — any workflow action
 ├─ properties.inputs          the action's inputs; "{{field}}" marks a runtime-overridable field
 ├─ properties.dP              [{p:"inputs.parameters.x"}] — paths that hold templates
 ├─ properties.interfaceId, interfacePageId (page id, or e_global_<appId>)
 ├─ properties.type            "APPLICATION"
 └─ properties.advancedOptions {runBehaviour:"automatic"|"manual", timing:{runQueryOnPageLoad, runQueryPeriodically}, refetchOnWindowFocus}
```

## A block

```json
"b_tele1": {
  "id": "b_tele1", "displayName": "telemetryTitle", "parentId": "root_id",
  "component": { "componentType": "Typography",
                 "appearance": {"variant":"text-sm","weight":"regular","color":"text-secondary"},
                 "content": {"type":"PLAIN_TEXT", "value":"{{ e_6ab0ebe6f843281fda5f6032['data']['telemetry']['title'] }}"} },
  "visibility": {"value": true},
  "events": [],
  "dataSourceIds": ["e_6ab0ebe6f843281fda5f6032"],
  "dpOn": [{"id":"e_6ab0ebe6f843281fda5f6032","p":["e_6ab0ebe6f843281fda5f6032['data']['telemetry']['title']"]}],
  "dP": [{"p":"content.value"}]
}
```

- Add the block id to its parent's `component.content.blockIds` (keep `"__PLACEHOLDER__"` last).
- `{{ <dsId>['data'][...] }}` reads the data source's `response`. Other scopes seen:
  `pageInputs['x']`, `location['pathname']`, `<blockId>['selectedRow'][...]`.
- `dpOn` = which data sources/paths the block depends on; `dP` = which of its own paths hold
  expressions. `cP` = paths holding conditions.
- Component types seen: Stack, Typography, Table, Form, Card, Button, ButtonGroup, IconButton,
  Icon, Tag, Avatar, Module, Modal, Drawer, Tabs, Repeatable, ProgressBar, Divider, Chart,
  FileUpload, StepperV2, StepIndicator, Checkbox, TextInput, Link, KeyValue, Comments, Loader, Image.
- `additional.customCSS` holds per-block CSS scoped by `[data-block-id='b_x']`.

**Table** — `content.dataSourceId`, `content.data: "{{ ds['data']['result'] }}"`,
`content.columns[] {id, label, fieldKey:{path,key}, type, columnComponentProps}`,
`content.identifier`, `content.rowSelection`, `addOns.page {type:"INFINITE", size}`.

**Form** — `content.schema.schema` (JSON Schema) + `content.schema.layout` (`ui:order`,
`ua:fieldType`, `ui:widget`, e.g. `LookupByDatasourceWidget` with `ua:dataSourceMapping`).

**Events** — `events: [{id, eventType:"onClick"|"onSubmit"|"onRowSelect"|..., action:{id,
actionType, payload, executionType}}]`. Action types seen: `navigateToPage`
(`{pageId, target, pageInputs, history}`), `showNotification` (`{title, type, autoHideDuration}`).
Triggering a data source from an event exists in the UI; its payload is not yet captured.

## Endpoints

| Step | Call | |
|---|---|---|
| Create app | `POST /api/entity/create-update-or-delete/hierarchical` `{entity:{id:<slug>, entityType:"e_interface", tags, properties:{type:"application", name, description, manifest:{type:"WEB"}, deviceDetails:{base:"desktop"}, navigation:{...}, locale, theme:{defaultThemeId}, metadata:{logo, _counter}}}, requestType:"CREATED", ignoreVersion:true}` | ✅ |
| Map its domain | `POST /api/domain-mapping/interface` `{domain:"<slug>-orbit.matrix-uat.unifyapps.com", module:"INTERFACE", applicationId:<slug>}` → 204 | ✅ |
| Create page | same hierarchical endpoint, `entity:{entityType:"e_component", properties:{componentType:"PAGE", interfaceId, name, slug, publicAccess:false, layout, blocks:{header_id,root_id,footer_id}, pageVariables:{}, dataSources:{}, metadata:{_version:2}}}`, `requestType:"CREATED"`, `parentEntities:[{type:"e_interface", id}]`, `postUpdateEntities:[<the app, with entityDetailsMap / navigation.defaultPageId updated; "NEW_ENTITY_ID" as placeholder>]` | 👁 (UI) |
| Global page | the UI creates `e_global_<appId>` (name/slug `global-page-of-<appId>`) with the first page, same call | 👁 |
| Update page | same endpoint, `entity:<full page>`, `requestType:"UPDATED"`, `parentEntities:[{type:"e_interface", id}]` | ✅ |
| List pages/modules | `POST /api/entity/e_component` `{filter:{op:"AND",values:[{field:"properties.interfaceId",op:"EQUAL",values:[appId]},{field:"properties.componentType",op:"EQUAL",values:["PAGE"]}]}, page:{limit:200,offset:0}}` | ✅ |
| Page + its data sources | `POST /api/entity/embedded-entities/e_component` `{entityId, allowedEntityTypes:["e_component","e_data_source","e_interface"]}` | ✅ |
| Create data source | `POST /api/entity` `{entityType:"e_data_source", properties:{...}}` | ✅ |
| Update data source | `POST /api/entity/update` (full properties + version) | ✅ |
| Run data source | `POST /api/workflow/execute/node?name=<name>&requestId=<dsId>` | ✅ |
| Dependencies | `POST /api/entity/entity-dependency` `{entityType:"e_interface", entityId}` | 👁 |
| Publish | `POST /api/entity/e_interface/{appId}/deploy` `{deploymentNotes}` → `deploymentState.version` | ✅ (UI click, captured) |
| Deployed copy | `GET /api/entity/deployed/e_interface/{id}`, `POST /api/entity/deployed/embedded-entities/e_component` (types `e_component_deployed`) | 👁 |
| Versions | `POST /api/aggregation?entityType=EntitySnapshot&group=STANDARD` with `additional:{entityType:"e_interface", entityId}` | 👁 |
| Templates | `POST /api/entity/e_page_template` | 👁 |
| Custom components | `POST /api/entity/e_custom_component` (manifest: `main` .es.js + `style` .css URLs) | 👁 |

## Data source recipes

**Call an automation** (it must be deployed and have a CALLABLE trigger):

```json
{ "entityType": "e_data_source", "properties": {
  "name": "ds_vehicle_telemetry", "type": "APPLICATION",
  "interfaceId": "maher-scratch-cfg", "interfacePageId": "e_global_maher-scratch-cfg",
  "context": {"appName":"callables","resourceName":"callables_call_automation","resourceVersion":3124},
  "inputs": {"automationId":"6aae3aab0900af6ee3a552c0","version":"-1","runtimeConnections":{},
             "parameters":{"vehicleId":"{{vehicleId}}"},"synchronous":true},
  "dP": [{"p":"inputs.parameters.vehicleId"}], "dpOn": [], "metadata": {"isManuallyRenamed": false},
  "advancedOptions": {"refetchOnWindowFocus":true,"timing":{"runQueryOnPageLoad":false,"runQueryPeriodically":false},"runBehaviour":"automatic"} } }
```

Resolve `resourceVersion` live: `GET /api/workflow-builder/node/callables/resource/callables_call_automation` → `.version`.

Execute it:

```json
POST /api/workflow/execute/node?name=ds_vehicle_telemetry&requestId=<dsId>
{ "context": {"appName":"callables","resourceName":"callables_call_automation","resourceVersion":3124},
  "id": "<dsId>",
  "inputs": {"automationId":"6aae3aab0900af6ee3a552c0","version":"-1","runtimeConnections":{},
             "parameters":{"__internals__":{"m":"PREVIEW","s":"global-page-of-<appId>","c":"PLATFORM","p":"browser"},
                           "vehicleId":"V-100"},
             "synchronous":true},
  "options": {} }
→ 200 { "executionInstanceId", "id", "lookupReferences": {}, "response": <the workflow's STOP result> }
```

`__internals__.m` is `BUILDER` / `PREVIEW` at design time; `s` is the page slug.

**Read an object directly** (no automation): `context {appName:"storage_by_unifyapps",
resourceName:"storage_by_unifyapps_fetch_records", resourceVersion}` and inputs
`{object_type, triggerInputCondition:{operator:"AND", filters:[{property:"properties_stage", filter:{operator:"EQUAL", value:"..."}}]}, numberOfRecordsToFetch:"MULTIPLE", page:{paginateBy:"OFFSET", limit}, sortBy:[...], ...}`.
Other storage actions: `_create_record`, `_update_record_by_id`, `_delete_record_by_id`.

## Traps

- The hierarchical endpoint returns an **array** of the saved entities.
- A block referencing a data source must list it in `dataSourceIds` **and** `dpOn`, or it will
  not re-render when data arrives.
- A data source with `runQueryOnPageLoad:false` and `runBehaviour:"automatic"` still ran on
  page load when bound blocks depended on it (observed in the UI); use
  `runBehaviour:"manual"` for mutation-style sources.
- Config-app "Versions" are publish snapshots only — there is no Git for config apps.
- **Page inputs from the URL** (✅ Sales 2026-09-29): `.../preview/<slug>?account_id=C_239&account_name=PhonePe`
  fills `pageInputs['account_id']` / `['account_name']`. This is how an export can render a page for one record.
- **Export a page to PDF**: data source `utility_by_unifyapps_export_unifyapps_pages_to_pdf` with
  `pdfPages[{url, fileName, externalPage:false}]`, `page:{format, layout, scale, timeout}`; button event
  `controlDataSource {dataSourceId, method:"trigger"}`, `callbacks.successEvents` `downloadFile`. Over REST
  `/execute/node` returns no file; inside a workflow the node returns `outputs.file[0].link` (✅, PDF downloaded
  and checked). Use `layout:"landscape"` (portrait A4 is under 900px wide) and `timeout` ≈ 20000 so data loads.
- **Storage data source + JS transformer**: `options.transformerConfig {enabled, includeOriginalOutput, type:"javascript",
  context:{appName:"code_by_unifyapps", resourceName:"code_by_unifyapps_javascript"}, inputs:{code}}`; `data` is the
  fetch output (`data.objects` for MULTIPLE); blocks read the returned object as `{{ ds['data']['x'] }}` (✅).
- **Show/hide on a condition** needs `cP: [{p:"visibility.conditions"}]` as well as the `dP` path, or it is ignored.
- **Repeatable items**: `{{ <repeatableId>['context']['item']['x'] }}` — when generating these in Python never use
  an f-string for the closing `}}` (it collapses to `}` and the block renders the raw expression).
- **Unclosed `/*` in any block's customCSS** silences block CSS that comes after it on that page; put new styles
  in `customCode.header` (`<style>…</style>`) on such pages.
- **Delete an `e_data_source`**: hierarchical endpoint with `requestType:"DELETED"` (✅); `DELETE /api/entity/...` is 405.

