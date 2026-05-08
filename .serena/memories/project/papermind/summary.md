# Project: PaperMind (Paper Knowledge Base)

## 📌 Project Overview
A full-stack application that emulates human long-term memory consolidation for research papers. It uses a graph-based structure to link related papers and reinforces knowledge through active recall quizzes.

## 🛠 Tech Stack
- **Backend:** FastAPI, Neo4j (Graph DB), ChromaDB (Vector DB).
- **Frontend:** React, TailwindCSS, D3.js (Visualization), Lucide Icons.
- **AI/ML:** 
  - Summarization: OpenAI GPT-3.5 (Primary) / Ollama Llama 3 (Fallback).
  - Embedding: Local `sentence-transformers/all-MiniLM-L6-v2`.

## 🚀 Key Features Implemented
- **Security & Multi-tenancy:**
  - JWT-based authentication (Login/Register).
  - Data isolation using `userId` in Neo4j and user-specific collections in ChromaDB.
- **Knowledge Consolidation Logic:**
  - **Threshold:** AI-driven relationship mapping (Shadow Links) only activates after **5 papers** are uploaded.
  - **Shadow Links:** Dashed edges generated via vector similarity (threshold < 0.5 distance).
  - **Active Recall Quizzes:** Users explain relationships between papers to convert Shadow Links (dashed) into confirmed links (solid).
- **Dashboard & UI:**
  - **Home:** Stats (Paper/Link count) and paper upload form.
  - **Knowledge Graph:** Interactive D3.js force-graph.
  - **Settings:** Dynamic switching between OpenAI and Ollama; adjustable quiz frequency.

## 📁 Core Directory Structure
- `backend/app/core/`: Config, Security, DB clients.
- `backend/app/api/`: Auth, User, Papers endpoints.
- `backend/app/services/`: AI processing, Knowledge graph logic.
- `frontend/src/components/`: Graph, Quiz, ProtectedRoute, Layout.
- `frontend/src/pages/`: Home, Login, Graph, Settings.

## 📝 Current Status
- Backend core, AI pipeline, and Frontend dashboard are fully implemented.
- Documentation (README.md) and environment setups (requirements.txt) are finalized.
