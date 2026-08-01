"""Extract the browser proposal message inventory without executing JavaScript."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_MODULE_PATH = ROOT / "assets/commonworld-proposal.js"
TR_CALL_RE = re.compile(r"\btr\s*\(")
TEMPLATE_VALUE_RE = re.compile(r"\$\{\s*([A-Za-z_$][\w$]*)\s*\}")


def _split_first_arguments(source: str, start: int) -> tuple[list[str], int]:
    arguments: list[str] = []
    token: list[str] = []
    depth = 0
    quote: str | None = None
    escaped = False
    template_depth = 0
    index = start
    while index < len(source):
        character = source[index]
        if quote is not None:
            token.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif quote == "`" and character == "$" and index + 1 < len(source) and source[index + 1] == "{":
                token.append("{")
                index += 1
                template_depth += 1
            elif quote == "`" and template_depth and character == "{":
                template_depth += 1
            elif quote == "`" and template_depth and character == "}":
                template_depth -= 1
            elif character == quote and template_depth == 0:
                quote = None
        elif character in {'"', "'", "`"}:
            quote = character
            token.append(character)
        elif character in "([{":
            depth += 1
            token.append(character)
        elif character in ")]}":
            if character == ")" and depth == 0:
                arguments.append("".join(token).strip())
                return arguments, index
            depth -= 1
            token.append(character)
        elif character == "," and depth == 0:
            arguments.append("".join(token).strip())
            token = []
            if len(arguments) >= 2:
                return arguments, index
        else:
            token.append(character)
        index += 1
    raise ValueError("unterminated tr() call")


def _decode_literal(expression: str) -> str:
    value = expression.strip()
    if value[:1] in {'"', "'"} and value[-1:] == value[:1]:
        decoded = ast.literal_eval(value)
        if not isinstance(decoded, str):
            raise ValueError("proposal translation literal must be a string")
        return decoded
    if value.startswith("`") and value.endswith("`"):
        return TEMPLATE_VALUE_RE.sub(r"{\1}", value[1:-1]).replace("\\`", "`")
    raise ValueError(f"unsupported proposal translation expression: {value}")


def proposal_runtime_inventory(path: Path = PROPOSAL_MODULE_PATH) -> dict[str, str]:
    source = path.read_text(encoding="utf-8")
    inventory: dict[str, str] = {}
    for match in TR_CALL_RE.finditer(source):
        arguments, _ = _split_first_arguments(source, match.end())
        if len(arguments) < 2:
            continue
        german = _decode_literal(arguments[0])
        english = _decode_literal(arguments[1])
        previous = inventory.setdefault(english, german)
        if previous != german:
            raise ValueError(f"ambiguous proposal runtime source message: {english!r}")
    if not inventory:
        raise ValueError("proposal runtime message inventory is empty")
    return inventory
