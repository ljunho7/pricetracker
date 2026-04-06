import { useState, useEffect, useCallback } from 'react'
import LockScreen    from './components/LockScreen'
import ProductCard   from './components/ProductCard'
import ProductDetail from './components/ProductDetail'
import AddItem       from './components/AddItem'
import { fetchProducts, fetchSnapshots } from './lib/github'

export default function App() {
  const [unlocked,  setUnlocked]  = useState(() => localStorage.getItem('pt_unlocked') === '1')
  const [products,  setProducts]  = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [selected,  setSelected]  = useState(null)   // product detail drawer
  const [addOpen,   setAddOpen]   = useState(false)  // add item modal
  const [lastSync,  setLastSync]  = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [prods, snaps] = await Promise.all([fetchProducts(), fetchSnapshots(90)])
      setProducts(prods)
      setSnapshots(snaps)
      setLastSync(new Date())
    } catch (e) {
      console.error('Load error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { if (unlocked) load() }, [unlocked, load])

  // Get latest snapshot entry for a product
  function getLatestPrices(productId) {
    if (!snapshots.length) return null
    const latest = snapshots[snapshots.length - 1]
    const entry  = latest?.data?.find(e => e.id === productId)
    return entry || null
  }

  // Summary stats
  const totalItems   = products.length
  const inStockCount = products.filter(p => {
    const snap = getLatestPrices(p.id)
    return snap && Object.values(snap.prices || {}).some(v => v?.in_stock_in_size)
  }).length
  const lastDate = snapshots.length ? snapshots[snapshots.length - 1].date : null

  if (!unlocked) return <LockScreen onUnlock={() => setUnlocked(true)} />

  return (
    <div style={styles.app}>
      {/* Header */}
      <header style={styles.header}>
        <div>
          <h1 style={styles.logo}>✦ Price Tracker</h1>
          <p style={styles.sub}>Saks · Neiman Marcus · Farfetch · Net-a-Porter</p>
        </div>
        <button style={styles.addBtn} onClick={() => setAddOpen(true)}>+ Add item</button>
      </header>

      {/* Stats bar */}
      {!loading && products.length > 0 && (
        <div style={styles.statsBar}>
          <div style={styles.stat}>
            <span style={styles.statVal}>{totalItems}</span>
            <span style={styles.statLabel}>tracked</span>
          </div>
          <div style={styles.statDivider} />
          <div style={styles.stat}>
            <span style={styles.statVal}>{inStockCount}</span>
            <span style={styles.statLabel}>in stock in your size</span>
          </div>
          <div style={styles.statDivider} />
          <div style={styles.stat}>
            <span style={styles.statVal}>{lastDate || '—'}</span>
            <span style={styles.statLabel}>last checked</span>
          </div>
        </div>
      )}

      {/* Content */}
      <main style={styles.main}>
        {loading ? (
          <div style={styles.loading}>
            <div style={styles.spinner} />
            <p>Loading prices…</p>
          </div>
        ) : products.length === 0 ? (
          <div style={styles.empty}>
            <p style={styles.emptyIcon}>✦</p>
            <p style={styles.emptyTitle}>No items tracked yet</p>
            <p style={styles.emptySub}>Add your first item to start tracking prices across all four retailers.</p>
            <button style={styles.emptyBtn} onClick={() => setAddOpen(true)}>Add your first item</button>
          </div>
        ) : (
          <div style={styles.grid}>
            {products.map(product => (
              <ProductCard
                key={product.id}
                product={product}
                latestPrices={getLatestPrices(product.id)}
                onClick={() => setSelected(product)}
              />
            ))}
          </div>
        )}
      </main>

      {/* Refresh button */}
      {!loading && (
        <button style={styles.refreshBtn} onClick={load} title="Refresh">
          ↻
        </button>
      )}

      {/* Modals */}
      {selected && (
        <ProductDetail
          product={selected}
          snapshots={snapshots}
          onClose={() => setSelected(null)}
        />
      )}
      {addOpen && (
        <AddItem
          onClose={() => setAddOpen(false)}
          onAdded={load}
        />
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
        * { -webkit-tap-highlight-color: transparent; }
      `}</style>
    </div>
  )
}

const styles = {
  app:         { minHeight:'100vh', background:'#f7f7f5' },
  header:      { background:'#fff', borderBottom:'1px solid #eee', padding:'18px 20px',
                 display:'flex', alignItems:'center', justifyContent:'space-between',
                 position:'sticky', top:0, zIndex:10 },
  logo:        { fontSize:18, fontWeight:500, color:'#111', letterSpacing:'.02em' },
  sub:         { fontSize:11, color:'#aaa', marginTop:2 },
  addBtn:      { background:'#111', color:'#fff', border:'none', borderRadius:10,
                 padding:'10px 18px', fontSize:14, fontWeight:500, cursor:'pointer' },
  statsBar:    { background:'#fff', borderBottom:'1px solid #f0f0f0',
                 padding:'12px 20px', display:'flex', alignItems:'center', gap:16 },
  stat:        { display:'flex', flexDirection:'column', alignItems:'center' },
  statVal:     { fontSize:16, fontWeight:500, color:'#111' },
  statLabel:   { fontSize:11, color:'#aaa' },
  statDivider: { width:1, height:28, background:'#eee' },
  main:        { padding:'20px', maxWidth:960, margin:'0 auto' },
  grid:        { display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(200px, 1fr))', gap:16 },
  loading:     { display:'flex', flexDirection:'column', alignItems:'center',
                 justifyContent:'center', padding:'80px 0', color:'#aaa', gap:16 },
  spinner:     { width:28, height:28, border:'2px solid #eee', borderTopColor:'#111',
                 borderRadius:'50%', animation:'spin .8s linear infinite' },
  empty:       { textAlign:'center', padding:'80px 20px' },
  emptyIcon:   { fontSize:32, color:'#ccc', marginBottom:16 },
  emptyTitle:  { fontSize:20, fontWeight:500, color:'#111', marginBottom:8 },
  emptySub:    { fontSize:14, color:'#aaa', maxWidth:320, margin:'0 auto 24px' },
  emptyBtn:    { background:'#111', color:'#fff', border:'none', borderRadius:10,
                 padding:'12px 24px', fontSize:15, fontWeight:500, cursor:'pointer' },
  refreshBtn:  { position:'fixed', bottom:24, right:24, width:44, height:44,
                 background:'#fff', border:'1px solid #eee', borderRadius:'50%',
                 fontSize:20, cursor:'pointer', color:'#666', boxShadow:'0 2px 8px rgba(0,0,0,.08)' },
}
