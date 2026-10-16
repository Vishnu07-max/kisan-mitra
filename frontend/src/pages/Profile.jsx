import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import FormField from '../components/FormField'
import SelectField from '../components/SelectField'
import { useAuth } from '../context/AuthContext'
import { updateProfile } from '../services/auth'
import { getErrorInfo } from '../utils/errors'

export default function Profile() {
  const { t, i18n } = useTranslation()
  const { profile, setProfile } = useAuth()

  const [form, setForm] = useState({
    full_name: profile.full_name || '',
    preferred_language: profile.preferred_language || 'en',
    phone: profile.phone || '',
    state: profile.state || '',
    district: profile.district || '',
  })
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [saved, setSaved] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const onChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value })
    setSaved(false)
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    setErrors({})
    setFormError('')
    setSaved(false)
    setSubmitting(true)
    try {
      const languageChanged = form.preferred_language !== profile.preferred_language
      const updated = await updateProfile(form)
      setProfile(updated)
      if (languageChanged) i18n.changeLanguage(updated.preferred_language)
      setSaved(true)
    } catch (err) {
      const info = getErrorInfo(err)
      setErrors(info.fields)
      if (info.type === 'validation') setFormError(t('auth.errors.validation'))
      else if (info.type === 'network') setFormError(t('auth.errors.network'))
      else setFormError(t('profile.saveError'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto max-w-xl px-4 py-8">
      <h1 className="text-3xl font-bold text-leaf-900">{t('profile.title')}</h1>
      <p className="mt-1 text-leaf-900/70">{t('profile.subtitle')}</p>

      <form
        onSubmit={onSubmit}
        noValidate
        className="mt-6 space-y-4 rounded-xl border border-cream-dark bg-white p-5 shadow-sm"
      >
        <FormField id="username" label={t('profile.username')} value={profile.username} disabled readOnly />
        <FormField
          id="full_name"
          label={t('profile.fullName')}
          value={form.full_name}
          onChange={onChange}
          error={errors.full_name}
        />
        <SelectField
          id="preferred_language"
          label={t('profile.language')}
          value={form.preferred_language}
          onChange={onChange}
          error={errors.preferred_language}
          options={[
            { value: 'en', label: 'English' },
            { value: 'hi', label: 'हिन्दी' },
          ]}
        />
        <div>
          <FormField
            id="phone"
            type="tel"
            label={t('profile.phone')}
            value={form.phone}
            onChange={onChange}
            error={errors.phone}
          />
          <p className="mt-1 text-sm text-leaf-900/70">{t('profile.phoneHint')}</p>
        </div>
        <FormField id="state" label={t('profile.state')} value={form.state} onChange={onChange} error={errors.state} />
        <FormField
          id="district"
          label={t('profile.district')}
          value={form.district}
          onChange={onChange}
          error={errors.district}
        />

        {formError && (
          <p role="alert" className="rounded-lg bg-red-100 px-3 py-2 text-red-900">
            {formError}
          </p>
        )}
        {saved && (
          <p role="status" className="rounded-lg bg-leaf-100 px-3 py-2 text-leaf-900">
            {t('profile.saved')}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="min-h-12 w-full rounded-lg bg-leaf-600 px-4 py-3 font-semibold text-white hover:bg-leaf-700 disabled:opacity-60"
        >
          {submitting ? t('profile.saving') : t('profile.save')}
        </button>
      </form>
    </main>
  )
}