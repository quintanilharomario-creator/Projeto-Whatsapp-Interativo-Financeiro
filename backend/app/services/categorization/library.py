"""Keyword library for transaction categorization.

Each entry is a tuple: (main_category, subcategory_or_None, keywords).
Entries are ordered from most-specific to least-specific so that when two
entries tie on score, the more-specific one appears first and wins.
Keywords with accents are stored as-is; the categorizer normalizes them at
match time via unidecode.
"""

# ── EXPENSE ENTRIES ────────────────────────────────────────────────────────────
# fmt: off
EXPENSE_ENTRIES: list[tuple[str, str | None, list[str]]] = [

    # ── Alimentação ──────────────────────────────────────────────────────────
    ("Alimentação", "Fast Food", [
        "mcdonalds", "mc donalds", "mcdonald", "mecdonalds", "macdonalds",
        "mac donald", "mc", "burger king", "burguer king", "burguer", "bk",
        "subway", "pizza hut", "dominos", "kfc", "giraffas", "habibs",
        "china in box", "fastfood", "fast food",
    ]),
    ("Alimentação", "Delivery", [
        "ifood", "rappi", "uber eats", "james delivery",
        "delivery", "pedido delivery", "entrega delivery",
    ]),
    ("Alimentação", "Bar", [
        "cerveja", "bebida", "bar", "boteco", "balada", "pub",
        "drink", "cachaca", "vodka", "vinho", "whisky", "caipirinha",
    ]),
    ("Alimentação", "Restaurante", [
        "restaurante", "almoco", "jantar", "lanchonete",
        "pizzaria", "hamburgueria", "sushi", "churrasco",
        "churrascaria", "self-service", "marmita", "comida",
    ]),
    ("Alimentação", "Mercado", [
        "mercado", "supermercado", "hortifruti", "sacolao",
        "acougue", "padaria", "mercearia", "atacadao", "atacado",
        "feira", "quitanda",
    ]),
    ("Alimentação", None, [
        "cafe", "lanche", "alimentacao", "alimento", "refeicao",
        "ifood",
    ]),

    # ── Transporte ───────────────────────────────────────────────────────────
    ("Transporte", "App", [
        "uber", "99", "indriver", "cabify", "corrida", "motorista",
    ]),
    ("Transporte", "Táxi", [
        "taxi", "taxista",
    ]),
    ("Transporte", "Combustível", [
        "gasolina", "alcool", "etanol", "diesel", "posto",
        "abastecimento", "abasteci", "combustivel",
    ]),
    ("Transporte", "Público", [
        "onibus", "busao", "metro", "trem", "brt", "vlt",
        "bilhete unico", "passagem onibus",
    ]),
    ("Transporte", "Estacionamento", [
        "estacionamento", "zona azul", "parquimetro",
        "estacionei", "manobrista", "valet",
    ]),
    ("Transporte", "Manutenção Veicular", [
        "mecanico", "oficina", "troca de oleo", "pneu",
        "borracharia", "lavagem do carro", "lava-jato", "lava jato",
        "funilaria", "pintura automotiva",
    ]),

    # ── Moradia ──────────────────────────────────────────────────────────────
    ("Moradia", "Aluguel", [
        "aluguel", "locacao", "imovel", "casa", "apartamento",
    ]),
    ("Moradia", "Condomínio", [
        "condominio", "taxa condominial",
    ]),
    ("Moradia", "Contas", [
        "luz", "energia", "conta de luz", "agua", "conta de agua",
        "gas", "gas encanado", "botijao", "internet", "wifi",
        "telefone fixo", "tv a cabo", "sky", "net",
    ]),
    ("Moradia", "Operadora", [
        "claro", "vivo", "oi", "tim",
    ]),
    ("Moradia", "Manutenção", [
        "reforma", "pintura casa", "encanador", "eletricista",
        "pedreiro", "marceneiro", "vidraceiro", "chaveiro",
        "desentupidora", "dedetizacao",
    ]),

    # ── Materiais ────────────────────────────────────────────────────────────
    ("Materiais", "Construção", [
        "cimento", "tijolo", "areia", "brita", "tinta construcao",
        "madeira", "prego", "parafuso", "construcao", "obra",
        "material de construcao", "ferragem", "ferragens",
    ]),
    ("Materiais", "Elétrica", [
        "fio eletrico", "cabo eletrico", "disjuntor", "tomada",
        "interruptor", "lampada", "led", "fita isolante",
        "material eletrico",
    ]),
    ("Materiais", "Hidráulica", [
        "cano", "tubo hidraulico", "conexao hidraulica", "registro",
        "torneira", "valvula", "sifao", "material hidraulico",
    ]),
    ("Materiais", "Ferramentas", [
        "ferramenta", "furadeira", "martelo", "chave de fenda",
        "alicate", "serra", "parafusadeira",
    ]),

    # ── Saúde ─────────────────────────────────────────────────────────────────
    ("Saúde", "Farmácia", [
        "remedio", "medicamento", "farmacia", "drogaria",
        "comprimido", "vitamina", "antibiotico",
    ]),
    ("Saúde", "Consultas", [
        "medico", "consulta", "dentista", "psicologo",
        "fisioterapeuta", "nutricionista", "ortopedista",
        "pediatra", "ginecologista", "cardiologista",
    ]),
    ("Saúde", "Exames", [
        "exame", "raio-x", "raio x", "ultrassom", "ressonancia",
        "tomografia", "laboratorio",
    ]),
    ("Saúde", "Plano de Saúde", [
        "plano de saude", "unimed", "amil", "bradesco saude",
        "sulamerica", "hapvida",
    ]),

    # ── Beleza e Cuidados ────────────────────────────────────────────────────
    ("Beleza", "Cabelo", [
        "corte de cabelo", "cabeleireiro", "salao", "barbeiro",
        "barbearia", "escova cabelo", "tintura", "mecha",
        "hidratacao capilar",
    ]),
    ("Beleza", "Unhas", [
        "manicure pedicure", "pedicure", "manicure", "esmalte",
        "unhada",
    ]),
    ("Beleza", "Estética", [
        "estetica", "massagem", "depilacao", "sobrancelha",
        "cilios", "micropigmentacao", "botox", "peeling",
    ]),
    ("Beleza", "Cosméticos", [
        "maquiagem", "batom", "base", "perfume", "creme beleza",
        "shampoo", "condicionador",
    ]),

    # ── Educação ─────────────────────────────────────────────────────────────
    ("Educação", "Mensalidade", [
        "faculdade", "escola", "mensalidade escolar",
        "colegio", "universidade", "ensino",
    ]),
    ("Educação", "Material", [
        "livro", "caderno", "apostila", "material escolar",
        "livraria",
    ]),
    ("Educação", "Curso Online", [
        "alura", "udemy", "coursera", "hotmart", "kiwify",
        "curso online", "dio",
    ]),
    ("Educação", None, [
        "curso",
    ]),

    # ── Lazer ─────────────────────────────────────────────────────────────────
    ("Lazer", "Streaming", [
        "netflix", "spotify", "amazon prime", "prime video",
        "disney+", "disney plus", "hbo max", "globoplay",
        "youtube premium", "deezer", "apple music",
        "paramount", "telecine",
    ]),
    ("Lazer", "Cinema / Show", [
        "cinema", "ingresso", "filme", "teatro", "show",
        "espetaculo",
    ]),
    ("Lazer", "Games", [
        "game", "jogo digital", "playstation", "xbox", "steam",
        "nintendo", "skin", "robux", "vbucks",
    ]),
    ("Lazer", "Viagem", [
        "viagem", "hotel", "pousada", "hospedagem", "airbnb",
        "booking", "passagem aerea", "gol", "latam", "azul",
    ]),

    # ── Vestuário ────────────────────────────────────────────────────────────
    ("Vestuário", "Roupas", [
        "roupa", "camisa", "camiseta", "calca", "vestido",
        "blusa", "casaco", "saia", "short", "bermuda",
    ]),
    ("Vestuário", "Calçados", [
        "sapato", "tenis", "sandalia", "chinelo", "bota",
        "scarpin", "salto alto",
    ]),
    ("Vestuário", "Acessórios", [
        "bolsa", "mochila", "carteira", "oculos", "relogio",
        "colar", "brinco", "pulseira",
    ]),

    # ── Pets ──────────────────────────────────────────────────────────────────
    ("Pets", "Veterinário", [
        "veterinario", "vet", "consulta vet", "vacina pet",
    ]),
    ("Pets", "Alimentação Pet", [
        "racao", "petisco", "sache", "alimento pet",
    ]),
    ("Pets", "Acessórios Pet", [
        "brinquedo pet", "coleira", "casinha", "areia gato",
    ]),

    # ── Assinaturas ──────────────────────────────────────────────────────────
    ("Assinaturas", "SaaS / Office", [
        "microsoft 365", "office", "adobe", "dropbox",
        "google one", "icloud",
    ]),
    ("Assinaturas", "Academia", [
        "academia", "smartfit", "bioritmo", "body tech",
        "pilates", "crossfit", "yoga", "personal trainer",
    ]),
    ("Assinaturas", None, [
        "assinatura", "mensalidade plano", "plano premium",
    ]),

    # ── Outros ───────────────────────────────────────────────────────────────
    ("Outros", "Doações", [
        "doacao", "ofertou", "dizimo", "igreja",
    ]),
    ("Outros", "Presentes", [
        "presente", "mimo", "lembranca", "gift",
    ]),
    ("Outros", "Cigarros", [
        "cigarro", "tabaco", "vape", "pod", "narguilé", "narguile",
    ]),
    ("Outros", "Impostos / Multas", [
        "multa", "taxa", "imposto", "ipva", "iptu", "dpvat",
    ]),
]
# fmt: on

