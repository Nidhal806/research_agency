// research_agency/public/js/site.js
// RTL + تحميل partials + إحصاءات ديناميكية مع انيميشن

// 1) فرض اتجاه RTL
(function () {
  try {
    const dir = document.documentElement.getAttribute('dir');
    if (dir !== 'rtl') {
      document.documentElement.setAttribute('dir', 'rtl');
    }
  } catch (e) {}
})();


// 2) بعد جاهزية DOM
document.addEventListener('DOMContentLoaded', function () {

  // -------------------------------
  // تحميل partials (هيدر + فوتر)
  // -------------------------------
  function inject(targetId, url) {
    var host = document.getElementById(targetId);
    if (!host) return;

    fetch(url + (url.includes('?') ? '&' : '?') + 'v=4', { cache: 'no-cache' })
      .then(r => r.text())
      .then(html => { host.innerHTML = html; })
      .catch(() => {});
  }

  inject('site-header', '/iraq_index/partials/iraqindex_header.html');
  inject('site-footer', '/iraq_index/partials/iraqindex_footer.html');


  // -------------------------------
  // انيميشن الإحصاءات
  // -------------------------------
  function animateStat(el, duration = 1000) {
    const target = Number(el.getAttribute('data-target')) || 0;
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
      const progress = Math.min((currentTime - startTime) / duration, 1);
      const value = Math.floor(start + (target - start) * progress);

      // تنسيق عربي
      el.textContent = value.toLocaleString('ar-IQ');

      if (progress < 1) {
        requestAnimationFrame(update);
      } else {
        el.textContent = target.toLocaleString('ar-IQ');
      }
    }

    requestAnimationFrame(update);
  }


  // -------------------------------
  // جلب الإحصاءات من API
  // -------------------------------
  async function loadPlatformStats() {
    try {
      const response = await fetch(
        '/api/method/research_agency.api.get_platform_stats',
        { cache: 'no-cache' }
      );

      const data = await response.json();

      if (data.message) {
        const stats = data.message;

        const statCards = document.querySelectorAll('.stat-num');

        if (statCards.length >= 3) {
          statCards[0].setAttribute('data-target', stats.journals || 0);
          statCards[1].setAttribute('data-target', stats.articles || 0);
          statCards[2].setAttribute('data-target', stats.authors || 0);

          // تشغيل الانيميشن بعد تحديث الأرقام
          statCards.forEach(el => animateStat(el));
        }
      }

    } catch (error) {
      console.error('Error loading platform stats:', error);
    }
  }

  // تشغيل تحميل الإحصاءات
  loadPlatformStats();

});
