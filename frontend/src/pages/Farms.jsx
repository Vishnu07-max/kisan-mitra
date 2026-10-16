import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import FarmForm from '../components/FarmForm'
import { deleteFarm, listFarms } from '../services/farms'

export default function Farms() {
  const { t } = useTranslation()
  const [farms, setFarms] = useState([])
  const [status, setStatus] = useState('loading') // loading | ready | error
  const [editing, setEditing] = useState(null) // null | 'new' | a farm object
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setStatus('loading')
    try {
      setFarms(await listFarms())
      setStatus('ready')
    } catch {
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const onSaved = () => {
    setEditing(null)
    setMessage('')
    load()
  }

  const onDelete = async (farm) => {
    if (!window.confirm(t('farms.deleteConfirm', { name: farm.name }))) return
    try {
      await deleteFarm(farm.id)
      setFarms((current) => current.filter((f) => f.id !== farm.id))
      setMessage('')
    } catch {
      setMessage(t('farms.deleteError'))
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold text-leaf-900">{t('farms.title')}</h1>
          <p className="mt-1 text-leaf-900/70">{t('farms.subtitle')}</p>
        </div>
        {editing === null && (
          <button
            onClick={() => setEditing('new')}
            className="min-h-12 rounded-lg bg-leaf-600 px-5 py-3 font-semibold text-white hover:bg-leaf-700"
          >
            + {t('farms.add')}
          </button>
        )}
      </div>

      {editing !== null && (
        <div className="mt-6">
          <FarmForm
            key={editing === 'new' ? 'new' : editing.id}
            farm={editing === 'new' ? null : editing}
            onSaved={onSaved}
            onCancel={() => setEditing(null)}
          />
        </div>
      )}

      {message && (
        <p role="alert" className="mt-4 rounded-lg bg-red-100 px-3 py-2 text-red-900">
          {message}
        </p>
      )}

      <div className="mt-6">
        {status === 'loading' && (
          <p className="text-leaf-900/70">{t('common.loading')}</p>
        )}

        {status === 'error' && (
          <div className="rounded-lg bg-red-100 px-4 py-3 text-red-900">
            {t('farms.loadError')}{' '}
            <button onClick={load} className="font-semibold underline">
              {t('farms.retry')}
            </button>
          </div>
        )}

        {status === 'ready' && farms.length === 0 && editing === null && (
          <div className="rounded-xl border border-dashed border-leaf-500 bg-white p-8 text-center">
            <div className="text-4xl" aria-hidden="true">🌱</div>
            <h2 className="mt-2 text-xl font-semibold text-leaf-700">{t('farms.emptyTitle')}</h2>
            <p className="mt-1 text-leaf-900/70">{t('farms.emptyText')}</p>
          </div>
        )}

        {status === 'ready' && farms.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {farms.map((farm) => (
              <article
                key={farm.id}
                className="rounded-xl border border-cream-dark bg-white p-5 shadow-sm"
              >
                <h3 className="text-lg font-semibold text-leaf-700">{farm.name}</h3>
                <p className="text-leaf-900/80">
                  {farm.district}, {farm.state}
                </p>
                <dl className="mt-3 space-y-1 text-sm">
                  <div className="flex gap-2">
                    <dt className="font-medium">{t('farms.fields.soilType')}:</dt>
                    <dd>{t(`farms.soil.${farm.soil_type}`)}</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="font-medium">{t('farms.fields.irrigation')}:</dt>
                    <dd>{t(`farms.irrigationTypes.${farm.irrigation_type}`)}</dd>
                  </div>
                  {farm.area_acres && (
                    <div className="flex gap-2">
                      <dt className="font-medium">{t('farms.fields.area')}:</dt>
                      <dd>
                        {farm.area_acres} {t('farms.acres')}
                      </dd>
                    </div>
                  )}
                </dl>
                <div className="mt-4 flex gap-3">
                  <button
                    onClick={() => setEditing(farm)}
                    className="min-h-11 rounded-lg border border-leaf-600 px-4 py-2 font-semibold text-leaf-700 hover:bg-leaf-50"
                  >
                    {t('farms.edit')}
                  </button>
                  <button
                    onClick={() => onDelete(farm)}
                    className="min-h-11 rounded-lg border border-red-600 px-4 py-2 font-semibold text-red-700 hover:bg-red-50"
                  >
                    {t('farms.delete')}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}