# ── INCOME ENTRIES ─────────────────────────────────────────────────────────────
# All income uses main_category="Renda" for backward compatibility.
# Subcategory provides the detail.
# fmt: off
INCOME_ENTRIES: list[tuple[str, str | None, list[str]]] = [

    # ── Trabalho formal ──────────────────────────────────────────────────────
    ("Renda", "Salário", [
        "salario", "pagamento mensal", "contracheque", "holerite",
        "ordenado", "vencimento", "pro-labore", "prolabore",
    ]),
    ("Renda", "13º / Bônus", [
        "decimo terceiro", "13 salario", "bonus", "gratificacao",
        "premiacao", "plr", "participacao nos lucros", "ferias",
    ]),

    # ── Freelance / Serviços ─────────────────────────────────────────────────
    ("Renda", "Freelance - Tech", [
        "desenvolvimento", "programacao", "site", "sistema", "app",
        "design", "ux", "ui", "consultoria tech",
    ]),
    ("Renda", "Freelance - Beleza", [
        "manicure", "pedicure", "cabeleireiro", "escova", "maquiagem",
        "sobrancelha", "depilacao", "massagem",
        "unha", "unhas", "corte cabelo", "tintura cabelo",
    ]),
    ("Renda", "Freelance - Construção", [
        "pedreiro", "eletrica", "encanador",
        "marcenaria", "vidracaria", "reforma feita",
    ]),
    ("Renda", "Freelance - Aulas", [
        "aula particular", "professor particular",
        "monitoria", "tutoria", "mentoria",
    ]),
    ("Renda", "Freelance - Doméstico", [
        "faxina", "diarista", "limpeza", "jardinagem",
        "cuidador", "baba", "motorista particular",
    ]),
    ("Renda", "Freelance", [
        "freelance", "freela", "freelancer", "servico", "servicos",
        "pagamento servico", "consultoria", "projeto",
    ]),

    # ── Vendas ───────────────────────────────────────────────────────────────
    ("Renda", "Vendas - Online", [
        "mercado livre", "shopee", "amazon venda", "olx", "enjoei",
    ]),
    ("Renda", "Vendas - Catálogo", [
        "natura", "avon", "jequiti", "herbalife",
        "hinode", "mary kay",
    ]),
    ("Renda", "Vendas", [
        "vendi", "venda", "comprador pagou", "venda produto",
    ]),

    # ── Investimentos ────────────────────────────────────────────────────────
    ("Renda", "Investimentos", [
        "rendimento", "dividendos", "juros", "rentabilidade",
        "resgate", "lucro investimento", "vendi acao",
        "vendi cripto", "bitcoin", "cripto",
    ]),

    # ── Aluguel ──────────────────────────────────────────────────────────────
    ("Renda", "Aluguel Recebido", [
        "aluguel recebido", "inquilino pagou",
        "aluguel do imovel", "locacao recebida",
    ]),

    # ── Outros recebimentos ──────────────────────────────────────────────────
    ("Renda", "Reembolso", [
        "reembolso", "devolucao", "estorno", "ressarcimento",
    ]),
    ("Renda", "Presentes", [
        "ganhei de", "presente recebido", "mesada", "ajuda",
    ]),
    ("Renda", "Comissão", [
        "comissao", "indicacao", "afiliado",
    ]),
    ("Renda", None, [
        "renda", "receita", "lucro", "ganho",
    ]),
]
# fmt: on
