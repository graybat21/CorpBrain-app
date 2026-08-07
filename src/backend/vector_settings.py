"""
ChromaDB client settings factory (DEC-06 / DEC-15).

Two reasons this is a single function rather than inline kwargs at each call site:

1. **Chroma caches a System per persist_directory.** ``SharedSystemClient`` keys its
   identifier off ``persist_directory``; constructing a second client for the same directory
   with a *different* ``Settings`` object raises
   ``ValueError: An instance of Chroma already exists for ... with different settings``.
   Every client in the process must therefore build settings the same way.

2. **Telemetry must be disabled by explicit kwarg, not by environment.** ``Settings`` is a
   pydantic ``BaseSettings`` with ``env_file=".env"`` and an empty ``env_prefix``, so a stray
   ``.env`` file or an ``ANONYMIZED_TELEMETRY`` variable can set these fields. Constructor
   kwargs take precedence over both, which is what makes passing them here a real control
   rather than a comment.

Honest scope note (see the PR body for #16): chromadb's own outbound calls cannot pass
through ``NetworkGuard`` — it bundles its own HTTP stack, and the only way to intercept that
would be monkey-patching ``socket.socket``, which CLAUDE.md forbids outright. DEC-15
compliance here rests on four controls instead: the exact version pin in requirements.txt,
these explicit settings, the ``test_telemetry_is_disabled_and_inert`` regression test, and
never invoking the bundled ``chroma`` CLI. That is an acknowledged partial exception to the
"single gate" rule, not a claim that the gate covers it.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import-time cost avoidance only
    from chromadb.config import Settings


def build_chroma_settings(persist_dir: str) -> "Settings":
    """
    Build the one and only ``Settings`` configuration CorpBrain uses.

    ``chromadb`` is imported lazily: it pulls in numpy, onnxruntime and friends, and importing
    it at module scope would slow every process that merely touches this module.
    """
    from chromadb.config import Settings

    return Settings(
        # DEC-06: a real on-disk store. EphemeralClient would satisfy the API but lose
        # everything on exit, which is precisely the defect this replaces.
        is_persistent=True,
        persist_directory=persist_dir,
        # DEC-15: zero telemetry. Passed explicitly so a .env/env var cannot re-enable it.
        anonymized_telemetry=False,
        chroma_otel_granularity=None,
        chroma_otel_collection_endpoint="",
        # A stray reset() would drop every workspace's collection at once. Nothing in
        # CorpBrain needs it — workspace deletion uses delete_collection (DEC-09).
        allow_reset=False,
    )
