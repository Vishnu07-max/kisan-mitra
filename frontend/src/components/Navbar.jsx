import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import LanguageSwitch from './LanguageSwitch'

export default function Navbar() {
  const { t } = useTranslation()

  return (
    <header className="sticky top-0 z-10 border-b border-cream-dark bg-cream/95 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold text-leaf-700">
          <span aria-hidden="true">🌾</span>
          {t('app.name')}
        </Link>

        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="hidden px-3 py-2 text-leaf-900 hover:text-leaf-600 sm:inline"
          >
            {t('nav.home')}
          </Link>
          <LanguageSwitch />
          <button
            disabled
            title={t('landing.comingSoon')}
            className="min-h-11 cursor-not-allowed rounded-lg bg-leaf-600 px-4 py-2 font-semibold text-white opacity-60"
          >
            {t('nav.login')}
          </button>
        </div>
      </nav>
    </header>
  )
}