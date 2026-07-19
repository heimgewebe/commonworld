import re
import unittest
from pathlib import Path

from scripts.render_public_shell import render_shell

ROOT = Path(__file__).resolve().parents[1]


class IpadLandscapeLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rendered_shell = render_shell(ROOT)
        self.index_html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.propose_html = (ROOT / "propose.html").read_text(encoding="utf-8")
        self.proposal_css = (ROOT / "assets/proposal.css").read_text(encoding="utf-8")
        self.ipad_layout_css = (ROOT / "assets/ipad-layout.css").read_text(encoding="utf-8")
        self.shell_source = (ROOT / "scripts/render_public_shell.py").read_text(encoding="utf-8")

    # 1. propose.html scroll fix
    def test_propose_page_loads_index_css_before_proposal_css(self) -> None:
        index_link = '<link rel="stylesheet" href="./index.css" />'
        proposal_link = '<link rel="stylesheet" href="./assets/proposal.css" />'
        self.assertIn(index_link, self.propose_html)
        self.assertIn(proposal_link, self.propose_html)
        self.assertLess(self.propose_html.index(index_link), self.propose_html.index(proposal_link))

    def test_proposal_css_overrides_global_body_overflow_hidden(self) -> None:
        match = re.search(r"body\.proposal-page\s*\{([^}]*)\}", self.proposal_css)
        self.assertIsNotNone(match, "assets/proposal.css must style body.proposal-page")
        block = match.group(1)
        self.assertIn("overflow-y: auto", block)
        self.assertIn("overflow-x: hidden", block)
        self.assertIn("-webkit-overflow-scrolling: touch", block)
        self.assertRegex(block, r"overscroll-behavior(-y)?:\s*contain")

    def test_proposal_css_does_not_reintroduce_overflow_hidden_on_body(self) -> None:
        match = re.search(r"body\.proposal-page\s*\{([^}]*)\}", self.proposal_css)
        self.assertIsNotNone(match)
        self.assertNotIn("overflow: hidden", match.group(1))
        self.assertNotIn("overflow-y: hidden", match.group(1))

    # 2. presence filter compact wrapper markup
    def test_render_source_wraps_presence_filter_options(self) -> None:
        self.assertIn('class="filter-presence-options"', self.shell_source)

    def test_generated_shell_has_presence_options_wrapper_around_both_checkboxes(self) -> None:
        match = re.search(
            r'<fieldset class="filter-presence-group"><legend>[^<]*</legend>'
            r'<div class="filter-presence-options">(.*?)</div></fieldset>',
            self.rendered_shell,
        )
        self.assertIsNotNone(match, "presence fieldset must wrap its options in .filter-presence-options")
        wrapped = match.group(1)
        self.assertIn('id="filter-presence-geographic"', wrapped)
        self.assertIn('id="filter-presence-digital"', wrapped)

    def test_index_html_matches_freshly_rendered_shell(self) -> None:
        self.assertEqual(self.rendered_shell, self.index_html)

    def test_ipad_layout_css_makes_presence_group_and_options_compact(self) -> None:
        self.assertIn(".filter-presence-group", self.ipad_layout_css)
        self.assertIn(".filter-presence-options", self.ipad_layout_css)
        options_block_match = re.search(r"\.filter-presence-options label\s*\{([^}]*)\}", self.ipad_layout_css)
        self.assertIsNotNone(options_block_match, "presence options must define a compact, touch-safe label style")
        self.assertRegex(options_block_match.group(1), r"min-height:\s*var\(--minimum-touch-target")

    # 3. ipad-layout.css wiring
    def test_ipad_layout_css_file_exists(self) -> None:
        self.assertTrue((ROOT / "assets/ipad-layout.css").is_file())

    def test_index_html_loads_ipad_layout_css_after_index_css(self) -> None:
        index_link = '<link rel="stylesheet" href="./index.css" />'
        ipad_link = '<link rel="stylesheet" href="./assets/ipad-layout.css" />'
        self.assertIn(index_link, self.index_html)
        self.assertIn(ipad_link, self.index_html)
        self.assertLess(self.index_html.index(index_link), self.index_html.index(ipad_link))

    def test_render_source_emits_ipad_layout_css_link(self) -> None:
        self.assertIn('<link rel="stylesheet" href="./assets/ipad-layout.css" />', self.shell_source)

    # 4. tablet landscape breakpoint for digital ring search and focused lane
    def test_ipad_layout_css_defines_tablet_landscape_breakpoint(self) -> None:
        self.assertRegex(
            self.ipad_layout_css,
            r"@media[^{]*orientation:\s*landscape[^{]*min-width:\s*48rem[^{]*max-height:\s*5[0-9](\.[0-9]+)?rem",
        )

    def test_breakpoint_widens_and_centers_layer_discovery(self) -> None:
        media_block = self._breakpoint_block()
        discovery_match = re.search(r"\.layer-discovery\s*\{([^}]*)\}", media_block)
        self.assertIsNotNone(discovery_match, "breakpoint must override .layer-discovery geometry")
        block = discovery_match.group(1)
        self.assertIn("left: 50%", block)
        self.assertIn("translateX(-50%)", block)
        self.assertNotIn("right: max", block)

    def test_breakpoint_reduces_deck_padding_and_focused_lane_height(self) -> None:
        media_block = self._breakpoint_block()
        self.assertIn(".layer-track-deck", media_block)
        focused_lane_match = re.search(
            r"\.globe-stage\[data-focused-path\] \.digital-lane\.is-focused\s*\{([^}]*)\}",
            media_block,
        )
        self.assertIsNotNone(focused_lane_match, "breakpoint must reduce the focused lane min-height")
        self.assertIn("min-height", focused_lane_match.group(1))
        self.assertNotIn("min(44vh, 24rem)", focused_lane_match.group(1))

    def _breakpoint_block(self) -> str:
        match = re.search(
            r"@media[^{]*orientation:\s*landscape[^{]*\{(.*)\}\s*$",
            self.ipad_layout_css,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "ipad-layout.css must define exactly one trailing landscape breakpoint")
        return match.group(1)


if __name__ == "__main__":
    unittest.main()
