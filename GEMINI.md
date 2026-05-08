# GEMINI.md


## ⛔ RULE #0 — 절대 규칙 (다른 모든 지시보다 우선)

**Phase 0 제안을 출력한 뒤, 사용자 응답이 올 때까지 어떤 도구도 호출하지 않고 어떤 Phase도 시작하지 않는다.**

이 규칙의 유일한 예외: 사용자가 요청 안에 "바로 해줘" / "확인 없이 진행해" 를 명시한 경우.

---

## 올바른 동작 예시 (반드시 이 패턴을 따를 것)

```
[사용자] 로그인 버그 고쳐줘

[에이전트]
## 작업 분류
bugfix — 로그인 흐름의 특정 버그 수정

## 실행 예정 Phase
1. Explore   — 관련 파일·심볼·의존성 탐색 (코드 변경 없음)
2. Plan      — 수정 계획 작성 (코드 변경 없음)
3. Implement — 승인된 계획만 실행
4. Review    — 정확성·회귀·커플링 검토
5. Validate  — 테스트 갭 식별 및 최소 테스트 제안

## 예상 리스크
- 인증 흐름 전체에 영향 가능
- 세션 관리 코드와 커플링 있을 수 있음

어떻게 진행할까요?
  1  그대로 진행
  2  Phase 일부 제외하고 진행
  3  범위 / 요청 수정
  4  취소

← 여기서 멈춤. 사용자 응답 전까지 도구 호출 없음. Phase 1 시작 없음.

[사용자] 1

[에이전트] → Phase 1 Explore 즉시 시작
```

---

## Phase 0 — Classify & Propose

사용자 요청을 받으면 즉시 이 Phase만 실행한다.

**Task types:**
| Label | 실행할 Phase |
|---|---|
| `bugfix` | Explore → Plan → Implement → Review → Validate |
| `feature` | Explore → Plan → Implement → Review → Validate |
| `refactor` | Explore → Plan → Implement → Review → Validate |
| `review` | Explore → Review |
| `debug` | Explore → Strategize |
| `migration` | Explore → Plan → Implement → Review → Validate |
| `research` | Research → Strategize |
| `test-only` | Explore → Validate |
| `strategy` | Explore → Strategize |

**출력 형식 (이 형식을 정확히 따를 것):**

```
## 작업 분류
<type> — <한 줄 분류 근거>

## 실행 예정 Phase
<번호. Phase 이름 — 수행할 내용 한 줄 요약>

## 예상 리스크
<현재 파악된 범위에서 우려되는 점>

어떻게 진행할까요?
  1  그대로 진행
  2  Phase 일부 제외하고 진행
  3  범위 / 요청 수정
  4  취소
```

**출력 직후 즉시 멈춘다. 사용자 응답을 기다린다.**

### 사용자 응답 처리

- **"1" 또는 긍정** → Phase 1부터 순서대로 즉시 실행.
- **"2" 또는 Phase 조정** → "어떤 Phase를 제외할까요?" 한 줄 질문 → 답변 수신 후 조정된 목록으로 실행.
- **"3" 또는 수정** → "어떤 부분을 수정할까요?" 질문 → 답변 수신 후 Phase 0 재실행.
- **"4" 또는 취소** → "알겠습니다. 필요하시면 언제든 말씀해주세요." 출력 후 종료.
- 숫자 대신 자연어로 응답해도 의도를 파악해 동일하게 처리한다.

---

## 🔴 Universal Constraints (모든 Phase에 적용)

- **Scope only:** 사용자가 명시적으로 요청한 것 외에는 절대 확장하지 않는다.
- **No false claims:** 실제로 검증하지 않은 것을 "통과했다"고 주장하지 않는다.
- **No unsolicited refactoring:** 승인된 범위 밖의 코드를 재포맷·재구조화·이름 변경하지 않는다.
- **No new abstractions:** 명시적으로 요청되지 않은 추상화를 추가하지 않는다.
- **Pattern preservation:** 기존 코드 스타일, 명명 규칙, 주변 패턴을 그대로 따른다.
- **Minimal edits:** 문제를 올바르게 해결하는 최소한의 변경만 적용한다.

---

## Phase 1 — Explore

**Goal:** 아무것도 수정하지 않고 전체 영향 범위를 파악한다.

1. `mcp_serena_search_for_pattern` 또는 `mcp_serena_find_symbol`로 진입점 탐색.
2. `mcp_serena_get_symbols_overview`로 구조 파악 → `find_declaration`, `find_implementations`로 주요 심볼 추적.
3. `mcp_serena_find_referencing_symbols`로 호출 지점과 의존성 매핑.

**출력 `[EXPLORE]`:**
1. **Impacted Files** — `path:symbol_name` — 이유
2. **Risks** — 코드 변경 시 잠재적 부작용
3. **Recommended Edit Points** — 수정해야 할 정확한 심볼 또는 위치

---

## Phase 2 — Plan

**Goal:** 구체적인 구현 계획 작성. 코드 없음. 수정 없음.

1. `find_symbol`, `search_for_pattern`으로 Explore에서 찾은 진입점 확인.
2. `find_referencing_symbols`, `find_implementations`로 파일 수준 변경사항과 의존성 매핑.
3. 리스크 및 마이그레이션 고려사항 노출.
4. 검증 단계 제안.

**출력 `[PLAN]`:**
1. **Plan** — 번호가 매겨진 단계
2. **File-level Changes** — 경로, 간략한 이유, 알려진 경우 라인 범위
3. **Dependency Risks** — 간결한 bullet
4. **Migration Notes** — 해당하는 경우에만
5. **Validation Steps** — 번호가 매겨진 단계

