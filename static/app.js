// ─────────────────────────────────────────────────────────────
// Field Companion — the chat page's behaviour.
// Sends questions to our Flask backend (/api/chat) and shows the answers.
// ─────────────────────────────────────────────────────────────

// Chapter names, used for the Contents list AND for labelling answer sources.
const CHAPTERS = [
  ["00", "Prologue"],
  ["01", "The Lure of Adventure"],
  ["02", "Infernal Place"],
  ["03", "The Malaysia Job"],
  ["04", "A Normal Life"],
  ["05", "Hector Alcazar"],
  ["06", "Once a Thief"],
  ["07", "Lights Out"],
  ["08", "The Grave of Henry Avery"],
  ["09", "Those Who Prove Worthy"],
  ["10", "The Twelve Towers"],
];
const CHAPTER_TITLES = Object.fromEntries(CHAPTERS);

// Friendly names for the data files that aren't chapters.
const FILE_LABELS = {
  "characters.txt": "Characters",
  "uncharted4_a_thiefs_end.txt": "Story",
  "uncharted4_collectibles.txt": "Collectibles",
};

// Page elements we need to work with.
const form = document.querySelector("#ask-form");
const input = document.querySelector("#question");
const sendButton = document.querySelector("#send");
const log = document.querySelector("#log");
const emptyState = document.querySelector("#empty");
const clearButton = document.querySelector("#clear");
const statusDot = document.querySelector("#status-dot");
const statusText = document.querySelector("#status-text");
const chatSection = document.querySelector("#ask");

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let waiting = false; // true while we're waiting for an answer


// ── Turning file names into labels ───────────────────────────
// "uncharted4_ch08_grave_of_henry_avery.txt" -> "Ch. 08 · The Grave of Henry Avery"
function sourceLabel(file) {
  if (FILE_LABELS[file]) return FILE_LABELS[file];

  const match = file.match(/_ch(\d{2})_/);
  if (match) {
    const number = match[1];
    if (number === "00") return "Prologue";
    const title = CHAPTER_TITLES[number];
    return title ? `Ch. ${number} · ${title}` : `Ch. ${number}`;
  }
  return file.replace(/\.txt$/, "").replace(/_/g, " ");
}


// ── A small, safe Markdown renderer ──────────────────────────
// Gemini replies in Markdown (**bold**, lists...). We first escape all HTML
// so nothing in the reply can inject code into the page, then convert the
// few Markdown features we need.
function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderInline(text) {
  return text
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\s][^*]*)\*(?!\*)/g, "$1<em>$2</em>");
}

