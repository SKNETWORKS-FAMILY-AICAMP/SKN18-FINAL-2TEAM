// Paper Graph Modal Component JavaScript Logic

// Graph nodes data - matching React component
let graphNodes = [
    { id: 'cobo-2011', label: 'Cobo, 2011', size: 35, x: 0, y: 0, color: '#9E7B9E' },
    { id: 'eck-2010', label: 'Eck, 2010', size: 28, x: -2, y: -1, color: '#7B9E9E' },
    { id: 'eck-2009', label: 'Eck, 2009', size: 30, x: -1.5, y: 1.5, color: '#7B9E9E' },
    { id: 'callon-1991', label: 'Callon, 1991', size: 25, x: -2.5, y: 1, color: '#9E9E9E' },
    { id: 'waltman-2010', label: 'Waltman, 2010', size: 22, x: -3, y: -0.5, color: '#9E9E9E' },
    { id: 'noyons-1999', label: 'Noyons, 1999', size: 22, x: -3.5, y: -1.5, color: '#9E9E9E' },
    { id: 'small-1999', label: 'Small, 1999', size: 20, x: -3, y: 0.5, color: '#9E9E9E' },
    { id: 'coulter-1998', label: 'Coulter, 1998', size: 18, x: -3, y: 1.5, color: '#9E9E9E' },
    { id: 'callon-1983', label: 'Callon, 1983', size: 20, x: -2.5, y: 2.5, color: '#9E9E9E' },
    { id: 'small-1973', label: 'Small, 1973', size: 26, x: -4.5, y: -1, color: '#9E9E9E' },
    { id: 'kessler-1963', label: 'Kessler, 1963', size: 24, x: -5, y: 0, color: '#9E9E9E' },
    { id: 'bornner-2005', label: 'Bornner, 2005', size: 22, x: -2, y: 2, color: '#9E9E9E' },
    { id: 'boyack-2004', label: 'Boyack, 2004', size: 20, x: -1.5, y: 3, color: '#9E9E9E' },
    { id: 'rusydiana-2021', label: 'Rusydiana, 2021', size: 18, x: -4.5, y: 2.5, color: '#5B7E8E' },
    
    { id: 'aria-2017', label: 'Aria, 2017', size: 32, x: 1.5, y: 0, color: '#5B8E7E' },
    { id: 'bales-2019', label: 'Bales, 2019', size: 24, x: 1, y: -1.5, color: '#5B8E7E' },
    { id: 'cobo-2012', label: 'Cobo, 2012', size: 20, x: 0.5, y: 1, color: '#5B8E7E' },
    { id: 'eck-2014', label: 'Eck, 2014', size: 20, x: -1, y: -2, color: '#7B9E9E' },
    
    { id: 'smyrnova-trybulska-2017', label: 'Smyrnova-Trybulska, 2017', size: 28, x: 1.5, y: -3, color: '#7B9E9E' },
    { id: 'lou-2020', label: 'Lou, 2020', size: 22, x: 2.5, y: -2, color: '#5B8E7E' },
    { id: 'ju-2018', label: 'Ju, 2018', size: 20, x: 3, y: -1, color: '#5B8E7E' },
    
    { id: 'moral-munoz-2020', label: 'Moral Munoz, 2020', size: 24, x: 2, y: -0.5, color: '#5B8E7E' },
    { id: 'moral-munoz-2019', label: 'Moral Munoz, 2019', size: 22, x: 2.5, y: 0.5, color: '#5B8E7E' },
    { id: 'moral-munoz-2014', label: 'Moral Munoz, 2014', size: 20, x: 2, y: 1.5, color: '#5B8E7E' },
    
    { id: 'baier-fuentes-2018', label: 'Baier Fuentes, 2018', size: 22, x: 3, y: -2.5, color: '#5B8E7E' },
    { id: 'baier-fuentes-2021', label: 'Baier Fuentes, 2021', size: 20, x: 3.5, y: -0.5, color: '#5B8E7E' },
    { id: 'guerrero-2019', label: 'Guerrero, 2019', size: 20, x: 3.5, y: -2, color: '#5B8E7E' },
    
    { id: 'cobo-2018', label: 'Cobo, 2018', size: 20, x: 2.5, y: 1.5, color: '#5B8E7E' },
    { id: 'cobo-2015', label: 'Cobo, 2015', size: 18, x: 1.5, y: 2, color: '#5B8E7E' },
    { id: 'martinez-2015', label: 'Martinez, 2015', size: 18, x: 1, y: 2.5, color: '#5B8E7E' },
    { id: 'cobo-2017', label: 'Cobo, 2017', size: 18, x: 2, y: 2.5, color: '#5B8E7E' },
    
    { id: 'gutierrez-salcedo-2017', label: 'Gutierrez Salcedo, 2017', size: 20, x: 1.5, y: 1.5, color: '#5B8E7E' },
    { id: 'herrera-viedma-2016', label: 'Herrera Viedma, 2016', size: 18, x: 1, y: 3, color: '#5B8E7E' },
    { id: 'murgado-armenteros-2014', label: 'Murgado Armenteros, 2014', size: 20, x: 0.5, y: 3, color: '#5B8E7E' },
    { id: 'martinez-2014', label: 'Martinez, 2014', size: 20, x: 0, y: 3.5, color: '#5B8E7E' },
    { id: 'jiang-2019', label: 'Jiang, 2019', size: 22, x: 1, y: 4, color: '#5B8E7E' },
    
    { id: 'martinez-estevez-2022', label: 'Martinez Estevez, 2022', size: 18, x: 3, y: 2.5, color: '#5B8E7E' },
    { id: 'salovic-2022', label: 'Salovic, 2022', size: 18, x: 3.5, y: 1, color: '#5B8E7E' },
];

