**개요**
- 이 문서는 현재 저장소의 backend와 frontend 구현을 기준으로, 논문 업로드부터 AI 분석, Neo4j/Chroma 저장, 그래프 시각화, Active Recall 퀴즈, 사용자 설정까지의 기술 흐름을 정리한다.
- 참고 대상은 [backend/](backend)와 [frontend/](frontend)이며, [temp.py](temp.py)는 문서 기준에서 제외한다.

**시스템 구성**
- Backend: FastAPI + Neo4j + ChromaDB + JWT 인증
- Frontend: React 18 + React Router v6 + D3.js + Axios + TailwindCSS + Lucide Icons
- AI: OpenAI, Gemini, Ollama를 provider 설정에 따라 선택하고, 임베딩은 SentenceTransformer로 생성한다.

**애플리케이션 진입점**
- FastAPI 앱은 [backend/main.py](backend/main.py)에서 생성되며, `auth`, `user`, `papers` 라우터를 `/api/auth`, `/api/user`, `/api` prefix로 마운트한다.
- 프론트엔드는 [frontend/package.json](frontend/package.json)에서 `proxy`를 `http://localhost:8000`으로 두고 백엔드 API와 통신한다.
- React 라우팅은 `login`, `dashboard`, `graph`, `settings`로 나뉘고, 인증이 없으면 ProtectedRoute가 `/login`으로 보낸다.

**인증 흐름**
- 회원가입과 로그인은 [backend/app/api/auth.py](backend/app/api/auth.py)에서 처리한다.
- `POST /api/auth/register`는 `username`, `email`, `password`를 받아 Neo4j의 `User` 노드를 생성하고 JWT access token을 반환한다.
- `POST /api/auth/login`은 `OAuth2PasswordRequestForm` 형식의 username/password를 검증한 뒤 JWT access token을 반환한다.
- `GET /api/auth/me`는 현재 토큰의 사용자 정보를 조회한다.
- 프론트엔드는 [frontend/src/AuthContext.js](frontend/src/AuthContext.js)에서 토큰을 `localStorage`에 저장하고, Axios 기본 Authorization 헤더를 설정한다.

**사용자 설정**
- 사용자별 설정은 [backend/app/api/user.py](backend/app/api/user.py)에서 관리한다.
- `GET /api/user/stats`는 논문 수와 관계 수를 계산해 대시보드에 반환한다.
- `GET /api/user/settings`와 `POST /api/user/settings`는 `ai_provider`, `quiz_frequency`, `ai_edge_threshold`, `final_k`를 읽고 저장한다.
- 기본값은 `ai_provider=openai`, `quiz_frequency=3`, `ai_edge_threshold=0.35`, `final_k=10`이다.

**논문 업로드 처리**
- 논문 업로드는 [frontend/src/pages/Home.js](frontend/src/pages/Home.js)에서 제목과 본문을 입력한 뒤 `POST /api/papers`로 전송한다.
- 서버 측 핸들러는 [backend/app/api/papers.py](backend/app/api/papers.py)의 `upload_paper`이며, 인증된 사용자 식별자와 함께 `knowledge_base_service.add_paper(...)`를 호출한다.
- 응답이 성공하면 대시보드 통계가 갱신되고, 이후 그래프와 퀴즈 슬롯이 새 논문을 반영할 수 있다.

**AI 분석 흐름**
- 핵심 구현은 [backend/app/services/ai_service.py](backend/app/services/ai_service.py)와 [backend/app/services/knowledge_service.py](backend/app/services/knowledge_service.py)에 있다.
- `add_paper`는 먼저 Semantic Scholar에서 제목 기준으로 논문 메타데이터를 조회한 뒤, `get_keywords_and_importance(text, provider)`를 호출한다.
- provider 우선순위는 설정값에 따라 `gemini`, `openai`, `ollama` 순으로 분기되며, 실패 시 다음 provider로 폴백한다.
- 키워드 프롬프트는 요약을 생성하지 않고, 3~7개의 핵심 키워드와 각 키워드의 중요도만 반환하도록 지시한다.
- 파싱 결과는 `keywords`, `keyword_importance`로 정리되고, 임베딩은 `SentenceTransformer(settings.EMBEDDING_MODEL_NAME)`로 생성된다.
- 기본 임베딩 모델은 `thenlper/gte-large`이다.