function renderMarkdown(markdown) {
  const lines = escapeHtml(markdown.trim()).split(/\r?\n/);
  let html = "";
  let paragraph = [];
  let openList = null; // "ul", "ol" or null

  const flushParagraph = () => {
    if (paragraph.length) html += `<p>${renderInline(paragraph.join(" "))}</p>`;
    paragraph = [];
  };
  const closeList = () => {
    if (openList) html += `</${openList}>`;
    openList = null;
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    let match;

    if (line === "") {
      flushParagraph();
      closeList();
    } else if ((match = line.match(/^#{1,6}\s+(.*)$/))) {
      flushParagraph();
      closeList();
      html += `<h4>${renderInline(match[1])}</h4>`;
    } else if ((match = line.match(/^[-*•]\s+(.*)$/))) {
      flushParagraph();
      if (openList !== "ul") { closeList(); html += "<ul>"; openList = "ul"; }
      html += `<li>${renderInline(match[1])}</li>`;
    } else if ((match = line.match(/^(\d+)[.)]\s+(.*)$/))) {
      flushParagraph();
      if (openList !== "ol") { closeList(); html += `<ol start="${match[1]}">`; openList = "ol"; }
      html += `<li>${renderInline(match[2])}</li>`;
    } else {
      closeList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  closeList();
  return html;
}


// ── Building chat entries ────────────────────────────────────
function makeLabel(text, withDot) {
  const label = document.createElement("p");
  label.className = "flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-paper/60";
  if (withDot) {
    const dot = document.createElement("span");
    dot.className = "size-1.5 rounded-full bg-accent";
    dot.setAttribute("aria-hidden", "true");
    label.append(dot);
  }
  label.append(text);
  return label;
}

function addQuestionEntry(question) {
  const entry = document.createElement("article");
  entry.className = "entry-in";

  const text = document.createElement("p");
  text.className = "mt-2 font-display italic text-2xl sm:text-3xl leading-tight text-paper";
  text.textContent = question; // textContent = shown as plain text, never as HTML

  entry.append(makeLabel("You", false), text);
  log.append(entry);
  return entry;
}

function addAnswerEntry() {
  const entry = document.createElement("article");
  entry.className = "entry-in";

  const body = document.createElement("div");
  body.className = "mt-3";
  body.innerHTML = `
    <div class="relative h-px w-40 overflow-hidden bg-paper/15" aria-hidden="true">
      <div class="scan absolute inset-y-0 left-0 w-1/3 bg-accent"></div>
    </div>
    <p class="mt-3 font-mono text-[11px] uppercase tracking-[0.18em] text-paper/70">
      <span data-thinking-text>Consulting the journal</span>
      <span data-elapsed class="ml-2 text-paper/60"></span>
    </p>`;

  entry.append(makeLabel("Companion", true), body);
  log.append(entry);
  return { entry, body };
}

function showAnswer(body, answer, sources, answeredBy) {
  body.innerHTML = `<div class="answer">${renderMarkdown(answer)}</div>`;

  const labels = [...new Set(sources.map(sourceLabel))];
  if (labels.length) {
    const footer = document.createElement("div");
    footer.className = "mt-5 flex flex-wrap items-center gap-2";

    const title = document.createElement("span");
    title.className = "mr-1 font-mono text-[10px] uppercase tracking-[0.18em] text-paper/60";
    title.textContent = "From";
    footer.append(title);

    for (const label of labels) {
      const stamp = document.createElement("span");
      stamp.className = "border border-paper/25 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-paper/75 hover:border-accent hover:text-paper transition-colors";
      stamp.textContent = label;
      footer.append(stamp);
    }
    body.append(footer);
  }

  // Which AI provider actually wrote this answer (useful with the fallback chain).
  if (answeredBy) {
    const via = document.createElement("p");
    via.className = "mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-paper/60";
    via.textContent = `Answered by ${answeredBy}`;
    body.append(via);
  }
}

function showError(body, message, question) {
  body.innerHTML = "";
  const box = document.createElement("div");
  box.className = "border-l-2 border-accent pl-4";

  const heading = document.createElement("p");
  heading.className = "text-paper";
  heading.textContent = "Couldn't get an answer this time.";

  const detail = document.createElement("p");
  detail.className = "mt-1 text-sm leading-relaxed text-paper/70";
  detail.textContent = message;

  const retry = document.createElement("button");
  retry.type = "button";
  retry.className = "mt-3 font-mono text-[11px] uppercase tracking-[0.18em] border-b border-paper/40 pb-0.5 hover:text-accent hover:border-accent transition-colors";
  retry.textContent = "Try again →";
  retry.addEventListener("click", () => ask(question));

  box.append(heading, detail, retry);
  body.append(box);
}


// ── Talking to the backend ───────────────────────────────────
function setWaiting(isWaiting) {
  waiting = isWaiting;
  sendButton.disabled = isWaiting;
  statusText.textContent = isWaiting ? "Thinking" : "Ready";
  statusDot.classList.toggle("animate-pulse", isWaiting);
}

function scrollLogTo(element) {
  log.scrollTo({ top: element.offsetTop - 24, behavior: reduceMotion ? "auto" : "smooth" });
}

async function ask(question) {
  question = question.trim();
  if (!question || waiting) return;

  emptyState.hidden = true;
  clearButton.hidden = false;

  const questionEntry = addQuestionEntry(question);
  const { body } = addAnswerEntry();
  scrollLogTo(questionEntry);
  setWaiting(true);

  // Show how long we've been waiting. Busy providers can slow things down.
  const started = Date.now();
  const timer = setInterval(() => {
    const seconds = Math.round((Date.now() - started) / 1000);
    const elapsed = body.querySelector("[data-elapsed]");
    const text = body.querySelector("[data-thinking-text]");
    if (elapsed) elapsed.textContent = `${seconds}s`;
    if (text && seconds >= 7) text.textContent = "Still working, trying other AI providers";
  }, 1000);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: AbortSignal.timeout(90000), // give up after 90 seconds
    });

    let data = {};
    try { data = await response.json(); } catch { /* not JSON, handled below */ }

    if (!response.ok || data.error) {
      showError(body, data.error || `The server replied with an error (${response.status}).`, question);
    } else {
      showAnswer(body, data.answer || "", data.sources || [], data.answered_by);
    }
  } catch (error) {
    const message = error.name === "TimeoutError"
      ? "It took too long to answer. Please try again."
      : "Couldn't reach the server. Is app.py still running?";
    showError(body, message, question);
  } finally {
    clearInterval(timer);
    setWaiting(false);
    scrollLogTo(questionEntry); // question at the top, answer right below it
  }
}


