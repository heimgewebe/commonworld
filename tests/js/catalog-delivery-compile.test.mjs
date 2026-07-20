import assert from 'node:assert/strict';
import test from 'node:test';

import { normalizeBootstrapForCompile } from '../../scripts/catalog_delivery_compile.mjs';

test('normalizes the one bootstrap export across whitespace variations', () => {
  const source = 'export\n  const   BOOTSTRAP_RECORDS\t = [{"id":"one"}];\n';
  assert.equal(
    normalizeBootstrapForCompile(source),
    'const BOOTSTRAP_RECORDS = [{"id":"one"}];\n',
  );
});

test('rejects a missing bootstrap export assignment', () => {
  assert.throws(
    () => normalizeBootstrapForCompile('const BOOTSTRAP_RECORDS = [];'),
    /expected exactly one BOOTSTRAP_RECORDS export assignment, found 0/,
  );
});

test('rejects multiple bootstrap export assignments', () => {
  assert.throws(
    () => normalizeBootstrapForCompile(
      'export const BOOTSTRAP_RECORDS = [];\nexport const BOOTSTRAP_RECORDS = [];\n',
    ),
    /expected exactly one BOOTSTRAP_RECORDS export assignment, found 2/,
  );
});
