import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import api from '../services/api'

export default function HealthStatus() {
  const { t } = useTranslation()
  const [state, setState] = useState('loading') // loading | ok | error

  const check = useCallback(async () => {
    setState('loading')
    try {
      const res = await api.get('/health/')
      setState(res.data.status === 'ok' && res.data.database === 'ok' ? 'ok' : 'error')
    } catch {
      setState('error')
    }
  }, [])

  useEffect(() => {
    check()
  }, [check])

  const styles = {
    loading: 'bg-cream-dark text-leaf-900',
    ok: 'bg-leaf-100 text-leaf-900',
    error: 'bg-red-100 text-red-900',
  }

  return (
    <div className={`inline-flex items-center gap-3 rounded-lg px-4 py-2 text-sm ${styles[state]}`}>
      <span className="font-semibold">{t('status.title')}:</span>
      <span>{t(`status.${state === 'loading' ? 'checking' : state}`)}</span>
      {state === 'error' && (
        <button onClick={check} className="font-semibold underline">
          {t('status.retry')}
        </button>
      )}
    </div>
  )
}