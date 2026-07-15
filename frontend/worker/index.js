const TICKER_PATTERN = /^[A-Z0-9][A-Z0-9.-]{0,9}$/
const PERIODS = new Set(['1mo', '3mo', '6mo', '1y', '2y', '5y'])
const CACHE_TTL = 5 * 60 * 1000
const responseCache = new Map()

const FUNDAMENTAL_TYPES = [
  'trailingMarketCap',
  'trailingPeRatio',
  'trailingForwardPeRatio',
  'trailingPsRatio',
  'trailingFreeCashFlow',
  'trailingNetIncome',
  'trailingTotalRevenue',
  'trailingOperatingIncome',
  'quarterlyTotalRevenue',
  'quarterlyTotalDebt',
  'quarterlyStockholdersEquity',
  'quarterlyCurrentAssets',
  'quarterlyCurrentLiabilities',
  'annualCashDividendsPaid',
  'annualBasicAverageShares',
]

const COMPARE_METRICS = [
  ['market_cap', 'Market cap', true],
  ['trailing_pe', 'Trailing P/E', false],
  ['forward_pe', 'Forward P/E', false],
  ['price_to_sales', 'Price / Sales', false],
  ['revenue_growth', 'Revenue growth (YoY)', true],
  ['profit_margin', 'Net margin', true],
  ['operating_margin', 'Operating margin', true],
  ['debt_to_equity', 'Debt / Equity', false],
  ['free_cash_flow', 'Free cash flow', true],
  ['dividend_yield', 'Dividend yield', true],
  ['beta', 'Beta', null],
]

const DISCLAIMER =
  'FinSight explains evidence; it does not give investment advice. Data may be delayed or incomplete. Always do your own research.'

class ApiError extends Error {
  constructor(message, status = 502) {
    super(message)
    this.status = status
  }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': status === 200 ? 'public, max-age=60' : 'no-store',
    },
  })
}

export function normalizeTicker(value) {
  const ticker = String(value || '').trim().toUpperCase()
  if (!TICKER_PATTERN.test(ticker)) {
    throw new ApiError(
      'Use a valid ticker with up to 10 letters, numbers, periods, or hyphens',
      400,
    )
  }
  return ticker
}

function normalizeComparison(value) {
  const raw = String(value || '').split(',').map((ticker) => ticker.trim()).filter(Boolean)
  if (raw.length < 2) throw new ApiError('Provide at least 2 tickers', 400)
  if (raw.length > 5) throw new ApiError('Compare up to 5 tickers at a time', 400)
  const tickers = raw.map(normalizeTicker)
  if (new Set(tickers).size !== tickers.length) {
    throw new ApiError('Each comparison ticker must be unique', 400)
  }
  return tickers
}

function cached(key, loader) {
  const existing = responseCache.get(key)
  if (existing && existing.expiresAt > Date.now()) return existing.value
  const value = Promise.resolve(loader()).catch((error) => {
    responseCache.delete(key)
    throw error
  })
  responseCache.set(key, { expiresAt: Date.now() + CACHE_TTL, value })
  return value
}

async function yahooFetch(url, responseType = 'json') {
  const response = await fetch(url, {
    headers: {
      accept: responseType === 'json' ? 'application/json' : 'application/rss+xml,text/xml',
      'user-agent':
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/138 Safari/537.36',
    },
  })
  if (response.ok) {
    return responseType === 'json' ? response.json() : response.text()
  }

  // Yahoo often rate-limits cloud runtimes even for its public chart and
  // fundamentals responses. Jina Reader provides a read-only fetch fallback.
  if (responseType === 'json') {
    const source = new URL(url)
    const proxyUrl = `https://r.jina.ai/http://${source.host}${source.pathname}${source.search}`
    const proxyResponse = await fetch(proxyUrl, { headers: { accept: 'text/plain' } })
    if (proxyResponse.ok) {
      const body = await proxyResponse.text()
      const marker = 'Markdown Content:'
      const content = body.slice(body.indexOf(marker) + marker.length).trim()
      try {
        return JSON.parse(content)
      } catch {
        // Fall through to the provider error below.
      }
    }
  }

  throw new ApiError('Market data is temporarily unavailable. Please try again.')
}

