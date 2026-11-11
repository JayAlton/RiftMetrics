"""One-time, idempotent patch for RiftMetrics dashboard.py; preserves other tabs."""
import ast
from pathlib import Path

path = Path(__file__).resolve().parent / "dashboard.py"
source = path.read_text(encoding="utf-8")
if "render_live_draft(matches, version)" in source:
    print("Live Draft tab already installed.")
    raise SystemExit(0)

tree = ast.parse(source)
target = None
for node in ast.walk(tree):
    if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
        continue
    fn = node.value.func
    if isinstance(fn, ast.Attribute) and fn.attr == "tabs" and isinstance(fn.value, ast.Name) and fn.value.id == "st":
        if len(node.targets) == 1 and isinstance(node.targets[0], (ast.Tuple, ast.List)) and len(node.value.args) == 1 and isinstance(node.value.args[0], (ast.List, ast.Tuple)):
            target = node
            break
if target is None:
    raise SystemExit("Could not find the dashboard's st.tabs(...) assignment. No files changed.")
if any(isinstance(t, ast.Name) and t.id == "live_draft_tab" for t in target.targets[0].elts):
    raise SystemExit("Live Draft tab seems to exist already; no files changed.")

# Replace only the tabs assignment; leave the rest of dashboard.py untouched.
left = [ast.unparse(x) for x in target.targets[0].elts] + ["live_draft_tab"]
labels = [ast.unparse(x) for x in target.value.args[0].elts] + [repr("🎯 Live Draft")]
replacement = f"{', '.join(left)} = st.tabs([{', '.join(labels)}])"
lines = source.splitlines(keepends=True)
indent = " " * target.col_offset
lines[target.lineno - 1:target.end_lineno] = [indent + replacement + "\n"]
text = "".join(lines)
text += "\n\n# Manual live draft assistant: read-only against matches SQLite.\n"
text += "from riftmetrics.draft_assistant import render_live_draft\n"
text += "with live_draft_tab:\n    render_live_draft(matches, version)\n"
ast.parse(text)
backup = path.with_name("dashboard.before_live_draft.py.bak")
if not backup.exists():
    backup.write_text(source, encoding="utf-8")
path.write_text(text, encoding="utf-8")
print(f"Installed Live Draft tab in {path.name}. Backup: {backup.name}")
