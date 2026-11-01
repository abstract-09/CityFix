import { api, session } from '../services/api.js';
import { h } from './dom.js';
import { banner, field, spinner } from './ui.js';

// role: 'officer' | 'admin'. Calls onSuccess(user) once a matching account has signed in.
export function loginForm({ role, title, intro, onSuccess }) {
  const slot = h('div');
  const username = h('input', { id: 'login-user', class: 'input', type: 'text', autocomplete: 'username', required: true, autocapitalize: 'none', spellcheck: 'false' });
  const password = h('input', { id: 'login-pass', class: 'input', type: 'password', autocomplete: 'current-password', required: true });
  const submit = h('button', { class: 'btn btn--primary', type: 'submit' }, 'Sign in');

  const form = h('form', {
    class: 'card login', novalidate: true,
    onsubmit: async (e) => {
      e.preventDefault();
      slot.replaceChildren();
      if (!username.value.trim() || !password.value) {
        slot.replaceChildren(banner('error', 'Enter your username and password'));
        return;
      }
      submit.disabled = true;
      submit.replaceChildren(spinner('Signing in'), ' Signing in…');
      try {
        const data = await api.login(username.value.trim(), password.value);
        if (data.user.role !== role) {
          session.clear();
          throw new Error(role === 'admin' ? 'This account is not an administrator account' : 'This account is not an officer account');
        }
        session.set({ token: data.token, user: data.user });
        onSuccess(data.user);
      } catch (err) {
        password.value = '';
        slot.replaceChildren(banner('error', err.message));
        submit.disabled = false;
        submit.replaceChildren('Sign in');
      }
    },
  },
  h('h2', { class: 'card__title' }, title),
  h('p', { class: 'muted' }, intro),
  slot,
  field({ id: 'login-user', label: 'Username', control: username }),
  field({ id: 'login-pass', label: 'Password', control: password }),
  submit);
  return form;
}
