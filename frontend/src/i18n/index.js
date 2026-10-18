import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './en.json'
import hi from './hi.json'
import enFarms from './en.farms.json'
import hiFarms from './hi.farms.json'
import enDisease from './en.disease.json'
import hiDisease from './hi.disease.json'

const savedLang = localStorage.getItem('lang') || 'en'

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: { ...en, ...enFarms, ...enDisease } },
    hi: { translation: { ...hi, ...hiFarms, ...hiDisease } },
  },
  lng: savedLang,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

document.documentElement.lang = savedLang

i18n.on('languageChanged', (lng) => {
  localStorage.setItem('lang', lng)
  document.documentElement.lang = lng
})

export default i18n