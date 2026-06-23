// research_agency/public/js/success.js
(function () {
  const $ = (id) => document.getElementById(id);

  const outId     = $("outId");
  const alertBox  = $("alert");
  const badgeHint = $("badgeHint");

  const btnCopyId    = $("btnCopyId");
  const btnCopyTrack = $("btnCopyTrack");

  const btnPayNow   = $("btnPayNow");
  const btnTrackNow = $("btnTrackNow");

  function showAlert(msg, ok) {
    if (!alertBox) return;
    alertBox.hidden = false;
    alertBox.className = "iqx-alert " + (ok ? "ok" : "err");
    alertBox.textContent = msg;
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      console.error(e);
      return false;
    }
  }

  function setLinks(appId) {
  // ✅ المسار الموحد: ادفع الآن -> التتبع أولاً
  const trackUrl = `/iraq_index/track?application_id=${encodeURIComponent(appId)}`;

  if (btnPayNow)   btnPayNow.href = trackUrl;  // كان pay-online
  if (btnTrackNow) btnTrackNow.href = trackUrl;

  if (btnCopyId) {
    btnCopyId.onclick = async () => {
      const ok = await copyText(appId);
      showAlert(ok ? "تم نسخ رقم الطلب ✅" : "تعذر نسخ رقم الطلب. انسخه يدويا.", ok);
    };
  }

  if (btnCopyTrack) {
    btnCopyTrack.onclick = async () => {
      const full = location.origin + trackUrl;
      const ok = await copyText(full);
      showAlert(ok ? "تم نسخ رابط المتابعة ✅" : "تعذر نسخ الرابط. انسخه يدويا.", ok);
    };
  }
 }


  function lockActions() {
    if (btnCopyId) btnCopyId.disabled = true;
    if (btnCopyTrack) btnCopyTrack.disabled = true;
    if (btnPayNow) btnPayNow.href = "/iraq_index/track";
    if (btnTrackNow) btnTrackNow.href = "/iraq_index/track";
  }

  function init() {
    if (alertBox) alertBox.hidden = true;

    // ✅ نقرأ رقم الطلب من الاستعلام ?application_id=...
    const qs = new URLSearchParams(location.search);
    const appId = (qs.get("application_id") || "").trim();

    if (!appId) {
      if (badgeHint) badgeHint.textContent = "لم يتم العثور على رقم الطلب";
      if (outId) outId.textContent = "—";
      showAlert("لم يتم العثور على رقم الطلب في الرابط.", false);
      lockActions();
      return;
    }

    if (badgeHint) badgeHint.textContent = "جاهز";
    if (outId) outId.textContent = appId;

    setLinks(appId);
    showAlert("✅ تم تسجيل الطلب بنجاح. يمكنكِ الآن الدفع أو متابعة الطلب.", true);
  }

  init();
})();
