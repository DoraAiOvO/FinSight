"""Cached multilingual help and glossary responses for the FinSight Assistant."""
from __future__ import annotations

import re
from functools import lru_cache


_CONCEPT_ALIASES = {
    "pe": ("p/e", "pe ratio", "price to earnings", "precio beneficio", "cours bénéfice", "市盈率", "株価収益率", "주가수익비율", "kurs-gewinn-verhältnis", "preço/lucro", "prezzo/utili", "مكرر الربحية"),
    "eps": ("eps", "earnings per share", "beneficio por acción", "bénéfice par action", "每股收益", "1株当たり利益", "주당순이익", "gewinn je aktie", "lucro por ação", "utile per azione", "ربحية السهم"),
    "market_cap": ("market cap", "market capitalization", "capitalización bursátil", "capitalisation boursière", "市值", "時価総額", "시가총액", "marktkapitalisierung", "capitalização de mercado", "capitalizzazione di mercato", "القيمة السوقية"),
    "free_cash_flow": ("free cash flow", "fcf", "flujo de caja libre", "flux de trésorerie disponible", "自由现金流", "フリーキャッシュフロー", "잉여현금흐름", "freier cashflow", "fluxo de caixa livre", "flusso di cassa libero", "التدفق النقدي الحر"),
    "beta": ("beta", "贝塔", "ベータ", "베타", "بيتا"),
    "debt_to_equity": ("debt to equity", "debt/equity", "d/e", "deuda a capital", "dette sur capitaux propres", "负债权益比", "負債資本倍率", "부채비율", "verschuldungsgrad", "dívida/patrimônio", "debito/patrimonio", "الدين إلى حقوق الملكية"),
    "revenue_growth": ("revenue growth", "crecimiento de ingresos", "croissance du chiffre d'affaires", "营收增长", "売上高成長率", "매출 성장률", "umsatzwachstum", "crescimento da receita", "crescita dei ricavi", "نمو الإيرادات"),
    "profit_margin": ("profit margin", "margen de beneficio", "marge bénéficiaire", "利润率", "利益率", "이익률", "gewinnmarge", "margem de lucro", "margine di profitto", "هامش الربح"),
}

