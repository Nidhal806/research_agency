// =========================
// State
// =========================
let currentPage = 1;
let pageSize = 20;

let currentTitle = "";
let currentAuthor = "";

let isManualSearch = false;

let requestCounter = 0;


// =========================
// Init
// =========================
document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadFilters();
  loadArticles();
});


// =========================
// Events
// =========================
function bindEvents() {

  const btn = document.getElementById("search-btn");

  if (btn) {
    btn.addEventListener("click", () => {
      currentPage = 1;

      isManualSearch = true; // 🔥 هذا السطر أضيفيه فقط

      const titleInput = document.getElementById("search-title");
      const authorInput = document.getElementById("search-author");

      currentTitle = titleInput ? titleInput.value.trim() : "";
      currentAuthor = authorInput ? authorInput.value.trim() : "";

      loadArticles();
    });
  }

  // الفلاتر (sidebar)
  document.addEventListener("change", (e) => {
    if (
      e.target.closest("#filter-subjects") ||
      e.target.closest("#filter-doc-types") ||
      e.target.closest("#filter-years")
    ) {
      currentPage = 1;
      loadArticles();
    }
  });

}


// =========================
// Load Filters
// =========================
async function loadFilters() {

  const res = await fetch('/api/method/research_agency.api.get_filters_normalized');
  const data = await res.json();
  const filters = data.message;

  renderSubjects(filters.subjects || []);
  renderDocTypes(filters.doc_types || []);
  renderYears(filters.years || []);
}


// =========================
// Render Filters
// =========================
function renderSubjects(list) {
  const container = document.getElementById("filter-subjects");
  container.innerHTML = "";

  list.slice(0, 10).forEach(item => {
    container.innerHTML += `
      <div class="filter-item">
        <label>
          <input type="checkbox" value="${item.name}">
          <span>${item.name}</span>
        </label>
      </div>
    `;
  });
}

function renderDocTypes(list) {
  const container = document.getElementById("filter-doc-types");
  container.innerHTML = "";

  list.slice(0, 6).forEach(item => {
    container.innerHTML += `
      <div class="filter-item">
        <label>
          <input type="checkbox" value="${item.name}">
          ${item.name}
        </label>
      </div>
    `;
  });
}

function renderYears(list) {
  const container = document.getElementById("filter-years");
  container.innerHTML = "";

  list.slice(0, 10).forEach(item => {
    container.innerHTML += `
      <div class="filter-item">
        <label>
          <input type="checkbox" value="${item.name}">
          ${item.name}
        </label>
      </div>
    `;
  });
}


// =========================
// Load Articles (FULL)
// =========================
function loadArticles() {

  const btn = document.getElementById("search-btn");

  // 🔹 تعطيل الزر فقط
  if (btn) {
    btn.disabled = true;
  }

  const params = new URLSearchParams();

  params.set("page", currentPage);
  params.set("page_size", pageSize);

  if (currentTitle) params.set("title", currentTitle);
  if (currentAuthor) params.set("author", currentAuthor);

  const subjects = [...document.querySelectorAll('#filter-subjects input:checked')].map(x => x.value);
  const docTypes = [...document.querySelectorAll('#filter-doc-types input:checked')].map(x => x.value);
  const years = [...document.querySelectorAll('#filter-years input:checked')].map(x => x.value);

  if (subjects.length) params.set("subjects", subjects.join(","));
  if (docTypes.length) params.set("doc_types", docTypes.join(","));
  if (years.length) params.set("years", years.join(","));

  fetch(`/api/method/research_agency.api.get_articles_public_v2?${params.toString()}`)
    .then(r => r.json())
    .then(res => {
      if (!res.message) {
        console.error("API ERROR:", res);
        return;
      }

      const data = res.message;

      renderArticles(data.articles || []);
      renderPager(data.page, data.page_size, data.total);
    })
    .finally(() => {
      // 🔹 يرجع الزر يشتغل فقط
      if (btn) {
        btn.disabled = false;
      }
    });

}




// =========================
// Render Articles (نفس القديم 100%)
// =========================
function renderArticles(articles) {

  const container = document.getElementById("articles-results");
  container.innerHTML = "";

  if (!articles.length) {
    container.innerHTML = `<p style="opacity:.7">لا توجد نتائج مطابقة.</p>`;
    return;
  }

  articles.forEach(a => {

    const card = document.createElement("article");
    card.className = "article-card";

    card.innerHTML = `
      <h3 class="article-title">
        <a href="${a.article_url}" target="_blank">
          ${a.article_title}
        </a>
      </h3>

      <div class="article-authors">${a.authors_text || ""}</div>

      <div class="article-meta">
        ${a.journal_name_display || ""}
        • ${new Date(a.publication_date).getFullYear()}
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


// =========================
// Helpers
// =========================
function truncate(text, max) {
  return text.length > max ? text.slice(0, max) + "…" : text;
}


// =========================
// Pagination (نفس القديم)
// =========================
function renderPager(page, pageSize, total) {

  const pager = document.getElementById("pager");
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


function renderFilters(subjects, docTypes) {

  const subjectsBox = document.getElementById("filter-subjects");
  const docTypesBox = document.getElementById("filter-doc-types");

  subjectsBox.innerHTML = "";
  docTypesBox.innerHTML = "";

  subjects.forEach(s => {
    subjectsBox.innerHTML += `
      <div class="filter-item">
        <label>
          <input type="checkbox" value="${s.name}">
          ${s.name} (${s.count})
        </label>
      </div>
    `;
  });

  docTypes.forEach(d => {
    docTypesBox.innerHTML += `
      <div class="filter-item">
        <label>
          <input type="checkbox" value="${d.name}">
          ${d.name} (${d.count})
        </label>
      </div>
    `;
  });
}