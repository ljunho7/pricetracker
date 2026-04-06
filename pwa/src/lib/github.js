// lib/github.js — reads and writes data via GitHub Contents API

const REPO   = import.meta.env.VITE_GITHUB_REPO   // e.g. "username/pricetracker"
const BRANCH = import.meta.env.VITE_GITHUB_BRANCH || 'main'
const RAW    = `https://raw.githubusercontent.com/${REPO}/${BRANCH}`

// ── Read helpers ──────────────────────────────────────────────────

export async function fetchProducts() {
  const res = await fetch(`${RAW}/data/products.json`, { cache: 'no-store' })
  if (!res.ok) return []
  return res.json()
}

export async function fetchSnapshots(days = 90) {
  // Generate list of dates to try (last N days)
  const dates = []
  for (let i = 0; i < days; i++) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    dates.push(d.toISOString().split('T')[0])
  }

  const results = await Promise.allSettled(
    dates.map(date =>
      fetch(`${RAW}/data/snapshots/${date}.json`, { cache: 'no-store' })
        .then(r => r.ok ? r.json() : null)
        .then(data => data ? { date, data } : null)
    )
  )

  return results
    .filter(r => r.status === 'fulfilled' && r.value)
    .map(r => r.value)
    .sort((a, b) => a.date.localeCompare(b.date))
}

// Build price history for a specific product across all retailers
export function buildPriceHistory(productId, snapshots) {
  const RETAILERS = ['neiman_marcus', 'saks', 'farfetch', 'net_a_porter']
  const LABELS    = {
    neiman_marcus: 'Neiman Marcus',
    saks:          'Saks',
    farfetch:      'Farfetch',
    net_a_porter:  'Net-a-Porter',
  }

  return snapshots.map(({ date, data }) => {
    const entry = data.find(e => e.id === productId)
    const point = { date }
    RETAILERS.forEach(r => {
      const prices = entry?.prices?.[r]
      point[LABELS[r]] = prices?.price ?? null
      point[`${LABELS[r]}_stock`] = prices?.in_stock_in_size ?? false
    })
    return point
  })
}

// ── Write helpers (via Vercel API route) ─────────────────────────

export async function addProduct({ url, size, alertBelow, addedBy }) {
  const res = await fetch('/api/add-item', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ url, size, alert_below: alertBelow, added_by: addedBy }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.error || 'Failed to add item')
  }
  return res.json()
}
