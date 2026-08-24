import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.render_public_shell import (
    LANGUAGE_NATIVE_NAMES, MODULE_IMPORT_DEPENDENCIES, ORBIT_PROFILES, RECOVERY_PAGE_SIZE, activity_notice, catalog_language_codes, language_option_direction, load_records, orbit_path_data, render_bootstrap_catalog, render_cards, render_shell,
)
from scripts.static_surface_parser import (
    find_css_block,
    find_media_block,
    parse_presence_group,
    parse_stylesheet_links,
)
from scripts.validate_public_shell import ROOT, validate_public_shell


class PublicShellTests(unittest.TestCase):
    def refresh_app_version(self, root: Path) -> None:
        version = hashlib.sha256((root / "assets/commonworld-app.js").read_bytes()).hexdigest()[:12]
        path = root / "index.html"
        html = re.sub(
            r'\./assets/commonworld-app\.js\?v=[0-9a-f]{12}',
            f'./assets/commonworld-app.js?v={version}',
            path.read_text(encoding="utf-8"),
            count=1,
        )
        path.write_text(html, encoding="utf-8")

    def refresh_ipad_version(self, root: Path) -> None:
        version = hashlib.sha256((root / "assets/ipad-layout.css").read_bytes()).hexdigest()[:12]
        path = root / "index.html"
        html = re.sub(
            r'\./assets/ipad-layout\.css\?v=[0-9a-f]{12}',
            f'./assets/ipad-layout.css?v={version}',
            path.read_text(encoding="utf-8"),
            count=1,
        )
        path.write_text(html, encoding="utf-8")

    def copy_shell(self, tmp_dir: str) -> Path:
        root = Path(tmp_dir)
        shutil.copy2(ROOT / "index.html", root / "index.html")
        shutil.copy2(ROOT / "index.css", root / "index.css")
        shutil.copy2(ROOT / "method.html", root / "method.html")
        (root / "assets").mkdir()
        for asset in (
            "commonworld-bootstrap-catalog.mjs",
            "commonworld-catalog-runtime.mjs",
            "commonworld-i18n.mjs",
            "commonworld-en-locale.mjs",
            "commonworld-locale-registry.mjs",
            "commonworld-wave1-locales.mjs",
            "commonworld-locale.mjs",
            "commonworld-core.mjs",
            "commonworld-app.js",
            "ipad-layout.css",
            "vendor/mapbox-gl-rtl-text.js",
        ):
            target = root / "assets" / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / "assets" / asset, target)
        (root / "scripts").mkdir()
        if (ROOT / "scripts/render_public_shell.py").exists():
            shutil.copy2(ROOT / "scripts/render_public_shell.py", root / "scripts/render_public_shell.py")
        return root

    def test_public_shell_validates(self) -> None:
        self.assertEqual([], validate_public_shell(ROOT))

    def test_locale_index_brand_resets_within_the_current_surface(self) -> None:
        expected = {
            "en": "./",
            "de": "./de.html",
            "es": "./es.html",
            "fr": "./fr.html",
            "pt-BR": "./pt-BR.html",
            "ar": "./ar.html",
        }
        for locale, href in expected.items():
            with self.subTest(locale=locale):
                markup = render_shell(locale=locale)
                self.assertIn(f'<a class="brand" href="{href}"', markup)
                self.assertIn('id="semantic-breadcrumb-accessible" class="visually-hidden"', markup)

    def test_catalog_counts_use_build_count_and_locale_noun(self) -> None:
        count = len(load_records(ROOT))
        arabic = render_shell(locale="ar")
        self.assertIn(f'id="discovery-count" class="discovery-count" role="status">{count} المشاعات</p>', arabic)
        self.assertIn(f'id="text-count" class="text-count">{count} المشاعات</p>', arabic)
        self.assertNotIn(f'{count} Commons', arabic)

    def test_language_filter_is_derived_from_catalog_content_languages(self) -> None:
        codes = catalog_language_codes(load_records(ROOT))
        self.assertGreater(len(codes), 2)
        for locale in ("de", "en", "es", "fr", "pt-BR", "ar"):
            markup = render_shell(locale=locale)
            match = re.search(r'<select id="filter-language"[^>]*>(.*?)</select>', markup, re.S)
            self.assertIsNotNone(match, locale)
            option_markup = re.findall(r'<option ([^>]*)>(.*?)</option>', match.group(1), re.S)
            values = [re.search(r'value="([^"]*)"', attrs).group(1) for attrs, _ in option_markup]
            self.assertEqual(values, ["", *codes, "unknown"], locale)
            labels = {value: label for value, (_, label) in zip(values, option_markup)}
            for code in codes:
                self.assertEqual(labels[code], LANGUAGE_NATIVE_NAMES.get(code, code), (locale, code))
                attrs = next(attrs for attrs, _ in option_markup if f'value="{code}"' in attrs)
                self.assertIn(f'lang="{code}"', attrs, (locale, code))
                self.assertIn(f'dir="{language_option_direction(code)}"', attrs, (locale, code))

    def test_filter_layout_renderer_uses_compact_semantic_structure(self) -> None:
        german = render_shell(locale="de")
        english = render_shell(locale="en")

        for markup in (german, english):
            self.assertIn('class="filter-group filter-group--purpose"', markup)
            self.assertIn('class="filter-group filter-group--location"', markup)
            self.assertIn('class="location-filter-layout"', markup)
            self.assertIn('id="advanced-filters" class="advanced-filters"', markup)
            self.assertNotIn('id="advanced-filters" class="advanced-filters" open', markup)
            self.assertRegex(
                markup,
                r'<button id="filter-sections-toggle"[^>]*aria-hidden="true"[^>]*hidden>',
            )

        self.assertIn('<legend>Erforderliche Präsenz</legend>', german)
        self.assertIn('gemeinsam erfüllt sein (UND)', german)
        self.assertIn('<option value="auto">Empfohlen</option>', german)
        self.assertIn('id="filter-nearby-radius" disabled', german)
        self.assertIn('Land und Umkreis schließen sich aus', german)
        self.assertIn('<legend>Required presence</legend>', english)
        self.assertIn('all be present (AND)', english)
        self.assertIn('<option value="auto">Recommended</option>', english)
        self.assertIn('Country and radius are mutually exclusive', english)

    def test_filter_layout_css_contract_is_bounded_and_responsive(self) -> None:
        stylesheet = (ROOT / "index.css").read_text(encoding="utf-8")
        self.assertIn("/* Filter layout semantics v1 */", stylesheet)
        self.assertIn("width: min(56rem, calc(100% - 2rem));", stylesheet)
        self.assertIn(".filter-group--location,\n.advanced-filters", stylesheet)
        self.assertIn("@media (max-width: 48rem)", stylesheet)
        self.assertIn("@media (max-width: 34rem)", stylesheet)
        ipad_stylesheet = (ROOT / "assets/ipad-layout.css").read_text(encoding="utf-8")
        self.assertIn("width: min(56rem, calc(100% - 1.5rem));", ipad_stylesheet)
        self.assertNotIn("width: min(64rem, calc(100% - 1.5rem));", ipad_stylesheet)

    def test_local_module_graph_is_content_versioned(self) -> None:
        for module_path, dependencies in MODULE_IMPORT_DEPENDENCIES:
            source = (ROOT / module_path).read_text(encoding="utf-8")
            for dependency_path in dependencies:
                version = hashlib.sha256((ROOT / dependency_path).read_bytes()).hexdigest()[:12]
                versioned_specifier = f"./{Path(dependency_path).name}?v={version}"
                self.assertTrue(
                    f"from '{versioned_specifier}'" in source
                    or f"import('{versioned_specifier}')" in source
                )

    def test_wave1_candidate_pack_is_loaded_dynamically(self) -> None:
        source = (ROOT / "assets/commonworld-i18n.mjs").read_text(encoding="utf-8")
        version = hashlib.sha256((ROOT / "assets/commonworld-wave1-locales.mjs").read_bytes()).hexdigest()[:12]
        specifier = f"./commonworld-wave1-locales.mjs?v={version}"
        self.assertIn(f"import('{specifier}')", source)
        self.assertNotIn(f"from '{specifier}'", source)

    def test_public_shell_rejects_stale_transitive_module_import(self) -> None:
        for replacement, observed in (
            ("./commonworld-i18n.mjs?v=000000000000", "000000000000"),
            ("./commonworld-i18n.mjs", "<missing>"),
        ):
            with self.subTest(observed=observed), tempfile.TemporaryDirectory() as tmp_dir:
                root = self.copy_shell(tmp_dir)
                core_path = root / "assets/commonworld-core.mjs"
                i18n_path = root / "assets/commonworld-i18n.mjs"
                expected = hashlib.sha256(i18n_path.read_bytes()).hexdigest()[:12]
                core_path.write_text(
                    core_path.read_text(encoding="utf-8").replace(
                        f"./commonworld-i18n.mjs?v={expected}",
                        replacement,
                        1,
                    ),
                    encoding="utf-8",
                )
                core_version = hashlib.sha256(core_path.read_bytes()).hexdigest()[:12]
                app_path = root / "assets/commonworld-app.js"
                app_source = app_path.read_text(encoding="utf-8")
                app_source = re.sub(
                    r"\./commonworld-core\.mjs\?v=[0-9a-f]{12}",
                    f"./commonworld-core.mjs?v={core_version}",
                    app_source,
                    count=1,
                )
                app_path.write_text(app_source, encoding="utf-8")
                self.refresh_app_version(root)
                errors = validate_public_shell(root)

                self.assertIn(
                    "public shell module import is not content-bound: "
                    "assets/commonworld-core.mjs -> assets/commonworld-i18n.mjs; "
                    f"observed token: {observed}; expected token: {expected}",
                    errors,
                )
                self.assertNotIn(tmp_dir, "\n".join(errors))

    def test_public_shell_accepts_supported_double_quoted_module_import_forms(self) -> None:
        cases = (
            (
                "static",
                "assets/commonworld-core.mjs",
                "assets/commonworld-i18n.mjs",
                "from './commonworld-i18n.mjs?v={token}'",
                'from "./commonworld-i18n.mjs?v={token}"',
            ),
            (
                "dynamic-with-whitespace",
                "assets/commonworld-i18n.mjs",
                "assets/commonworld-wave1-locales.mjs",
                "import('./commonworld-wave1-locales.mjs?v={token}')",
                'import(   "./commonworld-wave1-locales.mjs?v={token}")',
            ),
        )
        for name, module_path, dependency_path, before_template, after_template in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp_dir:
                root = self.copy_shell(tmp_dir)
                dependency = root / dependency_path
                expected = hashlib.sha256(dependency.read_bytes()).hexdigest()[:12]
                module = root / module_path
                source = module.read_text(encoding="utf-8")
                before = before_template.format(token=expected)
                after = after_template.format(token=expected)
                self.assertIn(before, source)
                module.write_text(source.replace(before, after, 1), encoding="utf-8")

                errors = validate_public_shell(root)
                prefix = f"public shell module import is not content-bound: {module_path} -> {dependency_path};"
                self.assertFalse(any(error.startswith(prefix) for error in errors), errors)

    def test_public_shell_reports_stale_tokens_for_supported_double_quoted_import_forms(self) -> None:
        cases = (
            (
                "static",
                "assets/commonworld-core.mjs",
                "assets/commonworld-i18n.mjs",
                "from './commonworld-i18n.mjs?v={token}'",
                'from "./commonworld-i18n.mjs?v={token}"',
                "111111111111",
            ),
            (
                "dynamic-with-whitespace",
                "assets/commonworld-i18n.mjs",
                "assets/commonworld-wave1-locales.mjs",
                "import('./commonworld-wave1-locales.mjs?v={token}')",
                'import(   "./commonworld-wave1-locales.mjs?v={token}")',
                "222222222222",
            ),
        )
        for name, module_path, dependency_path, before_template, after_template, observed in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp_dir:
                root = self.copy_shell(tmp_dir)
                dependency = root / dependency_path
                expected = hashlib.sha256(dependency.read_bytes()).hexdigest()[:12]
                module = root / module_path
                source = module.read_text(encoding="utf-8")
                before = before_template.format(token=expected)
                after = after_template.format(token=observed)
                self.assertIn(before, source)
                module.write_text(source.replace(before, after, 1), encoding="utf-8")

                errors = validate_public_shell(root)
                self.assertIn(
                    f"public shell module import is not content-bound: {module_path} -> {dependency_path}; "
                    f"observed token: {observed}; expected token: {expected}",
                    errors,
                )
                self.assertNotIn(tmp_dir, "\n".join(errors))

    def test_public_shell_rejects_old_proof_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(path.read_text(encoding="utf-8") + "\n<p>Proof hub</p>\n", encoding="utf-8")

            errors = validate_public_shell(root)

        self.assertIn("public shell contains obsolete or unsafe token: proof hub", errors)

    def test_public_shell_requires_digital_sphere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(path.read_text(encoding="utf-8").replace('class="digital-sphere"', 'class="orbit"'), encoding="utf-8")

            errors = validate_public_shell(root)

        self.assertIn('public shell missing required token: class="digital-sphere"', errors)

    def test_digital_sphere_orbits_are_deterministic_svg_paths(self) -> None:
        markup = render_shell(locale="en")
        self.assertNotIn('<ellipse id="sphere-path-', markup)
        self.assertEqual(len(ORBIT_PROFILES), markup.count('<path id="sphere-path-'))
        for index, (rx, ry, rotation) in enumerate(ORBIT_PROFILES, start=1):
            expected = (
                f'<path id="sphere-path-{index}" d="{orbit_path_data(rx, ry)}" '
                f'transform="rotate({rotation} 320 320)" />'
            )
            self.assertEqual(1, markup.count(expected))
        self.assertEqual(
            "M 4 320 A 316 300 0 1 1 636 320 A 316 300 0 1 1 4 320 Z",
            orbit_path_data(316, 300),
        )

    def test_bootstrap_catalog_is_a_deterministic_module_not_dom_text(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        module = (ROOT / "assets/commonworld-bootstrap-catalog.mjs").read_text(encoding="utf-8")
        self.assertNotIn('id="catalog-bootstrap"', html)
        self.assertEqual(render_bootstrap_catalog(load_records(ROOT)), module)
        self.assertTrue(module.startswith("// Generated by scripts/render_public_shell.py"))
        self.assertIn("export const BOOTSTRAP_RECORDS = [", module)

    def test_linear_catalog_fallback_is_independent_and_removed_only_after_boot(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        app = (ROOT / "assets/commonworld-app.js").read_text(encoding="utf-8")
        self.assertEqual(1, html.count('id="static-catalog-fallback"'))
        self.assertNotIn("<noscript", html.casefold())
        self.assertIn('id="text-skip-link" class="skip-link" href="/#static-catalog-fallback"', html)
        self.assertIn('id="static-catalog-fallback" class="static-catalog-fallback" tabindex="-1"', html)
        fallback = html.split('id="static-catalog-fallback"', 1)[1]
        self.assertEqual(min(RECOVERY_PAGE_SIZE, len(load_records(ROOT))), fallback.count('class="catalog-card"'))
        self.assertIn(f'data-recovery-page-size="{RECOVERY_PAGE_SIZE}"', html)
        self.assertIn('entries remain available here while the interactive view is loading or unavailable.', html)
        self.assertIn('href="catalog/"', fallback)
        self.assertNotIn('href="/catalog/', fallback)
        self.assertIn("catalog?.querySelectorAll('.catalog-card[data-commonproject-id]')", app)
        self.assertNotIn("document.querySelectorAll('.catalog-card[data-commonproject-id]')", app)
        self.assertIn("const recoveryCatalog = document.querySelector('[data-static-catalog-fallback]')", app)
        self.assertIn("recoveryCatalog.dataset.skipActivated = 'true'", app)
        self.assertIn("recoveryCatalog.focus({ preventScroll: true })", app)
        self.assertIn("recoveryCatalog.scrollIntoView({ block: 'start' })", app)
        css = (ROOT / 'index.css').read_text(encoding='utf-8')
        self.assertIn('.static-catalog-fallback:target,', css)
        self.assertIn('.static-catalog-fallback[data-skip-activated="true"]', css)
        self.assertIn("target.hash = 'text-view'", app)
        self.assertIn("document.querySelector('[data-static-catalog-fallback]')?.remove()", app)

    def test_public_shell_rejects_missing_linear_catalog_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(
                path.read_text(encoding="utf-8").replace('id="static-catalog-fallback"', 'id="catalog-lost"', 1),
                encoding="utf-8",
            )
            errors = validate_public_shell(root)
        self.assertIn('public shell missing required token: id="static-catalog-fallback"', errors)

    def test_public_shell_rejects_fallback_inside_noscript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    '<section id="static-catalog-fallback"',
                    '<noscript><section id="static-catalog-fallback"',
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_shell(root)
        self.assertIn('public shell contains obsolete or unsafe token: <noscript', errors)

    def test_public_shell_rejects_wrong_fallback_skip_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'id="text-skip-link" class="skip-link" href="/#static-catalog-fallback"',
                    'id="text-skip-link" class="skip-link" href="/#text-view"',
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_shell(root)
        self.assertIn(
            'public shell missing required token: id="text-skip-link" class="skip-link" href="/#static-catalog-fallback"',
            errors,
        )

    def test_public_shell_rejects_missing_fragment_recovery_reveal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            css_path = root / 'index.css'
            css_path.write_text(
                css_path.read_text(encoding='utf-8').replace(
                    '.static-catalog-fallback:target,',
                    '.static-catalog-fallback[data-missing-fragment-target],',
                    1,
                ),
                encoding='utf-8',
            )
            errors = validate_public_shell(root)
        self.assertIn('public shell CSS missing required token: .static-catalog-fallback:target,', errors)

    def test_public_shell_rejects_global_catalog_card_filtering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            app_path = root / "assets/commonworld-app.js"
            app_path.write_text(
                app_path.read_text(encoding="utf-8").replace(
                    "catalog?.querySelectorAll('.catalog-card[data-commonproject-id]')",
                    "document.querySelectorAll('.catalog-card[data-commonproject-id]')",
                    1,
                ),
                encoding="utf-8",
            )
            self.refresh_app_version(root)
            errors = validate_public_shell(root)
        self.assertIn('runtime catalog filtering must not mutate the bootstrap recovery surface', errors)

    def test_public_shell_rejects_missing_recovery_skip_focus_route(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            app_path = root / "assets/commonworld-app.js"
            app_path.write_text(
                app_path.read_text(encoding="utf-8").replace(
                    "const recoveryCatalog = document.querySelector('[data-static-catalog-fallback]')",
                    "const recoveryCatalog = null",
                    1,
                ),
                encoding="utf-8",
            )
            self.refresh_app_version(root)
            errors = validate_public_shell(root)
        self.assertIn(
            "public shell runtime missing bootstrap-recovery handoff: const recoveryCatalog = document.querySelector('[data-static-catalog-fallback]')",
            errors,
        )

    def test_public_shell_rejects_failure_claim_in_recovery_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'entries remain available here while the interactive view is loading or unavailable.',
                    'The interactive globe is unavailable.',
                    1,
                ),
                encoding="utf-8",
            )
            errors = validate_public_shell(root)
        self.assertIn(
            'public shell missing required token: entries remain available here while the interactive view is loading or unavailable.',
            errors,
        )

    def test_public_shell_rejects_missing_recovery_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            app_path = root / "assets/commonworld-app.js"
            app_path.write_text(
                app_path.read_text(encoding="utf-8").replace(
                    "document.querySelector('[data-static-catalog-fallback]')?.remove()",
                    "document.querySelector('[data-static-catalog-fallback]')",
                    1,
                ),
                encoding="utf-8",
            )
            self.refresh_app_version(root)
            errors = validate_public_shell(root)
        self.assertIn(
            "public shell runtime missing bootstrap-recovery handoff: document.querySelector('[data-static-catalog-fallback]')?.remove()",
            errors,
        )

    def test_candidate_static_content_and_dates_keep_explicit_bidi_boundaries(self) -> None:
        arabic = render_shell(locale="ar")
        self.assertIn('<h2 lang="en" dir="ltr">', arabic)
        self.assertIn('<h2 dir="auto">', arabic)
        self.assertIn('<p lang="ar" dir="auto">', arabic)
        unknown = next(record for record in load_records(ROOT) if record.get("activity", {}).get("status") == "unknown")
        notice = activity_notice(unknown, "ar")
        self.assertIn("\u2068", notice)
        self.assertIn("\u2069", notice)

    def test_unknown_activity_notice_is_rendered_in_static_cards(self) -> None:
        records = load_records(ROOT)
        unknown_records = [record for record in records if record.get("activity", {}).get("status") == "unknown"]
        self.assertGreater(len(unknown_records), 0)
        self.assertTrue(all(activity_notice(record) for record in unknown_records))
        html = render_cards(records, interactive=False)
        self.assertEqual(len(unknown_records), html.count('class="catalog-activity-notice"'))
        self.assertEqual(len(unknown_records), html.count("Aktueller Betriebszustand nicht zeitnah verifiziert"))

    def test_public_shell_rejects_dom_embedded_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    '<main class="app-shell">',
                    '<template id="catalog-bootstrap">[]</template><main class="app-shell">',
                ),
                encoding="utf-8",
            )
            errors = validate_public_shell(root)
        self.assertIn("public shell must not embed catalog JSON in the DOM", errors)

    def test_public_shell_uses_local_scripts_and_no_form(self) -> None:
        html = (ROOT / "index.html").read_text(encoding="utf-8").casefold()
        self.assertRegex(html, r'<script src="\./assets/vendor/maplibre-gl\.js\?v=[0-9a-f]{12}" defer></script>')
        self.assertRegex(html, r'<script type="module" src="\./assets/commonworld-locale\.mjs\?v=[0-9a-f]{12}"></script>')
        self.assertRegex(html, r'<script type="module" src="\./assets/commonworld-app\.js\?v=[0-9a-f]{12}"></script>')
        self.assertRegex(html, r'<link rel="stylesheet" href="\./assets/ipad-layout\.css\?v=[0-9a-f]{12}" />')
        self.assertNotIn("unpkg.com", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertNotIn("<form", html)

    def test_public_shell_requires_human_readable_method_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "method.html"
            path.write_text(path.read_text(encoding="utf-8").replace("not a complete global statistic", "complete global statistic"), encoding="utf-8")
            errors = validate_public_shell(root)
        self.assertTrue(any("not a complete global statistic" in error for error in errors))

    def test_presence_html_tolerates_formatting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            html = path.read_text(encoding="utf-8")
            
            # Replace nicely formatted presence group with a messy one
            import re
            html = re.sub(
                r'<fieldset class="filter-presence-group">.*?</fieldset>',
                '''<fieldset 
                  data-extra="true" 
                  class="extra filter-presence-group another"
                >
                  <legend>Presence</legend>
                  <div class="filter-presence-options" style="display:flex">
                    <label><input type="checkbox" id="filter-presence-geographic" checked /> Geographic</label>
                    <label><input id="filter-presence-digital" type="checkbox" /> Digital</label>
                  </div>
                </fieldset>''',
                html,
                flags=re.DOTALL
            )
            path.write_text(html, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertEqual([], errors)

    def test_stylesheet_links_tolerate_formatting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            html = path.read_text(encoding="utf-8")
            html = re.sub(
                r'<link rel="stylesheet" href="(\./index\.css\?v=[0-9a-f]{12})" />',
                r"<link href='\1' rel='stylesheet' data-extra='1' />",
                html,
                count=1,
            )
            html = re.sub(
                r'<link rel="stylesheet" href="(\./assets/ipad-layout\.css\?v=[0-9a-f]{12})" />',
                r"<link href='\1' rel='stylesheet' />",
                html,
                count=1,
            )
            path.write_text(html, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertEqual([], errors)
            
    def test_extra_css_rule_after_ipad_media(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "assets/ipad-layout.css"
            path.write_text(path.read_text(encoding="utf-8") + "\n\n.extra-trailing-rule { color: red; }\n", encoding="utf-8")
            self.refresh_ipad_version(root)
            errors = validate_public_shell(root)
            self.assertEqual([], errors)
            
    def test_negative_presence_missing_checkbox(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            html = path.read_text(encoding="utf-8")
            html = html.replace('id="filter-presence-geographic"', 'id="filter-presence-broken"')
            path.write_text(html, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertIn('presence options wrapper must contain both presence checkboxes', errors)

    def test_negative_missing_target_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "assets/ipad-layout.css"
            css = path.read_text(encoding="utf-8")
            # Break the discovery block
            css = css.replace('.layer-discovery', '.layer-broken')
            path.write_text(css, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertIn('tablet landscape breakpoint must override .layer-discovery geometry', errors)

    def test_foreign_media_query_before_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "assets/ipad-layout.css"
            css = path.read_text(encoding="utf-8")
            # An unrelated portrait media query emitted before the tablet landscape target.
            foreign = "@media (orientation: portrait) and (max-width: 30rem) {\n  .layer-discovery { top: 0; }\n}\n\n"
            path.write_text(foreign + css, encoding="utf-8")
            self.refresh_ipad_version(root)
            errors = validate_public_shell(root)
            self.assertEqual([], errors)

    def test_similarly_named_selector_is_not_matched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "assets/ipad-layout.css"
            css = path.read_text(encoding="utf-8")
            # Rename the real target to a near-miss so the boundary-aware scanner rejects it.
            css = css.replace('.layer-discovery {', '.layer-discovery-alt {')
            path.write_text(css, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertIn('tablet landscape breakpoint must override .layer-discovery geometry', errors)

    def test_braces_inside_css_comment_and_string_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "assets/ipad-layout.css"
            css = path.read_text(encoding="utf-8")
            decoy = '/* pseudo braces } { should not confuse the scanner */\n.decoy-content::before { content: "} { }"; }\n\n'
            path.write_text(decoy + css, encoding="utf-8")
            self.refresh_ipad_version(root)
            errors = validate_public_shell(root)
            self.assertEqual([], errors)

    def test_stylesheet_links_tolerate_rel_tokens_and_casing(self) -> None:
        html = (
            '<link href="./index.css" REL="Stylesheet preload">'
            "<link rel='preload' href='./ignored.css'>"
            '<link rel="stylesheet" href="./assets/ipad-layout.css" />'
        )
        self.assertEqual(["./index.css", "./assets/ipad-layout.css"], parse_stylesheet_links(html))

    def test_presence_group_tolerates_nested_divs(self) -> None:
        html = (
            '<fieldset class="filter-presence-group"><legend>Presence</legend>'
            '<div class="filter-presence-options"><div class="row">'
            '<label><input type="checkbox" id="filter-presence-geographic"> Vor Ort</label></div>'
            '<div class="row"><label><input type="CHECKBOX" id="filter-presence-digital"> Digital</label></div>'
            "</div></fieldset>"
        )
        presence = parse_presence_group(html)
        self.assertEqual(1, presence.fieldset_count)
        self.assertEqual(1, presence.options_wrapper_count)
        self.assertTrue(presence.has_legend)
        self.assertTrue(presence.has_both_checkboxes)

    def test_presence_group_missing_legend_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            html = path.read_text(encoding="utf-8")
            original = html
            html = html.replace("<legend>Required presence</legend>", "", 1)
            self.assertNotEqual(original, html)
            path.write_text(html, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertIn("presence fieldset must expose a legend", errors)

    def test_presence_group_duplicate_fieldset_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.html"
            html = path.read_text(encoding="utf-8")
            duplicate = (
                '<fieldset class="filter-presence-group"><legend>Präsenz</legend>'
                '<div class="filter-presence-options">'
                '<label><input type="checkbox" id="filter-presence-geographic"> Vor Ort</label>'
                '<label><input type="checkbox" id="filter-presence-digital"> Digital</label>'
                "</div></fieldset>"
            )
            html = html.replace("</main>", duplicate + "</main>", 1)
            path.write_text(html, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertIn("index.html must define exactly one presence fieldset", errors)

    def test_target_media_block_found_by_feature_tests(self) -> None:
        css = (ROOT / "assets/ipad-layout.css").read_text(encoding="utf-8")
        match = find_media_block(
            css,
            ("orientation: landscape", "min-width: 48rem", "max-width: 90rem", "max-height: 65rem"),
        )
        self.assertIsNotNone(match)
        self.assertIn(".layer-discovery", match[1])
        # A near-miss target selector must not match the real rule.
        self.assertIsNone(find_css_block(match[1], ".layer-discovery-alt"))
        self.assertIsNotNone(find_css_block(match[1], ".layer-discovery"))

    def test_top_level_semicolon_prelude_does_not_bleed_into_target(self) -> None:
        # A leading @charset/@import prelude ends at its semicolon and must not be
        # absorbed into the following media query's selector.
        css = (
            '@charset "utf-8";\n'
            '@import url("./tokens.css");\n'
            "@media (orientation: landscape) and (min-width: 48rem) "
            "and (max-width: 90rem) and (max-height: 65rem) {\n"
            "  .layer-discovery { left: 50%; }\n"
            "}\n"
        )
        match = find_media_block(
            css,
            ("orientation: landscape", "min-width: 48rem", "max-width: 90rem", "max-height: 65rem"),
        )
        self.assertIsNotNone(match)
        self.assertIsNotNone(find_css_block(match[1], ".layer-discovery"))

    def test_overbroad_descendant_selector_is_not_an_exact_target(self) -> None:
        # A descendant selector must not be accepted as the exact target selector.
        css = ".surface .layer-discovery { left: 50%; }\n"
        self.assertIsNone(find_css_block(css, ".layer-discovery"))
        self.assertIsNotNone(find_css_block(css, ".surface .layer-discovery"))


    def test_public_shell_requires_forced_colors_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.css"
            css = path.read_text(encoding="utf-8").replace(
                "@media (forced-colors: active)",
                "@media (forced-colors: none)",
                1,
            )
            path.write_text(css, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertIn("public shell CSS must define a forced-colors: active contract", errors)

    def test_public_shell_requires_increased_contrast_state_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.css"
            css = path.read_text(encoding="utf-8").replace(
                '[aria-checked="true"]',
                '[aria-checked="mixed"]',
                1,
            )
            path.write_text(css, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertIn(
                'public increased-contrast contract missing token: [aria-checked="true"]',
                errors,
            )


    def test_public_shell_reduced_motion_disables_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = self.copy_shell(tmp_dir)
            path = root / "index.css"
            css = path.read_text(encoding="utf-8").replace(
                "transition: none !important",
                "transition-duration: 0.01ms !important",
                1,
            )
            path.write_text(css, encoding="utf-8")
            errors = validate_public_shell(root)
            self.assertIn("public reduced-motion contract must disable transitions", errors)


    def test_digital_lanes_present_each_common_once(self) -> None:
        app = (ROOT / "assets/commonworld-app.js").read_text(encoding="utf-8")
        self.assertNotIn("ribbonRepeatCount", app)
        self.assertNotIn("data-ribbon-copy", app)
        self.assertIn("new Map(allRecords.map((record) => [record.id, record]))", app)
        self.assertIn("for (const record of records) content.append(createRibbonSegment(record));", app)
        self.assertIn("function selectDigitalProject", app)
        self.assertNotIn("deriveDigitalProjectPath(record)", app)
        self.assertNotIn("setDigitalPath(derived.path", app)
        self.assertIn("renderLayerProjectDetail(view);", app)
        self.assertIn("selectProject(record.id, { trigger });", app)
        self.assertIn("elements.layerProjects.hidden = true", app)
        self.assertIn("segment.setAttribute('aria-controls', 'project-focus')", app)
        self.assertIn("runtime.digitalTreeCache.get(records)", app)
        self.assertIn("reconcileProjectSelection();", app)

    def test_final_digital_lane_uses_only_the_shared_focus_detail(self) -> None:
        app = (ROOT / "assets/commonworld-app.js").read_text(encoding="utf-8")
        css = (ROOT / "index.css").read_text(encoding="utf-8")
        i18n = (ROOT / "assets/commonworld-i18n.mjs").read_text(encoding="utf-8")
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("function renderLayerProjectDetail", app)
        self.assertIn("runtime.layerPreviewProject = null", app)
        self.assertIn("elements.layerProjects.hidden = true", app)
        self.assertIn("elements.layerProjects.replaceChildren()", app)
        self.assertIn("segment.setAttribute('aria-controls', 'project-focus')", app)
        self.assertIn("if (focus) elements.focus.focus({ preventScroll: true });", app)
        self.assertIn('id="layer-project-status"', html)
        self.assertNotIn("previewRecord ?? records[0]", app)
        self.assertNotIn("runtime.layerPreviewProject = closingIdentifier", app)
        self.assertNotIn(".layer-project-detail", css)
        self.assertNotIn(".project-detail-", css)
        self.assertNotIn("back_to_bundle", i18n)
        self.assertNotIn("detail_profile", i18n)
        self.assertIn("document.createElement(identityLevel ? 'header' : 'button')", app)

    def test_digital_lane_edges_and_labels_remain_legible(self) -> None:
        css = (ROOT / "index.css").read_text(encoding="utf-8")
        self.assertIn(".digital-lane-scroll[data-overflowing][data-at-start]", css)
        self.assertIn(".digital-lane-scroll[data-overflowing][data-at-end]", css)
        self.assertIn(".digital-ribbon-item:last-child::after", css)
        label_block = find_css_block(css, ".digital-lane-focus span")
        self.assertIsNotNone(label_block)
        self.assertIn("hyphens: manual", label_block[1])
        self.assertIn("word-break: normal", label_block[1])

    def test_nonserialized_spatial_state_defers_release_navigation_without_persistence(self) -> None:
        app = (ROOT / "assets/commonworld-app.js").read_text(encoding="utf-8")
        self.assertNotIn("commonworld-release-check.js", app)
        self.assertIn("const RELEASE_NAVIGATION_EVENT = 'commonworld:release-navigation';", app)
        self.assertIn("const RELEASE_CHECK_REQUEST_EVENT = 'commonworld:release-check-request';", app)
        self.assertIn("function nonSerializedSpatialStateActive()", app)
        self.assertIn("Array.isArray(runtime.state.nearbyOrigin)", app)
        self.assertIn("document.addEventListener(RELEASE_NAVIGATION_EVENT", app)
        self.assertIn("event.preventDefault();", app)
        self.assertIn("runtime.releaseNavigationDeferred = true;", app)
        self.assertIn("elements.stage.dataset.releaseNavigationDeferred = 'spatial-filter';", app)
        self.assertIn("function resumeDeferredReleaseCheck()", app)
        self.assertIn("delete elements.stage.dataset.releaseNavigationDeferred;", app)
        self.assertIn("document.dispatchEvent(new Event(RELEASE_CHECK_REQUEST_EVENT));", app)
        release_check = (ROOT / "assets/commonworld-release-check.js").read_text(encoding="utf-8")
        self.assertIn("export const RELEASE_CHECK_REQUEST_EVENT = 'commonworld:release-check-request';", release_check)
        self.assertIn("documentImpl.addEventListener?.(RELEASE_CHECK_REQUEST_EVENT, runWhenVisible);", release_check)
        self.assertIn("documentImpl.removeEventListener?.(RELEASE_CHECK_REQUEST_EVENT, runWhenVisible);", release_check)
        self.assertGreaterEqual(app.count("resumeDeferredReleaseCheck();"), 5)
        self.assertNotIn("parameters.set('nearby", (ROOT / "assets/commonworld-core.mjs").read_text(encoding="utf-8"))

    def test_filter_grid_keeps_action_and_location_controls_in_rhythm(self) -> None:
        render_source = (ROOT / "scripts/render_public_shell.py").read_text(encoding="utf-8")
        css = (ROOT / "index.css").read_text(encoding="utf-8")
        self.assertIn('class="filter-action"', render_source)
        self.assertIn(".filter-commons-type,\n.filter-action {", css)
        self.assertIn(".filter-action {\n  grid-column: span 2", css)
        location_block = find_css_block(css, ".filter-group-controls #use-current-location")
        self.assertIsNotNone(location_block)
        self.assertIn("justify-self: start", location_block[1])
        self.assertIn("width: max-content", location_block[1])
        self.assertIn("min-height: var(--minimum-touch-target, 44px)", location_block[1])
        self.assertIn(".geolocation-status:empty", css)


if __name__ == "__main__":
    unittest.main()
