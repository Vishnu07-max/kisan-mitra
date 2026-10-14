import { useTranslation } from 'react-i18next'

export default function LanguageSwitch() {
  const { i18n } = useTranslation()
  const current = i18n.language

  const buttonClass = (lang) =>
    `px-3 py-2 text-sm font-semibold min-w-12 transition ${
      current === lang
        ? 'bg-leaf-600 text-white'
        : 'bg-white text-leaf-700 hover:bg-leaf-50'
    }`

  return (
    <div className="inline-flex overflow-hidden rounded-lg border border-leaf-600">
      <button className={buttonClass('en')} onClick={() => i18n.changeLanguage('en')}>
        EN
      </button>
      <button className={buttonClass('hi')} onClick={() => i18n.changeLanguage('hi')}>
        हिन्दी
      </button>
    </div>
  )
}