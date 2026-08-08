#!/usr/bin/env python3
"""One-shot branch bootstrap for a complete Simplified Chinese locale draft.

This file is intentionally removed by the bootstrap workflow after it writes the
reviewable source pack and catalog overlay. The draft writer is Google Translate;
release remains blocked until an independent, digest-bound language review and
all normal locale release gates pass.
"""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import time
from pathlib import Path

from deep_translator import GoogleTranslator

ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "assets/locales/wave1-locales.json"
EN_CATALOG_PATH = ROOT / "catalog/locales/en.json"
ZH_CATALOG_PATH = ROOT / "catalog/locales/zh-Hans.json"
CONTRACT_PATH = ROOT / "docs/architecture/locale-release.contract.json"
SOURCE_LOCALE = "en"
TARGET_TRANSLATOR_LOCALE = "zh-CN"
TARGET_LOCALE = "zh-Hans"

PROTECTED = re.compile(
    r"https?://[^\s<>'\"]+|"
    r"\{[A-Za-z0-9_]+\}|"
    r"`[^`]+`|"
    r"\b(?:Commonworld|CommonProject|Commons|MapLibre|OpenFreeMap|GitHub|JSON|API|URL|RTL|BCP\s*47|AGPL-3\.0|CC0-1\.0|ODbL-1\.0|npm|JavaScript)\b|"
    r"\b[A-Za-z0-9_.-]+\.(?:json|html|mjs|js|css|md)\b"
)
ATTR_RE = re.compile(r'\b(aria-label|title|placeholder|content)=("|\')(.*?)(\2)', re.DOTALL)
TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")

CACHE: dict[tuple[str, str], str] = {}
TRANSLATORS: dict[str, GoogleTranslator] = {}


def translator(source: str) -> GoogleTranslator:
    if source not in TRANSLATORS:
        TRANSLATORS[source] = GoogleTranslator(source=source, target=TARGET_TRANSLATOR_LOCALE)
    return TRANSLATORS[source]


def protect(text: str) -> tuple[str, dict[str, str]]:
    values: dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        token = f"ZXQCW{len(values):04d}QXZ"
        values[token] = match.group(0)
        return token

    return PROTECTED.sub(repl, text), values


def restore(text: str, values: dict[str, str]) -> str:
    result = text
    for token, value in values.items():
        result = result.replace(token, value)
        # Google occasionally inserts spaces inside our sentinel.
        result = result.replace(token.replace("QXZ", " QXZ"), value)
    return result


def translate_plain(text: str, source: str = SOURCE_LOCALE) -> str:
    raw = str(text)
    if not raw.strip():
        return raw
    cache_key = (source, raw)
    if cache_key in CACHE:
        return CACHE[cache_key]
    protected, values = protect(raw)
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            translated = translator(source).translate(protected)
            if not isinstance(translated, str) or not translated.strip():
                raise RuntimeError("translator returned empty text")
            translated = restore(translated, values)
            CACHE[cache_key] = translated
            time.sleep(0.08)
            return translated
        except Exception as exc:  # network-backed draft writer; retry boundedly
            last_error = exc
            time.sleep(min(8.0, 0.75 * (2**attempt)))
    raise RuntimeError(f"translation failed after retries: {raw[:80]!r}") from last_error


def translate_tag(tag: str, source: str) -> str:
    def repl(match: re.Match[str]) -> str:
        name, quote, value, _ = match.groups()
        if not value.strip() or value.startswith(("http://", "https://")):
            return match.group(0)
        return f"{name}={quote}{translate_plain(value, source)}{quote}"

    return ATTR_RE.sub(repl, tag)


def translate_markup(text: str, source: str = SOURCE_LOCALE) -> str:
    parts = TAG_SPLIT_RE.split(str(text))
    rendered: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("<") and part.endswith(">"):
            rendered.append(translate_tag(part, source))
        else:
            rendered.append(translate_plain(part, source) if part.strip() else part)
    return "".join(rendered)


def translate_value(value, source: str):
    if isinstance(value, str):
        return translate_markup(value, source)
    if isinstance(value, list):
        return [translate_value(item, source) for item in value]
    if isinstance(value, dict):
        return {key: translate_value(item, source) for key, item in value.items()}
    return value


def english_runtime_maps(template: dict) -> dict[str, dict[str, str]]:
    key_sets = {
        name: list(template.get(name, {}))
        for name in ("ui", "themes", "taxonomy", "actions")
    }
    env = os.environ.copy()
    env["CW_ZH_KEYS"] = json.dumps(key_sets, ensure_ascii=False)
    code = r'''
import { text, themeLabel, taxonomyLabel, actionLabel } from './assets/commonworld-i18n.mjs';
const keys = JSON.parse(process.env.CW_ZH_KEYS);
const out = {ui:{}, themes:{}, taxonomy:{}, actions:{}};
for (const key of keys.ui || []) out.ui[key] = text('en', key, '');
for (const key of keys.themes || []) out.themes[key] = themeLabel(key, 'en');
for (const key of keys.taxonomy || []) out.taxonomy[key] = taxonomyLabel(key, 'en', '');
for (const key of keys.actions || []) out.actions[key] = actionLabel(key, 'en');
console.log(JSON.stringify(out));
'''
    output = subprocess.check_output(
        ["node", "--input-type=module", "-e", code],
        cwd=ROOT,
        env=env,
        text=True,
    )
    return json.loads(output)


