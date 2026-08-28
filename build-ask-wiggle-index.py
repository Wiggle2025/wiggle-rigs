#!/usr/bin/env python3
"""Build the Ask Wiggle search index from the live site and Rig Finder data."""

from __future__ import annotations

import argparse
import difflib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path


BASE = "https://wiggleyawormrigs.com"
SITEMAPS = {
    "website": f"{BASE}/sitemap.website.xml",
    "blog": f"{BASE}/sitemap.blog.xml",
    "shop": f"{BASE}/sitemap.ols.xml",
}
USER_AGENT = "AskWiggleIndexBuilder/1.0 (+https://wiggleyawormrigs.com)"

SYNONYMS = {
    "mulloway": ["jewfish", "jewie", "jewies"],
    "jewfish": ["mulloway", "jewie", "jewies"],
    "luderick": ["blackfish"],
    "blackfish": ["luderick"],
    "australian salmon": ["salmon", "aussie salmon"],
    "gummy shark": ["gummy", "school shark", "flake"],
    "school shark": ["gummy shark", "gummy", "flake"],
    "flathead": ["flatty", "flatties", "lizard"],
    "whiting": ["ting", "tings"],
    "paternoster": ["dropper rig", "dropper", "bottom rig"],
    "running sinker": ["fish finder", "fishfinder"],
    "fish finder": ["running sinker", "fishfinder"],
    "long cast": ["distance casting", "pulley rig", "long distance"],
    "leader": ["trace"],
    "trace": ["leader"],
    "mono": ["monofilament"],
    "monofilament": ["mono"],
    "tangle": ["tangling", "tangled", "wrap", "wrapping"],
    "snag": ["snagging", "snagged", "caught on rocks"],
    "bite off": ["bite-off", "bitten off"],
}

BOILERPLATE = {
    "home", "sign in", "create account", "orders", "my account", "sign out",
    "privacy policy", "terms and conditions", "powered by", "drop us a line!",
    "cancel", "send", "accept", "share this post:", "read more",
}

EXCLUDED_PATHS = {
    "/", "/terms-and-conditions", "/privacy-policy", "/wiggles-blog",
    "/m/login", "/m/reset", "/m/create", "/m/create-account",
    "/snapper-rigs-in-australia",  # Retained older page; current guide uses the -1 URL.
    "/state-packs",                # Retained older page; current page is /state-rig-packs.
}


