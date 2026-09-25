(() => {
  'use strict';
  const form = document.getElementById('farm-setup-form');
  const error = document.getElementById('farm-setup-error');
  const button = form.querySelector('button[type="submit"]');
  const setValue = (name, value) => {
    const field = form.elements.namedItem(name);
    if (!field || value == null || value === '') return;
    if (field.tagName === 'SELECT' && !Array.from(field.options).some(option => option.value === String(value))) {
      field.add(new Option(String(value), String(value)));
    }
    field.value = value;
  };

  async function loadExistingProfile() {
    try {
      const response = await fetch('/api/farms', {credentials: 'same-origin'});
      if (!response.ok) return;
      const farms = await response.json();
      const farm = farms[0];
      if (!farm) return;
      const contextResponse = await fetch('/api/farms/' + encodeURIComponent(farm.id), {credentials: 'same-origin'});
      if (!contextResponse.ok) return;
      const context = await contextResponse.json();
      const crop = context.active_crop || {};
      for (const [name, value] of Object.entries({
        name: farm.name, location: farm.location, district: farm.district, state: farm.state,
        area_acres: farm.area_ha == null ? '' : Number(farm.area_ha) / 0.40468564224,
        crop: crop.crop, soil_type: farm.soil_type, irrigation_system: farm.irrigation_system
      })) setValue(name, value);
    } catch (_) { /* The form remains usable while the API status appears in validation errors. */ }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    error.textContent = '';
    if (!form.reportValidity()) return;
    const values = Object.fromEntries(new FormData(form).entries());
    values.area_acres = Number(values.area_acres);
    button.disabled = true;
    button.textContent = window.AgriPilotI18n ? window.AgriPilotI18n.t('Saving farm details…') : 'Saving farm details…';
    try {
      const response = await fetch('/api/farm-setup', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify(values)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not save farm details.');
      window.location.assign(result.redirect || '/dashboard');
    } catch (e) {
      error.textContent = e.message || 'The AgriPilot server is unavailable.';
      button.disabled = false;
      button.textContent = window.AgriPilotI18n ? window.AgriPilotI18n.t('Save farm details') : 'Save farm details';
    }
  });

  document.getElementById('farm-setup-logout').addEventListener('click', async () => {
    await fetch('/api/auth/logout', {method: 'POST', credentials: 'same-origin'});
    window.location.assign('/');
  });
  loadExistingProfile();
})();
