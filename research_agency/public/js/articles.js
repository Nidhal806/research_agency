// =========================
// State
// =========================
let currentPage = 1;
let pageSize = 20;
let currentTitle = "";
let currentAuthor = "";
let currentSpecialization = "الكل";
let journalId = null;
let specializationsCache = [];

// =========================
// Utils
// =========================
function getParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

function qs(id) {
  return document.getElementById(id);
}

// =========================
// Init
// =========================
document.addEventListener("DOMContentLoaded", () => {
  journalId = getParam("journal");

  if (journalId) {
    qs("journal-scope").style.display = "block";
    // الاسم سيُملأ لاحقًا إن رغبتِ من API آخر، حاليًا نعرض الرمز
    fetch(`/api/method/research_agency.api.get_journal_public_info?journal=${journalId}`)
    .then(r => r.json())
    .then(res => {
      if (res.message && res.message.journal_name) {
        qs("journal-name").textContent = res.message.journal_name;
      } else {
        qs("journal-name").textContent = journalId;
      }
    });

  }

  bindEvents();
  loadSpecializations();
  loadArticles();
});

// =========================
// Events
// =========================
function bindEvents() {
  qs("search-btn").addEventListener("click", () => {
    currentPage = 1;
    currentTitle = qs("search-title").value.trim();
    currentAuthor = qs("search-author").value.trim();
    currentSpecialization = qs("search-specialization").value.trim() || "الكل";
    loadArticles();
  });

  qs("search-specialization").addEventListener("input", onSpecializationInput);
  document.addEventListener("click", () => {
    qs("specialization-suggestions").style.display = "none";
  });
}

// =========================
// API Calls
// =========================
function loadArticles() {
  const params = new URLSearchParams();
  params.set("page", currentPage);
  params.set("page_size", pageSize);

  if (currentTitle) params.set("title", currentTitle);
  if (currentAuthor) params.set("author", currentAuthor);
  if (currentSpecialization && currentSpecialization !== "الكل") {
    params.set("specialization", currentSpecialization);
  }
  if (journalId) params.set("journal", journalId);

  fetch(`/api/method/research_agency.api.get_articles_public?${params.toString()}`)
    .then(r => r.json())
    .then(res => {
      const data = res.message;
      renderArticles(data.articles || []);
      renderPager(data.page, data.page_size, data.total);
    });
}

function loadSpecializations() {
  fetch(`/api/method/research_agency.api.get_article_specializations_public`)
    .then(r => r.json())
    .then(res => {
      specializationsCache = res.message.specializations || [];
    });
}

// =========================
// Autocomplete (Specialization)
// =========================
function onSpecializationInput(e) {
  const val = e.target.value.toLowerCase();
  const box = qs("specialization-suggestions");
  box.innerHTML = "";

  if (!val) {
    box.style.display = "none";
    return;
  }

  const matches = specializationsCache
    .filter(s => s.toLowerCase().includes(val))
    .slice(0, 12);

  if (!matches.length) {
    box.style.display = "none";
    return;
  }

  matches.forEach(s => {
    const div = document.createElement("div");
    div.className = "autocomplete-item";
    div.textContent = s;
    div.onclick = () => {
      qs("search-specialization").value = s;
      box.style.display = "none";
    };
    box.appendChild(div);
  });

  box.style.display = "block";
}

// =========================
// Render
// =========================
function renderArticles(articles) {
  const container = qs("articles-results");
  container.innerHTML = "";

  if (!articles.length) {
    container.innerHTML = `<p style="opacity:.7">لا توجد نتائج مطابقة.</p>`;
    return;
  }

  articles.forEach(a => {
    const card = document.createElement("article");
    card.className = "article-card";
    card.dir = "ltr";

    card.innerHTML = `
      <h3 class="article-title">
        <a href="${a.article_url}" target="_blank" rel="noopener">
          ${a.article_title}
        </a>
      </h3>

      <div class="article-authors">${a.authors_text || ""}</div>

      <div class="article-meta">
        ${a.journal_name || ""} • ${new Date(a.publication_date).getFullYear()}
        ${a.volume ? `• Vol. ${a.volume}` : ""}
        ${a.issue ? `(Issue ${a.issue})` : ""}
        ${a.pages ? `, pp. ${a.pages}` : ""}
      </div>

      <p class="article-abstract">
        ${truncate(a.abstract || "", 420)}
      </p>

      <div class="article-actions">
        ${a.doi ? `<span class="doi">DOI: ${a.doi}</span>` : ""}
        <a href="${a.article_url}" target="_blank" class="source-link">عرض المصدر</a>
      </div>
    `;

    container.appendChild(card);
  });
}

function truncate(text, max) {
  return text.length > max ? text.slice(0, max) + "…" : text;
}

// =========================
// Pagination
// =========================
function renderPager(page, pageSize, total) {
  const pager = qs("pager");
  const pages = Math.max(1, Math.ceil(total / pageSize));

  pager.innerHTML = `
    <button ${page <= 1 ? "disabled" : ""} onclick="changePage(${page - 1})">السابق</button>
    <span>${page} / ${pages}</span>
    <button ${page >= pages ? "disabled" : ""} onclick="changePage(${page + 1})">التالي</button>
  `;
}

function changePage(p) {
  currentPage = p;
  loadArticles();
}