// Graph edges data - matching React component
let graphEdges = [
    // Central cluster connections
    ['cobo-2011', 'eck-2010'],
    ['cobo-2011', 'eck-2009'],
    ['cobo-2011', 'aria-2017'],
    ['cobo-2011', 'cobo-2012'],
    ['cobo-2011', 'gutierrez-salcedo-2017'],
    
    ['eck-2010', 'eck-2009'],
    ['eck-2010', 'waltman-2010'],
    ['eck-2010', 'noyons-1999'],
    ['eck-2010', 'eck-2014'],
    
    ['eck-2009', 'callon-1991'],
    ['eck-2009', 'bornner-2005'],
    
    ['callon-1991', 'callon-1983'],
    ['callon-1991', 'coulter-1998'],
    ['callon-1991', 'small-1999'],
    
    ['waltman-2010', 'noyons-1999'],
    ['noyons-1999', 'small-1973'],
    ['small-1973', 'kessler-1963'],
    
    ['boyack-2004', 'bornner-2005'],
    ['rusydiana-2021', 'small-1973'],
    
    // Right cluster connections
    ['aria-2017', 'bales-2019'],
    ['aria-2017', 'moral-munoz-2020'],
    ['aria-2017', 'moral-munoz-2019'],
    ['aria-2017', 'cobo-2012'],
    ['aria-2017', 'gutierrez-salcedo-2017'],
    
    ['bales-2019', 'smyrnova-trybulska-2017'],
    ['bales-2019', 'lou-2020'],
    
    ['smyrnova-trybulska-2017', 'lou-2020'],
    ['smyrnova-trybulska-2017', 'baier-fuentes-2018'],
    
    ['lou-2020', 'ju-2018'],
    ['lou-2020', 'baier-fuentes-2018'],
    
    ['ju-2018', 'baier-fuentes-2018'],
    ['ju-2018', 'moral-munoz-2020'],
    
    ['moral-munoz-2020', 'moral-munoz-2019'],
    ['moral-munoz-2020', 'baier-fuentes-2021'],
    ['moral-munoz-2020', 'guerrero-2019'],
    
    ['moral-munoz-2019', 'moral-munoz-2014'],
    ['moral-munoz-2019', 'gutierrez-salcedo-2017'],
    
    ['baier-fuentes-2018', 'baier-fuentes-2021'],
    ['baier-fuentes-2021', 'guerrero-2019'],
    
    ['cobo-2012', 'cobo-2018'],
    ['cobo-2018', 'cobo-2015'],
    ['cobo-2018', 'cobo-2017'],
    ['cobo-2018', 'martinez-estevez-2022'],
    
    ['cobo-2015', 'martinez-2015'],
    ['cobo-2017', 'martinez-estevez-2022'],
    
    ['gutierrez-salcedo-2017', 'moral-munoz-2014'],
    ['gutierrez-salcedo-2017', 'herrera-viedma-2016'],
    ['gutierrez-salcedo-2017', 'murgado-armenteros-2014'],
    
    ['herrera-viedma-2016', 'martinez-2014'],
    ['murgado-armenteros-2014', 'martinez-2014'],
    ['martinez-2014', 'jiang-2019'],
    
    ['salovic-2022', 'martinez-estevez-2022'],
];

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
function renderGraph(containerElement) {
    if (!containerElement) return null;
    
    // Cleanup existing instance
    cleanupGraph();
    
    // Check if graphology and sigma are available
    // React uses: import Graph from 'graphology'; import Sigma from 'sigma';
    // In Django, these should be available via vite build or CDN
    let Graph, Sigma;
    
    // Try different ways the libraries might be exposed
    if (typeof window.Graph !== 'undefined') {
        Graph = window.Graph;
    } else if (typeof window.GraphologyGraph !== 'undefined') {
        Graph = window.GraphologyGraph;
    } else if (typeof window.graphology !== 'undefined' && window.graphology.Graph) {
        Graph = window.graphology.Graph;
    } else {
        console.warn('Graphology library not found');
        containerElement.innerHTML = `
            <div class="graph-loading">
                <i class="fas fa-exclamation-triangle"></i>
                <p>그래프 라이브러리를 로드할 수 없습니다.</p>
            </div>
        `;
        return null;
    }
    
    if (typeof window.Sigma !== 'undefined') {
        Sigma = window.Sigma;
    } else if (typeof window.sigma !== 'undefined' && window.sigma.Sigma) {
        Sigma = window.sigma.Sigma;
    } else {
        console.warn('Sigma library not found');
        containerElement.innerHTML = `
            <div class="graph-loading">
                <i class="fas fa-exclamation-triangle"></i>
                <p>그래프 라이브러리를 로드할 수 없습니다.</p>
            </div>
        `;
        return null;
    }
    
    if (Graph && Sigma) {
        
        const graph = new Graph();
        
        // Add nodes
        graphNodes.forEach(node => {
            graph.addNode(node.id, {
                label: node.label,
                size: node.size,
                x: node.x * 100,
                y: node.y * 100,
                color: node.color,
            });
        });
        
        // Add edges
        graphEdges.forEach(([source, target]) => {
            graph.addEdge(source, target, {
                size: 1,
                color: '#CCCCCC',
            });
        });
        
        // Apply circular layout (matching React component)
        // React uses: import { circular } from 'graphology-layout';
        // circular.assign(graph);
        if (typeof window.GraphologyLayout !== 'undefined' && window.GraphologyLayout.circular) {
            window.GraphologyLayout.circular.assign(graph);
        } else if (typeof window.forceAtlas2 !== 'undefined') {
            // Fallback to forceAtlas2 if circular layout not available
            window.forceAtlas2.assign(graph, {
                iterations: 50,
                settings: {
                    gravity: 0.5,
                },
            });
        }
        
        // Create Sigma instance
        sigmaInstance = new Sigma(graph, containerElement, {
            renderEdgeLabels: false,
            defaultNodeColor: '#5B8E7E',
            defaultEdgeColor: '#CCCCCC',
            labelFont: 'Arial',
            labelSize: 12,
            labelWeight: 'normal',
            labelColor: { color: '#000000' },
        });
        
        return sigmaInstance;
    } else {
        // Fallback: show message if libraries not available
        containerElement.innerHTML = `
            <div class="graph-loading">
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

// Open modal and render graph
function openPaperGraphModal(data = null) {
    // Update graph data if provided
    if (data && data.nodes) {
        graphNodes = data.nodes;
    }
    if (data && data.edges) {
        graphEdges = data.edges;
    }
    
    // Open modal
    if (window.Modal) {
        window.Modal.open(modalId);
    }
    
    // Render graph after modal is opened
    setTimeout(() => {
        const container = document.getElementById(containerId);
        if (container) {
            renderGraph(container);
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
        console.log('Exporting graph...');
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPaperGraphModal);
} else {
    initPaperGraphModal();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.PaperGraphModal = {
        open: openPaperGraphModal,
        close: closePaperGraphModal,
        renderGraph,
        cleanupGraph,
        exportGraph,
    };
}
