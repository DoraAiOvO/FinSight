// UI translations, mirroring the RoboPrompt language option.
// `getTranslation` resolves UI strings by key; `translateServerText` maps the
// fixed set of English strings produced by the backend rules engine (insight
// titles, explanations, metric names) and falls back to the original text.

export const translations = {
  en: {
    // Header / footer
    headerNote: 'Research assistant · Not investment advice',
    goHome: 'Go to FinSight home',
    footerTagline: 'See beyond the numbers.',
    footerDisclaimer: 'Educational research only. Verify important information independently.',
    changeLanguage: 'Change language',

    // Landing
    eyebrow: 'Evidence-first equity research',
    heroTitle: 'See the business',
    heroTitleEm: 'behind the ticker.',
    heroLede:
      'Turn fundamentals, price movement, recent news, and risk signals into one balanced research brief you can actually follow.',
    startWith: 'Start with',
    tryPopular: 'Try a popular ticker',
    methodKicker: 'How FinSight works',
    methodBadge: 'No black box',
    methodTitle: 'A research trail, not a verdict.',
    methodCollect: 'Collect',
    methodCollectDesc: 'Fundamentals, pricing, and news',
    methodTest: 'Test',
    methodTestDesc: 'Metrics against visible benchmarks',
    methodExplain: 'Explain',
    methodExplainDesc: 'Risks and opportunities together',

    // Loading / errors / notices
    loadingCompare: 'Building a consistent comparison…',
    loadingAnalyze: 'Gathering the evidence…',
    errorTitle: 'We couldn’t build that report.',
    partialReport: 'Partial report',
    noticeHistory: 'Price history is temporarily unavailable.',
    noticeAnalysis: 'Risk analysis is temporarily unavailable.',
    noticeNews: 'Recent news is temporarily unavailable.',
    noticeHistoryUpdate: 'Price history could not be updated',

    // Report headings
    researchBriefKicker: 'Research brief',
    reportTitle: 'A balanced view of',
    reportTitleEm: 'the evidence',
    generatedAt: 'Generated',
    dataDelayed: 'Yahoo Finance data may be delayed',
    peerKicker: 'Peer research',
    compareTitle: 'Compare the evidence,',
    compareTitleEm: 'metric by metric.',

    // Search bar
    searchAriaLabel: 'Stock research search',
    modeAriaLabel: 'Research mode',
    modeCompany: 'Company',
    modeCompare: 'Compare',
    labelAnalyze: 'Research a public company',
    labelCompare: 'Compare 2–5 companies',
    placeholderAnalyze: 'Enter a ticker, e.g. AAPL',
    placeholderCompare: 'AAPL, MSFT, GOOGL',
    working: 'Working…',
    analyzeCta: 'Build research brief',
    compareCta: 'Compare companies',
    vEnterTicker: 'Enter a ticker to begin.',
    vTickerFormat: 'Use ticker symbols only, such as BRK-B or RDS.A.',
    vCompareCount: 'Enter between two and five tickers to compare.',
    vOneTicker: 'Enter one ticker, or switch to Compare for multiple companies.',
    vDuplicate: 'Use each ticker only once.',

    // Overview
    companyProfile: 'Company profile',
    currentPrice: 'Current price',
    today: 'today',
    range52: '52-week range',
    throughRange: 'through range',
    mMarketCap: 'Market cap',
    mTrailingPe: 'Trailing P/E',
    mForwardPe: 'Forward P/E',
    mPriceToSales: 'Price / Sales',
    mNetMargin: 'Net margin',
    mRevenueGrowth: 'Revenue growth',
    mDebtToEquity: 'Debt / Equity',
    mFreeCashFlow: 'Free cash flow',

    // Price chart
    chartKicker: 'Market context',
    chartTitle: 'Price performance',
    chartPeriodAria: 'Price history period',
    over: 'over',
    updatingChart: 'Updating chart…',
    low: 'Low',
    high: 'High',

    // Analysis panel
    analysisKicker: 'Transparent rules engine',
    analysisTitle: 'Risks & opportunities',
    upside: 'upside',
    riskCount: 'risk',
    synthesis: 'FinSight synthesis',
    filterAria: 'Filter research signals',
    filterAll: 'All evidence',
    filterOpportunities: 'Opportunities',
    filterRisks: 'Risks',
    noFlags: 'No notable flags were triggered by the available metrics.',
    riskSignal: 'Risk signal',
    opportunitySignal: 'Opportunity signal',
    sevHigh: 'high',
    sevMedium: 'medium',
    sevLow: 'low',
    disclaimer:
      'FinSight explains evidence; it does not give investment advice. Data may be delayed or incomplete. Always do your own research.',

    // News feed
    newsKicker: 'What is changing',
    newsTitle: 'Recent news',
    sources: 'sources',
    headlineThemes: 'Headline themes',
    noHeadlines: 'No recent headlines were found.',

    // Compare table
    compareKicker: 'Consistent criteria',
    compareTableTitle: 'Side-by-side fundamentals',
    compareNote: 'Stronger marks the favorable direction for this metric—not the “better stock.”',
    metricHeader: 'Metric',
    higherFavorable: 'Higher is favorable',
    lowerFavorable: 'Lower is favorable',
    strongerValue: 'Stronger value',
  },
  es: {
    headerNote: 'Asistente de investigación · No es asesoramiento de inversión',
    goHome: 'Ir al inicio de FinSight',
    footerTagline: 'Ve más allá de los números.',
    footerDisclaimer: 'Solo investigación educativa. Verifica la información importante por tu cuenta.',
    changeLanguage: 'Cambiar idioma',

    eyebrow: 'Análisis bursátil basado en evidencia',
    heroTitle: 'Ve el negocio',
    heroTitleEm: 'detrás del ticker.',
    heroLede:
      'Convierte fundamentales, movimiento de precios, noticias recientes y señales de riesgo en un informe de análisis equilibrado que realmente puedes seguir.',
    startWith: 'Empieza con',
    tryPopular: 'Prueba un ticker popular',
    methodKicker: 'Cómo funciona FinSight',
    methodBadge: 'Sin caja negra',
    methodTitle: 'Un rastro de evidencia, no un veredicto.',
    methodCollect: 'Recopilar',
    methodCollectDesc: 'Fundamentales, precios y noticias',
    methodTest: 'Contrastar',
    methodTestDesc: 'Métricas frente a referencias visibles',
    methodExplain: 'Explicar',
    methodExplainDesc: 'Riesgos y oportunidades en conjunto',

    loadingCompare: 'Construyendo una comparación consistente…',
    loadingAnalyze: 'Reuniendo la evidencia…',
    errorTitle: 'No pudimos generar ese informe.',
    partialReport: 'Informe parcial',
    noticeHistory: 'El historial de precios no está disponible temporalmente.',
    noticeAnalysis: 'El análisis de riesgos no está disponible temporalmente.',
    noticeNews: 'Las noticias recientes no están disponibles temporalmente.',
    noticeHistoryUpdate: 'No se pudo actualizar el historial de precios',

    researchBriefKicker: 'Informe de análisis',
    reportTitle: 'Una visión equilibrada de',
    reportTitleEm: 'la evidencia',
    generatedAt: 'Generado',
    dataDelayed: 'Los datos de Yahoo Finance pueden llegar con retraso',
    peerKicker: 'Análisis comparativo',
    compareTitle: 'Compara la evidencia,',
    compareTitleEm: 'métrica a métrica.',

    searchAriaLabel: 'Búsqueda de análisis bursátil',
    modeAriaLabel: 'Modo de análisis',
    modeCompany: 'Empresa',
    modeCompare: 'Comparar',
    labelAnalyze: 'Investiga una empresa cotizada',
    labelCompare: 'Compara de 2 a 5 empresas',
    placeholderAnalyze: 'Escribe un ticker, p. ej. AAPL',
    placeholderCompare: 'AAPL, MSFT, GOOGL',
    working: 'Trabajando…',
    analyzeCta: 'Crear informe de análisis',
    compareCta: 'Comparar empresas',
    vEnterTicker: 'Escribe un ticker para empezar.',
    vTickerFormat: 'Usa solo símbolos de ticker, como BRK-B o RDS.A.',
    vCompareCount: 'Escribe entre dos y cinco tickers para comparar.',
    vOneTicker: 'Escribe un solo ticker, o cambia a Comparar para varias empresas.',
    vDuplicate: 'Usa cada ticker solo una vez.',

    companyProfile: 'Perfil de la empresa',
    currentPrice: 'Precio actual',
    today: 'hoy',
    range52: 'Rango de 52 semanas',
    throughRange: 'del rango',
    mMarketCap: 'Capitalización',
    mTrailingPe: 'PER (últ. 12 m)',
    mForwardPe: 'PER adelantado',
    mPriceToSales: 'Precio / Ventas',
    mNetMargin: 'Margen neto',
    mRevenueGrowth: 'Crecimiento de ingresos',
    mDebtToEquity: 'Deuda / Capital',
    mFreeCashFlow: 'Flujo de caja libre',

    chartKicker: 'Contexto de mercado',
    chartTitle: 'Evolución del precio',
    chartPeriodAria: 'Periodo del historial de precios',
    over: 'en',
    updatingChart: 'Actualizando gráfico…',
    low: 'Mín.',
    high: 'Máx.',

    analysisKicker: 'Motor de reglas transparente',
    analysisTitle: 'Riesgos y oportunidades',
    upside: 'a favor',
    riskCount: 'riesgo',
    synthesis: 'Síntesis de FinSight',
    filterAria: 'Filtrar señales de análisis',
    filterAll: 'Toda la evidencia',
    filterOpportunities: 'Oportunidades',
    filterRisks: 'Riesgos',
    noFlags: 'Las métricas disponibles no activaron ninguna señal destacable.',
    riskSignal: 'Señal de riesgo',
    opportunitySignal: 'Señal de oportunidad',
    sevHigh: 'alta',
    sevMedium: 'media',
    sevLow: 'baja',
    disclaimer:
      'FinSight explica la evidencia; no da consejos de inversión. Los datos pueden llegar con retraso o estar incompletos. Investiga siempre por tu cuenta.',

    newsKicker: 'Qué está cambiando',
    newsTitle: 'Noticias recientes',
    sources: 'fuentes',
    headlineThemes: 'Temas de los titulares',
    noHeadlines: 'No se encontraron titulares recientes.',

    compareKicker: 'Criterios consistentes',
    compareTableTitle: 'Fundamentales lado a lado',
    compareNote: 'La estrella marca la dirección favorable de esta métrica, no la «mejor acción».',
    metricHeader: 'Métrica',
    higherFavorable: 'Más alto es favorable',
    lowerFavorable: 'Más bajo es favorable',
    strongerValue: 'Valor más fuerte',
  },
  fr: {
    headerNote: 'Assistant de recherche · Pas un conseil en investissement',
    goHome: 'Aller à l’accueil FinSight',
    footerTagline: 'Voyez au-delà des chiffres.',
    footerDisclaimer: 'Recherche éducative uniquement. Vérifiez vous-même les informations importantes.',
    changeLanguage: 'Changer de langue',

    eyebrow: 'Recherche actions fondée sur les preuves',
    heroTitle: 'Voyez l’entreprise',
    heroTitleEm: 'derrière le ticker.',
    heroLede:
      'Transformez fondamentaux, évolution du cours, actualités récentes et signaux de risque en une note de recherche équilibrée que vous pouvez vraiment suivre.',
    startWith: 'Commencez avec',
    tryPopular: 'Essayez un ticker populaire',
    methodKicker: 'Comment fonctionne FinSight',
    methodBadge: 'Pas de boîte noire',
    methodTitle: 'Une piste de preuves, pas un verdict.',
    methodCollect: 'Collecter',
    methodCollectDesc: 'Fondamentaux, cours et actualités',
    methodTest: 'Confronter',
    methodTestDesc: 'Les métriques face à des repères visibles',
    methodExplain: 'Expliquer',
    methodExplainDesc: 'Risques et opportunités ensemble',

    loadingCompare: 'Construction d’une comparaison cohérente…',
    loadingAnalyze: 'Collecte des preuves…',
    errorTitle: 'Impossible de générer ce rapport.',
    partialReport: 'Rapport partiel',
    noticeHistory: 'L’historique des cours est temporairement indisponible.',
    noticeAnalysis: 'L’analyse des risques est temporairement indisponible.',
    noticeNews: 'Les actualités récentes sont temporairement indisponibles.',
    noticeHistoryUpdate: 'L’historique des cours n’a pas pu être mis à jour',

    researchBriefKicker: 'Note de recherche',
    reportTitle: 'Une vision équilibrée',
    reportTitleEm: 'des preuves',
    generatedAt: 'Généré à',
    dataDelayed: 'Les données Yahoo Finance peuvent être différées',
    peerKicker: 'Analyse comparative',
    compareTitle: 'Comparez les preuves,',
    compareTitleEm: 'métrique par métrique.',

    searchAriaLabel: 'Recherche d’analyse boursière',
    modeAriaLabel: 'Mode de recherche',
    modeCompany: 'Société',
    modeCompare: 'Comparer',
    labelAnalyze: 'Étudier une société cotée',
    labelCompare: 'Comparer 2 à 5 sociétés',
    placeholderAnalyze: 'Saisissez un ticker, p. ex. AAPL',
    placeholderCompare: 'AAPL, MSFT, GOOGL',
    working: 'En cours…',
    analyzeCta: 'Créer la note de recherche',
    compareCta: 'Comparer les sociétés',
    vEnterTicker: 'Saisissez un ticker pour commencer.',
    vTickerFormat: 'Utilisez uniquement des symboles de ticker, comme BRK-B ou RDS.A.',
    vCompareCount: 'Saisissez entre deux et cinq tickers à comparer.',
    vOneTicker: 'Saisissez un seul ticker, ou passez en mode Comparer pour plusieurs sociétés.',
    vDuplicate: 'N’utilisez chaque ticker qu’une seule fois.',

    companyProfile: 'Profil de la société',
    currentPrice: 'Cours actuel',
    today: 'aujourd’hui',
    range52: 'Plage sur 52 semaines',
    throughRange: 'de la plage',
    mMarketCap: 'Capitalisation',
    mTrailingPe: 'PER (12 m glissants)',
    mForwardPe: 'PER prévisionnel',
    mPriceToSales: 'Cours / CA',
    mNetMargin: 'Marge nette',
    mRevenueGrowth: 'Croissance du CA',
    mDebtToEquity: 'Dette / Capitaux propres',
    mFreeCashFlow: 'Flux de trésorerie disponible',

    chartKicker: 'Contexte de marché',
    chartTitle: 'Performance du cours',
    chartPeriodAria: 'Période de l’historique des cours',
    over: 'sur',
    updatingChart: 'Mise à jour du graphique…',
    low: 'Bas',
    high: 'Haut',

    analysisKicker: 'Moteur de règles transparent',
    analysisTitle: 'Risques et opportunités',
    upside: 'atouts',
    riskCount: 'risque',
    synthesis: 'Synthèse FinSight',
    filterAria: 'Filtrer les signaux de recherche',
    filterAll: 'Toutes les preuves',
    filterOpportunities: 'Opportunités',
    filterRisks: 'Risques',
    noFlags: 'Aucun signal notable n’a été déclenché par les métriques disponibles.',
    riskSignal: 'Signal de risque',
    opportunitySignal: 'Signal d’opportunité',
    sevHigh: 'élevée',
    sevMedium: 'moyenne',
    sevLow: 'faible',
    disclaimer:
      'FinSight explique les preuves ; il ne donne pas de conseils en investissement. Les données peuvent être différées ou incomplètes. Faites toujours vos propres recherches.',

    newsKicker: 'Ce qui change',
    newsTitle: 'Actualités récentes',
    sources: 'sources',
    headlineThemes: 'Thèmes des titres',
    noHeadlines: 'Aucun titre récent n’a été trouvé.',

    compareKicker: 'Critères cohérents',
    compareTableTitle: 'Fondamentaux côte à côte',
    compareNote: 'L’étoile marque la direction favorable pour cette métrique — pas la « meilleure action ».',
    metricHeader: 'Métrique',
    higherFavorable: 'Plus haut est favorable',
    lowerFavorable: 'Plus bas est favorable',
    strongerValue: 'Valeur plus forte',
  },
  zh: {
    headerNote: '研究助手 · 不构成投资建议',
    goHome: '返回 FinSight 首页',
    footerTagline: '看见数字背后的故事。',
    footerDisclaimer: '仅供学习研究之用。重要信息请自行核实。',
    changeLanguage: '切换语言',

    eyebrow: '证据优先的股票研究',
    heroTitle: '看见代码背后的',
    heroTitleEm: '真实公司。',
    heroLede: '将基本面、价格走势、最新新闻和风险信号整合成一份真正可以参考的均衡研究简报。',
    startWith: '从这里开始',
    tryPopular: '试试热门股票代码',
    methodKicker: 'FinSight 如何工作',
    methodBadge: '没有黑箱',
    methodTitle: '呈现研究线索，而非下结论。',
    methodCollect: '收集',
    methodCollectDesc: '基本面、价格与新闻',
    methodTest: '检验',
    methodTestDesc: '用可见的基准检验各项指标',
    methodExplain: '解释',
    methodExplainDesc: '同时呈现风险与机会',

    loadingCompare: '正在构建一致的对比…',
    loadingAnalyze: '正在收集证据…',
    errorTitle: '无法生成该报告。',
    partialReport: '部分报告',
    noticeHistory: '价格历史暂时不可用。',
    noticeAnalysis: '风险分析暂时不可用。',
    noticeNews: '最新新闻暂时不可用。',
    noticeHistoryUpdate: '价格历史更新失败',

    researchBriefKicker: '研究简报',
    reportTitle: '均衡地看待',
    reportTitleEm: '这些证据',
    generatedAt: '生成于',
    dataDelayed: 'Yahoo Finance 数据可能有延迟',
    peerKicker: '同业研究',
    compareTitle: '逐项指标，',
    compareTitleEm: '对比证据。',

    searchAriaLabel: '股票研究搜索',
    modeAriaLabel: '研究模式',
    modeCompany: '单家公司',
    modeCompare: '对比',
    labelAnalyze: '研究一家上市公司',
    labelCompare: '对比 2–5 家公司',
    placeholderAnalyze: '输入股票代码，如 AAPL',
    placeholderCompare: 'AAPL, MSFT, GOOGL',
    working: '处理中…',
    analyzeCta: '生成研究简报',
    compareCta: '对比公司',
    vEnterTicker: '请输入股票代码开始。',
    vTickerFormat: '请只使用股票代码，例如 BRK-B 或 RDS.A。',
    vCompareCount: '请输入两到五个股票代码进行对比。',
    vOneTicker: '请只输入一个代码，或切换到“对比”模式研究多家公司。',
    vDuplicate: '每个代码只能使用一次。',

    companyProfile: '公司概况',
    currentPrice: '当前价格',
    today: '今日',
    range52: '52 周区间',
    throughRange: '区间位置',
    mMarketCap: '市值',
    mTrailingPe: '市盈率（TTM）',
    mForwardPe: '预期市盈率',
    mPriceToSales: '市销率',
    mNetMargin: '净利率',
    mRevenueGrowth: '营收增长',
    mDebtToEquity: '负债/股东权益',
    mFreeCashFlow: '自由现金流',

    chartKicker: '市场背景',
    chartTitle: '价格表现',
    chartPeriodAria: '价格历史周期',
    over: '·',
    updatingChart: '正在更新图表…',
    low: '最低',
    high: '最高',

    analysisKicker: '透明规则引擎',
    analysisTitle: '风险与机会',
    upside: '项利好',
    riskCount: '项风险',
    synthesis: 'FinSight 综合解读',
    filterAria: '筛选研究信号',
    filterAll: '全部证据',
    filterOpportunities: '机会',
    filterRisks: '风险',
    noFlags: '现有指标未触发任何值得注意的信号。',
    riskSignal: '风险信号',
    opportunitySignal: '机会信号',
    sevHigh: '高',
    sevMedium: '中',
    sevLow: '低',
    disclaimer: 'FinSight 只解释证据，不提供投资建议。数据可能延迟或不完整。请务必自行研究。',

    newsKicker: '正在发生的变化',
    newsTitle: '最新新闻',
    sources: '条来源',
    headlineThemes: '头条主题',
    noHeadlines: '未找到最新头条。',

    compareKicker: '一致的标准',
    compareTableTitle: '基本面并列对比',
    compareNote: '星标表示该指标的有利方向，并不代表“更好的股票”。',
    metricHeader: '指标',
    higherFavorable: '越高越有利',
    lowerFavorable: '越低越有利',
    strongerValue: '更强的数值',
  },
}

