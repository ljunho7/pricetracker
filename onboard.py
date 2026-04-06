"""
onboard.py — Add a new item to products.json

Usage:
    python onboard.py --url "https://www.neimanmarcus.com/p/..." --size "S"
    python onboard.py --url "..." --size "M" --alert 300 --email "user@email.com"
"""

import argparse
import json
import sys
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add scrapers dir to path
sys.path.insert(0, str(Path(__file__).parent))

import extractors.neiman   as neiman
import extractors.saks     as saks
import extractors.farfetch as farfetch
import extractors.nap      as nap

DATA_FILE = Path(__file__).parent.parent / "data" / "products.json"

RETAILER_MODULES = {
    "neiman_marcus": neiman,
    "saks":          saks,
    "farfetch":      farfetch,
    "net_a_porter":  nap,
}

RETAILER_LABELS = {
    "neiman_marcus": "Neiman Marcus",
    "saks":          "Saks Fifth Avenue",
    "farfetch":      "Farfetch",
    "net_a_porter":  "Net-a-Porter",
}

def detect_source_retailer(url: str) -> str | None:
    url = url.lower()
    if "neimanmarcus.com" in url:
        return "neiman_marcus"
    if "saksfifthavenue.com" in url or "saks.com" in url:
        return "saks"
    if "farfetch.com" in url:
        return "farfetch"
    if "net-a-porter.com" in url:
        return "net_a_porter"
    return None


def extract_source_product(url: str, retailer: str) -> dict | None:
    mod = RETAILER_MODULES.get(retailer)
    if not mod:
        print(f"[onboard] Unknown source retailer: {retailer}")
        return None
    print(f"[onboard] Extracting product from {RETAILER_LABELS[retailer]}...")
    return mod.extract_from_url(url)


def search_retailer(retailer_key: str, brand: str, name: str,
                    size: str, source_url: str) -> tuple[str, dict | None]:
    mod = RETAILER_MODULES[retailer_key]
    label = RETAILER_LABELS[retailer_key]
    print(f"[onboard] Searching {label}...")
    try:
        result = mod.search(brand, name, size)
        if result:
            print(f"[onboard]   ✓ Found on {label}: ${result.get('price')} | size {size} {'✓' if result.get('in_stock_in_size') else '✗'}")
        else:
            print(f"[onboard]   ✗ Not found on {label}")
        return retailer_key, result
    except Exception as e:
        print(f"[onboard]   ! Error on {label}: {e}")
        return retailer_key, None


def load_products() -> list:
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return []


def save_products(products: list):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print(f"[onboard] Saved {len(products)} product(s) to {DATA_FILE}")


def onboard(url: str, size: str, alert_below: float | None = None,
            added_by: str | None = None) -> dict | None:

    # 1. Detect which retailer the URL is from
    source_retailer = detect_source_retailer(url)
    if not source_retailer:
        print(f"[onboard] Unrecognized retailer URL: {url}")
        print("[onboard] Supported: neimanmarcus.com, saksfifthavenue.com, farfetch.com, net-a-porter.com")
        return None

    # 2. Extract product info from source page
    source = extract_source_product(url, source_retailer)
    if not source:
        print("[onboard] Failed to extract product info from source URL.")
        return None

    brand = source.get("brand") or ""
    name  = source.get("name") or ""
    image = source.get("image")

    print(f"\n[onboard] Product identified:")
    print(f"  Brand : {brand}")
    print(f"  Name  : {name}")
    print(f"  Price : ${source.get('price')}")
    print(f"  Size  : {size}\n")

    # 3. Search all 4 retailers in parallel
    retailers_data = {}
    search_keys = list(RETAILER_MODULES.keys())

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                search_retailer, key, brand, name, size, url
            ): key
            for key in search_keys
        }
        for future in as_completed(futures):
            key, result = future.result()
            retailers_data[key] = result

    # 4. If source retailer search failed, fall back to the source URL directly
    if not retailers_data.get(source_retailer) and source.get("price"):
        print(f"[onboard] Using source URL as fallback for {RETAILER_LABELS[source_retailer]}")
        retailers_data[source_retailer] = {
            "retailer":         source_retailer,
            "url":              url,
            "brand":            brand,
            "name":             name,
            "image":            image,
            "price":            source.get("price"),
            "in_stock_in_size": False,  # Will be updated on next daily run
            "currency":         "USD",
        }

    # 5. Build product record
    product_id = str(uuid.uuid4())[:8]
    retailers = {}
    for key in RETAILER_MODULES:
        result = retailers_data.get(key)
        retailers[key] = {
            "url":   result["url"] if result else None,
            "found": result is not None,
        }

    product = {
        "id":           product_id,
        "brand":        brand,
        "name":         name,
        "size":         size.upper(),
        "added_by":     added_by or "unknown",
        "added_at":     datetime.now(timezone.utc).isoformat(),
        "alert_below":  alert_below,
        "source_url":   url,
        "image":        image,
        "retailers":    retailers,
    }

    # 6. Build today's snapshot entry
    snapshot_entry = {
        "id":         product_id,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "size":       size.upper(),
        "prices": {
            key: {
                "price":            (retailers_data[key] or {}).get("price"),
                "in_stock_in_size": (retailers_data[key] or {}).get("in_stock_in_size", False),
            }
            for key in RETAILER_MODULES
        }
    }

    # 7. Save to products.json
    products = load_products()
    products.append(product)
    save_products(products)

    # 8. Save initial snapshot
    from daily_scrape import write_snapshot_entry
    write_snapshot_entry(snapshot_entry)

    print(f"\n[onboard] Done! Product ID: {product_id}")
    found_count = sum(1 for r in retailers.values() if r["found"])
    print(f"[onboard] Found on {found_count}/4 retailers\n")

    return product


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add a product to the price tracker")
    parser.add_argument("--url",      required=True,  help="Product URL from any supported retailer")
    parser.add_argument("--size",     required=True,  help="Size to track (e.g. S, M, L, XS)")
    parser.add_argument("--alert",    type=float,     help="Alert if price drops below this amount")
    parser.add_argument("--email",    default=None,   help="Who is adding this item")
    args = parser.parse_args()

    result = onboard(
        url=args.url,
        size=args.size,
        alert_below=args.alert,
        added_by=args.email,
    )
    if not result:
        sys.exit(1)
