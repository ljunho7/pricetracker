import { useState } from 'react'

const PASSWORD = import.meta.env.VITE_APP_PASSWORD || 'luxury'

export default function LockScreen({ onUnlock }) {
  const [value, setValue]   = useState('')
  const [error, setError]   = useState(false)
  const [shake, setShake]   = useState(false)

  function attempt() {
    if (value === PASSWORD) {
      localStorage.setItem('pt_unlocked', '1')
      onUnlock()
    } else {
      setError(true)
      setShake(true)
      setValue('')
      setTimeout(() => setShake(false), 500)
    }
  }

  return (
    <div style={styles.wrap}>
      <div style={{ ...styles.card, animation: shake ? 'shake .4s ease' : 'none' }}>
        <div style={styles.logo}>✦</div>
        <h1 style={styles.title}>Price Tracker</h1>
        <p style={styles.sub}>Luxury · Saks · NM · Farfetch · NAP</p>
        <input
          style={{ ...styles.input, borderColor: error ? '#c00' : '#ddd' }}
          type="password"
          placeholder="Password"
          value={value}
          autoFocus
          onChange={e => { setValue(e.target.value); setError(false) }}
          onKeyDown={e => e.key === 'Enter' && attempt()}
        />
        {error && <p style={styles.err}>Incorrect password</p>}
        <button style={styles.btn} onClick={attempt}>Enter</button>
      </div>
      <style>{`
        @keyframes shake {
          0%,100%{ transform:translateX(0) }
          20%     { transform:translateX(-8px) }
          40%     { transform:translateX(8px) }
          60%     { transform:translateX(-6px) }
          80%     { transform:translateX(6px) }
        }
      `}</style>
    </div>
  )
}

const styles = {
  wrap:  { minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'#f7f7f5' },
  card:  { background:'#fff', border:'1px solid #eee', borderRadius:16, padding:'48px 40px', width:340, textAlign:'center' },
  logo:  { fontSize:28, marginBottom:16, color:'#111' },
  title: { fontSize:22, fontWeight:500, marginBottom:6, color:'#111' },
  sub:   { fontSize:13, color:'#999', marginBottom:32 },
  input: { width:'100%', padding:'12px 16px', fontSize:15, border:'1.5px solid #ddd', borderRadius:10,
           outline:'none', marginBottom:8, textAlign:'center', letterSpacing:4 },
  err:   { fontSize:12, color:'#c00', marginBottom:8 },
  btn:   { width:'100%', padding:'12px', background:'#111', color:'#fff', border:'none',
           borderRadius:10, fontSize:15, fontWeight:500, cursor:'pointer', marginTop:8 },
}
