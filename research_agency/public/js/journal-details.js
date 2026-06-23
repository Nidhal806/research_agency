const params = new URLSearchParams(window.location.search);
const journalId = params.get("journal");

let currentPage = 1;
let currentSearch = "";

if (!journalId) {
  alert("معرّف المجلة غير موجود");
}

/* =========================
   تحميل بيانات المجلة
========================= */
function loadJournal() {
  fetch(
    `/api/method/research_agency.api.get_journal_details_public?journal=${journalId}&page=${currentPage}&search=${encodeURIComponent(currentSearch)}`
  )
    .then(r => r.json())
    .then(res => {
      if (!res.message) return;
      renderPage(res.message);
    });
}

/* =========================
   عرض الصفحة
========================= */
function renderPage(data) {

  /* ====== العنوان (Hero) ====== */
  document.getElementById("journal-title").textContent =
    data.journal.journal_name || "—";

  /* ====== معلومات المجلة ====== */
  document.getElementById("journal-meta").innerHTML = `
    <div class="stat-card">
      <div class="stat-title">الجهة الناشرة</div>
      <div>${data.journal.institution || "—"}</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">التخصص</div>
      <div>${data.journal.specialization || "—"}</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">لغة النشر</div>
      <div>${data.journal.language || "—"}</div>
    </div>
    <div class="stat-card">
      <div class="stat-title">ISSN</div>
      <div>${
        [data.journal.print_issn, data.journal.online_issn]
          .filter(Boolean)
          .join(" / ") || "—"
      }</div>
    </div>
  `;

  /* ====== رابط المجلة ====== */
  if (data.journal.journal_url) {
    document.getElementById("journal-link").innerHTML =
      `<a href="${data.journal.journal_url}" target="_blank" rel="noopener">
        الموقع الرسمي للمجلة
      </a>`;
  } else {
    document.getElementById("journal-link").innerHTML = "";
  }

  /* ====== الإحصاءات ====== */
  document.getElementById("stat-articles").textContent =
    data.stats.articles ?? "—";
  document.getElementById("stat-batches").textContent =
    data.stats.batches ?? "—";
  document.getElementById("stat-last-intake").textContent =
    data.stats.last_intake || "—";

  /* ====== المؤلفون ====== */
  document.getElementById("authors-box").innerHTML =
    (data.authors || [])
      .sort((a, b) => b.count - a.count)
      .map(a => `<span class="c-if">${a.name} (${a.count})</span>`)
      .join("");

  /* ====== المقالات ====== */
  renderArticles(data.articles || []);
  renderPager(data.page, data.page_size, data.total);
}

/* =========================
   عرض المقالات
========================= */
function renderArticles(articles) {
  document.getElementById("articles-body").innerHTML =
    articles.map(a => `
      <tr>
        <td class="c-title">
          ${
            a.article_url
              ? `<a href="${a.article_url}" target="_blank" rel="noopener">
                   ${a.article_title}
                 </a>`
              : a.article_title
          }
        </td>
        <td>${a.authors_text || "—"}</td>
        <td>${a.publication_date || "—"}</td>
        <td>${a.volume || "—"}</td>
        <td>${a.issue || "—"}</td>
        <td>${a.doi || "—"}</td>
      </tr>
    `).join("");
}

/* =========================
   التصفح (Pagination)
========================= */
function renderPager(page, pageSize, total) {
  const pages = Math.max(1, Math.ceil(total / pageSize));

  document.getElementById("pager").innerHTML = `
    <button ${page <= 1 ? "disabled" : ""} onclick="changePage(${page - 1})">
      السابق
    </button>
    <span>${page} / ${pages}</span>
    <button ${page >= pages ? "disabled" : ""} onclick="changePage(${page + 1})">
      التالي
    </button>
  `;
}

function changePage(p) {
  currentPage = p;
  loadJournal();
}

/* =========================
   البحث في المقالات
========================= */
function searchArticles() {
  currentSearch = document.getElementById("article-search").value.trim();
  currentPage = 1;
  loadJournal();
}

/* =========================
   تحميل أولي
========================= */
loadJournal();
