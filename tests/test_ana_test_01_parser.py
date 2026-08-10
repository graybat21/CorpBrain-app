"""
ANA-TEST-01 (issue #9) — text extraction across the four supported formats (REQ-FUNC-006).

There was no test for `DocumentParser` at all. AC S1 asks for one file per format with Korean and
English text, extracted correctly.

Fixtures are **real files of each format**, built in-process:

- `.txt` / `.md` — written directly, in several encodings.
- `.docx` — built with `python-docx`, which is already a dependency (SRS §8) and can write.
- `.pdf` — hand-assembled minimal PDF bytes (catalog / pages / page / content stream / font +
  xref). `pdfminer.six` is read-only and there is no PDF *writer* in the approved dependency list
  (CLAUDE.md §4), so a hand-built file is the only way to test the real extractor without adding
  one. Verified to round-trip through `pdfminer` before being relied on.

The parser's silent fallbacks get their own tests. `_extract_docx` falls back to a plain-text read
on ImportError, and `_extract_pdf` falls through two ImportErrors to the same place — so a missing
library returns **binary garbage instead of raising**, and a caller cannot tell that from a badly
written document. That behaviour is pinned here so a reader sees it is deliberate rather than
discovering it from a corrupted wiki.
"""

import os
import tempfile

import pytest

from src.backend.services.document_parser import DocumentParser, TextChunker

KOREAN = "2026년 사업계획서 최종본입니다."
ENGLISH = "Quarterly Report 2026 revenue analysis."


def _minimal_pdf(text: str) -> bytes:
    """
    A structurally valid single-page PDF containing `text`.

    Assembled by hand rather than with a library: `pdfminer.six` only reads, and adding a PDF
    writer would be an undeclared dependency (CLAUDE.md §4). Latin-1 only — the built-in
    Helvetica font has no CID mapping for Hangul, so the Korean cases use the other three formats.
    """
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)


@pytest.fixture
def workdir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def _write_docx(path: str, *paragraphs: str) -> str:
    import docx

    document = docx.Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(path)
    return path


# --- AC Scenario 1: all four formats extract their text ----------------------------------


def test_scenario_1_txt_extracts_korean_and_english(workdir):
    path = os.path.join(workdir, "메모.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{KOREAN}\n{ENGLISH}")

    text = DocumentParser.extract_text(path, ".txt")

    assert text.strip() != ""
    assert KOREAN in text
    assert ENGLISH in text


def test_scenario_1_md_extracts_content_including_markup(workdir):
    """
    Markdown is extracted as-is, markup included.

    Deliberate: the chunks feed an LLM, and `## 계약 조건` carries structure the model can use.
    Stripping it would discard information for a cosmetic gain no consumer asked for.
    """
    path = os.path.join(workdir, "위키.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 제목\n\n{KOREAN}\n\n- 항목 1\n- 항목 2\n")

    text = DocumentParser.extract_text(path, ".md")

    assert KOREAN in text
    assert "# 제목" in text
    assert "- 항목 1" in text


def test_scenario_1_docx_extracts_every_paragraph(workdir):
    path = _write_docx(
        os.path.join(workdir, "계약서.docx"), KOREAN, ENGLISH, "세 번째 단락"
    )

    text = DocumentParser.extract_text(path, ".docx")

    assert KOREAN in text
    assert ENGLISH in text
    assert "세 번째 단락" in text


def test_scenario_1_pdf_extracts_its_content_stream(workdir):
    path = os.path.join(workdir, "보고서.pdf")
    with open(path, "wb") as f:
        f.write(_minimal_pdf(ENGLISH))

    text = DocumentParser.extract_text(path, ".pdf")

    assert text.strip() != ""
    assert "Quarterly Report 2026" in text


