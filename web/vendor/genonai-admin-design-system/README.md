# @genonai/admin-design-system (local vendor)

Public npm에는 `@genonai/admin-design-system`이 없습니다(비공개 GitHub Packages).
이 디렉터리는 동일한 이름·유사한 API를 가진 **로컬 대체 패키지**입니다.

- 앱은 `"@genonai/admin-design-system": "file:./vendor/genonai-admin-design-system"` 로 참조합니다.
- 토큰/스타일: `src/styles.css` (`index.ts`에서 자동 import).
- 비공개 패키지를 쓸 수 있게 되면 `web/package.json`의 의존성만 레지스트리 버전으로 교체하면 됩니다 (`web/.npmrc.example` 참고).
