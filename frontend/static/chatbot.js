document.addEventListener('DOMContentLoaded', () => {
    const chatWidget = document.createElement('div');
    chatWidget.id = 'chatbot-widget';
    chatWidget.innerHTML = `
        <button id="chatbot-button">
            <img src="/static/chatbot_logo.png" alt="Chat" style="width: 40px; height: 40px;">
        </button>
        <div id="chatbot-window">
            <div class="chatbot-header">
                <span class="title">SmartShop Assistant</span>
                <span class="close-btn">&times;</span>
            </div>
            <div id="chatbot-messages">
                <div class="message bot">Hi! I'm your SmartShop assistant. How can I help you today?</div>
            </div>
            <div class="chatbot-input-area">
                <input type="text" id="chatbot-input" placeholder="Ask me anything..." autocomplete="off">
                <button id="chatbot-send"><i class="fas fa-paper-plane"></i></button>
            </div>
        </div>
    `;
    document.body.appendChild(chatWidget);

    const btn = document.getElementById('chatbot-button');
    const win = document.getElementById('chatbot-window');
    const closeBtn = document.querySelector('.close-btn');
    const input = document.getElementById('chatbot-input');
    const sendBtn = document.getElementById('chatbot-send');
    const messages = document.getElementById('chatbot-messages');

    btn.addEventListener('click', () => {
        win.classList.toggle('active');
        if (win.classList.contains('active')) {
            input.focus();
        }
    });

    closeBtn.addEventListener('click', () => {
        win.classList.remove('active');
    });

    const addMessage = (text, sender = 'bot', recommendations = []) => {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        msgDiv.innerText = text;
        messages.appendChild(msgDiv);

        if (recommendations && recommendations.length > 0) {
            recommendations.forEach(prod => {
                const card = document.createElement('div');
                card.className = 'recommendation-card';
                card.innerHTML = `
                    <img src="${prod.image}" alt="${prod.name}">
                    <div class="info">
                        <span class="name">${prod.name}</span>
                        <span class="price">₹${prod.price}</span>
                    </div>
                `;
                card.onclick = () => window.location.href = `/product/${prod.id}`;
                messages.appendChild(card);
            });
        }
        messages.scrollTop = messages.scrollHeight;
    };

    const showTyping = () => {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing message bot';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = '<span></span><span></span><span></span>';
        messages.appendChild(typingDiv);
        messages.scrollTop = messages.scrollHeight;
        return typingDiv;
    };

    const handleSend = async () => {
        const text = input.value.trim();
        if (!text) return;

        addMessage(text, 'user');
        input.value = '';

        const typing = showTyping();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            const data = await response.json();
            
            typing.remove();
            addMessage(data.reply, 'bot', data.recommendations);
        } catch (error) {
            typing.remove();
            addMessage("Sorry, I'm having trouble connecting right now.", 'bot');
        }
    };

    sendBtn.addEventListener('click', handleSend);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });
});