_CONCEPTS = {
    "en": {
        "pe": {
            "simple": "P/E (price-to-earnings ratio) compares a share's price with the company's earnings per share. It shows how much investors are paying for each dollar of past earnings. Compare it with similar companies and the same company's history; a high or low P/E is not a verdict by itself.",
            "standard": "P/E, or price-to-earnings ratio, is share price divided by earnings per share (EPS). It indicates how much the market pays for each dollar of trailing earnings. Differences can reflect expected growth, risk, accounting effects, or an unusual earnings period, so compare P/E with relevant peers and history rather than using it alone.",
            "professional": "P/E is equity value per share divided by EPS, usually measured on trailing or forward earnings. It compresses growth expectations, risk, capital intensity, and accounting quality into one multiple. It becomes unreliable when earnings are negative or temporarily distorted, and peer comparability depends on business mix and accounting consistency.",
        },
        "eps": {"simple": "EPS means earnings per share: company profit allocated to each share. It helps compare earnings with the share price, but dilution and one-off accounting items can change it.", "standard": "Earnings per share (EPS) is net income available to common shareholders divided by the weighted-average share count. Review basic versus diluted EPS and whether unusual items affected the period.", "professional": "EPS allocates earnings available to common equity across the weighted-average share base. Diluted EPS incorporates potentially dilutive securities; quality analysis should reconcile reported and adjusted EPS, one-offs, and share-count changes."},
        "market_cap": {"simple": "Market cap is the market value of a company's shares: share price multiplied by shares outstanding. It measures equity value, not the value of the whole business including debt.", "standard": "Market capitalization equals current share price times shares outstanding. It is the market value of common equity; enterprise value adds debt and other claims and subtracts cash.", "professional": "Market capitalization is the spot equity value implied by price and shares outstanding. Use diluted share counts when relevant, and distinguish it from enterprise value when comparing operations or capital structures."},
        "free_cash_flow": {"simple": "Free cash flow (FCF) is cash left after operating needs and capital spending. It can support debt repayment, reinvestment, dividends, or buybacks, but one period can be noisy.", "standard": "Free cash flow (FCF) commonly means operating cash flow minus capital expenditures. Definitions vary, so check the calculation and review several periods for working-capital or investment timing effects.", "professional": "FCF typically deducts capital expenditures from cash from operations, although levered and unlevered definitions differ. Normalize working capital, stock-based compensation, acquisitions, and maintenance versus growth capex before comparing firms."},
        "beta": {"simple": "Beta estimates how much a stock has moved relative to the overall market. Above 1 has historically meant larger moves; below 1, smaller moves. It is backward-looking and can change.", "standard": "Beta is a historical estimate of a stock's sensitivity to market returns. It depends on the chosen index and measurement window and captures only one form of risk, not the chance of permanent loss.", "professional": "Beta is the slope coefficient from regressing security excess returns on market excess returns. Results are specification-sensitive and unstable across regimes; beta measures systematic covariance, not total or fundamental risk."},
        "debt_to_equity": {"simple": "Debt-to-equity compares debt with shareholders' equity. A higher ratio can mean more financial leverage, but normal levels vary a lot by industry.", "standard": "Debt-to-equity compares company debt with book equity. Interpret it with cash flow, interest coverage, debt maturity, and industry norms because book equity can be small or negative.", "professional": "Debt-to-equity is a book-capital leverage measure whose usefulness depends on debt definitions and equity quality. Pair it with net leverage, coverage, liquidity, covenants, and maturity structure."},
        "revenue_growth": {"simple": "Revenue growth is the percentage increase or decrease in sales over time. Check whether it comes from real demand, acquisitions, price changes, or currency effects.", "standard": "Revenue growth measures the change in sales between periods. Separate organic growth from acquisitions, pricing, volume, and foreign-exchange effects, and compare like periods.", "professional": "Revenue growth should be decomposed into volume, price/mix, M&A, and currency, with attention to constant-currency and organic definitions. Growth quality depends on retention, unit economics, and durability."},
        "profit_margin": {"simple": "Profit margin shows how much profit remains from each dollar of revenue. Compare the same margin definition across similar companies and over time.", "standard": "Profit margin divides a profit measure by revenue. Gross, operating, and net margins answer different questions, so keep definitions consistent and check for one-off items.", "professional": "Margin analysis should separate gross, operating, EBITDA, and net margins and normalize nonrecurring items. Business mix, capitalization policies, and stock-based compensation can limit peer comparability."},
    },
    "es": {
        "pe": {"simple": "El P/E (precio/beneficio) compara el precio de una acción con el beneficio por acción. Indica cuánto paga el mercado por cada unidad de beneficio pasado. Compáralo con empresas similares y con el historial de la misma empresa; por sí solo no es una conclusión.", "standard": "El P/E, o ratio precio/beneficio, es el precio por acción dividido por EPS. Puede reflejar expectativas de crecimiento, riesgo o beneficios atípicos, por lo que conviene compararlo con pares relevantes y con el historial.", "professional": "El P/E relaciona el valor por acción con EPS, usando beneficios trailing o forward. Resume expectativas, riesgo y calidad contable, pero pierde utilidad con beneficios negativos o distorsionados y exige pares realmente comparables."},
        "eps": {"simple": "EPS significa beneficio por acción: la parte del beneficio atribuida a cada acción. La dilución y las partidas extraordinarias pueden cambiarlo.", "standard": "EPS es el beneficio neto disponible para accionistas comunes dividido por el promedio ponderado de acciones. Revisa EPS básico y diluido y los efectos no recurrentes.", "professional": "EPS distribuye el beneficio atribuible al capital común sobre las acciones medias ponderadas. Conviene conciliar EPS reportado y ajustado, dilución y partidas no recurrentes."},
        "market_cap": {"simple": "La capitalización bursátil es el precio por acción multiplicado por las acciones en circulación. Mide el valor del capital, no todo el negocio con su deuda.", "standard": "La capitalización bursátil mide el valor de mercado del capital común. El enterprise value también considera deuda, otras obligaciones y efectivo.", "professional": "La capitalización es el valor spot del equity implícito en precio y acciones; la comparación operativa suele requerir enterprise value y una base diluida coherente."},
        "free_cash_flow": {"simple": "Free cash flow (FCF) es el efectivo que queda tras las operaciones y la inversión de capital. Un solo periodo puede ser irregular.", "standard": "FCF suele calcularse como flujo de caja operativo menos capex. La definición puede variar; revisa varios periodos y el efecto del capital circulante.", "professional": "FCF puede ser levered o unlevered. Para compararlo, normaliza capital circulante, capex de mantenimiento y crecimiento, adquisiciones y compensación en acciones."},
        "beta": {"simple": "Beta estima cuánto se ha movido una acción frente al mercado. Es retrospectiva y puede cambiar.", "standard": "Beta estima la sensibilidad histórica a los rendimientos del mercado. Depende del índice y del periodo y no mide todas las formas de riesgo.", "professional": "Beta es el coeficiente de una regresión de rendimientos excedentes. Es sensible a la especificación y mide covarianza sistemática, no riesgo total o fundamental."},
    },
    "fr": {
        "pe": {"simple": "Le P/E (cours/bénéfice) compare le prix d'une action au bénéfice par action. Il indique combien le marché paie pour une unité de bénéfice passé. Comparez-le aux entreprises similaires et à l'historique ; seul, il ne permet pas de conclure.", "standard": "Le P/E est le cours divisé par l'EPS. Il peut refléter la croissance attendue, le risque ou des bénéfices atypiques ; il faut donc le comparer à des pairs pertinents et à l'historique.", "professional": "Le P/E rapporte la valeur par action à l'EPS trailing ou forward. Il agrège attentes, risque et qualité comptable, mais devient peu pertinent avec des bénéfices négatifs ou temporairement déformés."},
        "eps": {"simple": "L'EPS est le bénéfice par action. La dilution et les éléments exceptionnels peuvent le modifier.", "standard": "L'EPS correspond au résultat net attribuable aux actionnaires ordinaires divisé par le nombre moyen pondéré d'actions. Vérifiez l'EPS dilué et les éléments non récurrents.", "professional": "L'EPS alloue le résultat disponible aux actions ordinaires. L'analyse doit rapprocher EPS publié et ajusté, dilution et éléments exceptionnels."},
        "market_cap": {"simple": "La capitalisation boursière est le cours multiplié par le nombre d'actions. Elle mesure la valeur des fonds propres, pas celle de toute l'entreprise avec sa dette.", "standard": "La capitalisation mesure la valeur de marché des actions ordinaires. L'enterprise value ajoute notamment la dette et retranche la trésorerie.", "professional": "La capitalisation est la valeur spot des fonds propres. Les comparaisons opérationnelles exigent souvent l'enterprise value et une base diluée cohérente."},
        "free_cash_flow": {"simple": "Le free cash flow (FCF) est la trésorerie restante après les opérations et les investissements. Une seule période peut être trompeuse.", "standard": "Le FCF correspond souvent au cash-flow opérationnel moins les dépenses d'investissement. Vérifiez la définition et plusieurs périodes.", "professional": "Le FCF peut être levered ou unlevered. Normalisez besoin en fonds de roulement, capex, acquisitions et rémunération en actions pour comparer."},
        "beta": {"simple": "Le beta estime les mouvements historiques d'une action par rapport au marché. Il est rétrospectif et peut changer.", "standard": "Le beta estime la sensibilité historique aux rendements du marché. Il dépend de l'indice et de la période et ne couvre pas tous les risques.", "professional": "Le beta est la pente d'une régression des rendements excédentaires. Il est sensible à la spécification et ne mesure que la covariance systématique."},
    },
    "zh": {
        "pe": {"simple": "P/E（市盈率）是股价除以每股收益（EPS），表示市场愿意为每一元过去收益支付多少。应与相似公司和该公司历史比较；高或低 P/E 本身不是结论。", "standard": "P/E（市盈率）等于股价除以 EPS。它可能反映增长预期、风险或异常盈利期，因此应结合同行和历史区间理解。", "professional": "P/E 用每股权益价值除以历史或预期 EPS，浓缩了增长预期、风险和会计质量。当盈利为负或暂时失真时，该指标可比性较差。"},
        "eps": {"simple": "EPS 是每股收益，即每股对应的公司利润。股份稀释和一次性项目会影响它。", "standard": "EPS 是普通股股东可分配净利润除以加权平均股数。应同时查看基本和稀释 EPS 以及非经常性项目。", "professional": "EPS 将归属普通股的盈利分配到加权平均股本。分析时应调节报告与调整 EPS、稀释及一次性项目。"},
        "market_cap": {"simple": "市值等于股价乘以流通在外股数。它是股权价值，不等于包含债务的整体企业价值。", "standard": "市值是普通股的市场价值。企业价值还会加上债务等权益并减去现金。", "professional": "市值是由当前股价和股数隐含的股权价值。运营比较通常需使用企业价值，并统一稀释股本口径。"},
        "free_cash_flow": {"simple": "自由现金流（FCF）是经营和资本支出后剩余的现金。单一期可能波动很大。", "standard": "FCF 通常等于经营现金流减资本支出。定义可能不同，应查看多个期间及营运资金影响。", "professional": "FCF 可分为股权口径和企业口径。比较时应标准化营运资金、维护与增长性资本支出、并购及股权激励。"},
        "beta": {"simple": "贝塔系数估计股价相对整体市场的历史波动敏感度。它基于过去，也会改变。", "standard": "贝塔系数是股票对市场收益敏感度的历史估计，受基准指数和时间窗口影响，且不代表全部风险。", "professional": "贝塔系数是证券超额收益对市场超额收益回归的斜率。它对设定和市场阶段敏感，只衡量系统性协方差。"},
    },
}

