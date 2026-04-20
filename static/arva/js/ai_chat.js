/*
 * AI Chat JavaScript - Arva
 * =========================
 * Client-side functionality for AI Chat interface
 */

// Parse markdown for existing AI messages on page load
// Use polling to wait for marked.js to be available
function initMarkdownParsing() {
    if (typeof marked !== 'undefined') {
        // marked.js is available, configure and parse
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false
        });
        
        // Parse existing AI messages - baca dari innerHTML agar emoji tidak hilang
        document.querySelectorAll('.markdown-content').forEach(function(el) {
            if (el.getAttribute('data-parsed') !== 'true') {
                let content = el.innerHTML;
                if (content && content.trim()) {
                    el.innerHTML = marked.parse(content);
                    el.setAttribute('data-parsed', 'true');
                }
            }
        });
    } else {
        // marked.js not loaded yet, retry after 100ms
        setTimeout(initMarkdownParsing, 100);
    }
}

// Start initialization when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMarkdownParsing);
} else {
    // DOM already loaded, start immediately
    initMarkdownParsing();
}

/**
 * Get CSRF token from cookies
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/**
 * Scroll chat to bottom
 */
function scrollToBottom() {
    const el = document.getElementById('chat-messages');
    if (el) {
        el.scrollTop = el.scrollHeight;
    }
}

/**
 * Show typing indicator
 */
function showTyping() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.classList.remove('d-none');
    }
    scrollToBottom();
}

/**
 * Hide typing indicator
 */
function hideTyping() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.classList.add('d-none');
    }
}

/**
 * Add a message to the chat
 */
function addMessage(role, content, time) {
    const area = document.getElementById('chat-messages');
    const welcome = document.getElementById('welcome-message');
    
    if (!area) return;
    
    if (welcome) welcome.remove();

    const isUser = role === 'user';
    
    // Parse markdown for AI messages, use plain text for user messages
    let formattedContent;
    if (isUser) {
        // For user messages, just replace newlines with <br>
        formattedContent = content.replace(/\n/g, '<br>');
    } else {
        // For AI messages, parse markdown using marked.js
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,        // Convert single newlines to <br>
                gfm: true,           // GitHub Flavored Markdown
                headerIds: false,    // Don't add ids to headers
                mangle: false,       // Don't mangle email addresses
                sanitize: false      // We trust the AI output
            });
            // Content from API is plain text, parse directly
            formattedContent = marked.parse(content);
        } else {
            // Fallback if marked.js is not loaded
            formattedContent = content.replace(/\n/g, '<br>');
        }
    }
    
    const html = `
        <div class="message-item ${isUser ? 'user' : ''}">
            <div class="message-avatar-modern ${isUser ? 'user' : 'ai'}">
                <i class="fas ${isUser ? 'fa-user' : 'fa-robot'}"></i>
            </div>
            <div class="message-wrapper">
                <div class="message-meta-modern">
                    <span class="sender-name">${isUser ? 'Anda' : 'Arva AI'}</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-bubble-modern ${isUser ? 'user' : 'ai'}">
                    ${formattedContent}
                </div>
            </div>
        </div>
    `;
    area.insertAdjacentHTML('beforeend', html);
    scrollToBottom();
}

/**
 * Send a message to the AI
 */
let isSending = false; // Flag untuk mencegah double submit
async function sendMessage(event) {
    event.preventDefault();
    event.stopPropagation();
    
    // Cegah double submit
    if (isSending) return;
    
    const input = document.getElementById('chat-input');
    if (!input) return;
    
    const message = input.value.trim();
    if (!message) return;
    
    isSending = true;
    input.value = '';
    
    const now = new Date();
    const dateTimeStr = now.toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' }) + ' ' + 
                        now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    
    // Tampilkan pesan user secara temporary (akan di-replace dengan data dari server)
    showTyping();
    
    try {
        const response = await fetch('/ai/chat/send/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded', 
                'X-CSRFToken': getCookie('csrftoken') 
            },
            body: 'message=' + encodeURIComponent(message)
        });
        
        const data = await response.json();
        hideTyping();
        
        if (data.success) {
            // Tampilkan KEDUA pesan (user + AI) dari response server
            // Ini memastikan data yang ditampilkan sesuai dengan yang ada di database
            addMessage('user', data.user_message.content, data.user_message.created_at);
            addMessage('assistant', data.ai_message.content, data.ai_message.created_at);
        } else {
            addMessage('assistant', 'Maaf, terjadi kesalahan: ' + (data.error || 'Unknown error'), dateTimeStr);
        }
    } catch (error) {
        hideTyping();
        addMessage('assistant', 'Maaf, terjadi kesalahan koneksi. Silakan coba lagi.', dateTimeStr);
    } finally {
        isSending = false;
    }
}

/**
 * Ask "What should I work on today?"
 */
async function askTodayWork() {
    const now = new Date();
    const dateTimeStr = now.toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' }) + ' ' + 
                        now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    
    showTyping();
    
    try {
        const response = await fetch('/ai/chat/today-work/');
        const data = await response.json();
        hideTyping();
        
        if (data.success) {
            // Tampilkan pesan user + AI response
            addMessage('user', 'Apa yang harus saya kerjakan hari ini?', dateTimeStr);
            addMessage('assistant', data.message.content, data.message.created_at);
        } else {
            addMessage('assistant', 'Maaf, terjadi kesalahan: ' + (data.error || 'Unknown error'), dateTimeStr);
        }
    } catch (error) {
        hideTyping();
        addMessage('assistant', 'Maaf, terjadi kesalahan koneksi. Silakan coba lagi.', dateTimeStr);
    }
}

/**
 * Clear all chat messages
 */
async function clearChat() {
    if (!confirm('Hapus semua percakapan?')) return;
    
    try {
        const response = await fetch('/ai/chat/clear/', {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        
        const data = await response.json();
        if (data.success) location.reload();
    } catch (error) {
        console.error('Error:', error);
    }
}
