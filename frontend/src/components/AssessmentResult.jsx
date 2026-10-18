import { useTranslation } from 'react-i18next'

export default function AssessmentResult({
  assessment: a,
  supportedCrops = [],
  experimentalCrops = [],
  compact = false,
}) {
  const { t } = useTranslation()
  const cropName = (name) => t(`disease.crops.${name}`, { defaultValue: name })

  if (a.status === 'no_match') {
    return (
      <div className="rounded-xl border border-amber-300 bg-amber-50 p-5">
        <h2 className="text-xl font-semibold text-amber-900">{t('disease.noMatchTitle')}</h2>
        {!compact && (
          <>
            <p className="mt-2 text-amber-900">{t('disease.noMatchText')}</p>
            <p className="mt-1 text-sm text-amber-900/80">{t('disease.noMatchNote')}</p>

            <h3 className="mt-4 font-semibold text-leaf-900">{t('disease.tipsTitle')}</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-leaf-900">
              {[1, 2, 3, 4].map((n) => (
                <li key={n}>{t(`disease.tip${n}`)}</li>
              ))}
            </ul>

            {supportedCrops.length > 0 && (
              <>
                <h3 className="mt-4 font-semibold text-leaf-900">{t('disease.supportedTitle')}</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {supportedCrops.map((c) => (
                    <span key={c} className="rounded-full bg-white px-3 py-1 text-sm text-leaf-900 shadow-sm">
                      {cropName(c)}
                      {experimentalCrops.includes(c) && (
                        <span className="ml-1 text-xs text-soil">({t('disease.experimental')})</span>
                      )}
                    </span>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>
    )
  }

  const noDisease = a.outcome === 'no_disease_detected'
  const percent = Math.round(a.confidence * 100)

  return (
    <div className="rounded-xl border border-cream-dark bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold text-leaf-700">
          {noDisease ? t('disease.noDisease') : t('disease.possible', { condition: a.condition })}
        </h2>
        {a.experimental && (
          <span className="rounded-full bg-cream-dark px-3 py-1 text-xs font-semibold text-soil">
            {t('disease.experimental')}
          </span>
        )}
      </div>
      <p className="mt-1 text-leaf-900">{t('disease.cropLine', { crop: cropName(a.crop) })}</p>
      <p className="mt-1 font-medium text-leaf-900">{t('disease.confidence', { percent })}</p>

      {!compact && (
        <>
          <p className="mt-1 text-sm text-leaf-900/70">{t('disease.confidenceNote')}</p>
          {noDisease && (
            <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {t('disease.noDiseaseNote')}
            </p>
          )}
          {a.experimental && (
            <p className="mt-3 rounded-lg bg-cream-dark px-3 py-2 text-sm text-leaf-900">
              {t('disease.experimentalNote')}
            </p>
          )}
        </>
      )}
    </div>
  )
}