/**
 * API URL 조립 — 브라우저·Node 어디서든 동일하게 동작하는 순수 함수 (issue #162).
 *
 * `window` 를 직접 읽지 않고 `locationHref` 를 인자로 받는다. 그래서 이 모듈은 다른 import 없이
 * 홀로 서고, 회귀 테스트가 Node 에서 그대로 실행해 검증할 수 있다. 실제 브라우저 값은
 * `client.ts` 의 `buildUrl` 이 `window.location.href` 로 넘긴다.
 *
 * **왜 base 를 먼저 `locationHref` 에 대해 절대화하는가 (이 버그의 핵심).**
 * 셸(`src/main.py`)과 `scripts/dev_serve.py` 는 세션 브리지에 `baseUrl: "/"` 를 주입한다 — OS 가
 * 할당한 포트를 마크업에 박지 않으려는 의도다. 그런데 WHATWG `URL` 생성자는 **base 인자가 절대
 * URL 이 아니면 `TypeError`("Failed to construct 'URL': Invalid base URL")를 던진다.** `"/"` 는
 * 상대 URL 이므로 `new URL(path, "/")` 는 던지고, 그 결과 SPA 의 모든 API 호출이 실패했다.
 * `"/"` 를 페이지 자신의 href 에 대해 먼저 해석하면 `http://127.0.0.1:<port>/` 가 되어 유효한
 * base 가 된다. 개발 시 절대 `baseUrl`(전체 URL)을 주입해도 그대로 동작한다 — 절대 URL 을 base 로
 * 다시 해석하면 자기 자신이 나온다.
 */
export function resolveApiUrl(
  baseUrl: string,
  locationHref: string,
  template: string,
  params?: Record<string, string>,
  query?: Record<string, string | number | undefined>,
): string {
  let path = template;
  for (const [key, value] of Object.entries(params ?? {})) {
    path = path.replace(`{${key}}`, encodeURIComponent(value));
  }
  const remaining = path.match(/\{(\w+)\}/);
  if (remaining) {
    throw new Error(`missing path parameter "${remaining[1]}" for ${template}`);
  }

  // Resolve the injected baseUrl against the page's own location FIRST, so a relative "/"
  // becomes an absolute base instead of throwing. Only then resolve the path against it.
  const withSlash = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
  const absoluteBase = new URL(withSlash, locationHref);
  const url = new URL(path.replace(/^\//, ''), absoluteBase);

  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}
