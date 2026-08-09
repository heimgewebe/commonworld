#!/usr/bin/env python3
from pathlib import Path

path = Path('.github/pr203_repair.py')
source = path.read_text(encoding='utf-8')

if '    patch_sources()\n' not in source:
    raise SystemExit('patch_sources call missing')
source = source.replace('    patch_sources()\n', '', 1)

validate_anchor = '''    refresh_evidence()
    run("git", "diff", "--check")
    run("make", "validate")
'''
validate_replacement = '''    refresh_evidence()
    for helper in (
        ROOT / ".github/pr203_repair.py",
        ROOT / ".github/pr203_prepare_final.py",
        ROOT / ".github/pr203_validate_driver.py",
        ROOT / ".github/workflows/pr203-repair.yml",
    ):
        helper.unlink(missing_ok=True)
    run("git", "diff", "--check")
    run("make", "validate")
'''
if validate_anchor not in source:
    raise SystemExit('validation cleanup insertion point missing')
source = source.replace(validate_anchor, validate_replacement, 1)

cleanup_anchor = '''    shutil.rmtree(TMP, ignore_errors=True)
    run("git", "config", "user.name", "Commonworld Repair Bot")
'''
cleanup_replacement = '''    shutil.rmtree(TMP, ignore_errors=True)
    (ROOT / "pr203-repair.log").unlink(missing_ok=True)
    run("git", "config", "user.name", "Commonworld Repair Bot")
'''
if cleanup_anchor not in source:
    raise SystemExit('final cleanup insertion point missing')
source = source.replace(cleanup_anchor, cleanup_replacement, 1)
source = source.replace(
    'run("git", "commit", "-m", "fix: restore coarse-touch ring motion safely")',
    'run("git", "commit", "-m", "fix: harden touch ring browser contract")',
    1,
)
path.write_text(source, encoding='utf-8')
