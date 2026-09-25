(() => {
  'use strict';
  const form = document.getElementById('auth-form');
  if (!form) return;
  const error = document.getElementById('auth-error');
  const button = form.querySelector('button[type="submit"]');
  form.addEventListener('submit', async event => {
    event.preventDefault();
    error.textContent = '';
    if (!form.reportValidity()) return;
    const values = Object.fromEntries(new FormData(form).entries());
    const kind = form.dataset.kind;
    if (kind === 'register' && values.password !== values.confirm) {
      error.textContent = 'The passwords do not match.';
      return;
    }
    delete values.confirm;
    if (values.area_ha === '') delete values.area_ha;
    button.disabled = true;
    button.textContent = kind === 'login' ? 'Signing in…' : 'Creating account…';
    try {
      const response = await fetch('/api/auth/' + kind, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify(values)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Request failed. Please try again.');
      window.location.assign(result.redirect || '/dashboard');
    } catch (e) {
      error.textContent = e.message || 'The AgriPilot server is unavailable.';
      button.disabled = false;
      button.textContent = kind === 'login' ? 'Sign in' : 'Create farmer account';
    }
  });
})();
