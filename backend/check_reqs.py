from packaging.requirements import Requirement
from importlib.metadata import version, PackageNotFoundError
import sys


def read_requirements(path):
    lines = []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('-r '):
                    include = line.split(None, 1)[1]
                    lines.extend(read_requirements(include))
                    continue
                lines.append(line)
    except FileNotFoundError:
        pass
    return lines


req_lines = read_requirements('requirements.txt')
if not req_lines:
    print('No requirements found in requirements.txt')
    sys.exit(1)

results = []
all_ok = True
for line in req_lines:
    # Skip editable/vcs URLs and options
    if line.startswith('-') or '://' in line or line.startswith('git+') or line.startswith('file:'):
        results.append((line, None, 'UNCHECKABLE'))
        all_ok = False
        continue
    try:
        req = Requirement(line)
    except Exception:
        results.append((line, None, 'INVALID'))
        all_ok = False
        continue
    name = req.name
    spec = req.specifier
    try:
        inst = version(name)
        ok = True
        if spec:
            ok = spec.contains(inst, prereleases=True)
        status = 'OK' if ok else f'VERSION MISMATCH (installed {inst}, required {spec})'
        if not ok:
            all_ok = False
    except PackageNotFoundError:
        inst = None
        status = 'NOT INSTALLED'
        all_ok = False
    results.append((name, inst, status))

# Print a concise table
for name, inst, status in results:
    print(f"{name:30} {inst or '----':12} {status}")

if all_ok:
    print('\nALL_REQUIREMENTS_INSTALLED')
    sys.exit(0)
else:
    print('\nSOME_REQUIREMENTS_MISSING_OR_MISMATCH')
    sys.exit(2)
