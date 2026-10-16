import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import FormField from '../components/FormField'
import { useAuth } from '../context/AuthContext'
import { getErrorInfo } from '../utils/errors'

export default function Register() {
  const { t, i18n } = useTranslation()
  const { register } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    username: '',
    password: '',
    full_name: '',
    preferred_language: i18n.language === 'hi' ? 'hi' : 'en',
  })
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    const newErrors = {}
    if (form.username.trim().length < 3) newErrors.username = t('auth.errors.usernameShort')
    if (form.password.length < 8) newErrors.password = t('auth.errors.passwordShort')
    setErrors(newErrors)
    setFormError('')
    if (Object.keys(newErrors).length > 0) return

    setSubmitting(true)
    try {
      await register({ ...form, username: form.username.trim() })
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const info = getErrorInfo(err)
      setErrors({ username: info.fields.username, password: info.fields.password })
      setFormError(t(`auth.errors.${info.type}`))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto max-w-md px-4 py-10">
      <div className="rounded-xl border border-cream-dark bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-leaf-900">{t('auth.registerTitle')}</h1>
        <p className="mt-1 text-leaf-900/70">{t('auth.registerSubtitle')}</p>

        <form onSubmit={onSubmit} noValidate className="mt-6 space-y-4">
          <FormField
            id="full_name"
            label={t('auth.fullName')}
            value={form.full_name}
            onChange={onChange}
            autoComplete="name"
          />
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
            autoComplete="new-password"
          />

          <div>
            <label htmlFor="preferred_language" className="mb-1 block font-medium text-leaf-900">
              {t('auth.language')}
            </label>
            <select
              id="preferred_language"
              name="preferred_language"
              value={form.preferred_language}
              onChange={onChange}
              className="min-h-12 w-full rounded-lg border border-cream-dark bg-white px-3 py-2"
            >
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
            </select>
          </div>

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
            {submitting ? t('auth.working') : t('auth.registerButton')}
          </button>
        </form>

        <p className="mt-5 text-center text-leaf-900/80">
          {t('auth.haveAccount')}{' '}
          <Link to="/login" className="font-semibold text-leaf-700 underline">
            {t('nav.login')}
          </Link>
        </p>
      </div>
    </main>
  )
}