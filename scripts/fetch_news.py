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
    from deep_translator import MyMemoryTranslator, GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False
    print("[WARN] deep-translator not installed")

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

# عکس‌های سینمایی تیره به عنوان جایگزین (Unsplash)
CINEMA_IMAGES = [
    "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?w=900&q=80",
    "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=900&q=80",
    "https://images.unsplash.com/photo-1478720568477-152d9b164e26?w=900&q=80",
    "https://images.unsplash.com/photo-1440404653325-ab127d49abc1?w=900&q=80",
    "https://images.unsplash.com/photo-1485846234645-a62644f84728?w=900&q=80",
    "https://images.unsplash.com/photo-1594908900066-3f47337549aa?w=900&q=80",
    "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=900&q=80",
    "https://images.unsplash.com/photo-1524985069026-dd778a71c7b4?w=900&q=80",
    "https://images.unsplash.com/photo-1478146896981-b80fe463b330?w=900&q=80",
    "https://images.unsplash.com/photo-1574267432553-4b4628081c31?w=900&q=80",
]

# ================== توابع ==================

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
            # سعی در گرفتن عکس از media:content یا enclosure
            image = _get_rss_image(entry)
            source = _extract_source(url)

            if title and link:
                items.append({
                    "title": _clean(title),
                    "link": link.strip(),
                    "description": _clean(description)[:900] if description else "",
                    "pub_date": pub_date,
                    "source": source,
                    "image": image,
                })
        return items
    except Exception as e:
        print(f"[WARN] {url} → {e}")
        return []


def _get_text(elem, tags):
    for tag in tags:
        found = elem.find(tag)
        if found is not None and (found.text or list(found)):
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


def _get_rss_image(entry) -> str:
    """تلاش برای گرفتن عکس از خود RSS"""
    # media:content
    for child in entry.iter():
        tag = child.tag.lower()
        if "content" in tag or "thumbnail" in tag or "image" in tag:
            url = child.get("url") or child.get("href")
            if url and url.startswith("http") and any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                return url
        if child.tag.endswith("enclosure"):
            url = child.get("url")
            if url and "image" in (child.get("type") or ""):
                return url
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


