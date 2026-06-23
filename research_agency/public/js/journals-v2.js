let currentPage = 1;
let pageSize = 20;
let currentName = "";
let currentInstitution = "";
let currentSpecialization = "الكل";

let specializationsCache = [];

function qs(id) {
  return document.getElementById(id);
}

document.addEventListener("DOMContentLoaded", () => {
  bindEvents();
  loadSpecializations();
  loadJournals();
});

function bindEvents() {
  qs("search-btn").addEventListener("click", () => {
    currentPage = 1;
    currentName = qs("search-name").value.trim();
    currentInstitution = qs("search-institution").value.trim();
    currentSpecialization =
      qs("search-specialization").value.trim() || "الكل";
    loadJournals();
  });

  qs("search-specialization").addEventListener(
    "input",
    onSpecializationInput
  );

  document.addEventListener("click", () => {
    qs("specialization-suggestions").style.display = "none";
  });
}

/* =========================
   Load Specializations
========================= */

function loadSpecializations() {
  fetch(
    `/api/method/research_agency.api.get_journal_specializations_public`
  )
    .then((r) => r.json())
    .then((res) => {
      specializationsCache = res.message.specializations || [];
    });
}

/* =========================
   Autocomplete
========================= */

function onSpecializationInput(e) {
  const val = e.target.value.toLowerCase();
  const box = qs("specialization-suggestions");
  box.innerHTML = "";

  if (!val) {
    renderSuggestions(specializationsCache);
    return;
  }

  const matches = specializationsCache.filter((s) =>
    s.toLowerCase().includes(val)
  );

  renderSuggestions(matches);
}

function renderSuggestions(list) {
  const box = qs("specialization-suggestions");
  box.innerHTML = "";

  if (!list.length) {
    box.style.display = "none";
    return;
  }

  list.forEach((s) => {
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

/* =========================
   Load Journals
========================= */

// function loadJournals() {
//   const params = new URLSearchParams();
//   params.set("page", currentPage);
//   params.set("page_size", pageSize);

//   if (currentName) params.set("search_term", currentName);

//   if (
//     currentSpecialization &&
//     currentSpecialization !== "الكل"
//   ) {
//     params.set("specialization_filter", currentSpecialization);
//   }

//   if (currentInstitution)
//      params.set("institution_filter", currentInstitution);


//   fetch(
//     `/api/method/research_agency.api.get_journals_public_list?${params.toString()}`
//   )
//     .then((r) => r.json())
//     .then((res) => {
//       const data = res.message;
//       renderJournals(data.journals || []);
//       renderPager(data.page, data.page_size, data.total_count);
//     });
// }


function loadJournals() {

  const btn = qs("search-btn");

  // 🔹 تعطيل الزر فقط (بدون تغيير النص)
  if (btn) {
    btn.disabled = true;
    btn.style.background = "#ccc";   // 🔥 يتغير اللون فوراً
  }

  const params = new URLSearchParams();
  params.set("page", currentPage);
  params.set("page_size", pageSize);

  if (currentName) params.set("search_term", currentName);

  if (
    currentSpecialization &&
    currentSpecialization !== "الكل"
  ) {
    params.set("specialization_filter", currentSpecialization);
  }

  if (currentInstitution)
    params.set("institution_filter", currentInstitution);

  fetch(
    `/api/method/research_agency.api.get_journals_public_list?${params.toString()}`
  )
    .then((r) => r.json())
    .then((res) => {
      const data = res.message;
      renderJournals(data.journals || []);
      renderPager(data.page, data.page_size, data.total_count);
    })
    .finally(() => {
      // 🔹 يرجع الزر طبيعي
      if (btn) {
        btn.disabled = false;
        btn.style.background = "";  // 🔥 يرجع طبيعي
      }
    });
}



/* =========================
   Render Cards
========================= */

function renderJournals(list) {
  const container = qs("journals-results");
  container.innerHTML = "";

  if (!list.length) {
    container.innerHTML =
      `<p style="opacity:.7">لا توجد نتائج مطابقة.</p>`;
    return;
  }

  list.forEach((j) => {
    const card = document.createElement("article");
    card.className = "journal-card";

  card.innerHTML = `
    <h3 class="journal-title" dir="ltr">
      <a href="${j.journal_url || "#"}"
        target="_blank"
        rel="noopener">
        ${j.journal_name || ""}
      </a>
    </h3>

    <div class="journal-meta">
      ${j.institution_name || "—"} • ${j.specialization || "—"}
    </div>

    <div class="journal-meta">
      ISSN: ${j.print_issn || "—"} /
      ${j.online_issn || "—"}
    </div>

    <div class="journal-meta">
      ${(j.article_count || 0)} مقالة مفهرسة
    </div>

    <div class="journal-actions">
      <span></span>
      <a href="/iraq_index/articles?journal=${j.name}">
        عرض المقالات
      </a>
    </div>
  `;


    container.appendChild(card);
  });
}

/* =========================
   Pager
========================= */

function renderPager(page, pageSize, total) {
  const pager = qs("pager");
  const pages = Math.max(1, Math.ceil(total / pageSize));

  pager.innerHTML = `
    <button ${page <= 1 ? "disabled" : ""}
      onclick="changePage(${page - 1})">
      السابق
    </button>

    <span>${page} / ${pages}</span>

    <button ${page >= pages ? "disabled" : ""}
      onclick="changePage(${page + 1})">
      التالي
    </button>
  `;
}

function changePage(p) {
  currentPage = p;
  loadJournals();
}