**Semantic Scholar 연동**
- 논문 업로드와 추천 후보 보강은 Semantic Scholar Graph API를 사용한다.
- 검색과 상세 조회에서 `FIELDS_SEARCH`와 `FIELDS_DETAIL`을 사용해 `title`, `abstract`, `year`, `authors`, `tldr`, `citationCount`, `externalIds`, `references`, `citations`를 읽는다.
- 업로드 시에는 title 기반 조회로 `title`, `year`, `authors`, `citationCount`, `doi`, `tldr`, `abstract`를 보강하고, references/citations는 Neo4j의 `SemanticScholarPaper` 관계로 저장한다.

**저장 구조**
- Neo4j는 [backend/app/core/database.py](backend/app/core/database.py)를 통해 접근한다.
- 논문은 `Paper` 노드로 저장되며, `id`는 UUID, `title`, `summary`, `keywords`, `keyword_importance`, `userId`, `createdAt`를 가진다.
- 사용자와 논문은 `(:User)-[:OWNS]->(:Paper)` 관계로 연결된다.
- 논문 간 관계는 `SHADOW_LINK` 또는 `RELATED_TO`로 표현되며, `status`, `score`, `vector_score`, `keyword_score`, `description`, `question`, `commonalities`, `differences`를 저장한다.
- Semantic Scholar에서 가져온 참고 논문은 `SemanticScholarPaper` 노드로 저장되며, 추천 후보와 업로드 시의 references/citations가 여기에 연결된다.
- ChromaDB는 [backend/app/core/vector_db.py](backend/app/core/vector_db.py)에서 사용자별 컬렉션을 생성하며, 컬렉션 이름은 `papers_user_{user_id}`를 안전하게 정규화한 값이다.
- Chroma에는 논문 UUID를 `id`로 사용해 임베딩과 요약 문서, 메타데이터를 저장한다.

**추천 파이프라인**
- 추천은 [backend/app/api/papers.py](backend/app/api/papers.py)의 `POST /api/recommend/single`과 `POST /api/recommend/dual`로 시작한다.
- single 추천은 선택된 논문 하나를 기준으로 Neo4j의 references/citations를 우선 후보로 가져오고, 없으면 다른 user paper를 fallback 후보로 사용한다.
- 후보는 LLM으로 1차 선별한 뒤, 선택된 후보 5개에 대해 Semantic Scholar 재조회, 키워드 추출, 임베딩 계산, 하이브리드 점수 계산을 수행한다.
- 추천 후보의 메타데이터는 `SemanticScholarPaper`로 저장되지만, 사용자 `Paper`는 생성하지 않는다.
- 추천 결과는 `Recommendation`와 `RecommendedCandidate` 관계로 저장되며, 나중에 같은 노드를 다시 선택하면 최신 single recommendation이 자동 복원된다.
- 프론트엔드 추천 화면에서는 노드 클릭이 추천 실행이 아니라 선택만 담당하고, 실제 재실행은 Recommend 버튼으로만 수행한다.
- 추천 결과는 오른쪽 패널에 카드 형태로 나열되며, 각 카드는 GraphComponent의 Paper Info 배너처럼 제목, 연도, abstract/tldr, keywords, score를 보여준다.
- dual 추천 버튼은 현재 UI에는 노출되지만, 구현 완료 전까지는 안내 문구만 표시한다.

**추천 설정**
- 추천 결과 개수는 사용자 설정의 `final_k`를 따른다.
- [frontend/src/pages/Settings.js](frontend/src/pages/Settings.js)에서 `final_k`를 변경하면 [frontend/src/pages/Recommendations.js](frontend/src/pages/Recommendations.js)가 이를 읽어 single 추천 요청에 반영한다.

**유사도와 섀도우 링크**
- 논문 수가 `settings.MIN_PAPER_COUNT` 이상이면 `create_shadow_links`가 실행된다.
- 유사도는 임베딩 코사인 유사도 60%와 키워드 중요도 유사도 40%를 합친 하이브리드 점수로 계산한다.
- 점수가 사용자 설정 임계값 `ai_edge_threshold` 이상이면 Neo4j에 `SHADOW_LINK`가 생성되고, 기본 상태는 `pending`이다.
- 그래프 화면에서는 이 자동 후보 링크를 점선 스타일로 보여주고, 사용자가 확정하면 `confirmed` 상태로 바뀐다.

**그래프 API**
- `GET /api/graph`는 [backend/app/services/knowledge_service.py](backend/app/services/knowledge_service.py)의 `get_graph_data`를 통해 노드와 링크를 반환한다.
- 반환 형식은 대략 아래와 같다.

```json
{
  "nodes": [
    { "id": "...", "title": "...", "summary": "...", "keywords": ["..."] }
  ],
  "links": [
    { "source": "...", "target": "...", "type": "SHADOW_LINK", "score": 0.82, "status": "pending" }
  ],
  "ai_edge_threshold": 0.35
}
```

