import { displayDataPoint } from './api.js'

const UI = {
  en: {
    open: 'Open FinSight Assistant', close: 'Close assistant', title: 'FinSight Assistant',
    subtitle: 'Evidence-first financial guide', greeting: 'Hi—I can explain financial concepts, help with this report, find tickers, or show you around FinSight. What would you like to understand?',
    placeholder: 'Ask about a concept, company, or report…', send: 'Send', retry: 'Retry',
    loading: 'FinSight Assistant is thinking', error: 'I couldn’t reach the assistant. Your message is still here.',
    offline: 'You’re offline. Reconnect to send a message.', current: 'Using current report',
    evidence: 'Evidence', disclaimer: 'Education and research support only—not personalized investment advice.',
    chars: 'characters remaining', suggestions: 'Suggested questions', you: 'You',
    questions: ['What does P/E mean?', 'Explain this report simply.', 'How do I compare companies?', "Find Microsoft's ticker."],
  },
  es: {
    open: 'Abrir el Asistente FinSight', close: 'Cerrar el asistente', title: 'Asistente FinSight',
    subtitle: 'Guía financiera basada en evidencia', greeting: 'Hola. Puedo explicar conceptos financieros, ayudarte con este informe, buscar tickers o mostrarte cómo usar FinSight. ¿Qué te gustaría entender?',
    placeholder: 'Pregunta por un concepto, empresa o informe…', send: 'Enviar', retry: 'Reintentar',
    loading: 'El Asistente FinSight está pensando', error: 'No pude conectar con el asistente. Tu mensaje sigue aquí.',
    offline: 'Estás sin conexión. Reconéctate para enviar un mensaje.', current: 'Usando el informe actual',
    evidence: 'Evidencia', disclaimer: 'Solo educación y apoyo a la investigación; no es asesoramiento personalizado.',
    chars: 'caracteres restantes', suggestions: 'Preguntas sugeridas', you: 'Tú',
    questions: ['¿Qué significa P/E?', 'Explica este informe de forma sencilla.', '¿Cómo comparo empresas?', 'Busca el ticker de Microsoft.'],
  },
  fr: {
    open: 'Ouvrir l’Assistant FinSight', close: 'Fermer l’assistant', title: 'Assistant FinSight',
    subtitle: 'Guide financier fondé sur les preuves', greeting: 'Bonjour. Je peux expliquer des concepts financiers, vous aider avec ce rapport, trouver des tickers ou vous guider dans FinSight. Que souhaitez-vous comprendre ?',
    placeholder: 'Question sur un concept, une entreprise ou un rapport…', send: 'Envoyer', retry: 'Réessayer',
    loading: 'L’Assistant FinSight réfléchit', error: 'Je n’ai pas pu joindre l’assistant. Votre message est toujours là.',
    offline: 'Vous êtes hors ligne. Reconnectez-vous pour envoyer un message.', current: 'Rapport actuel utilisé',
    evidence: 'Preuves', disclaimer: 'Aide à l’éducation et à la recherche uniquement, pas de conseil personnalisé.',
    chars: 'caractères restants', suggestions: 'Questions suggérées', you: 'Vous',
    questions: ['Que signifie P/E ?', 'Explique simplement ce rapport.', 'Comment comparer des entreprises ?', 'Trouve le ticker de Microsoft.'],
  },
  zh: {
    open: '打开 FinSight 助手', close: '关闭助手', title: 'FinSight 助手',
    subtitle: '证据优先的金融指南', greeting: '你好！我可以解释金融概念、帮你理解当前报告、查找 ticker，或介绍 FinSight 的用法。你想了解什么？',
    placeholder: '询问金融概念、公司或报告…', send: '发送', retry: '重试',
    loading: 'FinSight 助手正在思考', error: '暂时无法连接助手，你的消息仍在。',
    offline: '你已离线。重新连接后即可发送消息。', current: '正在使用当前报告',
    evidence: '证据', disclaimer: '仅用于教育和研究支持，不构成个人化投资建议。',
    chars: '剩余字符', suggestions: '建议问题', you: '你',
    questions: ['P/E 是什么？', '用简单的话解释这份报告。', '如何比较公司？', '查找 Microsoft 的 ticker。'],
  },
}

export function assistantUi(language) {
  return UI[language] || UI.en
}

function sourceFor(point) {
  return [point?.provider, point?.source].filter(Boolean).join(' · ') || 'FinSight report'
}

function addPoint(evidence, key, label, point) {
  if (point == null || displayDataPoint(point) == null) return
  evidence.push({
    evidence_id: `overview.${key}`,
    label,
    value: String(displayDataPoint(point)),
    source: sourceFor(point),
    as_of_date: point.as_of_date || null,
    source_url: point.source_url || null,
  })
}

export function buildAssistantReportContext(data, comparison) {
  if (data?.overview) {
    const overview = data.overview
    const evidence = []
    const metrics = {
      price: 'Share price', market_cap: 'Market cap', trailing_pe: 'Trailing P/E',
      forward_pe: 'Forward P/E', price_to_sales: 'Price / Sales',
      revenue_growth: 'Revenue growth', profit_margin: 'Profit margin',
      free_cash_flow: 'Free cash flow', debt_to_equity: 'Debt / Equity', beta: 'Beta',
      dividend_yield: 'Dividend yield',
    }
    Object.entries(metrics).forEach(([key, label]) => addPoint(evidence, key, label, overview[key]))
    ;(data.analysis?.insights || []).slice(0, 8).forEach((insight, index) => {
      const explanation = insight.explanation
      if (!explanation?.claim) return
      evidence.push({
        evidence_id: `analysis.insights.${index}`,
        label: insight.title?.claim || insight.code,
        value: explanation.claim,
        source: sourceFor(explanation),
        as_of_date: explanation.as_of_date || null,
        source_url: explanation.source_url || null,
      })
    })
    return {
      ticker: overview.ticker,
      company_name: overview.name || overview.ticker,
      evidence,
    }
  }
  if (comparison?.rows?.length) {
    const evidence = comparison.rows.slice(0, 12).map((row, index) => {
      const entries = Object.entries(row.values || {}).filter(([, point]) => point != null)
      const firstPoint = entries[0]?.[1]
      return {
        evidence_id: `comparison.rows.${index}`,
        label: row.label,
        value: entries.map(([ticker, point]) => `${ticker}: ${displayDataPoint(point)}`).join('; '),
        source: sourceFor(firstPoint),
        as_of_date: firstPoint?.as_of_date || null,
        source_url: firstPoint?.source_url || null,
      }
    })
    return {
      ticker: comparison.tickers.join(', '),
      company_name: 'Current company comparison',
      evidence,
    }
  }
  return null
}
