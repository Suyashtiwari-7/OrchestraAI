// OrchestraAI — Frontend Controller App

document.addEventListener("DOMContentLoaded", () => {
    // UI Elements
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const chatMessages = document.getElementById("chat-messages");
    const welcomeScreen = document.getElementById("welcome-screen");
    const chatLoading = document.getElementById("chat-loading");
    const loadingStatus = document.getElementById("loading-status");
    
    const sidebar = document.getElementById("app-sidebar");
    const sidebarToggle = document.getElementById("sidebar-toggle");
    
    const providerStatusList = document.getElementById("provider-status-list");
    const routingTableBody = document.getElementById("routing-table-body");
    
    const btnClear = document.getElementById("btn-clear");
    const btnClearMobile = document.getElementById("clear-chat-mobile");
    const btnExport = document.getElementById("btn-export");
    
    const overridePills = document.querySelectorAll(".override-pill");
    const quickPromptCards = document.querySelectorAll(".quick-prompt-card");

    // Local State
    let activeOverrideProvider = ""; // "gemini", "groq", "cerebras", or ""
    let chatHistory = [];

    // Initialize Page
    fetchSystemStatus();
    fetchRoutingTable();
    loadChatHistory();

    // Hide mascot overlay if running inside the desktop app webview
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('desktop') === 'true') {
        const mascot = document.getElementById('robot-mascot');
        const cmdWindow = document.getElementById('mascot-command-window');
        if (mascot) mascot.style.display = 'none';
        if (cmdWindow) cmdWindow.style.display = 'none';
    }

    // --- Event Listeners ---

    // Toggle Sidebar (Mobile view)
    sidebarToggle.addEventListener("click", (e) => {
        e.stopPropagation();
        sidebar.classList.toggle("active");
    });

    // Close Sidebar clicking outside on mobile
    document.addEventListener("click", (e) => {
        if (window.innerWidth <= 768 && sidebar.classList.contains("active")) {
            if (!sidebar.contains(e.target) && e.target !== sidebarToggle) {
                sidebar.classList.remove("active");
            }
        }
    });

    // Quick Prompt Cards click handler
    quickPromptCards.forEach(card => {
        card.addEventListener("click", () => {
            const prompt = card.getAttribute("data-prompt");
            userInput.value = prompt;
            userInput.focus();
        });
    });

    // Provider override selector pills
    overridePills.forEach(pill => {
        pill.addEventListener("click", () => {
            overridePills.forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            activeOverrideProvider = pill.getAttribute("data-provider");
            userInput.focus();
        });
    });

    // Chat form submit handler
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (!text) return;

        // Clear input field
        userInput.value = "";

        // Add user bubble
        appendMessageBubble("user", text);
        
        // Hide welcome screen
        welcomeScreen.classList.add("hidden");

        // Close sidebar if open on mobile
        if (window.innerWidth <= 768) {
            sidebar.classList.remove("active");
        }

        // Show loading spinner
        showLoader("Classifying task routing...");

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    prompt: text,
                    provider_override: activeOverrideProvider
                })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Server error occurred");
            }

            const data = await response.json();
            
            // Hide loader
            hideLoader();

            // Add assistant bubble
            appendMessageBubble("assistant", data.content, data);

        } catch (error) {
            hideLoader();
            appendMessageBubble("assistant", `❌ **Error:** ${error.message}. Please verify your API keys are configured and try again.`);
        }
    });

    // Clear Memory handler
    const clearMemoryAction = async () => {
        if (confirm("Are you sure you want to clear the conversation memory?")) {
            try {
                const response = await fetch("/api/clear", { method: "POST" });
                if (response.ok) {
                    chatMessages.innerHTML = "";
                    welcomeScreen.classList.remove("hidden");
                    chatHistory = [];
                }
            } catch (error) {
                console.error("Failed to clear chat memory:", error);
            }
        }
    };
    btnClear.addEventListener("click", clearMemoryAction);
    btnClearMobile.addEventListener("click", clearMemoryAction);

    // Export Chat History handler
    btnExport.addEventListener("click", () => {
        if (chatHistory.length === 0) {
            alert("No conversation history to export.");
            return;
        }
        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(chatHistory, null, 2));
        const downloadAnchor = document.createElement('a');
        downloadAnchor.setAttribute("href", dataStr);
        downloadAnchor.setAttribute("download", `orchestra_chat_${new Date().toISOString().slice(0,10)}.json`);
        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();
    });

    // --- API Functions ---

    // Fetch API status & configurations
    async function fetchSystemStatus() {
        try {
            const response = await fetch("/api/status");
            if (!response.ok) throw new Error();
            const data = await response.json();
            
            // Render providers list in sidebar
            providerStatusList.innerHTML = "";
            data.providers.forEach(p => {
                const statusDotClass = p.configured ? "active" : "inactive";
                const statusTagText = p.configured ? "Active" : "Disabled";
                const statusTagClass = p.configured ? "active" : "inactive";
                
                const row = document.createElement("div");
                row.className = "provider-status-row";
                row.innerHTML = `
                    <div class="provider-info">
                        <span class="provider-status-dot ${statusDotClass}"></span>
                        <span>${p.display_name}</span>
                    </div>
                    <span class="status-tag ${statusTagClass}">${statusTagText}</span>
                `;
                providerStatusList.appendChild(row);
            });
        } catch (error) {
            providerStatusList.innerHTML = `<div class="provider-loading" style="color:red">Failed to reach API server</div>`;
        }
    }

    // Fetch routing matrix for sidebar display
    async function fetchRoutingTable() {
        try {
            const response = await fetch("/api/models");
            if (!response.ok) throw new Error();
            const data = await response.json();
            
            routingTableBody.innerHTML = "";
            data.routes.forEach(r => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td>
                        <strong>${r.task_type}</strong>
                        <span class="sub">${r.description}</span>
                    </td>
                    <td>${r.primary_model} <span class="sub">${r.primary_provider.toUpperCase()}</span></td>
                `;
                routingTableBody.appendChild(row);
            });
        } catch (error) {
            console.error("Failed to load routing table:", error);
        }
    }

    // Load existing history from backend
    async function loadChatHistory() {
        try {
            const response = await fetch("/api/history");
            if (!response.ok) throw new Error();
            const data = await response.json();
            
            chatHistory = data.history || [];
            
            if (chatHistory.length > 0) {
                welcomeScreen.classList.add("hidden");
                chatHistory.forEach(entry => {
                    // Reconstruct meta-structure for assistant bubbles
                    const meta = entry.role === "assistant" ? {
                        task_type: entry.task_type,
                        model_used: entry.model_used,
                        provider_used: entry.provider,
                        latency_ms: 0,
                        used_fallback: false
                    } : null;
                    appendMessageBubble(entry.role, entry.content, meta, false);
                });
            }
        } catch (error) {
            console.error("Failed to fetch history:", error);
        }
    }

    // --- UI Render Helpers ---

    function showLoader(statusText) {
        loadingStatus.innerText = statusText;
        chatLoading.classList.remove("hidden");
        scrollToBottom();
    }

    function hideLoader() {
        chatLoading.classList.add("hidden");
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Render message bubble in flow
    function appendMessageBubble(role, text, metadata = null, updateLocalState = true) {
        const wrapper = document.createElement("div");
        wrapper.className = `chat-bubble-wrapper ${role}`;
        
        let metadataHTML = "";
        let toolsHTML = "";
        
        let isTerminalCommand = false;
        let isSandboxCode = false;
        let commandStr = "";
        let commandReasoning = "";
        
        if (role === "assistant" && text.startsWith("PENDING_TERMINAL_COMMAND:")) {
            isTerminalCommand = true;
            const parts = text.split(":");
            commandStr = parts[1];
            commandReasoning = parts.slice(2).join(":");
        } else if (role === "assistant" && text.startsWith("PENDING_SANDBOX_CODE:")) {
            isSandboxCode = true;
            const parts = text.split(":");
            try {
                commandStr = atob(parts[1]); // decode base64
            } catch (err) {
                commandStr = parts[1];
            }
            commandReasoning = parts.slice(2).join(":");
        }
        
        // Add metadata headers for assistant
        if (role === "assistant" && metadata) {
            const providerClass = metadata.provider_used ? metadata.provider_used.toLowerCase() : "default";
            const fallbackHTML = metadata.used_fallback ? `<span class="msg-meta-pill fallback-tag">⚠ Fallback Used</span>` : "";
            const latencyText = metadata.latency_ms > 0 ? `<span class="msg-meta-pill latency">⏱ ${metadata.latency_ms.toFixed(0)}ms</span>` : "";
            
            const providerEmojiMap = {
                "gemini": "🔵",
                "groq": "🟢",
                "cerebras": "🟣",
                "sambanova": "🌋",
                "mistral": "🌪️",
                "cohere": "🌿",
                "pollinations": "🎨"
            };
            const providerEmoji = providerEmojiMap[providerClass] || "🟣";
            
            metadataHTML = `
                <div class="msg-metadata">
                    <span class="msg-meta-pill ${providerClass}">
                        ${providerEmoji} ${metadata.model_used}
                    </span>
                    <span class="msg-meta-pill task-type ${metadata.task_type === 'system_command' ? 'system-command' : ''}">
                        ${metadata.task_type === 'system_command' ? '💻 system_command' : metadata.task_type}
                    </span>
                    ${latencyText}
                    ${fallbackHTML}
                    <button class="msg-meta-pill tts-btn" onclick="toggleReadAloud(this)" title="Read Aloud" style="cursor:pointer; border-radius:12px; margin-left:auto;">
                        🔊 Listen
                    </button>
                </div>
            `;

            // If image url exists
            if (metadata.image_url) {
                toolsHTML += `
                    <div class="generated-image-card">
                        <img src="${metadata.image_url}" alt="AI Generated Image">
                        <div class="image-actions">
                            <span>Image output saved to disk</span>
                            <a href="${metadata.image_url}" download="orchestra_gen.png" class="image-download-btn">Download</a>
                        </div>
                    </div>
                `;
            }

            // If saved files list exists
            if (metadata.saved_files && metadata.saved_files.length > 0) {
                toolsHTML += `<div class="saved-files-list">`;
                metadata.saved_files.forEach(filepath => {
                    toolsHTML += `
                        <div class="saved-file-row">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
                            File saved: ${filepath}
                        </div>
                    `;
                });
                toolsHTML += `</div>`;
            }
        }

        let parsedContent = "";
        if (isTerminalCommand) {
            parsedContent = `
                <div class="terminal-card">
                    <div class="terminal-title">
                        <span>⚠️ Pending Terminal Command Execution</span>
                    </div>
                    <div class="terminal-reasoning">
                        <strong>Reasoning:</strong> ${commandReasoning}
                    </div>
                    <div class="terminal-cmd-block">
                        <code>${commandStr}</code>
                    </div>
                    <div class="terminal-actions">
                        <button class="terminal-btn approve" onclick="confirmTerminalCommand(this, '${commandStr}')">Run Command</button>
                        <button class="terminal-btn reject" onclick="rejectTerminalCommand(this)">Reject</button>
                    </div>
                </div>
            `;
        } else if (isSandboxCode) {
            const escapedCode = commandStr.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            parsedContent = `
                <div class="terminal-card sandbox-card">
                    <div class="terminal-title">
                        <span>🐍 Pending Python Sandbox Execution</span>
                    </div>
                    <div class="terminal-reasoning">
                        <strong>Reasoning:</strong> ${commandReasoning}
                    </div>
                    <div class="terminal-cmd-block sandbox-code-block">
                        <pre><code>${escapedCode}</code></pre>
                    </div>
                    <div class="terminal-actions">
                        <button class="terminal-btn approve sandbox-btn" onclick="confirmSandboxCommand(this)">Run Python Script</button>
                        <button class="terminal-btn reject" onclick="rejectSandboxCommand(this)">Reject</button>
                    </div>
                </div>
            `;
        } else {
            parsedContent = parseMarkdown(text);
        }
        
        wrapper.innerHTML = `
            ${metadataHTML}
            <div class="chat-bubble">
                ${parsedContent}
                ${toolsHTML}
            </div>
        `;
        
        chatMessages.appendChild(wrapper);
        scrollToBottom();

        // Update local history cache for export utilities
        if (updateLocalState) {
            chatHistory.push({
                role: role,
                content: text,
                model_used: metadata ? metadata.model_used : "",
                provider: metadata ? metadata.provider_used : "",
                task_type: metadata ? metadata.task_type : "",
                timestamp: new Date().toISOString()
            });
        }
    }

    // Simple robust Regex Markdown Parser with syntax container
    function parseMarkdown(text) {
        // Safe escaping function
        const escapeHTML = str => str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        
        let html = text;

        // 1. Extract block code segments to prevent inline replacements inside codes
        const codeBlocks = [];
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const index = codeBlocks.length;
            const escapedCode = escapeHTML(code.trim());
            const langLabel = lang || "code";
            
            codeBlocks.push(`
                <div class="code-block-container">
                    <div class="code-header">
                        <span>${langLabel.toUpperCase()}</span>
                        <button class="btn-copy-code" onclick="navigator.clipboard.writeText(this.parentNode.nextElementSibling.innerText); this.innerText='Copied!'; setTimeout(() => this.innerText='Copy', 2000);">Copy</button>
                    </div>
                    <pre><code>${escapedCode}</code></pre>
                </div>
            `);
            return `__CODE_BLOCK_PLACEHOLDER_${index}__`;
        });

        // Escaping normal HTML in text
        html = escapeHTML(html);

        // 2. Headings (###)
        html = html.replace(/^### (.*?)$/gm, "<h3>$1</h3>");
        html = html.replace(/^## (.*?)$/gm, "<h2>$1</h2>");
        html = html.replace(/^# (.*?)$/gm, "<h1>$1</h1>");

        // 3. Bold (**)
        html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

        // 4. Inline code (`)
        html = html.replace(/`(.*?)`/g, "<code>$1</code>");

        // 5. Bullet lists (- or *)
        let inList = false;
        const lines = html.split("\n");
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].trim().startsWith("- ") || lines[i].trim().startsWith("* ")) {
                const cleanItem = lines[i].trim().substring(2);
                if (!inList) {
                    lines[i] = "<ul><li>" + cleanItem + "</li>";
                    inList = true;
                } else {
                    lines[i] = "<li>" + cleanItem + "</li>";
                }
            } else {
                if (inList) {
                    lines[i-1] = lines[i-1] + "</ul>";
                    inList = false;
                }
            }
        }
        if (inList) {
            lines[lines.length - 1] = lines[lines.length - 1] + "</ul>";
        }
        html = lines.join("\n");

        // 6. Restore block code segments
        codeBlocks.forEach((blockHTML, index) => {
            html = html.replace(`__CODE_BLOCK_PLACEHOLDER_${index}__`, blockHTML);
        });

        // 7. Linebreaks to <br> (excluding inside blocks)
        html = html.split("\n").map(line => {
            if (line.includes("<div") || line.includes("<pre") || line.includes("<code") || line.includes("</pre") || line.includes("</div") || line.includes("<li>") || line.includes("<ul>") || line.includes("</ul>")) {
                return line;
            }
            return line + "<br>";
        }).join("\n");

        return html;
    }

    // --- Robot Mascot Interaction ---
    const robotMascot = document.getElementById("robot-mascot");
    const mascotCommandWindow = document.getElementById("mascot-command-window");
    const mascotCloseBtn = document.getElementById("mascot-close-btn");
    const mascotSubmitBtn = document.getElementById("mascot-submit-btn");
    const mascotInput = document.getElementById("mascot-input");

    // Toggle mascot quick command window
    robotMascot.addEventListener("click", () => {
        mascotCommandWindow.classList.toggle("hidden");
        if (!mascotCommandWindow.classList.contains("hidden")) {
            mascotInput.focus();
        }
    });

    // Close mascot window
    mascotCloseBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        mascotCommandWindow.classList.add("hidden");
    });

    // Submit quick command from mascot
    const submitMascotCommand = async () => {
        const text = mascotInput.value.trim();
        if (!text) return;

        mascotInput.value = "";
        mascotCommandWindow.classList.add("hidden");

        // Display user bubble in chat
        appendMessageBubble("user", text);
        welcomeScreen.classList.add("hidden");

        // Animate bot to listening state
        robotMascot.className = "robot-mascot listening";
        showLoader("DARKI parsing command...");

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    prompt: text,
                    provider_override: activeOverrideProvider
                })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Server error occurred");
            }

            const data = await response.json();
            hideLoader();

            // Display assistant response
            appendMessageBubble("assistant", data.content, data);

            // Animate bot to success state
            robotMascot.className = "robot-mascot success";
            setTimeout(() => {
                robotMascot.className = "robot-mascot";
            }, 2500);

        } catch (error) {
            hideLoader();
            appendMessageBubble("assistant", `❌ **Error:** ${error.message}. Please verify your API keys are configured and try again.`);
            
            // Animate bot to error state
            robotMascot.className = "robot-mascot error";
            setTimeout(() => {
                robotMascot.className = "robot-mascot";
            }, 2500);
        }
    };

    mascotSubmitBtn.addEventListener("click", submitMascotCommand);
    mascotInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            submitMascotCommand();
        }
    });

    // --- Global Window Helpers (TTS & Terminal execution) ---
    
    // Text-to-Speech (TTS)
    let currentUtterance = null;
    window.toggleReadAloud = (button) => {
        if (window.speechSynthesis.speaking) {
            window.speechSynthesis.cancel();
            if (currentUtterance && currentUtterance.button === button) {
                button.innerHTML = "🔊 Listen";
                currentUtterance = null;
                return;
            }
        }

        const bubbleWrapper = button.closest(".chat-bubble-wrapper");
        const bubble = bubbleWrapper.querySelector(".chat-bubble");
        
        // Extract clean text (removing copy blocks and pending commands)
        let cleanText = bubble.innerText;
        cleanText = cleanText.replace(/COPY\n/g, "");
        
        // Strip out pending terminal command block text if present
        if (cleanText.includes("Pending Terminal Command Execution")) {
            cleanText = "This response is a pending terminal command awaiting your execution approval.";
        }

        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.button = button;

        utterance.onend = () => {
            button.innerHTML = "🔊 Listen";
            currentUtterance = null;
        };

        utterance.onerror = () => {
            button.innerHTML = "🔊 Listen";
            currentUtterance = null;
        };

        button.innerHTML = "⏹ Stop";
        currentUtterance = utterance;
        window.speechSynthesis.speak(utterance);
    };

    // Review & Proceed Command Executor
    window.confirmTerminalCommand = async (button, command) => {
        button.disabled = true;
        button.innerText = "Running...";
        button.nextElementSibling.disabled = true;
        
        // Animate mascot to listening state
        const mascot = document.getElementById("robot-mascot");
        mascot.className = "robot-mascot listening";
        
        try {
            const response = await fetch("/api/terminal/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ command })
            });
            
            const data = await response.json();
            
            // Remove button panel and append status
            const actionsDiv = button.parentNode;
            if (data.success) {
                actionsDiv.innerHTML = `<span style="color:var(--accent-green)">✓ Executed successfully</span>`;
                mascot.className = "robot-mascot success";
                setTimeout(() => mascot.className = "robot-mascot", 2000);
            } else {
                actionsDiv.innerHTML = `<span style="color:red">✗ Failed to execute</span>`;
                mascot.className = "robot-mascot error";
                setTimeout(() => mascot.className = "robot-mascot", 2000);
            }
            
            // Append response output bubble
            appendMessageBubble("assistant", data.formatted_output, {
                task_type: "system_command",
                model_used: "System Shell",
                provider_used: "localhost",
                latency_ms: 0,
                used_fallback: false
            }, true);
            
        } catch (error) {
            button.innerText = "Error";
            console.error(error);
            mascot.className = "robot-mascot error";
            setTimeout(() => mascot.className = "robot-mascot", 2000);
        }
    };

    window.rejectTerminalCommand = (button) => {
        button.disabled = true;
        button.previousElementSibling.disabled = true;
        button.parentNode.innerHTML = `<span style="color:var(--text-disabled)">✗ Command rejected by user</span>`;
    };

    window.confirmSandboxCommand = async (button) => {
        const card = button.closest(".sandbox-card");
        const code = card.querySelector(".sandbox-code-block pre code").innerText;
        
        button.disabled = true;
        button.innerText = "Executing...";
        button.nextElementSibling.disabled = true;
        
        const mascot = document.getElementById("robot-mascot");
        mascot.className = "robot-mascot listening";
        
        try {
            const response = await fetch("/api/sandbox/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code })
            });
            
            const data = await response.json();
            const actionsDiv = button.parentNode;
            
            if (data.success) {
                actionsDiv.innerHTML = `<span style="color:var(--accent-green)">✓ Executed successfully</span>`;
                mascot.className = "robot-mascot success";
                setTimeout(() => mascot.className = "robot-mascot", 2000);
            } else {
                actionsDiv.innerHTML = `<span style="color:red">✗ Execution failed</span>`;
                mascot.className = "robot-mascot error";
                setTimeout(() => mascot.className = "robot-mascot", 2000);
            }
            
            appendMessageBubble("assistant", data.formatted_output, {
                task_type: "system_command",
                model_used: "Python Sandbox",
                provider_used: "localhost",
                latency_ms: 0,
                used_fallback: false
            }, true);
            
        } catch (error) {
            button.innerText = "Error";
            console.error(error);
            mascot.className = "robot-mascot error";
            setTimeout(() => mascot.className = "robot-mascot", 2000);
        }
    };

    window.rejectSandboxCommand = (button) => {
        button.disabled = true;
        button.previousElementSibling.disabled = true;
        button.parentNode.innerHTML = `<span style="color:var(--text-disabled)">✗ Execution rejected by user</span>`;
    };

    // --- Speech Recognition & Voice Activation ("Hey DARKI") ---
    let wakeWordRecognition = null;
    let isWakeWordListening = false;
    let manualRecognition = null;
    let isManualListening = false;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const voiceToggleBtn = document.getElementById("voice-toggle-btn");
    const micBtn = document.getElementById("mic-btn");
    const mascotMicBtn = document.getElementById("mascot-mic-btn");

    if (SpeechRecognition) {
        // 1. Manual Dictation setup
        manualRecognition = new SpeechRecognition();
        manualRecognition.continuous = false;
        manualRecognition.interimResults = false;
        manualRecognition.lang = 'en-US';

        // 2. Wake-word continuous listening setup
        wakeWordRecognition = new SpeechRecognition();
        wakeWordRecognition.continuous = true;
        wakeWordRecognition.interimResults = true;
        wakeWordRecognition.lang = 'en-US';

        // Synthesise audio wake chime
        function playWakeChime() {
            try {
                const AudioContext = window.AudioContext || window.webkitAudioContext;
                if (!AudioContext) return;
                const ctx = new AudioContext();
                
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = "sine";
                osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
                osc.frequency.exponentialRampToValueAtTime(783.99, ctx.currentTime + 0.15); // G5
                
                gain.gain.setValueAtTime(0.08, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
                
                osc.connect(gain);
                gain.connect(ctx.destination);
                
                osc.start();
                osc.stop(ctx.currentTime + 0.25);
            } catch (err) {
                console.log("AudioContext failed:", err);
            }
        }

        // Toggle manual push-to-talk dictation
        function toggleManualDictation(inputElement, buttonElement) {
            if (isManualListening) {
                manualRecognition.stop();
                return;
            }

            if (isWakeWordListening) {
                wakeWordRecognition.stop();
            }

            buttonElement.classList.add("recording");
            isManualListening = true;

            manualRecognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                inputElement.value = transcript;
                inputElement.focus();
            };

            manualRecognition.onend = () => {
                buttonElement.classList.remove("recording");
                isManualListening = false;
                
                // Restart wake word background listening if enabled
                if (isWakeWordListening) {
                    try { wakeWordRecognition.start(); } catch(e){}
                }
            };

            manualRecognition.onerror = (err) => {
                console.error("Manual STT error:", err.error);
                buttonElement.classList.remove("recording");
                isManualListening = false;
                
                if (isWakeWordListening) {
                    try { wakeWordRecognition.start(); } catch(e){}
                }
            };

            manualRecognition.start();
        }

        if (micBtn) {
            micBtn.addEventListener("click", () => {
                toggleManualDictation(userInput, micBtn);
            });
        }

        if (mascotMicBtn) {
            mascotMicBtn.addEventListener("click", () => {
                toggleManualDictation(mascotInput, mascotMicBtn);
            });
        }

        // Wake word result parsing
        wakeWordRecognition.onresult = (event) => {
            let transcript = "";
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                transcript += event.results[i][0].transcript;
            }
            
            transcript = transcript.toLowerCase().trim();
            console.log("[Wake Word Monitor]:", transcript);

            const triggers = ["darki", "hey darki", "hi darki", "okay darki", "ok darki", "hey ducky", "hey docky"];
            let triggered = false;
            let query = "";

            for (const t of triggers) {
                if (transcript.includes(t)) {
                    triggered = true;
                    const idx = transcript.lastIndexOf(t);
                    query = transcript.substring(idx + t.length).trim();
                    break;
                }
            }

            // Trigger action if query exists following the wake word
            if (triggered && query.length > 3) {
                wakeWordRecognition.stop(); // Stop listening during process
                playWakeChime();
                
                // Wake up Mascot widget
                const mascot = document.getElementById("robot-mascot");
                mascot.className = "robot-mascot listening";

                userInput.value = query;
                
                // Trigger form submission after brief visual confirmation
                setTimeout(() => {
                    chatForm.dispatchEvent(new Event("submit"));
                }, 800);
            }
        };

        wakeWordRecognition.onend = () => {
            // Restart automatically if toggled ON and manual dictation is not active
            if (isWakeWordListening && !isManualListening) {
                try { wakeWordRecognition.start(); } catch(e){}
            }
        };

        wakeWordRecognition.onerror = (event) => {
            if (event.error !== 'no-speech') {
                console.warn("[Wake Word Engine Error]:", event.error);
            }
        };

        // Toggle background "Hey DARKI" wake word listener
        if (voiceToggleBtn) {
            voiceToggleBtn.addEventListener("click", () => {
                if (isWakeWordListening) {
                    isWakeWordListening = false;
                    wakeWordRecognition.stop();
                    voiceToggleBtn.classList.remove("active");
                    voiceToggleBtn.innerHTML = "🎙️ Hey DARKI: OFF";
                } else {
                    isWakeWordListening = true;
                    voiceToggleBtn.classList.add("active");
                    voiceToggleBtn.innerHTML = "🎙️ Hey DARKI: ON";
                    try {
                        wakeWordRecognition.start();
                        playWakeChime();
                    } catch(e) {
                        console.error("Failed to start wake word engine:", e);
                    }
                }
            });
        }
    } else {
        // Fallback for unsupported browsers
        if (voiceToggleBtn) voiceToggleBtn.style.display = "none";
        if (micBtn) micBtn.style.display = "none";
        if (mascotMicBtn) mascotMicBtn.style.display = "none";
        console.warn("SpeechRecognition API is not supported in this browser environment.");
    }
});
