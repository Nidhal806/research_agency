// research_agency/public/js/pay-online.js
(function () {
  const $btn   = document.getElementById('btn-confirm');
  const $meth  = document.getElementById('pay-method'); // <select>
  const $alert = document.getElementById('alert');
  if (!($btn && $meth && $alert)) return;

  // ✅ الحالات المعتمدة
  const PAID_VALUE   = 'مدفوع (تجريبي)';
  const UNPAID_VALUE = 'غير مدفوع';
  const FAIL_VALUE   = 'فشل (وهمي)';

  function showAlert(msg, ok) {
    $alert.hidden = false;
    $alert.className = 'alert ' + (ok ? 'alert--ok' : 'alert--err');
    $alert.textContent = msg;
  }

  // 1) الكود العام من الرابط (نُبقي اسمه application_id لرجعية الروابط)
  const qs = new URLSearchParams(location.search);
  const publicCode = (qs.get('application_id') || '').trim();
  if (!publicCode) {
    $btn.disabled = true;
    showAlert('رقم الطلب غير موجود في الرابط. افتحي صفحة الدفع من شاشة النجاح أو من صفحة المتابعة.', false);
    return;
  }

  // 2) حلّ الكود العام → doc.name داخلي
  let docName = null;
  $btn.disabled = true;

  async function resolveDocName() {
    const r = await fetch(
      `/api/method/research_agency.api.resolve_application_id?application_id=${encodeURIComponent(publicCode)}`,
      { headers: { Accept: 'application/json' } }
    );
    const j = await r.json().catch(() => ({}));
    return j && j.message ? j.message.name : null;
  }

  async function fetchStatusByDocName(name) {
    const r = await fetch(
      `/api/method/research_agency.api.get_application_public_status?application_id=${encodeURIComponent(name)}`,
      { headers: { Accept: 'application/json' } }
    );
    const j = await r.json().catch(() => ({}));
    return j && j.message ? j.message : null;
  }

  function decideAndToggleByStatus(payStatusRaw) {
    const pay = (payStatusRaw || '').trim();

    // نطبع الحالة للديبغ إن لزم
    console.log('[PAY STATUS]', pay || '(empty)');

    if (pay === PAID_VALUE) {
      $btn.disabled = true;
      showAlert('تم استلام الدفع مسبقًا لهذا الطلب.', false);
      return;
    }

    if (pay === UNPAID_VALUE || pay === '') {
      $btn.disabled = false;
      showAlert('جاهز لتأكيد الدفع التجريبي.', true);
      return;
    }

    if (pay === FAIL_VALUE) {
      $btn.disabled = true;
      showAlert('حالة الطلب: فشل (وهمي). لا يمكن المتابعة بالدفع. أرسلي طلبًا جديدًا أو تواصلي مع الدعم.', false);
      return;
    }

    // أي قيمة غير متوقعة
    $btn.disabled = true;
    showAlert(`حالة غير معروفة: ${pay}. أوقِفنا الدفع احترازيًا.`, false);
  }

  async function init() {
    try {
      showAlert('جاري تجهيز الطلب…', true);
      docName = await resolveDocName();
      if (!docName) {
        showAlert('تعذر العثور على الطلب. تحققي من الرقم أو ابدئي من صفحة النجاح.', false);
        return;
      }
      const status = await fetchStatusByDocName(docName);
      if (!status) {
        showAlert('تعذر التحقق من حالة الطلب حالياً.', false);
        return;
      }
      decideAndToggleByStatus(status.payment_status);
    } catch (e) {
      console.error(e);
      showAlert('تعذر الاتصال بالخادم.', false);
    }
  }

  init();

  async function confirmPayment(name) {
    try {
      $btn.disabled = true;
      showAlert('...جاري تأكيد الدفع التجريبي', true);

      // نقرأ النص العربي الظاهر لضمان التوافق مع Select في DocType
      const opt = $meth.options[$meth.selectedIndex];
      const methodText = (opt && opt.text) ? opt.text.trim() : ($meth.value || '').trim();

      const r = await fetch(
        `/api/method/research_agency.api.update_application_status?application_id=${encodeURIComponent(name)}&payment_method=${encodeURIComponent(methodText)}`,
        { method: 'GET', headers: { Accept: 'application/json' } }
      );
      const j = await r.json().catch(() => ({}));
      const st = j && j.message ? j.message.status : null;

      if (st === 'already_paid') {
        showAlert('تم استلام الدفع مسبقًا لهذا الطلب.', false);
        return;
      }
      if (st === 'success') {
        showAlert(`✅ تم تأكيد الدفع التجريبي. (رقمك: ${publicCode})`, true);
        setTimeout(() => {
          location.href = `/iraq_index/track?application_id=${encodeURIComponent(publicCode)}`;
        }, 900);
        return;
      }
      showAlert('حدث خطأ أثناء العملية.', false);
    } catch (e) {
      console.error(e);
      showAlert('تعذر الاتصال بالخادم.', false);
    } finally {
      setTimeout(() => { $btn.disabled = false; }, 1200);
    }
  }

  $btn.addEventListener('click', async (ev) => {
    ev.preventDefault();

    if (!docName) {
      showAlert('جارٍ التجهيز… أعيدي المحاولة بعد ثوانٍ.', false);
      return;
    }

    // إعادة تحقق فوري قبل الدفع (يحسم تضارب الحالات)
    const status = await fetchStatusByDocName(docName);
    if (!status) {
      showAlert('تعذر التحقق من حالة الطلب.', false);
      return;
    }

    const pay = (status.payment_status || '').trim();
    if (pay === PAID_VALUE) {
      showAlert('تم استلام الدفع مسبقًا لهذا الطلب.', false);
      $btn.disabled = true;
      return;
    }
    if (!(pay === UNPAID_VALUE || pay === '')) {
      // فشل وهمي أو قيمة غير معروفة
      decideAndToggleByStatus(pay);
      return;
    }

    confirmPayment(docName);
  });
})();
