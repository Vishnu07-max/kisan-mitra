import { useTranslation } from 'react-i18next'
import HealthStatus from '../components/HealthStatus'

const features = [
  { key: 'disease', icon: '🍃' },
  { key: 'crop', icon: '🌱' },
  { key: 'weather', icon: '⛅' },
  { key: 'market', icon: '📊' },
  { key: 'assistant', icon: '💬' },
]

export default function Landing() {
  const { t } = useTranslation()

  return (
    <main>
      <section className="bg-leaf-50">
        <div className="mx-auto max-w-6xl px-4 py-14 sm:py-20">
          <p className="mb-3 font-semibold text-leaf-600">{t('app.tagline')}</p>
          <h1 className="max-w-2xl text-3xl font-bold leading-tight text-leaf-900 sm:text-5xl">
            {t('landing.heroTitle')}
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-leaf-900/80">{t('landing.heroText')}</p>
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button
              disabled
              className="min-h-12 cursor-not-allowed rounded-lg bg-leaf-600 px-6 py-3 text-lg font-semibold text-white opacity-60"
            >
              {t('landing.getStarted')}
            </button>
            <HealthStatus />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <h2 className="mb-6 text-2xl font-bold text-leaf-900">{t('landing.featuresTitle')}</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <article
              key={f.key}
              className="rounded-xl border border-cream-dark bg-white p-5 shadow-sm"
            >
              <div className="mb-3 text-3xl" aria-hidden="true">{f.icon}</div>
              <h3 className="text-lg font-semibold text-leaf-700">{t(`features.${f.key}.title`)}</h3>
              <p className="mt-1 text-leaf-900/80">{t(`features.${f.key}.desc`)}</p>
              <span className="mt-3 inline-block rounded-full bg-cream-dark px-3 py-1 text-xs font-semibold text-soil">
                {t('landing.comingSoon')}
              </span>
            </article>
          ))}
        </div>
      </section>

      <footer className="border-t border-cream-dark py-6 text-center text-sm text-leaf-900/70">
        {t('landing.footer')}
      </footer>
    </main>
  )
}