#!/usr/bin/env python3
"""Index record metadata from official J&K GAD listings; never invent PDF URLs."""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "live-archive.json"
BASE = "https://jkgad.nic.in/En/OrderCirculer.aspx"
FEEDS = [
    ("orders", "O", "Orders", "J&K General Administration Department"),
    ("orders", "C", "Circulars", "J&K General Administration Department"),
    ("orders", "N", "Notifications", "J&K General Administration Department"),
    ("rules", "S", "SRO / SO / Rules", "J&K General Administration Department"),
]
HEADERS = {"User-Agent": "GovPay360 official-index/1.1 (public government-record index)"}
DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
]


def norm_date(text):
    """Parse a date from the listing's order-number/date cell, not title text first."""
    for pat in DATE_PATTERNS:
        m = pat.search(text or "")
        if not m:
            continue
        try:
            if len(m.groups()) == 3 and len(m.group(1)) != 4:
                day, month, year = map(int, m.groups())
            else:
                year, month, day = map(int, m.groups())
            return datetime(year, month, day).date().isoformat()
        except ValueError:
            continue
    return ""


def valid_http_url(href, page_url):
    """Resolve a real HTTP(S) link; reject JS postbacks, fragments and other pseudo-links."""
    href = (href or "").strip()
    if not href or href.lower().startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
        return ""
    resolved = urljoin(page_url, href)
    parsed = urlparse(resolved)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return resolved


def stable_id(section, title, source_url):
    raw = f"{section}|{title}|{source_url}".encode("utf-8", "ignore")
    return hashlib.sha256(raw).hexdigest()[:20]


def _row_cells(row):
    # GAD's listing is a table. Only inspect actual rows to avoid indexing navigation links.
    return row.find_all(["td", "th"], recursive=False)


def parse_listing(html, section, type_name, source_name, page_url):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    seen_ids = set()

    for row in soup.find_all("tr"):
        cells = _row_cells(row)
        if len(cells) < 2 or any(c.name == "th" for c in cells):
            continue

        # Listing columns are subject, order number/date, department. Ignore pager/menu rows.
        title_cell = cells[0]
        title_anchor = None
        for a in title_cell.find_all("a", href=True):
            candidate = " ".join(a.get_text(" ", strip=True).split())
            if len(candidate) >= 4 and not candidate.lower() in {"previous", "next", "view", "download", "h", "u"}:
                title_anchor = a
                break
        title = " ".join((title_anchor.get_text(" ", strip=True) if title_anchor else title_cell.get_text(" ", strip=True)).split())
        meta_text = " ".join(cells[1].get_text(" ", strip=True).split())
        dept_text = " ".join(cells[2].get_text(" ", strip=True).split()) if len(cells) >= 3 else source_name
        row_text = " ".join(row.get_text(" ", strip=True).split())

        if len(title) < 4 or title.lower() in {"order subject", "order no & date", "department", "previous", "next"}:
            continue
        # Reject pager rows and records without a date/reference cell.
        if not meta_text or not re.search(r"\b(?:dt|dated)\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b", meta_text, re.I):
            continue

        source_url = valid_http_url(title_anchor.get("href") if title_anchor else "", page_url)
        # Never publish a fabricated URL for an ASP.NET postback or a navigation link.
        if source_url and urlparse(source_url).path.lower().endswith("ordercirculer.aspx"):
            if urlparse(source_url).query == urlparse(page_url).query:
                source_url = ""
        pdf_url = ""
        for a in row.find_all("a", href=True):
            u = valid_http_url(a.get("href"), page_url)
            if u and urlparse(u).path.lower().endswith(".pdf"):
                pdf_url = u
                break

        issued = norm_date(meta_text) or norm_date(row_text)
        ref_text = re.split(r"\b(?:dt|dated)\b", meta_text, maxsplit=1, flags=re.I)[0].strip(" \t:-–")
        ref_text = re.sub(r"\s+", " ", ref_text)
        # If the date cell contains only a date, don't label that date as an order reference.
        if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", ref_text):
            ref_text = ""

        item = {
            "id": stable_id(section, title, source_url or f"{page_url}|{meta_text}"),
            "section": section,
            "type": type_name,
            "title": title,
            "reference": ref_text,
            "issued": issued,
            "department": dept_text or source_name,
            "source_name": source_name,
            "source_url": source_url or page_url,
            "pdf_url": pdf_url,
        }
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            found.append(item)
    return found


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    previous = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            previous = {x.get("id"): x for x in old.get("items", []) if x.get("id")}
        except Exception:
            previous = {}

    session = requests.Session()
    session.headers.update(HEADERS)
    warnings, observed, source_rows = [], 0, []
    successful = 0
    for section, code, label, source_name in FEEDS:
        url = f"{BASE}?ordType={code}"
        try:
            response = session.get(url, timeout=35)
            response.raise_for_status()
            if not response.text or len(response.text) < 500:
                raise RuntimeError("listing response was unexpectedly short")
            records = parse_listing(response.text, section, label, source_name, url)
            if not records:
                raise RuntimeError("no document table rows parsed; site markup may have changed")
            successful += 1
            observed += len(records)
            source_rows.append({"name": label, "url": url, "checked_at": datetime.now(timezone.utc).isoformat(), "records_parsed": len(records)})
            for item in records:
                previous[item["id"]] = item
            print(f"{label}: indexed {len(records)} records")
        except Exception as exc:
            msg = f"{label}: {type(exc).__name__}: {exc}"
            warnings.append(msg)
            print(msg, file=sys.stderr)

    if successful == 0:
        print("No official listing could be parsed; existing feed was not overwritten.", file=sys.stderr)
        return 1

    all_items = sorted(previous.values(), key=lambda x: (x.get("issued") or "", x.get("title") or ""), reverse=True)
    payload = {
        "status": "ok" if not warnings else "partial",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": all_items,
        "sources": source_rows,
        "sync_warnings": warnings,
        "run_observed_count": observed,
        "note": "Cumulative index of records observed on the official listing pages checked by this workflow; not a complete historical archive.",
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUT)
    print(f"Saved {len(all_items)} cumulative records to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