async function getChart(ticker, period = '1y') {
  return cached(`chart:${ticker}:${period}`, async () => {
    const url =
      `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}` +
      `?range=${period}&interval=1d&events=div%2Csplits`
    const payload = await yahooFetch(url)
    const result = payload?.chart?.result?.[0]
    if (!result || payload?.chart?.error) {
      throw new ApiError(`No data found for ticker '${ticker}'`, 404)
    }
    return result
  })
}

async function getFundamentals(ticker) {
  return cached(`fundamentals:${ticker}`, async () => {
    const period2 = Math.floor(Date.now() / 1000) + 86400
    const period1 = period2 - 900 * 86400
    const url =
      'https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/' +
      `${encodeURIComponent(ticker)}?symbol=${encodeURIComponent(ticker)}` +
      `&type=${FUNDAMENTAL_TYPES.join(',')}&merge=false&period1=${period1}&period2=${period2}`
    const payload = await yahooFetch(url)
    return payload?.timeseries?.result || []
  })
}

function seriesFor(results, type) {
  const item = results.find((entry) => entry?.meta?.type?.includes(type))
  return (item?.[type] || []).filter((entry) => Number.isFinite(entry?.reportedValue?.raw))
}

function latestRaw(results, type) {
  const series = seriesFor(results, type)
  return series.at(-1)?.reportedValue?.raw ?? null
}

function ratio(numerator, denominator) {
  return Number.isFinite(numerator) && Number.isFinite(denominator) && denominator !== 0
    ? numerator / denominator
    : null
}

export function buildOverview(ticker, chart, fundamentals = []) {
  const meta = chart.meta || {}
  const price = Number.isFinite(meta.regularMarketPrice) ? meta.regularMarketPrice : null
  const previous = meta.previousClose ?? meta.chartPreviousClose
  const revenue = latestRaw(fundamentals, 'trailingTotalRevenue')
  const netIncome = latestRaw(fundamentals, 'trailingNetIncome')
  const operatingIncome = latestRaw(fundamentals, 'trailingOperatingIncome')
  const debt = latestRaw(fundamentals, 'quarterlyTotalDebt')
  const equity = latestRaw(fundamentals, 'quarterlyStockholdersEquity')
  const currentAssets = latestRaw(fundamentals, 'quarterlyCurrentAssets')
  const currentLiabilities = latestRaw(fundamentals, 'quarterlyCurrentLiabilities')
  const dividendsPaid = latestRaw(fundamentals, 'annualCashDividendsPaid')
  const averageShares = latestRaw(fundamentals, 'annualBasicAverageShares')
  const quarterlyRevenue = seriesFor(fundamentals, 'quarterlyTotalRevenue')
  const latestQuarter = quarterlyRevenue.at(-1)?.reportedValue?.raw
  const priorYearQuarter = quarterlyRevenue.at(-5)?.reportedValue?.raw
  const dividendPerShare = ratio(Math.abs(dividendsPaid), averageShares)

  return {
    ticker,
    name: meta.longName || meta.shortName || ticker,
    sector: null,
    industry: meta.fullExchangeName || meta.exchangeName || null,
    currency: meta.currency || null,
    price,
    change_percent: ratio(price != null && previous != null ? price - previous : null, previous) != null
      ? ratio(price - previous, previous) * 100
      : null,
    market_cap: latestRaw(fundamentals, 'trailingMarketCap'),
    trailing_pe: latestRaw(fundamentals, 'trailingPeRatio'),
    forward_pe: latestRaw(fundamentals, 'trailingForwardPeRatio'),
    price_to_sales: latestRaw(fundamentals, 'trailingPsRatio'),
    profit_margin: ratio(netIncome, revenue),
    operating_margin: ratio(operatingIncome, revenue),
    revenue_growth: ratio(
      latestQuarter != null && priorYearQuarter != null ? latestQuarter - priorYearQuarter : null,
      priorYearQuarter,
    ),
    earnings_growth: null,
    debt_to_equity: ratio(debt, equity) != null ? ratio(debt, equity) * 100 : null,
    current_ratio: ratio(currentAssets, currentLiabilities),
    free_cash_flow: latestRaw(fundamentals, 'trailingFreeCashFlow'),
    beta: null,
    dividend_yield: ratio(dividendPerShare, price),
    fifty_two_week_low: meta.fiftyTwoWeekLow ?? null,
    fifty_two_week_high: meta.fiftyTwoWeekHigh ?? null,
    analyst_target_mean: null,
    recommendation: null,
    summary: null,
  }
}