def fetch(url: str, attempts: int = 8, delay: float = 2.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(delay * (attempt + 1))
    raise RuntimeError(f"Unable to fetch {url}: {last_error}")


def sitemap_urls(url: str, fallback: list[str] | None = None) -> list[str]:
    """Read a sitemap, retaining the last good URL list during a temporary outage."""
    try:
        root = ET.fromstring(fetch(url, attempts=4, delay=2.0))
    except Exception as exc:
        if fallback:
            print(
                f"Warning: {url} was unavailable ({exc}); "
                f"using {len(fallback)} URLs from the current index.",
                flush=True,
            )
            return fallback
        raise
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [item.text.strip() for item in root.findall("sm:url/sm:loc", namespace)]


def normalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = re.sub(r"^/online-shop(?=/ols/)", "", parsed.path.rstrip("/"))
    return path.lower() or "/"


def public_shop_url(url: str) -> str:
    """Return the live GoDaddy shop route while preserving its query and fragment."""
    parsed = urllib.parse.urlsplit(url)
    path = parsed.path.rstrip("/")
    if path == "/ols" or path.startswith("/ols/"):
        path = f"/online-shop{path}"
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = value.replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def meta_value(source: str, key: str) -> str:
    patterns = [
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']*)',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, source, re.I)
        if match:
            return clean_text(match.group(1))
    return ""


def page_title(source: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", source, re.I | re.S)
    return clean_text(re.sub(r"<[^>]+>", " ", match.group(1))) if match else ""


def canonical_url(source: str, fallback: str) -> str:
    match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)', source, re.I)
    if not match:
        match = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', source, re.I)
    return html.unescape(match.group(1)) if match else fallback


class VisibleBlockParser(HTMLParser):
    BLOCKS = {"h1", "h2", "h3", "h4", "p", "li"}
    SKIP = {"script", "style", "svg", "nav", "footer", "header", "form", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.active_tag = None
        self.parts: list[str] = []
        self.blocks: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.SKIP:
            self.skip_depth += 1
        if self.skip_depth == 0 and tag in self.BLOCKS and self.active_tag is None:
            self.active_tag = tag
            self.parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_depth == 0 and self.active_tag == tag:
            text = clean_text(" ".join(self.parts))
            if text:
                self.blocks.append((tag, text))
            self.active_tag = None
            self.parts = []
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth == 0 and self.active_tag:
            self.parts.append(data)


def useful_block(text: str, title: str) -> bool:
    low = text.lower().strip(" .")
    if not text or low in BOILERPLATE:
        return False
    if low == title.lower().strip(" ."):
        return False
    if "this site is protected by recaptcha" in low or "this website uses cookies" in low:
        return False
    if low.startswith("copyright ©") or low.startswith("signed in as"):
        return False
    return len(text) >= 18


def sections_from_blocks(title: str, blocks: list[tuple[str, str]]) -> list[dict]:
    sections: list[dict] = []
    current_heading = title
    current_text: list[str] = []
    seen = set()

    def flush() -> None:
        nonlocal current_text
        text = clean_text(" ".join(current_text))
        if len(text) >= 40:
            sections.append({"heading": current_heading, "text": text[:2200]})
        current_text = []

    for tag, text in blocks:
        identity = (tag, text.lower())
        if identity in seen or not useful_block(text, title):
            continue
        seen.add(identity)
        if tag in {"h1", "h2", "h3", "h4"}:
            flush()
            current_heading = text
        else:
            current_text.append(text)
            if sum(map(len, current_text)) > 1800:
                flush()
    flush()
    return sections[:80]


def generic_page(url: str, source: str) -> dict:
    title = page_title(source) or urllib.parse.unquote(url.rstrip("/").split("/")[-1]).replace("-", " ").title()
    description = meta_value(source, "description")
    parser = VisibleBlockParser()
    parser.feed(source)
    sections = sections_from_blocks(title, parser.blocks)
    path = normalize_url(url)
    if path == "/rig-finder":
        kind = "tool"
    elif any(term in path for term in ("about", "contact", "retailer", "global", "wiggle-wins")):
        kind = "information"
    else:
        kind = "guide"
    return {
        "id": f"page:{path}",
        "type": kind,
        "title": title,
        "url": canonical_url(source, url),
        "description": description or (sections[0]["text"][:240] if sections else ""),
        "keywords": [],
        "sections": [] if kind == "information" else sections,
    }


def blog_page(url: str, source: str) -> dict:
    match = re.search(r"window\._BLOG_DATA=(.*?);</script>", source, re.S)
    if not match:
        page = generic_page(url, source)
        page["type"] = "blog"
        page["id"] = "blog:" + normalize_url(url)
        return page
    data = json.loads(match.group(1))
    post = data.get("post", {})
    title = clean_text(post.get("title") or page_title(source))
    description = clean_text(post.get("content") or meta_value(source, "description"))
    try:
        draft = json.loads(post.get("fullContent") or "{}")
        blocks = []
        for block in draft.get("blocks", []):
            text = clean_text(block.get("text", ""))
            block_type = block.get("type", "unstyled")
            if block_type.startswith("header-"):
                level = {"header-one": "h1", "header-two": "h2", "header-three": "h3"}.get(block_type, "h4")
                blocks.append((level, text))
            elif text:
                blocks.append(("p", text))
        sections = sections_from_blocks(title, blocks)
    except (TypeError, ValueError):
        sections = []
    return {
        "id": "blog:" + normalize_url(url),
        "type": "blog",
        "title": title,
        "url": canonical_url(source, url),
        "description": description or (sections[0]["text"][:240] if sections else ""),
        "keywords": list(post.get("categories") or []),
        "sections": sections,
    }


def flatten_values(value) -> list[str]:
    if value is None or value is False:
        return []
    if isinstance(value, list):
        return [clean_text(str(item)) for item in value if clean_text(str(item))]
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(flatten_values(item))
        return result
    text = clean_text(str(value))
    return [text] if text and text.lower() not in {"true", "false"} else []


def slug_title(url: str) -> str:
    slug = urllib.parse.unquote(url.rstrip("/").split("/")[-1])
    text = slug.replace("-", " ")
    text = re.sub(r"\b(\d+)lb\b", lambda m: f"{m.group(1)}lb", text, flags=re.I)
    text = re.sub(r"\b(\d+)x\b", lambda m: f"{m.group(1)}×", text, flags=re.I)
    text = re.sub(
        r"\b(\d{1,2})0\b(?=\s+(?:(?:octopus|circle|beak|recurve|sport|ganged)\s+)?hooks?\b)",
        lambda m: f"{m.group(1)}/0",
        text,
        flags=re.I,
    )
    title = text.title().replace("Lb", "lb")
    return re.sub(r"(?<=\d)M\b", "m", title)


def match_terms(value: str) -> set[str]:
    ignored = {"wiggle", "ya", "worm", "hand", "tied", "fishing", "rig", "rigs", "with", "and", "for", "the"}
    return {term for term in re.findall(r"[a-z0-9]+", value.lower()) if term not in ignored}


def fuzzy_rig_match(url: str, candidates: list[dict]) -> tuple[list[dict], float]:
    slug = urllib.parse.unquote(url.rstrip("/").split("/")[-1]).replace("-", " ").lower()
    slug_terms = match_terms(slug)
    if not slug_terms:
        return [], 0.0
    best: list[dict] = []
    best_score = 0.0
    for rig in candidates:
        candidate = clean_text(f"{rig.get('name', '')} {urllib.parse.unquote((rig.get('url') or '').rstrip('/').split('/')[-1]).replace('-', ' ')}").lower()
        candidate_terms = match_terms(candidate)
        overlap = len(slug_terms & candidate_terms)
        if overlap < 3:
            continue
        coverage = overlap / min(len(slug_terms), len(candidate_terms))
        sequence = difflib.SequenceMatcher(None, slug, candidate).ratio()
        score = (coverage * 0.66) + (sequence * 0.34)
        slug_numbers = {term for term in slug_terms if any(char.isdigit() for char in term)}
        candidate_numbers = {term for term in candidate_terms if any(char.isdigit() for char in term)}
        if slug_numbers and candidate_numbers and not (slug_numbers & candidate_numbers):
            score -= 0.18
        if score > best_score:
            best_score = score
            best = [rig]
    return (best, best_score) if best_score >= 0.69 else ([], best_score)


def build_product_documents(urls: list[str], rig_data: dict) -> tuple[list[dict], dict]:
    by_url: dict[str, list[dict]] = defaultdict(list)
    for rig in rig_data.get("rigs", []):
        if rig.get("url"):
            by_url[normalize_url(rig["url"])].append(rig)

    documents = []
    matched = 0
    fuzzy_matched = 0
    product_count = 0
    category_count = 0
    for url in urls:
        path = normalize_url(url)
        if path in {"/ols/products", "/ols/categories"}:
            continue
        if "/ols/categories/" in path:
            category_count += 1
            documents.append({
                "id": f"collection:{path}",
                "type": "collection",
                "title": slug_title(url),
                "url": public_shop_url(url),
                "description": "Browse this collection of Wiggle ya Worm products.",
                "keywords": urllib.parse.unquote(path).replace("-", " ").split("/"),
                "sections": [],
            })
            continue
        if "/ols/products/" not in path:
            continue
        product_count += 1
        rigs = by_url.get(path, [])
        if rigs:
            matched += 1
            exact_match = True
        else:
            rigs, _ = fuzzy_rig_match(url, rig_data.get("rigs", []))
            fuzzy_matched += bool(rigs)
            exact_match = False
        title = clean_text(rigs[0].get("name", "")) if rigs and exact_match else slug_title(url)
        keyword_fields = (
            "rig_type", "usage", "environment", "species", "bait", "current",
            "cast", "distance", "bait_size", "terrain", "sinker", "leader", "cap",
        )
        keywords = []
        reasons = []
        image = ""
        for rig in rigs:
            for field in keyword_fields:
                keywords.extend(flatten_values(rig.get(field)))
            reasons.extend(flatten_values(rig.get("why") or rig.get("w")))
            image = image or clean_text(rig.get("image", ""))
        keywords.extend(match_terms(urllib.parse.unquote(path).replace("-", " ")))
        keywords = list(dict.fromkeys(item.lower() for item in keywords if item))
        reasons = list(dict.fromkeys(reasons))
        documents.append({
            "id": f"product:{path}",
            "type": "product",
            "title": title,
            "url": public_shop_url(url),
            "description": reasons[0] if reasons else "Hand-tied Wiggle ya Worm fishing rig.",
            "keywords": keywords,
            "sections": [],
            **({"image": image} if image else {}),
        })
    stats = {
        "products": product_count,
        "matchedToRigFinderData": matched,
        "fuzzyMatchedToRigData": fuzzy_matched,
        "collections": category_count,
    }
    return documents, stats


def combined_rig_data(root: Path) -> dict:
    with (root / "rig-dataset.json").open(encoding="utf-8") as handle:
        current = json.load(handle).get("rigs", [])
    legacy = []
    legacy_path = root / "rigs.json"
    if legacy_path.exists():
        with legacy_path.open(encoding="utf-8") as handle:
            for item in json.load(handle):
                legacy.append({
                    "name": item.get("n"),
                    "url": item.get("u"),
                    "image": item.get("i"),
                    "rig_type": item.get("p"),
                    "environment": item.get("l"),
                    "species": item.get("s"),
                    "leader": item.get("ld"),
                    "why": item.get("w"),
                })
    return {"rigs": current + legacy}


def finalize_documents(documents: list[dict]) -> list[dict]:
    selected: dict[str, dict] = {}
    for item in documents:
        path = normalize_url(item.get("url", ""))
        if path in EXCLUDED_PATHS:
            continue
        existing = selected.get(path)
        if not existing or len(item.get("sections", [])) > len(existing.get("sections", [])):
            selected[path] = item
    return sorted(selected.values(), key=lambda item: (item["type"], item["title"].lower()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="ask-wiggle-index.json")
    parser.add_argument("--delay", type=float, default=1.25, help="Delay between page requests")
    parser.add_argument("--limit-pages", type=int, default=0, help="Development-only page limit")
    parser.add_argument("--refresh-products-only", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    rig_data = combined_rig_data(root)

    output = root / args.output
    if args.refresh_products_only and output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        shop_urls = [
            item["url"] for item in existing.get("documents", [])
            if item.get("type") in {"product", "collection"}
        ]
        product_documents, product_stats = build_product_documents(shop_urls, rig_data)
        existing["documents"] = finalize_documents([
            item for item in existing["documents"]
            if item.get("type") not in {"product", "collection"}
        ] + product_documents)
        existing["stats"].update(product_stats)
        existing["stats"]["documents"] = len(existing["documents"])
        existing["stats"]["sections"] = sum(len(item.get("sections", [])) for item in existing["documents"])
        existing["generatedAt"] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(existing, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(json.dumps(existing["stats"], indent=2))
        print(f"Refreshed products in {output}")
        return

    existing_documents = []
    if output.exists():
        existing_documents = json.loads(output.read_text(encoding="utf-8")).get("documents", [])
    site_fallback = [
        item["url"] for item in existing_documents
        if item.get("type") not in {"blog", "product", "collection"} and item.get("url")
    ]
    blog_fallback = [
        item["url"] for item in existing_documents
        if item.get("type") == "blog" and item.get("url")
    ]
    shop_fallback = [
        item["url"] for item in existing_documents
        if item.get("type") in {"product", "collection"} and item.get("url")
    ]

    site_urls = sitemap_urls(SITEMAPS["website"], site_fallback)
    blog_urls = sitemap_urls(SITEMAPS["blog"], blog_fallback)
    shop_urls = sitemap_urls(SITEMAPS["shop"], shop_fallback)
    product_documents, product_stats = build_product_documents(shop_urls, rig_data)

    if args.refresh_products_only:
        existing = json.loads(output.read_text(encoding="utf-8"))
        existing["documents"] = finalize_documents([
            item for item in existing["documents"]
            if item.get("type") not in {"product", "collection"}
        ] + product_documents)
        existing["stats"].update(product_stats)
        existing["stats"]["documents"] = len(existing["documents"])
        existing["stats"]["sections"] = sum(len(item.get("sections", [])) for item in existing["documents"])
        existing["generatedAt"] = datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(existing, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(json.dumps(existing["stats"], indent=2))
        print(f"Refreshed products in {output}")
        return

    crawl_targets = [("website", url) for url in site_urls] + [("blog", url) for url in blog_urls]
    if args.limit_pages:
        crawl_targets = crawl_targets[: args.limit_pages]

    documents = list(product_documents)
    failures = []
    for index, (kind, url) in enumerate(crawl_targets, start=1):
        print(f"[{index}/{len(crawl_targets)}] {kind}: {url}", flush=True)
        try:
            source = fetch(url)
            document = blog_page(url, source) if kind == "blog" or "/wiggles-blog/f/" in url else generic_page(url, source)
            if document["title"] and normalize_url(document["url"]) != "/":
                documents.append(document)
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})
        time.sleep(args.delay)

    if failures:
        print(
            f"Index update cancelled: {len(failures)} page(s) could not be read. "
            "The current live index has been left unchanged.",
            flush=True,
        )
        for failure in failures:
            print(f"- {failure['url']}: {failure['error']}", flush=True)
        raise SystemExit(1)

    documents = finalize_documents(documents)
    result = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "brand": "Ask Wiggle",
        "source": BASE,
        "synonyms": SYNONYMS,
        "stats": {
            "sitemapWebsiteUrls": len(site_urls),
            "sitemapBlogUrls": len(blog_urls),
            "sitemapShopUrls": len(shop_urls),
            "documents": len(documents),
            "sections": sum(len(item.get("sections", [])) for item in documents),
            **product_stats,
            "failures": len(failures),
        },
        "failures": failures,
        "documents": documents,
    }
    if output.exists():
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
            unchanged = (
                existing.get("synonyms") == result.get("synonyms")
                and existing.get("stats") == result.get("stats")
                and existing.get("failures") == result.get("failures")
                and existing.get("documents") == result.get("documents")
            )
            if unchanged:
                print("No searchable content changed; the existing index is current.")
                return
        except (OSError, ValueError):
            pass
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(result["stats"], indent=2))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