export function getTranslation(language, key) {
  return translations[language]?.[key] || translations.en[key] || key
}

// Fixed English strings produced by the backend rules engine, translated
// client-side. Anything not found here falls back to the original text.
const SERVER_TEXT = {
  es: {
    // Insight titles
    'Rich valuation': 'Valoración exigente',
    'Low earnings multiple': 'Múltiplo de beneficios bajo',
    'High leverage': 'Apalancamiento alto',
    'Tight short-term liquidity': 'Liquidez a corto plazo ajustada',
    'Negative free cash flow': 'Flujo de caja libre negativo',
    'Strong cash generation': 'Fuerte generación de caja',
    'Fast revenue growth': 'Crecimiento rápido de ingresos',
    'Shrinking revenue': 'Ingresos en descenso',
    'High profitability': 'Alta rentabilidad',
    'Unprofitable operations': 'Operaciones no rentables',
    'High volatility': 'Alta volatilidad',
    'Meaningful dividend income': 'Ingreso por dividendos relevante',
    'Trading at 52-week highs': 'Cotiza en máximos de 52 semanas',
    'Near 52-week lows': 'Cerca de mínimos de 52 semanas',
    'Analyst targets diverge from price': 'Los objetivos de analistas divergen del precio',
    // Evidence metric names
    'Current ratio': 'Ratio corriente',
    'Free cash flow (TTM)': 'Flujo de caja libre (TTM)',
    'FCF yield': 'Rentabilidad FCF',
    'Revenue growth (YoY)': 'Crecimiento de ingresos (interanual)',
    'Net profit margin': 'Margen de beneficio neto',
    'Beta (5y)': 'Beta (5 años)',
    'Dividend yield': 'Rentabilidad por dividendo',
    'Position in 52-week range': 'Posición en el rango de 52 semanas',
    'Mean analyst target': 'Objetivo medio de analistas',
    'Trailing P/E': 'PER (últ. 12 m)',
    'Debt / Equity': 'Deuda / Capital',
    // Compare table labels
    'Market cap': 'Capitalización',
    'Forward P/E': 'PER adelantado',
    'Price / Sales': 'Precio / Ventas',
    'Net margin': 'Margen neto',
    'Operating margin': 'Margen operativo',
    'Free cash flow': 'Flujo de caja libre',
    Beta: 'Beta',
  },
  fr: {
    'Rich valuation': 'Valorisation élevée',
    'Low earnings multiple': 'Multiple de bénéfices faible',
    'High leverage': 'Endettement élevé',
    'Tight short-term liquidity': 'Liquidité à court terme tendue',
    'Negative free cash flow': 'Flux de trésorerie disponible négatif',
    'Strong cash generation': 'Forte génération de trésorerie',
    'Fast revenue growth': 'Croissance rapide du chiffre d’affaires',
    'Shrinking revenue': 'Chiffre d’affaires en recul',
    'High profitability': 'Rentabilité élevée',
    'Unprofitable operations': 'Activité non rentable',
    'High volatility': 'Volatilité élevée',
    'Meaningful dividend income': 'Revenu de dividendes significatif',
    'Trading at 52-week highs': 'Au plus haut sur 52 semaines',
    'Near 52-week lows': 'Proche des plus bas sur 52 semaines',
    'Analyst targets diverge from price': 'Les objectifs des analystes divergent du cours',
    'Current ratio': 'Ratio de liquidité générale',
    'Free cash flow (TTM)': 'Flux de trésorerie disponible (12 m glissants)',
    'FCF yield': 'Rendement du FCF',
    'Revenue growth (YoY)': 'Croissance du CA (sur un an)',
    'Net profit margin': 'Marge nette',
    'Beta (5y)': 'Bêta (5 ans)',
    'Dividend yield': 'Rendement du dividende',
    'Position in 52-week range': 'Position dans la plage 52 semaines',
    'Mean analyst target': 'Objectif moyen des analystes',
    'Trailing P/E': 'PER (12 m glissants)',
    'Debt / Equity': 'Dette / Capitaux propres',
    'Market cap': 'Capitalisation',
    'Forward P/E': 'PER prévisionnel',
    'Price / Sales': 'Cours / CA',
    'Net margin': 'Marge nette',
    'Operating margin': 'Marge opérationnelle',
    'Free cash flow': 'Flux de trésorerie disponible',
    Beta: 'Bêta',
  },
  zh: {
    'Rich valuation': '估值偏高',
    'Low earnings multiple': '盈利倍数偏低',
    'High leverage': '杠杆偏高',
    'Tight short-term liquidity': '短期流动性紧张',
    'Negative free cash flow': '自由现金流为负',
    'Strong cash generation': '现金创造能力强',
    'Fast revenue growth': '营收快速增长',
    'Shrinking revenue': '营收萎缩',
    'High profitability': '盈利能力强',
    'Unprofitable operations': '经营尚未盈利',
    'High volatility': '波动性高',
    'Meaningful dividend income': '股息收益可观',
    'Trading at 52-week highs': '处于 52 周高点',
    'Near 52-week lows': '接近 52 周低点',
    'Analyst targets diverge from price': '分析师目标价与现价背离',
    'Current ratio': '流动比率',
    'Free cash flow (TTM)': '自由现金流（TTM）',
    'FCF yield': '自由现金流收益率',
    'Revenue growth (YoY)': '营收增长（同比）',
    'Net profit margin': '净利率',
    'Beta (5y)': '贝塔系数（5 年）',
    'Dividend yield': '股息率',
    'Position in 52-week range': '在 52 周区间中的位置',
    'Mean analyst target': '分析师平均目标价',
    'Trailing P/E': '市盈率（TTM）',
    'Debt / Equity': '负债/股东权益',
    'Market cap': '市值',
    'Forward P/E': '预期市盈率',
    'Price / Sales': '市销率',
    'Net margin': '净利率',
    'Operating margin': '营业利润率',
    'Free cash flow': '自由现金流',
    Beta: '贝塔系数',
  },
}

