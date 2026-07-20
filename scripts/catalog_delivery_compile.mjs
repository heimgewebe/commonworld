const BOOTSTRAP_EXPORT_PATTERN = /export\s+const\s+BOOTSTRAP_RECORDS\s*=/g;

export function normalizeBootstrapForCompile(source) {
  if (typeof source !== 'string') throw new TypeError('bootstrap source must be a string');
  const matches = [...source.matchAll(BOOTSTRAP_EXPORT_PATTERN)];
  if (matches.length !== 1) {
    throw new Error(`expected exactly one BOOTSTRAP_RECORDS export assignment, found ${matches.length}`);
  }
  return source.replace(BOOTSTRAP_EXPORT_PATTERN, 'const BOOTSTRAP_RECORDS =');
}
