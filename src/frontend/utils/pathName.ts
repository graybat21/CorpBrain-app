/**
 * 경로에서 마지막 폴더명을 뽑는 순수 함수 (issue #167).
 *
 * 워크스페이스 생성 시 사용자가 이름을 직접 입력하지 않았으면 선택한 폴더명을 기본 이름으로 쓴다.
 * `window` 를 읽지 않는 순수 함수라 회귀 테스트가 Node 로 그대로 실행해 검증할 수 있다.
 *
 * Windows 경로가 대상이므로 `\` 와 `/` 를 모두 구분자로 취급하고, 끝에 붙은 구분자는 무시한다.
 * 빈 문자열·구분자뿐인 입력은 `''` 를 반환한다(호출부가 "이름 못 뽑음" 으로 처리). 드라이브 루트
 * (`C:\`)는 `C:` 를 반환한다 — 폴더명이랄 게 없으므로 사용자가 이어서 수정하면 된다.
 */
export function deriveWorkspaceName(path: string): string {
  if (!path) {
    return '';
  }
  const withoutTrailing = path.replace(/[\\/]+$/, '');
  const segments = withoutTrailing.split(/[\\/]/);
  return segments[segments.length - 1] ?? '';
}