def test_all_four_formats_pass_together(workdir):
    """
    AC S1 as stated: four files, one pipeline run, all four extracted.

    The per-format tests above localise a failure; this one is the AC's own framing and would
    catch a dispatch bug that somehow passes each format individually.
    """
    files = {}
    txt = os.path.join(workdir, "a.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write(KOREAN)
    files[".txt"] = txt

    md = os.path.join(workdir, "b.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write(f"# {KOREAN}")
    files[".md"] = md

    files[".docx"] = _write_docx(os.path.join(workdir, "c.docx"), KOREAN)

    pdf = os.path.join(workdir, "d.pdf")
    with open(pdf, "wb") as f:
        f.write(_minimal_pdf(ENGLISH))
    files[".pdf"] = pdf

    extracted = {ext: DocumentParser.extract_text(p, ext) for ext, p in files.items()}

    assert len(extracted) == 4
    for ext, text in extracted.items():
        assert text.strip() != "", f"{ext} produced empty text"
    for ext in (".txt", ".md", ".docx"):
        assert KOREAN in extracted[ext], ext
    assert "Quarterly Report" in extracted[".pdf"]


# --- Encoding (the AC's "인코딩이 깨지는 케이스") ------------------------------------------


@pytest.mark.parametrize("encoding", ["utf-8", "cp949", "euc-kr", "utf-16"])
def test_korean_text_survives_every_declared_encoding(workdir, encoding):
    """
    The encoding ladder is tried in order, so each rung must actually work.

    `cp949`/`euc-kr` matter in practice: a Korean Windows user's Notepad still writes them, and a
    parser that only handled UTF-8 would silently mojibake most of a real corpus.
    """
    path = os.path.join(workdir, f"doc_{encoding}.txt")
    with open(path, "w", encoding=encoding) as f:
        f.write(KOREAN)

    text = DocumentParser.extract_text(path, ".txt")

    assert KOREAN in text, f"{encoding} produced {text!r}"


def test_undecodable_bytes_do_not_raise(workdir):
    """
    The last resort is `errors="ignore"`, so a truly broken file returns partial text.

    Returning something is right here — one unreadable file must not abort a 10,000-file analysis
    (DEC-16 per-file isolation) — but it does mean "empty or garbled" is a *possible success*,
    which is why the caller checks `parse_status` rather than trusting the string.
    """
    path = os.path.join(workdir, "손상.txt")
    with open(path, "wb") as f:
        f.write(b"\xff\xfe\x00valid tail")

    text = DocumentParser.extract_text(path, ".txt")

    assert isinstance(text, str)


def test_an_empty_file_returns_an_empty_string(workdir):
    """Empty is a legitimate document state, not an error — and the chunker drops it."""
    path = os.path.join(workdir, "empty.txt")
    open(path, "w").close()

    assert DocumentParser.extract_text(path, ".txt") == ""


# --- Error paths -------------------------------------------------------------------------


def test_a_missing_file_raises_file_not_found(workdir):
    with pytest.raises(FileNotFoundError):
        DocumentParser.extract_text(os.path.join(workdir, "nope.txt"), ".txt")


@pytest.mark.parametrize("ext", [".hwp", ".xlsx", ".pptx", ".exe"])
def test_an_unsupported_extension_raises(workdir, ext):
    """
    CON-06 limits MVP to four formats, and the parser must refuse rather than guess.

    A plain-text read of a `.xlsx` would return ZIP header bytes, which then get embedded and
    searched as if they were prose.
    """
    path = os.path.join(workdir, f"doc{ext}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("content")

    with pytest.raises(ValueError):
        DocumentParser.extract_text(path, ext)


def test_the_extension_argument_is_case_and_dot_insensitive(workdir):
    """`.TXT`, `TXT` and `.txt` name the same format — callers pass all three shapes."""
    path = os.path.join(workdir, "doc.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(KOREAN)

    for variant in (".txt", "txt", ".TXT", "TXT"):
        assert KOREAN in DocumentParser.extract_text(path, variant), variant


def test_a_corrupt_docx_raises_rather_than_returning_garbage(workdir):
    """
    A file named `.docx` that is not a zip must fail loudly.

    `_extract_docx` re-raises everything except ImportError, which is the right split: a broken
    document is a per-file failure the batch records (DEC-16), whereas silently returning its raw
    bytes would embed binary noise into the vector store and pollute every later search.
    """
    path = os.path.join(workdir, "corrupt.docx")
    with open(path, "wb") as f:
        f.write(b"this is definitely not a docx")

    with pytest.raises(Exception) as exc:
        DocumentParser.extract_text(path, ".docx")
    assert not isinstance(exc.value, FileNotFoundError)


# --- The documented fallbacks, pinned so they are visible --------------------------------


def test_a_missing_docx_library_falls_back_to_a_plain_read(workdir, monkeypatch):
    """
    Pins existing behaviour rather than endorsing it.

    Without `python-docx`, `_extract_docx` reads the file as text — so a caller receives ZIP
    header bytes and no exception, and cannot distinguish that from a badly written document.
    `python-docx` is a declared dependency (SRS §8) so this path should be unreachable in a
    correct install; the test exists so the failure mode is documented rather than discovered
    from a corrupted wiki.
    """
    import builtins

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "docx":
            raise ImportError("simulated missing python-docx")
        return real_import(name, *args, **kwargs)

    path = _write_docx(os.path.join(workdir, "doc.docx"), KOREAN)
    monkeypatch.setattr(builtins, "__import__", blocked_import)

    text = DocumentParser.extract_text(path, ".docx")

    # No exception, and the real paragraph text is absent — the caller gets container bytes.
    assert isinstance(text, str)
    assert KOREAN not in text, "if this ever passes, the fallback has become a real parser"


# --- Chunker interaction (the pipeline AC S1 refers to) ----------------------------------


def test_extracted_text_chunks_with_dec06_metadata(workdir):
    """
    AC S1 says "파싱 파이프라인", so extraction must feed the chunker cleanly.

    DEC-06 requires `{workspace_id, file_id, chunk_index, folder_1depth}` on every chunk, and
    DEC-09 requires the deterministic `file_id:index` chunk id — a chunk missing either cannot be
    deleted by metadata filter later, which is how orphan vectors appear.
    """
    path = os.path.join(workdir, "문서.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(KOREAN * 80)

    text = DocumentParser.extract_text(path, ".txt")
    chunks = TextChunker(chunk_size=100, overlap=10).chunk_text(
        text, "file-1", workspace_id="ws-1", folder_1depth="계약"
    )

    assert len(chunks) > 1
    for index, chunk in enumerate(chunks):
        assert chunk["chunk_id"] == f"file-1:{index}"
        assert chunk["chunk_index"] == index
        assert chunk["workspace_id"] == "ws-1"
        assert chunk["folder_1depth"] == "계약"
        # DEC-08: never a path in vector metadata.
        assert workdir not in str(chunk)


def test_whitespace_only_text_yields_no_chunks(workdir):
    """
    Chroma rejects an empty ids list, so a blank document must produce zero chunks — not one
    empty chunk that then fails the upsert.
    """
    path = os.path.join(workdir, "blank.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("   \n\t  \n")

    text = DocumentParser.extract_text(path, ".txt")

    assert TextChunker().chunk_text(text, "file-1") == []
