import json
import re
from bs4 import BeautifulSoup
from session import get, make_session, get_with_fallback
from match import is_match, normalize_size

RETAILER = "neiman_marcus"
BASE = "https://www.neimanmarcus.com"
SEARCH_URL = "https://www.neimanmarcus.com/search.jsp"


def extract_from_url(url: str) -> dict | None:
    try:
        resp = get_with_fallback(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        result = {"brand": None, "name": None, "image": None,
                  "price": None, "currency": "USD", "url": url}
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string)
                if isinstance(data, list): data = data[0]
                if data.get("@type") in ("Product", "product"):
                    result["name"]  = data.get("name")
                    result["brand"] = (data.get("brand") or {}).get("name") or data.get("brand")
                    result["image"] = (data.get("image") or [None])[0] if isinstance(data.get("image"), list) else data.get("image")
                    offers = data.get("offers") or {}
                    if isinstance(offers, list): offers = offers[0]
                    result["price"]    = float(offers.get("price", 0)) or None
                    result["currency"] = offers.get("priceCurrency", "USD")
                    break
            except Exception: continue
        if not result["name"]:
            tag = soup.find("meta", property="og:title")
            if tag: result["name"] = tag.get("content", "").strip()
        if not result["image"]:
            tag = soup.find("meta", property="og:image")
            if tag: result["image"] = tag.get("content", "").strip()
        return result if result["name"] else None
    except Exception as e:
        print(f"[NM] extract error: {e}")
        return None


def _parse_price(raw) -> float | None:
    try:
        return float(str(raw).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _scrape_size_and_price(url: str, norm_size: str) -> dict | None:
    try:
        resp = get_with_fallback(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        price = None
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(tag.string)
                if isinstance(d, list): d = d[0]
                offers = d.get("offers", {})
                if isinstance(offers, list): offers = offers[0]
                price = float(offers.get("price", 0)) or None
                break
            except Exception: continue
        if not price:
            tag = soup.find("meta", property="product:price:amount")
            if tag: price = _parse_price(tag.get("content"))
        in_stock = False
        size_els = soup.select(
            "[class*='size'] button, [class*='size'] li, "
            "[data-size], [aria-label*='size'], [class*='sizeButton']"
        )
        for el in size_els:
            label = (el.get("data-size") or el.get("aria-label", "") or el.get_text(strip=True)).upper()
            if norm_size in label or label == norm_size:
                disabled = (
                    el.get("disabled") is not None
                    or "disabled" in (el.get("class") or [])
                    or "sold-out" in " ".join(el.get("class") or []).lower()
                    or "unavailable" in " ".join(el.get("class") or []).lower()
                )
                in_stock = not disabled
                break
        return {"price": price, "in_stock_in_size": in_stock}
    except Exception as e:
        print(f"[NM] size scrape error: {e}")
        return None


def search(brand: str, name: str, size: str, session=None) -> dict | None:
    query = f"{brand} {name}"
    norm_size = normalize_size(size)
    try:
        s = session or make_session()
        resp = s.get(SEARCH_URL, params={"q": query, "from": "brSearch"}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        data = None
        for tag in soup.find_all("script"):
            text = tag.string or ""
            if "searchProductResults" in text or "productList" in text:
                m = re.search(r'"productList"\s*:\s*(\[.*?\])\s*[,}]', text, re.S)
                if m:
                    try: data = json.loads(m.group(1)); break
                    except Exception: pass
        if not data:
            cards = soup.select("[class*='product-thumbnail']")
            data = []
            for card in cards[:10]:
                title_el = card.select_one("[class*='product-name'], [class*='productName']")
                price_el = card.select_one("[class*='price']")
                link_el  = card.select_one("a[href]")
                if title_el and link_el:
                    data.append({
                        "displayName": title_el.get_text(strip=True),
                        "designerName": brand,
                        "price": price_el.get_text(strip=True) if price_el else None,
                        "productUrl": link_el["href"],
                    })
        for item in (data or []):
            result_brand = item.get("designerName", "")
            result_name  = item.get("displayName", item.get("name", ""))
            if not is_match(brand, name, result_brand, result_name): continue
            raw_url = item.get("productUrl", "")
            product_url = raw_url if raw_url.startswith("http") else BASE + raw_url
            detail = _scrape_size_and_price(product_url, norm_size)
            if not detail: continue
            return {
                "retailer": RETAILER, "url": product_url,
                "brand": result_brand or brand, "name": result_name,
                "image": item.get("imageUrl"),
                "price": detail["price"], "in_stock_in_size": detail["in_stock_in_size"],
                "currency": "USD",
            }
        return None
    except Exception as e:
        print(f"[NM] search error: {e}")
        return None


def scrape_price_and_stock(url: str, size: str) -> dict:
    norm_size = normalize_size(size)
    detail = _scrape_size_and_price(url, norm_size)
    if detail: return detail
    return {"price": None, "in_stock_in_size": False}
