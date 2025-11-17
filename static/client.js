document.addEventListener("DOMContentLoaded", function () {

    const socket = io();
    const outputEl = document.getElementById("terminal-output");
    const inputEl = document.getElementById("terminal-input");
    const prompt = "sophy@field:~$ ";

    function refocus() {
        setTimeout(() => inputEl.focus(), 10);
    }

    refocus();

    function appendOutput(text, className = "") {
        const span = document.createElement("span");
        if (className) span.classList.add(className);
        span.textContent = text;
        outputEl.appendChild(span);
        outputEl.appendChild(document.createElement("br"));
        outputEl.scrollTop = outputEl.scrollHeight;
    }

    // ENTER key command handler
    inputEl.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            const cmd = inputEl.value.trim();

            if (cmd.length > 0) {
                appendOutput(prompt + cmd, "command-text");
                socket.emit("command", { command: cmd });
            } else {
                appendOutput(prompt);
            }

            inputEl.value = "";
            refocus();
        }
    });

    socket.on("output", function (data) {
        if (data.result && data.result.trim().length > 0) {
            appendOutput(data.result);
        }
        appendOutput(prompt);
        refocus();
    });

    // floating avatar drag
    const avatar = document.getElementById("avatar-ball");
    let dragging = false, offsetX = 0, offsetY = 0;

    avatar.addEventListener("mousedown", (e) => {
        dragging = true;
        offsetX = e.clientX - avatar.offsetLeft;
        offsetY = e.clientY - avatar.offsetTop;
        avatar.style.cursor = "grabbing";
    });

    document.addEventListener("mousemove", (e) => {
        if (!dragging) return;
        avatar.style.left = (e.clientX - offsetX) + "px";
        avatar.style.top = (e.clientY - offsetY) + "px";
    });

    document.addEventListener("mouseup", () => {
        dragging = false;
        avatar.style.cursor = "grab";
    });

});