// Insight explanations (fixed strings in backend/app/services/analysis.py).
const SERVER_EXPLANATIONS = {
  es: {
    'The market is paying a high multiple of current earnings. If growth slows, high-multiple stocks tend to fall harder.':
      'El mercado paga un múltiplo alto sobre los beneficios actuales. Si el crecimiento se frena, las acciones con múltiplos altos tienden a caer con más fuerza.',
    'Shares trade cheaply relative to current earnings. That can signal value — or that the market expects earnings to decline; check why.':
      'Las acciones cotizan baratas respecto a los beneficios actuales. Puede ser señal de valor — o de que el mercado espera que los beneficios caigan; averigua el porqué.',
    'Debt is large relative to shareholder equity, which magnifies losses in downturns and raises refinancing risk when rates rise.':
      'La deuda es grande respecto al capital de los accionistas, lo que amplifica las pérdidas en las caídas y eleva el riesgo de refinanciación cuando suben los tipos.',
    'Current liabilities exceed current assets; the company may depend on new financing or fast inventory turnover to pay near-term bills.':
      'Los pasivos corrientes superan a los activos corrientes; la empresa puede depender de nueva financiación o de una rotación rápida de inventario para pagar sus facturas a corto plazo.',
    'The business consumes more cash than it generates, so it must fund itself from reserves, debt, or dilution.':
      'El negocio consume más caja de la que genera, por lo que debe financiarse con reservas, deuda o dilución.',
    "Free cash flow is high relative to the company's price, giving flexibility for buybacks, dividends, or reinvestment.":
      'El flujo de caja libre es alto respecto al precio de la empresa, lo que da flexibilidad para recompras, dividendos o reinversión.',
    'Sales are expanding well above typical GDP-level growth, suggesting market share gains or a growing market.':
      'Las ventas crecen muy por encima del crecimiento típico del PIB, lo que sugiere ganancias de cuota o un mercado en expansión.',
    'Sales are declining year over year. Check whether this is cyclical, one-off, or structural.':
      'Las ventas caen interanualmente. Comprueba si es algo cíclico, puntual o estructural.',
    'The company keeps a large share of every dollar of revenue as profit, often a sign of pricing power or scale advantages.':
      'La empresa retiene como beneficio una gran parte de cada dólar de ingresos, a menudo señal de poder de fijación de precios o ventajas de escala.',
    'The company currently loses money on a net basis; the investment case depends on a credible path to profitability.':
      'La empresa pierde dinero en términos netos; la tesis de inversión depende de un camino creíble hacia la rentabilidad.',
    'The stock historically moves much more than the overall market, in both directions. Expect larger swings.':
      'Históricamente la acción se mueve mucho más que el mercado, en ambas direcciones. Espera oscilaciones mayores.',
    'The stock pays a substantial dividend relative to its price. Verify the payout is covered by earnings and cash flow.':
      'La acción paga un dividendo sustancial respecto a su precio. Verifica que el pago esté cubierto por beneficios y flujo de caja.',
    'The price sits at the top of its one-year range. Momentum can continue, but there is little recent price support below.':
      'El precio está en la parte alta de su rango anual. El impulso puede continuar, pero hay poco soporte de precios reciente por debajo.',
    'The price is at the bottom of its one-year range. This may reflect real problems or an overreaction — check the news and fundamentals.':
      'El precio está en la parte baja de su rango anual. Puede reflejar problemas reales o una reacción exagerada — revisa las noticias y los fundamentales.',
    'Consensus analyst targets sit well above the current price. Analyst targets are frequently wrong — treat as one input, not a verdict.':
      'El consenso de objetivos de analistas está muy por encima del precio actual. Los objetivos de analistas se equivocan con frecuencia — trátalos como un dato más, no como un veredicto.',
    'Consensus analyst targets sit well below the current price. Analyst targets are frequently wrong — treat as one input, not a verdict.':
      'El consenso de objetivos de analistas está muy por debajo del precio actual. Los objetivos de analistas se equivocan con frecuencia — trátalos como un dato más, no como un veredicto.',
  },
  fr: {
    'The market is paying a high multiple of current earnings. If growth slows, high-multiple stocks tend to fall harder.':
      'Le marché paie un multiple élevé des bénéfices actuels. Si la croissance ralentit, les valeurs à multiples élevés tendent à chuter plus fort.',
    'Shares trade cheaply relative to current earnings. That can signal value — or that the market expects earnings to decline; check why.':
      'L’action se paie peu cher par rapport aux bénéfices actuels. Cela peut signaler de la valeur — ou une anticipation de baisse des bénéfices ; vérifiez pourquoi.',
    'Debt is large relative to shareholder equity, which magnifies losses in downturns and raises refinancing risk when rates rise.':
      'La dette est importante par rapport aux capitaux propres, ce qui amplifie les pertes en période de repli et accroît le risque de refinancement quand les taux montent.',
    'Current liabilities exceed current assets; the company may depend on new financing or fast inventory turnover to pay near-term bills.':
      'Les passifs courants dépassent les actifs courants ; l’entreprise peut dépendre de nouveaux financements ou d’une rotation rapide des stocks pour régler ses échéances proches.',
    'The business consumes more cash than it generates, so it must fund itself from reserves, debt, or dilution.':
      'L’activité consomme plus de trésorerie qu’elle n’en génère ; elle doit donc se financer par ses réserves, la dette ou la dilution.',
    "Free cash flow is high relative to the company's price, giving flexibility for buybacks, dividends, or reinvestment.":
      'Le flux de trésorerie disponible est élevé par rapport au prix de l’entreprise, offrant de la flexibilité pour rachats d’actions, dividendes ou réinvestissement.',
    'Sales are expanding well above typical GDP-level growth, suggesting market share gains or a growing market.':
      'Les ventes progressent bien au-dessus d’une croissance de type PIB, suggérant des gains de parts de marché ou un marché en expansion.',
    'Sales are declining year over year. Check whether this is cyclical, one-off, or structural.':
      'Les ventes reculent d’une année sur l’autre. Vérifiez si c’est cyclique, ponctuel ou structurel.',
    'The company keeps a large share of every dollar of revenue as profit, often a sign of pricing power or scale advantages.':
      'L’entreprise conserve en bénéfice une grande partie de chaque dollar de revenu, souvent signe de pouvoir de fixation des prix ou d’avantages d’échelle.',
    'The company currently loses money on a net basis; the investment case depends on a credible path to profitability.':
      'L’entreprise perd actuellement de l’argent en net ; la thèse d’investissement dépend d’un chemin crédible vers la rentabilité.',
    'The stock historically moves much more than the overall market, in both directions. Expect larger swings.':
      'Historiquement, l’action bouge bien plus que l’ensemble du marché, dans les deux sens. Attendez-vous à des variations plus amples.',
    'The stock pays a substantial dividend relative to its price. Verify the payout is covered by earnings and cash flow.':
      'L’action verse un dividende substantiel par rapport à son cours. Vérifiez que le versement est couvert par les bénéfices et la trésorerie.',
    'The price sits at the top of its one-year range. Momentum can continue, but there is little recent price support below.':
      'Le cours se situe en haut de sa plage annuelle. L’élan peut se poursuivre, mais il y a peu de support récent en dessous.',
    'The price is at the bottom of its one-year range. This may reflect real problems or an overreaction — check the news and fundamentals.':
      'Le cours est au bas de sa plage annuelle. Cela peut refléter de vrais problèmes ou une réaction excessive — vérifiez les actualités et les fondamentaux.',
    'Consensus analyst targets sit well above the current price. Analyst targets are frequently wrong — treat as one input, not a verdict.':
      'Le consensus des objectifs d’analystes est bien au-dessus du cours actuel. Ces objectifs sont souvent erronés — considérez-les comme un élément parmi d’autres, pas un verdict.',
    'Consensus analyst targets sit well below the current price. Analyst targets are frequently wrong — treat as one input, not a verdict.':
      'Le consensus des objectifs d’analystes est bien en dessous du cours actuel. Ces objectifs sont souvent erronés — considérez-les comme un élément parmi d’autres, pas un verdict.',
  },
  zh: {
    'The market is paying a high multiple of current earnings. If growth slows, high-multiple stocks tend to fall harder.':
      '市场正在为当前盈利支付很高的倍数。一旦增长放缓，高倍数股票往往跌得更狠。',
    'Shares trade cheaply relative to current earnings. That can signal value — or that the market expects earnings to decline; check why.':
      '相对于当前盈利，股价偏便宜。这可能是价值信号——也可能是市场预期盈利将下滑；需要查明原因。',
    'Debt is large relative to shareholder equity, which magnifies losses in downturns and raises refinancing risk when rates rise.':
      '债务相对股东权益偏高，会在下行周期放大亏损，并在利率上升时增加再融资风险。',
    'Current liabilities exceed current assets; the company may depend on new financing or fast inventory turnover to pay near-term bills.':
      '流动负债超过流动资产；公司可能需要依赖新融资或快速的存货周转来支付近期账单。',
    'The business consumes more cash than it generates, so it must fund itself from reserves, debt, or dilution.':
      '业务消耗的现金多于产生的现金，因此必须依靠储备、举债或增发稀释来维持运转。',
    "Free cash flow is high relative to the company's price, giving flexibility for buybacks, dividends, or reinvestment.":
      '相对于公司市值，自由现金流很充裕，为回购、分红或再投资提供了灵活性。',
    'Sales are expanding well above typical GDP-level growth, suggesting market share gains or a growing market.':
      '销售增速远高于一般 GDP 水平，说明公司可能在扩大市场份额，或所处市场正在增长。',
    'Sales are declining year over year. Check whether this is cyclical, one-off, or structural.':
      '销售额同比下滑。需要判断这是周期性、一次性还是结构性的。',
    'The company keeps a large share of every dollar of revenue as profit, often a sign of pricing power or scale advantages.':
      '公司能把每一美元收入中的很大一部分留存为利润，这通常是定价权或规模优势的表现。',
    'The company currently loses money on a net basis; the investment case depends on a credible path to profitability.':
      '公司目前净亏损；投资逻辑取决于是否有可信的盈利路径。',
    'The stock historically moves much more than the overall market, in both directions. Expect larger swings.':
      '这只股票历史上的波动幅度远大于整体市场，涨跌皆然。请预期更大的震荡。',
    'The stock pays a substantial dividend relative to its price. Verify the payout is covered by earnings and cash flow.':
      '相对股价而言，股息相当可观。请核实派息是否有盈利和现金流支撑。',
    'The price sits at the top of its one-year range. Momentum can continue, but there is little recent price support below.':
      '股价处于一年区间的顶部。势头可能延续，但下方缺乏近期的价格支撑。',
    'The price is at the bottom of its one-year range. This may reflect real problems or an overreaction — check the news and fundamentals.':
      '股价处于一年区间的底部。这可能反映真实问题，也可能是过度反应——请查看新闻和基本面。',
    'Consensus analyst targets sit well above the current price. Analyst targets are frequently wrong — treat as one input, not a verdict.':
      '分析师共识目标价远高于现价。分析师目标价经常出错——只应作为参考之一，而非定论。',
    'Consensus analyst targets sit well below the current price. Analyst targets are frequently wrong — treat as one input, not a verdict.':
      '分析师共识目标价远低于现价。分析师目标价经常出错——只应作为参考之一，而非定论。',
  },
}

