import { useEffect, useState } from 'react'
import { fetchImageBlob } from '../services/disease'

export default function AuthImage({ url, alt, className = '' }) {
  const [src, setSrc] = useState(null)

  useEffect(() => {
    let objectUrl = null
    let cancelled = false
    fetchImageBlob(url)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setSrc(objectUrl)
      })
      .catch(() => {})
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url])

  if (!src) return <div className={`animate-pulse bg-cream-dark ${className}`} aria-hidden="true" />
  return <img src={src} alt={alt} className={className} />
}