# Complete the shared glossary in every supported language. These shorter
# entries keep less common concepts deterministic even when the AI layer is off.
_CONCEPTS["es"].update({
    "debt_to_equity": {"simple": "Debt-to-equity compara la deuda con el patrimonio. Un ratio mayor suele indicar más apalancamiento, aunque el nivel normal varía por sector.", "standard": "Debt-to-equity compara la deuda con el patrimonio contable. Interprétalo junto con flujo de caja, cobertura de intereses, vencimientos y normas del sector.", "professional": "Debt-to-equity es una medida contable de apalancamiento sensible a la definición de deuda y a la calidad del patrimonio. Complétala con deuda neta, cobertura, liquidez y vencimientos."},
    "revenue_growth": {"simple": "El crecimiento de ingresos es el cambio porcentual de las ventas. Revisa si procede de demanda, precios, adquisiciones o divisas.", "standard": "El crecimiento de ingresos mide el cambio de ventas entre periodos comparables. Separa crecimiento orgánico, adquisiciones, precio, volumen y divisas.", "professional": "Conviene descomponer el crecimiento entre volumen, precio/mix, M&A y divisas, y revisar retención, economía unitaria y durabilidad."},
    "profit_margin": {"simple": "El margen de beneficio muestra cuánto beneficio queda por cada unidad de ingresos. Compara la misma definición entre pares y a lo largo del tiempo.", "standard": "El margen divide una medida de beneficio por los ingresos. Margen bruto, operativo y neto responden preguntas distintas; mantén definiciones coherentes.", "professional": "El análisis debe separar margen bruto, operativo y neto y normalizar partidas no recurrentes, mezcla de negocio y políticas contables."},
})
_CONCEPTS["fr"].update({
    "debt_to_equity": {"simple": "Le debt-to-equity compare la dette aux capitaux propres. Un ratio plus élevé signale souvent davantage de levier, mais les normes varient selon le secteur.", "standard": "Le debt-to-equity compare la dette aux capitaux propres comptables. Analysez-le avec les flux de trésorerie, la couverture des intérêts et les échéances.", "professional": "Le debt-to-equity est une mesure comptable du levier, sensible aux définitions. Complétez-la par la dette nette, la couverture, la liquidité et les maturités."},
    "revenue_growth": {"simple": "La croissance du chiffre d'affaires mesure l'évolution des ventes. Vérifiez si elle vient de la demande, des prix, d'acquisitions ou des devises.", "standard": "La croissance du chiffre d'affaires compare les ventes entre périodes comparables. Séparez croissance organique, acquisitions, prix, volumes et change.", "professional": "Décomposez la croissance entre volumes, prix/mix, M&A et devises, puis examinez la rétention, l'économie unitaire et la durabilité."},
    "profit_margin": {"simple": "La marge bénéficiaire indique le bénéfice restant pour chaque unité de revenu. Comparez la même définition entre pairs et dans le temps.", "standard": "Une marge divise un niveau de résultat par le chiffre d'affaires. Les marges brute, opérationnelle et nette répondent à des questions différentes.", "professional": "L'analyse doit distinguer les marges brute, opérationnelle et nette et normaliser les éléments non récurrents, le mix et les conventions comptables."},
})
_CONCEPTS["zh"].update({
    "debt_to_equity": {"simple": "负债权益比比较债务与股东权益。较高通常表示更多杠杆，但正常水平因行业而异。", "standard": "负债权益比将债务与账面权益比较。应结合现金流、利息覆盖、债务到期和行业水平分析。", "professional": "负债权益比是受债务口径和权益质量影响的账面杠杆指标，应补充净杠杆、覆盖率、流动性和到期结构。"},
    "revenue_growth": {"simple": "营收增长是销售收入的百分比变化。应区分需求、价格、并购和汇率因素。", "standard": "营收增长比较可比期间的销售变化。应拆分内生增长、并购、价格、销量和汇率。", "professional": "营收增长应拆分为销量、价格与结构、并购和汇率，并检查留存、单位经济性和可持续性。"},
    "profit_margin": {"simple": "利润率表示每一元收入留下多少利润。应在同行和历史中使用同一口径比较。", "standard": "利润率用某一利润口径除以营收。毛利率、营业利润率和净利率回答不同问题，应保持定义一致。", "professional": "利润率分析应区分毛利、营业利润和净利润，并标准化非经常性项目、业务结构和会计政策差异。"},
})

