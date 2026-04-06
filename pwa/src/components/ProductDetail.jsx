import PriceChart from './PriceChart'
import { buildPriceHistory } from '../lib/github'

const RETAILER_LABELS = {
  neiman_marcus: 'Neiman Marcus',
  saks:          'Saks Fifth Avenue',
  farfetch:      'Farfetch',
  net_a_porter:  'Net-a-Porter',
}

export default function ProductDetail({ product, snapshots, onClose }) {
  const history      = buildPriceHistory(product.id, snapshots)
  const latestSnap   = snapshots[snapshots.length - 1]
  const latestPrices = latestSnap?.data?.find(e => e.id === product.id)?.prices || {}
  const retailers    = product.retailers || {}

  return (
    <div style={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={styles.drawer}>
        {/* Header */}
        <div style={styles.header}>
          <div>
            <p style={styles.brand}>{product.brand}</p>
            <h2 style={styles.name}>{product.name}</h2>
            <p style={styles.size}>Size {product.size}</p>
          </div>
          <button style={styles.close} onClick={onClose}>✕</button>
        </div>

        {/* Alert badge */}
        {product.alert_below && (
          <div style={styles.alertBadge}>
            Alert set for under ${product.alert_below.toLocaleString()}
          </div>
        )}

        {/* Price chart */}
        <div style={styles.section}>
          <p style={styles.sectionLabel}>Price history</p>
          <PriceChart history={history} alertBelow={product.alert_below} />
        </div>

        {/* Current prices table */}
        <div style={styles.section}>
          <p style={styles.sectionLabel}>Current prices</p>
          <div style={styles.retailerList}>
            {Object.entries(retailers).map(([key, val]) => {
              const snap     = latestPrices[key]
              const price    = snap?.price
              const inStock  = snap?.in_stock_in_size
              const found    = val.found

              return (
                <a
                  key={key}
                  href={val.url || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ ...styles.retailerRow, opacity: found ? 1 : .4,
                           pointerEvents: val.url ? 'auto' : 'none' }}
                >
                  <div>
                    <p style={styles.retailerName}>{RETAILER_LABELS[key]}</p>
                    {!found && <p style={styles.notFound}>Not available</p>}
                  </div>
                  <div style={styles.priceCell}>
                    {price
                      ? <span style={styles.retailerPrice}>${price.toLocaleString()}</span>
                      : <span style={styles.noPrice}>—</span>
                    }
                    {found && (
                      <span style={{
                        ...styles.stockBadge,
                        background: inStock ? '#e8f5ee' : '#f5f5f5',
                        color:      inStock ? '#2d8a4e' : '#999',
                      }}>
                        {inStock ? `Size ${product.size} in stock` : 'Out of stock'}
                      </span>
                    )}
                    {val.url && <span style={styles.arrow}>→</span>}
                  </div>
                </a>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

const styles = {
  overlay:      { position:'fixed', inset:0, background:'rgba(0,0,0,.4)',
                  display:'flex', alignItems:'flex-end', justifyContent:'center', zIndex:100 },
  drawer:       { background:'#fff', borderRadius:'20px 20px 0 0', padding:'28px 24px 48px',
                  width:'100%', maxWidth:600, maxHeight:'92vh', overflowY:'auto' },
  header:       { display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:16 },
  brand:        { fontSize:11, color:'#999', textTransform:'uppercase', letterSpacing:'.06em', marginBottom:3 },
  name:         { fontSize:20, fontWeight:500, color:'#111', lineHeight:1.2 },
  size:         { fontSize:13, color:'#aaa', marginTop:4 },
  close:        { background:'none', border:'none', fontSize:20, cursor:'pointer', color:'#999', padding:4 },
  alertBadge:   { display:'inline-block', background:'#fff8e6', color:'#8a6000', fontSize:12,
                  padding:'5px 12px', borderRadius:20, marginBottom:20, border:'1px solid #f0d580' },
  section:      { marginBottom:28 },
  sectionLabel: { fontSize:11, color:'#aaa', textTransform:'uppercase', letterSpacing:'.08em',
                  marginBottom:14, fontWeight:500 },
  retailerList: { display:'flex', flexDirection:'column', gap:0 },
  retailerRow:  { display:'flex', justifyContent:'space-between', alignItems:'center',
                  padding:'14px 0', borderBottom:'1px solid #f5f5f5',
                  textDecoration:'none', color:'inherit' },
  retailerName: { fontSize:15, fontWeight:500, color:'#111' },
  notFound:     { fontSize:12, color:'#bbb', marginTop:2 },
  priceCell:    { display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4 },
  retailerPrice:{ fontSize:17, fontWeight:500, color:'#111' },
  noPrice:      { fontSize:17, color:'#ddd' },
  stockBadge:   { fontSize:11, padding:'3px 9px', borderRadius:20 },
  arrow:        { fontSize:14, color:'#ccc', marginTop:2 },
}
