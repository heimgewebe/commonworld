from pathlib import Path

path = Path(__file__).resolve().parents[1] / "tests/js/locale-preference.test.mjs"
text = path.read_text(encoding="utf-8")
old = """test('locale preference accepts only automatic and supported manual choices', () => {
  assert.equal(normalizeLocalePreference('AUTO'), 'auto');
  assert.equal(normalizeLocalePreference('de'), 'de');
  assert.equal(normalizeLocalePreference('fr'), null);
});
"""
new = """test('locale preference accepts automatic, released and preview manual choices', () => {
  assert.equal(normalizeLocalePreference('AUTO'), 'auto');
  assert.equal(normalizeLocalePreference('de'), 'de');
  assert.equal(normalizeLocalePreference('fr'), 'fr');
  assert.equal(normalizeLocalePreference('pt-PT'), 'pt-BR');
  assert.equal(normalizeLocalePreference('zh-Hans'), null);
});
"""
if text.count(old) != 1:
    raise RuntimeError("locale preference assertion block drifted")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
