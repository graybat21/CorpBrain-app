"""
Ollama provisioning — LLM-CMD-03 / DEC-13 (issue #29).

The premise DEC-13 settles: **"offline" is a property of the steady state, not of
installation.** REQ-FUNC-010 (download the installer and the models) and CON-03 / REQ-NF-005
(closed network, zero telemetry) read as a contradiction only while those two moments are
conflated. Separated, both hold — so this module is allowed to fetch binaries, and is forbidden
from ever sending document content, paths, or usage data anywhere.

Two modes, auto-detected, never guessed
---------------------------------------
`assisted`     — the installer host answered a HEAD probe: download + silent install + pull.
`detect_only`  — it did not: **detect a pre-provisioned Ollama and nothing else.** No install
                 attempt, no model download, no retry loop.

The mode is decided once per task by a reachability pre-check and recorded in
`Async_Task.result_json.provision_mode`, so a support case can tell which path ran.

Three things this module must never do (DEC-13's explicit prohibitions)
----------------------------------------------------------------------
1. **Attempt an install in `detect_only`.** On a closed network the admin pre-provisions; the
   app detects. Trying anyway produces a hang, not a helpful retry.
2. **Park a failed task in "downloading".** Failure is terminal and immediate:
   `status='failed'` + `error_code='LLM_PROVISION_REQUIRED'`, with the required-model list
   surfaced so the user knows what to copy in.
3. **Fall back to Option A.** That would send document content to Anthropic without consent —
   the single worst outcome available to this codebase, and the reason `LLMRouter` has no
   auto-switch either (DEC-16).

Model identity comes from `App_Config` (`local_embedding_model` / `local_generation_model`),
never from a literal here: `purpose='embedding'` needs only the embedder (~274MB, required by
*every* user including Option A per DEC-06), while `purpose='generation'` additionally needs
the generation model (~4.7GB, Option B only). The two are reported separately — never summed
into one progress bar, because a user who agreed to 274MB did not agree to 5GB.
"""

import json
import logging
import os
import subprocess
import tempfile
from typing import Any, Callable, Dict, List, Optional

from src.backend.config_manager import ConfigManager
from src.backend.network_guard import (
    EgressBlockedError,
    NetworkGuard,
    UpstreamStatusError,
    UpstreamUnavailableError,
)
from src.backend.utils.platform_compat import IS_WINDOWS

logger = logging.getLogger("CorpBrain.ProvisioningService")

#: Ollama's loopback API. Host is whitelisted for `llm_local` (DEC-15).
OLLAMA_BASE_URL = "http://127.0.0.1:11434"

#: Installer download. Host must be in NetworkGuard's `provisioning` whitelist — adding a
#: destination here without updating that code constant raises EgressBlockedError, by design.
OLLAMA_INSTALLER_URL = "https://ollama.com/download/OllamaSetup.exe"

#: DEC-13: HEAD, 5s. Short on purpose — this runs before the user sees any progress, and a
#: closed network typically blackholes rather than refusing, so the timeout *is* the answer.
REACHABILITY_TIMEOUT_SEC = 5.0

PURPOSE_EMBEDDING = "embedding"
PURPOSE_GENERATION = "generation"
VALID_PURPOSES = (PURPOSE_EMBEDDING, PURPOSE_GENERATION)

MODE_ASSISTED = "assisted"
MODE_DETECT_ONLY = "detect_only"

#: Advisory sizes for progress text only. Never used to compute a total or gate a decision —
#: they are documentation of why the two models are presented separately (DEC-13).
MODEL_SIZE_HINTS = {
    "embedding": "약 274MB",
    "generation": "약 4.7GB",
}


class ProvisioningError(Exception):
    """
    Provisioning could not complete.

    Carries `error_code` so TaskRunner's generic handler records the DEC-03 code rather than
    INTERNAL_ERROR, and `required_models` so the UI can list exactly what to copy in.
    """

    def __init__(self, message: str, required_models: Optional[List[str]] = None):
        super().__init__(message)
        self.error_code = "LLM_PROVISION_REQUIRED"
        self.required_models = required_models or []


