// api/add-item.js — Vercel serverless function
// Receives { url, size, alert_below, added_by } from PWA
// Appends a pending entry to products.json via GitHub Contents API

const GITHUB_PAT  = process.env.GITHUB_PAT
const GITHUB_REPO = process.env.GITHUB_REPO   // "username/reponame"
const BRANCH      = process.env.GITHUB_BRANCH || 'main'
const FILE_PATH   = 'data/products.json'

const SUPPORTED_DOMAINS = [
  'neimanmarcus.com',
  'saksfifthavenue.com',
  'farfetch.com',
  'net-a-porter.com',
]

function detectRetailer(url) {
  const u = url.toLowerCase()
  if (u.includes('neimanmarcus.com'))    return 'neiman_marcus'
  if (u.includes('saksfifthavenue.com')) return 'saks'
  if (u.includes('farfetch.com'))        return 'farfetch'
  if (u.includes('net-a-porter.com'))    return 'net_a_porter'
  return null
}

function normalizeSize(raw) {
  const map = {
    'extra small': 'XS', 'extrasmall': 'XS', 'xsmall': 'XS',
    'small': 'S', 'medium': 'M', 'large': 'L',
    'extra large': 'XL', 'extralarge': 'XL', 'xlarge': 'XL',
    'one size': 'OS', 'onesize': 'OS', 'os': 'OS',
    'xxs': 'XXS', 'xs': 'XS', 's': 'S', 'm': 'M',
    'l': 'L', 'xl': 'XL', 'xxl': 'XXL',
  }
  const key = raw.toLowerCase().trim().replace(/-/g, '').replace(/\s+/g, ' ')
  return map[key] || map[key.replace(' ', '')] || raw.toUpperCase()
}

async function githubRequest(path, method = 'GET', body = null) {
  const url = `https://api.github.com/repos/${GITHUB_REPO}/contents/${path}?ref=${BRANCH}`
  console.log('[add-item] calling:', url, 'PAT set:', !!GITHUB_PAT) 
  const opts = {
    method,
    headers: {
      Authorization: `Bearer ${GITHUB_PAT}`,
      Accept:        'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
  }
  if (body) opts.body = JSON.stringify(body)
  const res  = await fetch(url, opts)
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || `GitHub API error ${res.status}`)
  return data
}

export default async function handler(req, res) {
  // CORS for PWA
  res.setHeader('Access-Control-Allow-Origin',  '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  if (req.method === 'OPTIONS') return res.status(200).end()
  if (req.method !== 'POST')   return res.status(405).json({ error: 'Method not allowed' })

  try {
    const { url, size, alert_below, added_by } = req.body

    // Validate
    if (!url || !size) return res.status(400).json({ error: 'url and size are required' })
    const retailer = detectRetailer(url)
    if (!retailer)    return res.status(400).json({ error: 'URL not from a supported retailer' })

    // Read current products.json from GitHub
    const fileData = await githubRequest(FILE_PATH)
    const content  = Buffer.from(fileData.content, 'base64').toString('utf8')
    const products = JSON.parse(content)

    // Check for duplicate URL
    const exists = products.some(p =>
      p.source_url === url || Object.values(p.retailers || {}).some(r => r.url === url)
    )
    if (exists) return res.status(409).json({ error: 'This item is already being tracked.' })

    // Build new pending entry
    const id = Math.random().toString(36).slice(2, 10)
    const newProduct = {
      id,
      brand:       null,       // filled by onboard.py
      name:        null,       // filled by onboard.py
      size:        normalizeSize(size),
      added_by:    added_by || 'unknown',
      added_at:    new Date().toISOString(),
      alert_below: alert_below ? parseFloat(alert_below) : null,
      source_url:  url,
      image:       null,       // filled by onboard.py
      status:      'pending',  // onboard.py sets to 'active' after finding all retailers
      retailers: {
        neiman_marcus: { url: null, found: false },
        saks:          { url: null, found: false },
        farfetch:      { url: null, found: false },
        net_a_porter:  { url: null, found: false },
        // pre-fill the source retailer URL
        [retailer]:    { url, found: true },
      },
    }

    products.push(newProduct)

    // Write back to GitHub
    const updatedContent = Buffer.from(JSON.stringify(products, null, 2)).toString('base64')
    await githubRequest(FILE_PATH, 'PUT', {
      message: `feat: track new item (${id}) — pending onboarding`,
      content: updatedContent,
      sha:     fileData.sha,
      branch:  BRANCH,
    })

    return res.status(200).json({ success: true, id, message: 'Item added. Prices will be checked tonight.' })

  } catch (e) {
    console.error('[add-item]', e)
    return res.status(500).json({ error: e.message || 'Internal error' })
  }
}
