// ua_apps.js — run in a logged-in UnifyApps tab (same origin; the session cookie authenticates).
// Paste into the console or execute via a browser tool, then call window.ua.*.
// Every call below was verified on orbit.uat 2026-09-21. No credentials are handled here.
(() => {
  const post = async (url, body) => {
    const r = await fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    const t = await r.text();
    if (!r.ok) throw new Error(`${r.status} ${url}: ${t.slice(0, 400)}`);
    return t ? JSON.parse(t) : null;
  };
  const get = async (url) => {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${r.status} ${url}: ${(await r.text()).slice(0, 400)}`);
    return r.json();
  };

  const ua = {
    // ---------- Objects ----------
    createObject: (id, { name = id, pluralName = id + 's', description = '', tags = [] } = {}) =>
      post('/api/entity-type', { id, name, pluralName, description, metadata: { storeDetails: { store: 'MONGO' } }, tags }),

    getObject: (id) => get(`/api/entity-type?entityType=${encodeURIComponent(id)}`),

    // props: { key: {type, title, format?, oneOf?, primaryKey?, nameField?, searchable?, sortable?, filterable?, ...} }
    setObjectSchema: async (id, props, required = [], extra = {}) => {
      const cur = await ua.getObject(id);
      const S = { type: 'object', properties: props, additionalProperties: false, required };
      return post('/api/entity-type/update', {
        ...cur, ...extra,
        input: { type: 'SCHEMA_AND_LAYOUT', schema: S, layout: { 'ui:order': Object.keys(props) } },
        schema: { dynamic: false, type: 'SCHEMA', schema: S },
      });
    },

    createRecord: (objectId, properties) => post('/api/entity', { entityType: objectId, properties }),
    getRecord: (objectId, id) => get(`/api/entity/${objectId}/${encodeURIComponent(id)}`),
    listRecords: (objectId, filter, { limit = 50, offset = 0, sorts } = {}) =>
      post(`/api/entity/${objectId}`, { ...(filter ? { filter } : {}), ...(sorts ? { sorts } : {}), page: { limit, offset } }),
    // full-replace update: pass the complete properties map
    updateRecord: async (objectId, id, mutate) => {
      const cur = await ua.getRecord(objectId, id);
      return post('/api/entity/update', { id, entityType: objectId, version: cur.version, properties: mutate({ ...cur.properties }) });
    },

    // ---------- Connections ----------
    connectorAuthSpec: (appName) =>
      get(`/api/applications/${appName}?fields=authSpec,iconUrl,displayName,name,refreshable,includeOptions`),
    // body = {name, authType, inputs:{...per authSpec}, options, tags}
    testConnection: (appName, body) => post(`/api/connection/input/test?appName=${appName}`, body), // null (204) = success
    createConnection: (appName, body) => post(`/api/connection/input?appName=${appName}`, body),
    findConnections: async (appName, { activeOnly = true, limit = 50 } = {}) => {
      const values = [{ field: 'appName', op: 'EQUAL', values: [appName] }];
      if (activeOnly) values.push({ field: 'active', op: 'EQUAL', values: [true] });
      const r = await post('/api/aggregation?entityType=Connection&group=STANDARD', {
        entityType: 'Connection', group: 'STANDARD', includeTotalHits: true, filter: { op: 'AND', values },
        projections: [{ name: 'id' }, { name: 'name' }, { name: 'appName' }, { name: 'oUId' }, { name: 'cTm' }],
        sorts: [{ field: 'cTm', order: 'DESC' }], page: { limit, offset: 0 },
      });
      return r.objects.map((o) => o.columns);
    },

    // ---------- Apps / data sources ----------
    callableResourceVersion: async () =>
      (await get('/api/workflow-builder/node/callables/resource/callables_call_automation')).version,

    // Registers an automation for an app. params: names of CALLABLE inputs the app will set.
    createAutomationDataSource: async (appId, name, automationId, params, pageId = `e_global_${appId}`) => {
      const rv = await ua.callableResourceVersion();
      const parameters = Object.fromEntries(params.map((p) => [p, `{{${p}}}`]));
      const ds = await post('/api/entity', {
        entityType: 'e_data_source',
        properties: {
          name, type: 'APPLICATION', interfaceId: appId, interfacePageId: pageId,
          context: { appName: 'callables', resourceName: 'callables_call_automation', resourceVersion: rv },
          inputs: { automationId, version: '-1', runtimeConnections: {}, parameters, synchronous: true },
          dP: params.map((p) => ({ p: `inputs.parameters.${p}` })), dpOn: [], metadata: { isManuallyRenamed: false },
          advancedOptions: { refetchOnWindowFocus: true, timing: { runQueryOnPageLoad: false, runQueryPeriodically: false }, runBehaviour: 'automatic' },
        },
      });
      return { dataSourceId: ds.id, resourceVersion: rv };
    },

    runAutomationDataSource: async (dsId, args, pageSlug) => {
      const ds = await get(`/api/entity/e_data_source/${dsId}`);
      const p = ds.properties;
      return post(`/api/workflow/execute/node?name=${encodeURIComponent(p.name)}&requestId=${dsId}`, {
        context: p.context, id: dsId,
        inputs: { ...p.inputs, parameters: { __internals__: { m: 'PREVIEW', s: pageSlug || `global-page-of-${p.interfaceId}`, c: 'PLATFORM', p: 'browser' }, ...args } },
        options: {},
      }); // -> { response: <STOP result> }
    },

    listPages: (appId) => post('/api/entity/e_component', {
      filter: { op: 'AND', values: [{ field: 'properties.interfaceId', op: 'EQUAL', values: [appId] }, { field: 'properties.componentType', op: 'EQUAL', values: ['PAGE'] }] },
      sorts: [{ field: 'cTm', order: 'ASC' }], page: { limit: 200, offset: 0 },
    }),

    // mutate(properties) edits the page in place; sends the full page back
    updatePage: async (appId, pageId, mutate) => {
      const page = await get(`/api/entity/e_component/${pageId}`);
      mutate(page.properties);
      return post('/api/entity/create-update-or-delete/hierarchical', {
        entity: page, requestType: 'UPDATED', parentEntities: [{ type: 'e_interface', id: appId }],
      });
    },

    deployApp: (appId, deploymentNotes) => post(`/api/entity/e_interface/${appId}/deploy`, { deploymentNotes }),

    // ---------- Code apps (agent-api) — all verified 2026-09-21 ----------
    // Starts the Code Builder agent AND creates the e_interface + domain the session does not create.
    createCodeApp: async (name, brief, { description = '', themeId = 'e_6a8e91f922e51f30962be140' } = {}) => {
      const me = (await get('/api/user-context?includeRoles=true')).user;
      const { appId, sessionId } = await post('/agent-api/sessions', { target: 'code-builder', input: brief, userName: me.name, userEmail: me.email });
      const logo = { small: 'https://assets.unifyapps.com/interface/brand-logo/brand-logo-sm-3-comp.svg', large: 'https://assets.unifyapps.com/interface/brand-logo/brand-logo-lg-4.svg', favicon: 'https://assets.unifyapps.com/interface/brand-logo/brand-logo-sm-3-comp.svg' };
      await post('/api/entity/create-update-or-delete/hierarchical', {
        entity: { id: appId, entityType: 'e_interface', tags: [], properties: {
          type: 'application', name, description, standard: false, manifest: { type: 'WEB', mode: 'code' },
          deviceDetails: { base: 'desktop' }, metadata: { logo, _counter: { _pageCount: 0, _moduleCount: 0, _mqttTopicCounter: 0, _templateComponentCount: 0 } },
          navigation: { primary: [], secondary: [], defaultPageId: '' }, locale: { defaultLocale: 'en-US' },
          theme: { defaultThemeId: themeId }, flags: { shouldReEvaluateUsingEntityIds: true }, chatSessionId: sessionId } },
        requestType: 'CREATED', ignoreVersion: true,
      });
      const host = location.hostname.replace(/^orbit\./, '').replace('.unifyapps.com', ''); // "uat"
      await post('/api/domain-mapping/interface', { domain: `${appId}-orbit.tensor-${host}.unifyapps.com`, module: 'INTERFACE', applicationId: appId });
      return { appId, sessionId };
    },
    // status: 'running' | 'done'
    codeSessionStatus: async (sessionId) => {
      const r = await post('/api/workflow/execute/node?name=fetch_records', { context: { appName: 'storage_by_unifyapps', resourceName: 'storage_by_unifyapps_fetch_records' },
        inputs: { object_type: 'service_hub_case', numberOfRecordsToFetch: 'SINGLE', triggerInputCondition: { operator: 'AND', filters: [{ property: 'id', filter: { operator: 'EQUAL', value: sessionId } }] } } });
      return r.response?.properties?.customProperties?.enginePayload?.status;
    },
    githubOwners: async (connectionId) => (await post('/api/lookup?ByQuery=APPROVED_GITHUB_ORG', {
      type: 'ByQuery', lookupType: 'APPROVED_GITHUB_ORG', options: { connectionId, skipApprovalCheck: true, source_resource_name: 'github_fetch_organizations' }, query: '', page: { limit: 1000, offset: 0 },
    })).response.objects, // [{id:"username:<login>"|<org>, name}]
    linkGithub: (sessionId, connectionId, owner, repo, description = '') => post(`/agent-api/sessions/${sessionId}/git`, {
      provider: 'GITHUB', connectionId, repositoryName: repo, projectName: repo, organizationName: owner,
      createOptions: { autoCreate: true, payload: { visibility: 'private', newRepoName: repo, org: owner, description } },
    }),
    gitStatus: (sessionId) => get(`/agent-api/sessions/${sessionId}/git`),
    appBranches: (appId) => get(`/agent-api/apps/${appId}/branches?offset=0&limit=50&detail=basic`),
    switchBranch: (sessionId, branch) => post(`/agent-api/sessions/${sessionId}/branch`, { branch }), // pulls remote commits
    // writes the working tree only; ask the builder agent to commit afterwards
    saveFiles: async (sessionId, edits) => {
      const r = await fetch(`/agent-api/sessions/${sessionId}/files/contents`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ edits }) });
      if (!r.ok) throw new Error(`${r.status} saveFiles: ${(await r.text()).slice(0, 300)}`);
      return r.json(); // {filesVersion}
    },
    codeCommits: (sessionId) => get(`/agent-api/sessions/${sessionId}/changes`),
    codeFiles: (sessionId) => get(`/agent-api/sessions/${sessionId}/files`),
    codeFile: async (sessionId, path) => (await fetch(`/agent-api/sessions/${sessionId}/files/content?path=${encodeURIComponent(path)}`)).text(),
    codeBranches: (sessionId) => get(`/agent-api/sessions/${sessionId}/branches`),
  };
  window.ua = ua;
  return 'window.ua ready: ' + Object.keys(ua).join(', ');
})();
