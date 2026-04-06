const RETAILER_LABELS = {
  neiman_marcus: 'Neiman Marcus',
  saks:          'Saks',
  farfetch:      'Farfetch',
  net_a_porter:  'Net-a-Porter',
}

const RETAILER_COLORS = {
  neiman_marcus: '#8B6F47',
  saks:          '#1a1a2e',
  farfetch:      '#333',
  net_a_porter:  '#c8a882',
}

export default function ProductCard({ product, latestPrices, onClick }) {
  const retailers  = product.retailers || {}
  const prices     = latestPrices?.prices || {}

  // Find lowest available price
  const available = Object.entries(prices)
    .filter(([, v]) => v?.price && v?.in_stock_in_size)
    .map(([k, v]) => ({ retailer: k, price: v.price }))
    .sort((a, b) => a.price - b.price)

  const lowestPrice = available[0]

  // Check for any price change (vs yesterday is not tracked here — just show current)
  const allPrices = Object.values(prices).filter(v => v?.price).map(v => v.price)
  const minPrice  = allPrices.length ? Math.min(...allPrices) : null
  const maxPrice  = allPrices.length ? Math.max(...allPrices) : null

  return (
    <div style={styles.card} onClick={onClick}>
      {/* Image */}
      <div style={styles.imgWrap}>
        {product.image
          ? <img src={product.image} alt={product.name} style={styles.img} />
          : <div style={styles.imgPlaceholder}>✦</div>
        }
        {lowestPrice && (
          <div style={styles.badge}>In stock</div>
        )}
      </div>

      {/* Info */}
      <div style={styles.info}>
        <p style={styles.brand}>{product.brand}</p>
        <p style={styles.name}>{product.name}</p>
        <p style={styles.size}>Size {product.size}</p>

        {/* Price range */}
        {minPrice ? (
          <div style={styles.priceRow}>
            <span style={styles.price}>${minPrice.toLocaleString()}</span>
            {maxPrice !== minPrice && (
              <span style={styles.priceRange}> – ${maxPrice.toLocaleString()}</span>
            )}
          </div>
        ) : (
          <p style={styles.noPrice}>Checking prices…</p>
        )}

        {/* Retailer pills */}
        <div style={styles.pills}>
          {Object.entries(retailers).map(([key, val]) => {
            const snap = prices[key]
            const found = val.found
            const inStock = snap?.in_stock_in_size
            return (
              <span
                key={key}
                style={{
                  ...styles.pill,
                  background: found ? (inStock ? '#f0f0f0' : '#f7f7f5') : '#fafafa',
                  color:      found ? '#333' : '#bbb',
                  textDecoration: found ? 'none' : 'line-through',
                }}
              >
                {inStock && <span style={{ color: '#2d8a4e', marginRight: 3 }}>·</span>}
                {RETAILER_LABELS[key]}
                {found && snap?.price ? ` $${snap.price.toLocaleString()}` : ''}
              </span>
            )
          })}
        </div>
      </div>
    </div>
  )
}

const styles = {
  card:           { background:'#fff', border:'1px solid #eee', borderRadius:14, overflow:'hidden',
                    cursor:'pointer', transition:'box-shadow .15s', display:'flex', flexDirection:'column' },
  imgWrap:        { position:'relative', aspectRatio:'3/4', background:'#f7f7f5', overflow:'hidden' },
  img:            { width:'100%', height:'100%', objectFit:'cover' },
  imgPlaceholder: { width:'100%', height:'100%', display:'flex', alignItems:'center',
                    justifyContent:'center', fontSize:32, color:'#ccc' },
  badge:          { position:'absolute', top:10, right:10, background:'#2d8a4e', color:'#fff',
                    fontSize:11, fontWeight:500, padding:'3px 8px', borderRadius:20 },
  info:           { padding:'14px 16px 16px', flex:1, display:'flex', flexDirection:'column', gap:3 },
  brand:          { fontSize:11, color:'#999', textTransform:'uppercase', letterSpacing:'.06em' },
  name:           { fontSize:14, fontWeight:500, color:'#111', lineHeight:1.3 },
  size:           { fontSize:12, color:'#aaa', marginBottom:6 },
  priceRow:       { display:'flex', alignItems:'baseline', gap:2, margin:'4px 0 8px' },
  price:          { fontSize:18, fontWeight:500, color:'#111' },
  priceRange:     { fontSize:13, color:'#999' },
  noPrice:        { fontSize:13, color:'#bbb', fontStyle:'italic', margin:'4px 0 8px' },
  pills:          { display:'flex', flexWrap:'wrap', gap:4, marginTop:'auto' },
  pill:           { fontSize:11, padding:'3px 7px', borderRadius:20, border:'1px solid #eee' },
}
