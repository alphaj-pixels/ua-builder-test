// FDSE utilisation migration, browser version of migrate.py for SSO accounts.
// Run it in DevTools on the TARGET tenant while signed in there; every call rides that tab's own session,
// so no password or identity provider id is needed. build_console.py inlines bundle.json into migrate_console.js.
//
//   await fdseMigrate()                                              // dry run, group fdse: reads only
//   await fdseMigrate({ groups: 'fdse,slack_sync' })                 // include the Slack -> tracker flow
//   await fdseMigrate({ apply: true, app: '<interface id>', conn: { google_workspace: '<connection id>' },
//                       tmSlug, scopeRoot, navModule, reuseExisting, skip: 'fdse_sync' })   // skip also drops callers
//
// Same steps and order as migrate.py. Ids it creates are kept in this browser's localStorage per host, so a rerun
// updates instead of duplicating; fdseMigrate.state() shows them.
(() => {
  const SKEY = 'fdse_migrate_state_' + location.hostname;
  const loadState = () => { try { return JSON.parse(localStorage.getItem(SKEY)) || null; } catch (e) { return null; } };
  let state = loadState() || { workflows: {}, page: null, ds: null };
  const saveState = () => { try { localStorage.setItem(SKEY, JSON.stringify(state)); } catch (e) { console.warn('could not save state', e); } };
  const all = (s, a, b) => s.split(a).join(b);

  async function call(method, path, body) {
    const r = await fetch(path, { method, credentials: 'include', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                                  body: body === undefined ? undefined : JSON.stringify(body) });
    const ct = r.headers.get('content-type') || '', raw = await r.text();
    if (raw && !ct.includes('json')) throw new Error(`HTTP ${r.status} non-JSON (${ct}) - signed out? sign in again`);
    const out = raw ? JSON.parse(raw) : null;
    if (r.status >= 400) throw new Error(`HTTP ${r.status} ${JSON.stringify(out).slice(0, 300)}`);
    return out;
  }
  const RV = {};
  async function resourceVersion(app, res) {
    if (!(app in RV)) {
      try { RV[app] = Object.fromEntries((await call('GET', `/api/workflow-builder/node/${app}/resources`)).objects.map(o => [o.name, o.version])); }
      catch (e) { RV[app] = {}; }
    }
    return RV[app][res] ?? null;
  }
  async function findWorkflow(name) {
    const r = await call('POST', '/api/aggregation?entityType=WorkflowDefinition&group=STANDARD', { entityType: 'WorkflowDefinition', group: 'STANDARD',
      filter: { op: 'EQUAL', field: 'name', values: [name] }, sorts: [], projections: [{ name: 'id' }, { name: 'name' }], page: { limit: 5, offset: 0 } });
    return (r.objects || []).map(o => o.columns.id);
  }
  async function connectionsFor(app) {
    const r = await call('POST', '/api/aggregation?entityType=Connection&group=STANDARD', { entityType: 'Connection', group: 'STANDARD',
      filter: { op: 'AND', values: [{ field: 'appName', op: 'EQUAL', values: [app] }, { field: 'active', op: 'EQUAL', values: [true] }] },
      sorts: [], projections: [{ name: 'id' }, { name: 'name' }], page: { limit: 20, offset: 0 } });
    return (r.objects || []).map(o => [o.columns.id, o.columns.name]);
  }
  async function getType(oid) { try { return await call('GET', `/api/entity-type?entityType=${oid}`); } catch (e) { return null; } }
  function orderWorkflows(keys) {
    const done = new Set(), out = [];
    const visit = k => { if (done.has(k) || !keys.includes(k)) return; done.add(k); for (const c of B.deps[k].calls) visit(c); out.push(k); };
    keys.forEach(visit);
    return out;
  }

  async function fdseMigrate(o = {}) {
    const apply = !!o.apply, conn = o.conn || {}, problems = [], log = s => console.log(s);
    const groups = (Array.isArray(o.groups) ? o.groups : String(o.groups || 'fdse').split(',')).map(g => g.trim()).filter(Boolean);
    for (const g of groups) if (!B.groups[g]) throw new Error(`unknown group ${g}; choose from ${Object.keys(B.groups)}`);
    const me = await call('GET', '/api/user-context?includeRoles=true'), who = (me && me.user) || me || {};
    log(`Target: ${location.hostname} (${me.environment || '?'}) | signed in as ${who.email || who.id} | ${apply ? 'APPLY' : 'DRY RUN'} | groups ${groups}`);
    if (location.hostname === new URL(B.source_host).hostname) {
      log('  note: this is the SOURCE environment' + (apply ? '; refusing to apply.' : '; dry run only.'));
      if (apply) return;
    }

    // 1. objects
    const objects = [...new Set(groups.flatMap(g => B.groups[g].objects))].sort();
    log('\n1. Objects');
    for (const oid of objects) {
      const src = B.objects[oid].schema.schema.properties; let cur = await getType(oid);
      if (!cur) {
        log(`  ${oid}: missing -> create with ${Object.keys(src).length} fields`);
        if (apply) {
          await call('POST', '/api/entity-type', { id: oid, name: oid, pluralName: oid, description: B.objects[oid].description || '',
                                                   metadata: { storeDetails: { store: 'MONGO' } }, tags: [] });
          cur = await getType(oid);
          const props = { ...src }, S = { type: 'object', additionalProperties: true, required: [], properties: props };
          cur.input = { type: 'SCHEMA_AND_LAYOUT', schema: S, layout: { 'ui:order': Object.keys(props) } };
          cur.schema = { dynamic: false, type: 'SCHEMA', schema: S };
          await call('POST', '/api/entity-type/update', cur);
        }
      } else {
        const have = cur.schema.schema.properties, add = Object.fromEntries(Object.entries(src).filter(([k]) => !(k in have))), ak = Object.keys(add);
        log(`  ${oid}: exists, ${Object.keys(have).length} fields` + (ak.length ? ` -> add ${ak.length}: ${ak.slice(0, 12).join(', ')}${ak.length > 12 ? ' …' : ''}` : ', nothing to add'));
        if (apply && ak.length) {
          const props = { ...have, ...add }, S = { type: 'object', additionalProperties: true, required: cur.schema.schema.required || [], properties: props };
          cur.schema.schema = S;
          if (cur.input && cur.input.schema) {
            cur.input.schema = S; cur.input.layout = cur.input.layout || {};
            cur.input.layout['ui:order'] = [...(cur.input.layout['ui:order'] || Object.keys(have)), ...ak];
          }
          await call('POST', '/api/entity-type/update', cur);
        }
      }
      if (oid === 'db_user_management' && groups.includes('fdse')) {
        cur = await getType(oid);
        if (cur && !(cur.metadata || {}).supportsWebhook) {
          log('  db_user_management: record webhooks off -> turn on (needed by the new-user trigger)');
          if (apply) { cur.metadata = cur.metadata || {}; cur.metadata.supportsWebhook = true; await call('POST', '/api/entity-type/update', cur); }
        }
      }
    }

    // 2. workflows
    const keys = orderWorkflows(groups.flatMap(g => B.groups[g].workflows));
    const skip = new Set((Array.isArray(o.skip) ? o.skip : String(o.skip || '').split(',')).map(s => s.trim()).filter(Boolean));
    for (let more = true; more;) {   // skipping a workflow also skips the ones that call it
      more = false;
      for (const k of keys) if (!skip.has(k) && B.deps[k].calls.some(c => skip.has(c))) { skip.add(k); more = true; }
    }
    const linked = {};   // same-name workflows already on the target that are left as they are
    log('\n2. Workflows (called workflows first)');
    for (const k of keys) {
      const w = B.workflows[k];
      if (skip.has(k)) { log(`  [${k}] ${w.name}: skipped`); continue; }
      let existing = state.workflows[k];
      const sameName = existing ? [] : await findWorkflow(w.name);
      if (sameName.length && !o.reuseExisting) {
        linked[k] = sameName[0];
        log(`  [${k}] ${w.name}: already exists as ${sameName[0]}, left as it is (reuseExisting: true replaces it with this version)`);
        continue;
      }
      if (sameName.length) existing = sameName[0];
      const nodes = structuredClone(w.nodes), notes = [];
      for (const n of nodes) {
        const ctx = n.context || {};
        if (ctx.appName && ctx.resourceName) {
          const v = await resourceVersion(ctx.appName, ctx.resourceName);
          if (v === null) problems.push(`${w.name}: step ${n.id} uses ${ctx.appName}/${ctx.resourceName}, not available on the target`);
          else ctx.resourceVersion = v;
        }
        if (ctx.connectionId) {
          const app = ctx.appName; let tgt = conn[app];
          if (!tgt) {
            const c = await connectionsFor(app);
            if (c.length === 1) { tgt = c[0][0]; notes.push(`connection ${app} -> ${c[0][1]}`); }
            else problems.push(`${w.name}: needs a ${app} connection; pass conn: { ${app}: '<id>' } (target has ${c.length}: ${JSON.stringify(c.slice(0, 5).map(x => x[1]))})`);
          }
          if (tgt) ctx.connectionId = tgt;
        }
        const inp = n.inputs || {};
        if (ctx.resourceName === 'callables_call_automation' && inp.automationId) {
          const ck = Object.keys(B.workflows).find(kk => B.workflows[kk].id === inp.automationId);
          if (ck && (state.workflows[ck] || linked[ck])) inp.automationId = state.workflows[ck] || linked[ck];
          else if (ck) notes.push(`call to ${B.workflows[ck].name} remapped once it exists`);
          else problems.push(`${w.name}: calls workflow ${inp.automationId} that is not in the bundle`);
        }
        if (o.scopeRoot && k === 'fdse_page' && typeof inp.code === 'string') inp.code = all(inp.code, 'sumeet@unifyapps.com', o.scopeRoot);
      }
      log(`  [${k}] ${w.name}: ${existing ? 'update ' + existing : 'create'}` + (notes.length ? ` | ${notes.join('; ')}` : ''));
      if (apply) {
        if (!existing) existing = (await call('POST', '/api/workflow-definition', { name: w.name, description: w.description || '', tags: ['DB', 'migrated'],
          nodes: [{ id: 'n_seed', type: 'START', title: 'seed', trigger: { type: 'EVENT' }, index: 0, groupId: 'n_seed-1', fallbackMode: 'STOP', skip: false }], edges: [] })).id;
        state.workflows[k] = existing; saveState();
        const cur = await call('GET', `/api/workflow-definition/${existing}`);
        const r = await call('POST', '/api/workflow-definition/saveAndReturnViolations', { id: existing, name: w.name, description: w.description || '',
          version: cur.version, standard: false, schemaReferences: [], settings: w.settings || {}, tags: ['DB', 'migrated'], nodes, edges: w.edges });
        if (r && r.violations && r.violations.length) throw new Error(`${w.name}: saved with violations, not deploying: ${JSON.stringify(r.violations).slice(0, 400)}`);
        const ver = (await call('GET', `/api/workflow-definition/${existing}`)).version;
        await call('POST', `/api/workflow-definition/${existing}/deploy?version=${ver}`, { deploymentNotes: 'migrated from ' + B.source_host, _type: 'WORKFLOW_DEPLOY_OPTIONS' });
        const dep = ((await call('GET', `/api/workflow-definition/${existing}`)).deploymentState || {}).workflowVersion;
        log(`    saved v${ver}, deployed v${dep}`);
      }
    }

    // 3. page
    if (groups.includes('fdse')) {
      log("\n3. Page 'FDSE utilisation'");
      log(`  access limited to: ${B.page_refs.emails.join(', ')}`);
      log("  Task Management links point at app slug 'task-management-application-clone'" + (o.tmSlug ? ` -> '${o.tmSlug}'` : ' (pass tmSlug if the target app has another slug)'));
      if (!o.app && !state.page) problems.push("page: pass app: '<target interface id>' for the app that should hold the page");
      else if (apply) {
        const appId = o.app; let pid = state.page;
        if (!pid) {
          const props = { componentType: 'PAGE', interfaceId: appId, name: 'FDSE utilisation', slug: 'fdse-utilisation', publicAccess: false, interfaceType: 'application',
            documentTitle: 'FDSE utilisation', layout: { body: 'root_id', header: 'header_id', footer: 'footer_id' }, blocks: {}, pageVariables: {}, dataSources: {},
            flags: { shouldUseBuiltDependencies: true }, eligibleOverrides: [], inputSchema: B.page.properties.inputSchema,
            outputSchema: { type: 'SCHEMA_AND_LAYOUT', dynamic: false }, metadata: { _version: 2 } };
          let appent = await call('GET', `/api/entity/e_interface/${appId}`);
          appent.properties.entityDetailsMap = { ...(appent.properties.entityDetailsMap || {}),
            NEW_ENTITY_ID: { slug: 'fdse-utilisation', isPublic: false, type: 'PAGE', name: 'FDSE utilisation' } };
          let res = await call('POST', '/api/entity/create-update-or-delete/hierarchical', { entity: { entityType: 'e_component', properties: props }, requestType: 'CREATED',
            parentEntities: [{ type: 'e_interface', id: appId }], postUpdateEntities: [appent] });
          res = Array.isArray(res) ? res : [res];
          pid = res.map(x => x.id || '').find(id => id.startsWith('e_') && id !== appId);
          if (!pid) throw new Error('page create returned no page id: ' + JSON.stringify(res).slice(0, 300));
          appent = await call('GET', `/api/entity/e_interface/${appId}`); const edm = appent.properties.entityDetailsMap || {};
          if (edm.NEW_ENTITY_ID) { edm[pid] = edm.NEW_ENTITY_ID; delete edm.NEW_ENTITY_ID; await call('POST', '/api/entity/update', appent); }
          state.page = pid; saveState();
        }
        const dsp = structuredClone(B.data_source.properties);
        Object.assign(dsp, { interfaceId: appId, interfacePageId: pid }); dsp.inputs.automationId = state.workflows.fdse_page;
        if (!state.ds) { state.ds = (await call('POST', '/api/entity', { entityType: 'e_data_source', properties: dsp })).id; saveState(); }
        const curDs = await call('GET', `/api/entity/e_data_source/${state.ds}`);
        await call('POST', '/api/entity/update', { ...curDs, properties: dsp });
        let txt = JSON.stringify(Object.fromEntries(['blocks', 'pageVariables', 'customCode', 'metadata'].map(k => [k, B.page.properties[k] ?? null])));
        txt = all(all(txt, B.data_source.id, state.ds), B.page.id, pid);
        if (o.tmSlug) txt = all(txt, 'task-management-application-clone', o.tmSlug);
        const page = (await call('POST', '/api/entity/embedded-entities/e_component', { entityId: pid, allowedEntityTypes: ['e_component'] })).entity;
        Object.assign(page.properties, JSON.parse(txt));
        await call('POST', '/api/entity/create-update-or-delete/hierarchical', { entity: page, requestType: 'UPDATED', parentEntities: [{ type: 'e_interface', id: appId }] });
        log(`  page ${pid} with data source ${state.ds}`);
      }
      if (o.navModule && apply && state.page) {
        const m = (await call('POST', '/api/entity/embedded-entities/e_component', { entityId: o.navModule, allowedEntityTypes: ['e_component'] })).entity;
        const blocks = m.properties.blocks;
        if (!blocks.b_nav_fu_item) {
          const nb = JSON.parse(all(JSON.stringify(B.nav_blocks), B.page.id, state.page));
          const right = Object.values(blocks).find(b => ((b.component || {}).content || {}).blockIds != null && b.id === 'b_nav_right');
          if (!right) problems.push("nav: the module has no 'b_nav_right' container; add the nav item by hand");
          else {
            Object.assign(blocks, nb); const ids = right.component.content.blockIds; ids.splice(ids.length - 1, 0, 'b_nav_fu_item');
            nb.b_nav_fu_item.parentId = 'b_nav_right';
            await call('POST', '/api/entity/create-update-or-delete/hierarchical', { entity: m, requestType: 'UPDATED', parentEntities: [{ type: 'e_interface', id: o.app }] });
            log('  nav item added');
          }
        }
      }
    }

    log(problems.length ? '\nNeeds attention:' : '\nNo blockers found.');
    for (const p of problems) log('  - ' + p);
    if (!apply) log('\nDry run only: nothing was written.');
    return { problems, state: structuredClone(state) };
  }
  fdseMigrate.state = () => structuredClone(state);
  fdseMigrate.resetState = () => { state = { workflows: {}, page: null, ds: null }; saveState(); };
  window.fdseMigrate = fdseMigrate;

  const B = /*__BUNDLE__*/null;
  console.log(`fdseMigrate ready (bundle exported from ${B.source_host}). Dry run: await fdseMigrate()`);
})();
