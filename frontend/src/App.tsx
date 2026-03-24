import { useState, useEffect, useCallback, useRef } from 'react'

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '')

interface ImageInfo {
  filename: string
  timestamp: string | null
  size: number
}

interface ImageResponse {
  images: ImageInfo[]
  total: number
  page: number
  per_page: number
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return 'Unknown'
  const d = new Date(ts)
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDate(ts: string | null): string {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function App() {
  const [images, setImages] = useState<ImageInfo[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [perPage] = useState(50)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [capturing, setCapturing] = useState(false)
  const [loading, setLoading] = useState(true)
  const viewerRef = useRef<HTMLDivElement>(null)

  const fetchImages = useCallback(async (p: number) => {
    setLoading(true)
    try {
      const res = await fetch(`${BASE}/api/images?page=${p}&per_page=${perPage}`)
      const data: ImageResponse = await res.json()
      setImages(data.images)
      setTotal(data.total)
      setPage(data.page)
    } catch (err) {
      console.error('Failed to fetch images:', err)
    } finally {
      setLoading(false)
    }
  }, [perPage])

  useEffect(() => {
    fetchImages(1)
  }, [fetchImages])

  const handleCapture = async () => {
    setCapturing(true)
    try {
      const res = await fetch(`${BASE}/api/capture`, { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        // Refresh to show new image
        await fetchImages(1)
        setPage(1)
      } else {
        alert('Capture failed: ' + (data.error || 'Unknown error'))
      }
    } catch (err) {
      alert('Capture failed: network error')
    } finally {
      setCapturing(false)
    }
  }

  const totalPages = Math.ceil(total / perPage)

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (selectedIndex === null) return
    if (e.key === 'Escape') {
      setSelectedIndex(null)
    } else if (e.key === 'ArrowLeft' && selectedIndex > 0) {
      setSelectedIndex(selectedIndex - 1)
    } else if (e.key === 'ArrowRight' && selectedIndex < images.length - 1) {
      setSelectedIndex(selectedIndex + 1)
    }
  }, [selectedIndex, images.length])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  // Group images by date
  const groupedImages: { date: string; items: (ImageInfo & { globalIndex: number })[] }[] = []
  let currentDate = ''
  for (let i = 0; i < images.length; i++) {
    const img = images[i]
    const date = formatDate(img.timestamp)
    if (date !== currentDate) {
      currentDate = date
      groupedImages.push({ date, items: [] })
    }
    groupedImages[groupedImages.length - 1].items.push({ ...img, globalIndex: i })
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '24px',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 600 }}>Pioreactor Camera</h1>
          <p style={{ color: '#8b949e', fontSize: '14px', marginTop: '4px' }}>
            {total.toLocaleString()} images captured
          </p>
        </div>
        <button
          onClick={handleCapture}
          disabled={capturing}
          style={{
            padding: '10px 20px',
            fontSize: '14px',
            fontWeight: 600,
            background: capturing ? '#333' : '#238636',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: capturing ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          {capturing ? 'Capturing...' : 'Take Photo'}
        </button>
      </div>

      {/* Image Grid */}
      {loading && images.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#8b949e' }}>
          Loading images...
        </div>
      ) : images.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px', color: '#8b949e' }}>
          No images yet. Click "Take Photo" to capture one.
        </div>
      ) : (
        <>
          {groupedImages.map((group) => (
            <div key={group.date} style={{ marginBottom: '32px' }}>
              <h2 style={{
                fontSize: '16px',
                fontWeight: 600,
                color: '#8b949e',
                marginBottom: '12px',
                borderBottom: '1px solid #21262d',
                paddingBottom: '8px',
              }}>
                {group.date || 'Unknown Date'}
              </h2>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: '8px',
              }}>
                {group.items.map((img) => (
                  <div
                    key={img.filename}
                    onClick={() => setSelectedIndex(img.globalIndex)}
                    style={{
                      cursor: 'pointer',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      background: '#161b22',
                      border: '1px solid #21262d',
                      transition: 'border-color 0.15s',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#388bfd')}
                    onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#21262d')}
                  >
                    <img
                      src={`${BASE}/images/${img.filename}`}
                      alt={img.filename}
                      loading="lazy"
                      style={{
                        width: '100%',
                        aspectRatio: '4/3',
                        objectFit: 'cover',
                        display: 'block',
                      }}
                    />
                    <div style={{ padding: '6px 8px' }}>
                      <div style={{ fontSize: '12px', color: '#8b949e' }}>
                        {img.timestamp
                          ? new Date(img.timestamp).toLocaleTimeString(undefined, {
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : 'Unknown time'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              gap: '8px',
              marginTop: '24px',
              paddingBottom: '24px',
            }}>
              <button
                onClick={() => fetchImages(page - 1)}
                disabled={page <= 1}
                style={{
                  padding: '8px 16px',
                  background: page <= 1 ? '#161b22' : '#21262d',
                  color: page <= 1 ? '#484f58' : '#c9d1d9',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  cursor: page <= 1 ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                }}
              >
                Previous
              </button>
              <span style={{ color: '#8b949e', fontSize: '14px' }}>
                Page {page} of {totalPages}
              </span>
              <button
                onClick={() => fetchImages(page + 1)}
                disabled={page >= totalPages}
                style={{
                  padding: '8px 16px',
                  background: page >= totalPages ? '#161b22' : '#21262d',
                  color: page >= totalPages ? '#484f58' : '#c9d1d9',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                  fontSize: '14px',
                }}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* Lightbox */}
      {selectedIndex !== null && images[selectedIndex] && (
        <div
          ref={viewerRef}
          onClick={(e) => {
            if (e.target === e.currentTarget) setSelectedIndex(null)
          }}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.9)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          {/* Close button */}
          <button
            onClick={() => setSelectedIndex(null)}
            style={{
              position: 'absolute',
              top: '16px',
              right: '16px',
              background: 'none',
              border: 'none',
              color: '#8b949e',
              fontSize: '28px',
              cursor: 'pointer',
              padding: '4px 8px',
              lineHeight: 1,
            }}
          >
            x
          </button>

          {/* Navigation arrows */}
          {selectedIndex > 0 && (
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedIndex(selectedIndex - 1) }}
              style={{
                position: 'absolute',
                left: '16px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'rgba(33,38,45,0.8)',
                border: '1px solid #30363d',
                color: '#c9d1d9',
                fontSize: '24px',
                cursor: 'pointer',
                padding: '12px 16px',
                borderRadius: '6px',
              }}
            >
              &lt;
            </button>
          )}
          {selectedIndex < images.length - 1 && (
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedIndex(selectedIndex + 1) }}
              style={{
                position: 'absolute',
                right: '16px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'rgba(33,38,45,0.8)',
                border: '1px solid #30363d',
                color: '#c9d1d9',
                fontSize: '24px',
                cursor: 'pointer',
                padding: '12px 16px',
                borderRadius: '6px',
              }}
            >
              &gt;
            </button>
          )}

          {/* Image */}
          <img
            src={`${BASE}/images/${images[selectedIndex].filename}`}
            alt={images[selectedIndex].filename}
            style={{
              maxWidth: '90vw',
              maxHeight: '80vh',
              objectFit: 'contain',
              borderRadius: '4px',
            }}
          />

          {/* Info bar */}
          <div style={{
            marginTop: '12px',
            textAlign: 'center',
            color: '#8b949e',
            fontSize: '14px',
          }}>
            <div style={{ fontWeight: 600, color: '#c9d1d9' }}>
              {formatTimestamp(images[selectedIndex].timestamp)}
            </div>
            <div style={{ marginTop: '4px' }}>
              {formatSize(images[selectedIndex].size)} &middot; {images[selectedIndex].filename}
            </div>
            <div style={{ marginTop: '4px', fontSize: '12px' }}>
              {selectedIndex + 1 + (page - 1) * perPage} of {total}
              {' '}&middot; Use arrow keys to navigate, Esc to close
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
