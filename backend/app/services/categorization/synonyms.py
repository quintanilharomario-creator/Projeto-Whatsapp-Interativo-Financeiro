"""Verb synonyms for transaction type detection (income / expense / query)."""

INCOME_VERBS: frozenset[str] = frozenset(
    [
        "recebi",
        "ganhei",
        "entrou",
        "caiu",
        "faturei",
        "embolsei",
        "levei",
        "peguei",
        "lucrei",
        "conquistei",
        "captei",
        "arrecadei",
        "obtive",
        "alcancei",
        "consegui",
        "fechei",
        "veio",
        "pingou",
        "recebimento",
        "depositaram",
        "caiu na conta",
        "caiu o pix",
        "pix recebido",
        "transferencia recebida",
        "deposito",
    ]
)

EXPENSE_VERBS: frozenset[str] = frozenset(
    [
        "gastei",
        "paguei",
        "saiu",
        "comprei",
        "torrei",
        "queimei",
        "fui",
        "mandei",
        "dei",
        "soltei",
        "deixei",
        "desembolsei",
        "investi",
        "apliquei",
        "custou",
        "foi",
        "perdi",
        "desperdicei",
        "esbanjei",
        "fritei",
        "escorri",
        "derreti",
    ]
)

QUERY_VERBS: frozenset[str] = frozenset(
    [
        "saldo",
        "extrato",
        "resumo",
        "quanto",
        "relatorio",
        "relatorio",
        "gastos",
        "sobrou",
        "sobra",
        "tenho",
        "balanco",
        "balanço",
        "movimentacao",
        "movimentacoes",
        "transacao",
        "transacoes",
    ]
)
