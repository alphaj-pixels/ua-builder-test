"""RBAC admin gate: admins / open scope skip the RBAC filters entirely (operator NOT_IN ['__never__']); everyone else IN their list."""
import json, copy
RET_OLD = "return [ids: ids ?: ['__none__'], names: names ?: ['__none__']]"
RET_NEW = ("return [ids: ids ?: ['__none__'], names: names ?: ['__none__'], f_op: open ? 'NOT_IN' : 'IN', "
           "f_ids: open ? ['__never__'] : (ids ?: ['__none__']), f_names: open ? ['__never__'] : (names ?: ['__none__'])]")
def _walk(x, fn):
    if isinstance(x, dict):
        fn(x)
        for v in x.values(): _walk(v, fn)
    elif isinstance(x, list):
        for v in x: _walk(v, fn)
def gate(w):
    w = copy.deepcopy(w); changed = 0
    for n in w["nodes"]:
        if n["id"] == "n_rbids":
            c = n["inputs"]["code"]
            if RET_OLD in c: n["inputs"]["code"] = c.replace(RET_OLD, RET_NEW); changed += 1
            props = n["inputs"].setdefault("output", {}).setdefault("properties", {})
            props.setdefault("f_op", {"type": "string", "title": "f_op"})
            props.setdefault("f_ids", {"type": "array", "items": {"type": "string"}, "title": "f_ids"})
            props.setdefault("f_names", {"type": "array", "items": {"type": "string"}, "title": "f_names"})
    def fix(d):
        nonlocal changed
        f = d.get("filter")
        if isinstance(f, dict) and f.get("operator") == "IN" and f.get("value") in ("{{ n_rbids.outputs.result.ids }}", "{{ n_rbids.outputs.result.names }}"):
            f["value"] = f["value"].replace(".ids }}", ".f_ids }}").replace(".names }}", ".f_names }}")
            f["operator"] = "{{ n_rbids.outputs.result.f_op }}"; changed += 1
    for n in w["nodes"]:
        if n["id"] != "n_rbids": _walk(n.get("inputs"), fix)
    return w, changed
