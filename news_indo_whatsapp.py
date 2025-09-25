#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
news_indo_whatsapp.py
Ambil headline Google News, filter media Indonesia, lalu format untuk WhatsApp.
Sekarang link otomatis dirapikan ke sumber asli.
"""

import sys
import html
import time
import textwrap
import urllib.parse
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlparse, urlunparse
import requests
from email.utils import parsedate_to_datetime

# ====== Konfigurasi ======

ALLOWED_DOMAINS = {
    "cnbcindonesia.com",
    "kontan.co.id",
    "idnfinancials.com",
    "investor.id",
    "bisnis.com",
    "kompas.com",
    "finance.detik.com",
    "detik.com",
    "tempo.co",
    "cnnindonesia.com",
    "okezone.com",
    "id.investing.com",
    "market.bisnis.com",
    "kumparan.com",
    "katadata.co.id",
    "emitennews.com",
    "cnbc.com",
    "finance.yahoo.com",
    "reuters.com",
    "infobanknews.com",
    "ajaib.co.id",
    "liputan6.com",
    "fxstreet-id.com"
}

WHATSAPP_MSG_LIMIT = 3500

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MasBonoBot/1.0; +https://example.com)"
}

# ====== Util ======

def strip_tracking_params(url: str) -> str:
    try:
        parsed = urlparse(url)
        q = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        cleaned_q = [(k, v) for (k, v) in q if not (k.startswith("utm_")
                                                    or k in {"gclid", "fbclid", "yclid", "mc_cid", "mc_eid"})]
        new_query = urllib.parse.urlencode(cleaned_q)
        cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        return cleaned
    except Exception:
        return url

def clean_google_news_link(link: str) -> str:
    """
    Ambil URL asli dari link Google News (kalau ada).
    Kalau tidak ketemu, kembalikan link original.
    """
    try:
        # Cari parameter 'url='
        m = re.search(r"url=(https?%3A%2F%2F[^&]+)", link)
        if m:
            real_url = urllib.parse.unquote(m.group(1))
            return strip_tracking_params(real_url)
        return link
    except Exception:
        return link

def get_domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        for prefix in ("www.", "m.", "amp."):
            if netloc.startswith(prefix):
                netloc = netloc[len(prefix):]
        return netloc
    except Exception:
        return ""

def parse_pubdate_to_wib(pubdate: str) -> datetime:
    try:
        dt = parsedate_to_datetime(pubdate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("Asia/Jakarta"))
    except Exception:
        return datetime.now(ZoneInfo("Asia/Jakarta"))

def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: max(0, n - 1)] + "…"

# ====== Core ======

def google_news_rss(query: str, lang_region: str = "ID:id", limit: int = 10, retries: int = 2, timeout: int = 15):
    base = "https://news.google.com/rss/search"
    q = quote(query)
    url = f"{base}?q={q}&hl=id&gl=ID&ceid={lang_region}"

    last_exc = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            items = []
            for item in root.findall(".//item"):
                title = html.unescape(item.findtext("title") or "")
                link = item.findtext("link") or ""
                pubdate = item.findtext("pubDate") or ""
                source_el = item.find("{*}source")
                source = source_el.text.strip() if source_el is not None and source_el.text else ""
                items.append(
                    {
                        "title": title.strip(),
                        "link": link.strip(),
                        "source": source,
                        "pubDate": pubdate.strip(),
                    }
                )
            return items[:limit * 3]
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
            else:
                raise RuntimeError(f"Gagal mengambil RSS Google News: {e}") from e
    raise last_exc

def filter_by_allowed_domains(items, allowed_domains=ALLOWED_DOMAINS, limit=10):
    seen = set()
    out = []
    for it in items:
        # rapikan link
        raw_link = it["link"]
        link = clean_google_news_link(strip_tracking_params(raw_link))
        dom = get_domain(link)
        source_name = (it.get("source") or "").lower()

        allowed = dom in allowed_domains or any(dom.endswith(d) for d in allowed_domains)
        if not allowed:
            for d in allowed_domains:
                if d.replace(".com", "").replace(".co.id", "") in source_name:
                    allowed = True
                    break

        if not allowed:
            continue

        key = (it["title"].strip().lower(), source_name)
        if key in seen:
            continue
        seen.add(key)

        it2 = dict(it)
        it2["link"] = link
        it2["domain"] = dom
        out.append(it2)
        if len(out) >= limit:
            break
    return out

def format_item_whatsapp(it) -> str:
    dt_wib = parse_pubdate_to_wib(it.get("pubDate", ""))
    tgl = dt_wib.strftime("%d %b %Y, %H:%M WIB")
    source = it.get("source") or it.get("domain") or "Sumber"
    title = truncate(it.get("title", "").strip(), 200)
    link = it.get("link", "").strip()
    title_wrapped = textwrap.shorten(title, width=200, placeholder="…")
    return f"• [{source}] {title_wrapped} ({tgl})\n  {link}"

def format_whatsapp_list(query: str, items) -> str:
    header = f"📰 *Berita Terkini:* {query}\n"
    body = "\n".join(format_item_whatsapp(it) for it in items)
    return f"{header}{body}"

def split_to_wa_chunks(text: str, limit: int = WHATSAPP_MSG_LIMIT):
    if len(text) <= limit:
        return [text]
    parts = []
    lines = text.splitlines(keepends=False)
    cur = ""
    for ln in lines:
        if len(cur) + len(ln) + 1 > limit:
            parts.append(cur.rstrip())
            cur = ""
        cur += ln + "\n"
    if cur.strip():
        parts.append(cur.rstrip())
    return parts

def fetch_news_indo(query: str, limit: int = 8):
    raw = google_news_rss(query=query, limit=limit)
    filtered = filter_by_allowed_domains(raw, limit=limit)
    return filtered

def handle_news_command(text: str, default_limit: int = 8):
    parts = text.strip().split()
    if len(parts) == 0 or parts[0].upper() != "NEWS":
        return ["Format perintah salah. Contoh: NEWS BBCA 7"]

    limit = default_limit
    if len(parts) >= 3 and parts[-1].isdigit():
        limit = max(1, min(20, int(parts[-1])))
        query_tokens = parts[1:-1]
    else:
        query_tokens = parts[1:]

    if not query_tokens:
        return ["Mohon sertakan kata kunci. Contoh: NEWS BBCA 7"]

    query = " ".join(query_tokens).strip()
    if query.upper() == "BBCA":
        query = 'BBCA OR "Bank Central Asia"'

    items = fetch_news_indo(query=query, limit=limit)
    if not items:
        return [f"Tidak ditemukan berita untuk: {query} (media Indonesia)"]

    text_out = format_whatsapp_list(query, items)
    return split_to_wa_chunks(text_out)

# ====== CLI ======

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Pemakaian:")
        print('  python news_indo_whatsapp.py "BBCA OR \\"Bank Central Asia\\"" 8')
        print("atau:")
        print("  python news_indo_whatsapp.py NEWS BBCA 8")
        sys.exit(0)

    if sys.argv[1].upper() == "NEWS":
        cmd = " ".join(sys.argv[1:])
        msgs = handle_news_command(cmd)
        for i, m in enumerate(msgs, 1):
            print(f"\n--- Pesan {i} ---\n{m}\n")
        sys.exit(0)

    query_arg = sys.argv[1]
    limit_arg = int(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[2].isdigit() else 8

    items = fetch_news_indo(query=query_arg, limit=limit_arg)
    if not items:
        print(f"Tidak ditemukan berita untuk: {query_arg}")
        sys.exit(0)

    msg = format_whatsapp_list(query_arg, items)
    chunks = split_to_wa_chunks(msg)
    for i, c in enumerate(chunks, 1):
        print(f"\n--- Pesan {i} ---\n{c}\n")
