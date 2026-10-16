import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'

export default function Dashboard() {
  const { t } = useTranslation()
  const { profile } = useAuth()
  const name = profile.full_name || profile.username

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-3xl font-bold text-leaf-900">{t('dashboard.welcome', { name })}</h1>
      <p className="mt-1 text-leaf-900/70">{t('dashboard.subtitle')}</p>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-cream-dark bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-leaf-700">{t('dashboard.profileTitle')}</h2>
          <dl className="mt-3 space-y-1">
            <div className="flex gap-2">
              <dt className="font-medium">{t('dashboard.username')}:</dt>
              <dd>{profile.username}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="font-medium">{t('dashboard.language')}:</dt>
              <dd>{profile.preferred_language === 'hi' ? 'हिन्दी' : 'English'}</dd>
            </div>
          </dl>
        </section>

        <section className="rounded-xl border border-cream-dark bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-leaf-700">{t('dashboard.nextTitle')}</h2>
          <p className="mt-2 text-leaf-900/80">{t('dashboard.nextText')}</p>
        </section>
      </div>
    </main>
  )
}