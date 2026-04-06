"""
daily_scrape.py — Run every morning via GitHub Actions cron.
Reads products.json, onboards pending items, scrapes current prices,
writes snapshot, triggers email alerts.
"""

import json
import os
import sys
from datetime import datetime, timezone, date
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))

import extractors.neiman   as neiman
import extractors.saks     as saks
import extractors.farfetch as farfetch
import extractors.nap      as nap

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

DATA_DIR      = Path(__file__).parent.parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"


def load_products() -> list:
    if not PRODUCTS_FILE.exists():
        return []
    with open(PRODUCTS_FILE) as f:
        return json.load(f)


def save_products(products: list):
    with open(PRODUCTS_FILE, "w") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)


def onboard_pending(product: dict) -> dict:
    """Run onboarding for a pending product — extract info and find all retailers."""
    from onboard import detect_source_retailer, extract_source_product, search_retailer
    from concurrent.futures import ThreadPoolExecutor, as_completed as caf

    url  = product.get("source_url", "")
    size = product.get("size", "")

    print(f"[daily] Onboarding pending item: {url}")

    source_retailer = detect_source_retailer(url)
    if not source_retailer:
        print(f"[daily] Cannot detect retailer for {url}")
        return product

    source = extract_source_product(url, source_retailer)
    if not source:
        print(f"[daily] Failed to extract product info from {url}")
        return product

    brand = source.get("brand") or ""
    name  = source.get("name") or ""
    image = source.get("image")

    print(f"[daily] Identified: {brand} — {name}")

    product["brand"]  = brand
    product["name"]   = name
    product["image"]  = image
    product["status"] = "active"

    # Search all retailers
    retailers_data = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(search_retailer, key, brand, name, size, url): key
            for key in RETAILER_MODULES
        }
        for future in caf(futures):
            key, result = future.result()
            retailers_data[key] = result

    # Fallback: use source URL for source retailer if search failed
    if not retailers_data.get(source_retailer) and source.get("price"):
        retailers_data[source_retailer] = {
            "url": url, "price": source.get("price"), "in_stock_in_size": False,
        }

    for key in RETAILER_MODULES:
        result = retailers_data.get(key)
        product["retailers"][key] = {
            "url":   result["url"] if result else None,
            "found": result is not None,
        }

    return product


def load_yesterday_snapshot() -> dict[str, dict]:
    files = sorted(SNAPSHOTS_DIR.glob("*.json"))
    today = str(date.today())
    candidates = [f for f in files if f.stem != today]
    if not candidates:
        return {}
    with open(candidates[-1]) as f:
        entries = json.load(f)
    return {entry["id"]: entry["prices"] for entry in entries}


def scrape_product_retailer(product: dict, retailer_key: str) -> tuple[str, dict]:
    retailer_info = product["retailers"].get(retailer_key, {})
    if not retailer_info.get("found") or not retailer_info.get("url"):
        return retailer_key, {"price": None, "in_stock_in_size": False}
    mod = RETAILER_MODULES[retailer_key]
    try:
        result = mod.scrape_price_and_stock(retailer_info["url"], product["size"])
        return retailer_key, result
    except Exception as e:
        print(f"  [!] {RETAILER_LABELS[retailer_key]}: {e}")
        return retailer_key, {"price": None, "in_stock_in_size": False}


def write_snapshot_entry(entry: dict):
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    today_file = SNAPSHOTS_DIR / f"{date.today()}.json"
    existing = []
    if today_file.exists():
        with open(today_file) as f:
            existing = json.load(f)
    updated = [e for e in existing if e["id"] != entry["id"]]
    updated.append(entry)
    with open(today_file, "w") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)


def check_alerts(product, today_prices, yesterday_prices):
    alerts = []
    alert_below = product.get("alert_below")
    for retailer_key, today in today_prices.items():
        new_price    = today.get("price")
        new_in_stock = today.get("in_stock_in_size", False)
        if not new_price:
            continue
        yesterday = (yesterday_prices or {}).get(retailer_key, {})
        old_price    = yesterday.get("price")
        old_in_stock = yesterday.get("in_stock_in_size", False)
        if alert_below and new_price < alert_below and new_in_stock:
            if not old_price or old_price >= alert_below:
                alerts.append({"type": "price_below_threshold", "product": product,
                                "retailer": retailer_key, "old_price": old_price, "new_price": new_price})
        if old_price and new_price < old_price and new_in_stock:
            alerts.append({"type": "price_drop", "product": product,
                            "retailer": retailer_key, "old_price": old_price, "new_price": new_price})
        if old_price and new_price > old_price:
            alerts.append({"type": "price_increase", "product": product,
                            "retailer": retailer_key, "old_price": old_price, "new_price": new_price})
        if not old_in_stock and new_in_stock:
            alerts.append({"type": "restock", "product": product,
                            "retailer": retailer_key, "old_price": old_price, "new_price": new_price})
    return alerts


def run():
    products = load_products()
    if not products:
        print("[daily] No products to scrape.")
        return

    # Onboard any pending items first
    changed = False
    for i, product in enumerate(products):
        if product.get("status") == "pending":
            products[i] = onboard_pending(product)
            changed = True
    if changed:
        save_products(products)
        print("[daily] Pending items onboarded.")

    yesterday = load_yesterday_snapshot()
    all_alerts = []

    print(f"[daily] Scraping {len(products)} product(s)...\n")

    for product in products:
        label = f"{product.get('brand','?')} — {product.get('name','?')}"
        print(f"[daily] {label} (size {product.get('size','?')})")
        today_prices = {}

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(scrape_product_retailer, product, key): key
                for key in RETAILER_MODULES
            }
            for future in as_completed(futures):
                key, result = future.result()
                today_prices[key] = result
                label2 = RETAILER_LABELS[key]
                price  = result.get("price")
                stock  = "✓" if result.get("in_stock_in_size") else "✗"
                print(f"  {label2}: ${price} | size {product['size']} {stock}")

        snapshot_entry = {
            "id":         product["id"],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "size":       product["size"],
            "prices":     today_prices,
        }
        write_snapshot_entry(snapshot_entry)

        yesterday_prices = yesterday.get(product["id"])
        alerts = check_alerts(product, today_prices, yesterday_prices)
        all_alerts.extend(alerts)
        print()

    if all_alerts:
        print(f"[daily] {len(all_alerts)} alert(s) to send...")
        from notify import send_alerts
        send_alerts(all_alerts)
    else:
        print("[daily] No price changes detected.")

    print(f"[daily] Done. Snapshot written for {date.today()}.")


if __name__ == "__main__":
    run()
