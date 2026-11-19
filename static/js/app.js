(() => {
  const toggle = document.querySelector('[data-menu]');
  const sidebar = document.querySelector('#sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', () => {
      const open = sidebar.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') sidebar.classList.remove('is-open');
    });
  }
})();
