import './SourceBadge.css'

export default function SourceBadge({ source }) {
  const title = source.title || source.source_title || 'Source'
  const year  = source.year  || ''
  const type  = source.type  || source.source_type || ''

  const typeColors = {
    book:       '#a8c4e0',
    paper:      '#d4a843',
    transcript: '#a8e0a8',
    essays:     '#c0a8e8',
    interview:  '#e0c0a8',
    letter:     '#e8a0a0',
    unknown:    '#888',
  }
  const color = typeColors[type] || typeColors.unknown

  return (
    <div
      className="source-badge"
      title={`${title} (${year})`}
      style={{
        background: color + '15',
        borderColor: color + '30',
        color: color,
      }}
    >
      <span className="source-badge-icon">📄</span>
      <span className="source-badge-text">
        {title.length > 30 ? title.slice(0, 28) + '…' : title}
        {year ? ` · ${year}` : ''}
      </span>
    </div>
  )
}
