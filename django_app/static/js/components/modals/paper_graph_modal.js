// Paper Graph Modal Component JavaScript Logic
(function() {
    'use strict';

// Graph nodes data - matching React component (업데이트된 색상 팔레트)
    const graphNodes = [];

// Graph edges data - matching React component
    const graphEdges = [];

let sigmaInstance = null;
const modalId = 'paperGraphModal';
const containerId = 'paperGraphContainer';

// Initialize graph
function initializeGraph(containerElement) {
    if (!containerElement) return null;
    
    return {
        nodes: graphNodes,
        edges: graphEdges,
        container: containerElement,
    };
}

// Render graph using Sigma (if available)
    function renderGraph(containerElement, data = null) {
        if (!containerElement) {
            console.error('[PaperGraph] Container element not found');
            return null;
        }
    
    // Cleanup existing instance
    cleanupGraph();
        
        // Use provided data or fallback to default
        let nodesToUse = graphNodes;
        let edgesToUse = graphEdges;
        
        if (data && data.nodes && Array.isArray(data.nodes) && data.nodes.length > 0) {
            // Convert server data format to graph format
            nodesToUse = data.nodes.map(node => ({
                id: String(node.id || node.paper_id || `node-${Math.random()}`),
                label: node.label || node.paper_label || node.id || 'Unknown',
                size: node.size || node.node_size || 20,
                x: node.x !== undefined ? node.x : (node.x_position || 0),
                y: node.y !== undefined ? node.y : (node.y_position || 0),
                color: node.color || node.node_color || '#457B9D' // 관련 논문 기본 색상 (파랑)
            }));
        }
        
        if (data && data.edges && Array.isArray(data.edges) && data.edges.length > 0) {
            // Convert server data format to graph format
            edgesToUse = data.edges.map(edge => {
                if (Array.isArray(edge)) {
                    return [String(edge[0]), String(edge[1])]; // Ensure strings
                } else if (edge.source && edge.target) {
                    return [String(edge.source), String(edge.target)];
                } else if (edge.source_paper_id && edge.target_paper_id) {
                    return [String(edge.source_paper_id), String(edge.target_paper_id)];
                }
                return null;
            }).filter(edge => edge !== null);
        }
    
    // Check if graphology and sigma are available
    let Graph, Sigma;
    
    // Try different ways the libraries might be exposed
    if (typeof window.Graph !== 'undefined') {
        Graph = window.Graph;
    } else if (typeof window.graphology !== 'undefined' && window.graphology.Graph) {
        Graph = window.graphology.Graph;
    } else {
            console.error('[PaperGraph] Graphology library not found. Available window properties:', 
                Object.keys(window).filter(k => k.toLowerCase().includes('graph')));
        containerElement.innerHTML = `
                <div class="graph-loading" style="padding: 20px; text-align: center;">
                <i class="fas fa-exclamation-triangle"></i>
                    <p>Graphology 라이브러리를 로드할 수 없습니다.</p>
                    <p style="font-size: 12px; color: #666;">window.Graph: ${typeof window.Graph}, window.graphology: ${typeof window.graphology}</p>
            </div>
        `;
        return null;
    }
    
    if (typeof window.Sigma !== 'undefined') {
        Sigma = window.Sigma;
        } else if (typeof window.sigma !== 'undefined') {
            Sigma = window.sigma;
    } else {
            console.error('[PaperGraph] Sigma library not found. Available window properties:', 
                Object.keys(window).filter(k => k.toLowerCase().includes('sigma')));
        containerElement.innerHTML = `
                <div class="graph-loading" style="padding: 20px; text-align: center;">
                <i class="fas fa-exclamation-triangle"></i>
                    <p>Sigma 라이브러리를 로드할 수 없습니다.</p>
                    <p style="font-size: 12px; color: #666;">window.Sigma: ${typeof window.Sigma}, window.sigma: ${typeof window.sigma}</p>
            </div>
        `;
        return null;
    }
    
    if (Graph && Sigma) {
            try {
        const graph = new Graph();
        
        // Add nodes
                nodesToUse.forEach((node) => {
                    // x, y coordinates: 서버에서 이미 스케일링된 값 사용 (200, -200 등)
                    // 절대값이 10보다 크면 이미 스케일링된 것으로 간주
                    const xCoord = (typeof node.x === 'number' && Math.abs(node.x) > 10) ? node.x : (node.x || 0) * 100;
                    const yCoord = (typeof node.y === 'number' && Math.abs(node.y) > 10) ? node.y : (node.y || 0) * 100;
                    
                    // 라벨 텍스트를 최대 길이로 제한 (겹침 방지)
                    let labelText = String(node.label || node.id);
                    const maxLabelLength = 50; // 최대 라벨 길이
                    if (labelText.length > maxLabelLength) {
                        labelText = labelText.substring(0, maxLabelLength) + '...';
                    }
                    
                    // 노드 스타일 개선
                    const nodeColor = node.color || '#457B9D'; // 관련 논문 기본 색상 (파랑)
                    graph.addNode(String(node.id), {
                        label: labelText,
                        size: node.size || 20,
                        x: xCoord,
                        y: yCoord,
                        color: nodeColor,
                        // 초기 라벨 표시 여부 (호버/클릭 시 변경)
                        labelVisible: false,
                        // 노드 스타일 개선을 위한 추가 속성
                        borderColor: nodeColor,
                        borderSize: 1,
            });
        });
        
                // Add edges with improved styling
                edgesToUse.forEach(([source, target]) => {
                    if (source && target) {
                        try {
                            graph.addEdge(String(source), String(target), {
                                size: 1.5,  // 약간 더 두껍게
                                color: '#B0BEC5',  // 더 부드러운 회색
                                type: 'line',  // 선형 엣지
                            });
                        } catch (e) {
                            // Edge may already exist, ignore
                        }
                    }
                });
                
                // Apply layout if nodes don't have positions or need repositioning
                // 서버에서 이미 위치가 있으면 레이아웃 적용 안 함
                const hasPositions = nodesToUse.some(n => Math.abs(n.x) > 10 || Math.abs(n.y) > 10);
                if (!hasPositions) {
                    // Force-directed layout을 사용하여 노드 간 거리 확보
                    if (typeof window.forceAtlas2 !== 'undefined') {
            window.forceAtlas2.assign(graph, {
                            iterations: 100,
                settings: {
                    gravity: 0.5,
                                strongGravityMode: false,
                                barnesHutOptimize: true,
                                barnesHutTheta: 0.5,
                                edgeWeightInfluence: 0.2,
                                scalingRatio: 1.0,
                                outboundAttractionDistribution: false,
                                linLogMode: false,
                                adjustSizes: false,
                            }
                        });
                    } else if (typeof window.GraphologyLayout !== 'undefined' && window.GraphologyLayout.circular) {
                        window.GraphologyLayout.circular.assign(graph);
                    } else if (typeof window.graphologyLayout !== 'undefined' && window.graphologyLayout.circular) {
                        window.graphologyLayout.circular.assign(graph);
                    }
                }
                
                // Create Sigma instance with improved styling
                try {
                    const sigmaConfig = {
            renderEdgeLabels: false,
                        defaultNodeColor: '#457B9D', // 관련 논문 기본 색상 (파랑)
                        defaultEdgeColor: '#B0BEC5',
                        // 레이블 스타일 개선
                        labelFont: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif',
                        labelSize: 10,
                        labelWeight: '500',  // Medium weight
                        labelColor: { color: '#1A1A1A' },  // 더 진한 검정 (가독성 향상)
                        // 라벨 겹침 방지 설정
                        labelDensity: 0.1,
                        labelRenderedSizeThreshold: 0,
                        zIndex: true,
                        // 렌더링 품질 개선
                        allowInvalidEdges: false,
                        renderLabels: true,
                        // 배경색 설정 (그래프 영역) - CSS 그라데이션이 보이도록 투명하게 설정
                        // backgroundColor는 Sigma가 canvas를 렌더링할 때 사용되므로, 
                        // CSS 배경이 보이려면 투명하거나 CSS와 일치해야 함
                        backgroundColor: 'transparent',
                        // 마우스 인터랙션 개선
                        mouseWheelEnabled: true,
                        // 렌더링 최적화
                        minCameraRatio: 0.1,
                        maxCameraRatio: 10,
                    };
                    
                    if (typeof Sigma === 'function') {
                        sigmaInstance = new Sigma(graph, containerElement, sigmaConfig);
                    } else if (typeof Sigma === 'object' && Sigma.default) {
                        sigmaInstance = new Sigma.default(graph, containerElement, sigmaConfig);
                    } else {
                        throw new Error('Sigma is not a constructor function');
                    }
                    
                    // 호버/클릭 시 라벨 강조 및 관련 노드/엣지 하이라이트
                    let hoveredNode = null;
                    let clickedNodes = new Set();
                    const originalNodeColors = new Map();
                    const originalEdgeColors = new Map();
                    const originalEdgeSizes = new Map();
                    
                    // Hex 색상을 RGBA로 변환하는 헬퍼 함수
                    function hexToRgba(hex, alpha = 1) {
                        const r = parseInt(hex.slice(1, 3), 16);
                        const g = parseInt(hex.slice(3, 5), 16);
                        const b = parseInt(hex.slice(5, 7), 16);
                        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
                    }
                    
                    // 초기 노드/엣지 색상 및 크기 저장
                    graph.forEachNode((node) => {
                        originalNodeColors.set(node, graph.getNodeAttribute(node, 'color'));
                        graph.setNodeAttribute(node, 'labelSize', 0);
                    });
                    graph.forEachEdge((edge) => {
                        originalEdgeColors.set(edge, graph.getEdgeAttribute(edge, 'color'));
                        originalEdgeSizes.set(edge, graph.getEdgeAttribute(edge, 'size') || 1);
                    });
                    
                    // 노드와 연결된 모든 노드 및 엣지 찾기
                    function getConnectedNodesAndEdges(nodeId) {
                        const connectedNodes = new Set([nodeId]);
                        const connectedEdges = [];
                        
                        // 현재 노드와 연결된 모든 엣지 찾기
                        graph.forEachEdge((edge, attributes, source, target) => {
                            if (source === nodeId || target === nodeId) {
                                connectedEdges.push(edge);
                                connectedNodes.add(source);
                                connectedNodes.add(target);
                            }
                        });
                        
                        return { connectedNodes, connectedEdges };
                    }
                    
                    sigmaInstance.on('enterNode', ({ node }) => {
                        hoveredNode = node;
                        
                        // 연결된 노드와 엣지 찾기
                        const { connectedNodes, connectedEdges } = getConnectedNodesAndEdges(node);
                        
                        // 모든 노드 처리
                        graph.forEachNode((nodeId) => {
                            if (connectedNodes.has(nodeId)) {
                                // 연결된 노드: 하이라이트 (원래 색상 유지, 밝게)
                                graph.setNodeAttribute(nodeId, 'highlighted', true);
                                const originalColor = originalNodeColors.get(nodeId) || '#457B9D';
                                graph.setNodeAttribute(nodeId, 'color', originalColor);
                                // 호버된 노드 자체는 더 밝게
                                if (nodeId === node) {
                                    graph.setNodeAttribute(nodeId, 'labelSize', 12);
                                } else {
                                    graph.setNodeAttribute(nodeId, 'labelSize', 10);
                                }
                            } else {
                                // 연결되지 않은 노드: 반투명하게
                                graph.setNodeAttribute(nodeId, 'highlighted', false);
                                const originalColor = originalNodeColors.get(nodeId) || '#457B9D';
                                // 색상을 반투명하게 (alpha 0.3)
                                const fadedColor = hexToRgba(originalColor, 0.3);
                                graph.setNodeAttribute(nodeId, 'color', fadedColor);
                                graph.setNodeAttribute(nodeId, 'labelSize', 0);
                            }
                        });
                        
                        // 모든 엣지 처리
                        graph.forEachEdge((edge) => {
                            if (connectedEdges.includes(edge)) {
                                // 연결된 엣지: 하이라이트 (더 진하고 두껍게)
                                graph.setEdgeAttribute(edge, 'color', '#666666');
                                graph.setEdgeAttribute(edge, 'size', 2);
                            } else {
                                // 연결되지 않은 엣지: 반투명하게
                                graph.setEdgeAttribute(edge, 'color', 'rgba(204, 204, 204, 0.2)');
                                graph.setEdgeAttribute(edge, 'size', 0.5);
                            }
                        });
                        
                        sigmaInstance.refresh();
                    });
                    
                    sigmaInstance.on('leaveNode', ({ node }) => {
                        graph.setNodeAttribute(node, 'highlighted', false);
                        
                        // 모든 노드 원래 색상으로 복원
                        graph.forEachNode((nodeId) => {
                            const originalColor = originalNodeColors.get(nodeId) || '#5B8E7E';
                            graph.setNodeAttribute(nodeId, 'color', originalColor);
                            
                            // 클릭되지 않은 노드는 라벨 숨김
                            if (!clickedNodes.has(nodeId)) {
                                graph.setNodeAttribute(nodeId, 'labelSize', 0);
                            } else {
                                // 클릭된 노드는 라벨 유지
                                graph.setNodeAttribute(nodeId, 'labelSize', 10);
                            }
                        });
                        
                        // 모든 엣지 원래 색상 및 크기로 복원
                        graph.forEachEdge((edge) => {
                            const originalColor = originalEdgeColors.get(edge) || '#B0BEC5';
                            const originalSize = originalEdgeSizes.get(edge) || 1.5;
                            graph.setEdgeAttribute(edge, 'color', originalColor);
                            graph.setEdgeAttribute(edge, 'size', originalSize);
                        });
                        
                        sigmaInstance.refresh();
                    });
                    
                    // 클릭 시 PubMed URL로 새 탭 열기
                    sigmaInstance.on('clickNode', ({ node }) => {
                        // 노드 ID (paper_id = PMID) 가져오기
                        const nodeId = node;
                        const pmid = String(nodeId);
                        
                        // PubMed URL 생성
                        const pubmedUrl = `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
                        
                        // 새 탭에서 PubMed 페이지 열기
                        window.open(pubmedUrl, '_blank', 'noopener,noreferrer');
                        
                        // 클릭된 노드는 라벨 표시 (선택적)
                        if (!clickedNodes.has(node)) {
                            clickedNodes.add(node);
                            graph.setNodeAttribute(node, 'labelSize', 10);
                            sigmaInstance.refresh();
                        }
                    });
                    
                    // 배경 클릭 시 모든 라벨 숨김
                    sigmaInstance.on('clickStage', () => {
                        clickedNodes.forEach(node => {
                            graph.setNodeAttribute(node, 'labelSize', 0);
                        });
                        clickedNodes.clear();
                        sigmaInstance.refresh();
        });
        
        return sigmaInstance;
                } catch (sigmaError) {
                    console.error('[PaperGraph] Error creating Sigma instance:', sigmaError);
                    throw sigmaError;
                }
                
            } catch (error) {
                console.error('[PaperGraph] Error creating graph:', error);
                containerElement.innerHTML = `
                    <div class="graph-loading" style="padding: 20px; text-align: center;">
                        <i class="fas fa-exclamation-triangle"></i>
                        <p>그래프 생성 중 오류가 발생했습니다.</p>
                        <p style="font-size: 12px; color: #666;">${error.message}</p>
                    </div>
                `;
                return null;
            }
    } else {
            console.error('[PaperGraph] Graph or Sigma is not available');
        containerElement.innerHTML = `
                <div class="graph-loading" style="padding: 20px; text-align: center;">
                <i class="fas fa-exclamation-triangle"></i>
                <p>그래프 라이브러리를 로드할 수 없습니다.</p>
            </div>
        `;
    }
    
    return null;
}

// Cleanup graph
function cleanupGraph() {
    if (sigmaInstance) {
        if (typeof sigmaInstance.kill === 'function') {
            sigmaInstance.kill();
        }
        sigmaInstance = null;
    }
}

    // Wait for libraries to be available
    function waitForLibraries(maxAttempts = 50, interval = 100) {
        return new Promise((resolve, reject) => {
            let attempts = 0;
            const checkLibraries = () => {
                attempts++;
                const hasGraph = typeof window.Graph !== 'undefined' || 
                               (typeof window.graphology !== 'undefined' && window.graphology.Graph);
                const hasSigma = typeof window.Sigma !== 'undefined' || 
                               typeof window.sigma !== 'undefined';
                
                if (hasGraph && hasSigma) {
                    resolve();
                } else if (attempts >= maxAttempts) {
                    console.error('[PaperGraphModal] Libraries not loaded after', maxAttempts, 'attempts');
                    reject(new Error('Libraries not available'));
                } else {
                    setTimeout(checkLibraries, interval);
                }
            };
            checkLibraries();
        });
    }

    // Open modal and render graph
    async function openPaperGraphModal(data = null) {
        // Wait for libraries to be available
        try {
            await waitForLibraries();
        } catch (error) {
            console.error('[PaperGraphModal] Failed to load libraries:', error);
            // Continue anyway - renderGraph will show error message
    }
    
    // Open modal
    if (window.Modal) {
        window.Modal.open(modalId);
        } else {
            console.error('[PaperGraphModal] window.Modal is not available');
    }
    
    // Render graph after modal is opened
    setTimeout(() => {
        const container = document.getElementById(containerId);
        if (container) {
                renderGraph(container, data);
            } else {
                console.error('[PaperGraphModal] Container element not found:', containerId);
        }
    }, 100);
}

// Close modal
function closePaperGraphModal() {
    cleanupGraph();
    if (window.Modal) {
        window.Modal.close(modalId);
    }
}

// Export graph
function exportGraph() {
    // Export graph as image or data
    if (sigmaInstance) {
        // Use Sigma's export functionality if available
        // Implementation depends on Sigma version
    }
}

// Initialize modal handlers
function initPaperGraphModal() {
    const modal = document.getElementById(modalId);
    if (!modal) return;
    
    // Footer button handlers
    const footer = modal.querySelector('.modal-footer');
    if (footer) {
        footer.addEventListener('click', (e) => {
            const action = e.target.closest('[data-action]')?.getAttribute('data-action');
            if (action === 'close') {
                closePaperGraphModal();
            } else if (action === 'export') {
                exportGraph();
            }
        });
    }
    
    // Listen for modal open event
    document.addEventListener('modal:open', (e) => {
        if (e.detail.modalId === modalId) {
            const container = document.getElementById(containerId);
            if (container) {
                renderGraph(container);
            }
        }
    });
    
    // Listen for modal close event
    document.addEventListener('modal:close', (e) => {
        if (e.detail.modalId === modalId) {
            cleanupGraph();
        }
    });
}

// Export for use in other modules
    // This ensures window.PaperGraphModal is available immediately when script loads
    window.PaperGraphModal = {
        open: openPaperGraphModal,
        close: closePaperGraphModal,
        renderGraph,
        cleanupGraph,
        exportGraph,
    };

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPaperGraphModal);
    } else {
        initPaperGraphModal();
    }
})();
