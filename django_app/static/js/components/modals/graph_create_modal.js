// Graph Create Modal for Note Editor
(function() {
    'use strict';

    // State
    let selectedChartType = 'line';
    let additionalSeriesCount = 0;
    let chartInstance = null;

    // DOM Elements
    let graphCreateModal = null;
    let graphCreateModalCloseBtn = null;
    let graphCreateModalCancelBtn = null;
    let graphCreateModalInsertBtn = null;
    let chartTypeSelector = null;
    let graphTitleInput = null;
    let xAxisInput = null;
    let yAxisInput = null;
    let seriesNameInput = null;
    let btnAddSeries = null;
    let additionalSeriesContainer = null;
    let btnUpdateChart = null;
    let graphPreviewContainer = null;

    // Callback for when chart is inserted
    let onInsertCallback = null;

    // Initialize
    function initGraphCreateModal() {
        console.log('[GraphCreateModal] Initializing...');
        
        graphCreateModal = document.getElementById('graphCreateModal');
        graphCreateModalCloseBtn = document.getElementById('graphCreateModalCloseBtn');
        graphCreateModalCancelBtn = document.getElementById('graphCreateModalCancelBtn');
        graphCreateModalInsertBtn = document.getElementById('graphCreateModalInsertBtn');
        chartTypeSelector = document.getElementById('chartTypeSelector');
        graphTitleInput = document.getElementById('graphTitleInput');
        xAxisInput = document.getElementById('xAxisInput');
        yAxisInput = document.getElementById('yAxisInput');
        seriesNameInput = document.getElementById('seriesNameInput');
        btnAddSeries = document.getElementById('btnAddSeries');
        additionalSeriesContainer = document.getElementById('additionalSeriesContainer');
        btnUpdateChart = document.getElementById('btnUpdateChart');
        graphPreviewContainer = document.getElementById('graphPreviewContainer');

        // Attach event listeners
        if (graphCreateModalCloseBtn) {
            graphCreateModalCloseBtn.addEventListener('click', closeModal);
        }
        if (graphCreateModalCancelBtn) {
            graphCreateModalCancelBtn.addEventListener('click', closeModal);
        }
        if (graphCreateModalInsertBtn) {
            graphCreateModalInsertBtn.addEventListener('click', handleInsertChart);
        }
        if (btnAddSeries) {
            btnAddSeries.addEventListener('click', addSeriesInput);
        }
        if (btnUpdateChart) {
            btnUpdateChart.addEventListener('click', updateChartPreview);
        }

        // Chart type selection
        if (chartTypeSelector) {
            chartTypeSelector.querySelectorAll('.chart-type-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    chartTypeSelector.querySelectorAll('.chart-type-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    selectedChartType = btn.getAttribute('data-type');
                    updateChartPreview();
                });
            });
        }

        // Close on overlay click
        if (graphCreateModal) {
            graphCreateModal.addEventListener('click', (e) => {
                if (e.target === graphCreateModal) {
                    closeModal();
                }
            });
        }

        // Auto-update on input change (with debounce)
        let updateTimeout = null;
        const debouncedUpdate = () => {
            clearTimeout(updateTimeout);
            updateTimeout = setTimeout(() => {
                updateChartPreview();
            }, 500);
        };

        [graphTitleInput, xAxisInput, yAxisInput, seriesNameInput].forEach(input => {
            if (input) {
                input.addEventListener('input', debouncedUpdate);
            }
        });

        console.log('[GraphCreateModal] Initialized successfully');
    }

    // Open modal
    function openModal(callback) {
        console.log('[GraphCreateModal] Opening modal...');
        
        // Re-query if not found
        if (!graphCreateModal) {
            graphCreateModal = document.getElementById('graphCreateModal');
        }

        if (!graphCreateModal) {
            console.error('[GraphCreateModal] Modal element not found!');
            return;
        }

        onInsertCallback = callback || null;

        // Reset state
        selectedChartType = 'line';
        additionalSeriesCount = 0;
        if (additionalSeriesContainer) {
            additionalSeriesContainer.innerHTML = '';
        }

        // Reset chart type buttons
        if (chartTypeSelector) {
            chartTypeSelector.querySelectorAll('.chart-type-btn').forEach(btn => {
                btn.classList.remove('active');
                if (btn.getAttribute('data-type') === 'line') {
                    btn.classList.add('active');
                }
            });
        }

        // Show modal
        graphCreateModal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Initial chart render
        setTimeout(() => {
            updateChartPreview();
        }, 100);
    }

    // Close modal
    function closeModal() {
        if (graphCreateModal) {
            graphCreateModal.classList.remove('active');
        }
        document.body.style.overflow = '';
        
        // Destroy chart instance
        if (chartInstance) {
            chartInstance.destroy();
            chartInstance = null;
        }
    }

    // Parse comma-separated values
    function parseCSV(value, isNumeric = false) {
        if (!value) return [];
        return value.split(',').map(v => {
            const trimmed = v.trim();
            if (isNumeric) {
                const num = parseFloat(trimmed);
                return isNaN(num) ? 0 : num;
            }
            return trimmed;
        }).filter(v => v !== '' && v !== 0 || isNumeric);
    }

    // Get all series data
    function getAllSeriesData() {
        const series = [];
        
        // Main series
        const mainYData = parseCSV(yAxisInput?.value, true);
        const mainName = seriesNameInput?.value?.trim() || '시리즈 1';
        
        if (mainYData.length > 0) {
            series.push({
                name: mainName,
                data: mainYData
            });
        }

        // Additional series
        if (additionalSeriesContainer) {
            additionalSeriesContainer.querySelectorAll('.additional-series-item').forEach((item, index) => {
                const nameInput = item.querySelector('.series-name-input');
                const dataInput = item.querySelector('.series-data-input');
                
                if (nameInput && dataInput) {
                    const name = nameInput.value?.trim() || `시리즈 ${index + 2}`;
                    const data = parseCSV(dataInput.value, true);
                    
                    if (data.length > 0) {
                        series.push({ name, data });
                    }
                }
            });
        }

        return series;
    }

    // Update chart preview
    function updateChartPreview() {
        if (!graphPreviewContainer) {
            console.warn('[GraphCreateModal] Preview container not found');
            return;
        }

        if (!window.Highcharts) {
            console.error('[GraphCreateModal] Highcharts not available');
            graphPreviewContainer.innerHTML = '<p style="color: #ef4444; text-align: center; padding: 2rem;">Highcharts를 로드할 수 없습니다.</p>';
            return;
        }

        const title = graphTitleInput?.value?.trim() || '차트';
        const categories = parseCSV(xAxisInput?.value);
        const series = getAllSeriesData();

        // Destroy previous chart
        if (chartInstance) {
            chartInstance.destroy();
            chartInstance = null;
        }

        // Chart options
        const chartOptions = {
            chart: {
                type: selectedChartType,
                backgroundColor: 'transparent'
            },
            title: {
                text: title,
                style: {
                    fontSize: '16px',
                    fontWeight: '600'
                }
            },
            xAxis: {
                categories: categories.length > 0 ? categories : undefined,
                title: {
                    text: null
                }
            },
            yAxis: {
                title: {
                    text: null
                }
            },
            legend: {
                enabled: series.length > 1
            },
            credits: {
                enabled: false
            },
            plotOptions: {
                pie: {
                    allowPointSelect: true,
                    cursor: 'pointer',
                    dataLabels: {
                        enabled: true,
                        format: '<b>{point.name}</b>: {point.percentage:.1f} %'
                    }
                },
                series: {
                    animation: {
                        duration: 500
                    }
                }
            },
            colors: ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
            series: selectedChartType === 'pie' ? [{
                name: series[0]?.name || '데이터',
                colorByPoint: true,
                data: categories.map((cat, index) => ({
                    name: cat,
                    y: series[0]?.data[index] || 0
                }))
            }] : series
        };

        // Create chart
        chartInstance = window.Highcharts.chart(graphPreviewContainer, chartOptions);
        console.log('[GraphCreateModal] Chart updated:', selectedChartType);
    }

    // Add series input
    function addSeriesInput() {
        if (!additionalSeriesContainer) return;

        additionalSeriesCount++;
        const seriesIndex = additionalSeriesCount;

        const seriesHtml = `
            <div class="additional-series-item" data-series-index="${seriesIndex}">
                <div class="additional-series-header">
                    <span class="additional-series-title">시리즈 ${seriesIndex + 1}</span>
                    <button class="btn-remove-series" type="button" title="시리즈 삭제">
                        <i class="fa-solid fa-times"></i>
                    </button>
                </div>
                <div class="additional-series-inputs">
                    <input 
                        type="text" 
                        class="config-input series-name-input" 
                        placeholder="시리즈 이름"
                        value="시리즈 ${seriesIndex + 1}"
                    />
                    <input 
                        type="text" 
                        class="config-input series-data-input" 
                        placeholder="Y축 값 (쉼표로 구분)"
                    />
                </div>
            </div>
        `;

        additionalSeriesContainer.insertAdjacentHTML('beforeend', seriesHtml);

        // Attach remove listener
        const newItem = additionalSeriesContainer.lastElementChild;
        const removeBtn = newItem.querySelector('.btn-remove-series');
        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                newItem.remove();
                updateChartPreview();
            });
        }

        // Attach input listeners for auto-update
        newItem.querySelectorAll('input').forEach(input => {
            input.addEventListener('input', () => {
                clearTimeout(window._graphUpdateTimeout);
                window._graphUpdateTimeout = setTimeout(updateChartPreview, 500);
            });
        });
    }

    // Handle insert chart
    function handleInsertChart() {
        if (!chartInstance) {
            if (window.notyf) {
                window.notyf.error('차트를 먼저 생성해주세요.');
            }
            return;
        }

        let svg = '';
        if (typeof chartInstance.getSVG === 'function') {
            // Get chart as SVG using Highcharts API (requires exporting module)
            svg = chartInstance.getSVG({
                chart: {
                    width: 600,
                    height: 400
                }
            });
        } else if (graphPreviewContainer) {
            // Fallback: extract current SVG markup directly from the preview container
            const svgElement = graphPreviewContainer.querySelector('svg');
            if (svgElement) {
                svg = svgElement.outerHTML;
            }
        }

        if (!svg) {
            console.error('[GraphCreateModal] Unable to export chart SVG');
            if (window.notyf) {
                window.notyf.error('차트 이미지를 생성할 수 없습니다.');
            }
            return;
        }

        // Convert SVG to base64 data URL
        const svgBase64 = btoa(unescape(encodeURIComponent(svg)));
        const dataUrl = `data:image/svg+xml;base64,${svgBase64}`;

        // Create chart data object
        const chartData = {
            type: selectedChartType,
            title: graphTitleInput?.value?.trim() || '차트',
            categories: parseCSV(xAxisInput?.value),
            series: getAllSeriesData(),
            imageDataUrl: dataUrl,
            svgContent: svg
        };

        // Call callback
        if (onInsertCallback && typeof onInsertCallback === 'function') {
            onInsertCallback(chartData);
        }

        // Show success message
        if (window.notyf) {
            window.notyf.success('차트가 노트에 삽입되었습니다.');
        }

        closeModal();
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initGraphCreateModal);
    } else {
        initGraphCreateModal();
    }

    // Export to window
    window.GraphCreateModal = {
        open: openModal,
        close: closeModal,
        updatePreview: updateChartPreview
    };
})();
