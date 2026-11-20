"""Dependency-free source structural audit. Not a substitute for Django/Docker tests.

Usage: python scripts/static_audit.py
"""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []

for source in ROOT.rglob("*.py"):
    try:
        ast.parse(source.read_text(encoding="utf8"), filename=str(source))
    except SyntaxError as exc:
        errors.append(f"Python syntax: {source.relative_to(ROOT)}: {exc}")

for source in ROOT.rglob("*.json"):
    try:
        json.loads(source.read_text(encoding="utf8"))
    except json.JSONDecodeError as exc:
        errors.append(f"JSON syntax: {source.relative_to(ROOT)}: {exc}")

url_source = (ROOT / "officeflow" / "urls.py").read_text(encoding="utf8")
url_names = set(re.findall(r'name="([\w-]+)"', url_source))
for template in (ROOT / "templates").rglob("*.html"):
    content = template.read_text(encoding="utf8")
    for name in re.findall(r"{%\s*url\s+'([\w-]+)'", content):
        if name not in url_names:
            errors.append(f"Unknown URL name {name} in {template.relative_to(ROOT)}")
    tokens = re.findall(r"{%\s*(if|for|block|endif|endfor|endblock)\b", content)
    stack = []
    ends = {"endif": "if", "endfor": "for", "endblock": "block"}
    for token in tokens:
        if token in ("if", "for", "block"):
            stack.append(token)
        elif not stack or stack.pop() != ends[token]:
            errors.append(f"Bad template tag nesting in {template.relative_to(ROOT)} ({token})")
    if stack:
        errors.append(f"Unclosed template tags {stack} in {template.relative_to(ROOT)}")

required = [
    "Dockerfile", "compose.yaml", ".github/workflows/ci.yml", "README.md",
    "workspace/services.py", "workspace/api.py", "workspace/migrations/0002_postgres_overlap_guard.py",
    "static/css/app.css", "static/js/app.js", "scripts/loadtest.js",
    "docs/REQUIREMENTS.md", "docs/PILOT.md", "infra/grafana/dashboards/officeflow.json",
    ".env.production.example", "compose.production.yaml", "docker-entrypoint.sh",
    "infra/caddy/Caddyfile", "scripts/backup.sh", "scripts/test-restore.sh",
]
for rel in required:
    if not (ROOT / rel).is_file():
        errors.append(f"Missing required artifact {rel}")

print(f"Python: {len(list(ROOT.rglob('*.py')))} files")
print(f"Templates: {len(list((ROOT / 'templates').rglob('*.html')))} files")
print(f"JSON: {len(list(ROOT.rglob('*.json')))} files")
print(f"Declared HTML URL names: {len(url_names)}")
if errors:
    print("STRUCTURAL AUDIT FAILED")
    for error in errors:
        print(" - " + error)
    raise SystemExit(1)
print("STRUCTURAL AUDIT PASSED (syntax/structure only; Django runtime NOT exercised)")