_EXTRA_CONCEPTS = {
    "ja": {
        "pe": "P/E（株価収益率）は、株価を1株当たり利益（EPS）で割った指標です。成長期待やリスクも反映するため、同業他社や自社の過去と比較し、単独で結論を出さないことが大切です。",
        "eps": "EPS（1株当たり利益）は、普通株主に帰属する利益を加重平均株式数で割ったものです。希薄化や一時的な項目も確認してください。",
        "market_cap": "時価総額は、株価に発行済株式数を掛けた普通株式の市場価値です。負債を含む企業価値とは異なります。",
        "free_cash_flow": "フリーキャッシュフロー（FCF）は、通常、営業キャッシュフローから設備投資を差し引いたものです。定義と複数期間の推移を確認してください。",
        "beta": "ベータは、株価が市場収益率にどれだけ反応してきたかを示す過去の推定値です。将来を保証せず、リスクの一部しか表しません。",
        "debt_to_equity": "負債資本倍率は、負債と株主資本を比較する指標です。キャッシュフロー、利払い能力、返済期限、業界水準と併せて見ます。",
        "revenue_growth": "売上高成長率は、比較可能な期間の売上変化を示します。数量、価格、買収、為替の影響を分けて確認します。",
        "profit_margin": "利益率は、売上高に対してどれだけ利益が残るかを示します。粗利率、営業利益率、純利益率を同じ定義で比較してください。",
    },
    "ko": {
        "pe": "P/E(주가수익비율)는 주가를 주당순이익(EPS)으로 나눈 값입니다. 성장 기대와 위험도 반영하므로 동종 기업 및 과거 수준과 비교해야 하며, 단독으로 결론을 내리면 안 됩니다.",
        "eps": "EPS(주당순이익)는 보통주 주주에게 귀속되는 이익을 가중평균 주식 수로 나눈 값입니다. 희석과 일회성 항목도 확인해야 합니다.",
        "market_cap": "시가총액은 주가에 발행주식 수를 곱한 보통주 지분의 시장가치입니다. 부채를 포함한 기업가치와는 다릅니다.",
        "free_cash_flow": "잉여현금흐름(FCF)은 보통 영업현금흐름에서 자본적 지출을 뺀 값입니다. 정의와 여러 기간의 흐름을 확인하세요.",
        "beta": "베타는 주식이 시장 수익률에 얼마나 민감하게 움직였는지 보여 주는 과거 추정치입니다. 미래를 보장하지 않으며 위험의 일부만 측정합니다.",
        "debt_to_equity": "부채비율은 부채와 주주자본을 비교합니다. 현금흐름, 이자보상능력, 만기 구조, 업종 수준과 함께 봐야 합니다.",
        "revenue_growth": "매출 성장률은 비교 가능한 기간의 매출 변화를 나타냅니다. 판매량, 가격, 인수, 환율 효과를 나누어 확인해야 합니다.",
        "profit_margin": "이익률은 매출 중 얼마가 이익으로 남는지 보여 줍니다. 매출총이익률, 영업이익률, 순이익률을 같은 기준으로 비교하세요.",
    },
    "de": {
        "pe": "Das KGV (P/E) teilt den Aktienkurs durch den Gewinn je Aktie (EPS). Es kann Wachstumserwartungen und Risiken widerspiegeln und sollte mit passenden Unternehmen sowie der eigenen Historie verglichen werden.",
        "eps": "Der Gewinn je Aktie (EPS) verteilt den Stammaktionären zurechenbaren Gewinn auf die gewichtete Aktienzahl. Verwässerung und Sondereffekte sollten mitgeprüft werden.",
        "market_cap": "Die Marktkapitalisierung ist Aktienkurs mal ausstehende Aktien. Sie misst den Marktwert des Eigenkapitals, nicht den gesamten Unternehmenswert einschließlich Schulden.",
        "free_cash_flow": "Der freie Cashflow (FCF) ist meist operativer Cashflow abzüglich Investitionsausgaben. Definition und Entwicklung über mehrere Perioden sind wichtig.",
        "beta": "Beta schätzt die historische Empfindlichkeit einer Aktie gegenüber dem Markt. Es ist rückblickend und misst nur einen Teil des Risikos.",
        "debt_to_equity": "Der Verschuldungsgrad vergleicht Schulden mit Eigenkapital. Er sollte zusammen mit Cashflow, Zinsdeckung, Fälligkeiten und Branchenwerten gelesen werden.",
        "revenue_growth": "Das Umsatzwachstum misst die Veränderung der Erlöse zwischen vergleichbaren Perioden. Preis, Menge, Übernahmen und Währungseffekte sollten getrennt werden.",
        "profit_margin": "Die Gewinnmarge zeigt, wie viel Gewinn je Umsatzeinheit verbleibt. Brutto-, operative und Nettomarge müssen mit gleicher Definition verglichen werden.",
    },
    "pt": {
        "pe": "O P/L (P/E) divide o preço da ação pelo lucro por ação (EPS). Pode refletir expectativas de crescimento e risco, por isso deve ser comparado com empresas semelhantes e com o histórico da própria empresa.",
        "eps": "O lucro por ação (EPS) divide o lucro atribuível aos acionistas ordinários pela média ponderada de ações. Considere diluição e itens não recorrentes.",
        "market_cap": "A capitalização de mercado é o preço da ação multiplicado pelas ações em circulação. Mede o valor do patrimônio, não o valor total da empresa com dívida.",
        "free_cash_flow": "O fluxo de caixa livre (FCF) costuma ser o caixa operacional menos os investimentos. Verifique a definição e vários períodos.",
        "beta": "Beta estima a sensibilidade histórica de uma ação ao mercado. É retrospectivo e mede apenas uma parte do risco.",
        "debt_to_equity": "Dívida/patrimônio compara a dívida com o patrimônio líquido. Analise também caixa, cobertura de juros, vencimentos e padrões do setor.",
        "revenue_growth": "O crescimento da receita mede a mudança das vendas entre períodos comparáveis. Separe preço, volume, aquisições e câmbio.",
        "profit_margin": "A margem de lucro mostra quanto lucro permanece em relação à receita. Compare margem bruta, operacional e líquida com definições consistentes.",
    },
    "it": {
        "pe": "Il P/E divide il prezzo dell’azione per l’utile per azione (EPS). Può riflettere aspettative di crescita e rischio, quindi va confrontato con società simili e con la storia della stessa società.",
        "eps": "L’utile per azione (EPS) divide l’utile attribuibile agli azionisti ordinari per il numero medio ponderato di azioni. Vanno considerate diluizione e voci non ricorrenti.",
        "market_cap": "La capitalizzazione di mercato è il prezzo dell’azione moltiplicato per le azioni in circolazione. Misura il valore del capitale, non l’intero valore aziendale con il debito.",
        "free_cash_flow": "Il flusso di cassa libero (FCF) è normalmente il flusso operativo meno gli investimenti. Controlla la definizione e più periodi.",
        "beta": "Il beta stima la sensibilità storica di un’azione al mercato. È retrospettivo e misura solo una parte del rischio.",
        "debt_to_equity": "Debito/patrimonio confronta il debito con il patrimonio netto. Va letto insieme a flussi di cassa, copertura degli interessi e scadenze.",
        "revenue_growth": "La crescita dei ricavi misura la variazione delle vendite tra periodi comparabili. Separa prezzo, volumi, acquisizioni e cambi.",
        "profit_margin": "Il margine di profitto mostra quanto utile rimane rispetto ai ricavi. Confronta margine lordo, operativo e netto con definizioni coerenti.",
    },
    "ar": {
        "pe": "مكرر الربحية (P/E) هو سعر السهم مقسومًا على ربحية السهم (EPS). قد يعكس توقعات النمو والمخاطر، لذلك يُقارن بشركات مماثلة وبالسجل التاريخي للشركة ولا يُستخدم وحده.",
        "eps": "ربحية السهم (EPS) هي الربح المتاح للمساهمين العاديين مقسومًا على المتوسط المرجح لعدد الأسهم. يجب مراعاة التخفيف والبنود غير المتكررة.",
        "market_cap": "القيمة السوقية تساوي سعر السهم مضروبًا في عدد الأسهم القائمة. وهي تقيس قيمة حقوق الملكية لا قيمة الشركة الكاملة مع الديون.",
        "free_cash_flow": "التدفق النقدي الحر (FCF) هو عادة التدفق النقدي التشغيلي ناقص النفقات الرأسمالية. تحقّق من التعريف ومن عدة فترات.",
        "beta": "بيتا تقدّر حساسية السهم التاريخية لتحركات السوق. هي مقياس رجعي ولا تغطي جميع أنواع المخاطر.",
        "debt_to_equity": "نسبة الدين إلى حقوق الملكية تقارن الدين بحقوق المساهمين. تُقرأ مع التدفقات النقدية وتغطية الفوائد وآجال الدين ومستويات القطاع.",
        "revenue_growth": "نمو الإيرادات يقيس تغير المبيعات بين فترات قابلة للمقارنة. افصل أثر السعر والحجم والاستحواذات والعملات.",
        "profit_margin": "هامش الربح يوضح مقدار الربح المتبقي من الإيرادات. قارن الهامش الإجمالي والتشغيلي والصافي بالتعريف نفسه.",
    },
}
for _language, _entries in _EXTRA_CONCEPTS.items():
    _CONCEPTS[_language] = {
        key: {"simple": text, "standard": text, "professional": text}
        for key, text in _entries.items()
    }

