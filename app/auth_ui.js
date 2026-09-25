(() => {
  'use strict';
  async function start() {
    const response = await fetch('/api/auth/session', {credentials:'same-origin'});
    if (!response.ok) { window.location.replace('/'); return; }
    const {user} = await response.json();
    window.AGRIPILOT_CURRENT_USER = user;
    if (!localStorage.getItem('agripilot-language') && window.AgriPilotI18n) {
      window.AgriPilotI18n.setLanguage(user.language || 'en', false);
    }
    document.body.classList.add(user.role === 'analyst' ? 'auth-analyst' : 'auth-farmer');
    const identity = document.getElementById('auth-identity');
    if (identity) identity.textContent = `${user.name} · ${user.role}`;
    const analystMode = document.getElementById('mode-analyst');
    if (analystMode) analystMode.hidden = user.role !== 'analyst';
    if (user.role !== 'analyst') {
      const simulationFarmPicker = document.querySelector('.farmswitch');
      if (simulationFarmPicker) simulationFarmPicker.hidden = true;
      const farmSelector = document.getElementById('farm-selection-controls');
      const farmOptions = document.querySelectorAll('#api-farm option');
      if (farmSelector && farmOptions.length <= 1) farmSelector.hidden = true;
      const simulationHero = document.getElementById('hero');
      if (simulationHero) simulationHero.hidden = true;
      const simulationQueue = document.getElementById('queue-wrap');
      if (simulationQueue) simulationQueue.hidden = true;
      const simulationLogNav = document.querySelector('.navbtn[data-p="advisories"]');
      if (simulationLogNav) simulationLogNav.hidden = true;
      const crumb = document.getElementById('tb-crumb');
      const pill = document.getElementById('tb-pill');
      if (crumb) crumb.textContent = '';
      if (pill) pill.textContent = '';
      const todayNav = document.querySelector('.navbtn[data-p="today"]');
      if (todayNav) todayNav.lastChild.textContent = window.AgriPilotI18n ? window.AgriPilotI18n.t('My Farm') : 'My Farm';
      const title = document.getElementById('tb-title');
      if (title) title.textContent = window.AgriPilotI18n ? window.AgriPilotI18n.t('My Farm') : 'My Farm';
      if (typeof window.setMode === 'function') window.setMode('farmer');
      document.querySelectorAll('.navbtn[data-p="season"],.navbtn[data-p="compare"],.navbtn[data-p="ml"]').forEach(el => el.hidden = true);
    } else if (typeof window.setMode === 'function') {
      window.setMode('analyst');
    }
    const logout = document.getElementById('auth-logout');
    if (logout) logout.addEventListener('click', async () => {
      logout.disabled = true;
      try { await fetch('/api/auth/logout', {method:'POST',credentials:'same-origin'}); }
      finally { window.location.assign('/'); }
    });
  }
  document.addEventListener('DOMContentLoaded', () => start().catch(() => window.location.replace('/')));
})();
