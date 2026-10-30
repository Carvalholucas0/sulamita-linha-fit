QUIZ_VERSION = "sulalover-2026-10-29-v2"
CAMPAIGN_SOURCE = "Evento Linha Fit — São Francisco — 31/10/2026"
MARKETING_CONSENT_VERSION = "whatsapp-ofertas-v1"
PRIVACY_NOTICE_VERSION = "privacy-notice-2026-10-29-v1"

QUESTIONS = [
    {
        "id": "frequency",
        "text": "Como anda sua história com a Sulamita?",
        "options": [
            {"id": "weekly", "text": "Toda semana tem Sulamita. Já faz parte da rotina!", "profile": None},
            {"id": "monthly", "text": "Uma ou duas vezes por mês a gente se encontra.", "profile": None},
            {"id": "occasionally", "text": "De vez em quando, quando bate aquela saudade.", "profile": None},
            {"id": "first_time", "text": "Nossa história tá começando agora. Prazer, Sulamita! 🤎", "profile": None},
        ],
    },
    {
        "id": "occasion",
        "text": "Qual momento mais pede uma Sulamita?",
        "options": [
            {"id": "any_day", "text": "Qualquer dia merece esse carinho.", "profile": "raiz"},
            {"id": "at_home", "text": "O momento em casa, com um pedido chegando e tudo no meu tempo.", "profile": "nutella"},
            {"id": "after_workout", "text": "Depois da corrida, caminhada ou treino. Afinal, eu treino pra isso!", "profile": "no_pique"},
            {"id": "gathering", "text": "Os encontros com as pessoas que eu amo. Sempre cabe mais um à mesa!", "profile": "mesa_cheia"},
        ],
    },
    {
        "id": "product",
        "text": "Na vitrine, seu olho vai primeiro para?",
        "options": [
            {"id": "quiches", "text": "Vou nas quiches gratinadas, tem sabor que conquista de primeira!", "profile": "raiz"},
            {"id": "fit_line", "text": "As opções da linha fit. Quero conhecer os sabores!", "profile": "no_pique"},
            {"id": "sweets", "text": "Sou Team docinho! Já posso escolher a sobremesa?", "profile": "formiguinha"},
            {"id": "empadao", "text": "Um empadão pra compartilhar!", "profile": "mesa_cheia"},
        ],
    },
    {
        "id": "experience",
        "text": "Qual experiência com a Sulamita mais combina com você?",
        "options": [
            {"id": "store_combo", "text": "Passar no bistrô e levar o meu combo favorito.", "profile": "raiz"},
            {"id": "delivery", "text": "Pedir no iFood e receber no conforto de casa.", "profile": "nutella"},
            {"id": "coffee_chat", "text": "Sentar na loja pra um café e deixar a conversa render.", "profile": "formiguinha"},
            {"id": "celebration", "text": "Encomendar pra servir num almoço ou comemoração.", "profile": "mesa_cheia"},
        ],
    },
    {
        "id": "news",
        "text": "Que notícia da Sulamita você ia adorar receber?",
        "options": [
            {"id": "home_orders", "text": "Novidades e facilidades pra pedir de casa.", "profile": "nutella"},
            {"id": "fit_news", "text": "Tudo que chegar de novo na linha fit.", "profile": "no_pique"},
            {"id": "new_flavors", "text": "Os sabores que acabaram de chegar.", "profile": "formiguinha"},
            {"id": "surprise", "text": "Um pouquinho de tudo. Pode me surpreender!", "profile": None},
        ],
    },
]

