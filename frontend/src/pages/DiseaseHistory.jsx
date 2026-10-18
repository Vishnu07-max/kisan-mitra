import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import AssessmentResult from '../components/AssessmentResult'
import AuthImage from '../components/AuthImage'
import { deleteAssessment, listAssessments } from '../services/disease'

export default function DiseaseHistory() {
  const { t, i18n } = useTranslation()
  const [page, setPage] = useState(1)
  const [data, setData] = useState({ count: 0, results: [], next: null, previous: null })
  const [status, setStatus] = useState('loading') // loading | ready | error
  const [message, setMessage] = useState('')

  const load = useCallback(async (p) => {
    setStatus('loading')
    try {
      const d = await listAssessments(p)
      if (d.results.length === 0 && p > 1) {
        setPage(p - 1)
        return
      }
      setData(d)
      setStatus('ready')
    } catch {
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    load(page)
  }, [page, load])

  const onDelete = async (id) => {
    if (!window.confirm(t('disease.deleteConfirm'))) return
    try {
      await deleteAssessment(id)
      setMessage('')
      load(page)
    } catch {
      setMessage(t('disease.deleteError'))
    }
  }

  const locale = i18n.language === 'hi' ? 'hi-IN' : 'en-IN'

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-leaf-900">{t('disease.historyTitle')}</h1>
          <p className="mt-1 text-leaf-900/70">{t('disease.historySubtitle')}</p>
        </div>
        <Link
          to="/crop-doctor"
          className="inline-flex min-h-11 items-center rounded-lg bg-leaf-600 px-4 py-2 font-semibold text-white hover:bg-leaf-700"
        >
          {t('disease.navLabel')}
        </Link>
      </div>

      {message && (
        <p role="alert" className="mt-4 rounded-lg bg-red-100 px-3 py-2 text-red-900">
          {message}
        </p>
      )}

      <div className="mt-6 space-y-4">
        {status === 'loading' && <p className="text-leaf-900/70">{t('common.loading')}</p>}

        {status === 'error' && (
          <div className="rounded-lg bg-red-100 px-4 py-3 text-red-900">
            {t('disease.historyError')}{' '}
            <button onClick={() => load(page)} className="font-semibold underline">
              {t('disease.retry')}
            </button>
          </div>
        )}

        {status === 'ready' && data.results.length === 0 && (
          <div className="rounded-xl border border-dashed border-leaf-500 bg-white p-8 text-center text-leaf-900/80">
            {t('disease.historyEmpty')}
          </div>
        )}

        {status === 'ready' &&
          data.results.map((a) => (
            <article key={a.id} className="flex gap-4 rounded-xl border border-cream-dark bg-white p-4 shadow-sm">
              <AuthImage url={a.image_url} alt="" className="h-24 w-24 shrink-0 rounded-lg object-cover" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-leaf-900/70">{new Date(a.created_at).toLocaleString(locale)}</p>
                <div className="mt-2">
                  <AssessmentResult assessment={a} compact />
                </div>
                <button
                  onClick={() => onDelete(a.id)}
                  className="mt-3 min-h-11 rounded-lg border border-red-600 px-4 py-2 font-semibold text-red-700 hover:bg-red-50"
                >
                  {t('disease.delete')}
                </button>
              </div>
            </article>
          ))}

        {status === 'ready' && (data.previous || data.next) && (
          <div className="flex items-center justify-between pt-2">
            <button
              disabled={!data.previous}
              onClick={() => setPage(page - 1)}
              className="min-h-11 rounded-lg border border-leaf-600 px-4 py-2 font-semibold text-leaf-700 disabled:opacity-40"
            >
              {t('disease.prev')}
            </button>
            <span className="text-leaf-900/70">{t('disease.page', { n: page })}</span>
            <button
              disabled={!data.next}
              onClick={() => setPage(page + 1)}
              className="min-h-11 rounded-lg border border-leaf-600 px-4 py-2 font-semibold text-leaf-700 disabled:opacity-40"
            >
              {t('disease.next')}
            </button>
          </div>
        )}
      </div>
    </main>
  )
}