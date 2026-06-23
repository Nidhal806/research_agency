// research_agency/public/js/journal-search.js
// سكربت صفحة /iraq_index/journals فقط

(function () {
  // لو بتضمّنيه فقط في صفحة البحث، تقدرين تشيلين فحص المسار:
  const path = window.location.pathname.replace(/\/+$/, '');
  if (path !== '/iraq_index/journals') return;

  const $q    = document.getElementById('q');
  const $spec = document.getElementById('spec');
  const $btn  = document.getElementById('btn-search');
  const $res  = document.getElementById('results');
  const $prev = document.getElementById('prev');
  const $next = document.getElementById('next');
  const $page = document.getElementById('page');

  if (!($q && $btn && $res && $prev && $next && $page)) return;

  let page = 1;

  // تعبئة اختيارية للتخصصات
  if ($spec && !$spec.dataset.filled) {
    ['علمي', 'طبي','هندسي','انساني','اجتماعي','آخر'].forEach(v => {
      const opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      $spec.appendChild(opt);
    });
    $spec.dataset.filled = '1';
  }

  function apiUrl() {
    const term = $q.value.trim();
    const spec = $spec ? $spec.value.trim() : '';
    const params = new URLSearchParams({ page: String(page) });
    if (term) params.set('search_term', term);
    if (spec) params.set('specialization_filter', spec);
    return `/api/method/research_agency.api.get_journals_public_list?${params.toString()}`;
  }


function render(list) {
  if (!list || !list.length) {
    $res.innerHTML = `<div class="iqx-card">لا توجد نتائج.</div>`;
    return;
  }

  const rows = list.map(j => {
  const name   = j.name || '';
  const detailsUrl = `/iraq_index/articles.html?journal=${encodeURIComponent(name)}`;

  const title = `
    <a href="${detailsUrl}" class="iqx-link journal-link">
      ${j.journal_name || name || '—'}
    </a>
  `;


  const inst   = j.institution_name || '—';
  const spec   = j.specialization || '—';
  const pISSN  = j.print_issn || '—';
  const eISSN  = j.online_issn || '—';
  const ifVal  = (j.impact_factor !== undefined && j.impact_factor !== null && j.impact_factor !== '') ? j.impact_factor : '—';
  const link   = j.journal_url
    ? `<a href="${j.journal_url}" target="_blank" rel="noopener">رابط</a>`
    : '—';

  return `
    <tr>
      <td class="c-title">${title}</td>
      <td>${inst}</td>
      <td>${spec}</td>
      <td>${pISSN}</td>
      <td>${eISSN}</td>
      <td class="c-if">${ifVal}</td>
      <td>${link}</td>
    </tr>
  `;
}).join('');


  $res.innerHTML = `
    <div class="iqx-table-wrap">
      <table class="iqx-table">
        <thead>
          <tr>
            <th>المجلة</th>
            <th>الجهة الناشرة</th>
            <th>التخصص</th>
            <th>ISSN ورقي</th>
            <th>ISSN إلكتروني</th>
            <th>معامل التأثير</th>
            <th>الرابط</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}


  async function load() {
    $res.innerHTML = '<div class="iqx-card">... جاري جلب النتائج</div>';
    try {
      const r = await fetch(apiUrl(), { headers: { 'Accept': 'application/json' } });
      const data = await r.json();
      const msg   = data.message || {};
      const items = msg.journals || [];
      const total = Number(msg.total_count || 0);
      const ps    = Number(msg.page_size || 10);

      render(items);

      $page.textContent = String(page);
      const maxPage = Math.max(1, Math.ceil(total / ps));
      $prev.disabled = page <= 1;
      $next.disabled = page >= maxPage;
    } catch (e) {
      $res.innerHTML = '<div class="iqx-card">حدث خطأ أثناء جلب البيانات.</div>';
    }
  }

  // أحداث
  $btn.addEventListener('click', (e) => { e.preventDefault(); page = 1; load(); });
  if ($spec) $spec.addEventListener('change', () => { page = 1; load(); });
  $q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { page = 1; load(); } });
  $prev.addEventListener('click', () => { if (page > 1) { page--; load(); } });
  $next.addEventListener('click', () => { page++; load(); });

  // تحميل أولي
  load();
})();
