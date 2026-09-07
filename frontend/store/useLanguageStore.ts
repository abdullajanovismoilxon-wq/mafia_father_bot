'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Language, translations } from '../lib/i18n';

interface LanguageState {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: keyof typeof translations['uz']) => string;
}

export const useLanguageStore = create<LanguageState>()(
  persist(
    (set, get) => ({
      language: 'uz',
      setLanguage: (lang: Language) => set({ language: lang }),
      t: (key: keyof typeof translations['uz']) => {
        const lang = get().language || 'uz';
        const dict = translations[lang] || translations.uz;
        return (dict as any)[key] || (translations.uz as any)[key] || key;
      },
    }),
    {
      name: 'mafia_language_storage',
    }
  )
);
