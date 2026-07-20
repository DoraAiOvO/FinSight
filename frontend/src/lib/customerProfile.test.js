import assert from 'node:assert/strict'
import test from 'node:test'
import {
  defaultProfile,
  profilePayload,
  toggleSelection,
} from './customerProfile.js'

test('default profile records every onboarding preference', () => {
  assert.deepEqual(defaultProfile('zh'), {
    experience_level: 'intermediate',
    research_horizon: 'one_to_three_years',
    priorities: ['growth'],
    risk_comfort: 'medium',
    preferred_report_depth: 'standard',
    preferred_language: 'zh',
    industries_of_interest: ['Technology'],
  })
})

test('profile payload excludes server metadata and copies arrays', () => {
  const stored = {
    ...defaultProfile('en'),
    customer_id: 'customer-id',
    created_at: '2026-07-20T00:00:00Z',
  }
  const payload = profilePayload(stored)

  assert.equal(Object.hasOwn(payload, 'customer_id'), false)
  assert.equal(Object.hasOwn(payload, 'created_at'), false)
  assert.notEqual(payload.priorities, stored.priorities)
  assert.notEqual(payload.industries_of_interest, stored.industries_of_interest)
})

test('multi-select toggles values without exceeding its limit', () => {
  assert.deepEqual(toggleSelection(['growth'], 'value', 2), ['growth', 'value'])
  assert.deepEqual(toggleSelection(['growth', 'value'], 'income', 2), ['growth', 'value'])
  assert.deepEqual(toggleSelection(['growth', 'value'], 'growth', 2), ['value'])
})
