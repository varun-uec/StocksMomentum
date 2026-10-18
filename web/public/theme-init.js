// Applies the stored theme before first paint, so the page never flashes the
// wrong theme. A file, not an inline script, because the API's CSP allows
// only same-origin scripts. Keep the key in step with theme-provider.tsx.
(function () {
  try {
    var stored = localStorage.getItem('m25-theme');
    var mode = stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system';
    var dark = mode === 'dark' || (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', dark);
  } catch (e) {}
})();