_SITE_HELP = {
    "en": {
        "compare": "Choose Compare companies above the search box, enter 2–5 stock symbols separated by spaces or commas, and select Compare. FinSight uses consistent metrics and shows the evidence behind the table; differences are context, not a buy/sell ranking.",
        "report": "Search for one stock symbol and select Analyze. The report opens with the company overview, then evidence-backed benchmarks, valuation scenarios, risks and opportunities, news, and filings. Use the evidence labels and source links to verify company facts.",
        "profile": "Open Profile in the header to set your experience level, report depth, language, and research interests. These choices change presentation and explanation detail, never the underlying evidence or investment suitability.",
        "general": "Use the search bar to analyze a stock symbol or compare 2–5 companies. A report explains metrics, benchmarks, valuation scenarios, risks, news, and filings with evidence. You can also ask me about a financial term, the open report, or a company’s stock symbol.",
    },
    "es": {
        "compare": "Elige Comparar empresas sobre el buscador, introduce entre 2 y 5 símbolos bursátiles separados por espacios o comas y pulsa Comparar. FinSight usa métricas coherentes y muestra la evidencia; las diferencias no son una clasificación de compra o venta.",
        "report": "Busca un símbolo bursátil y pulsa Analizar. El informe muestra resumen, referencias comparativas, escenarios de valoración, riesgos y oportunidades, noticias y documentos regulatorios con evidencia verificable.",
        "profile": "Abre Perfil en el encabezado para configurar experiencia, profundidad, idioma e intereses. Solo cambia la presentación, nunca la evidencia ni la idoneidad de una inversión.",
        "general": "Usa el buscador para analizar un símbolo bursátil o comparar entre 2 y 5 empresas. También puedes preguntarme por un concepto financiero, el informe abierto o el símbolo bursátil de una empresa.",
    },
    "fr": {
        "compare": "Choisissez Comparer des entreprises, saisissez 2 à 5 symboles boursiers séparés par des espaces ou des virgules, puis lancez la comparaison. Les écarts sont un contexte fondé sur les preuves, pas un classement d'achat ou de vente.",
        "report": "Recherchez un symbole boursier puis choisissez Analyser. Le rapport présente la synthèse, les références comparatives, les scénarios de valorisation, les risques, les actualités et les documents réglementaires avec leurs preuves.",
        "profile": "Ouvrez Profil dans l'en-tête pour régler l'expérience, le niveau de détail, la langue et les centres d'intérêt. Cela ne modifie jamais les preuves ni l'adéquation d'un investissement.",
        "general": "Utilisez la recherche pour analyser un symbole boursier ou comparer 2 à 5 entreprises. Vous pouvez aussi m'interroger sur un concept, le rapport ouvert ou le symbole boursier d'une entreprise.",
    },
    "zh": {
        "compare": "在搜索框上方选择“比较公司”，输入 2–5 个用空格或逗号分隔的股票代码，然后点击比较。结果是基于证据的上下文，不是买卖排名。",
        "report": "搜索一个股票代码并点击“分析”。报告会展示概览、比较基准、估值情景、风险与机会、新闻和监管文件，并附可验证证据。",
        "profile": "在顶部打开“画像”，可设置经验水平、报告深度、语言和研究兴趣。这些只改变展示方式，不会改变证据或投资适合性。",
        "general": "使用搜索栏可分析一个股票代码或比较 2–5 家公司。你也可以问我金融概念、当前报告或公司的股票代码。",
    },
    "ja": {
        "compare": "検索欄の上で「企業を比較」を選び、2～5個の銘柄コードを空白またはカンマで区切って入力し、比較を実行します。結果は売買順位ではなく、根拠に基づく比較材料です。",
        "report": "銘柄コードを検索して「分析」を選ぶと、概要、比較基準、評価シナリオ、リスクと機会、ニュース、規制当局への提出書類を確認できます。",
        "profile": "ヘッダーのプロフィールから、経験、レポートの詳しさ、言語、関心分野を設定できます。表示方法だけが変わり、根拠や投資適合性は変わりません。",
        "general": "検索欄で銘柄コードを分析するか、2～5社を比較できます。金融用語、開いているレポート、企業の銘柄コードについても質問できます。",
    },
    "ko": {
        "compare": "검색창 위에서 ‘기업 비교’를 선택하고 2~5개의 종목 코드를 공백이나 쉼표로 구분해 입력한 뒤 비교를 실행하세요. 결과는 매수·매도 순위가 아니라 근거 기반 비교 자료입니다.",
        "report": "종목 코드를 검색하고 ‘분석’을 선택하면 개요, 비교 기준, 가치평가 시나리오, 위험과 기회, 뉴스, 규제 공시를 확인할 수 있습니다.",
        "profile": "헤더의 프로필에서 경험 수준, 보고서 깊이, 언어, 관심 분야를 설정할 수 있습니다. 표시 방식만 바뀌며 근거나 투자 적합성은 바뀌지 않습니다.",
        "general": "검색창에서 종목 코드를 분석하거나 2~5개 회사를 비교할 수 있습니다. 금융 용어, 열린 보고서, 회사의 종목 코드도 질문할 수 있습니다.",
    },
    "de": {
        "compare": "Wählen Sie oberhalb der Suche „Unternehmen vergleichen“, geben Sie 2–5 Aktiensymbole durch Leerzeichen oder Kommas getrennt ein und starten Sie den Vergleich. Das Ergebnis ist keine Kauf- oder Verkaufsrangliste.",
        "report": "Suchen Sie ein Aktiensymbol und wählen Sie „Analysieren“. Der Bericht zeigt Übersicht, Vergleichsmaßstäbe, Bewertungsszenarien, Risiken, Chancen, Nachrichten und regulatorische Meldungen mit Belegen.",
        "profile": "Im Profil können Sie Erfahrung, Berichtstiefe, Sprache und Interessengebiete einstellen. Das ändert nur die Darstellung, nicht die Belege oder die Anlegereignung.",
        "general": "Über die Suche können Sie ein Aktiensymbol analysieren oder 2–5 Unternehmen vergleichen. Sie können auch nach Finanzbegriffen, dem geöffneten Bericht oder einem Aktiensymbol fragen.",
    },
    "pt": {
        "compare": "Selecione “Comparar empresas”, informe de 2 a 5 símbolos de ações separados por espaços ou vírgulas e inicie a comparação. O resultado oferece contexto baseado em evidências, não uma classificação de compra ou venda.",
        "report": "Pesquise um símbolo de ação e selecione “Analisar”. O relatório mostra visão geral, referências comparativas, cenários de avaliação, riscos, oportunidades, notícias e documentos regulatórios com evidências.",
        "profile": "No perfil, você pode definir experiência, profundidade do relatório, idioma e interesses. Isso muda apenas a apresentação, nunca as evidências ou a adequação do investimento.",
        "general": "Use a pesquisa para analisar um símbolo de ação ou comparar de 2 a 5 empresas. Você também pode perguntar sobre conceitos, o relatório aberto ou o símbolo de uma empresa.",
    },
    "it": {
        "compare": "Seleziona “Confronta aziende”, inserisci da 2 a 5 simboli azionari separati da spazi o virgole e avvia il confronto. Il risultato offre un contesto basato su prove, non una classifica di acquisto o vendita.",
        "report": "Cerca un simbolo azionario e seleziona “Analizza”. Il rapporto mostra panoramica, riferimenti comparativi, scenari di valutazione, rischi, opportunità, notizie e documenti regolamentari con prove.",
        "profile": "Nel profilo puoi impostare esperienza, livello di dettaglio, lingua e interessi. Cambia solo la presentazione, non le prove o l’idoneità dell’investimento.",
        "general": "Usa la ricerca per analizzare un simbolo azionario o confrontare da 2 a 5 aziende. Puoi anche chiedere concetti, il rapporto aperto o il simbolo di un’azienda.",
    },
    "ar": {
        "compare": "اختر «مقارنة الشركات»، وأدخل من رمزين إلى خمسة رموز أسهم مفصولة بمسافات أو فواصل، ثم ابدأ المقارنة. النتيجة سياق قائم على الأدلة وليست ترتيبًا للشراء أو البيع.",
        "report": "ابحث عن رمز سهم واختر «تحليل». يعرض التقرير النظرة العامة والمعايير المقارنة وسيناريوهات التقييم والمخاطر والفرص والأخبار والإفصاحات التنظيمية مع الأدلة.",
        "profile": "يمكنك من الملف الشخصي ضبط الخبرة وعمق التقرير واللغة والاهتمامات. يتغير العرض فقط، ولا تتغير الأدلة أو ملاءمة الاستثمار.",
        "general": "استخدم البحث لتحليل رمز سهم أو مقارنة شركتين إلى خمس شركات. ويمكنك أيضًا السؤال عن مفهوم مالي أو التقرير المفتوح أو رمز سهم شركة.",
    },
}


