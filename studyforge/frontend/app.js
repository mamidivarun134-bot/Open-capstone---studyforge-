/* StudyForge frontend — no build step, no framework: talks directly to the FastAPI backend. */

const API = ""; // same-origin: FastAPI serves this file too
let token = localStorage.getItem("sf_token") || null;
let userEmail = localStorage.getItem("sf_email") || "";
let currentQuestion = null;
let masteryChart = null;

// ---------- API helper ----------
async function api(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body && !isForm) headers["Content-Type"] = "application/json";

  const resp = await fetch(API + path, {
    method,
    headers,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  });

  const contentType = resp.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await resp.json() : null;

  if (!resp.ok) {
    const message = (data && data.detail) || `Request failed (${resp.status})`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}

// ---------- View routing ----------
function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("is-active"));
  document.getElementById(`view-${name}`).classList.add("is-active");
  document.querySelectorAll(".rail-link").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.view === name);
  });
  if (name === "library") loadDocuments();
  if (name === "progress") loadDashboard();
}

document.getElementById("nav").addEventListener("click", (e) => {
  const btn = e.target.closest(".rail-link");
  if (btn) showView(btn.dataset.view);
});

function enterApp() {
  document.getElementById("nav").hidden = false;
  document.getElementById("railFoot").hidden = false;
  document.getElementById("userEmail").textContent = userEmail;
  showView("library");
}

function logout() {
  token = null;
  userEmail = "";
  localStorage.removeItem("sf_token");
  localStorage.removeItem("sf_email");
  document.getElementById("nav").hidden = true;
  document.getElementById("railFoot").hidden = true;
  showView("auth");
}

document.getElementById("logoutBtn").addEventListener("click", logout);

// ---------- Auth ----------
let authMode = "login";

document.querySelectorAll(".auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    authMode = tab.dataset.tab;
    document.querySelectorAll(".auth-tab").forEach((t) => t.classList.toggle("is-active", t === tab));
    document.getElementById("authSubmit").textContent = authMode === "login" ? "Sign in" : "Create account";
    document.getElementById("authError").hidden = true;
  });
});

document.getElementById("authForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("authEmail").value.trim();
  const password = document.getElementById("authPassword").value;
  const errorEl = document.getElementById("authError");
  const submitBtn = document.getElementById("authSubmit");
  errorEl.hidden = true;
  submitBtn.disabled = true;

  try {
    let data;
    if (authMode === "register") {
      data = await api("/api/auth/register", { method: "POST", body: { email, password } });
    } else {
      const form = new URLSearchParams();
      form.set("username", email);
      form.set("password", password);
      data = await api("/api/auth/login", { method: "POST", body: form, isForm: true });
    }
    token = data.access_token;
    userEmail = email;
    localStorage.setItem("sf_token", token);
    localStorage.setItem("sf_email", email);
    enterApp();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  } finally {
    submitBtn.disabled = false;
  }
});

// ---------- Library ----------
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");

document.getElementById("browseBtn").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) uploadFile(fileInput.files[0]);
});

["dragover", "dragenter"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

async function uploadFile(file) {
  const errorEl = document.getElementById("uploadError");
  const processingRow = document.getElementById("uploadingRow");
  errorEl.hidden = true;

  if (file.type !== "application/pdf") {
    errorEl.textContent = "Only PDF files are supported right now.";
    errorEl.hidden = false;
    return;
  }

  processingRow.hidden = false;
  try {
    const form = new FormData();
    form.append("file", file);
    await api("/api/documents/upload", { method: "POST", body: form, isForm: true });
    await loadDocuments();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  } finally {
    processingRow.hidden = true;
    fileInput.value = "";
  }
}

async function loadDocuments() {
  const list = document.getElementById("docList");
  const emptyNote = document.getElementById("docEmptyNote");
  try {
    const docs = await api("/api/documents");
    list.innerHTML = "";
    emptyNote.hidden = docs.length > 0;
    docs.forEach((doc) => {
      const li = document.createElement("li");
      li.className = "doc-item";
      const meta =
        doc.status === "ready"
          ? `${doc.page_count} page${doc.page_count === 1 ? "" : "s"}${doc.ocr_pages ? ` · ${doc.ocr_pages} via OCR` : ""}`
          : doc.error_message || "Processing…";
      li.innerHTML = `
        <div>
          <div class="doc-name">${escapeHtml(doc.filename)}</div>
          <div class="doc-meta">${escapeHtml(meta)}</div>
        </div>
        <span class="doc-status ${doc.status}">${doc.status}</span>
      `;
      list.appendChild(li);
    });
  } catch (err) {
    console.error(err);
  }
}

// ---------- Ask ----------
document.getElementById("askForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("askInput");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";

  const thread = document.getElementById("askThread");
  const item = document.createElement("div");
  item.className = "ask-item";
  item.innerHTML = `<div class="ask-question">${escapeHtml(question)}</div><div class="ask-answer">Thinking…</div>`;
  thread.prepend(item);

  try {
    const data = await api("/api/qa/ask", { method: "POST", body: { question } });
    const answerEl = item.querySelector(".ask-answer");
    answerEl.textContent = data.answer;

    if (data.citations.length) {
      const citeList = document.createElement("div");
      citeList.className = "citation-list";
      data.citations.forEach((c, i) => {
        const div = document.createElement("div");
        div.className = "citation";
        div.innerHTML = `<span class="cite-src">[${i + 1}] ${escapeHtml(c.document_filename)}${
          c.page_number ? ` · p.${c.page_number}` : ""
        }</span>${escapeHtml(c.excerpt)}`;
        citeList.appendChild(div);
      });
      item.appendChild(citeList);
    }
  } catch (err) {
    item.querySelector(".ask-answer").textContent = `Error: ${err.message}`;
  }
});

