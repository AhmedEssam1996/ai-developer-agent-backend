"""Prompt-injection defense for untrusted external content.

Emails, Teams messages, calendar bodies and documents are **untrusted input**.
They must never be able to:

* override system instructions,
* impersonate the system or user,
* or authorize an external side effect.

We defend in depth:

1. **Envelope**: untrusted text is wrapped in explicit, delimited markers with
   a label, and the system prompt instructs the model to treat it as data only.
2. **Sanitization**: we neutralize fence-breaking and role-marker sequences that
   could be used to escape the envelope.
3. **Detection**: a heuristic scanner flags likely injection attempts so they can
   be surfaced to the user and logged.
4. **Policy**: write actions *always* require human approval, so even a
   successful injection cannot autonomously trigger a side effect.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

UNTRUSTED_OPEN = "<<<UNTRUSTED_DATA>>>"
UNTRUSTED_CLOSE = "<<<END_UNTRUSTED_DATA>>>"

# Sequences that could be used to break out of the envelope or spoof roles.
_FENCE_BREAKERS = [
    UNTRUSTED_OPEN,
    UNTRUSTED_CLOSE,
    "```system",
    "<|system|>",
    "<|user|>",
    "<|assistant|>",
    "<|im_start|>",
    "<|im_end|>",
    "### System",
    "### Assistant",
]

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_instructions", re.compile(
        r"\b(ignore|disregard|forget)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all)\b"
        r"[^.\n]{0,20}\b(instructions?|rules?|prompt)\b", re.IGNORECASE)),
    ("override_system", re.compile(
        r"\b(override|replace|rewrite)\b[^.\n]{0,30}\b(system|developer)\b"
        r"[^.\n]{0,20}\b(prompt|message|instructions?)\b", re.IGNORECASE)),
    ("exfiltrate", re.compile(
        r"\b(send|forward|email|post|exfiltrate|leak)\b[^.\n]{0,40}"
        r"\b(all|every|entire)\b[^.\n]{0,20}\b(emails?|messages?|data|files?|contacts?)\b",
        re.IGNORECASE)),
    ("new_instructions", re.compile(
        r"\b(new|updated)\s+instructions?\b", re.IGNORECASE)),
    ("you_are_now", re.compile(
        r"\byou\s+are\s+now\b|\bact\s+as\b[^.\n]{0,20}\b(system|admin|developer)\b",
        re.IGNORECASE)),
    ("credential_request", re.compile(
        r"\b(send|share|provide|reply with|paste)\b[^.\n]{0,30}"
        r"\b(password|api[-_ ]?key|token|secret|credential)\b", re.IGNORECASE)),
    ("tool_coercion", re.compile(
        r"\b(call|execute|run|invoke)\b[^.\n]{0,30}\b(tool|function|command|script)\b",
        re.IGNORECASE)),
    ("jailbreak", re.compile(
        r"\b(jailbreak|do anything now|dan mode|developer mode)\b", re.IGNORECASE)),
]


@dataclass
class InjectionScanResult:
    is_suspicious: bool
    matched: list[str] = field(default_factory=list)
    score: float = 0.0


def sanitize_untrusted(text: str) -> str:
    """Neutralize fence-breaking sequences in untrusted text.

    We do not delete content (that could hide information the user needs); we
    defang marker sequences so they cannot be interpreted as control tokens.
    """
    if not text:
        return ""
    cleaned = text
    for marker in _FENCE_BREAKERS:
        cleaned = cleaned.replace(marker, marker.replace("<", "‹").replace(">", "›"))
    # Collapse extremely long runs of backticks that could open fake code fences.
    cleaned = re.sub(r"`{4,}", "```", cleaned)
    return cleaned


def scan_for_injection(text: str) -> InjectionScanResult:
    """Heuristically detect prompt-injection attempts."""
    if not text:
        return InjectionScanResult(False, [], 0.0)
    matched: list[str] = []
    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(name)
    score = min(1.0, len(matched) / 3.0)
    return InjectionScanResult(bool(matched), matched, score)


def wrap_untrusted(text: str, *, source: str, label: str = "") -> str:
    """Wrap untrusted text in a clearly delimited, labeled envelope."""
    safe = sanitize_untrusted(text or "")
    header = f"[source={source}]" + (f"[{label}]" if label else "")
    return f"{UNTRUSTED_OPEN}{header}\n{safe}\n{UNTRUSTED_CLOSE}"


def scan_and_wrap(text: str, *, source: str, label: str = "") -> tuple[str, InjectionScanResult]:
    """Convenience: scan for reporting, then wrap for the model."""
    scan = scan_for_injection(text or "")
    return wrap_untrusted(text or "", source=source, label=label), scan