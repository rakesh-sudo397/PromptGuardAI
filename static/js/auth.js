/**
 * Filename: static/js/auth.js
 * Action: CREATE
 * Purpose: Manage login/signup tab switching, authentication REST requests, and cookie tokens.
 */

function switchTab(tab) {
    const loginToggle = document.getElementById('toggle-login');
    const registerToggle = document.getElementById('toggle-register');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const forgotForm = document.getElementById('forgot-form');
    const subtext = document.getElementById('auth-subtext');
    const alertDiv = document.getElementById('auth-alert');

    // Reset error alerts
    alertDiv.style.display = 'none';

    if (tab === 'login') {
        loginToggle.classList.add('active');
        registerToggle.classList.remove('active');
        loginForm.classList.add('active');
        registerForm.classList.remove('active');
        forgotForm.classList.remove('active');
        subtext.textContent = 'Sign in to manage LLM security gateways';
    } else if (tab === 'register') {
        loginToggle.classList.remove('active');
        registerToggle.classList.add('active');
        loginForm.classList.remove('active');
        registerForm.classList.add('active');
        forgotForm.classList.remove('active');
        subtext.textContent = 'Join the PromptGuard developer network';
    } else if (tab === 'forgot') {
        loginToggle.classList.remove('active');
        registerToggle.classList.remove('active');
        loginForm.classList.remove('active');
        registerForm.classList.remove('active');
        forgotForm.classList.add('active');
        subtext.textContent = 'Recover your developer account';
    }
}

async function handleAuth(event, type) {
    event.preventDefault();
    const alertDiv = document.getElementById('auth-alert');
    alertDiv.style.display = 'none';

    let username, password;

    if (type === 'login') {
        username = document.getElementById('login-username').value.trim();
        password = document.getElementById('login-password').value;
    } else {
        username = document.getElementById('reg-username').value.trim();
        password = document.getElementById('reg-password').value;
        const confirm = document.getElementById('reg-confirm').value;

        if (password !== confirm) {
            showAlert('Passwords do not match.');
            return;
        }
        if (password.length < 6) {
            showAlert('Password must be at least 6 characters long.');
            return;
        }
    }

    try {
        const url = type === 'login' ? '/api/v1/auth/login' : '/api/v1/auth/signup';
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (!response.ok) {
            showAlert(data.detail || 'Authentication failed. Please try again.');
            return;
        }

        // Successfully authenticated! Set session_token cookie (managed by browser or manually)
        // Vercel serverless functions support cookies.
        document.cookie = `session_token=${encodeURIComponent(username)}; path=/; max-age=86400; SameSite=Lax`;
        
        // Redirect to Dashboard
        window.location.href = '/dashboard';

    } catch (err) {
        console.error('Authentication request error:', err);
        showAlert('Network error. Failed to reach the security gateway.');
    }
}

function showAlert(message) {
    const alertDiv = document.getElementById('auth-alert');
    alertDiv.textContent = message;
    alertDiv.style.display = 'block';
}

function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    const btn = input.nextElementSibling;
    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = '🙈';
    } else {
        input.type = 'password';
        btn.textContent = '👁️';
    }
}

async function handleForgotPassword(event) {
    event.preventDefault();
    const alertDiv = document.getElementById('auth-alert');
    alertDiv.style.display = 'none';

    const username = document.getElementById('forgot-username').value.trim();
    const new_password = document.getElementById('forgot-password').value;

    if (new_password.length < 8) {
        showAlert('Password must be at least 8 characters long.');
        return;
    }

    try {
        const response = await fetch('/api/v1/auth/reset-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, new_password })
        });

        const data = await response.json();

        if (!response.ok) {
            showAlert(data.detail || 'Password reset failed.');
            return;
        }

        alert('Password reset successful! You can now log in with your new password.');
        switchTab('login');

    } catch (err) {
        console.error('Password reset request error:', err);
        showAlert('Network error. Failed to reach the security gateway.');
    }
}
