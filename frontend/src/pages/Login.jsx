import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import FormField from '../components/FormField'
import { useAuth } from '../context/AuthContext'
import { getErrorInfo } from '../utils/errors'

export default function Login() {
  const { t } = useTranslation()
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const redirectTo = location.state?.from || '/dashboard'

  const [form, setForm] = useState({ username: '', password: '' })
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    const newErrors = {}
    if (!form.username.trim()) newErrors.username = t('auth.errors.required')
    if (!form.password) newErrors.password = t('auth.errors.required')
    setErrors(newErrors)
    setFormError('')
    if (Object.keys(newErrors).length > 0) return

    setSubmitting(true)
    try {
      await login(form.username.trim(), form.password)
      navigate(redirectTo, { replace: true })
    } catch (err) {
      setFormError(t(`auth.errors.${getErrorInfo(err).type}`))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-10">
      <div className="rounded-xl border border-cream-dark bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-leaf-900">{t('auth.loginTitle')}</h1>
        <p className="mt-1 text-leaf-900/70">{t('auth.loginSubtitle')}</p>

        <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
          <FormField
            id="username"
            label={t('auth.username')}
            value={form.username}
            onChange={onChange}
            error={errors.username}
            autoComplete="username"
          />
          <FormField
            id="password"
            type="password"
            label={t('auth.password')}
            value={form.password}
            onChange={onChange}
            error={errors.password}
            autoComplete="current-password"
          />

          {formError && (
            <p role="alert" className="rounded-lg bg-red-100 px-3 py-2 text-red-900">
              {formError}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="min-h-12 w-full rounded-lg bg-leaf-600 px-4 py-3 font-semibold text-white hover:bg-leaf-700 disabled:opacity-60"
          >
            {submitting ? t('auth.working') : t('auth.loginButton')}
          </button>
        </form>

        <p className="mt-5 text-center text-leaf-900/80">
          {t('auth.noAccount')}{' '}
          <Link to="/register" className="font-semibold text-leaf-700 underline">
            {t('nav.register')}
          </Link>
        </p>
      </div>
    </main>
  )
}