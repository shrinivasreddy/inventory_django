(function () {
  'use strict';

  function enhancePasswordField(input) {
    if (input.dataset.visibilityReady === 'true') return;
    input.dataset.visibilityReady = 'true';

    var wrapper = document.createElement('div');
    wrapper.className = 'password-visibility-field';
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);

    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'password-visibility-toggle';
    button.setAttribute('aria-label', 'Show password');
    button.setAttribute('aria-pressed', 'false');
    button.title = 'Show password';
    button.innerHTML = '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 5c-5.2 0-9.3 4.1-10.5 6.3a1.4 1.4 0 0 0 0 1.4C2.7 14.9 6.8 19 12 19s9.3-4.1 10.5-6.3a1.4 1.4 0 0 0 0-1.4C21.3 9.1 17.2 5 12 5zm0 11.5A4.5 4.5 0 1 1 12 7a4.5 4.5 0 0 1 0 9.5zm0-2.5a2 2 0 1 1 0-4 2 2 0 0 1 0 4z"/></svg>';
    wrapper.appendChild(button);

    button.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      button.setAttribute('aria-pressed', show ? 'true' : 'false');
      button.title = show ? 'Hide password' : 'Show password';
      input.focus({ preventScroll: true });
    });
  }

  document.querySelectorAll('input[type="password"]').forEach(enhancePasswordField);
}());
