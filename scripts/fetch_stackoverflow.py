"""
Fetch real CI/CD errors and fixes from Stack Exchange API.

Downloads top-voted Q&A from Stack Overflow for CI/CD-related tags.
Each document contains a real error question + real accepted answer.

No API key needed — uses public access (300 requests/day).

Usage: python scripts/fetch_stackoverflow.py
"""

import os
import json
import time
import gzip
import re
import urllib.request
import urllib.error
import urllib.parse
import html as html_module

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "stackoverflow")

# Tags sorted by relevance to CI/CD debugging
SO_TAGS = [
    "github-actions", "docker", "dockerfile", "docker-compose",
    "kubernetes", "jenkins", "gitlab-ci", "circleci",
    "pip", "npm", "npm-install", "yarn",
    "webpack", "pytest", "maven", "gradle",
    "continuous-integration", "deployment",
    "permission-denied", "environment-variables",
    "build-error", "ssl-certificate", "nginx",
    "travis-ci", "azure-devops",
    "setuptools", "virtualenv", "pnpm",
    "terraform", "ansible", "helm",
]

API_BASE = "https://api.stackexchange.com/2.3"
REQUESTS_MADE = 0
MAX_REQUESTS = 280


def api_get(url):
    """Raw GET request to SE API, handles gzip."""
    global REQUESTS_MADE
    if REQUESTS_MADE >= MAX_REQUESTS:
        return None

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "DevOps-Copilot/1.0",
            "Accept-Encoding": "gzip",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            try:
                raw = gzip.decompress(raw)
            except:
                pass
            REQUESTS_MADE += 1
            result = json.loads(raw.decode("utf-8"))

            # Check for backoff
            if "backoff" in result:
                wait = result["backoff"]
                print(f"    [BACKOFF] Waiting {wait}s...")
                time.sleep(wait)

            return result
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("    [THROTTLED] Waiting 60s...")
            time.sleep(60)
            return api_get(url)  # retry
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except:
            pass
        print(f"    [HTTP {e.code}] {body}")
        return None
    except Exception as e:
        print(f"    [ERROR] {e}")
        return None


def strip_html(text):
    """Convert HTML to plain text."""
    text = html_module.unescape(text or "")
    text = re.sub(r'<code>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)
    text = re.sub(r'<pre[^>]*>(.*?)</pre>', r'\n```\n\1\n```\n', text, flags=re.DOTALL)
    text = re.sub(r'<li>', '\n- ', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_tag(tag, site="stackoverflow"):
    """Fetch questions + answers for a tag using simple built-in filters."""
    docs = []

    for page in range(1, 4):  # 3 pages = up to 300 questions
        if REQUESTS_MADE >= MAX_REQUESTS:
            break

        # Step 1: Get question IDs (minimal data, just to get IDs with accepted answers)
        url = (
            f"{API_BASE}/search/advanced"
            f"?page={page}&pagesize=100"
            f"&order=desc&sort=votes"
            f"&tagged={urllib.parse.quote(tag)}"
            f"&site={site}"
            f"&accepted=True&answers=1"
            f"&filter=default"
        )
        result = api_get(url)
        if not result or "items" not in result:
            break

        questions = result["items"]
        if not questions:
            break

        quota = result.get("quota_remaining", "?")
        print(f"    Q page {page}: {len(questions)} Qs (quota: {quota})")

        # Get IDs of questions with accepted answers
        q_map = {}
        for q in questions:
            if q.get("accepted_answer_id"):
                q_map[q["question_id"]] = q

        if not q_map:
            if not result.get("has_more"):
                break
            time.sleep(1)
            continue

        # Step 2: Fetch question bodies in bulk
        ids = ";".join(str(qid) for qid in list(q_map.keys())[:100])
        url2 = (
            f"{API_BASE}/questions/{ids}"
            f"?pagesize=100&site={site}"
            f"&filter=withbody"
        )
        q_result = api_get(url2)
        if q_result and "items" in q_result:
            for qi in q_result["items"]:
                qid = qi["question_id"]
                if qid in q_map:
                    q_map[qid]["body"] = qi.get("body", "")

        time.sleep(0.5)

        # Step 3: Fetch accepted answer bodies in bulk
        answer_ids = [str(q_map[qid]["accepted_answer_id"]) for qid in q_map if q_map[qid].get("accepted_answer_id")]
        if not answer_ids:
            continue

        for i in range(0, len(answer_ids), 100):
            if REQUESTS_MADE >= MAX_REQUESTS:
                break
            batch = ";".join(answer_ids[i:i+100])
            url3 = (
                f"{API_BASE}/answers/{batch}"
                f"?pagesize=100&site={site}"
                f"&filter=withbody"
            )
            a_result = api_get(url3)
            if not a_result or "items" not in a_result:
                continue

            ans_map = {a["answer_id"]: a for a in a_result["items"]}

            for qid, q in q_map.items():
                aid = q.get("accepted_answer_id")
                if aid and aid in ans_map:
                    a = ans_map[aid]
                    q_body = strip_html(q.get("body", ""))
                    a_body = strip_html(a.get("body", ""))

                    if len(a_body) < 30:
                        continue

                    docs.append({
                        "title": html_module.unescape(q.get("title", "")),
                        "question": q_body[:3000],
                        "answer": a_body[:5000],
                        "tags": q.get("tags", []),
                        "q_score": q.get("score", 0),
                        "a_score": a.get("score", 0),
                        "url": q.get("link", f"https://stackoverflow.com/q/{qid}"),
                    })

            time.sleep(0.5)

        if not result.get("has_more"):
            break
        time.sleep(1)

    return docs


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total_docs = 0
    total_size = 0

    print("=" * 60)
    print("DOWNLOADING REAL CI/CD Q&A FROM STACK OVERFLOW")
    print("=" * 60)

    for tag in SO_TAGS:
        if REQUESTS_MADE >= MAX_REQUESTS:
            print(f"\n  [LIMIT] Reached {MAX_REQUESTS} API requests")
            break

        safe_name = tag.replace(".", "_").replace("-", "_")
        out_file = os.path.join(OUTPUT_DIR, f"so_{safe_name}.json")

        # Skip already fetched
        if os.path.exists(out_file) and os.path.getsize(out_file) > 500:
            with open(out_file, "r", encoding="utf-8") as f:
                count = len(json.load(f))
            fsize = os.path.getsize(out_file)
            print(f"  [SKIP] {tag}: {count} docs ({fsize/1024:.0f} KB)")
            total_docs += count
            total_size += fsize
            continue

        print(f"  [TAG]  {tag}")
        docs = fetch_tag(tag, "stackoverflow")

        if docs:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(docs, f, ensure_ascii=False, indent=1)
            fsize = os.path.getsize(out_file)
            print(f"         => {len(docs)} docs ({fsize/1024:.0f} KB)")
            total_docs += len(docs)
            total_size += fsize
        else:
            print(f"         => 0 docs")

    print()
    print("=" * 60)
    print(f"DONE!")
    print(f"  Total Q&A pairs: {total_docs}")
    print(f"  Total size:      {total_size/(1024*1024):.1f} MB")
    print(f"  API requests:    {REQUESTS_MADE}/{MAX_REQUESTS}")
    print(f"  Location:        {os.path.abspath(OUTPUT_DIR)}")
    print()
    print("Run again tomorrow to fetch more tags (skips existing)!")
    print("=" * 60)


if __name__ == "__main__":
    main()
