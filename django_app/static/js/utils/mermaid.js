// Mermaid Chart Utility Functions
// Uses mermaid library from django_ui

// Mermaid configuration
// React: startOnLoad: true, theme: 'default', flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' }
const mermaidConfig = {
    startOnLoad: false, // 수동 초기화 (자동 렌더링은 renderAll에서 처리)
    theme: 'default', // React와 동일
    themeVariables: {
        primaryColor: '#2563eb',
        primaryTextColor: '#ffffff',
        primaryBorderColor: '#1d4ed8',
        lineColor: '#9ca3af',
        secondaryColor: '#f3f4f6',
        tertiaryColor: '#ffffff',
        background: '#ffffff',
        mainBkg: '#ffffff',
        secondBkg: '#f9fafb',
        textColor: '#111827',
    },
    flowchart: {
        useMaxWidth: true, // React와 동일
        htmlLabels: true, // React와 동일
        curve: 'basis', // React와 동일
        padding: 20,
    },
    sequence: {
        diagramMarginX: 50,
        diagramMarginY: 10,
        actorMargin: 50,
        width: 150,
        height: 65,
        boxMargin: 10,
        boxTextMargin: 5,
        noteMargin: 10,
        messageMargin: 35,
        mirrorActors: true,
        bottomMarginAdj: 1,
        useMaxWidth: true,
        rightAngles: false,
        showSequenceNumbers: false,
    },
    gantt: {
        titleTopMargin: 25,
        barHeight: 20,
        barGap: 4,
        topPadding: 50,
        leftPadding: 75,
        gridLineStartPadding: 35,
        fontSize: 11,
        fontFamily: '"Arial", sans-serif',
        numberSectionStyles: 4,
        axisFormat: '%Y-%m-%d',
        topAxis: false,
    },
};

// Track initialization state
let isInitialized = false;

// Initialize Mermaid
function initializeMermaid(config = {}) {
    if (typeof window.mermaid === 'undefined') {
        console.warn('Mermaid library is not loaded');
        return false;
    }
    
    // 이미 초기화되었는지 확인
    if (isInitialized) {
        // 설정이 변경된 경우에만 재초기화
        if (Object.keys(config).length > 0) {
            const mergedConfig = { ...mermaidConfig, ...config };
            window.mermaid.initialize(mergedConfig);
        }
        return true;
    }
    
    // 초기화 실행
    const mergedConfig = { ...mermaidConfig, ...config };
    window.mermaid.initialize(mergedConfig);
    isInitialized = true;
    
    return true;
}

/**
 * Render Mermaid chart
 * @param {string} mermaidCode - Mermaid diagram code
 * @param {HTMLElement} containerElement - Container element to render into
 * @param {object} options - Rendering options
 * @returns {Promise} Promise that resolves when rendering is complete
 */
async function renderMermaidChart(mermaidCode, containerElement, options = {}) {
    if (!containerElement || !mermaidCode) {
        console.warn('Mermaid: container or code is missing');
        return;
    }
    
    // Initialize mermaid if not already initialized
    if (typeof window.mermaid === 'undefined') {
        console.warn('Mermaid library is not loaded');
        containerElement.innerHTML = `
            <div class="mermaid-error" style="padding: 1rem; color: #dc2626; background: #fee2e2; border-radius: 0.5rem;">
                <i class="fas fa-exclamation-triangle"></i>
                Mermaid 라이브러리를 로드할 수 없습니다.
            </div>
        `;
        return;
    }
    
    // Initialize if needed
    if (!isInitialized) {
        initializeMermaid(options.config);
    }
    
    try {
        // Generate unique ID for this chart
        const chartId = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        
        // Create wrapper element
        const wrapper = document.createElement('div');
        wrapper.className = 'mermaid-chart-wrapper';
        wrapper.id = chartId;
        wrapper.setAttribute('data-mermaid-code', mermaidCode);
        
        // Clear container and add wrapper
        containerElement.innerHTML = '';
        containerElement.appendChild(wrapper);
        
        // Render mermaid chart
        const result = await window.mermaid.render(chartId, mermaidCode);
        
        // Insert rendered SVG
        wrapper.innerHTML = result.svg;
        
        // Add click handler for SVG download if needed
        if (options.enableDownload) {
            addDownloadButton(wrapper, chartId);
        }
        
        return result;
    } catch (error) {
        console.error('Mermaid rendering error:', error);
        containerElement.innerHTML = `
            <div class="mermaid-error" style="padding: 1rem; color: #dc2626; background: #fee2e2; border-radius: 0.5rem;">
                <i class="fas fa-exclamation-triangle"></i>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.875rem;">다이어그램 렌더링 중 오류가 발생했습니다.</p>
                <p style="margin: 0.25rem 0 0 0; font-size: 0.75rem; color: #991b1b;">${escapeHtml(error.message)}</p>
            </div>
        `;
    }
}

/**
 * Render all mermaid diagrams in a container
 * @param {HTMLElement} container - Container element
 * @param {object} options - Rendering options
 */
