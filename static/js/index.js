var socketio = io();

const messages = document.getElementById("messages")

// Display message
const createMessage = (name, msg) => {
    const content = `
    <div class="text">
        <span>
            <strong>${name}</strong> ${msg}
        </span>
        <span class="muted">
        </span>
    </div>
    `;
    messages.innerHTML += content;
};

socketio.on("message", (data) => {
    createMessage(data.username, data.message)
});

// Send message
const sendMessage = () => {
    const message = document.getElementById("message");
    if (message.value == "") return;
    socketio.emit("message", { data: message.value });
    message.value = "";
};