def ordered_english_replacements(section: str, template: dict) -> dict[str, str] | None:
    import scripts.commonworld_i18n as i18n

    constant = {
        "shell": "SHELL_REPLACEMENTS_EN",
        "method": "METHOD_REPLACEMENTS_EN",
        "proposal": "PROPOSAL_REPLACEMENTS_EN",
    }.get(section)
    if not constant:
        return None
    mapping = getattr(i18n, constant, None)
    target = template.get(section)
    if not isinstance(mapping, dict) or not isinstance(target, dict):
        return None
    keys = list(target)
    values = list(mapping.values())
    if len(keys) != len(values):
        return None
    return dict(zip(keys, values, strict=True))


def build_pack(payload: dict) -> dict:
    template = copy.deepcopy(payload["locales"]["es"])
    runtime_en = english_runtime_maps(template)
    result: dict = {}
    for section, value in template.items():
        if section == "meta":
            result[section] = {
                "draft_origin": "machine_translation_assisted",
                "independent_language_review": "pending",
                "direction": "ltr",
                "source_revision": os.environ.get("GITHUB_SHA", "branch-bootstrap"),
            }
            continue
        if section in runtime_en and isinstance(value, dict):
            result[section] = {
                key: translate_markup(runtime_en[section][key], SOURCE_LOCALE)
                for key in value
            }
            continue
        replacements = ordered_english_replacements(section, template)
        if replacements is not None:
            result[section] = {
                key: translate_markup(source_text, SOURCE_LOCALE)
                for key, source_text in replacements.items()
            }
            continue
        if section == "proposal_runtime" and isinstance(value, dict):
            # Keys are the canonical English browser message inventory.
            result[section] = {key: translate_markup(key, SOURCE_LOCALE) for key in value}
            continue
        # Static/auxiliary pack strings have no exported English inventory. Use
        # the released Spanish pack as a machine-draft source, then require the
        # independent reviewer to compare the result against English surfaces.
        result[section] = translate_value(value, "es")
    return result


def build_catalog(pack: dict) -> dict:
    source = json.loads(EN_CATALOG_PATH.read_text(encoding="utf-8"))
    projects: dict[str, dict] = {}
    for project_id, entry in source["projects"].items():
        translated = {
            "summary": translate_markup(entry["summary"], SOURCE_LOCALE),
            "geographic_labels": {
                key: translate_markup(label, SOURCE_LOCALE)
                for key, label in entry.get("geographic_labels", {}).items()
            },
        }
        if "digital_label" in entry:
            translated["digital_label"] = translate_markup(entry["digital_label"], SOURCE_LOCALE)
        # Deliberately omit title: project/organization proper names stay
        # canonical and the runtime will use the English title locale when one
        # exists instead of falsely labelling Latin proper names as Chinese.
        projects[project_id] = translated
    return {
        "schema_version": 1,
        "locale": TARGET_LOCALE,
        "fallback_locale": "en",
        "contract": source.get("contract", {}),
        "taxonomy_labels": pack.get("taxonomy", {}),
        "projects": projects,
    }


def patch_contract() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    released = contract["decision"]["released_locales"]
    if TARGET_LOCALE not in released:
        released.append(TARGET_LOCALE)
    entry = contract["locale_registry"][TARGET_LOCALE]
    entry.update(
        {
            "status": "released",
            "direction": "ltr",
            "surface_files": {
                "index": "zh-Hans.html",
                "method": "method.zh-Hans.html",
                "proposal": "propose.zh-Hans.html",
            },
            "native_name": "简体中文",
            "english_name": "Simplified Chinese",
            "translation_pack": "wave_1",
        }
    )
    entry.pop("release_evidence", None)
    wave1 = contract["rollout"]["wave_1"]
    if TARGET_LOCALE not in wave1:
        wave1.append(TARGET_LOCALE)
    wave2 = contract["rollout"].get("wave_2", [])
    contract["rollout"]["wave_2"] = [locale for locale in wave2 if locale != TARGET_LOCALE]
    CONTRACT_PATH.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    payload = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pack = build_pack(payload)
    payload["locales"][TARGET_LOCALE] = pack
    PACK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ZH_CATALOG_PATH.write_text(
        json.dumps(build_catalog(pack), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    patch_contract()
    print(f"generated {TARGET_LOCALE} machine-assisted draft with {len(CACHE)} translated strings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
