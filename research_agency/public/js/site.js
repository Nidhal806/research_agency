// research_agency/public/js/site.js
// كود عام للموقع (مؤثرات بسيطة لاحقًا). الآن تحقّق من اتجاه الصفحة.
(function () {
  try {
    const dir = document.documentElement.getAttribute('dir');
    if (dir !== 'rtl') document.documentElement.setAttribute('dir', 'rtl');
    // Placeholder: تأثير hover أو أحداث لاحقة…
    // console.log('IraqIndex site.js loaded');
  } catch (e) { /* لا شيء */ }
})();
