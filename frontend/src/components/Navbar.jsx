import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import LanguageSwitch from './LanguageSwitch'

export default function Navbar() {
  const { t } = useTranslation()
  const { isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  const onLogout = async () => {
    await logout()
    navigate('/')
  }

  const linkClass = 'px-2 py-2 text-sm text-leaf-900 hover:text-leaf-600 sm:px-3 sm:text-base'
  const primaryButton =
    'inline-flex min-h-11 items-center rounded-lg bg-leaf-600 px-4 py-2 font-semibold text-white hover:bg-leaf-700'

  return (
    <header className="sticky top-0 z-10 border-b border-cream-dark bg-cream/95 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-3">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold text-leaf-700">
          <span aria-hidden="true">🌾</span>
          {t('app.name')}
        </Link>

        <div className="flex flex-wrap items-center gap-1 sm:gap-3">
          {isAuthenticated && (
            <>
              <Link to="/dashboard" className={linkClass}>
                {t('nav.dashboard')}
              </Link>
              <Link to="/farms" className={linkClass}>
                {t('farms.navLabel')}
              </Link>
              <Link to="/profile" className={linkClass}>
                {t('profile.navLabel')}
              </Link>
            </>
          )}
          <LanguageSwitch />
          {isAuthenticated ? (
            <button onClick={onLogout} className={primaryButton}>
              {t('nav.logout')}
            </button>
          ) : (
            <>
              <Link to="/login" className={linkClass}>
                {t('nav.login')}
              </Link>
              <Link to="/register" className={primaryButton}>
                {t('nav.register')}
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  )
}