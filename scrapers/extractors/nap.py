import json
import re
from bs4 import BeautifulSoup
from session import get, make_session
from match import is_match, normalize_size

RETAILER = "net_a_porter"
BASE = "https://www.net-a-porter.com"
SEARCH_URL = "https://www.net-a-porter.com/en-us/shop/search"


def extract_from_url(url: str) -> dict | None:
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
                if data.get("@type") == "Product":
                    result["name"]  = data.get("name")
                    brand = data.get("brand", {})
                    result["brand"] = brand.get("name") if isinstance(brand, dict) else brand
                    offers = data.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0]
                    result["price"]    = float(offers.get("price", 0)) or None
                    result["currency"] = offers.get("priceCurrency", "USD")
                    imgs = data.get("image", [])
                    result["image"] = imgs[0] if isinstance(imgs, list) and imgs else imgs
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
        print(f"[NAP] extract error: {e}")
        return None


def _scrape_size_and_price(url: str, norm_size: str) -> dict | None:
    try:
        resp = get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        price = None
        in_stock = False

        # NAP embeds product state in a window.__INITIAL_STATE__ or similar
        for tag in soup.find_all("script"):
            text = tag.string or ""
            if "sizeList" in text or "stockStatus" in text:
                # Try to extract JSON blob
                m = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>', text, re.S)
                if not m:
                    m = re.search(r'"sizeList"\s*:\s*(\[.*?\])', text, re.S)
                if m:
                    try:
                        blob = json.loads(m.group(1))
                        if isinstance(blob, list):
                            for s in blob:
                                label = (s.get("name", "") or s.get("label", "")).upper()
                                if norm_size in label or label == norm_size:
                                    in_stock = s.get("isAvailable", s.get("available", False))
                                    break
                    except Exception:
                        pass

        # JSON-LD price
        for ld_tag in soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(ld_tag.string)
                if isinstance(d, list):
                    d = d[0]
                offers = d.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0]
                price = float(offers.get("price", 0)) or None
                break
            except Exception:
                continue

        # Size buttons HTML fallback
        if not in_stock:
            size_els = soup.select(
                "[class*='size'], [data-size], "
                "button[data-label], [class*='Size']"
            )
            for el in size_els:
                label = (
                    el.get("data-size")
                    or el.get("data-label", "")
                    or el.get_text(strip=True)
                ).upper()
                if norm_size in label or label == norm_size:
                    classes = " ".join(el.get("class") or []).lower()
                    in_stock = not (
                        el.get("disabled") is not None
                        or "disabled" in classes
                        or "sold-out" in classes
                        or "out-of-stock" in classes
                    )
                    break

        return {"price": price, "in_stock_in_size": in_stock}
    except Exception as e:
        print(f"[NAP] size scrape error: {e}")
        return None


def search(brand: str, name: str, size: str, session=None) -> dict | None:
    query = f"{brand} {name}"
    norm_size = normalize_size(size)
    try:
        s = session or make_session()
        resp = s.get(SEARCH_URL, params={"q": query}, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        products = []

        # NAP search results in __NEXT_DATA__ or window state
        nd_tag = soup.find("script", id="__NEXT_DATA__")
        if nd_tag:
            try:
                nd = json.loads(nd_tag.string)
                items = (
                    nd.get("props", {})
                    .get("pageProps", {})
                    .get("products", [])
                ) or []
                for item in items:
                    products.append({
                        "brand": (item.get("designer") or {}).get("name", ""),
                        "name":  item.get("name", ""),
                        "url":   BASE + item.get("href", ""),
                        "image": (item.get("images") or [{}])[0].get("src"),
                    })
            except Exception:
                pass

        # HTML fallback
        if not products:
            cards = soup.select("[class*='product']")
            for card in cards[:10]:
                name_el  = card.select_one("[class*='name'], [class*='title']")
                brand_el = card.select_one("[class*='brand'], [class*='designer']")
                link_el  = card.select_one("a[href]")
                if name_el and link_el:
                    href = link_el["href"]
                    products.append({
                        "brand": brand_el.get_text(strip=True) if brand_el else brand,
                        "name":  name_el.get_text(strip=True),
                        "url":   href if href.startswith("http") else BASE + href,
                        "image": None,
                    })

        for item in products:
            if not is_match(brand, name, item["brand"], item["name"]):
                continue

            detail = _scrape_size_and_price(item["url"], norm_size)
            if not detail:
                continue

            return {
                "retailer":         RETAILER,
                "url":              item["url"],
                "brand":            item["brand"] or brand,
                "name":             item["name"],
                "image":            item.get("image"),
                "price":            detail["price"],
                "in_stock_in_size": detail["in_stock_in_size"],
                "currency":         "USD",
            }

        return None
    except Exception as e:
        print(f"[NAP] search error: {e}")
        return None


def scrape_price_and_stock(url: str, size: str) -> dict:
    norm_size = normalize_size(size)
    detail = _scrape_size_and_price(url, norm_size)
    if detail:
        return detail
    return {"price": None, "in_stock_in_size": False}
