import assert from 'node:assert/strict'
import test from 'node:test'
import {
  readStoredLanguage,
  resolveLanguage,
  storeLanguage,
} from './language.js'

test('language priority is profile, storage, browser, then English', () => {
  assert.equal(resolveLanguage({
    profileLanguage: 'fr',
    storedLanguage: 'es',
    browserLanguages: ['zh-CN'],
  }), 'fr')
  assert.equal(resolveLanguage({
    storedLanguage: 'es',
    browserLanguages: ['zh-CN'],
  }), 'es')
  assert.equal(resolveLanguage({ browserLanguages: ['de-DE', 'zh-CN'] }), 'zh')
  assert.equal(resolveLanguage({ browserLanguages: ['de-DE'] }), 'en')
})

test('stored language can be restored on refresh', () => {
  const values = new Map()
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  }

  assert.equal(storeLanguage(storage, 'zh'), true)
  assert.equal(readStoredLanguage(storage), 'zh')
  assert.equal(resolveLanguage({
    storedLanguage: readStoredLanguage(storage),
    browserLanguages: ['en-US'],
  }), 'zh')
})
