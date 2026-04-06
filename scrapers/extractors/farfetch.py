import json
import re
from bs4 import BeautifulSoup
from session import get, make_session
from match import is_match, normalize_size

RETAILER = "farfetch"
BASE = "https://www.farfetch.com"
# Farfetch has an internal API endpoint used by their search page
SEARCH_URL = "https://www.farfetch.com/us/plpslice/listing-api/products-facets"


def extract_from_url(url: str) -> dict | None:
    try:
        resp = get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        result = {"brand": None, "name": None, "image": None,
                  "price": None, "currency": "USD", "url": url}

        # Farfetch puts full product state in __NEXT_DATA__
        tag = soup.find("script", id="__NEXT_DATA__")
        if tag:
            try:
                nd = json.loads(tag.string)
                product = (
                    nd.get("props", {})
                    .get("pageProps", {})
                    .get("initialData", {})
                    .get("productDetails", {})
                )
                if product:
                    result["name"]  = product.get("name")
                    result["brand"] = (product.get("brand") or {}).get("name")
                    result["price"] = (
                        product.get("priceInfo", {})
                        .get("finalPrice", {})
                        .get("value")
                    )
                    imgs = product.get("images", [])
                    result["image"] = imgs[0].get("src") if imgs else None
            except Exception:
                pass

        # JSON-LD fallback
        if not result["name"]:
            for ld_tag in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(ld_tag.string)
                    if isinstance(data, list):
                        data = data[0]
                    if data.get("@type") == "Product":
                        result["name"]  = data.get("name")
                        brand = data.get("brand", {})
                        result["brand"] = brand.get("name") if isinstance(brand, dict) else brand
                        offers = data.get("offers", {})
                        if isinstance(offers, list):
                            offers = offers[0]
                        result["price"] = float(offers.get("price", 0)) or None
                        imgs = data.get("image", [])
                        result["image"] = imgs[0] if isinstance(imgs, list) and imgs else imgs
                        break
                except Exception:
                    continue

        return result if result["name"] else None
    except Exception as e:
        print(f"[Farfetch] extract error: {e}")
        return None


def _scrape_size_and_price(url: str, norm_size: str) -> dict | None:
    try:
        resp = get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        price = None
        in_stock = False

        tag = soup.find("script", id="__NEXT_DATA__")
        if tag:
            try:
                nd = json.loads(tag.string)
                product = (
                    nd.get("props", {})
                    .get("pageProps", {})
                    .get("initialData", {})
                    .get("productDetails", {})
                )
                if product:
                    price = (
                        product.get("priceInfo", {})
                        .get("finalPrice", {})
                        .get("value")
                    )
                    # Sizes live in variants/sizes array
                    sizes = (
                        product.get("sizes")
                        or product.get("variants")
                        or product.get("sizeOptions")
                        or []
                    )
                    for s in sizes:
                        label = (
                            s.get("name", "")
                            or s.get("size", "")
                            or s.get("label", "")
                        ).upper()
                        if norm_size in label or label == norm_size:
                            in_stock = s.get("isAvailable", s.get("available", False))
                            break
            except Exception:
                pass

        if not price:
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

        return {"price": price, "in_stock_in_size": in_stock}
    except Exception as e:
        print(f"[Farfetch] size scrape error: {e}")
        return None


def search(brand: str, name: str, size: str, session=None) -> dict | None:
    query = f"{brand} {name}"
    norm_size = normalize_size(size)
    try:
        s = session or make_session()
        # Try Farfetch listing API (used by their own frontend)
        params = {
            "q": query,
            "view": "24",
            "scale": "282",   # US sizing scale
            "sort": "3",      # relevance
        }
        s.headers.update({
            "Accept": "application/json",
            "Referer": "https://www.farfetch.com/",
        })
        resp = s.get(SEARCH_URL, params=params, timeout=15)

        products = []
        try:
            data = resp.json()
            items = (
                data.get("listingItems", {}).get("items")
                or data.get("products")
                or data.get("items")
                or []
            )
            for item in items:
                products.append({
                    "brand": (item.get("brand") or {}).get("name", ""),
                    "name":  item.get("shortDescription", item.get("name", "")),
                    "url":   BASE + item.get("url", ""),
                    "image": (item.get("images") or [{}])[0].get("src"),
                    "price": (
                        item.get("priceInfo", {})
                        .get("finalPrice", {})
                        .get("value")
                    ),
                })
        except Exception:
            # HTML fallback — search via regular search page
            s.headers.update({"Accept": "text/html,*/*"})
            resp2 = s.get(
                "https://www.farfetch.com/us/shopping/women/search/items.aspx",
                params={"q": query},
                timeout=15
            )
            soup = BeautifulSoup(resp2.text, "html.parser")
            nd_tag = soup.find("script", id="__NEXT_DATA__")
            if nd_tag:
                nd = json.loads(nd_tag.string)
                items = (
                    nd.get("props", {})
                    .get("pageProps", {})
                    .get("initialData", {})
                    .get("listingItems", {})
                    .get("items", [])
                )
                for item in items:
                    products.append({
                        "brand": (item.get("brand") or {}).get("name", ""),
                        "name":  item.get("shortDescription", ""),
                        "url":   BASE + item.get("url", ""),
                        "image": (item.get("images") or [{}])[0].get("src"),
                        "price": None,
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
                "price":            detail["price"] or item.get("price"),
                "in_stock_in_size": detail["in_stock_in_size"],
                "currency":         "USD",
            }

        return None
    except Exception as e:
        print(f"[Farfetch] search error: {e}")
        return None


def scrape_price_and_stock(url: str, size: str) -> dict:
    norm_size = normalize_size(size)
    detail = _scrape_size_and_price(url, norm_size)
    if detail:
        return detail
    return {"price": None, "in_stock_in_size": False}