def fetch_og_image(url: str) -> str:
    """سعی می‌کند og:image صفحه خبر را بگیرد"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = Request(url, headers=headers)
        with urlopen(req, timeout=12) as resp:
            html_content = resp.read().decode("utf-8", errors="ignore")
        # جستجوی og:image
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html_content, re.I
        )
        if not match:
            match = re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                html_content, re.I
            )
        if match:
            img = match.group(1).strip()
            if img.startswith("//"):
                img = "https:" + img
            if img.startswith("http"):
                return img
    except Exception:
        pass
    return ""


def translate_to_fa(text: str) -> str:
    """ترجمه با پاکسازی بهتر + تلاش چند سرویس"""
    if not text or not HAS_TRANSLATOR:
        return text

    # پاکسازی متن قبل از ترجمه
    clean = re.sub(r"\[.*?\]", "", text)          # حذف [EXCLUSIVE] و مشابه
    clean = re.sub(r"\(.*?\)", "", clean)         # حذف پرانتز
    clean = re.sub(r"The post .* appeared first on.*", "", clean, flags=re.I)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return text

    chunk = clean[:4000]

    # اول MyMemory
    try:
        result = MyMemoryTranslator(source="en", target="fa").translate(chunk)
        time.sleep(0.4)
        if result and len(result) > 5 and result.lower() != chunk.lower():
            return result.strip()
    except Exception as e:
        print(f"[WARN] MyMemory: {e}")

    # فال‌بک Google
    try:
        result = GoogleTranslator(source="en", target="fa").translate(chunk)
        time.sleep(0.4)
        if result:
            return result.strip()
    except Exception as e:
        print(f"[WARN] Google: {e}")

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

    # ========== حذف تکراری خیلی قوی ==========
    from difflib import SequenceMatcher

    def normalize_title(t: str) -> str:
        t = t.lower()
        t = re.sub(r"[‘’“”\"'`]", "", t)
        junk = [
            "exclusive", "breaking", "official", "the wrap", "variety",
            "deadline", "hollywood reporter", "indiewire", "report", "says",
            "reveals", "announces", "unveils", "first-look", "photo",
            "guest star", "guest-starring", "season 3", "season 2", "premiere",
            "to", "on", "in", "with", "for", "a", "the", "and", "of", "as",
            "recruits", "reunites", "returns", "casts", "joins"
        ]
        for w in junk:
            t = re.sub(rf"\b{re.escape(w)}\b", " ", t)
        t = re.sub(r"[^a-z0-9\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def extract_key_phrases(t: str) -> set:
        t = t.lower()
        phrases = set()
        words = re.findall(r"[a-z0-9]+", t)
        for i in range(len(words) - 1):
            pair = words[i] + " " + words[i+1]
            if len(words[i]) > 2 and len(words[i+1]) > 2:
                phrases.add(pair)
        for w in words:
            if len(w) >= 5:
                phrases.add(w)
        return phrases

    def is_duplicate(a: str, b: str) -> bool:
        a_low, b_low = a.lower(), b.lower()
        na = normalize_title(a)
        nb = normalize_title(b)
        if not na or not nb:
            return False

        # قانون سخت: اگر نام شخص + نام پروژه مشترک باشد
        people = ["damon wayans", "jean smart", "wagner moura", "jacob elordi",
                  "scarlett johansson", "dakota fanning", "david alan grier"]
        shows = ["st. denis", "st denis", "denis medical", "hacks", "the last house",
                 "living color", "in living color"]
        for person in people:
            if person in a_low and person in b_low:
                for show in shows:
                    if show in a_low and show in b_low:
                        return True
                # حتی بدون show، اگر همان شخص در هر دو باشد و کلمات مشترک زیاد
                wa = set(na.split())
                wb = set(nb.split())
                if len(wa & wb) >= 3:
                    return True

        ratio = SequenceMatcher(None, na, nb).ratio()
        if ratio >= 0.45:
            return True
        wa = set(na.split())
        wb = set(nb.split())
        if len(wa) >= 2 and len(wb) >= 2:
            overlap = len(wa & wb) / min(len(wa), len(wb))
            if overlap >= 0.45:
                return True
        pa = extract_key_phrases(a)
        pb = extract_key_phrases(b)
        common = pa & pb
        if len(common) >= 2:
            return True
        strong = {p for p in common if " " in p and len(p) > 8}
        if strong:
            return True
        return False

    unique = []
    for item in important:
        is_dup = False
        for existing in unique:
            if is_duplicate(item["title"], existing["title"]):
                is_dup = True
                if item["score"] > existing["score"] or len(item.get("description","")) > len(existing.get("description","")):
                    unique.remove(existing)
                    unique.append(item)
                break
        if not is_dup:
            unique.append(item)

    final = unique[:MAX_NEWS]
    print(f"\nSelected {len(final)} unique important news (duplicates removed).")
    print("Fetching images + translating...")

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(final),
        "news": []
    }

    for i, item in enumerate(final):
        title_en = item["title"]
        excerpt_en = item["description"][:500] + ("..." if len(item["description"]) > 500 else "")

        # عکس: اول از RSS، بعد og:image، بعد عکس سینمایی
        image = item.get("image") or ""
        if not image:
            print(f"  [{i+1}] fetching og:image for: {title_en[:50]}...")
            image = fetch_og_image(item["link"])
            time.sleep(0.6)

        if not image:
            image = CINEMA_IMAGES[i % len(CINEMA_IMAGES)]

        title_fa = translate_to_fa(title_en)
        # اگر ترجمه شکست خورد و هنوز انگلیسی بود، دوباره تلاش کن یا همون عنوان رو بگذار
        if not title_fa or title_fa.strip() == title_en.strip() or re.search(r"[a-zA-Z]{4,}", title_fa) and not re.search(r"[\u0600-\u06FF]", title_fa):
            title_fa = translate_to_fa(title_en) or title_en

        excerpt_fa = translate_to_fa(excerpt_en) if excerpt_en else title_fa
        if excerpt_en and (not excerpt_fa or not re.search(r"[\u0600-\u06FF]", excerpt_fa)):
            excerpt_fa = translate_to_fa(excerpt_en) or excerpt_en

        content_en = item["description"] or title_en
        content_fa = translate_to_fa(content_en[:800]) if content_en else excerpt_fa
        if content_en and (not content_fa or not re.search(r"[\u0600-\u06FF]", content_fa)):
            content_fa = translate_to_fa(content_en[:600]) or content_en

        output["news"].append({
            "id": item["id"],
            "title": {"en": title_en, "fa": title_fa},
            "excerpt": {"en": excerpt_en, "fa": excerpt_fa},
            "content": {"en": content_en, "fa": content_fa},
            "source": {"en": item["source"], "fa": item["source"]},
            "link": item["link"],
            "date": item["date"],
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
