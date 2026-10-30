const screens = {
    welcome: document.getElementById("welcome-screen"),
    signup: document.getElementById("signup-screen"),
    quiz: document.getElementById("quiz-screen"),
    result: document.getElementById("result-screen"),
};
const form = document.getElementById("customer-form");
const answers = {};
const errorFields = ["name", "whatsapp", "neighborhood", "data-consent"];
let questions = [];
let questionIndex = 0;
let participant = null;
const submissionKeys = new Map();

function showScreen(screen, focusSelector) {
    Object.values(screens).forEach((element) => {
        element.hidden = element !== screen;
    });
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
    window.scrollTo({ top: 0, behavior });
    if (focusSelector) {
        window.requestAnimationFrame(() => {
            const target = document.querySelector(focusSelector);
            if (!target) return;
            target.focus({ preventScroll: true });
            target.scrollIntoView({ block: "nearest", behavior });
        });
    }
}

function setError(element, message = "") {
    element.textContent = message;
}

function setFieldError(field, message = "") {
    const element = document.getElementById(`${field}-error`);
    const input = document.getElementById(field);
    if (element) element.textContent = message;
    if (input) input.setAttribute("aria-invalid", message ? "true" : "false");
}

function focusField(field) {
    const input = document.getElementById(field);
    if (!input) return;
    input.focus();
    input.scrollIntoView({ block: "center", behavior: "smooth" });
}

function clearErrors() {
    errorFields.forEach((field) => setFieldError(field));
    setError(document.getElementById("form-error"));
}

function createSubmissionKey() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
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
        ? 'Concluir e participar <span aria-hidden="true">→</span>'
        : 'Continuar <span aria-hidden="true">→</span>';
    nextButton.disabled = !answers[question.id];
}

function renderResult(profile) {
    document.getElementById("result-title").textContent = profile.title;
    document.getElementById("result-description").textContent = profile.description;
    const icon = document.getElementById("result-icon");
    icon.src = `/static/img/${encodeURIComponent(profile.icon)}`;
    icon.alt = "";
    showScreen(screens.result, "#result-title");
}

document.getElementById("open-signup").addEventListener("click", () => {
    clearErrors();
    showScreen(screens.signup, "#name");
});

document.getElementById("prev-btn").addEventListener("click", () => {
    if (questionIndex > 0) {
        questionIndex -= 1;
        renderQuestion();
    } else {
        showScreen(screens.signup, "#name");
    }
});

async function submitQuiz(button) {
    const formData = new FormData(form);
    const payload = {
        ...participant,
        marketing_consent: formData.get("marketing_consent") === "on",
        answers,
    };
    const payloadSignature = JSON.stringify(payload);
    if (!submissionKeys.has(payloadSignature)) {
        submissionKeys.set(payloadSignature, createSubmissionKey());
    }
    payload.submission_key = submissionKeys.get(payloadSignature);

    button.disabled = true;
    button.textContent = "Salvando sua participação...";
    setError(document.getElementById("quiz-error"));
    try {
        const response = await fetch("/api/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const result = await response.json();
        if (!response.ok) {
            if (result.field && document.getElementById(`${result.field}-error`)) {
                showScreen(screens.signup, `#${result.field}`);
                setFieldError(result.field, result.error);
            } else {
                throw new Error(result.error || "Não foi possível salvar sua participação.");
            }
            return;
        }
        renderResult(result.profile);
    } catch (error) {
        setError(
            document.getElementById("quiz-error"),
            `${error.message} Confira sua conexão e tente novamente; suas respostas continuam preenchidas.`,
        );
        button.textContent = "Tentar novamente →";
    } finally {
        button.disabled = false;
    }
}

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

    await submitQuiz(document.getElementById("next-btn"));
});

function validateSignup(payload) {
    const digits = payload.whatsapp.replace(/\D/g, "");
    const nationalNumber = digits.startsWith("55") && [12, 13].includes(digits.length)
        ? digits.slice(2)
        : [10, 11].includes(digits.length) ? digits : "";
    const areaCode = nationalNumber.slice(0, 2);
    const subscriber = nationalNumber.slice(2);
    const validPhone = Boolean(nationalNumber)
        && !areaCode.startsWith("0")
        && !subscriber.startsWith("0");

    if (!payload.name.trim()) setFieldError("name", "Informe seu primeiro nome.");
    if (!validPhone) setFieldError("whatsapp", "Confira o número e o DDD do WhatsApp.");
    if (!payload.neighborhood.trim()) setFieldError("neighborhood", "Informe seu bairro e cidade.");
    if (!payload.data_consent) {
        setFieldError("data-consent", "É necessário aceitar o aviso para concluir o cadastro.");
    }
    const firstInvalid = errorFields.find((field) => {
        const error = document.getElementById(`${field}-error`);
        return error && error.textContent;
    });
    if (firstInvalid) focusField(firstInvalid);
    return !firstInvalid;
}

form.addEventListener("input", (event) => {
    if (errorFields.includes(event.target.id)) setFieldError(event.target.id);
});

form.addEventListener("change", (event) => {
    if (errorFields.includes(event.target.id)) setFieldError(event.target.id);
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors();

    const formData = new FormData(form);
    const payload = {
        name: formData.get("name"),
        whatsapp: formData.get("whatsapp"),
        neighborhood: formData.get("neighborhood"),
        data_consent: formData.get("data_consent") === "on",
        marketing_consent: formData.get("marketing_consent") === "on",
        answers,
    };
    if (!validateSignup(payload)) return;

    const button = document.getElementById("start-quiz");
    button.disabled = true;
    setError(document.getElementById("form-error"));
    try {
        await loadQuestions();
        participant = {
            name: payload.name,
            whatsapp: payload.whatsapp,
            neighborhood: payload.neighborhood,
            data_consent: payload.data_consent,
        };
        questionIndex = 0;
        renderQuestion();
        showScreen(screens.quiz, "#question-text");
    } catch (error) {
        const message = document.getElementById("form-error");
        setError(message, error.message);
        message.focus();
    } finally {
        button.disabled = false;
    }
});
