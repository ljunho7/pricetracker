import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const RETAILER_LABELS = ['Neiman Marcus', 'Saks', 'Farfetch', 'Net-a-Porter']
const COLORS          = ['#8B6F47', '#1a1a2e', '#555', '#c8a882']

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background:'#fff', border:'1px solid #eee', borderRadius:8,
                  padding:'10px 14px', fontSize:13, boxShadow:'0 2px 12px rgba(0,0,0,.08)' }}>
      <p style={{ fontWeight:500, marginBottom:6, color:'#111' }}>{formatDate(label)}</p>
      {payload.map(p => p.value && (
        <p key={p.name} style={{ color:p.color, margin:'2px 0' }}>
          {p.name}: <strong>${p.value.toLocaleString()}</strong>
        </p>
      ))}
    </div>
  )
}

export default function PriceChart({ history, alertBelow }) {
  if (!history?.length) return (
    <div style={styles.empty}>No price history yet — check back after the first daily run.</div>
  )

  // Filter out dates where ALL retailers are null
  const filtered = history.filter(h =>
    RETAILER_LABELS.some(r => h[r] !== null && h[r] !== undefined)
  )

  // Y-axis domain with padding
  const allPrices = filtered.flatMap(h => RETAILER_LABELS.map(r => h[r]).filter(Boolean))
  const minP = allPrices.length ? Math.min(...allPrices) : 0
  const maxP = allPrices.length ? Math.max(...allPrices) : 1000
  const pad  = (maxP - minP) * 0.15 || 100
  const yMin = Math.floor((minP - pad) / 50) * 50
  const yMax = Math.ceil((maxP + pad) / 50) * 50

  return (
    <div style={styles.wrap}>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={filtered} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fontSize: 11, fill: '#999' }}
            tickLine={false}
            axisLine={{ stroke: '#eee' }}
          />
          <YAxis
            domain={[yMin, yMax]}
            tickFormatter={v => `$${v.toLocaleString()}`}
            tick={{ fontSize: 11, fill: '#999' }}
            tickLine={false}
            axisLine={false}
            width={72}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={7}
            wrapperStyle={{ fontSize: 12, paddingTop: 12 }}
          />
          {RETAILER_LABELS.map((r, i) => (
            <Line
              key={r}
              type="monotone"
              dataKey={r}
              stroke={COLORS[i]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls={false}
            />
          ))}
          {/* Alert threshold line */}
          {alertBelow && (
            <Line
              dataKey={() => alertBelow}
              stroke="#c00"
              strokeDasharray="4 4"
              strokeWidth={1}
              dot={false}
              name={`Alert $${alertBelow}`}
              legendType="none"
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

const styles = {
  wrap:  { width:'100%' },
  empty: { padding:'40px 0', textAlign:'center', color:'#bbb', fontSize:14 },
}