// ── Wiring up the page ───────────────────────────────────────
function autoResize() {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
}

function focusChat() {
  chatSection.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "center" });
  input.focus({ preventScroll: true });
  input.setSelectionRange(input.value.length, input.value.length);
}

form.addEventListener("submit", (event) => {
  event.preventDefault(); // stop the browser reloading the page
  const question = input.value;
  input.value = "";
  autoResize();
  ask(question);
});

input.addEventListener("input", autoResize);
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    form.requestSubmit();
  }
});

// Example questions: send straight away.
document.querySelectorAll("[data-ask]").forEach((button) => {
  button.addEventListener("click", () => ask(button.dataset.ask));
});

// "Ask the companion" button: jump to the chat and put the cursor in the box.
document.querySelectorAll("[data-focus-chat]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    focusChat();
  });
});

clearButton.addEventListener("click", () => {
  log.querySelectorAll("article").forEach((entry) => entry.remove());
  emptyState.hidden = false;
  clearButton.hidden = true;
  input.focus();
});

// Contents list: each chapter pre-fills a question you can edit before sending.
const chapterList = document.querySelector("#chapters");
for (const [number, title] of CHAPTERS) {
  const item = document.createElement("li");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "group relative w-full grid grid-cols-[4.25rem_1fr_auto] sm:grid-cols-[6rem_1fr_auto] items-baseline gap-3 py-5 sm:py-6 border-b border-ink/15 text-left";
  button.innerHTML = `
    <span class="font-mono text-xs text-ink/65">${number === "00" ? "Prol." : `Ch. ${number}`}</span>
    <span class="font-display text-[1.7rem] sm:text-4xl leading-tight transition-transform duration-500 group-hover:translate-x-2 group-hover:italic"></span>
    <span class="font-mono text-[11px] uppercase tracking-[0.16em] text-ink/65 group-hover:text-accent transition-colors">Ask →</span>
    <span class="absolute left-0 -bottom-px h-px w-0 bg-accent transition-all duration-500 group-hover:w-full" aria-hidden="true"></span>`;
  button.children[1].textContent = title;
  button.setAttribute("aria-label", `Ask for a walkthrough of ${number === "00" ? "the Prologue" : `Chapter ${Number(number)}, ${title}`}`);

  button.addEventListener("click", () => {
    input.value = number === "00"
      ? "Give me a walkthrough of the Prologue."
      : `Give me a walkthrough of Chapter ${Number(number)}: ${title}.`;
    autoResize();
    focusChat();
  });

  item.append(button);
  chapterList.append(item);
}

const lastItem = document.createElement("li");
lastItem.className = "grid grid-cols-[4.25rem_1fr] sm:grid-cols-[6rem_1fr] items-baseline gap-3 py-5 sm:py-6 text-ink/65";
lastItem.innerHTML = `
  <span class="font-mono text-xs">Ch. 11–22</span>
  <span class="font-display text-[1.7rem] sm:text-4xl leading-tight italic">Not yet in the journal</span>`;
chapterList.append(lastItem);

// Scroll reveal: fade elements up as they come into view.
const revealItems = document.querySelectorAll("[data-reveal]");
if (reduceMotion || !("IntersectionObserver" in window)) {
  revealItems.forEach((element) => element.classList.add("is-visible"));
} else {
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    }
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
  revealItems.forEach((element) => observer.observe(element));
}
