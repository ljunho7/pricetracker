"""
daily_scrape.py — Run every morning via GitHub Actions cron.
Reads products.json, scrapes current prices + size availability
from all 4 retailers, writes snapshot, triggers email alerts.
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


def load_yesterday_snapshot() -> dict[str, dict]:
    """Return { product_id: { retailer: { price, in_stock_in_size } } }"""
    files = sorted(SNAPSHOTS_DIR.glob("*.json"))
    if len(files) < 2:
        return {}
    yesterday_file = files[-2] if files[-1].stem == str(date.today()) else files[-1]
    with open(yesterday_file) as f:
        entries = json.load(f)
    return {entry["id"]: entry["prices"] for entry in entries}


def scrape_product_retailer(product: dict, retailer_key: str) -> tuple[str, dict]:
    """Scrape one retailer for one product. Returns (retailer_key, result)."""
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
    """Append or update one product entry in today's snapshot file."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    today_file = SNAPSHOTS_DIR / f"{date.today()}.json"

    existing = []
    if today_file.exists():
        with open(today_file) as f:
            existing = json.load(f)

    # Replace if product already in today's file, else append
    updated = [e for e in existing if e["id"] != entry["id"]]
    updated.append(entry)

    with open(today_file, "w") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)


def check_alerts(product: dict, today_prices: dict,
                 yesterday_prices: dict | None) -> list[dict]:
    """
    Return list of alert dicts to send.
    Each alert: { type, product, retailer, old_price, new_price }
    """
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

        # Price drop below threshold
        if alert_below and new_price < alert_below and new_in_stock:
            if not old_price or old_price >= alert_below:
                alerts.append({
                    "type":      "price_below_threshold",
                    "product":   product,
                    "retailer":  retailer_key,
                    "old_price": old_price,
                    "new_price": new_price,
                })

        # Any price drop (vs yesterday)
        if old_price and new_price < old_price and new_in_stock:
            alerts.append({
                "type":      "price_drop",
                "product":   product,
                "retailer":  retailer_key,
                "old_price": old_price,
                "new_price": new_price,
            })

        # Price increase (buy before it goes higher)
        if old_price and new_price > old_price:
            alerts.append({
                "type":      "price_increase",
                "product":   product,
                "retailer":  retailer_key,
                "old_price": old_price,
                "new_price": new_price,
            })

        # Restock in target size
        if not old_in_stock and new_in_stock:
            alerts.append({
                "type":      "restock",
                "product":   product,
                "retailer":  retailer_key,
                "old_price": old_price,
                "new_price": new_price,
            })

    return alerts


def run():
    products = load_products()
    if not products:
        print("[daily] No products to scrape.")
        return

    yesterday = load_yesterday_snapshot()
    all_alerts = []

    print(f"[daily] Scraping {len(products)} product(s)...\n")

    for product in products:
        print(f"[daily] {product['brand']} — {product['name']} (size {product['size']})")
        today_prices = {}

        # Scrape all retailers in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(scrape_product_retailer, product, key): key
                for key in RETAILER_MODULES
            }
            for future in as_completed(futures):
                key, result = future.result()
                today_prices[key] = result
                label = RETAILER_LABELS[key]
                price = result.get("price")
                stock = "✓" if result.get("in_stock_in_size") else "✗"
                print(f"  {label}: ${price} | size {product['size']} {stock}")

        # Build snapshot entry
        snapshot_entry = {
            "id":         product["id"],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "size":       product["size"],
            "prices":     today_prices,
        }
        write_snapshot_entry(snapshot_entry)

        # Check alerts
        yesterday_prices = yesterday.get(product["id"])
        alerts = check_alerts(product, today_prices, yesterday_prices)
        all_alerts.extend(alerts)
        print()

    # Send alerts
    if all_alerts:
        print(f"[daily] {len(all_alerts)} alert(s) to send...")
        from notify import send_alerts
        send_alerts(all_alerts)
    else:
        print("[daily] No price changes detected.")

    print(f"[daily] Done. Snapshot written for {date.today()}.")


if __name__ == "__main__":
    run()