def concept_key(message: str) -> str | None:
    normalized = message.casefold()
    for key, aliases in _CONCEPT_ALIASES.items():
        if any(
            re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized)
            if len(alias) <= 4 and alias.isascii()
            else alias in normalized
            for alias in aliases
        ):
            return key
    return None


@lru_cache(maxsize=128)
def concept_response(key: str, language: str, depth: str) -> str | None:
    language = language if language in _CONCEPTS else "en"
    depth = depth if depth in {"simple", "standard", "professional"} else "standard"
    entries = _CONCEPTS[language].get(key) or _CONCEPTS["en"].get(key)
    if entries is None:
        return None
    return entries.get(depth) or entries["standard"]


def site_topic(message: str) -> str:
    normalized = message.casefold()
    if any(value in normalized for value in ("compare", "comparar", "comparer", "vergleichen", "confrontare", "比較", "비교", "مقارنة", "比较")):
        return "compare"
    if any(value in normalized for value in ("profile", "perfil", "profil", "profilo", "perfil", "プロフィール", "프로필", "الملف", "画像", "preference")):
        return "profile"
    if any(value in normalized for value in ("report", "informe", "rapport", "bericht", "rapporto", "relatório", "レポート", "보고서", "تقرير", "报告")):
        return "report"
    return "general"


