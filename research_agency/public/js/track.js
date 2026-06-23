// research_agency/public/js/track.js
(function () {
  const $ = id => document.getElementById(id);

  const btn       = $('btnTrack');
  const input     = $('appId');
  const card      = $('card');
  const alertBox  = $('alert');

  const outId       = $('outId');
  const badgeApp    = $('badgeApp');
  const badgePay    = $('badgePay');
  const outCreated  = $('outCreated');
  const outModified = $('outModified');
  const outMethod   = $('outMethod');
  const timeline    = $('timeline');
  const btnCopy     = $('btnCopy');

  // ✅ زر الدفع الجديد (يظهر/يختفي حسب حالة الدفع)
  const btnPay      = $('btnPay');

function showAlert(msg, ok = true) {
  alertBox.hidden = false;
  alertBox.className = "iqx-alert " + (ok ? "ok" : "err");
  alertBox.textContent = msg;
}


  function formatFrappeDateTimeArIQ(dtStr) {
    if (!dtStr || typeof dtStr !== 'string') return '—';
    const m = dtStr.match(/^(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?$/);
    if (!m) return dtStr;
    const d = new Date(+m[3], +m[2]-1, +m[1], +m[4], +m[5], +(m[6]||0));
    if (isNaN(d.getTime())) return dtStr;
    return new Intl.DateTimeFormat('ar-IQ', {
      year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'
    }).format(d);
  }

  function renderTimeline(status) {
    const steps = ['تم استلام الطلب', 'قيد المراجعة', 'قرار اللجنة', 'تمت الفهرسة'];
    let idx = 0;
    if ((status||'').includes('قيد')) idx = 1;
    else if ((status||'').includes('مقبول') || (status||'').includes('مرفوض')) idx = 2;
    else if ((status||'').includes('تم الفهرسة')) idx = 3;

    timeline.innerHTML = '';
    steps.forEach((s,i) => {
      const div = document.createElement('div');
      div.className = 'step ' + (i < idx ? 'done' : i === idx ? 'active' : '');
      div.innerHTML = `<div class="dot"></div><div class="text">${s}</div>`;
      timeline.appendChild(div);
    });
  }

  async function resolveToDocName(incomingId) {
    try {
      const r = await fetch(
        `/api/method/research_agency.api.resolve_application_id?application_id=${encodeURIComponent(incomingId)}`,
        { headers: { Accept: 'application/json' } }
      );
      const j = await r.json().catch(() => ({}));
      return j && j.message ? j.message.name : null;
    } catch (e) {
      console.error(e);
      return null;
    }
  }

  function updatePayButton(paymentStatus, publicId) {
    if (!btnPay) return;

    const payStatus = (paymentStatus || '').trim();
    const PAID_VALUE = 'مدفوع (تجريبي)';

    // رابط الدفع يعتمد على الرقم العام الذي أدخله المستخدم
    const payUrl = `/iraq_index/pay-online?application_id=${encodeURIComponent(publicId)}`;
    btnPay.href = payUrl;

    // اخفاء افتراضي
    btnPay.hidden = true;

    // إظهار فقط في حالتين: غير مدفوع / فشل
    if (payStatus === PAID_VALUE) {
      btnPay.hidden = true;
    } else if (payStatus.includes('غير')) {
      btnPay.hidden = false;
    } else if (payStatus.includes('فشل')) {
      btnPay.hidden = false;
    } else {
      // حالة غير معروفة -> نخفيه حتى لا نربك المستخدم
      btnPay.hidden = true;
    }
  }

  async function fetchStatus(userEnteredId) {
    card.hidden = true;
    alertBox.hidden = true;

    // نخفي زر الدفع لحين ما نجيب الحالة
    if (btnPay) btnPay.hidden = true;

    const trimmed = (userEnteredId || '').trim();
    if (!trimmed) {
      showAlert('رجاء أدخل رقم الطلب');
      return;
    }

    const docname = await resolveToDocName(trimmed);
    if (!docname) {
      showAlert('لم يتم العثور على الطلب');
      return;
    }

    const r = await fetch(
      `/api/method/research_agency.api.get_application_public_status?application_id=${encodeURIComponent(docname)}`,
      { headers: { Accept: 'application/json' } }
    );
    const data = await r.json().catch(() => ({}));
    if (!data.message || !data.message.application_id) {
      showAlert('لم يتم العثور على الطلب');
      return;
    }

    const m = data.message;
    const PAID_VALUE = 'مدفوع (تجريبي)';

    outId.textContent      = trimmed; // نعرض ما كتبه المستخدم (الكود العام عادة)
    badgeApp.textContent   = m.application_status || '—';
    badgePay.textContent   = m.payment_status || '—';
    outCreated.textContent  = m.created_on  ? formatFrappeDateTimeArIQ(m.created_on)  : '—';
    outModified.textContent = m.modified_on ? formatFrappeDateTimeArIQ(m.modified_on) : '—';

    outMethod.textContent =
      ((m.payment_status || '').trim() === PAID_VALUE)
        ? (m.payment_method || '—')
        : '—';

    // ✅ زر الدفع حسب الحالة
    updatePayButton(m.payment_status, trimmed);

    renderTimeline(m.application_status || '');

    const box = document.getElementById('indexedBox');
    const dateEl = document.getElementById('indexedDate');
    if (box) box.hidden = true;
    if (m.application_status === 'تم الفهرسة' && m.indexing_date) {
      if (dateEl) dateEl.textContent = m.indexing_date;
      if (box) box.hidden = false;
    }

    card.hidden = false;
  }

  btn.addEventListener('click', () => fetchStatus(input.value));

  btnCopy.addEventListener('click', async () => {
    const id = outId.textContent.trim();
    if (!id || id === '—') {
      showAlert('لا يوجد رقم طلب لنسخه', false);
      return;
    }

    const url = location.origin + '/iraq_index/track?application_id=' + encodeURIComponent(id);

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(url);
        showAlert('تم نسخ رابط المتابعة ✅', true);
        return;
      }
    } catch (e) {}

    // fallback
    const ta = document.createElement('textarea');
    ta.value = url;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);

    showAlert(ok ? 'تم نسخ رابط المتابعة ✅' : 'تعذر النسخ. انسخي الرابط يدويًا: ' + url, ok);
  });


  // لو وصلنا من صفحة النجاح
  const p = new URLSearchParams(location.search).get('application_id');
  if (p) {
    input.value = p;
    fetchStatus(p);
  }
})();
