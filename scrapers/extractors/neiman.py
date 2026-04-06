import json
import re
from bs4 import BeautifulSoup
from session import get, make_session
from match import is_match, normalize_size

RETAILER = "neiman_marcus"
BASE = "https://www.neimanmarcus.com"
SEARCH_URL = "https://www.neimanmarcus.com/search.jsp"


def _find_product_json(soup):
    """Extract embedded product JSON from NM page scripts."""
    for tag in soup.find_all("script"):
        text = tag.string or ""
        if "productCatalogEntryView" in text or '"brand"' in text:
            # Try JSON-LD first
            if tag.get("type") == "application/ld+json":
                try:
                    return json.loads(text)
                except Exception:
                    pass
            # Try inline JS data blobs
            m = re.search(r'"productCatalogEntryView"\s*:\s*(\[.*?\])', text, re.S)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    pass
    return None


def extract_from_url(url: str) -> dict | None:
    """
    Scrape a Neiman Marcus product page.
    Returns { brand, name, image, price, currency } or None.
    """
    try:
        resp = get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        result = {"brand": None, "name": None, "image": None,
                  "price": None, "currency": "USD", "url": url}

        # --- JSON-LD ---
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") in ("Product", "product"):
                    result["name"]  = data.get("name")
                    result["brand"] = (data.get("brand") or {}).get("name") or data.get("brand")
                    result["image"] = (data.get("image") or [None])[0] if isinstance(data.get("image"), list) else data.get("image")
                    offers = data.get("offers") or {}
                    if isinstance(offers, list):
                        offers = offers[0]
                    result["price"]    = float(offers.get("price", 0)) or None
                    result["currency"] = offers.get("priceCurrency", "USD")
                    break
            except Exception:
                continue

        # --- Fallback: meta tags ---
        if not result["name"]:
            tag = soup.find("meta", property="og:title")
            if tag:
                result["name"] = tag.get("content", "").strip()
        if not result["image"]:
            tag = soup.find("meta", property="og:image")
            if tag:
                result["image"] = tag.get("content", "").strip()
        if not result["price"]:
            tag = soup.find("meta", property="product:price:amount")
            if tag:
                try:
                    result["price"] = float(tag.get("content", "0"))
                except Exception:
                    pass

        # --- Brand fallback from page title / breadcrumb ---
        if not result["brand"]:
            bc = soup.select_one("[class*='breadcrumb']")
            if bc:
                links = bc.find_all("a")
                if len(links) >= 2:
                    result["brand"] = links[-2].get_text(strip=True)

        return result if result["name"] else None

    except Exception as e:
        print(f"[NM] extract error: {e}")
        return None


def _parse_price(raw) -> float | None:
    try:
        s = str(raw).replace("$", "").replace(",", "").strip()
        return float(s)
    except Exception:
        return None


def search(brand: str, name: str, size: str, session=None) -> dict | None:
    """
    Search NM for brand+name, return best matching product dict or None.
    { url, price, in_stock_in_size, brand, name, image }
    """
    query = f"{brand} {name}"
    try:
        s = session or make_session()
        # NM search returns HTML with embedded JSON
        resp = s.get(SEARCH_URL, params={"q": query, "from": "brSearch"}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Results are in a JSON blob in a script tag
        data = None
        for tag in soup.find_all("script"):
            text = tag.string or ""
            if "searchProductResults" in text or "productList" in text:
                m = re.search(r'"productList"\s*:\s*(\[.*?\])\s*[,}]', text, re.S)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        break
                    except Exception:
                        pass

        # Fallback: parse product cards from HTML
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

        norm_size = normalize_size(size)

        for item in (data or []):
            result_brand = item.get("designerName", "")
            result_name  = item.get("displayName", item.get("name", ""))
            if not is_match(brand, name, result_brand, result_name):
                continue

            # Build full URL
            raw_url = item.get("productUrl", "")
            product_url = raw_url if raw_url.startswith("http") else BASE + raw_url

            # Scrape the product page to check size + exact price
            detail = _scrape_size_and_price(product_url, norm_size)
            if detail is None:
                continue

            return {
                "retailer":         RETAILER,
                "url":              product_url,
                "brand":            result_brand or brand,
                "name":             result_name,
                "image":            item.get("imageUrl"),
                "price":            detail["price"],
                "in_stock_in_size": detail["in_stock_in_size"],
                "currency":         "USD",
            }

        return None

    except Exception as e:
        print(f"[NM] search error: {e}")
        return None


def _scrape_size_and_price(url: str, norm_size: str) -> dict | None:
    """Visit product page, return { price, in_stock_in_size }."""
    try:
        resp = get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Price from JSON-LD
        price = None
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(tag.string)
                if isinstance(d, list):
                    d = d[0]
                offers = d.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0]
                price = float(offers.get("price", 0)) or None
                break
            except Exception:
                continue

        # Fallback price from meta
        if not price:
            tag = soup.find("meta", property="product:price:amount")
            if tag:
                price = _parse_price(tag.get("content"))

        # Size availability: look for size buttons/swatches
        in_stock = False
        size_els = soup.select(
            "[class*='size'] button, [class*='size'] li, "
            "[data-size], [aria-label*='size'], [class*='sizeButton']"
        )
        for el in size_els:
            label = (
                el.get("data-size")
                or el.get("aria-label", "")
                or el.get_text(strip=True)
            ).upper()
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


def scrape_price_and_stock(url: str, size: str) -> dict:
    """Daily scraper entry point — just grab price + size stock for a known URL."""
    norm_size = normalize_size(size)
    detail = _scrape_size_and_price(url, norm_size)
    if detail:
        return detail
    return {"price": None, "in_stock_in_size": False}