async function renderAllMermaidCharts(container, options = {}) {
    if (!container) return;
    
    // Find all mermaid code blocks
    const mermaidElements = container.querySelectorAll('.language-mermaid, .mermaid, code.language-mermaid, pre code.language-mermaid');
    
    if (mermaidElements.length === 0) return;
    
    // Initialize mermaid
    if (typeof window.mermaid === 'undefined') {
        console.warn('Mermaid library is not loaded');
        return;
    }
    
    if (!isInitialized) {
        initializeMermaid(options.config);
    }
    
    // Process each mermaid element
    const promises = Array.from(mermaidElements).map(async (element) => {
        const mermaidCode = element.textContent || element.innerText;
        if (!mermaidCode.trim()) return;
        
        // Create container for rendered chart
        const chartContainer = document.createElement('div');
        chartContainer.className = 'mermaid-chart-container';
        
        // Replace code element with container
        if (element.parentElement.tagName === 'PRE') {
            element.parentElement.replaceWith(chartContainer);
        } else {
            element.replaceWith(chartContainer);
        }
        
        // Render chart
        await renderMermaidChart(mermaidCode, chartContainer, options);
    });
    
    await Promise.all(promises);
}

/**
 * Add download button to mermaid chart
 * @param {HTMLElement} wrapper - Chart wrapper element
 * @param {string} chartId - Chart ID
 */
function addDownloadButton(wrapper, chartId) {
    const svg = wrapper.querySelector('svg');
    if (!svg) return;
    
    const button = document.createElement('button');
    button.className = 'mermaid-download-btn';
    button.innerHTML = '<i class="fas fa-download"></i>';
    button.title = '다이어그램 다운로드';
    button.style.cssText = `
        position: absolute;
        top: 0.5rem;
        right: 0.5rem;
        padding: 0.5rem;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 0.375rem;
        cursor: pointer;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        transition: background-color 0.2s;
    `;
    
    button.addEventListener('mouseenter', () => {
        button.style.background = '#f3f4f6';
    });
    
    button.addEventListener('mouseleave', () => {
        button.style.background = 'white';
    });
    
    button.addEventListener('click', () => {
        downloadMermaidChart(svg, chartId);
    });
    
    wrapper.style.position = 'relative';
    wrapper.appendChild(button);
}

/**
 * Download mermaid chart as SVG
 * @param {SVGElement} svg - SVG element
 * @param {string} filename - Filename for download
 */
function downloadMermaidChart(svg, filename = 'mermaid-chart') {
    if (!svg) return;
    
    // Clone SVG
    const clonedSvg = svg.cloneNode(true);
    
    // Get SVG as string
    const svgData = new XMLSerializer().serializeToString(clonedSvg);
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const svgUrl = URL.createObjectURL(svgBlob);
    
    // Create download link
    const downloadLink = document.createElement('a');
    downloadLink.href = svgUrl;
    downloadLink.download = `${filename}.svg`;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
    
    // Cleanup
    URL.revokeObjectURL(svgUrl);
}

/**
 * Validate mermaid syntax
 * @param {string} mermaidCode - Mermaid diagram code
 * @returns {Promise<boolean>} True if valid
 */
async function validateMermaidSyntax(mermaidCode) {
    if (typeof window.mermaid === 'undefined') {
        return false;
    }
    
    try {
        // Try to parse the mermaid code
        await window.mermaid.parse(mermaidCode);
        return true;
    } catch (error) {
        console.error('Mermaid syntax error:', error);
        return false;
    }
}

/**
 * Get mermaid chart type
 * @param {string} mermaidCode - Mermaid diagram code
 * @returns {string} Chart type (flowchart, sequence, gantt, etc.)
 */
function getMermaidChartType(mermaidCode) {
    if (!mermaidCode) return null;
    
    const firstLine = mermaidCode.trim().split('\n')[0].toLowerCase();
    
    if (firstLine.includes('graph') || firstLine.includes('flowchart')) {
        return 'flowchart';
    } else if (firstLine.includes('sequence')) {
        return 'sequence';
    } else if (firstLine.includes('gantt')) {
        return 'gantt';
    } else if (firstLine.includes('class')) {
        return 'class';
    } else if (firstLine.includes('state')) {
        return 'state';
    } else if (firstLine.includes('er')) {
        return 'er';
    } else if (firstLine.includes('journey')) {
        return 'journey';
    } else if (firstLine.includes('gitgraph')) {
        return 'gitgraph';
    } else if (firstLine.includes('pie')) {
        return 'pie';
    } else if (firstLine.includes('requirement')) {
        return 'requirement';
    }
    
    return 'unknown';
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize mermaid on page load
if (typeof window !== 'undefined') {
    // Wait for mermaid to be available and DOM to be ready
    function initMermaidOnReady() {
        if (typeof window.mermaid !== 'undefined') {
            // 초기화는 필요할 때만 수행 (lazy initialization)
            // 실제로 차트를 렌더링할 때 initializeMermaid()가 호출됨
            
            // Auto-render all mermaid charts in existing content
            setTimeout(() => {
                const markdownContainers = document.querySelectorAll('.markdown-content, .message-content-assistant');
                markdownContainers.forEach(container => {
                    renderAllMermaidCharts(container);
                });
            }, 100);
        }
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMermaidOnReady);
    } else {
        initMermaidOnReady();
    }
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.MermaidChart = {
        initialize: initializeMermaid,
        render: renderMermaidChart,
        renderAll: renderAllMermaidCharts,
        validate: validateMermaidSyntax,
        getType: getMermaidChartType,
        download: downloadMermaidChart,
        config: mermaidConfig,
        isInitialized: () => isInitialized,
    };
}
