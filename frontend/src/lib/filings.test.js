import assert from 'node:assert/strict'
import test from 'node:test'
import { api, evidenceText } from './api.js'

function response(payload) {
  return {
    ok: true,
    json: async () => payload,
  }
}

test('filing API paths encode ticker and accession safely', async () => {
  const calls = []
  const originalFetch = globalThis.fetch
  globalThis.fetch = async (path, options) => {
    calls.push({ path, options })
    return response({ ok: true })
  }
  try {
    await api.filings('BRK-B', 8)
    await api.filing('BRK-B', '0000000000-26-000001')
    await api.askFiling('BRK-B', '0000000000-26-000001', 'What changed?', 'zh')
  } finally {
    globalThis.fetch = originalFetch
  }

  assert.equal(calls[0].path, '/api/filings/BRK-B?limit=8')
  assert.equal(calls[1].path, '/api/filings/BRK-B/0000000000-26-000001')
  assert.equal(calls[2].options.method, 'POST')
  assert.deepEqual(JSON.parse(calls[2].options.body), {
    question: 'What changed?',
    lang: 'zh',
  })
})

test('filing answer evidence uses the shared claim unwrapping contract', () => {
  assert.equal(evidenceText({ claim: 'Grounded answer' }), 'Grounded answer')
})