// ---------- Quiz ----------
document.getElementById("startQuizBtn").addEventListener("click", loadNextQuestion);

async function loadNextQuestion() {
  const area = document.getElementById("quizArea");
  area.innerHTML = `<div class="processing-row"><span class="spinner"></span> Picking your next question…</div>`;
  try {
    currentQuestion = await api("/api/quiz/next", { method: "POST" });
    renderQuestion();
  } catch (err) {
    area.innerHTML = `<p class="form-error">${escapeHtml(err.message)}</p><button class="btn-primary" id="retryQuizBtn">Try again</button>`;
    document.getElementById("retryQuizBtn").addEventListener("click", loadNextQuestion);
  }
}

function renderQuestion() {
  const area = document.getElementById("quizArea");
  const q = currentQuestion;
  area.innerHTML = `
    <div class="quiz-card">
      <div class="quiz-meta">
        <span class="pill">${escapeHtml(q.topic_name)}</span>
        <span class="pill">${escapeHtml(q.difficulty)}</span>
      </div>
      <p class="quiz-question">${escapeHtml(q.question_text)}</p>
      <div class="quiz-options">
        ${q.options
          .map((opt, i) => `<button class="quiz-option" data-index="${i}">${escapeHtml(opt)}</button>`)
          .join("")}
      </div>
      <div id="quizFeedback"></div>
    </div>
  `;
  area.querySelectorAll(".quiz-option").forEach((btn) => {
    btn.addEventListener("click", () => submitAnswer(parseInt(btn.dataset.index, 10)));
  });
}

async function submitAnswer(selectedIndex) {
  const options = document.querySelectorAll(".quiz-option");
  options.forEach((b) => (b.disabled = true));

  try {
    const result = await api("/api/quiz/answer", {
      method: "POST",
      body: { question_id: currentQuestion.id, selected_option_index: selectedIndex },
    });

    options[selectedIndex].classList.add(result.is_correct ? "correct" : "incorrect");
    if (!result.is_correct) options[result.correct_option_index].classList.add("correct");

    const feedback = document.getElementById("quizFeedback");
    feedback.innerHTML = `
      <div class="quiz-feedback">
        <div class="verdict ${result.is_correct ? "correct" : "incorrect"}">${
      result.is_correct ? "Correct" : "Not quite"
    }</div>
        <p class="quiz-explanation">${escapeHtml(result.explanation)}</p>
        <button class="btn-primary" id="nextQuestionBtn">Next question</button>
      </div>
    `;
    document.getElementById("nextQuestionBtn").addEventListener("click", loadNextQuestion);
  } catch (err) {
    alert(err.message);
  }
}

// ---------- Progress ----------
async function loadDashboard() {
  try {
    const data = await api("/api/dashboard/mastery");
    document.getElementById("overallMastery").textContent = `${Math.round(data.overall_mastery * 100)}%`;
    document.getElementById("weakestTopic").textContent = data.weakest_topic || "—";

    const emptyNote = document.getElementById("progressEmptyNote");
    const canvas = document.getElementById("masteryChart");
    emptyNote.hidden = data.topics.length > 0;
    canvas.style.display = data.topics.length > 0 ? "block" : "none";

    if (data.topics.length > 0) {
      const ctx = canvas.getContext("2d");
      const labels = data.topics.map((t) => t.topic_name);
      const values = data.topics.map((t) => Math.round(t.mastery_score * 100));

      if (masteryChart) masteryChart.destroy();
      masteryChart = new Chart(ctx, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: "Mastery %",
              data: values,
              backgroundColor: "#d3934a",
              borderRadius: 6,
            },
          ],
        },
        options: {
          scales: {
            y: { beginAtZero: true, max: 100, ticks: { color: "#9a9fb0" }, grid: { color: "#3a4055" } },
            x: { ticks: { color: "#9a9fb0" }, grid: { display: false } },
          },
          plugins: { legend: { display: false } },
        },
      });
    }
  } catch (err) {
    console.error(err);
  }
}

// ---------- Utils ----------
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------- Boot ----------
if (token) {
  enterApp();
} else {
  showView("auth");
}