PROFILES = {
    "raiz": {
        "title": "SulaLover Raiz 🤎",
        "description": "Você é de transformar coisa boa em tradição: ter seus favoritos, indicar pra quem gosta e incluir a Sulamita nos dias comuns e nas comemorações. É esse carinho de quem é de casa que acompanha a gente desde as empadas na rua.",
        "icon": "hand-empada.png",
    },
    "nutella": {
        "title": "SulaLover Nutella 🛋️",
        "description": "Tem pedido chegando, mesa posta do seu jeito e aquela alegria de abrir a embalagem. De uma empada só sua a um empadão pra dividir, você sabe receber um carinho sem sair de casa. E a gente adora fazer parte desse momento.",
        "icon": "sparkle-badge.png",
    },
    "no_pique": {
        "title": "SulaLover No Pique ☀️",
        "description": "Depois da corrida, da caminhada ou entre os compromissos, você gosta de descobrir sabores que combinem com a sua rotina. A linha fit chega pra entrar nesses encontros: você traz seu pique e a gente prepara sua próxima pausa.",
        "icon": "no-pique.png",
    },
    "formiguinha": {
        "title": "SulaLover Formiguinha 🍰",
        "description": "Seu olhar encontra um doce e já começa a imaginar o primeiro pedaço. Um café, uma boa conversa e uma doçura no meio do dia têm um lugar especial no seu coração. Por aqui, a gente adora preparar esses pequenos encontros.",
        "icon": "formiguinha.png",
    },
    "mesa_cheia": {
        "title": "SulaLover Mesa Cheia 🥧",
        "description": "Você puxa a cadeira, chama mais um e já pensa no que vai servir. Do empadão no almoço à comemoração com a turma, a Sulamita entra no meio da mesa e vira parte das boas lembranças. Com você, carinho sempre rende mais uma porção.",
        "icon": "table-star.png",
    },
}

LEGACY_PROFILES = {
    "pratica": {"title": "Sabor que acompanha seu ritmo"},
    "equilibrio": {"title": "Leveza com sabor de verdade"},
    "pausa": {"title": "Sua pausa merece carinho"},
    "curiosa": {"title": "Novos sabores, novas histórias"},
}
ALL_PROFILES = {**LEGACY_PROFILES, **PROFILES}


def calculate_profile(answers):
    scores = {profile: 0 for profile in PROFILES}
    selected_profiles = {}

    for question in QUESTIONS:
        answer_id = answers[question["id"]]
        option = next(option for option in question["options"] if option["id"] == answer_id)
        profile_id = option["profile"]
        selected_profiles[question["id"]] = profile_id
        if profile_id:
            scores[profile_id] += 1

    highest_score = max(scores.values())
    tied_profiles = {
        profile_id for profile_id, score in scores.items() if score == highest_score
    }

    for question_id in ("product", "occasion", "experience", "news"):
        profile_id = selected_profiles[question_id]
        if profile_id in tied_profiles:
            return profile_id

    raise ValueError("Não foi possível desempatar o resultado do quiz.")


def build_answer_snapshot(answers):
    snapshot = {}
    for question in QUESTIONS:
        answer_id = answers[question["id"]]
        option = next(option for option in question["options"] if option["id"] == answer_id)
        snapshot[question["id"]] = {
            "question": question["text"],
            "answer_id": answer_id,
            "answer": option["text"],
        }
    return snapshot


def build_score_snapshot(answers):
    scores = {profile_id: 0 for profile_id in PROFILES}
    for question in QUESTIONS:
        option = next(
            option for option in question["options"] if option["id"] == answers[question["id"]]
        )
        if option["profile"]:
            scores[option["profile"]] += 1
    return scores


def build_declared_preferences(answers):
    return {
        "frequency": answers["frequency"],
        "occasion": answers["occasion"],
        "product_interest": answers["product"],
        "experience_preference": answers["experience"],
        "communication_interest": answers["news"],
    }


def option_label(question_id, option_id):
    question = next(question for question in QUESTIONS if question["id"] == question_id)
    option = next(
        (option for option in question["options"] if option["id"] == option_id),
        None,
    )
    return option["text"] if option else ""


def format_preference(question_id, option_id):
    label = option_label(question_id, option_id)
    if not label:
        return option_id or ""
    return f"{option_id}: {label}"
