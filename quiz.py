QUESTIONS = [
    {
        "id": "moment",
        "text": "Em que momento uma pausa gostosa faria diferença no seu dia?",
        "options": [
            {"id": "between_tasks", "text": "Entre um compromisso e outro", "profile": "pratica"},
            {"id": "afternoon", "text": "Na pausa tranquila da tarde", "profile": "pausa"},
            {"id": "after_movement", "text": "Depois de um dia em movimento", "profile": "equilibrio"},
            {"id": "with_people", "text": "Quando estou reunindo gente querida", "profile": "curiosa"},
        ],
    },
    {
        "id": "flavor",
        "text": "Qual clima de sabor combina mais com você?",
        "options": [
            {"id": "classic", "text": "Clássico e sem erro", "profile": "pratica"},
            {"id": "fresh", "text": "Leve e cheio de frescor", "profile": "equilibrio"},
            {"id": "comfort", "text": "Aconchegante e bem cremoso", "profile": "pausa"},
            {"id": "surprise", "text": "Uma combinação que surpreende", "profile": "curiosa"},
        ],
    },
    {
        "id": "choice",
        "text": "Na hora de escolher uma empada ou quiche, o que pesa mais?",
        "options": [
            {"id": "easy", "text": "Ser prática para levar comigo", "profile": "pratica"},
            {"id": "ingredients", "text": "Ingredientes que parecem de verdade", "profile": "equilibrio"},
            {"id": "comfort_food", "text": "Aquela sensação de comida feita com carinho", "profile": "pausa"},
            {"id": "new", "text": "Experimentar algo que ainda não provei", "profile": "curiosa"},
        ],
    },
    {
        "id": "fit_line",
        "text": "O que você mais quer descobrir na Linha Fit da Sulamita?",
        "options": [
            {"id": "routine", "text": "Uma opção gostosa para a rotina", "profile": "pratica"},
            {"id": "balance", "text": "Mais equilíbrio sem abrir mão do sabor", "profile": "equilibrio"},
            {"id": "pleasure", "text": "Uma pausa leve que continua sendo prazerosa", "profile": "pausa"},
            {"id": "novelty", "text": "Novos sabores para sair do óbvio", "profile": "curiosa"},
        ],
    },
]

PROFILES = {
    "pratica": {
        "title": "Sabor que acompanha seu ritmo",
        "description": "Você gosta de escolhas gostosas que cabem na vida real. A Linha Fit pode ser uma nova companhia para os seus dias corridos.",
        "accent": "Seu dia tem movimento — sua pausa também pode ter sabor.",
    },
    "equilibrio": {
        "title": "Leveza com sabor de verdade",
        "description": "Para você, equilíbrio não precisa significar abrir mão do prazer. Você procura ingredientes e sabores que façam sentido na sua rotina.",
        "accent": "Um momento para se cuidar do seu jeito.",
    },
    "pausa": {
        "title": "Sua pausa merece carinho",
        "description": "Você transforma uma pausa simples em um momento especial. Sabor, aconchego e cuidado fazem parte da experiência.",
        "accent": "Respira, aproveita e saboreia.",
    },
    "curiosa": {
        "title": "Novos sabores, novas histórias",
        "description": "Você adora descobrir combinações e experimentar novidades. O lançamento da Linha Fit é um convite para provar algo diferente.",
        "accent": "A próxima descoberta pode ser a sua favorita.",
    },
}


def calculate_profile(answers):
    scores = {profile: 0 for profile in PROFILES}
    for question in QUESTIONS:
        answer_id = answers[question["id"]]
        option = next(option for option in question["options"] if option["id"] == answer_id)
        scores[option["profile"]] += 1

    # Stable tie-break: the first profile encountered in the participant's answers wins.
    for question in QUESTIONS:
        answer_id = answers[question["id"]]
        option = next(option for option in question["options"] if option["id"] == answer_id)
        if scores[option["profile"]] == max(scores.values()):
            return option["profile"]
