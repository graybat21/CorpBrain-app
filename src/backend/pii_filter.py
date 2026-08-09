import re
from dataclasses import dataclass
from typing import Dict, List, Tuple


class PIIMaskingFailedException(Exception):
    """Raised when PII masking fails or integrity check 2-condition AND fails."""
    pass


@dataclass
class MaskedResult:
    masked_text: str
    counts: Dict[str, int]


class PIIFilter:
    # 7 Regex Patterns (DEC-14)
    #
    # Boundaries are `(?<!\d)` / `(?!\d)` rather than `\b`, and this is a security fix, not a
    # style preference (found while wiring DEC-17's rename path, issue #37).
    #
    # `\b` sits between a word character and a non-word character, but `_` IS a word character.
    # So in `홍길동_주민등록증_900101-1234567.pdf` there is no boundary between `_` and `9`, and
    # the RRN was **not masked at all** — it went out in the transmission payload verbatim. That
    # is exactly the leak DEC-17 exists to prevent, and filenames are full of underscores.
    #
    # A digit-only lookaround is also the *correct* boundary for these patterns: what must not
    # match is a longer run of digits (a 20-digit id containing a valid-looking RRN), not an
    # adjacent letter or underscore. `[^\d]` on either side would consume the neighbouring
    # character and shift the replacement offsets, so lookarounds are used.
    #
    # No nested quantifiers anywhere below (ReDoS — DEC-14), and no pattern is assembled from
    # user input.
    # Separator handling (issue #33): the hyphen is optional, and a single space is accepted where
    # the digit groups stay unambiguous. `[- ]?` rather than `[- ]*` — no nested quantifier, so
    # there is nothing for a ReDoS input to backtrack through.
    #
    # Deliberately NOT extended to hyphen-less BIZNO (10 bare digits) or ACCOUNT (a bare digit
    # run): those are not distinctive, and masking every 10-digit number would replace order
    # numbers, part codes and timestamps throughout ordinary documents. Over-masking is the safe
    # direction for a leak, but not when it corrupts most of the text.
    #
    # Known collision, stated rather than hidden: a hyphen-less RRN is 13 digits, and an EAN-13
    # barcode such as `8801234567890` parses as a valid date + gender digit, so it will be masked
    # as an RRN. That is the fail-closed direction DEC-14 asks for — a masked barcode is a
    # cosmetic loss, an unmasked RRN is the breach this filter exists to prevent — but it is a
    # real false positive and is called out in the PR.
    PATTERNS = {
        "RRN": re.compile(
            r"(?<!\d)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[- ]?[1-4]\d{6}(?!\d)"
        ),
        "PHONE": re.compile(
            r"(?<!\d)01[016789][- ]?\d{3,4}[- ]?\d{4}(?!\d)"
            r"|(?<!\d)0(2|[3-6][1-5])[- ]?\d{3,4}[- ]?\d{4}(?!\d)"
        ),
        # EMAIL: `_` is legal *inside* a local part, so it is included in the character class
        # instead of being treated as a boundary. `\b` at the start failed the same way as RRN —
        # `email_hong@example.com` left the address unmasked because there is no boundary
        # between `_` and `h`. Anchoring on "not an address character" also means the leading
        # underscores of `기획_hong@example.com` are excluded from the match rather than
        # swallowed into it.
        "EMAIL": re.compile(
            r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9.-])"
        ),
        "CARD": re.compile(
            r"(?<!\d)\d{4}-\d{4}-\d{4}-\d{4}(?!\d)|(?<!\d)\d{4} \d{4} \d{4} \d{4}(?!\d)"
        ),
        "BIZNO": re.compile(r"(?<!\d)\d{3}-\d{2}-\d{5}(?!\d)"),
        "ACCOUNT": re.compile(r"(?<!\d)\d{3,6}-\d{2,6}-\d{3,6}(?!\d)"),
        # PASSPORT keeps a letter-side guard: `M12345678` inside `ROOM12345678` is not a passport
        # number, so the preceding character must not be alphanumeric.
        "PASSPORT": re.compile(r"(?<![A-Za-z0-9])[M1S]\d{8}(?![A-Za-z0-9])"),
    }

    #: Fullwidth (U+FF10–U+FF19) → ASCII digits, plus the fullwidth hyphen and the two hyphen
    #: lookalikes a Korean IME produces (U+2010 HYPHEN, U+2212 MINUS SIGN).
    #:
    #: Why this exists (issue #33): `\d` in Python matches fullwidth digits, but an explicit
    #: class like `[1-4]` or a literal `0` does NOT. So `９００１０１-１２３４５６７` slipped
    #: through the RRN pattern entirely, while a fullwidth phone number matched ACCOUNT instead
    #: of PHONE — masked, but under the wrong type, which corrupts the per-type counts DEC-14
    #: allows us to log. Normalising first makes every pattern see one canonical form.
    #:
    #: Every mapping is **one character to one character**, so the normalised string has the
    #: same length and the same indices as the original. That is what lets the offsets found on
    #: the normalised text be applied to the ORIGINAL text — the replacement must happen on the
    #: original, or masking would silently rewrite the user's fullwidth characters as ASCII.
    _NORMALIZE_MAP = str.maketrans(
        "０１２３４５６７８９－‐−＠",
        "0123456789---@",
    )

    def _ner_scan(self, text: str) -> List[str]:
        """
        Interface reserved for NER scan. No-op in MVP (DEC-14).

        Returns an empty list, not None: NER is out of MVP scope by decision — probabilistic
        detection cannot produce the pass/fail criterion REQ-FUNC-009's fail-safe needs — but a
        caller iterating the result must not have to special-case the placeholder. Person and
        organisation names are therefore NOT masked, which is surfaced in the UI rather than
        papered over.
        """
        return []

    def mask(self, text: str) -> MaskedResult:
        if not text:
            return MaskedResult(masked_text="", counts={})

        try:
            # 1. Collect all matches across all 7 patterns
            matches: List[Tuple[int, int, str, str]] = []  # (start, end, pii_type, matched_str)
            counts: Dict[str, int] = {}

            # Scan the normalised form so fullwidth digits and hyphen lookalikes are seen, but
            # keep every offset valid against `text` — the map is strictly 1 char → 1 char, so
            # indices are identical in both strings. The raw string recorded for condition ⓑ is
            # taken from `text`, not from the normalised copy: condition ⓑ asks whether the
            # ORIGINAL matched substring survived, and a normalised copy of it never appeared in
            # the user's input.
            scan_text = text.translate(self._NORMALIZE_MAP)
            for pii_type, pattern in self.PATTERNS.items():
                for m in pattern.finditer(scan_text):
                    matches.append((m.start(), m.end(), pii_type, text[m.start():m.end()]))

            if not matches:
                return MaskedResult(masked_text=text, counts={})

            # Sort matches by start index ascending, then length descending
            matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

            # Merge overlapping matches (widest match priority)
            merged_matches: List[Tuple[int, int, str, str]] = []
            for m in matches:
                if not merged_matches:
                    merged_matches.append(m)
                else:
                    prev = merged_matches[-1]
                    # If current match is inside previous match, skip it
                    if m[0] >= prev[0] and m[1] <= prev[1]:
                        continue
                    # If overlapping, keep previous wider match
                    if m[0] < prev[1]:
                        continue
                    merged_matches.append(m)

            # 2. Perform back-to-front string substitution
            result_chars = list(text)
            detected_raw_strings = [m[3] for m in merged_matches]

            # Sort back-to-front
            merged_matches.sort(key=lambda item: item[0], reverse=True)

            for start, end, pii_type, _ in merged_matches:
                token = f"[PII:{pii_type}]"
                result_chars[start:end] = list(token)
                counts[pii_type] = counts.get(pii_type, 0) + 1

            masked_text = "".join(result_chars)

            # 3. Validate Integrity (2-condition AND) (DEC-14)
            if not self.validate_integrity(masked_text, detected_raw_strings):
                raise PIIMaskingFailedException("PII_MASKING_FAILED: Integrity check failed")

            return MaskedResult(masked_text=masked_text, counts=counts)

        except PIIMaskingFailedException:
            raise
        except Exception as e:
            # `from None` deliberately breaks the chain: DEC-14 forbids PII reaching a log or
            # error response, and a chained traceback would carry the original text along with
            # it. Only the exception type is named for the same reason.
            raise PIIMaskingFailedException(
                f"PII_MASKING_FAILED: Internal error ({type(e).__name__})"
            ) from None

    def validate_integrity(self, masked_text: str, original_matches: List[str]) -> bool:
        """
        2-condition AND validation (DEC-14):
        Condition A: Rescanning masked_text with all 7 regexes yields 0 matches.
        Condition B: None of original detected raw match strings exist as substring in masked_text.
        """
        # Condition A — rescan the NORMALISED masked text, matching what `mask` scans. Rescanning
        # the raw form would let a fullwidth RRN that survived masking pass verification, since
        # the patterns cannot see it in that form (issue #33).
        scan_text = masked_text.translate(self._NORMALIZE_MAP)
        for pattern in self.PATTERNS.values():
            if pattern.search(scan_text) is not None:
                return False

        # Condition B — the original matched substrings, checked against the masked text as-is.
        # Normalising here would be wrong: the question is whether the exact string that was
        # detected still survives, and comparing normalised forms could report a match that is
        # not literally present (or miss one that is).
        for raw_match in original_matches:
            if raw_match in masked_text:
                return False

        return True
