export const EXPERIENCE_OPTIONS = ['beginner', 'intermediate', 'advanced']
export const HORIZON_OPTIONS = ['short_term', 'one_to_three_years', 'five_plus_years']
export const PRIORITY_OPTIONS = ['growth', 'stability', 'income', 'value', 'innovation']
export const RISK_OPTIONS = ['low', 'medium', 'high']
export const REPORT_DEPTH_OPTIONS = ['quick', 'standard', 'deep']

export const INDUSTRY_OPTIONS = [
  'Technology',
  'Financial Services',
  'Healthcare',
  'Consumer Cyclical',
  'Industrials',
  'Energy',
  'Real Estate',
  'Communication Services',
  'Utilities',
  'Basic Materials',
]

export function defaultProfile(language = 'en') {
  return {
    experience_level: 'intermediate',
    research_horizon: 'one_to_three_years',
    priorities: ['growth'],
    risk_comfort: 'medium',
    preferred_report_depth: 'standard',
    preferred_language: language,
    industries_of_interest: ['Technology'],
  }
}

export function profilePayload(profile) {
  return {
    experience_level: profile.experience_level,
    research_horizon: profile.research_horizon,
    priorities: [...profile.priorities],
    risk_comfort: profile.risk_comfort,
    preferred_report_depth: profile.preferred_report_depth,
    preferred_language: profile.preferred_language,
    industries_of_interest: [...profile.industries_of_interest],
  }
}

export function toggleSelection(values, value, maximum) {
  if (values.includes(value)) return values.filter((current) => current !== value)
  if (values.length >= maximum) return values
  return [...values, value]
}
