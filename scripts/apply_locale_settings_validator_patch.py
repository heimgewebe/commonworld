from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/validate_proposal_path.py"
text = path.read_text(encoding="utf-8")
old = """    if 'href=\"./propose.de.html?ui_lang=de\"' not in page or 'href=\"./propose.html?ui_lang=en\"' not in german_page:
        errors.append(\"proposal locale switch must connect English and German surfaces\")
    for surface, name in ((page, \"propose.html\"), (german_page, \"propose.de.html\")):
        for marker in (
            'data-locale-choice=\"auto\"',
            'data-locale-choice=\"en\"',
            'data-locale-choice=\"de\"',
            'data-locale-effective',
        ):
            if marker not in surface: errors.append(f\"{name} locale control missing marker: {marker}\")
"""
new = """    for surface, name in ((page, \"propose.html\"), (german_page, \"propose.de.html\")):
        for marker in (
            'data-locale-choice=',
            'data-locale-effective',
            'language-switch',
        ):
            if marker in surface:
                errors.append(f\"{name} must not duplicate the global locale control: {marker}\")
"""
if text.count(old) != 1:
    raise RuntimeError("proposal locale validator block drifted")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