async function getOverview(ticker) {
  const [chart, fundamentalsResult] = await Promise.all([
    getChart(ticker, '5d'),
    getFundamentals(ticker).catch(() => []),
  ])
  return buildOverview(ticker, chart, fundamentalsResult)
}

function historyFromChart(ticker, period, chart) {
  const timestamps = chart.timestamp || []
  const closes = chart.indicators?.quote?.[0]?.close || []
  const points = timestamps.flatMap((timestamp, index) => {
    const close = closes[index]
    if (!Number.isFinite(close)) return []
    return [{ date: new Date(timestamp * 1000).toISOString().slice(0, 10), close: Math.round(close * 100) / 100 }]
  })
  if (points.length < 2) throw new ApiError(`No price history for '${ticker}'`, 404)
  return { ticker, period, points }
}

function fmtNumber(value) {
  if (!Number.isFinite(value)) return 'n/a'
  const absolute = Math.abs(value)
  if (absolute >= 1e12) return `${(value / 1e12).toFixed(2)}T`
  if (absolute >= 1e9) return `${(value / 1e9).toFixed(2)}B`
  if (absolute >= 1e6) return `${(value / 1e6).toFixed(2)}M`
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

function fmtPercent(value) {
  return Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : 'n/a'
}

export function buildInsights(metrics) {
  const insights = []
  const add = (kind, title, severity, explanation, evidence) => {
    insights.push({ kind, title, severity, explanation, evidence })
  }

  if (Number.isFinite(metrics.trailing_pe)) {
    if (metrics.trailing_pe > 40) {
      add('risk', 'Rich valuation', metrics.trailing_pe > 60 ? 'high' : 'medium',
        'The market is paying a high multiple of current earnings. If growth slows, high-multiple stocks tend to fall harder.',
        [{ metric: 'Trailing P/E', value: metrics.trailing_pe.toFixed(1), benchmark: 'Broad-market long-run average is roughly 15–20' }])
    } else if (metrics.trailing_pe < 12) {
      add('opportunity', 'Low earnings multiple', 'medium',
        'Shares trade cheaply relative to current earnings. That can signal value—or weaker future expectations.',
        [{ metric: 'Trailing P/E', value: metrics.trailing_pe.toFixed(1), benchmark: 'Broad-market long-run average is roughly 15–20' }])
    }
  }

  if (metrics.debt_to_equity > 150) {
    add('risk', 'High leverage', metrics.debt_to_equity > 300 ? 'high' : 'medium',
      'Debt is large relative to shareholder equity, which can magnify losses and refinancing risk.',
      [{ metric: 'Debt / Equity', value: `${metrics.debt_to_equity.toFixed(0)}%`, benchmark: 'Above ~150% is generally considered elevated' }])
  }
  if (Number.isFinite(metrics.current_ratio) && metrics.current_ratio < 1) {
    add('risk', 'Tight short-term liquidity', 'medium',
      'Current liabilities exceed current assets, so near-term obligations deserve closer attention.',
      [{ metric: 'Current ratio', value: metrics.current_ratio.toFixed(2), benchmark: 'Below 1.0 means near-term liabilities exceed current assets' }])
  }
  if (Number.isFinite(metrics.free_cash_flow) && metrics.free_cash_flow < 0) {
    add('risk', 'Negative free cash flow', 'high',
      'The business is consuming more cash than it generates.',
      [{ metric: 'Free cash flow (TTM)', value: fmtNumber(metrics.free_cash_flow), benchmark: 'Sustainable businesses generally generate positive free cash flow' }])
  } else if (metrics.free_cash_flow > 0 && metrics.market_cap > 0) {
    const fcfYield = metrics.free_cash_flow / metrics.market_cap
    if (fcfYield > 0.05) {
      add('opportunity', 'Strong cash generation', 'medium',
        'Free cash flow is high relative to the company valuation.',
        [{ metric: 'FCF yield', value: fmtPercent(fcfYield), benchmark: 'Above ~5% is considered strong' }])
    }
  }

  if (Number.isFinite(metrics.revenue_growth)) {
    if (metrics.revenue_growth > 0.15) {
      add('opportunity', 'Fast revenue growth', metrics.revenue_growth > 0.30 ? 'high' : 'medium',
        'Sales are expanding well above typical economy-level growth.',
        [{ metric: 'Revenue growth (YoY)', value: fmtPercent(metrics.revenue_growth), benchmark: 'Above ~15% is fast for an established company' }])
    } else if (metrics.revenue_growth < 0) {
      add('risk', 'Shrinking revenue', metrics.revenue_growth < -0.10 ? 'high' : 'medium',
        'Sales are declining year over year; check whether the cause is cyclical or structural.',
        [{ metric: 'Revenue growth (YoY)', value: fmtPercent(metrics.revenue_growth), benchmark: 'Negative growth means the top line is contracting' }])
    }
  }

  if (Number.isFinite(metrics.profit_margin)) {
    if (metrics.profit_margin > 0.20) {
      add('opportunity', 'High profitability', 'medium',
        'The company keeps a large share of revenue as profit, which can signal pricing power or scale.',
        [{ metric: 'Net profit margin', value: fmtPercent(metrics.profit_margin), benchmark: 'Above ~20% is high across most industries' }])
    } else if (metrics.profit_margin < 0) {
      add('risk', 'Unprofitable operations', 'medium',
        'The company currently loses money on a net basis.',
        [{ metric: 'Net profit margin', value: fmtPercent(metrics.profit_margin), benchmark: 'Negative margin means net losses' }])
    }
  }

  if (metrics.dividend_yield > 0.03) {
    add('opportunity', 'Meaningful dividend income', 'low',
      'The stock pays a substantial dividend relative to its price; verify that cash flow covers it.',
      [{ metric: 'Dividend yield', value: fmtPercent(metrics.dividend_yield), benchmark: 'Above ~3% is a meaningful income component' }])
  }

  const { price, fifty_two_week_low: low, fifty_two_week_high: high } = metrics
  if (price && low && high && high > low) {
    const position = (price - low) / (high - low)
    if (position > 0.95) {
      add('risk', 'Trading at 52-week highs', 'low',
        'The price sits at the top of its one-year range; momentum can continue, but recent support is lower.',
        [{ metric: 'Position in 52-week range', value: fmtPercent(position), benchmark: `Range ${low.toFixed(2)} – ${high.toFixed(2)}` }])
    } else if (position < 0.10) {
      add('opportunity', 'Near 52-week lows', 'low',
        'The price is near the bottom of its one-year range; investigate whether the market has overreacted.',
        [{ metric: 'Position in 52-week range', value: fmtPercent(position), benchmark: `Range ${low.toFixed(2)} – ${high.toFixed(2)}` }])
    }
  }

  const rank = { high: 0, medium: 1, low: 2 }
  return insights.sort((a, b) => rank[a.severity] - rank[b.severity] || a.kind.localeCompare(b.kind))
}

function buildComparison(overviews) {
  return COMPARE_METRICS.map(([metric, label, higherIsBetter]) => {
    const values = Object.fromEntries(overviews.map((overview) => [overview.ticker, overview[metric]]))
    const numeric = Object.entries(values).filter(([, value]) => Number.isFinite(value))
    let best = null
    if (higherIsBetter !== null && numeric.length >= 2) {
      best = numeric.reduce((winner, current) => {
        const preferable = higherIsBetter ? current[1] > winner[1] : current[1] < winner[1]
        return preferable ? current : winner
      })[0]
    }
    return { metric, label, values, best, higher_is_better: higherIsBetter }
  })
}

function decodeXml(value) {
  return String(value || '')
    .replace(/^<!\[CDATA\[|\]\]>$/g, '')
    .replaceAll('&amp;', '&')
    .replaceAll('&quot;', '"')
    .replaceAll('&#39;', "'")
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
}

function tagValue(xml, tag) {
  const match = xml.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i'))
  return decodeXml(match?.[1]?.trim())
}

async function getNews(ticker) {
  try {
    const xml = await cached(`news:${ticker}`, () => yahooFetch(
      `https://feeds.finance.yahoo.com/rss/2.0/headline?s=${encodeURIComponent(ticker)}&region=US&lang=en-US`,
      'text',
    ))
    const items = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/gi)].slice(0, 10).map((match) => {
      const item = match[1]
      const published = tagValue(item, 'pubDate')
      return {
        title: tagValue(item, 'title'),
        publisher: tagValue(item, 'source') || 'Yahoo Finance',
        link: tagValue(item, 'link') || null,
        published_at: published ? new Date(published).toISOString() : null,
      }
    }).filter((item) => item.title)
    return { ticker, items, ai_summary: null }
  } catch {
    return { ticker, items: [], ai_summary: null }
  }
}

