import json
import re
from bs4 import BeautifulSoup
from session import get, make_session
from match import is_match, normalize_size

RETAILER = "saks"
BASE = "https://www.saksfifthavenue.com"
SEARCH_URL = "https://www.saksfifthavenue.com/search"


def extract_from_url(url: str) -> dict | None:
    """Scrape a Saks product page."""
    try:
        resp = get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        result = {"brand": None, "name": None, "image": None,
                  "price": None, "currency": "USD", "url": url}

        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string)
                if isinstance(data, list):
                    data = data[0]
                if data.get("@type") in ("Product",):
                    result["name"]  = data.get("name")
                    brand = data.get("brand", {})
                    result["brand"] = brand.get("name") if isinstance(brand, dict) else brand
                    imgs = data.get("image", [])
                    result["image"] = imgs[0] if isinstance(imgs, list) and imgs else imgs
                    offers = data.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0]
                    result["price"]    = float(offers.get("price", 0)) or None
                    result["currency"] = offers.get("priceCurrency", "USD")
                    break
            except Exception:
                continue

        if not result["name"]:
            tag = soup.find("meta", property="og:title")
            if tag:
                result["name"] = tag.get("content", "").strip()
        if not result["image"]:
            tag = soup.find("meta", property="og:image")
            if tag:
                result["image"] = tag.get("content", "").strip()

        return result if result["name"] else None
    except Exception as e:
        print(f"[Saks] extract error: {e}")
        return None


def _scrape_size_and_price(url: str, norm_size: str) -> dict | None:
    try:
        resp = get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

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

        if not price:
            tag = soup.find("meta", property="product:price:amount")
            if tag:
                try:
                    price = float(tag.get("content", "0").replace(",", ""))
                except Exception:
                    pass

        # Saks size buttons
        in_stock = False
        size_els = soup.select(
            "[class*='size-option'], [class*='sizeButton'], "
            "[data-size], button[aria-label]"
        )
        for el in size_els:
            label = (
                el.get("data-size")
                or el.get("aria-label", "")
                or el.get_text(strip=True)
            ).upper()
            if norm_size in label or label == norm_size:
                classes = " ".join(el.get("class") or []).lower()
                disabled = (
                    el.get("disabled") is not None
                    or "disabled" in classes
                    or "sold-out" in classes
                    or "out-of-stock" in classes
                )
                in_stock = not disabled
                break

        return {"price": price, "in_stock_in_size": in_stock}
    except Exception as e:
        print(f"[Saks] size scrape error: {e}")
        return None


def search(brand: str, name: str, size: str, session=None) -> dict | None:
    query = f"{brand} {name}"
    norm_size = normalize_size(size)
    try:
        s = session or make_session()
        resp = s.get(SEARCH_URL, params={"q": query}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Saks embeds product data in a __NEXT_DATA__ JSON blob
        next_data_tag = soup.find("script", id="__NEXT_DATA__")
        products = []
        if next_data_tag:
            try:
                nd = json.loads(next_data_tag.string)
                # Navigate to product list — path varies by page version
                props = nd.get("props", {}).get("pageProps", {})
                search_data = (
                    props.get("searchData")
                    or props.get("initialData", {}).get("searchData")
                    or {}
                )
                products = (
                    search_data.get("products")
                    or search_data.get("items")
                    or []
                )
            except Exception:
                pass

        # HTML fallback
        if not products:
            cards = soup.select("[class*='product-card'], [class*='productCard']")
            for card in cards[:10]:
                name_el  = card.select_one("[class*='product-name'], [class*='title']")
                brand_el = card.select_one("[class*='brand'], [class*='designer']")
                link_el  = card.select_one("a[href]")
                price_el = card.select_one("[class*='price']")
                if name_el and link_el:
                    products.append({
                        "name":       name_el.get_text(strip=True),
                        "brand":      brand_el.get_text(strip=True) if brand_el else brand,
                        "url":        link_el["href"],
                        "price":      price_el.get_text(strip=True) if price_el else None,
                        "image":      None,
                    })

        for item in products:
            result_brand = item.get("brand", item.get("designerName", ""))
            result_name  = item.get("name", item.get("displayName", ""))
            if not is_match(brand, name, result_brand, result_name):
                continue

            raw_url = item.get("url", item.get("productUrl", ""))
            product_url = raw_url if raw_url.startswith("http") else BASE + raw_url

            detail = _scrape_size_and_price(product_url, norm_size)
            if not detail:
                continue

            return {
                "retailer":         RETAILER,
                "url":              product_url,
                "brand":            result_brand or brand,
                "name":             result_name,
                "image":            item.get("image", item.get("imageUrl")),
                "price":            detail["price"],
                "in_stock_in_size": detail["in_stock_in_size"],
                "currency":         "USD",
            }

        return None
    except Exception as e:
        print(f"[Saks] search error: {e}")
        return None


def scrape_price_and_stock(url: str, size: str) -> dict:
    norm_size = normalize_size(size)
    detail = _scrape_size_and_price(url, norm_size)
    if detail:
        return detail
    return {"price": None, "in_stock_in_size": False}