@lru_cache(maxsize=64)
def site_help_response(topic: str, language: str) -> str:
    language = language if language in _SITE_HELP else "en"
    return _SITE_HELP[language].get(topic, _SITE_HELP[language]["general"])


def preserve_mix(text: str, primary: str, languages: tuple[str, ...]) -> str:
    """Use a natural mixed-language lead-in without copying malformed grammar."""
    if len(languages) < 2:
        return text
    language_set = set(languages)
    if primary == "es" and "en" in language_set:
        lead = "En simple terms — "
    elif primary == "fr" and "en" in language_set:
        lead = "In simple terms — "
    elif primary == "zh" and "en" in language_set:
        lead = "简单来说 / in simple terms — "
    elif primary == "ja" and "en" in language_set:
        lead = "要点だけ言うと / in short — "
    elif primary == "ko" and "en" in language_set:
        lead = "요약하면 / in short — "
    elif primary == "de" and "en" in language_set:
        lead = "Kurz gesagt / in short — "
    elif primary == "pt" and "en" in language_set:
        lead = "Em resumo / in short — "
    elif primary == "it" and "en" in language_set:
        lead = "In breve / in short — "
    elif primary == "ar" and "en" in language_set:
        lead = "باختصار / in short — "
    elif primary == "en" and "es" in language_set:
        lead = "En resumen — "
    elif primary == "en" and "fr" in language_set:
        lead = "En bref — "
    elif primary == "en" and "zh" in language_set:
        lead = "简单来说 / in short — "
    elif primary == "en" and "ja" in language_set:
        lead = "要点だけ言うと / in short — "
    elif primary == "en" and "ko" in language_set:
        lead = "요약하면 / in short — "
    elif primary == "en" and "de" in language_set:
        lead = "Kurz gesagt / in short — "
    elif primary == "en" and "pt" in language_set:
        lead = "Em resumo / in short — "
    elif primary == "en" and "it" in language_set:
        lead = "In breve / in short — "
    elif primary == "en" and "ar" in language_set:
        lead = "باختصار / in short — "
    elif primary == "es" and "fr" in language_set:
        lead = "En bref — "
    elif primary == "fr" and "es" in language_set:
        lead = "En resumen — "
    else:
        lead = None
    if not lead:
        return text
    return lead + text
