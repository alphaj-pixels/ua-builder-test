"""Write migrate_console.js: console_runner.js with bundle.json inlined, ready to paste into DevTools on the target tenant."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
runner = open(os.path.join(HERE, "console_runner.js")).read()
bundle = json.dumps(json.load(open(os.path.join(HERE, "bundle.json"))), separators=(",", ":")).replace("</", "<\\/")
assert runner.count("/*__BUNDLE__*/null") == 1
open(os.path.join(HERE, "migrate_console.js"), "w").write(runner.replace("/*__BUNDLE__*/null", bundle))
print("wrote migrate_console.js", os.path.getsize(os.path.join(HERE, "migrate_console.js")), "bytes")
