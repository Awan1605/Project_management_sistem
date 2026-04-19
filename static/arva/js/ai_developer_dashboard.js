/**
 * AI Developer Dashboard JavaScript
 * Handles API status checking and UI interactions
 */

document.addEventListener('DOMContentLoaded', function () {
  // Check AI API status
  const apiStatusUrl = document.querySelector('meta[name="ai-api-status-url"]')?.content;
  
  if (apiStatusUrl) {
    fetch(apiStatusUrl)
      .then(r => r.json())
      .then(data => {
        const icon = document.getElementById('api-status-icon');
        const card = document.getElementById('api-status-card');
        
        if (icon && card) {
          if (data.available) {
            icon.innerHTML = '<i class="bi bi-check-circle-fill" style="font-size:1.6rem;color:var(--accent-green)"></i>';
            card.style.setProperty('--sc', 'var(--accent-green)');
          } else {
            icon.innerHTML = '<i class="bi bi-x-circle-fill" style="font-size:1.6rem;color:var(--accent-red)"></i>';
            card.style.setProperty('--sc', 'var(--accent-red)');
          }
        }
      })
      .catch(() => {
        const icon = document.getElementById('api-status-icon');
        if (icon) {
          icon.innerHTML = '<i class="bi bi-question-circle-fill" style="font-size:1.6rem;color:var(--accent-amber)"></i>';
        }
      });
  }
});
