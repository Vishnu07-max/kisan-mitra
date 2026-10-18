import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import AssessmentResult from '../components/AssessmentResult'
import SelectField from '../components/SelectField'
import { predict } from '../services/disease'
import { listFarms } from '../services/farms'

const MAX_MB = 8 // keep in step with DISEASE_MAX_UPLOAD_MB on the server (the server decides)
const ALLOWED = ['image/jpeg', 'image/png']

export default function CropDoctor() {
  const { t } = useTranslation()
  const cameraRef = useRef(null)
  const galleryRef = useRef(null)
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [farms, setFarms] = useState([])
  const [farmId, setFarmId] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => {
    listFarms().then(setFarms).catch(() => {})
  }, [])

  // Release the preview's memory when it changes or the page closes
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview])

  const pick = (e) => {
    const chosen = e.target.files?.[0]
    e.target.value = ''
    if (!chosen) return
    setError('')
    setResult(null)
    if (chosen.type && !ALLOWED.includes(chosen.type)) {
      setError(t('disease.errors.wrongType'))
      return
    }
    if (chosen.size > MAX_MB * 1024 * 1024) {
      setError(t('disease.errors.tooBig', { mb: MAX_MB }))
      return
    }
    setFile(chosen)
    setPreview(URL.createObjectURL(chosen))
  }

  const reset = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    setError('')
  }

  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      setResult(await predict(file, farmId))
    } catch (err) {
      const status = err.response?.status
      if (err.code === 'ECONNABORTED') setError(t('disease.errors.timeout'))
      else if (!err.response) setError(t('auth.errors.network'))
      else if (status === 503) setError(t('disease.errors.unavailable'))
      else if (status === 429) setError(t('auth.errors.throttled'))
      else if (status === 400) {
        const detail = err.response.data?.error?.details?.image
        setError(t('disease.errors.invalid') + (detail ? ` (${[].concat(detail).join(' ')})` : ''))
      } else setError(t('auth.errors.server'))
    } finally {
      setBusy(false)
    }
  }

  const buttonBase = 'min-h-12 rounded-lg px-5 py-3 font-semibold'

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-leaf-900">{t('disease.title')}</h1>
          <p className="mt-1 text-leaf-900/70">{t('disease.subtitle')}</p>
        </div>
        <Link
          to="/crop-doctor/history"
          className="inline-flex min-h-11 items-center rounded-lg border border-leaf-600 px-4 py-2 font-semibold text-leaf-700 hover:bg-leaf-50"
        >
          {t('disease.viewHistory')}
        </Link>
      </div>

      <p className="mt-4 rounded-lg bg-cream-dark px-4 py-3 text-sm text-leaf-900">{t('disease.disclaimer')}</p>

      {error && (
        <p role="alert" className="mt-4 rounded-lg bg-red-100 px-3 py-2 text-red-900">
          {error}
        </p>
      )}

      {!preview && (
        <section className="mt-6 rounded-xl border border-cream-dark bg-white p-5 shadow-sm">
          <div className="flex flex-wrap gap-3">
            <button onClick={() => cameraRef.current.click()} className={`${buttonBase} bg-leaf-600 text-white hover:bg-leaf-700`}>
              {t('disease.takePhoto')}
            </button>
            <button
              onClick={() => galleryRef.current.click()}
              className={`${buttonBase} border border-leaf-600 text-leaf-700 hover:bg-leaf-50`}
            >
              {t('disease.chooseFile')}
            </button>
          </div>
          <input ref={cameraRef} type="file" accept="image/jpeg,image/png" capture="environment" onChange={pick} className="hidden" />
          <input ref={galleryRef} type="file" accept="image/jpeg,image/png" onChange={pick} className="hidden" />

          <h2 className="mt-6 font-semibold text-leaf-900">{t('disease.tipsTitle')}</h2>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-leaf-900">
            {[1, 2, 3, 4].map((n) => (
              <li key={n}>{t(`disease.tip${n}`)}</li>
            ))}
          </ul>
        </section>
      )}

      {preview && (
        <section className="mt-6 space-y-4">
          <img src={preview} alt="" className="max-h-96 w-full rounded-xl border border-cream-dark bg-white object-contain" />

          {!result && (
            <div className="rounded-xl border border-cream-dark bg-white p-5 shadow-sm">
              {farms.length > 0 && (
                <SelectField
                  id="farm"
                  label={t('disease.farmLabel')}
                  value={farmId}
                  onChange={(e) => setFarmId(e.target.value)}
                  options={[
                    { value: '', label: t('disease.noFarm') },
                    ...farms.map((f) => ({ value: String(f.id), label: f.name })),
                  ]}
                />
              )}
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={submit}
                  disabled={busy}
                  className={`${buttonBase} bg-leaf-600 text-white hover:bg-leaf-700 disabled:opacity-60`}
                >
                  {busy ? t('disease.analyzing') : t('disease.analyze')}
                </button>
                <button
                  onClick={reset}
                  disabled={busy}
                  className={`${buttonBase} border border-leaf-600 text-leaf-700 hover:bg-leaf-50 disabled:opacity-60`}
                >
                  {t('disease.chooseFile')}
                </button>
              </div>
            </div>
          )}

          {result && (
            <>
              <AssessmentResult
                assessment={result}
                supportedCrops={result.supported_crops}
                experimentalCrops={result.experimental_crops}
              />
              <button onClick={reset} className={`${buttonBase} bg-leaf-600 text-white hover:bg-leaf-700`}>
                {t('disease.newCheck')}
              </button>
            </>
          )}
        </section>
      )}
    </main>
  )
}