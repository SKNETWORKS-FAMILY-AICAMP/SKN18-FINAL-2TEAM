// Markdown Utility Functions
// Uses markdown-it library from django_ui

/**
 * Render markdown content to HTML
 * @param {string} markdown - Markdown content
 * @param {object} options - Rendering options
 * @returns {string} HTML string
 */
function renderMarkdown(markdown, options = {}) {
    if (!markdown) return '';
    
    // Use markdown-it if available
    if (typeof window.MarkdownIt !== 'undefined') {
        const md = new window.MarkdownIt({
            html: options.html !== false, // Enable HTML tags
            linkify: options.linkify !== false, // Autoconvert URL-like text to links
            breaks: options.breaks || false, // Convert '\n' in paragraphs into <br>
            typographer: options.typographer !== false, // Enable some language-neutral replacement
        });
        
        // Enable table support (markdown-it supports tables by default in some configurations)
        // If markdown-it-table plugin is available, use it
        if (typeof window.MarkdownItTable !== 'undefined') {
            md.use(window.MarkdownItTable);
        }
        
        // Add plugins if needed
        if (options.highlight && typeof window.hljs !== 'undefined') {
            md.set({
                highlight: function (str, lang) {
                    if (lang && window.hljs.getLanguage(lang)) {
                        try {
                            return window.hljs.highlight(str, { language: lang }).value;
                        } catch (__) {}
                    }
                    return '';
                }
            });
        }
        
        return md.render(markdown);
    }
    
    // Fallback: simple markdown parser
    return parseMarkdownSimple(markdown);
}

/**
 * Simple markdown parser (fallback)
 * @param {string} markdown - Markdown content
 * @returns {string} HTML string
 */
function parseMarkdownSimple(markdown) {
    if (!markdown) return '';
    
    let html = markdown;
    
    // Code blocks (must be processed before other replacements)
    html = html.replace(/```([\s\S]*?)```/gim, '<pre><code>$1</code></pre>');
    
    // Inline code (must be processed before bold/italic)
    html = html.replace(/`([^`]+)`/gim, '<code>$1</code>');
    
    // Headings
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    
    // Blockquotes
    html = html.replace(/^>\s+(.*$)/gim, '<blockquote>$1</blockquote>');
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    html = html.replace(/__(.*?)__/gim, '<strong>$1</strong>');
    
    // Italic
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
    html = html.replace(/_(.*?)_/gim, '<em>$1</em>');
    
    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2">$1</a>');
    
    // Lists (unordered)
    html = html.replace(/^[\s]*[-*+]\s+(.*$)/gim, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // Lists (ordered)
    html = html.replace(/^[\s]*\d+\.\s+(.*$)/gim, '<li>$1</li>');
    
    // Line breaks
    html = html.replace(/\n\n/gim, '</p><p>');
    html = html.replace(/\n/gim, '<br>');
    
    // Wrap in paragraph if not already wrapped
    if (!html.startsWith('<')) {
        html = '<p>' + html + '</p>';
    }
    
    return html;
}

/**
 * Render markdown to a DOM element
 * @param {string} markdown - Markdown content
 * @param {HTMLElement} container - Container element
 * @param {object} options - Rendering options
 */
function renderMarkdownToElement(markdown, container, options = {}) {
    if (!container) return;
    
    const html = renderMarkdown(markdown, options);
    container.innerHTML = html;
    
    // Process code blocks for syntax highlighting
    if (options.highlight && typeof window.hljs !== 'undefined') {
        container.querySelectorAll('pre code').forEach(block => {
            window.hljs.highlightElement(block);
        });
    }
    
    // Process Mermaid diagrams
    if (options.processMermaid && typeof window.mermaid !== 'undefined') {
        container.querySelectorAll('.language-mermaid, .mermaid').forEach(element => {
            const mermaidCode = element.textContent;
            if (mermaidCode) {
                window.MermaidChart.render(mermaidCode, element.parentElement);
            }
        });
    }
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Unescape HTML
 * @param {string} html - HTML to unescape
 * @returns {string} Unescaped text
 */
function unescapeHtml(html) {
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || div.innerText || '';
}

/**
 * Strip markdown formatting
 * @param {string} markdown - Markdown content
 * @returns {string} Plain text
 */
function stripMarkdown(markdown) {
    if (!markdown) return '';
    
    let text = markdown;
    
    // Remove code blocks
    text = text.replace(/```[\s\S]*?```/g, '');
    
    // Remove inline code
    text = text.replace(/`[^`]+`/g, '');
    
    // Remove links but keep text
    text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
    
    // Remove images
    text = text.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1');
    
    // Remove bold/italic
    text = text.replace(/\*\*([^*]+)\*\*/g, '$1');
    text = text.replace(/\*([^*]+)\*/g, '$1');
    text = text.replace(/__([^_]+)__/g, '$1');
    text = text.replace(/_([^_]+)_/g, '$1');
    
    // Remove headers
    text = text.replace(/^#{1,6}\s+(.*)$/gm, '$1');
    
    // Remove list markers
    text = text.replace(/^[\s]*[-*+]\s+/gm, '');
    text = text.replace(/^[\s]*\d+\.\s+/gm, '');
    
    // Remove blockquotes
    text = text.replace(/^>\s+/gm, '');
    
    // Clean up whitespace
    text = text.replace(/\n{3,}/g, '\n\n');
    text = text.trim();
    
    return text;
}

/**
 * Extract text preview from markdown
 * @param {string} markdown - Markdown content
 * @param {number} maxLength - Maximum length of preview
 * @returns {string} Preview text
 */
function getMarkdownPreview(markdown, maxLength = 150) {
    const text = stripMarkdown(markdown);
    if (text.length <= maxLength) {
        return text;
    }
    return text.substring(0, maxLength).trim() + '...';
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.MarkdownUtils = {
        render: renderMarkdown,
        renderToElement: renderMarkdownToElement,
        parseSimple: parseMarkdownSimple,
        escape: escapeHtml,
        unescape: unescapeHtml,
        strip: stripMarkdown,
        getPreview: getMarkdownPreview,
    };
}
