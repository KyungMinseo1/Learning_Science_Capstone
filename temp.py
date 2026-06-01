import requests
import json
import time
import random
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = "https://api.semanticscholar.org/graph/v1"
REC_URL  = "https://api.semanticscholar.org/recommendations/v1"

API_KEY = os.getenv("S2_API_KEY")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

# search용 (references/citations 제외)
FIELDS_SEARCH = ",".join([
    "title", "abstract", "year", "authors",
    "tldr", "externalIds", "citationCount", "url",
])

# detail/recommendation용 (references, citations 포함)
FIELDS_DETAIL = ",".join([
    "title", "abstract", "year", "authors",
    "tldr", "externalIds", "citationCount", "url",
    "references.paperId", "references.title", "references.year", "references.authors",
    "citations.paperId", "citations.title", "citations.year", "citations.authors",
])


def _get(url: str, params: dict, max_retries: int = 6) -> dict:
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)

            if resp.status_code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"  [429] Rate limited. {wait:.1f}초 후 재시도... (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            print(f"  [Timeout] attempt {attempt+1}/{max_retries}")
            time.sleep(2 ** attempt)

    raise RuntimeError(f"Max retries exceeded for {url}")


def search_by_title(query: str, limit: int = 3) -> list[dict]:
    data = _get(f"{BASE_URL}/paper/search", {"query": query, "fields": FIELDS_SEARCH, "limit": limit})
    return data.get("data", [])


def get_paper_detail(paper_id: str) -> dict:
    return _get(f"{BASE_URL}/paper/{paper_id}", {"fields": FIELDS_DETAIL})


def get_recommendations(paper_id: str, limit: int = 5) -> list[dict]:
    """
    Recommendations API는 fields 파라미터 형식이 다름 → FIELDS_SEARCH만 사용
    paper_id는 반드시 SS 내부 ID (paperId) 여야 함 (arXiv ID 안 됨)
    """
    data = _get(
        f"{REC_URL}/papers/forpaper/{paper_id}",
        {"fields": FIELDS_SEARCH, "limit": limit},
    )
    return data.get("recommendedPapers", [])


def print_paper(paper: dict, show_references: bool = False):
    print("-" * 65)
    print(f"  제목    : {paper.get('title', 'N/A')}")
    print(f"  연도    : {paper.get('year', 'N/A')}")
    authors = [a.get("name", "") for a in paper.get("authors", [])]
    print(f"  저자    : {', '.join(authors[:3])}{'...' if len(authors) > 3 else ''}")
    print(f"  인용수  : {paper.get('citationCount', 'N/A')}")
    ext = paper.get("externalIds") or {}
    if ext.get("ArXiv"):
        print(f"  arXiv   : {ext['ArXiv']}")
    if ext.get("DOI"):
        print(f"  DOI     : {ext['DOI']}")
    tldr = paper.get("tldr")
    if tldr:
        print(f"  TLDR    : {tldr.get('text', '')[:200]}")
    abstract = paper.get("abstract") or ""
    if abstract:
        print(f"  Abstract: {abstract[:200]}{'...' if len(abstract) > 200 else ''}")

    if show_references:
        refs = paper.get("references") or []
        print(f"\n  📎 References ({len(refs)}개):")
        for r in refs[:5]:  # 너무 많으니 상위 5개만
            r_authors = [a.get("name", "") for a in r.get("authors", [])]
            print(f"    - {r.get('title', 'N/A')} ({r.get('year', '?')}) / {', '.join(r_authors[:2])}")
        if len(refs) > 5:
            print(f"    ... 외 {len(refs)-5}개")

        cits = paper.get("citations") or []
        print(f"\n  📣 Citations ({len(cits)}개):")
        for c in cits[:5]:
            c_authors = [a.get("name", "") for a in c.get("authors", [])]
            print(f"    - {c.get('title', 'N/A')} ({c.get('year', '?')}) / {', '.join(c_authors[:2])}")
        if len(cits) > 5:
            print(f"    ... 외 {len(cits)-5}개")


if __name__ == "__main__":

    # [STEP 1] 제목으로 검색
    print("\n▶ STEP 1: 제목으로 검색")
    results = search_by_title(
        "UCO: A Multi-Turn Interactive Reinforcement Learning Method for Adaptive Teaching with Large Language Models",
        limit=1
    )
    for p in results:
        print_paper(p)
    time.sleep(2)

    # [STEP 2] arXiv ID로 상세 조회 (references/citations 포함)
    print("\n▶ STEP 2: arXiv ID로 상세 조회 (references/citations 포함)")
    paper = get_paper_detail("arXiv:1706.03762")
    print_paper(paper, show_references=True)
    ss_id = paper.get("paperId")
    print(f"\n  → SS Paper ID: {ss_id}")
    time.sleep(2)

    # [STEP 3] Recommendations - ss_id 필수 (arXiv ID 안 됨!)
    print(f"\n▶ STEP 3: 관련 논문 추천")
    if ss_id:
        recs = get_recommendations(ss_id, limit=5)
        if recs:
            for p in recs:
                print_paper(p)
        else:
            print("  추천 논문 없음 (논문에 따라 recommendations 미지원 케이스 있음)")
    time.sleep(2)

    # [STEP 4] DB 저장용 메타데이터
    print("\n▶ STEP 4: DB 저장용 메타데이터 추출")
    results2 = search_by_title("GRPO reinforcement learning language model", limit=1)
    if results2:
        p = results2[0]
        metadata = {
            "ss_paper_id":    p.get("paperId"),
            "title":          p.get("title"),
            "abstract":       p.get("abstract"),
            "year":           p.get("year"),
            "authors":        [a["name"] for a in p.get("authors", [])],
            "tldr":           (p.get("tldr") or {}).get("text"),
            "doi":            (p.get("externalIds") or {}).get("DOI"),
            "arxiv_id":       (p.get("externalIds") or {}).get("ArXiv"),
            "citation_count": p.get("citationCount"),
            "url":            p.get("url"),
        }
        print(json.dumps(metadata, indent=2, ensure_ascii=False))