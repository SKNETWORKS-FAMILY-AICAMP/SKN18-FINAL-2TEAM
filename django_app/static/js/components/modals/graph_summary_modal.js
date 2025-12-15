// Graph Summary Modal JavaScript
// Based on chat_graph.js pattern

(function () {
    let currentMessageId = null;

    document.addEventListener("DOMContentLoaded", () => {
        const graphModal = document.getElementById("graphSummaryModal");
        const graphModalBody = document.getElementById("graphSummaryContainer");
        const closeBtn = graphModal?.querySelector(".modal-close-btn");
        const backdrop = graphModal?.querySelector(".modal-overlay");
        const footerCloseBtn = graphModal?.querySelector('[data-action="close"]');

        if (!graphModal || !graphModalBody) return;

        function showLoading() {
            graphModalBody.innerHTML = `
                <div class="graph-modal__loading" style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 3rem;">
                    <div class="graph-modal__spinner" style="width: 40px; height: 40px; border: 4px solid #e5e7eb; border-top-color: #2563eb; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                    <p style="margin-top: 1rem; color: #6b7280;">그래프를 생성하는 중입니다...</p>
                </div>
                <style>
                    @keyframes spin {
                        to { transform: rotate(360deg); }
                    }
                </style>
            `;
        }

        function normalizeGraphCode(raw = "") {
            const trimmed = (raw || "").trim();
            if (!trimmed) return "";
            if (trimmed.startsWith("```")) {
                const cleaned = trimmed.replace(/^```[a-zA-Z]*\s*/, "").replace(/```$/, "");
                return wrapNodeLabels(cleaned.trim());
            }
            return wrapNodeLabels(trimmed);
        }

        function wrapNodeLabels(code) {
            return code.replace(/\[([^\]]+)\]/g, (match, content) => {
                const text = content.trim();
                if (
                    (text.startsWith('"') && text.endsWith('"')) ||
                    (text.startsWith("'") && text.endsWith("'"))
                ) {
                    return `[${text}]`;
                }
                const escaped = text.replace(/"/g, '\\"');
                return `["${escaped}"]`;
            });
        }

        async function renderGraph(code = "") {
            const graphCode = normalizeGraphCode(code);

            if (!graphCode) {
                graphModalBody.innerHTML = `<p class="graph-modal__empty" style="padding: 2rem; text-align: center; color: #6b7280;">그래프 데이터를 생성하지 못했습니다.</p>`;
                return;
            }

            try {
                // Check if mermaid is available
                if (!window.mermaid) {
                    console.error('Mermaid is not available');
                    graphModalBody.innerHTML = `<pre class="graph-modal__error" style="padding: 1rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 0.5rem; color: #991b1b; overflow-x: auto;">${graphCode}</pre>`;
                    return;
                }

                // Initialize mermaid if not already initialized
                if (window.mermaid && typeof window.mermaid.initialize === 'function') {
                    window.mermaid.initialize({ 
                        startOnLoad: false,
                        theme: 'default',
                        securityLevel: 'loose'
                    });
                }

                // Generate unique ID for the graph
                const graphId = `graph-summary-${Date.now()}`;
                
                // Render the graph
                const { svg } = await window.mermaid.render(graphId, graphCode);
                
                // Clear and set the SVG
                graphModalBody.innerHTML = svg;
                
                // Style the SVG
                const svgEl = graphModalBody.querySelector("svg");
                if (svgEl) {
                    svgEl.setAttribute("width", "100%");
                    svgEl.setAttribute("height", "auto");
                    svgEl.style.maxWidth = "100%";
                    svgEl.style.display = "block";
                    svgEl.style.margin = "0 auto";
                }
            } catch (err) {
                console.error("Mermaid render error:", err);
                graphModalBody.innerHTML = `
                    <div style="padding: 1rem;">
                        <p style="color: #dc2626; margin-bottom: 0.5rem;">그래프 렌더링 중 오류가 발생했습니다.</p>
                        <pre class="graph-modal__error" style="padding: 1rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 0.5rem; color: #991b1b; overflow-x: auto; font-size: 0.875rem;">${graphCode}</pre>
                    </div>
                `;
            }
        }

        async function loadGraphSummary(messageId, messageContent = null) {
            if (!messageId && !messageContent) {
                graphModalBody.innerHTML = `<p style="padding: 2rem; text-align: center; color: #6b7280;">메시지 정보가 없습니다.</p>`;
                return;
            }

            showLoading();

            try {
                // POST 요청으로 메시지 내용 전달
                const requestBody = {
                    message_id: messageId || null,
                    message_content: messageContent || ''
                };

                const response = await fetch('/chat/api/graph-summary/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(requestBody),
                });

                let graphCode = '';

                if (response.ok) {
                    const data = await response.json();
                    graphCode = data.graph || '';
                    
                    if (!graphCode) {
                        // 그래프 코드가 없으면 기본 그래프 생성
                        graphCode = generateDefaultGraph(messageId);
                    }
                } else {
                    // API 실패 시 에러 메시지 표시
                    const errorData = await response.json().catch(() => ({}));
                    console.error('Error loading graph summary:', errorData);
                    graphModalBody.innerHTML = `
                        <div style="padding: 2rem; text-align: center;">
                            <p style="color: #dc2626; margin-bottom: 0.5rem;">그래프 생성에 실패했습니다.</p>
                            <p style="color: #6b7280; font-size: 0.875rem;">${errorData.error || '알 수 없는 오류가 발생했습니다.'}</p>
                        </div>
                    `;
                    return;
                }

                // Render the graph
                requestAnimationFrame(() => renderGraph(graphCode));
            } catch (error) {
                console.error('Error loading graph summary:', error);
                graphModalBody.innerHTML = `
                    <div style="padding: 2rem; text-align: center;">
                        <p style="color: #dc2626; margin-bottom: 0.5rem;">그래프 생성 중 오류가 발생했습니다.</p>
                        <p style="color: #6b7280; font-size: 0.875rem;">${error.message || '네트워크 오류가 발생했습니다.'}</p>
                    </div>
                `;
            }
        }

        // Generate default graph based on message ID or chat context
        function generateDefaultGraph(messageId) {
            // This would be replaced with actual graph generation logic
            // For now, return a simple default graph
            return `graph TD
    A[질문] --> B[AI 분석]
    B --> C[답변 생성]
    C --> D[결과 제공]`;
        }

        // Public API
        window.GraphSummaryModal = {
            open(messageId = null, messageContent = null) {
                currentMessageId = messageId;
                
                // Show modal
                if (window.Modal && window.Modal.open) {
                    window.Modal.open('graphSummaryModal');
                } else {
                    // Fallback: show modal directly
                    if (graphModal) {
                        graphModal.style.display = 'flex';
                    }
                }

                // Load and render graph
                if (messageId || messageContent) {
                    loadGraphSummary(messageId, messageContent);
                } else {
                    // Try to get message ID from context
                    const urlParams = new URLSearchParams(window.location.search);
                    const msgId = urlParams.get('message_id') || 
                                document.querySelector('[data-message-id]')?.getAttribute('data-message-id');
                    if (msgId) {
                        loadGraphSummary(msgId);
                    } else {
                        showLoading();
                        setTimeout(() => {
                            renderGraph(generateDefaultGraph());
                        }, 500);
                    }
                }
            },
            close() {
                if (window.Modal && window.Modal.close) {
                    window.Modal.close('graphSummaryModal');
                } else {
                    // Fallback: hide modal directly
                    if (graphModal) {
                        graphModal.style.display = 'none';
                    }
                }
                graphModalBody.innerHTML = "";
                currentMessageId = null;
            },
            showLoading,
        };

        function closeModal() {
            window.GraphSummaryModal.close();
        }

        // Event listeners
        if (closeBtn) closeBtn.addEventListener("click", closeModal);
        if (footerCloseBtn) footerCloseBtn.addEventListener("click", closeModal);
        if (backdrop) backdrop.addEventListener("click", (e) => {
            if (e.target === backdrop) {
                closeModal();
            }
        });

        // Listen for modal open event
        document.addEventListener('modal:open', (e) => {
            if (e.detail.modalId === 'graphSummaryModal') {
                const messageId = currentMessageId || 
                                e.detail.messageId ||
                                document.querySelector('[data-message-id]')?.getAttribute('data-message-id');
                if (messageId) {
                    loadGraphSummary(messageId);
                }
            }
        });
    });
})();

// Get CSRF token
function getCsrfToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'csrftoken') {
            return value;
        }
    }
    // Try to get from meta tag
    const metaTag = document.querySelector('meta[name=csrf-token]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    return '';
}
