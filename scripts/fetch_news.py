#!/usr/bin/env python3
"""
آنکات - اسکریپت جمع‌آوری خودکار اخبار مهم سینمایی
هر ۱ ساعت توسط GitHub Actions اجرا می‌شود.
منابع: Deadline, Variety, Hollywood Reporter, The Wrap, IndieWire
"""

import json
import re
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import html
import xml.etree.ElementTree as ET

try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False
    print("[WARN] deep-translator not installed – titles will stay in English")

# ================== تنظیمات ==================
RSS_FEEDS = [
    "https://deadline.com/feed/",
    "https://variety.com/feed/",
    "https://www.hollywoodreporter.com/feed/",
    "https://www.thewrap.com/feed/",
    "https://www.indiewire.com/feed/",
]

IMPORTANT_KEYWORDS = [
    r"\brenew(ed|al|s)?\b", r"\bcancel(led|s|ation)?\b", r"\bpremiere[sd]?\b",
    r"\bofficial\b", r"\btrailer\b", r"\bteaser\b", r"\bcast(ing)?\b",
    r"\border(ed)?\b", r"\bpick(ed)?\s*up\b", r"\bgreenlight\b",
    r"\bbox\s*office\b", r"\brelease\s*date\b", r"\bset\s*to\b",
    r"\bnetflix\b", r"\bhulu\b", r"\bdisney\+?\b", r"\bmax\b", r"\bhbo\b",
    r"\bprime\s*video\b", r"\bamazon\b", r"\bapple\s*tv\+?\b", r"\bparamount\+?\b",
    r"\bpeacock\b", r"\bseason\s*\d+", r"\bfilm(ing)?\b", r"\bseries\b",
    r"\bmovie\b", r"\bdocumentary\b", r"\bexclusive\b", r"\bbreaking\b",
    r"\bannounces?\b", r"\bunveils?\b", r"\bdrops?\b", r"\blaunches?\b",
    r"\bacquires?\b", r"\bdeal\b", r"\bpartnership\b",
]

MAX_NEWS = 24
OUTPUT_PATH = Path(__file__).parent.parent / "news.json"

# ================== توابع کمکی ==================

def fetch_rss(url: str) -> list[dict]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; UncutNewsBot/1.0)"}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=25) as resp:
            content = resp.read()
        root = ET.fromstring(content)

        items = []
        channel = root.find("channel")
        if channel is not None:
            entries = channel.findall("item")
        else:
            entries = root.findall("{http://www.w3.org/2005/Atom}entry") or []

        for entry in entries:
            title = _get_text(entry, ["title", "{http://www.w3.org/2005/Atom}title"])
            link = _get_link(entry)
            description = _get_text(entry, [
                "description", "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://www.w3.org/2005/Atom}content"
            ])
            pub_date = _get_text(entry, [
                "pubDate", "published", "updated",
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated"
            ])
            source = _extract_source(url)

            if title and link:
                items.append({
                    "title": _clean(title),
                    "link": link.strip(),
                    "description": _clean(description)[:450] if description else "",
                    "pub_date": pub_date,
                    "source": source,
                })
        return items
    except Exception as e:
        print(f"[WARN] {url} → {e}")
        return []


def _get_text(elem, tags):
    for tag in tags:
        found = elem.find(tag)
        if found is not None and (found.text or list(found)):
            # ممکن است داخل CDATA یا تگ‌های تو در تو باشد
            return "".join(found.itertext())
    return ""


def _get_link(elem):
    link = elem.find("link")
    if link is not None:
        return link.text or link.get("href") or ""
    for child in elem:
        if child.tag.endswith("link") and child.get("href"):
            return child.get("href")
    return ""


def _extract_source(feed_url: str) -> str:
    mapping = {
        "deadline": "Deadline",
        "variety": "Variety",
        "hollywoodreporter": "The Hollywood Reporter",
        "thewrap": "The Wrap",
        "indiewire": "IndieWire",
    }
    for key, name in mapping.items():
        if key in feed_url:
            return name
    return "Cinema News"


def _clean(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_important(title: str, description: str) -> bool:
    text = (title + " " + description).lower()
    return any(re.search(p, text, re.I) for p in IMPORTANT_KEYWORDS)


def score_importance(title: str, description: str) -> int:
    text = (title + " " + description).lower()
    score = 0
    high = ["renewed", "canceled", "cancelled", "premiere", "official trailer",
            "season", "netflix", "disney+", "hbo", "exclusive", "greenlight"]
    medium = ["casting", "orders", "box office", "release date", "announces",
              "acquires", "deal", "trailer", "teaser"]
    for w in high:
        if w in text:
            score += 3
    for w in medium:
        if w in text:
            score += 1
    return score


def parse_date(date_str: str) -> datetime:
    if not date_str:
        return datetime.now(timezone.utc)
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip()[:30], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def translate_to_fa(text: str) -> str:
    """ترجمه به فارسی با GoogleTranslator (رایگان و بدون کلید)"""
    if not text or not HAS_TRANSLATOR:
        return text
    try:
        # محدودیت طول برای جلوگیری از خطا
        chunk = text[:4500]
        result = GoogleTranslator(source="en", target="fa").translate(chunk)
        time.sleep(0.4)  # احترام به rate limit
        return result or text
    except Exception as e:
        print(f"[WARN] Translation failed: {e}")
        return text


def make_id(title: str, link: str) -> str:
    return hashlib.md5((title + link).encode("utf-8")).hexdigest()[:12]


def main():
    print("=== Uncut Auto News Fetcher ===")
    all_items = []

    for feed in RSS_FEEDS:
        print(f"→ {feed}")
        items = fetch_rss(feed)
        print(f"  {len(items)} items")
        all_items.extend(items)

    # فیلتر + امتیاز
    important = []
    for item in all_items:
        if is_important(item["title"], item["description"]):
            item["score"] = score_importance(item["title"], item["description"])
            item["id"] = make_id(item["title"], item["link"])
            item["date"] = parse_date(item["pub_date"]).isoformat()
            important.append(item)

    important.sort(key=lambda x: (x["score"], x["date"]), reverse=True)

    # حذف تکراری
    seen = set()
    unique = []
    for item in important:
        norm = re.sub(r"[^a-z0-9]", "", item["title"].lower())[:55]
        if norm not in seen:
            seen.add(norm)
            unique.append(item)

    final = unique[:MAX_NEWS]
    print(f"\nSelected {len(final)} important news. Translating...")

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(final),
        "news": []
    }

    for item in final:
        title_en = item["title"]
        excerpt_en = item["description"][:300] + ("..." if len(item["description"]) > 300 else "")

        title_fa = translate_to_fa(title_en)
        excerpt_fa = translate_to_fa(excerpt_en) if excerpt_en else title_fa

        # تصویر تصادفی اما ثابت برای هر خبر (چون RSS عکس ندارد)
        image = f"https://picsum.photos/seed/uncut{item['id']}/900/500"

        output["news"].append({
            "id": item["id"],
            "title": {"en": title_en, "fa": title_fa},
            "excerpt": {"en": excerpt_en, "fa": excerpt_fa},
            "content": {"en": item["description"] or title_en, "fa": excerpt_fa},
            "source": {"en": item["source"], "fa": item["source"]},
            "link": item["link"],
            "date": item["date"][:10],
            "image": image,
            "important": item["score"] >= 4,
            "score": item["score"]
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Done → {OUTPUT_PATH} ({len(final)} news)")
    print(f"Updated: {output['updated_at']}")


if __name__ == "__main__":
    main()