class ProvisioningService:
    def __init__(
        self,
        config_mgr: ConfigManager,
        network_guard: Any = None,
        installer_url: str = OLLAMA_INSTALLER_URL,
    ):
        self.config_mgr = config_mgr
        # Injected so tests exercise the real decision logic against a controllable network,
        # but defaulted to the real guard: a default of None would let a test pass while
        # bypassing the egress gate entirely (DECISION_LOG 재발방지 4).
        self.network_guard = network_guard or NetworkGuard
        self.installer_url = installer_url

    # --- model identity ------------------------------------------------------------------

    def required_models(self, purpose: str) -> List[str]:
        """
        Models needed for `purpose`, in install order, read from App_Config (DEC-13).

        `embedding` returns the embedder alone; `generation` returns the embedder *and* the
        generation model — Option B still needs embeddings to search (DEC-06), so returning
        only the generation model would produce a "ready" state that cannot answer a query.
        """
        if purpose not in VALID_PURPOSES:
            raise ValueError(f"purpose must be one of {VALID_PURPOSES}, got {purpose!r}")

        embedding_model = self.config_mgr.get("local_embedding_model", "nomic-embed-text")
        models = [embedding_model]
        if purpose == PURPOSE_GENERATION:
            generation_model = self.config_mgr.get("local_generation_model", "qwen2.5:7b-instruct")
            if generation_model not in models:
                models.append(generation_model)
        return models

    # --- detection ------------------------------------------------------------------------

    def list_installed_models(self) -> Optional[List[str]]:
        """
        Model names from Ollama's `GET /api/tags`, or None when the daemon is not answering.

        None and `[]` are different answers and are kept distinct: `[]` means "the daemon is up
        with no models" (pull them), None means "no daemon" (install it). Collapsing the two
        would make `detect_only` tell a closed-network user to pull models on a machine with no
        Ollama at all.
        """
        tags = self.network_guard.get_json(
            "llm_local", f"{OLLAMA_BASE_URL}/api/tags", timeout=REACHABILITY_TIMEOUT_SEC
        )
        if tags is None:
            return None
        return [m.get("name", "") for m in tags.get("models", []) if m.get("name")]

    @staticmethod
    def _model_present(model: str, installed: List[str]) -> bool:
        """
        Whether `model` is among `installed`, tolerating Ollama's implicit `:latest`.

        `ollama pull nomic-embed-text` lists as `nomic-embed-text:latest`, so an equality check
        would report a correctly provisioned machine as missing its models — and in
        `detect_only` that is an unrecoverable dead end for the user.
        """
        base = model.split(":")[0]
        for candidate in installed:
            if candidate == model:
                return True
            if ":" not in model and candidate.split(":")[0] == base:
                return True
        return False

    def missing_models(self, purpose: str, installed: List[str]) -> List[str]:
        return [m for m in self.required_models(purpose) if not self._model_present(m, installed)]

    # --- mode decision --------------------------------------------------------------------

    def decide_mode(self) -> str:
        """
        `assisted` if the installer host answers a HEAD probe, else `detect_only` (DEC-13).

        An `EgressBlockedError` deliberately does NOT become `detect_only`: that would convert
        a whitelist misconfiguration into a silent mode downgrade, and the operator would never
        learn the gate rejected them. It surfaces as LLM_PROVISION_REQUIRED instead.
        """
        try:
            reachable = self.network_guard.is_reachable(
                "provisioning", self.installer_url, timeout=REACHABILITY_TIMEOUT_SEC
            )
        except EgressBlockedError:
            logger.warning("[Provisioning] Installer host is not whitelisted; refusing to guess a mode")
            raise ProvisioningError(
                "설치 파일 주소가 허용 목록에 없습니다. 관리자에게 문의하세요."
            ) from None

        mode = MODE_ASSISTED if reachable else MODE_DETECT_ONLY
        logger.info("[Provisioning] mode=%s (installer reachable=%s)", mode, reachable)
        return mode

    # --- the task body --------------------------------------------------------------------

    def onboard(
        self,
        purpose: str,
        progress: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Run one provisioning attempt. Intended as a DEC-04 task body.

        Returns a dict for `TaskRunner.submit`'s contract. On success:
        `{"status": "completed", "result": {...}}`. Failure raises ProvisioningError, whose
        `error_code` the runner records — there is deliberately no "partially provisioned"
        success, because a missing model means analysis cannot run at all.

        `progress` receives human-readable Korean status lines; the caller persists them.
        """
        if purpose not in VALID_PURPOSES:
            raise ValueError(f"purpose must be one of {VALID_PURPOSES}, got {purpose!r}")

        def report(message: str) -> None:
            logger.info("[Provisioning] %s", message)
            if progress is not None:
                progress(message)

        required = self.required_models(purpose)
        mode = self.decide_mode()
        installed = self.list_installed_models()
        daemon_online = installed is not None

        if mode == MODE_DETECT_ONLY:
            return self._detect_only(purpose, required, installed, report)
        return self._assisted(purpose, required, installed, daemon_online, report)

    def _detect_only(
        self,
        purpose: str,
        required: List[str],
        installed: Optional[List[str]],
        report: Callable[[str], None],
    ) -> Dict[str, Any]:
        """
        Closed network: detect only. **No install, no pull, no retry** (DEC-13).

        Every failure exit here is terminal and names the missing pieces. "Retrying in the
        background" on a closed network is an infinite wait dressed up as progress.
        """
        report("폐쇄망으로 판정되었습니다 — 사전 설치된 Ollama 를 탐지합니다 (설치를 시도하지 않습니다).")

        if installed is None:
            raise ProvisioningError(
                "Ollama 데몬이 응답하지 않습니다. 관리자가 Ollama 를 사전 설치해야 합니다.",
                required_models=required,
            )

        missing = self.missing_models(purpose, installed)
        if missing:
            report(f"필요 모델 {len(missing)}개가 없습니다: {', '.join(missing)}")
            raise ProvisioningError(
                "필요한 모델이 준비되지 않았습니다. 오프라인 설치 절차를 따르세요.",
                required_models=missing,
            )

        report("사전 프로비저닝된 환경을 확인했습니다.")
        return {
            "status": "completed",
            "result": {
                "provision_mode": MODE_DETECT_ONLY,
                "purpose": purpose,
                "daemon_online": True,
                "required_models": required,
                "missing_models": [],
                "installed_models": installed,
            },
        }

    def _assisted(
        self,
        purpose: str,
        required: List[str],
        installed: Optional[List[str]],
        daemon_online: bool,
        report: Callable[[str], None],
    ) -> Dict[str, Any]:
        """Network available: install the daemon if absent, then pull whatever is missing."""
        installed_now = installed or []

        if not daemon_online:
            report("Ollama 가 설치되지 않았습니다 — 설치 파일을 내려받습니다.")
            self._install_ollama(report)
            probed = self.list_installed_models()
            if probed is None:
                # Installed but not answering yet. Terminal rather than a wait loop: the
                # installer may need a sign-out, and DEC-13 forbids parking the task.
                raise ProvisioningError(
                    "Ollama 설치를 완료했으나 데몬이 아직 응답하지 않습니다. 앱을 다시 실행해 주세요.",
                    required_models=required,
                )
            installed_now = probed

        missing = self.missing_models(purpose, installed_now)
        if not missing:
            report("필요한 모델이 이미 준비되어 있습니다.")
        for model in missing:
            # Named individually with its own size hint: DEC-13 forbids presenting the 274MB
            # embedder and the 4.7GB generation model as one bundled download.
            role = PURPOSE_EMBEDDING if model == required[0] else PURPOSE_GENERATION
            report(f"모델 내려받기: {model} ({MODEL_SIZE_HINTS.get(role, '크기 미상')})")
            self._pull_model(model)

        final_installed = self.list_installed_models() or []
        still_missing = self.missing_models(purpose, final_installed)
        if still_missing:
            raise ProvisioningError(
                "모델 준비를 완료하지 못했습니다.",
                required_models=still_missing,
            )

        report("프로비저닝을 완료했습니다.")
        return {
            "status": "completed",
            "result": {
                "provision_mode": MODE_ASSISTED,
                "purpose": purpose,
                "daemon_online": True,
                "required_models": required,
                "missing_models": [],
                "installed_models": final_installed,
                "pulled_models": missing,
            },
        }

    # --- side effects ---------------------------------------------------------------------

    def _install_ollama(self, report: Callable[[str], None]) -> None:
        """
        Download the installer through NetworkGuard and run it silently.

        Windows-only by nature — the installer is an `.exe` and DEC-01 ships Windows only. On a
        development host this refuses rather than pretending: a shim that "succeeded" without
        installing anything would make the assisted path untestable-by-construction and hide a
        real regression behind a green run on macOS.
        """
        if not IS_WINDOWS:
            raise ProvisioningError(
                "무인 설치는 Windows 에서만 지원됩니다. 개발 호스트에서는 Ollama 를 수동 설치하세요."
            )

        # NamedTemporaryFile(delete=False): Windows cannot execute a file while an open handle
        # holds it, so the handle is closed before the installer runs and removed in `finally`.
        fd, installer_path = tempfile.mkstemp(suffix="_OllamaSetup.exe")
        os.close(fd)
        try:
            def on_chunk(downloaded: int, total: Optional[int]) -> None:
                if total:
                    report(f"설치 파일 내려받기 {downloaded * 100 // total}%")

            try:
                self.network_guard.download_to_file(
                    "provisioning", self.installer_url, installer_path, progress_cb=on_chunk
                )
            except EgressBlockedError as e:
                # DEC-15: a redirect off the whitelist. Mapped to LLM_PROVISION_REQUIRED per
                # the issue's own instruction, and never retried (DEC-16).
                logger.warning("[Provisioning] Installer download blocked by egress whitelist")
                raise ProvisioningError(
                    "설치 파일 다운로드가 보안 정책에 의해 차단되었습니다."
                ) from e
            except (UpstreamUnavailableError, UpstreamStatusError) as e:
                raise ProvisioningError("설치 파일을 내려받지 못했습니다.") from e

            report("설치 파일을 실행합니다 (무인 설치).")
            try:
                subprocess.run(
                    [installer_path, "/VERYSILENT", "/NORESTART"],
                    check=True,
                    timeout=900,
                    # CREATE_NO_WINDOW: the shipped app is windowed (DEC-01); a console
                    # flashing up mid-install looks like malware to the user.
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.CalledProcessError as e:
                # Specific, per the issue's constraint — never a bare except. The return code
                # is logged; the installer's stderr is not surfaced to the client (DEC-03).
                logger.error("[Provisioning] Installer exited with code %s", e.returncode)
                raise ProvisioningError("Ollama 설치에 실패했습니다.") from e
            except subprocess.TimeoutExpired as e:
                raise ProvisioningError("Ollama 설치가 시간 내에 끝나지 않았습니다.") from e
        finally:
            _remove_quietly(installer_path)

    def _pull_model(self, model: str) -> None:
        """
        `ollama pull <model>` as a subprocess.

        A subprocess rather than the HTTP `POST /api/pull`: pull streams NDJSON progress for
        minutes, and `NetworkGuard.post_json` is a single-shot JSON call by design. The CLI is
        also what the documented offline procedure uses, so the two paths stay comparable.

        No retry loop (DEC-13). A failed pull ends the task with the model named.
        """
        try:
            completed = subprocess.run(
                ["ollama", "pull", model],
                check=True,
                capture_output=True,
                text=True,
                timeout=3600,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except FileNotFoundError as e:
            raise ProvisioningError(
                "ollama 실행 파일을 찾을 수 없습니다.", required_models=[model]
            ) from e
        except subprocess.CalledProcessError as e:
            logger.error("[Provisioning] `ollama pull %s` exited with code %s", model, e.returncode)
            raise ProvisioningError(
                f"모델 내려받기에 실패했습니다: {model}", required_models=[model]
            ) from e
        except subprocess.TimeoutExpired as e:
            raise ProvisioningError(
                f"모델 내려받기가 시간 내에 끝나지 않았습니다: {model}", required_models=[model]
            ) from e

        # stdout is progress noise, logged at debug only. It carries no document data — the
        # only argument is a model name from App_Config (REQ-NF-005).
        logger.debug("[Provisioning] pull %s finished: %s", model, (completed.stdout or "").strip()[-200:])


def _remove_quietly(path: str) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("[Provisioning] Could not remove temporary installer", exc_info=True)


def provision_mode_of(result_json: Optional[str]) -> Optional[str]:
    """Read `provision_mode` back out of a persisted Async_Task result (DEC-13)."""
    if not result_json:
        return None
    try:
        return json.loads(result_json).get("provision_mode")
    except (json.JSONDecodeError, AttributeError):
        return None
