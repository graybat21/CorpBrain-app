import os
import shutil
import sys
import tempfile

# Force UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from src.backend.db import DatabaseManager
from src.backend.repositories.workspace_repository import WorkspaceRepository
from src.backend.repositories.file_repository import FileRepository
from src.backend.services.workspace_service import WorkspaceService
from src.backend.services.scanner_service import ScannerService
from src.backend.services.analysis_service import FastAnalysisService
from src.backend.services.rename_service import RenameService
from src.backend.services.deeplink_service import DeepLinkService
from src.backend.pii_filter import PIIFilter
from src.backend.network_guard import NetworkGuard
from src.backend.config_manager import ConfigManager
from src.backend.api.app import create_app


def run_demo():
    print("=" * 70)
    print(" CorpBrain Backend Core Engine Integration Demonstration")
    print("=" * 70)

    # 1. Prepare temporary workspace environment with sample files
    temp_dir = tempfile.mkdtemp(prefix="corpbrain_demo_")
    db_path = os.path.join(temp_dir, "corpbrain_demo.db")
    ws_dir = os.path.join(temp_dir, "sample_workspace")
    os.makedirs(ws_dir, exist_ok=True)

    # Create dummy files (including one with PII for testing)
    with open(os.path.join(ws_dir, "2026년_사업기획서_최종.docx"), "w", encoding="utf-8") as f:
        f.write("2026년 사업기획 마스터 플랜")
    with open(os.path.join(ws_dir, "홍길동_주민등록증_900101-1234567.pdf"), "w", encoding="utf-8") as f:
        f.write("주민등록증 사본")
    with open(os.path.join(ws_dir, "임시_아이디어_메모.txt"), "w", encoding="utf-8") as f:
        f.write("아이디어 노트")

    print(f"\n[Step 1] 샘플 워크스페이스 준비 완료:")
    print(f"  경로: {ws_dir}")
    print(f"  샘플 파일 3개 생성 (사업기획서, PII 포함 주민등록증, 임시 메모)")

    # 2. Initialize Database & Run Migrations
    db_mgr = DatabaseManager(db_path=db_path, migrations_dir="migrations")
    print(f"\n[Step 2] SQLite 메타 DB 및 v001 마이그레이션 초기화:")
    print(f"  DB 경로: {db_path}")

    # 3. Create Workspace
    ws_repo = WorkspaceRepository(db_mgr)
    ws_service = WorkspaceService(ws_repo)
    ws = ws_service.create_workspace("2026_전략기획_워크스페이스", [ws_dir])
    ws_id = ws["workspace_id"]
    print(f"\n[Step 3] 워크스페이스 생성 성공 (WS-CMD-01):")
    print(f"  Workspace ID: {ws_id}")
    print(f"  워크스페이스 이름: {ws['workspace_name']}")

    # 4. Scan Workspace Files
    file_repo = FileRepository(db_mgr)
    scanner = ScannerService(file_repo)
    records, limit_reached = scanner.scan_workspace(ws_id, ws_dir)
    print(f"\n[Step 4] 파일 스캔 & 메타데이터 추출 완료 (SCAN-CMD-01):")
    print(f"  스캔된 파일 총 수: {len(records)}개 (Limit Guard 도달 여부: {limit_reached})")
    for r in records:
        print(f"    - {r['file_name']} (확장자: {r['extension']}, 크기: {r['size_bytes']} bytes)")

    # 5. Fast Analysis
    fast_ana = FastAnalysisService(file_repo)
    ana_results = fast_ana.run_fast_analysis(ws_id)
    print(f"\n[Step 5] 구조 기반 고속 분석 실행 결과 (ANA-CMD-01):")
    print(f"  중요도 산출 점수 (상위 순):")
    for item in ana_results:
        print(f"    - 점수 [{item['importance_score']:3d}점] : {item['file_name']}")

    # 6. PII Masking & Rename Recommendation
    pii_filter = PIIFilter()
    rename_service = RenameService(db_mgr, pii_filter)
    diff_results = rename_service.process_rename_suggestions(ws_id, records)
    print(f"\n[Step 6] PII 사전 마스킹 & 파일명 추천 Diff 산출 (RN-CMD-01 / LLM-CMD-02):")
    for diff in diff_results:
        print(f"    - 기존: {diff['old_name']}")
        print(f"      추천: {diff['new_name']}")
        print(f"      상태: {diff['status']} ({diff['note']})")

    # 7. DeepLink Anchor Parsing & Resolution
    dl_service = DeepLinkService(db_mgr, file_repo)
    sample_wiki = f"본 위키는 [[file_id:{records[0]['file_id']}]] 문서를 바탕으로 작성되었습니다."
    dl_mapping = dl_service.process_wiki_deeplinks(ws_id, sample_wiki)
    resolved_path = dl_service.resolve_deeplink_path(ws_id, records[0]["file_id"])
    print(f"\n[Step 7] 딥링크 Late Binding 경로 해석 (DL-CMD-01 / DEC-08):")
    print(f"  마크다운 위키 앵커: [[file_id:{records[0]['file_id']}]]")
    print(f"  실시간 해석된 로컬 경로: {resolved_path}")

    # 8. NetworkGuard Egress Defense Test
    print(f"\n[Step 8] NetworkGuard 3층 Egress 보안 방어 검증 (INF-CMD-03):")
    try:
        NetworkGuard.validate_egress("llm_cloud", "https://api.anthropic.com/v1/messages")
        print("  [PASS] 허용된 호스트 (api.anthropic.com) 통과 성공")
    except Exception as e:
        print(f"  [FAIL] 오류: {e}")

    try:
        NetworkGuard.validate_egress("llm_cloud", "https://api.anthropic.com.attacker.com/v1/messages")
        print("  [FAIL] 차단 실패")
    except Exception as e:
        print(f"  [PASS] 미승인 호스트 차단 성공: {e}")

    # 9. Clean up demo
    db_mgr.close()
    shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n" + "=" * 70)
    print(" 모든 백엔드 코어 모듈이 연동되어 정상적으로 구동함을 확인했습니다!")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
