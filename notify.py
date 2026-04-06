"""
notify.py — Send price alert emails via Resend.
Requires RESEND_API_KEY and ALERT_EMAIL env vars.
"""

import os
import json
from datetime import date

RETAILER_LABELS = {
    "neiman_marcus": "Neiman Marcus",
    "saks":          "Saks Fifth Avenue",
    "farfetch":      "Farfetch",
    "net_a_porter":  "Net-a-Porter",
}

ALERT_TYPE_SUBJECT = {
    "price_drop":             "Price drop",
    "price_below_threshold":  "Price alert hit",
    "price_increase":         "Price increase alert",
    "restock":                "Back in stock",
}

ALERT_TYPE_EMOJI = {
    "price_drop":             "↓",
    "price_below_threshold":  "🎯",
    "price_increase":         "↑",
    "restock":                "✓",
}


def _format_price(price) -> str:
    if price is None:
        return "N/A"
    return f"${price:,.0f}"


def _build_email_html(alerts: list[dict]) -> str:
    rows = ""
    for a in alerts:
        p = a["product"]
        retailer = RETAILER_LABELS.get(a["retailer"], a["retailer"])
        emoji    = ALERT_TYPE_EMOJI.get(a["type"], "•")
        label    = ALERT_TYPE_SUBJECT.get(a["type"], a["type"].replace("_", " ").title()
        old      = _format_price(a.get("old_price"))
        new      = _format_price(a.get("new_price"))
        url      = (p.get("retailers", {}).get(a["retailer"]) or {}).get("url", "#")
        img      = p.get("image", "")

        rows += f"""
        <tr>
          <td style="padding:16px 0;border-bottom:1px solid #eee;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="80">
                  {"<img src='" + img + "' width='72' style='border-radius:4px;display:block;'>" if img else ""}
                </td>
                <td style="padding-left:16px;vertical-align:top;">
                  <p style="margin:0 0 2px;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.06em;">
                    {retailer}
                  </p>
                  <p style="margin:0 0 4px;font-size:15px;font-weight:500;color:#111;">
                    {p.get("brand","")} — {p.get("name","")}
                  </p>
                  <p style="margin:0 0 8px;font-size:12px;color:#666;">
                    Size {p.get("size","")}
                  </p>
                  <p style="margin:0 0 8px;font-size:14px;color:#111;">
                    {emoji} {old} → <strong>{new}</strong>
                  </p>
                  <a href="{url}"
                     style="display:inline-block;padding:6px 14px;background:#111;color:#fff;
                            text-decoration:none;font-size:12px;border-radius:4px;">
                    Shop now
                  </a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#f9f9f9;font-family:-apple-system,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9f9f9;padding:32px 0;">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0"
                 style="background:#fff;border-radius:8px;padding:32px;border:1px solid #eee;">
            <tr>
              <td>
                <p style="margin:0 0 4px;font-size:11px;color:#888;letter-spacing:.08em;text-transform:uppercase;">
                  Price Tracker
                </p>
                <h1 style="margin:0 0 24px;font-size:20px;font-weight:500;color:#111;">
                  Price alert — {date.today().strftime("%B %d, %Y")}
                </h1>
                <table width="100%" cellpadding="0" cellspacing="0">
                  {rows}
                </table>
                <p style="margin:24px 0 0;font-size:12px;color:#aaa;text-align:center;">
                  Prices checked daily. All prices in USD.
                </p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """


def send_alerts(alerts: list[dict]):
    """Send a digest email for all alerts."""
    api_key    = os.environ.get("RESEND_API_KEY")
    to_email   = os.environ.get("ALERT_EMAIL")
    from_email = os.environ.get("FROM_EMAIL", "alerts@yourdomain.com")

    if not api_key or not to_email:
        print("[notify] RESEND_API_KEY or ALERT_EMAIL not set — skipping email.")
        for a in alerts:
            p = a["product"]
            print(f"  [{a['type']}] {p['brand']} {p['name']} size {p['size']} "
                  f"@ {RETAILER_LABELS.get(a['retailer'])} "
                  f"${a.get('old_price')} → ${a.get('new_price')}")
        return

    import urllib.request

    # Group subjects
    types = list({a["type"] for a in alerts})
    subject_parts = [ALERT_TYPE_SUBJECT.get(t, t) for t in types]
    subject = f"Price tracker: {', '.join(subject_parts)} — {len(alerts)} item(s)"

    html = _build_email_html(alerts)

    payload = json.dumps({
        "from":    from_email,
        "to":      [to_email],
        "subject": subject,
        "html":    html,
    }).encode()

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(f"[notify] Email sent: {result.get('id')}")
    except Exception as e:
        print(f"[notify] Failed to send email: {e}")
