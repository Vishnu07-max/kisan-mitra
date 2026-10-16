import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import FormField from './FormField'
import SelectField from './SelectField'
import { createFarm, updateFarm } from '../services/farms'
import { getErrorInfo } from '../utils/errors'

const SOIL_TYPES = ['alluvial', 'black', 'red', 'laterite', 'sandy', 'loamy', 'clay', 'unknown']
const IRRIGATION_TYPES = ['rainfed', 'canal', 'tubewell', 'drip', 'sprinkler', 'other']

const toForm = (farm) => ({
  name: farm?.name ?? '',
  state: farm?.state ?? '',
  district: farm?.district ?? '',
  soil_type: farm?.soil_type ?? 'unknown',
  irrigation_type: farm?.irrigation_type ?? 'rainfed',
  area_acres: farm?.area_acres ?? '',
  latitude: farm?.latitude ?? '',
  longitude: farm?.longitude ?? '',
})

function validate(form, t) {
  const e = {}
  if (!form.name.trim()) e.name = t('auth.errors.required')
  if (!form.state.trim()) e.state = t('auth.errors.required')
  if (!form.district.trim()) e.district = t('auth.errors.required')

  if (form.area_acres !== '' && !(Number(form.area_acres) > 0)) {
    e.area_acres = t('farms.errors.areaInvalid')
  }

  const hasLat = form.latitude !== ''
  const hasLon = form.longitude !== ''
  if (hasLat !== hasLon) {
    e.latitude = t('farms.errors.coordsBoth')
  } else if (hasLat && hasLon) {
    const lat = Number(form.latitude)
    const lon = Number(form.longitude)
    if (Number.isNaN(lat) || lat < -90 || lat > 90) e.latitude = t('farms.errors.latInvalid')
    if (Number.isNaN(lon) || lon < -180 || lon > 180) e.longitude = t('farms.errors.lonInvalid')
  }
  return e
}

export default function FarmForm({ farm, onSaved, onCancel }) {
  const { t } = useTranslation()
  const [form, setForm] = useState(toForm(farm))
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    const found = validate(form, t)
    setErrors(found)
    setFormError('')
    if (Object.keys(found).length > 0) return

    const payload = {
      name: form.name.trim(),
      state: form.state.trim(),
      district: form.district.trim(),
      soil_type: form.soil_type,
      irrigation_type: form.irrigation_type,
      area_acres: form.area_acres === '' ? null : form.area_acres,
      latitude: form.latitude === '' ? null : form.latitude,
      longitude: form.longitude === '' ? null : form.longitude,
    }

    setSubmitting(true)
    try {
      const saved = farm ? await updateFarm(farm.id, payload) : await createFarm(payload)
      onSaved(saved)
    } catch (err) {
      const info = getErrorInfo(err)
      setErrors(info.fields)
      if (info.type === 'validation') setFormError(t('auth.errors.validation'))
      else if (info.type === 'network') setFormError(t('auth.errors.network'))
      else if (info.type === 'throttled') setFormError(t('auth.errors.throttled'))
      else setFormError(t('farms.saveError'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="rounded-xl border border-cream-dark bg-white p-5 shadow-sm"
    >
      <h2 className="mb-4 text-xl font-semibold text-leaf-700">
        {farm ? t('farms.editTitle') : t('farms.addTitle')}
      </h2>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField id="name" label={t('farms.fields.name')} value={form.name} onChange={onChange} error={errors.name} />
        <FormField id="state" label={t('farms.fields.state')} value={form.state} onChange={onChange} error={errors.state} />
        <FormField id="district" label={t('farms.fields.district')} value={form.district} onChange={onChange} error={errors.district} />
        <FormField
          id="area_acres"
          type="number"
          step="any"
          min="0"
          label={t('farms.fields.area')}
          value={form.area_acres}
          onChange={onChange}
          error={errors.area_acres}
        />
        <SelectField
          id="soil_type"
          label={t('farms.fields.soilType')}
          value={form.soil_type}
          onChange={onChange}
          error={errors.soil_type}
          options={SOIL_TYPES.map((v) => ({ value: v, label: t(`farms.soil.${v}`) }))}
        />
        <SelectField
          id="irrigation_type"
          label={t('farms.fields.irrigation')}
          value={form.irrigation_type}
          onChange={onChange}
          error={errors.irrigation_type}
          options={IRRIGATION_TYPES.map((v) => ({ value: v, label: t(`farms.irrigationTypes.${v}`) }))}
        />
        <FormField
          id="latitude"
          type="number"
          step="any"
          label={t('farms.fields.latitude')}
          value={form.latitude}
          onChange={onChange}
          error={errors.latitude}
        />
        <FormField
          id="longitude"
          type="number"
          step="any"
          label={t('farms.fields.longitude')}
          value={form.longitude}
          onChange={onChange}
          error={errors.longitude}
        />
      </div>
      <p className="mt-2 text-sm text-leaf-900/70">{t('farms.coordsHint')}</p>

      {(formError || errors.non_field_errors) && (
        <p role="alert" className="mt-4 rounded-lg bg-red-100 px-3 py-2 text-red-900">
          {errors.non_field_errors || formError}
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          type="submit"
          disabled={submitting}
          className="min-h-12 rounded-lg bg-leaf-600 px-6 py-3 font-semibold text-white hover:bg-leaf-700 disabled:opacity-60"
        >
          {submitting ? t('farms.saving') : t('farms.save')}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="min-h-12 rounded-lg border border-leaf-600 px-6 py-3 font-semibold text-leaf-700 hover:bg-leaf-50"
        >
          {t('farms.cancel')}
        </button>
      </div>
    </form>
  )
}