async function handleApi(request) {
  const url = new URL(request.url)
  const path = url.pathname
  if (request.method !== 'GET') throw new ApiError('Method not allowed', 405)
  if (path === '/api/health') return json({ status: 'ok', ai_enabled: false, runtime: 'edge' })

  let match = path.match(/^\/api\/stocks\/([^/]+)\/history$/)
  if (match) {
    const ticker = normalizeTicker(decodeURIComponent(match[1]))
    const period = url.searchParams.get('period') || '6mo'
    if (!PERIODS.has(period)) throw new ApiError('Unsupported price-history period', 400)
    return json(historyFromChart(ticker, period, await getChart(ticker, period)))
  }

  match = path.match(/^\/api\/stocks\/([^/]+)$/)
  if (match) {
    const ticker = normalizeTicker(decodeURIComponent(match[1]))
    return json(await getOverview(ticker))
  }

  match = path.match(/^\/api\/analysis\/([^/]+)$/)
  if (match) {
    const ticker = normalizeTicker(decodeURIComponent(match[1]))
    const metrics = await getOverview(ticker)
    return json({ ticker, insights: buildInsights(metrics), ai_narrative: null, disclaimer: DISCLAIMER })
  }

  match = path.match(/^\/api\/news\/([^/]+)$/)
  if (match) {
    const ticker = normalizeTicker(decodeURIComponent(match[1]))
    return json(await getNews(ticker))
  }

  if (path === '/api/compare') {
    const tickers = normalizeComparison(url.searchParams.get('tickers'))
    const overviews = await Promise.all(tickers.map(getOverview))
    return json({ tickers, rows: buildComparison(overviews) })
  }

  throw new ApiError('API route not found', 404)
}

const worker = {
  async fetch(request, env) {
    const url = new URL(request.url)
    if (url.pathname.startsWith('/api/')) {
      try {
        return await handleApi(request)
      } catch (error) {
        const status = error instanceof ApiError ? error.status : 502
        const detail = error instanceof ApiError
          ? error.message
          : 'Market data is temporarily unavailable. Please try again.'
        return json({ detail }, status)
      }
    }

    if (!env?.ASSETS) return new Response('Static assets are not configured', { status: 503 })
    const asset = await env.ASSETS.fetch(request)
    if (asset.status !== 404) return asset
    return env.ASSETS.fetch(new Request(new URL('/index.html', request.url), request))
  },
}

export default worker
