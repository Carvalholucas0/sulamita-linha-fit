const screens = {
    welcome: document.getElementById("welcome-screen"),
    quiz: document.getElementById("quiz-screen"),
    result: document.getElementById("result-screen"),
};
const form = document.getElementById("customer-form");
const answers = {};
let questions = [];
let questionIndex = 0;

function showScreen(screen) {
    Object.values(screens).forEach((element) => {
        element.hidden = element !== screen;
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
}

function setError(element, message = "") {
    element.textContent = message;
}

async function loadQuestions() {
    const response = await fetch("/api/questions");
    if (!response.ok) throw new Error("Não foi possível carregar o quiz.");
    questions = await response.json();
    document.getElementById("total-questions").textContent = questions.length;
}

function renderQuestion() {
    const question = questions[questionIndex];
    document.getElementById("current-question").textContent = questionIndex + 1;
    document.getElementById("question-text").textContent = question.text;
    document.getElementById("progress-fill").style.width =
        `${((questionIndex + 1) / questions.length) * 100}%`;
    const optionsContainer = document.getElementById("options-container");
    optionsContainer.replaceChildren();

    question.options.forEach((option, index) => {
        const label = document.createElement("label");
        label.className = "option";
        const input = document.createElement("input");
        input.type = "radio";
        input.name = question.id;
        input.value = option.id;
        input.checked = answers[question.id] === option.id;
        const marker = document.createElement("span");
        marker.className = "option-marker";
        marker.textContent = String.fromCharCode(65 + index);
        const text = document.createElement("span");
        text.className = "option-text";
        text.textContent = option.text;
        label.append(input, marker, text);
        label.addEventListener("click", () => {
            answers[question.id] = option.id;
            optionsContainer.querySelectorAll(".option").forEach((item) => item.classList.remove("selected"));
            label.classList.add("selected");
            document.getElementById("next-btn").disabled = false;
            setError(document.getElementById("quiz-error"));
        });
        if (input.checked) label.classList.add("selected");
        optionsContainer.append(label);
    });

    document.getElementById("prev-btn").style.visibility = questionIndex === 0 ? "hidden" : "visible";
    const nextButton = document.getElementById("next-btn");
    nextButton.innerHTML = questionIndex === questions.length - 1
        ? 'Ver meu resultado <span aria-hidden="true">→</span>'
        : 'Continuar <span aria-hidden="true">→</span>';
    nextButton.disabled = !answers[question.id];
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setError(document.getElementById("form-error"));
    try {
        await loadQuestions();
        showScreen(screens.quiz);
        questionIndex = 0;
        renderQuestion();
    } catch (error) {
        setError(document.getElementById("form-error"), error.message);
    }
});

document.getElementById("prev-btn").addEventListener("click", () => {
    if (questionIndex > 0) {
        questionIndex -= 1;
        renderQuestion();
    } else {
        showScreen(screens.welcome);
    }
});

document.getElementById("next-btn").addEventListener("click", async () => {
    if (!answers[questions[questionIndex].id]) {
        setError(document.getElementById("quiz-error"), "Escolha uma opção para continuar.");
        return;
    }
    if (questionIndex < questions.length - 1) {
        questionIndex += 1;
        renderQuestion();
        return;
    }

    const button = document.getElementById("next-btn");
    button.disabled = true;
    setError(document.getElementById("quiz-error"));
    const formData = new FormData(form);
    try {
        const response = await fetch("/api/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: formData.get("name"),
                whatsapp: formData.get("whatsapp"),
                email: formData.get("email"),
                consent: formData.get("consent") === "on",
                marketing_consent: formData.get("marketing_consent") === "on",
                answers,
            }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Não foi possível registrar sua participação.");
        document.getElementById("result-title").textContent = result.profile.title;
        document.getElementById("result-description").textContent = result.profile.description;
        document.getElementById("result-accent").textContent = result.profile.accent;
        showScreen(screens.result);
    } catch (error) {
        setError(document.getElementById("quiz-error"), error.message);
        button.disabled = false;
    }
});
