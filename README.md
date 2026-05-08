# 🧠 PaperMind: Long-Term Memory Emulator

연구 논문의 지식 구조를 우리 뇌의 장기 기억 형성 과정처럼 구축하고 시각화하는 고성능 지식 베이스 애플리케이션입니다. 

단순히 논문을 저장하는 것을 넘어, AI가 제안한 논문 간의 관계를 사용자가 직접 정의하며 지식을 공고화(Consolidation)하는 과정을 지원합니다.

---

## 🚀 주요 기능

- **🔐 보안 및 개인화:** JWT 기반 로그인 시스템을 통해 각 사용자만의 독립적인 지식 베이스를 구축합니다.
- **📊 통합 대시보드:** 현재 저장된 논문 수, 지식 연결 수 등 학습 통계를 시각화하여 한눈에 확인합니다.
- **🤖 하이브리드 AI 분석:** OpenAI API(Cloud) 또는 로컬 Ollama(SLM)를 선택하여 논문을 자동으로 요약하고 키워드를 추출합니다.
- **🕸️ 지식 그래프 시각화:** D3.js 기반의 동적 그래프를 통해 논문 간의 관계를 탐색합니다. (확정된 관계는 실선, AI 추천 관계는 점선)
- **🧠 장기 기억 공고화 (Active Recall):** AI가 제안한 관계에 대해 직접 답변을 작성하며 기억을 강화하는 '능동 회상' 퀴즈 시스템을 제공합니다.
- **⚙️ 사용자 맞춤 설정:** 선호하는 AI 모델(OpenAI/Ollama)과 퀴즈 빈도를 설정에서 직접 제어할 수 있습니다.

## 🛠 기술 스택

- **Backend:** FastAPI, Neo4j (Graph DB), ChromaDB (Vector DB), JWT Auth
- **Frontend:** React, React Router v6, D3.js (Visualization), TailwindCSS, Lucide Icons
- **AI/ML:** Sentence-Transformers (Local Embedding), OpenAI API / Ollama (Llama 3)

---

## 📦 설치 및 실행 방법

### 1. 사전 요구사항
- Python 3.9+
- Node.js & npm
- [Neo4j Desktop](https://neo4j.com/download/) (실행 및 데이터베이스 활성화 필수)
- [Ollama](https://ollama.com/) (로컬 모델 사용 시 필요, `ollama run llama3`로 모델 다운로드 권장)

### 2. 백엔드 설정 (Backend)
```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate 

# 필수 패키지 설치
pip install -r requirements.txt

# .env 파일 설정
# backend/.env 파일을 생성하고 아래 내용을 입력하세요.
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
SECRET_KEY=your_secret_key_for_jwt
LLM_API_KEY=your_openai_api_key  # 생략 시 Ollama 자동Fallback
```

### 3. 서버 실행 (Root에서 실행 권장)
```bash
# Backend 실행
python -m uvicorn backend.main:app --reload

# Frontend 실행 (새 터미널)
cd frontend
npm install
npm start
```

---

## 🖥 사용 시나리오

1. **회원가입/로그인:** 본인만의 계정을 생성하여 개인 지식 공간을 할당받습니다.
2. **지식 축적:** 논문 제목과 본문을 업로드합니다. (최소 5개의 논문을 업로드해야 지식망 형성이 시작됩니다.)
3. **관계 탐색:** 'Knowledge Graph' 탭에서 AI가 유사도를 기반으로 생성한 점선(Shadow Links) 관계를 확인합니다.
4. **회상 및 확정:** 대시보드나 그래프 페이지에 나타나는 퀴즈에 두 논문의 관계를 설명하여 입력하면, 지식이 실선으로 확정되어 본인의 장기 기억 자산이 됩니다.
5. **개인화 설정:** 'Settings'에서 AI 엔진을 로컬(Ollama)로 바꿀지 클라우드(OpenAI)로 쓸지 결정할 수 있습니다.

## 📐 아키텍처 상세
- **Multi-tenancy:** Neo4j의 `userId` 속성 필터링과 ChromaDB의 사용자별 전용 컬렉션을 통해 완벽한 데이터 격리를 구현했습니다.
- **AI Fallback:** API Key 부재나 네트워크 오류 시 로컬 Ollama 모델로 즉시 전환되어 서비스 중단을 방지합니다.
- **Active Recall Logic:** 학습 과학의 '능동 회상' 이론을 적용하여, 사용자가 지식 간의 연결고리를 직접 언어화하도록 유도합니다.

---
## 📝 라이선스
MIT License