export function translateServerText(language, text) {
  if (!text || language === 'en') return text
  return SERVER_TEXT[language]?.[text] || SERVER_EXPLANATIONS[language]?.[text] || text
}

const BENCHMARK_TEXT = {
  es: {
    market_pe_average: 'La media histórica del mercado amplio ronda 15–20',
    debt_elevated: 'Más de ~150% suele considerarse elevado',
    current_ratio_low: 'Por debajo de 1,0, los pasivos próximos superan los activos líquidos',
    positive_fcf: 'Los negocios sostenibles generan flujo de caja libre positivo',
    fcf_yield_strong: 'Más de ~5% se considera sólido',
    vs_market_cap: 'frente a una capitalización de {marketCap}',
    revenue_growth_fast: 'Más de ~15% es rápido para una empresa consolidada',
    revenue_growth_negative: 'El crecimiento negativo indica contracción de los ingresos',
    net_margin_high: 'Más de ~20% es alto en la mayoría de sectores',
    net_margin_negative: 'Un margen negativo implica pérdidas netas',
    beta_volatile: '1,0 = se mueve con el mercado; más de 1,5 es volátil',
    dividend_meaningful: 'Más de ~3% aporta ingresos relevantes',
    range_values: 'Rango {low} – {high}',
    vs_current_price: 'frente al precio actual {price} (brecha de {gap})',
  },
  fr: {
    market_pe_average: 'La moyenne historique du marché large est d’environ 15–20',
    debt_elevated: 'Au-dessus de ~150 %, le niveau est généralement jugé élevé',
    current_ratio_low: 'Sous 1,0, les dettes à court terme dépassent les actifs liquides',
    positive_fcf: 'Une entreprise durable génère un flux de trésorerie disponible positif',
    fcf_yield_strong: 'Au-dessus de ~5 %, le niveau est jugé solide',
    vs_market_cap: 'contre une capitalisation de {marketCap}',
    revenue_growth_fast: 'Au-dessus de ~15 %, la croissance est rapide pour une entreprise établie',
    revenue_growth_negative: 'Une croissance négative signifie que le chiffre d’affaires se contracte',
    net_margin_high: 'Au-dessus de ~20 %, la marge est élevée dans la plupart des secteurs',
    net_margin_negative: 'Une marge négative signifie une perte nette',
    beta_volatile: '1,0 = évolue avec le marché ; au-dessus de 1,5 = volatil',
    dividend_meaningful: 'Au-dessus de ~3 %, le revenu devient significatif',
    range_values: 'Fourchette {low} – {high}',
    vs_current_price: 'contre un cours actuel de {price} (écart de {gap})',
  },
  zh: {
    market_pe_average: '大盘长期平均水平约为 15–20',
    debt_elevated: '超过约 150% 通常被视为偏高',
    current_ratio_low: '低于 1.0 表示短期负债超过流动资产',
    positive_fcf: '可持续经营的企业应产生正自由现金流',
    fcf_yield_strong: '超过约 5% 通常被视为较强',
    vs_market_cap: '对比市值 {marketCap}',
    revenue_growth_fast: '对成熟企业而言，超过约 15% 属于快速增长',
    revenue_growth_negative: '负增长表示营收正在收缩',
    net_margin_high: '在多数行业中，超过约 20% 属于较高水平',
    net_margin_negative: '负利润率意味着净亏损',
    beta_volatile: '1.0 = 与市场同步；高于 1.5 表示波动较大',
    dividend_meaningful: '超过约 3% 可构成有意义的收益来源',
    range_values: '区间 {low} – {high}',
    vs_current_price: '对比当前价格 {price}（差距 {gap}）',
  },
}

export function translateBenchmark(language, key, params = {}, fallback = '') {
  const template = BENCHMARK_TEXT[language]?.[key] || fallback
  return template.replace(/\{(\w+)\}/g, (match, name) => (
    params[name] == null ? match : String(params[name])
  ))
}
