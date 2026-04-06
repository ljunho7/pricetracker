import { useState } from 'react'
import { addProduct } from '../lib/github'

const SUPPORTED = ['neimanmarcus.com', 'saksfifthavenue.com', 'farfetch.com', 'net-a-porter.com']
const SIZES     = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', 'ONE SIZE']

export default function AddItem({ onClose, onAdded }) {
  const [url,        setUrl]        = useState('')
  const [size,       setSize]       = useState('')
  const [alertBelow, setAlertBelow] = useState('')
  const [error,      setError]      = useState('')
  const [loading,    setLoading]    = useState(false)
  const [success,    setSuccess]    = useState(false)

  function validateUrl(u) {
    return SUPPORTED.some(domain => u.toLowerCase().includes(domain))
  }

  async function submit() {
    setError('')
    if (!url.trim())         return setError('Please paste a product URL.')
    if (!validateUrl(url))   return setError('URL must be from Saks, Neiman Marcus, Farfetch, or Net-a-Porter.')
    if (!size)               return setError('Please select a size.')

    setLoading(true)
    try {
      await addProduct({
        url:        url.trim(),
        size,
        alertBelow: alertBelow ? parseFloat(alertBelow) : null,
        addedBy:    'user',
      })
      setSuccess(true)
      setTimeout(() => { onAdded(); onClose() }, 2000)
    } catch (e) {
      setError(e.message || 'Something went wrong. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={styles.modal}>
        <div style={styles.header}>
          <h2 style={styles.title}>Track a new item</h2>
          <button style={styles.close} onClick={onClose}>✕</button>
        </div>

        {success ? (
          <div style={styles.success}>
            <div style={styles.successIcon}>✓</div>
            <p style={styles.successText}>Added! Prices will be checked tonight.</p>
          </div>
        ) : (
          <>
            <div style={styles.field}>
              <label style={styles.label}>Product URL</label>
              <input
                style={styles.input}
                type="url"
                placeholder="Paste URL from Saks, Neiman Marcus, Farfetch, or Net-a-Porter"
                value={url}
                onChange={e => { setUrl(e.target.value); setError('') }}
              />
              <p style={styles.hint}>
                Supported: Saks, Neiman Marcus, Farfetch, Net-a-Porter
              </p>
            </div>

            <div style={styles.field}>
              <label style={styles.label}>Size</label>
              <div style={styles.sizeGrid}>
                {SIZES.map(s => (
                  <button
                    key={s}
                    style={{ ...styles.sizeBtn, ...(size === s ? styles.sizeBtnActive : {}) }}
                    onClick={() => setSize(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div style={styles.field}>
              <label style={styles.label}>Alert me if price drops below (optional)</label>
              <div style={styles.priceInput}>
                <span style={styles.dollar}>$</span>
                <input
                  style={{ ...styles.input, paddingLeft: 28 }}
                  type="number"
                  placeholder="e.g. 800"
                  value={alertBelow}
                  onChange={e => setAlertBelow(e.target.value)}
                />
              </div>
            </div>

            {error && <p style={styles.error}>{error}</p>}

            <div style={styles.actions}>
              <button style={styles.cancel} onClick={onClose}>Cancel</button>
              <button
                style={{ ...styles.submit, opacity: loading ? .6 : 1 }}
                onClick={submit}
                disabled={loading}
              >
                {loading ? 'Adding…' : 'Add item'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

const styles = {
  overlay:      { position:'fixed', inset:0, background:'rgba(0,0,0,.45)',
                  display:'flex', alignItems:'flex-end', justifyContent:'center',
                  zIndex:100, padding:'0 0 0 0' },
  modal:        { background:'#fff', borderRadius:'20px 20px 0 0', padding:'28px 24px 40px',
                  width:'100%', maxWidth:540, maxHeight:'90vh', overflowY:'auto' },
  header:       { display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:24 },
  title:        { fontSize:18, fontWeight:500, color:'#111' },
  close:        { background:'none', border:'none', fontSize:18, cursor:'pointer', color:'#999', padding:4 },
  field:        { marginBottom:20 },
  label:        { display:'block', fontSize:12, fontWeight:500, color:'#666',
                  textTransform:'uppercase', letterSpacing:'.06em', marginBottom:8 },
  input:        { width:'100%', padding:'11px 14px', fontSize:15, border:'1.5px solid #e8e8e8',
                  borderRadius:10, outline:'none', color:'#111' },
  hint:         { fontSize:12, color:'#aaa', marginTop:5 },
  sizeGrid:     { display:'flex', flexWrap:'wrap', gap:8 },
  sizeBtn:      { padding:'8px 16px', fontSize:13, border:'1.5px solid #e8e8e8',
                  borderRadius:8, cursor:'pointer', background:'#fff', color:'#555', fontWeight:400 },
  sizeBtnActive:{ background:'#111', color:'#fff', borderColor:'#111' },
  priceInput:   { position:'relative' },
  dollar:       { position:'absolute', left:14, top:'50%', transform:'translateY(-50%)',
                  fontSize:15, color:'#999', pointerEvents:'none' },
  error:        { fontSize:13, color:'#c00', marginBottom:16, padding:'10px 14px',
                  background:'#fff5f5', borderRadius:8 },
  actions:      { display:'flex', gap:10, marginTop:8 },
  cancel:       { flex:1, padding:'13px', background:'#f5f5f5', color:'#555',
                  border:'none', borderRadius:10, fontSize:15, cursor:'pointer' },
  submit:       { flex:2, padding:'13px', background:'#111', color:'#fff',
                  border:'none', borderRadius:10, fontSize:15, fontWeight:500, cursor:'pointer' },
  success:      { textAlign:'center', padding:'40px 0' },
  successIcon:  { fontSize:36, color:'#2d8a4e', marginBottom:12 },
  successText:  { fontSize:15, color:'#444' },
}