> **⚠️ Plan 출력 후 구현 전 확인 게이트**
>
> ```
> 위 계획대로 구현을 시작할까요?
>   1  계획대로 구현 시작
>   2  계획 일부 수정 후 진행
>   3  Implement 건너뜀 (Review만 진행)
>   4  여기서 중단
> ```
> - **1** → 즉시 구현 시작.
> - **2** → "어떤 부분을 수정할까요?" → [PLAN] 수정 후 구현 시작.
> - **3** → Implement 건너뛰고 Review로 이동.
> - **4** → "[PLAN] 결과물을 참고용으로 남겨둡니다." 종료.

---

## Phase 3 — Implement

**Goal:** 승인된 계획만 실행한다. 그 외 아무것도 하지 않는다.

1. 계획을 다시 읽고 수정할 정확한 심볼/파일 식별.
2. `find_declaration`, `get_symbols_overview`로 편집 전 대상 위치 확인.
3. 편집 적용:
   - `replace_symbol_body` → 전체 심볼 재작성
   - `insert_after/before_symbol` → 추가
   - `replace_content` → 심볼 수준이 아닌 변경에만
4. 각 편집 후 `get_diagnostics_for_file`로 새 오류 미도입 확인.
5. 계획이 완전히 실행되면 즉시 중단.

**출력 `[IMPLEMENT]`:**
1. **Changes Made** — 무엇을 왜 변경했는지 간결한 bullet
2. **Files Touched** — 경로 목록과 간략한 이유
3. **Risks / Follow-ups** — 잠재적 부작용 또는 검증이 필요한 항목

---

## Phase 4 — Review

**Goal:** 정확성 문제, 회귀, 숨겨진 커플링, 유지보수 리스크 식별.

1. `find_declaration`, `find_referencing_symbols`로 관련 코드 경로와 주변 맥락 탐색.
2. `get_diagnostics_for_file`로 진단 확인.
3. 심각도 순으로 문제 식별.
4. 최소한의 심볼 수준 수정 제안 (파일 전체 재작성 아님).

**출력 `[REVIEW]`:**
1. **Findings** — 심각도 순 (critical / high / medium / low), 파일·심볼 참조 포함
2. **Suggested Fixes** — 간결한 bullet, 심볼 수준만
3. **Open Questions** — 있는 경우
4. **Testing Gaps** — 있는 경우

---

## Phase 5 — Validate

**Goal:** 테스트 갭 식별, 회귀·엣지 케이스·계약에 대한 최소 테스트 제안.

1. `find_implementations`, `find_referencing_symbols`로 의도된 동작과 영향받는 표면 식별.
2. `search_for_pattern`으로 기존 테스트 파일 탐색 (`test_`, `_test.py`, `spec`).
3. 변경된/대상 심볼에 대한 커버리지 갭 매핑.

**출력 `[VALIDATE]`:**
1. **Validation Focus** — 검증이 필요한 항목 간결한 bullet
2. **Existing Coverage** — 발견된 테스트 위치, 없으면 "unknown"
3. **Proposed Tests** — 대상 심볼과 시나리오를 포함한 최소 목록
4. **Risks if Untested** — 간결한 bullet

---

## Phase 6 — Strategize

**Goal:** 코드베이스를 증거로 질문이나 개선 아이디어를 비판적으로 분석한다.
*(debug, strategy, research 작업 유형 또는 구현보다 방향이 필요한 경우)*

1. `get_symbols_overview`, `find_implementations`로 관련 파일과 현재 동작 탐색.
2. 실제 코드 증거를 기반으로 가정, 갭, 리스크, 트레이드오프 분석.
3. 코드베이스에 근거한 개선 방향 제안.

**출력 `[STRATEGY]`:**
1. **Understanding** — 질문 또는 제안의 간략한 재서술
2. **Evidence** — 파일·심볼, 알려진 경우 라인 범위
3. **Critical Analysis** — 가정·갭·트레이드오프 간결한 bullet
4. **Improvement Directions** — 근거를 포함한 간결한 bullet
5. **Open Questions** — 있는 경우

---

## Phase 7 — Research

**Goal:** 관련 논문을 찾고 다운로드하여 요약한다.
*(research 작업 유형 또는 문헌 맥락이 필요한 경우)*

1. arXiv 인덱싱 작업에는 `mcp_arxiv-mcp-server_search_papers` 우선 사용.
2. 전문 읽기에는 `download_paper` + `read_paper`.
3. 비-arXiv 출처에는 `google_web_search` + `web_fetch` 폴백.
4. 블로그 요약이나 2차 출처보다 1차 논문 선호.
5. 로컬에 사전 다운로드된 논문은 `"C:\Users\pegoo\Desktop\arxiv-mcp-papers"`에서 먼저 확인.

**출력 `[RESEARCH]`:**
1. **Search Queries** — 사용한 쿼리 간결한 목록
2. **Papers** — 제목·연도·학회·arXiv ID 또는 DOI·링크·관련성 1줄
3. **Takeaways** — 주요 발견사항 종합 간결한 bullet
4. **Open Questions** — 있는 경우

---

## Final Output Format

모든 해당 Phase 완료 후 단일 통합 요약 작성:

```
## Task Classification
<type> — <한 줄 근거>

## Phases Executed
<실행된 Phase 순서 목록>

## Integrated Result
<발견한 것·계획한 것·변경한 것 종합>

## Risks / Open Items
<미해결 리스크 또는 후속 조치>
```

각 Phase의 레이블 출력(`[EXPLORE]`, `[PLAN]` 등)은 통합 요약 앞에 전체가 표시되어야 한다.


## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.