- `GET /api/graph/similarity`는 선택한 두 논문의 하이브리드 유사도를 계산한다.
- `GET /api/graph/relationship`는 기존 관계가 있으면 저장된 상세 정보를 돌려준다.

**퀴즈와 Active Recall**
- `GET /api/quiz`는 현재 사용자의 퀴즈 슬롯 목록을 반환한다.
- `POST /api/quiz/question`은 두 논문을 입력받아 관계 정의용 질문을 생성한다.
- `POST /api/quiz/confirm`은 사용자가 입력한 관계 설명을 `RELATED_TO`, `SUPPORTS`, `CONTRADICTS`, `EXTENDS` 중 하나로 저장한다.
- `POST /api/quiz/refresh`는 가장 먼저 만료되는 쿨다운 슬롯 하나를 제거해 즉시 새 슬롯이 생성되도록 한다.
- 퀴즈 확정 시에는 `QuizCooldown` 노드가 생성되어 일정 시간 동안 같은 슬롯이 바로 다시 나오지 않도록 한다.

**프론트엔드 화면 구조**
- [frontend/src/App.js](frontend/src/App.js)는 `Login`, `Home`, `Graph`, `Settings` 페이지를 라우팅한다.
- [frontend/src/components/Layout.js](frontend/src/components/Layout.js)는 좌측 사이드바와 사용자 정보, 로그아웃 버튼을 제공한다.
- [frontend/src/pages/Home.js](frontend/src/pages/Home.js)는 업로드 폼과 통계 카드를 제공한다.
- [frontend/src/pages/Graph.js](frontend/src/pages/Graph.js)는 그래프, 관계 선택, 유사도 조회, 퀴즈 패널을 함께 다룬다.
- [frontend/src/pages/Settings.js](frontend/src/pages/Settings.js)는 AI provider와 퀴즈 빈도, AI edge threshold를 설정한다.

**그래프 시각화**
- [frontend/src/components/GraphComponent.js](frontend/src/components/GraphComponent.js)는 D3 force simulation을 사용한다.
- `SHADOW_LINK`는 점선 스타일로, `RELATED_TO`는 실선 스타일로 렌더링된다.
- 링크 굵기와 투명도는 `score`와 `status`에 따라 달라진다.
- 노드는 제목과 요약을 보여주고, 두 노드를 선택하면 관계 생성 또는 확인 패널이 열린다.

**퀴즈 UI**
- [frontend/src/components/QuizComponent.js](frontend/src/components/QuizComponent.js)는 두 논문의 요약, AI 질문, 공통점, 차이점, 관계 정의, 관계 타입을 입력받는다.
- 기본 관계 타입은 `RELATED_TO`이며, 저장 전에 사용자가 바꿀 수 있다.
- Graph 페이지에서는 활성 퀴즈 슬롯을 클릭해 질문을 불러오고, 관계를 저장하면 그래프와 슬롯이 갱신된다.

**실행 관련 설정**
- 백엔드는 Neo4j와 ChromaDB가 모두 실행 중이어야 정상 동작한다.
- 환경 변수는 [backend/app/core/config.py](backend/app/core/config.py)에서 읽으며, `.env`는 프로젝트 루트 기준으로 로드된다.
- 주요 설정값은 `SECRET_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `CHROMA_PATH`, `LLM_API_KEY`, `S2_API_KEY`, `HF_TOKEN`, `EMBEDDING_MODEL_NAME`, `MIN_PAPER_COUNT`이다.

**참고 코드 위치**
- FastAPI 엔트리: [backend/main.py](backend/main.py)
- 인증 API: [backend/app/api/auth.py](backend/app/api/auth.py)
- 사용자 API: [backend/app/api/user.py](backend/app/api/user.py)
- 논문/그래프/퀴즈 API: [backend/app/api/papers.py](backend/app/api/papers.py)
- AI 서비스: [backend/app/services/ai_service.py](backend/app/services/ai_service.py)
- 지식 서비스: [backend/app/services/knowledge_service.py](backend/app/services/knowledge_service.py)
- Neo4j 클라이언트: [backend/app/core/database.py](backend/app/core/database.py)
- Chroma 클라이언트: [backend/app/core/vector_db.py](backend/app/core/vector_db.py)
- 프론트 앱: [frontend/src/App.js](frontend/src/App.js)
- 그래프 컴포넌트: [frontend/src/components/GraphComponent.js](frontend/src/components/GraphComponent.js)
- 퀴즈 컴포넌트: [frontend/src/components/QuizComponent.js](frontend/src/components/QuizComponent.js)
