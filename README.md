# PPT List — 발표 자료 모음

발표 슬라이드를 한곳에 모아 **골라 볼 수 있는 갤러리 사이트**. 루트 `index.html`이
목록 페이지이고, 각 발표는 하위 폴더에 단일 HTML로 들어 있습니다. (CDN 의존 없음)

## ▶ 사이트
- **https://ppt-list.pages.dev/** (Cloudflare Pages)
- GitHub Pages: `https://b-hyoung.github.io/PPT-List/`

## 발표 목록
| 발표 | 폴더 | 설명 |
|------|------|------|
| 안심 스마트홈 | `smart-care-home/` | 독거노인을 위한 AIoT 안전 스마트홈 기획서 (Unreal·VR) |
| Hide In AI | `hide-in-ai/` | VR 라스트맨 스탠딩 멀티플레이 게임 발표 · [게임 레포](https://github.com/b-hyoung/HideInAI) |

## 새 발표 추가하기
1. `새폴더/index.html` 로 단일 HTML 슬라이드를 만든다.
2. 표지 썸네일을 `새폴더/thumbnail.png` 로 넣는다 (16:9 권장).
3. 루트 `index.html` 하단 `<script>`의 `decks` 배열에 항목 하나를 추가한다.
