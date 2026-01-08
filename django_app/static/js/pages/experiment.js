// Experiment Page JavaScript Logic

// State variables
let sequenceQuery = "";
let toolSearchQuery = "";
let selectedTools = [];
let selectedToolGuide = null;
let searchResults = [];
let currentPage = 1;
const itemsPerPage = 5;
let toolOptions = {}; // Store tool options: { toolId: { optionName: value } }
let selectedProtein = null; // Selected protein from search results or custom input

// DOM elements
const toolSidebar = document.getElementById('toolSidebar');
const toolSearchInput = document.getElementById('toolSearchInput');
const toolList = document.getElementById('toolList');
const proteinSequenceInput = document.getElementById('proteinSequenceInput');
const searchBtn = document.getElementById('searchBtn');
const clearBtn = document.getElementById('clearBtn');
const toolsGrid = document.getElementById('toolsGrid');
const pipelineActions = document.getElementById('pipelineActions');
const runSimulationBtn = document.getElementById('runSimulationBtn');
const clearPipelineBtn = document.getElementById('clearPipelineBtn');
const experimentTableBody = document.getElementById('experimentTableBody');
const searchResultsContainer = document.getElementById('searchResultsContainer');
const searchResultsList = document.getElementById('searchResultsList');
const searchResultsCount = document.getElementById('searchResultsCount');
const searchResultsPagination = document.getElementById('searchResultsPagination');
const prevPageBtn = document.getElementById('prevPageBtn');
const nextPageBtn = document.getElementById('nextPageBtn');
const currentPageSpan = document.getElementById('currentPage');
const totalPagesSpan = document.getElementById('totalPages');
const closeResultsBtn = document.getElementById('closeResultsBtn');
const pipelineSection = document.getElementById('pipelineSection');
const pipelineToolCount = document.getElementById('pipelineToolCount');
const pipelineItems = document.getElementById('pipelineItems');
const pipelineProteinBtn = document.getElementById('pipelineProteinBtn');
const pipelineProteinItem = document.getElementById('pipelineProteinItem');
const pipelineOptionsSection = document.getElementById('pipelineOptionsSection');
const pipelineOptionsGrid = document.getElementById('pipelineOptionsGrid');
const pipelineClearBtn = document.getElementById('pipelineClearBtn');
const pipelineRunBtn = document.getElementById('pipelineRunBtn');
const experimentResultSidebar = document.getElementById('experimentResultSidebar');
const experimentResultCloseBtn = document.getElementById('experimentResultCloseBtn');
const experimentResultPipelineName = document.getElementById('experimentResultPipelineName');
const experimentResultToolsList = document.getElementById('experimentResultToolsList');
const experimentResultStatus = document.getElementById('experimentResultStatus');
const experimentResultProgressFill = document.getElementById('experimentResultProgressFill');
const experimentResultProgressText = document.getElementById('experimentResultProgressText');
const experimentResultFilesList = document.getElementById('experimentResultFilesList');
const PIPELINE_ORDER = ['RFdiffusion', 'ProteinMPNN', 'AlphaFold3'];
// Available tools (will be loaded from API or context)
// Default tools structure matching React component
const defaultTools = [
    {
        id: 1,
        name: "RFdiffusion",
        category: "단백질 구조 생성",
        description: "단백질 구조 생성",
        icon: "fas fa-microscope", // Microscope icon
        optionFields: [
            { name: "temperature", label: "Temperature", type: "number", default: 1.0, min: 0.1, max: 2.0, step: 0.1 },
            { name: "numSteps", label: "Number of Steps", type: "number", default: 50, min: 10, max: 200 },
            { name: "guidanceScale", label: "Guidance Scale", type: "number", default: 7.5, min: 1, max: 20, step: 0.5 },
        ],
        guide: {
            overview: "RFdiffusion은 AI 기반의 단백질 구조 생성 도구입니다.",
            usage: [
                "1. 목표 구조의 조건을 설정합니다.",
                "2. Diffusion 모델을 실행합니다.",
                "3. 생성된 구조를 확인하고 검증합니다.",
                "4. 최적 구조를 선택합니다.",
            ],
            tips: "생성 조건을 명확히 설정할수록 더 정확한 결과를 얻을 수 있습니다.",
        },
    },
    {
        id: 2,
        name: "AlphaFold2",
        category: "단백질 구조 예측",
        description: "단백질 구조 예측",
        icon: "fas fa-flask", // FlaskConical icon
        optionFields: [
            { name: "mode", label: "Prediction Mode", type: "select", options: ["monomer", "multimer"], default: "monomer" },
            { name: "maxRecycles", label: "Max Recycles", type: "number", default: 3, min: 1, max: 10 },
            { name: "useTemplates", label: "Use Templates", type: "checkbox", default: true },
        ],
        guide: {
            overview: "AlphaFold2는 딥러닝 기반의 단백질 3D 구조 예측 도구입니다.",
            usage: [
                "1. 단백질 서열(FASTA 형식)을 입력합니다.",
                "2. 예측 모드를 선택합니다 (monomer/multimer).",
                "3. 구조 예측을 실행하고 결과를 확인합니다.",
                "4. 예측된 구조의 신뢰도(pLDDT)를 검토합니다.",
            ],
            tips: "서열이 긴 경우 처리 시간이 오래 걸릴 수 있습니다. 신뢰도 점수가 높은 영역을 중점적으로 분석하세요.",
        },
    },
    {
        id: 3,
        name: "DiffDock",
        category: "분자 도킹 시뮬레이션",
        description: "분자 도킹 시뮬레이션",
        icon: "fas fa-vial", // TestTube icon
        optionFields: [
            { name: "numPoses", label: "Number of Poses", type: "number", default: 10, min: 1, max: 50 },
            { name: "exhaustiveness", label: "Exhaustiveness", type: "number", default: 8, min: 1, max: 32 },
            { name: "energyCutoff", label: "Energy Cutoff (kcal/mol)", type: "number", default: 3.0, min: 0, max: 10, step: 0.5 },
        ],
        guide: {
            overview: "DiffDock은 AI 기반의 분자 도킹 시뮬레이션 도구입니다.",
            usage: [
                "1. 단백질 구조를 불러옵니다.",
                "2. 리간드 분자를 입력합니다.",
                "3. 도킹 시뮬레이션을 실행합니다.",
                "4. 결합 모드와 에너지를 분석합니다.",
            ],
            tips: "여러 포즈를 비교하여 최적 결합 모드를 찾으세요.",
        },
    },
    {
        id: 4,
        name: "AutoDock Vina",
        category: "자동 분자 도킹",
        description: "자동 분자 도킹",
        icon: "fas fa-flask", // Beaker icon
        optionFields: [
            { name: "centerX", label: "Center X", type: "number", default: 0, step: 0.1 },
            { name: "centerY", label: "Center Y", type: "number", default: 0, step: 0.1 },
            { name: "centerZ", label: "Center Z", type: "number", default: 0, step: 0.1 },
            { name: "sizeX", label: "Size X (Å)", type: "number", default: 20, min: 1, max: 50 },
            { name: "sizeY", label: "Size Y (Å)", type: "number", default: 20, min: 1, max: 50 },
            { name: "sizeZ", label: "Size Z (Å)", type: "number", default: 20, min: 1, max: 50 },
        ],
        guide: {
            overview: "AutoDock Vina는 단백질-리간드 상호작용을 예측하는 도구입니다.",
            usage: [
                "1. 수용체 단백질 구조를 준비합니다.",
                "2. 리간드 분자를 입력합니다.",
                "3. 도킹 영역을 설정합니다.",
                "4. 도킹을 실행하고 결합 에너지를 분석합니다.",
            ],
            tips: "결합 에너지가 낮을수록 안정적입니다.",
        },
    },
];

let availableTools = [];

// Store experiments list for table row click handlers
let experiments = [];

// Initialize experiment page
function initExperiment() {
    // Initialize availableTools from template data if available
    if (window.EXPERIMENT_TOOLS && Array.isArray(window.EXPERIMENT_TOOLS) && window.EXPERIMENT_TOOLS.length > 0) {
        availableTools = window.EXPERIMENT_TOOLS;
        renderToolList();
        renderToolsGrid();
    } else {
        // Load tools from API if not available in template
        loadAvailableTools();
    }

    // Load experiments
    loadExperiments();
     // ✅ 5초마다 실험 목록 상태 재조회 (폴링)
    if (!window.__experimentPollTimer) {
        window.__experimentPollTimer = setInterval(loadExperiments, 30000);
    }

    // Event listeners
    if (toolSearchInput) {
        toolSearchInput.addEventListener('input', handleToolSearch);
    }

    if (proteinSequenceInput) {
        proteinSequenceInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleSearch();
            }
        });
    }

    if (searchBtn) {
        searchBtn.addEventListener('click', handleSearch);
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', handleClearSearch);
    }

    // Search results pagination handlers
    if (prevPageBtn) {
        prevPageBtn.addEventListener('click', () => handlePageChange(currentPage - 1));
    }
    if (nextPageBtn) {
        nextPageBtn.addEventListener('click', () => handlePageChange(currentPage + 1));
    }
    if (closeResultsBtn) {
        closeResultsBtn.addEventListener('click', handleClearSearch);
    }

    if (runSimulationBtn) {
        runSimulationBtn.addEventListener('click', handleRunSimulation);
    }

    if (clearPipelineBtn) {
        clearPipelineBtn.addEventListener('click', handleClearPipeline);
    }

    // Tool item click handlers
    attachToolItemHandlers();

    // Tool card click handlers
    attachToolCardHandlers();

    // Experiment table row handlers
    attachExperimentTableHandlers();

    // Pipeline section handlers
    attachPipelineHandlers();

    // Listen for protein selection event
    document.addEventListener('proteinSelected', (e) => {
        selectedProtein = e.detail.protein;
        sequenceQuery = e.detail.sequence;
        updatePipelineSection();
    });

    // Experiment result sidebar close button
    experimentResultCloseBtn?.addEventListener('click', () => {
        closeExperimentResultSidebar();
    });

    // Close sidebar on overlay click (if overlay exists)
    experimentResultSidebar?.addEventListener('click', (e) => {
        if (e.target === experimentResultSidebar) {
            closeExperimentResultSidebar();
        }
    });
}

// Load available tools from API
async function loadAvailableTools() {
    try {
        const response = await fetch('/api/tools/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            const apiTools = data.results || data;
            // Merge API tools with default tools structure (guide, optionFields, icon)
            availableTools = apiTools.map(apiTool => {
                const defaultTool = defaultTools.find(dt => dt.id === apiTool.id || dt.name === apiTool.name);
                if (defaultTool) {
                    return {
                        ...apiTool,
                        icon: apiTool.icon || defaultTool.icon,
                        optionFields: apiTool.optionFields || defaultTool.optionFields || [],
                        guide: apiTool.guide || defaultTool.guide,
                    };
                }
                return {
                    ...apiTool,
                    icon: apiTool.icon || "fas fa-cog",
                    optionFields: apiTool.optionFields || [],
                    guide: apiTool.guide || {
                        overview: `${apiTool.name} 도구입니다.`,
                        usage: [],
                        tips: "",
                    },
                };
            });
            renderToolList();
            renderToolsGrid();
        }
    } catch (error) {
        console.error('Error loading tools:', error);
        // Use tools from context if API fails, or fallback to default tools
        availableTools = window.EXPERIMENT_TOOLS || defaultTools;
        renderToolList();
        renderToolsGrid();
    }
}

// Load experiments from API
async function loadExperiments() {
    try {
        const response = await fetch('/api/experiments/', {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            experiments = data.results || data;
            renderExperimentTable(experiments);
        }
    } catch (error) {
        console.error('Error loading experiments:', error);
    }
}

// Handle tool search
function handleToolSearch(e) {
    toolSearchQuery = e.target.value.toLowerCase().trim();
    renderToolList();
}

// Handle protein sequence search
async function handleSearch() {
    sequenceQuery = proteinSequenceInput?.value.trim() || "";
    
    if (!sequenceQuery) {
        if (window.notyf) {
            window.notyf.error('검색어를 입력해주세요.');
        } else {
            alert('검색어를 입력해주세요.');
        }
        return;
    }

    try {
        // Call API to search proteins
        const response = await fetch(
            `/api/experiments/uniprot/search/?keyword=${encodeURIComponent(sequenceQuery)}`,
            {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            const apiResults = data.results || [];

            // (원하면 여기서 실제 응답 확인)
            // console.log('[UniProt] raw', data);
            // console.log('[UniProt] first', apiResults[0]);

            // ✅ 2) UniProt 응답 → 화면에서 쓰는 구조로 매핑
            searchResults = apiResults.map((r, idx) => ({
                id: idx + 1,
                proteinId: r.accession,         // -> "P01308"
                proteinName: r.entry_name,      // -> "INS_HUMAN"
                description: r.protein_name,    // -> "Insulin"
                recommendedName: r.protein_name,
                gene: r.gene,                   // -> "INS"
                organism: r.organism,           // -> "Homo sapiens (Human)"
                length: r.length,               // -> 110 amino acids
                evidenceLevel: r.protein_existence,       // -> Evidence at protein level
                annotationScore: r.annotation_score,      // -> 5
                tags: r.keywords || [],         // -> #Hormone, ...
                sequence: r.sequence || "",
            }));

            currentPage = 1;
            renderSearchResults();
        } else {
            // 필요하면 기존 mock fallback 유지
            searchResults = generateMockSearchResults();
            currentPage = 1;
            renderSearchResults();
        }
    } catch (error) {
        console.error('Error searching proteins:', error);
        searchResults = generateMockSearchResults();
        currentPage = 1;
        renderSearchResults();
    }
}

// Generate mock search results for testing
// Data structure: proteinId, proteinName, description, gene, organism, tags, sequence, etc.
// function generateMockSearchResults() {
//     return [
//         {
//             id: 1,
//             proteinId: "P01308",
//             proteinName: "INS_HUMAN",
//             description: "Insulin",
//             recommendedName: "Insulin",
//             cleavedChains: ["Insulin B chain", "Insulin A chain"],
//             gene: "INS",
//             organism: "Homo sapiens (Human)",
//             taxonomicId: "9606 (NCBI)",
//             taxonomicLineage: "cellular organisms > Eukaryota (eukaryotes) > Opisthokonta > Metazoa (metazoans) > Eumetazoa > Bilateria > Deuterostomia > Chordata (chordates) > Craniata > Vertebrata (vertebrates) > Gnathostomata (jawed vertebrates) > Teleostomi > Euteleostomi (bony vertebrates) > Sarcopterygii > Dipnotetrapodomorpha > Tetrapoda > Amniota > Mammalia > Theria > Eutheria > Boreoeutheria > Euarchontoglires > Primates > Haplorrhini > Simiiformes > Catarrhini > Hominoidea (apes) > Hominidae (great apes) > Homininae > Homo > Homo sapiens (Human)",
//             length: 110,
//             mass: 12171,
//             lastUpdated: "2024-03-15 v3",
//             md5Checksum: "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6",
//             evidenceLevel: "Evidence at protein level",
//             annotationScore: 5,
//             tags: ["Hormone", "Carbohydrate metabolism", "Glucose metabolism", "Diabetes mellitus", "Disease variant"],
//             sequence: "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN",
//         },
//         {
//             id: 2,
//             proteinId: "P68871",
//             proteinName: "HBB_HUMAN",
//             description: "Hemoglobin subunit beta",
//             recommendedName: "Hemoglobin subunit beta",
//             cleavedChains: null,
//             gene: "HBB",
//             organism: "Homo sapiens (Human)",
//             taxonomicId: "9606 (NCBI)",
//             taxonomicLineage: "cellular organisms > Eukaryota (eukaryotes) > Opisthokonta > Metazoa (metazoans) > Eumetazoa > Bilateria > Deuterostomia > Chordata (chordates) > Craniata > Vertebrata (vertebrates) > Gnathostomata (jawed vertebrates) > Teleostomi > Euteleostomi (bony vertebrates) > Sarcopterygii > Dipnotetrapodomorpha > Tetrapoda > Amniota > Mammalia > Theria > Eutheria > Boreoeutheria > Euarchontoglires > Primates > Haplorrhini > Simiiformes > Catarrhini > Hominoidea (apes) > Hominidae (great apes) > Homininae > Homo > Homo sapiens (Human)",
//             length: 147,
//             mass: 15998,
//             lastUpdated: "2024-02-20 v2",
//             md5Checksum: "Q9W8E7R6T5Y4U3I2O1P0A9S8D7F6G5H4",
//             evidenceLevel: "Evidence at protein level",
//             annotationScore: 5,
//             tags: ["Oxygen transport", "Heme", "Iron", "Disease variant", "Sickle cell anemia"],
//             sequence: "MVHLTPEEKSAVTALWGKVNVDEVGGEALGRLLVVYPWTQRFFESFGDLSTPDAVMGNPKVKAHGKKVLGAFSDGLAHLDNLKGTFATLSELHCDKLHVDPENFRLLGNVLVCVLAHHFGKEFTPPVQAAYQKVVAGVANALAHKYH",
//         },
//         {
//             id: 3,
//             proteinId: "P04637",
//             proteinName: "P53_HUMAN",
//             description: "Cellular tumor antigen p53",
//             recommendedName: "Cellular tumor antigen p53",
//             cleavedChains: null,
//             gene: "TP53",
//             organism: "Homo sapiens (Human)",
//             taxonomicId: "9606 (NCBI)",
//             taxonomicLineage: "cellular organisms > Eukaryota (eukaryotes) > Opisthokonta > Metazoa (metazoans) > Eumetazoa > Bilateria > Deuterostomia > Chordata (chordates) > Craniata > Vertebrata (vertebrates) > Gnathostomata (jawed vertebrates) > Teleostomi > Euteleostomi (bony vertebrates) > Sarcopterygii > Dipnotetrapodomorpha > Tetrapoda > Amniota > Mammalia > Theria > Eutheria > Boreoeutheria > Euarchontoglires > Primates > Haplorrhini > Simiiformes > Catarrhini > Hominoidea (apes) > Hominidae (great apes) > Homininae > Homo > Homo sapiens (Human)",
//             length: 393,
//             mass: 43653,
//             lastUpdated: "2024-01-10 v4",
//             md5Checksum: "Z1X2C3V4B5N6M7A8S9D0F1G2H3J4K5L6",
//             evidenceLevel: "Evidence at protein level",
//             annotationScore: 5,
//             tags: ["Tumor suppressor", "DNA binding", "Apoptosis", "Cell cycle", "Cancer"],
//             sequence: "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYQGSYGFRLGFLHSGTAKSVTCTYSPALNKMFCQLAKTCPVQLWVDSTPPPGTRVRAMAIYKQSQHMTEVVRRCPHHERCSDSDGLAPPQHLIRVEGNLRVEYLDDRNTFRHSVVVPYEPPEVGSDCTTIHYNYMCNSSCMGGMNRRPILTIITLEDSSGNLLGRNSFEVRVCACPGRDRRTEEENLRKKGEPHHELPPGSTKRALPNNTSSSPQPKKKPLDGEYFTLQIRGRERFEMFRELNEALELKDAQAGKEPGGSRAHSSHLKSKKGQSTSRHKKLMFKTEGPDSD",
//         },
//         {
//             id: 4,
//             proteinId: "P02768",
//             proteinName: "ALBU_HUMAN",
//             description: "Serum albumin",
//             recommendedName: "Serum albumin",
//             cleavedChains: null,
//             gene: "ALB",
//             organism: "Homo sapiens (Human)",
//             taxonomicId: "9606 (NCBI)",
//             taxonomicLineage: "cellular organisms > Eukaryota (eukaryotes) > Opisthokonta > Metazoa (metazoans) > Eumetazoa > Bilateria > Deuterostomia > Chordata (chordates) > Craniata > Vertebrata (vertebrates) > Gnathostomata (jawed vertebrates) > Teleostomi > Euteleostomi (bony vertebrates) > Sarcopterygii > Dipnotetrapodomorpha > Tetrapoda > Amniota > Mammalia > Theria > Eutheria > Boreoeutheria > Euarchontoglires > Primates > Haplorrhini > Simiiformes > Catarrhini > Hominoidea (apes) > Hominidae (great apes) > Homininae > Homo > Homo sapiens (Human)",
//             length: 609,
//             mass: 69367,
//             lastUpdated: "2024-05-08 v2",
//             md5Checksum: "B1C2D3E4F5G6H7I8J9K0L1M2N3O4P5Q6",
//             evidenceLevel: "Evidence at protein level",
//             annotationScore: 5,
//             tags: ["Transport", "Blood protein", "Plasma", "Pharmaceutical"],
//             sequence: "MKWVTFISLLFLFSSAYSRGVFRRDAHKSEVAHRFKDLGEENFKALVLIAFAQYLQQCPFEDHVKLVNEVTEFAKTCVADESAENCDKSLHTLFGDKLCTVATLRETYGEMADCCAKQEPERNECFLQHKDDNPNLPRLVRPEVDVMCTAFHDNEETFLKKYLYEIARRHPYFYAPELLFFAKRYKAAFTECCQAADKAACLLPKLDELRDEGKASSAKQRLKCASLQKFGERAFKAWAVARLSQRFPKAEFAEVSKLVTDLTKVHTECCHGDLLECADDRADLAKYICENQDSISSKLKECCEKPLLEKSHCIAEVENDEMPADLPSLAADFVESKDVCKNYAEAKDVFLGMFLYEYARRHPDYSVVLLLRLAKTYETTLEKCCAAADPHECYAKVFDEFKPLVEEPQNLIKQNCELFEQLGEYKFQNALLVRYTKKVPQVSTPTLVEVSRNLGKVGSKCCKHPEAKRMPCAEDYLSVVLNQLCVLHEKTPVSDRVTKCCTESLVNRRPCFSALEVDETYVPKEFNAETFTFHADICTLSEKERQIKKQTALVELVKHKPKATKEQLKAVMDDFAAFVEKCCKADDKETCFAEEGKKLVAASQAALGL",
//         },
//         {
//             id: 5,
//             proteinId: "P62988",
//             proteinName: "UBIQ_HUMAN",
//             description: "Ubiquitin",
//             recommendedName: "Ubiquitin",
//             cleavedChains: null,
//             gene: "UBB",
//             organism: "Homo sapiens (Human)",
//             taxonomicId: "9606 (NCBI)",
//             taxonomicLineage: "cellular organisms > Eukaryota (eukaryotes) > Opisthokonta > Metazoa (metazoans) > Eumetazoa > Bilateria > Deuterostomia > Chordata (chordates) > Craniata > Vertebrata (vertebrates) > Gnathostomata (jawed vertebrates) > Teleostomi > Euteleostomi (bony vertebrates) > Sarcopterygii > Dipnotetrapodomorpha > Tetrapoda > Amniota > Mammalia > Theria > Eutheria > Boreoeutheria > Euarchontoglires > Primates > Haplorrhini > Simiiformes > Catarrhini > Hominoidea (apes) > Hominidae (great apes) > Homininae > Homo > Homo sapiens (Human)",
//             length: 76,
//             mass: 8565,
//             lastUpdated: "2024-04-12 v1",
//             md5Checksum: "C1D2E3F4G5H6I7J8K9L0M1N2O3P4Q5R6",
//             evidenceLevel: "Evidence at protein level",
//             annotationScore: 5,
//             tags: ["Protein degradation", "Ubiquitination", "Proteasome"],
//             sequence: "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG",
//         },
//         {
//             id: 6,
//             proteinId: "P01112",
//             proteinName: "RASH_HUMAN",
//             description: "GTPase HRas",
//             recommendedName: "GTPase HRas",
//             cleavedChains: null,
//             gene: "HRAS",
//             organism: "Homo sapiens (Human)",
//             taxonomicId: "9606 (NCBI)",
//             taxonomicLineage: "cellular organisms > Eukaryota (eukaryotes) > Opisthokonta > Metazoa (metazoans) > Eumetazoa > Bilateria > Deuterostomia > Chordata (chordates) > Craniata > Vertebrata (vertebrates) > Gnathostomata (jawed vertebrates) > Teleostomi > Euteleostomi (bony vertebrates) > Sarcopterygii > Dipnotetrapodomorpha > Tetrapoda > Amniota > Mammalia > Theria > Eutheria > Boreoeutheria > Euarchontoglires > Primates > Haplorrhini > Simiiformes > Catarrhini > Hominoidea (apes) > Hominidae (great apes) > Homininae > Homo > Homo sapiens (Human)",
//             length: 189,
//             mass: 21295,
//             lastUpdated: "2024-03-22 v2",
//             md5Checksum: "D1E2F3G4H5I6J7K8L9M0N1O2P3Q4R5S6",
//             evidenceLevel: "Evidence at protein level",
//             annotationScore: 5,
//             tags: ["GTPase", "Oncogene", "Signal transduction", "Cancer"],
//             sequence: "MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHHYREQIKRVKDSEDVPMVLVGNKCDLPSRTVDTKQAQDLARSYGIPFIETSAKTRQGVDDAFYTLVREIRKHKEKMSKDGKKKKKKSKTKCVIM",
//         },
//         {
//             id: 7,
//             proteinId: "P12931",
//             proteinName: "SRC_HUMAN",
//             description: "Proto-oncogene tyrosine-protein kinase Src",
//             recommendedName: "Proto-oncogene tyrosine-protein kinase Src",
//             cleavedChains: null,
//             gene: "SRC",
//             organism: "Homo sapiens (Human)",
//             taxonomicId: "9606 (NCBI)",
//             taxonomicLineage: "cellular organisms > Eukaryota (eukaryotes) > Opisthokonta > Metazoa (metazoans) > Eumetazoa > Bilateria > Deuterostomia > Chordata (chordates) > Craniata > Vertebrata (vertebrates) > Gnathostomata (jawed vertebrates) > Teleostomi > Euteleostomi (bony vertebrates) > Sarcopterygii > Dipnotetrapodomorpha > Tetrapoda > Amniota > Mammalia > Theria > Eutheria > Boreoeutheria > Euarchontoglires > Primates > Haplorrhini > Simiiformes > Catarrhini > Hominoidea (apes) > Hominidae (great apes) > Homininae > Homo > Homo sapiens (Human)",
//             length: 536,
//             mass: 59912,
//             lastUpdated: "2024-02-15 v3",
//             md5Checksum: "E1F2G3H4I5J6K7L8M9N0O1P2Q3R4S5T6",
//             evidenceLevel: "Evidence at protein level",
//             annotationScore: 5,
//             tags: ["Kinase", "Tyrosine-protein kinase", "Proto-oncogene", "Signal transduction"],
//             sequence: "MGSNKSKPKDASQRRRSLEPAENVHGAGGGAFPASQTPSKPASADGHRGPSAAFAPAAAEPKLFGGFNSSDTVTSPQRAGPLAGGVTTFVALYDYESRTETDLSFKKGERLQIVNNTEGDWWLAHSLSTGQTGYIPSNYVAPSDSIQAEEWYFGKITRRESERLLLNAENPRGTFLVRESETTKGAYCLSVSDFDNAKGLNVKHYKIRKLDSGGFYITSRTQFNSLQQLVAYYSKHADGLCHRLTTVCPTSKPQTQGLAKDAWEIPRESLRLEVKLGQGCFGEVWMGTWNGTTRVAIKTLKPGTMSPEAFLQEAQVMKKLRHEKLVQLYAVVSEEPIYIVTEYMSKGSLLDFLKGETGKYLRLPQLVDMAAQIASGMAYVERMNYVHRDLRAANILVGENLVCKVADFGLARLIEDNEYTARQGAKFPIKWTAPEAALYGRFTIKSDVWSFGILLTELTTKGRVPYPGMVNREVLDQVERGYRMPCPPECPESLHDLMCQCWRKEPEERPTFEYLQAFLEDYFTSTEPQYQPGENL",
//         },
//     ];
// }

// Handle clear search
function handleClearSearch() {
    if (proteinSequenceInput) {
        proteinSequenceInput.value = "";
    }
    sequenceQuery = "";
    searchResults = [];
    currentPage = 1;
    if (searchResultsContainer) {
        searchResultsContainer.style.display = 'none';
    }
}

// Render search results
function renderSearchResults() {
    if (!searchResultsList || !searchResultsContainer) return;

    if (searchResults.length === 0) {
        searchResultsContainer.style.display = 'block';
        searchResultsList.innerHTML = `
            <div class="search-results-empty">
                <p class="empty-message">검색 결과가 없습니다</p>
            </div>
        `;
        if (searchResultsCount) {
            searchResultsCount.textContent = '0';
        }
        if (searchResultsPagination) {
            searchResultsPagination.style.display = 'none';
        }
        return;
    }

    searchResultsContainer.style.display = 'block';

    // Update count
    if (searchResultsCount) {
        searchResultsCount.textContent = searchResults.length;
    }

    // Calculate pagination
    const totalPages = Math.ceil(searchResults.length / itemsPerPage);
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    const paginatedResults = searchResults.slice(startIndex, endIndex);

    // Render results
    searchResultsList.innerHTML = paginatedResults.map(result => {
        const tagsHtml = (result.tags || []).map(tag => 
            `<span class="protein-tag">#${escapeHtml(tag)}</span>`
        ).join('');

        return `
            <div class="search-result-item" data-protein-id="${result.id}">
                <div class="search-result-content">
                    <div class="search-result-header">
                        <span class="protein-icon">🧬</span>
                        <button class="protein-title-link" data-protein-id="${result.id}">
                            ${escapeHtml(result.proteinId || '')} · ${escapeHtml(result.proteinName || '')}
                        </button>
                    </div>
                    <p class="search-result-meta">
                        ${escapeHtml(result.description || '')} · Gene: ${escapeHtml(result.gene || '')} · ${escapeHtml(result.organism || '')} · ${result.length || 0} amino acids · ${escapeHtml(result.evidenceLevel || '')} · Annotation score: ${result.annotationScore || 0}/5
                    </p>
                    <div class="search-result-tags">
                        ${tagsHtml}
                    </div>
                </div>
                <div class="search-result-actions">
                    <button class="result-action-btn result-action-copy" title="복사" data-protein-id="${result.id}">
                        <i class="fas fa-copy"></i>
                    </button>
                    <button class="result-action-btn result-action-detail" title="상세 보기" data-protein-id="${result.id}">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="result-action-btn result-action-save" title="노트에 저장" data-protein-id="${result.id}">
                        <i class="fas fa-save"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    // Attach event handlers
    attachSearchResultHandlers();

    // Update pagination
    updatePagination(totalPages);
}

// Update pagination UI
function updatePagination(totalPages) {
    if (!searchResultsPagination || !prevPageBtn || !nextPageBtn || !currentPageSpan || !totalPagesSpan) return;

    if (searchResults.length > itemsPerPage) {
        searchResultsPagination.style.display = 'flex';
        
        prevPageBtn.disabled = currentPage === 1;
        nextPageBtn.disabled = currentPage === totalPages;
        
        currentPageSpan.textContent = currentPage;
        totalPagesSpan.textContent = totalPages;
    } else {
        searchResultsPagination.style.display = 'none';
    }
}

// Handle page change
function handlePageChange(page) {
    const totalPages = Math.ceil(searchResults.length / itemsPerPage);
    if (page < 1 || page > totalPages) return;
    
    currentPage = page;
    renderSearchResults();
    
    // Scroll to results
    if (searchResultsContainer) {
        searchResultsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Attach search result handlers
function attachSearchResultHandlers() {
    // Search result item click (opens detail modal and selects protein)
    const resultItems = searchResultsList?.querySelectorAll('.search-result-item');
    resultItems?.forEach(item => {
        item.addEventListener('click', (e) => {
            // Don't trigger if clicking on action buttons
            if (e.target.closest('.search-result-actions')) {
                return;
            }
            const proteinId = item.getAttribute('data-protein-id');
            const result = searchResults.find(r => r.id === parseInt(proteinId));
            if (result) {
                // Set as selected protein for pipeline
                selectedProtein = result;
                sequenceQuery = result.sequence || '';
                
                // Update protein input
                if (proteinSequenceInput) {
                    proteinSequenceInput.value = result.sequence || '';
                }
                
                // Update pipeline
                updatePipelineSection();
                
                // Open detail modal
                handleProteinDetailClick(result);
            }
        });
    });

    // Protein title click
    const titleLinks = searchResultsList?.querySelectorAll('.protein-title-link');
    titleLinks?.forEach(link => {
        link.addEventListener('click', (e) => {
            e.stopPropagation();
            const proteinId = link.getAttribute('data-protein-id');
            const result = searchResults.find(r => r.id === parseInt(proteinId));
            if (result) {
                // Set as selected protein for pipeline
                selectedProtein = result;
                sequenceQuery = result.sequence || '';
                
                // Update protein input
                if (proteinSequenceInput) {
                    proteinSequenceInput.value = result.sequence || '';
                }
                
                // Update pipeline
                updatePipelineSection();
                
                // Open detail modal
                handleProteinDetailClick(result);
            }
        });
    });

    // Copy button
    const copyBtns = searchResultsList?.querySelectorAll('.result-action-copy');
    copyBtns?.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const proteinId = btn.getAttribute('data-protein-id');
            const result = searchResults.find(r => r.id === parseInt(proteinId));
            if (result) {
                handleCopySequence(result);
            }
        });
    });

    // Detail button
    const detailBtns = searchResultsList?.querySelectorAll('.result-action-detail');
    detailBtns?.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const proteinId = btn.getAttribute('data-protein-id');
            const result = searchResults.find(r => r.id === parseInt(proteinId));
            if (result) {
                // Set as selected protein for pipeline
                selectedProtein = result;
                sequenceQuery = result.sequence || '';
                
                // Update protein input
                if (proteinSequenceInput) {
                    proteinSequenceInput.value = result.sequence || '';
                }
                
                // Update pipeline
                updatePipelineSection();
                
                // Open detail modal
                handleProteinDetailClick(result);
            }
        });
    });

    // Save button
    const saveBtns = searchResultsList?.querySelectorAll('.result-action-save');
    saveBtns?.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const proteinId = btn.getAttribute('data-protein-id');
            const result = searchResults.find(r => r.id === parseInt(proteinId));
            if (result) {
                handleSaveToNote(result);
            }
        });
    });
}

// Handle copy sequence
function handleCopySequence(result) {
    if (!result || !result.sequence) {
        if (window.notyf) {
            window.notyf.error('복사할 서열이 없습니다.');
        }
        return;
    }

    // Use modern Clipboard API if available
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(result.sequence).then(() => {
            if (window.notyf) {
                window.notyf.success('서열이 복사되었습니다.');
            }
        }).catch(err => {
            console.error('Failed to copy:', err);
            fallbackCopySequence(result.sequence);
        });
    } else {
        fallbackCopySequence(result.sequence);
    }
}

// Fallback copy method
function fallbackCopySequence(sequence) {
    const textArea = document.createElement('textarea');
    textArea.value = sequence;
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        if (window.notyf) {
            window.notyf.success('서열이 복사되었습니다.');
        }
    } catch (err) {
        console.error('Failed to copy:', err);
        if (window.notyf) {
            window.notyf.error('서열 복사에 실패했습니다.');
        }
    }
    
    document.body.removeChild(textArea);
}

// Handle protein detail click
async function handleProteinDetailClick(result) {
    if (!result) {
        console.error('Protein detail click: No result data provided');
        return;
    }
    let detail = { ...result };

    try {
        if (!result.proteinId) {
            console.error('No accession/proteinId on result:', result);
        } else {
            const response = await fetch(
                `/api/experiments/uniprot/detail/${encodeURIComponent(result.proteinId)}/`,
                {
                    method: 'GET',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json',
                    },
                },
            );

            if (response.ok) {
                const data = await response.json();
                const seq = data.sequence || {};

                // ✅ uniprot_detail_api 응답 → mock 구조 그대로 채우기
                detail = {
                    // 리스트 id는 그대로 유지
                    id: result.id || 0,

                    // 기본 ID / 이름
                    proteinId: data.accession,              // "P38567"
                    proteinName: data.entry_name,           // "HYALP_HUMAN"

                    // 설명/이름
                    description: data.description || result.description || '',
                    recommendedName: data.protein_recommended_name || result.recommendedName || result.description || '',

                    // cleaved chains (API에는 없으니 검색 결과/기본값 유지)
                    cleavedChains: result.cleavedChains || null,

                    // Names & Taxonomy
                    gene: data.gene || result.gene || '',
                    organism: data.organism || result.organism || '',
                    taxonomicId: data.taxonomy_id ? `${data.taxonomy_id} (NCBI)` : (result.taxonomicId || ''),
                    taxonomicLineage: data.lineage || result.taxonomicLineage || '',

                    // 추가 정보
                    length: data.length || seq.length || result.length || 0,
                    mass: seq.mass || result.mass || '',
                    lastUpdated: seq.last_updated || result.lastUpdated || '',
                    md5Checksum: seq.md5 || result.md5Checksum || '',
                    evidenceLevel: data.evidence_level || result.evidenceLevel || '',
                    annotationScore: data.annotation_score ?? result.annotationScore ?? 0,

                    // 태그
                    tags: data.keywords || result.tags || [],

                    // 서열
                    sequence: seq.value || result.sequence || '',
                };

                // 디버깅용
                // console.log('[UniProt detail mapped]', detail);
            } else {
                console.error('UniProt detail API error', response.status);
            }
        }
    } catch (error) {
        console.error('Error loading UniProt detail:', error);
    }
    // Set as selected protein for pipeline first
    selectedProtein = detail;
    if (window.ExperimentPage) {
        window.ExperimentPage.selectedProtein = detail;
    }

    // Update pipeline visualization
    updatePipelineSection();
    
    // Open detail modal
    if (window.ProteinDetailModal && window.ProteinDetailModal.open) {
        window.ProteinDetailModal.open(detail);
    } else {
        console.error('ProteinDetailModal not available. Make sure protein_detail_modal.js is loaded.');
        // Fallback: try to initialize modal if it exists
        const modal = document.getElementById('proteinDetailModal');
        if (modal && typeof initProteinDetailModal === 'function') {
            initProteinDetailModal();
            if (window.ProteinDetailModal && window.ProteinDetailModal.open) {
                window.ProteinDetailModal.open(detail);
            }
        }
    }
}

// Handle save to note
function handleSaveToNote(result) {
    if (window.SaveToNoteModal && window.SaveToNoteModal.open) {
        window.SaveToNoteModal.open(result);
    } else {
        console.error('SaveToNoteModal not available');
    }
}





// Handle tool selection
function toggleToolSelection(toolId) {
    if (selectedTools.includes(toolId)) {
        selectedTools = selectedTools.filter(id => id !== toolId);
    } else {
        selectedTools = [...selectedTools, toolId];
    }
    
    selectedTools = getSelectedToolsInOrder().map(t => t.id);
    updateToolCards();
    updatePipelineActions();
}

// Update tool cards UI
function updateToolCards() {
    const toolCards = toolsGrid?.querySelectorAll('.tool-card');
    toolCards?.forEach(card => {
        const toolId = parseInt(card.getAttribute('data-tool-id'));
        const isSelected = selectedTools.includes(toolId);
        
        if (isSelected) {
            card.classList.add('selected');
            const statusEl = card.querySelector('.tool-status');
            if (statusEl) {
                statusEl.textContent = '선택됨';
            }
            // Add check icon if not present
            if (!card.querySelector('.tool-check-icon')) {
                const checkIcon = document.createElement('div');
                checkIcon.className = 'tool-check-icon';
                checkIcon.innerHTML = '<i class="fas fa-check-circle"></i>';
                card.insertBefore(checkIcon, card.firstChild);
            }
        } else {
            card.classList.remove('selected');
            const statusEl = card.querySelector('.tool-status');
            if (statusEl) {
                statusEl.textContent = '대기';
            }
            // Remove check icon if present
            const checkIcon = card.querySelector('.tool-check-icon');
            if (checkIcon) {
                checkIcon.remove();
            }
        }
    });
}

// Update pipeline actions visibility
function updatePipelineActions() {
    if (pipelineActions) {
        if (selectedTools.length > 0) {
            pipelineActions.style.display = 'flex';
        } else {
            pipelineActions.style.display = 'none';
        }
    }

    // Update fixed pipeline section
    updatePipelineSection();
}

// Update fixed pipeline section
function updatePipelineSection() {
    if (!pipelineSection) return;

    const mainContent = document.querySelector('.experiment-main');
    
    if (selectedTools.length > 0) {
        pipelineSection.style.display = 'block';
        renderPipelineVisualization();
        renderPipelineOptions();
        // Add padding to main content when pipeline is shown (React: pb-48)
        if (mainContent) {
            mainContent.style.paddingBottom = '12rem'; // pb-48 = 12rem
        }
    } else {
        pipelineSection.style.display = 'none';
        // Remove padding when pipeline is hidden
        if (mainContent) {
            mainContent.style.paddingBottom = '';
        }
    }

    // Update tool count
    const pipelineToolCountEl = document.getElementById('pipelineToolCount');
    if (pipelineToolCountEl) {
        pipelineToolCountEl.textContent = selectedTools.length;
    }
}

// Render pipeline visualization
function renderPipelineVisualization() {
    if (!pipelineItems) return;

    // Get selected tools in order
    const selectedToolsData = getSelectedToolsInOrder();

    // Render protein button
    renderPipelineProteinButton();

    // Render tools with arrows between them
    // React structure: Protein -> Arrow -> Tool1 -> Arrow -> Tool2 -> ...
    const toolsHtml = selectedToolsData.map((tool, index) => {
        const iconClass = tool.icon || "fas fa-cog";
        return `
            <div class="pipeline-item pipeline-item-tool" data-tool-id="${tool.id}">
                <div class="pipeline-tool-card">
                    <i class="${iconClass}"></i>
                    <span>${escapeHtml(tool.name)}</span>
                    <button class="pipeline-tool-settings-btn" data-tool-id="${tool.id}" title="옵션 설정">
                        <i class="fas fa-cog"></i>
                    </button>
                </div>
            </div>
            ${index < selectedToolsData.length - 1 ? '<div class="pipeline-arrow"><i class="fas fa-arrow-right"></i></div>' : ''}
        `;
    }).join('');

    // Find protein item and insert arrow + tools after it
    const proteinItem = pipelineItems.querySelector('.pipeline-item-protein');
    if (proteinItem) {
        // Remove existing tool items and arrows (but keep protein item)
        const existingItems = pipelineItems.querySelectorAll('.pipeline-item-tool, .pipeline-arrow');
        existingItems.forEach(item => item.remove());

        // Insert arrow before tools if there are any tools
        if (selectedToolsData.length > 0) {
            // Add arrow after protein button
            const arrowAfterProtein = document.createElement('div');
            arrowAfterProtein.className = 'pipeline-arrow';
            arrowAfterProtein.innerHTML = '<i class="fas fa-arrow-right"></i>';
            proteinItem.after(arrowAfterProtein);
            
            arrowAfterProtein.insertAdjacentHTML('afterend', toolsHtml);
            // // Insert tools with arrows
            // const tempDiv = document.createElement('div');
            // tempDiv.innerHTML = toolsHtml;
            // while (tempDiv.firstChild) {
            //     arrowAfterProtein.after(tempDiv.firstChild);
            // }
        }
    }
    
    // Attach click handlers for settings buttons
    attachPipelineToolHandlers();
}

// Render pipeline protein button
function renderPipelineProteinButton() {
    if (!pipelineProteinBtn || !pipelineProteinItem) return;

    if (selectedProtein) {
        pipelineProteinBtn.className = 'pipeline-protein-btn pipeline-protein-btn-selected';
        const proteinName = selectedProtein.name || selectedProtein.proteinName || '선택된 서열';
        pipelineProteinBtn.innerHTML = `
            <i class="fas fa-file-lines"></i>
            <div>
                <p class="text-xs">${escapeHtml(proteinName)}</p>
            </div>
        `;
    } else {
        pipelineProteinBtn.className = 'pipeline-protein-btn pipeline-protein-btn-empty';
        pipelineProteinBtn.innerHTML = `
            <i class="fas fa-file-lines"></i>
            <div>
                <p class="text-xs text-red-600">단백질 서열 선택</p>
            </div>
        `;
    }
}

// Render pipeline options
function renderPipelineOptions() {
    if (!pipelineOptionsSection || !pipelineOptionsGrid) return;

    const selectedToolsData = getSelectedToolsInOrder();
    
    if (selectedToolsData.length === 0) {
        pipelineOptionsSection.style.display = 'none';
        return;
    }

    pipelineOptionsSection.style.display = 'block';

    // Render options for each tool
    pipelineOptionsGrid.innerHTML = selectedToolsData.map(tool => {
        const currentOptions = toolOptions[tool.id] || {};
        const optionFields = tool.optionFields || [];

        if (optionFields.length === 0) {
            return '';
        }

        return `
            <div class="pipeline-tool-options" data-tool-id="${tool.id}">
                <h4 class="pipeline-tool-options-title">${escapeHtml(tool.name)} 옵션</h4>
                <div class="pipeline-tool-options-fields">
                    ${optionFields.map(field => {
                        const value = currentOptions[field.name] ?? field.default;
                        return renderToolOptionField(tool.id, field, value);
                    }).join('')}
                </div>
            </div>
        `;
    }).filter(html => html).join('');

    // Attach option field listeners
    attachPipelineOptionListeners();
}

// Render tool option field - React layout: flex items-center gap-3
function renderToolOptionField(toolId, field, value) {
    let inputHtml = '';

    if (field.type === 'number') {
        inputHtml = `
            <div class="pipeline-option-field">
                <label class="pipeline-option-label">${escapeHtml(field.label)}</label>
                <input
                    type="number"
                    class="pipeline-option-input"
                    data-tool-id="${toolId}"
                    data-field-name="${field.name}"
                    value="${value}"
                    min="${field.min || ''}"
                    max="${field.max || ''}"
                    step="${field.step || 1}"
                />
            </div>
        `;
    } else if (field.type === 'select') {
        inputHtml = `
            <div class="pipeline-option-field">
                <label class="pipeline-option-label">${escapeHtml(field.label)}</label>
                <select
                    class="pipeline-option-select"
                    data-tool-id="${toolId}"
                    data-field-name="${field.name}"
                >
                    ${field.options.map(opt => 
                        `<option value="${opt}" ${value === opt ? 'selected' : ''}>${escapeHtml(opt)}</option>`
                    ).join('')}
                </select>
            </div>
        `;
    } else if (field.type === 'checkbox') {
        inputHtml = `
            <div class="pipeline-option-field">
                <label class="pipeline-option-label">${escapeHtml(field.label)}</label>
                <input
                    type="checkbox"
                    class="pipeline-option-checkbox-input"
                    data-tool-id="${toolId}"
                    data-field-name="${field.name}"
                    ${value ? 'checked' : ''}
                />
            </div>
        `;
    }

    return inputHtml;
}

// Attach pipeline option listeners
function attachPipelineOptionListeners() {
    const inputs = pipelineOptionsGrid?.querySelectorAll('[data-tool-id][data-field-name]');
    inputs?.forEach(input => {
        const toolId = parseInt(input.getAttribute('data-tool-id'));
        const fieldName = input.getAttribute('data-field-name');

        if (input.type === 'checkbox') {
            input.addEventListener('change', (e) => {
                updateToolOption(toolId, fieldName, e.target.checked);
            });
        } else {
            input.addEventListener('input', (e) => {
                const value = input.type === 'number' 
                    ? parseFloat(e.target.value) 
                    : e.target.value;
                updateToolOption(toolId, fieldName, value);
            });
        }
    });
}

// Update tool option
function updateToolOption(toolId, fieldName, value) {
    if (!toolOptions[toolId]) {
        toolOptions[toolId] = {};
    }
    toolOptions[toolId][fieldName] = value;
}

// Get selected tools in order
function getSelectedToolsInOrder() {
    // 1) 현재 선택된 도구 객체 배열
    const tools = selectedTools
        .map(id => availableTools.find(t => t.id === id))
        .filter(t => t);

    // 2) 이름에 키워드가 들어있는지 기준으로 정렬
    const getOrderKey = (tool) => {
        const name = (tool.name || '').toLowerCase();

        if (name.includes('rfdiffusion')) return 0;     // RFdiffusion
        if (name.includes('proteinmpnn')) return 1;     // ProteinMPNN
        if (name.includes('alphafold')) return 2;       // AlphaFold3

        return 99;  // 정의 안 된 도구는 맨 뒤
    };

    return tools.sort((a, b) => getOrderKey(a) - getOrderKey(b));
}
    // return selectedTools.map(id => 
    //     availableTools.find(t => t.id === id)
    // ).filter(t => t);

// Attach pipeline handlers
function attachPipelineHandlers() {
    console.log('[ExperimentPage] attachPipelineHandlers called');
    console.log('[ExperimentPage] pipelineProteinBtn:', pipelineProteinBtn);
    
    // Protein button click
    if (!pipelineProteinBtn) {
        console.error('[ExperimentPage] pipelineProteinBtn not found!');
        return;
    }
    
    pipelineProteinBtn.addEventListener('click', (e) => {
        console.log('[ExperimentPage] ====== pipelineProteinBtn CLICKED ======');
        console.log('[ExperimentPage] Event:', e);
        console.log('[ExperimentPage] window.SequenceInputModal:', window.SequenceInputModal);
        console.log('[ExperimentPage] window.SequenceInputModal?.open:', window.SequenceInputModal?.open);
        
        const openModal = () => {
            console.log('[ExperimentPage] openModal function called');
        if (window.SequenceInputModal && window.SequenceInputModal.open) {
            const initialSequence = selectedProtein?.sequence || sequenceQuery || '';
                console.log('[ExperimentPage] Opening SequenceInputModal with initialSequence:', initialSequence);
                console.log('[ExperimentPage] selectedProtein:', selectedProtein);
                console.log('[ExperimentPage] sequenceQuery:', sequenceQuery);
            window.SequenceInputModal.open(initialSequence);
                console.log('[ExperimentPage] SequenceInputModal.open called');
            } else {
                console.error('[ExperimentPage] SequenceInputModal not available in openModal');
                if (window.notyf) {
                    window.notyf.error('서열 입력 모달을 불러올 수 없습니다.');
                }
            }
        };
        
        // Try to open immediately
        if (window.SequenceInputModal && window.SequenceInputModal.open) {
            console.log('[ExperimentPage] SequenceInputModal available, opening immediately');
            openModal();
        } else {
            console.log('[ExperimentPage] SequenceInputModal not available, waiting...');
            // Wait for SequenceInputModal to be available
            let attempts = 0;
            const maxAttempts = 20;
            const checkInterval = setInterval(() => {
                attempts++;
                console.log(`[ExperimentPage] Checking SequenceInputModal (attempt ${attempts}/${maxAttempts})`);
                if (window.SequenceInputModal && window.SequenceInputModal.open) {
                    clearInterval(checkInterval);
                    console.log('[ExperimentPage] SequenceInputModal now available, opening');
                    openModal();
                } else if (attempts >= maxAttempts) {
                    clearInterval(checkInterval);
                    console.error('[ExperimentPage] SequenceInputModal not available after waiting');
                    if (window.notyf) {
                        window.notyf.error('서열 입력 모달을 불러올 수 없습니다.');
                    }
                }
            }, 50);
        }
    });
    
    console.log('[ExperimentPage] pipelineProteinBtn click event listener attached');

    // Clear pipeline button
    pipelineClearBtn?.addEventListener('click', () => {
        handleClearPipeline();
    });

    // Run pipeline button - opens simulation confirm modal
    pipelineRunBtn?.addEventListener('click', (e) => {
        console.log('[ExperimentPage] ====== pipelineRunBtn CLICKED ======');
        console.log('[ExperimentPage] window.SimulationConfirmModal:', window.SimulationConfirmModal);
        
        const openModal = () => {
            if (selectedTools.length === 0) {
                if (window.notyf) {
                    window.notyf.error('최소 하나의 도구를 선택해주세요.');
                }
                return;
            }

            if (!sequenceQuery && !proteinSequenceInput?.value.trim()) {
                if (window.notyf) {
                    window.notyf.error('단백질 서열을 입력해주세요.');
                }
                return;
            }

            const sequence = selectedProtein?.sequence || proteinSequenceInput?.value.trim() || sequenceQuery;
            const selectedToolsData = getSelectedToolsInOrder();   
            
            console.log('[ExperimentPage] Opening SimulationConfirmModal');
            console.log('[ExperimentPage] Selected tools:', selectedToolsData);
            console.log('[ExperimentPage] Sequence:', sequence);
            
            if (window.SimulationConfirmModal && window.SimulationConfirmModal.open) {
                window.SimulationConfirmModal.open(selectedToolsData, sequence);
            } else {
                console.error('[ExperimentPage] SimulationConfirmModal not available in openModal');
                if (window.notyf) {
                    window.notyf.error('시뮬레이션 확인 모달을 불러올 수 없습니다.');
                }
            }
        };
        
        // Try to open immediately
        if (window.SimulationConfirmModal && window.SimulationConfirmModal.open) {
            console.log('[ExperimentPage] SimulationConfirmModal available, opening immediately');
            openModal();
        } else {
            console.log('[ExperimentPage] SimulationConfirmModal not available, waiting...');
            // Wait for SimulationConfirmModal to be available
            let attempts = 0;
            const maxAttempts = 20;
            const checkInterval = setInterval(() => {
                attempts++;
                console.log(`[ExperimentPage] Checking SimulationConfirmModal (attempt ${attempts}/${maxAttempts})`);
                if (window.SimulationConfirmModal && window.SimulationConfirmModal.open) {
                    clearInterval(checkInterval);
                    console.log('[ExperimentPage] SimulationConfirmModal now available, opening');
                    openModal();
                } else if (attempts >= maxAttempts) {
                    clearInterval(checkInterval);
                    console.error('[ExperimentPage] SimulationConfirmModal not available after waiting');
                    // Fallback: use handleRunSimulation which has its own fallback
        handleRunSimulation();
                }
            }, 50);
        }
    });
}

// Attach pipeline tool handlers (settings button clicks)
function attachPipelineToolHandlers() {
    const settingsButtons = document.querySelectorAll('.pipeline-tool-settings-btn');
    settingsButtons.forEach(btn => {
        // Remove existing listeners to prevent duplicates
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        
        newBtn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent event bubbling
            const toolId = parseInt(newBtn.getAttribute('data-tool-id'));
            const tool = availableTools.find(t => t.id === toolId);
            if (tool && window.ToolOptionsModal) {
                window.ToolOptionsModal.open(tool);
            } else if (tool) {
                console.error('ToolOptionsModal not available');
                // Fallback: try to wait for modal
                let attempts = 0;
                const maxAttempts = 10;
                const checkInterval = setInterval(() => {
                    attempts++;
                    if (window.ToolOptionsModal) {
                        clearInterval(checkInterval);
                        window.ToolOptionsModal.open(tool);
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                        console.error('ToolOptionsModal not available after waiting');
                        if (window.notyf) {
                            window.notyf.error('옵션 모달을 불러올 수 없습니다.');
                        }
                    }
                }, 100);
            }
        });
    });
}

// Handle run simulation
async function handleRunSimulation() {
    if (selectedTools.length === 0) {
        if (window.notyf) {
            window.notyf.error('최소 하나의 도구를 선택해주세요.');
        } else {
            alert('최소 하나의 도구를 선택해주세요.');
        }
        return;
    }

    if (!sequenceQuery && !proteinSequenceInput?.value.trim()) {
        if (window.notyf) {
            window.notyf.error('단백질 서열을 입력해주세요.');
        } else {
            alert('단백질 서열을 입력해주세요.');
        }
        return;
    }

    // Open simulation confirm modal
    if (window.SimulationConfirmModal && window.SimulationConfirmModal.open) {
        const sequence = selectedProtein?.sequence || proteinSequenceInput?.value.trim() || sequenceQuery;
        const selectedToolsData = getSelectedToolsInOrder();
        window.SimulationConfirmModal.open(selectedToolsData, sequence);
    } else {
        // Fallback: direct confirmation
        const sequence = selectedProtein?.sequence || proteinSequenceInput?.value.trim() || sequenceQuery;
        const confirmed = confirm(`선택한 ${selectedTools.length}개의 도구로 시뮬레이션을 실행하시겠습니까?`);
        if (!confirmed) return;
        await executeSimulation(sequence);
    }
}

// Execute simulation (extracted for reuse)
async function executeSimulation(sequence = null, title = null) {
    // Use selected protein sequence if available
    const finalSequence = sequence || selectedProtein?.sequence || sequenceQuery || proteinSequenceInput?.value.trim() || '';
    
    if (!finalSequence) {
        console.log('[ExperimentPage] executeSimulation: No sequence provided');
        if (window.notyf) {
            window.notyf.error('단백질 서열을 입력해주세요.');
        } else {
            alert('단백질 서열을 입력해주세요.');
        }
        return;
    }
    const orderedTools = getSelectedToolsInOrder().map(t => t.id)
    const requestData = {
        tools: orderedTools,
        protein_sequence: finalSequence,
        pipeline_name: title || `Pipeline ${new Date().toLocaleString('ko-KR')}`,
        tool_options: toolOptions,
    };
    
    console.log('[ExperimentPage] ====== executeSimulation called ======');
    console.log('[ExperimentPage] Request URL: /api/experiments/');
    console.log('[ExperimentPage] Request method: POST');
    console.log('[ExperimentPage] Request data:', requestData);
    console.log('[ExperimentPage] CSRF Token:', getCsrfToken() ? 'Present' : 'Missing');

    try {
        const response = await fetch('/api/experiments/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData),
        });

        console.log('[ExperimentPage] Response status:', response.status);
        console.log('[ExperimentPage] Response statusText:', response.statusText);
        console.log('[ExperimentPage] Response headers:', {
            'content-type': response.headers.get('content-type'),
            'content-length': response.headers.get('content-length'),
        });

        // Check if response is JSON before parsing
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const text = await response.text();
            console.warn('[ExperimentPage] API returned non-JSON response');
            console.warn('[ExperimentPage] Response content (first 500 chars):', text.substring(0, 500));
            console.warn('[ExperimentPage] Response URL:', response.url);
            console.warn('[ExperimentPage] Response status:', response.status, response.statusText);
            // Don't show error to user, just log
            return;
        }

        if (response.ok) {
            try {
            const data = await response.json();
                console.log('[ExperimentPage] API response (success):', data);
            
            // Show success message
            if (window.notyf) {
                window.notyf.success('시뮬레이션이 시작되었습니다.');
            }
            
            // Reload experiments
            loadExperiments();
            
            // Clear selection
            selectedTools = [];
            updateToolCards();
            updatePipelineActions();
            } catch (jsonError) {
                console.error('[ExperimentPage] Error parsing JSON response:', jsonError);
                console.error('[ExperimentPage] JSON parse error details:', {
                    name: jsonError.name,
                    message: jsonError.message,
                });
            if (window.notyf) {
                    window.notyf.error('응답 데이터를 파싱하는데 실패했습니다.');
            }
        }
        } else {
            // Try to parse error response as JSON
            try {
                const error = await response.json();
                console.warn('[ExperimentPage] API error response:', error);
                // Don't show error to user, just log
            } catch (jsonError) {
                // If error response is not JSON, log status text
                const text = await response.text().catch(() => '');
                console.warn('[ExperimentPage] Error response is not JSON');
                console.warn('[ExperimentPage] Status:', response.status, response.statusText);
                console.warn('[ExperimentPage] Response content (first 500 chars):', text.substring(0, 500));
                // Don't show error to user, just log
            }
        }
    } catch (error) {
        console.error('[ExperimentPage] Error running simulation:', error);
        console.error('[ExperimentPage] Error details:', {
            name: error.name,
            message: error.message,
            stack: error.stack,
        });
        // Don't show error to user, just log
    }
    
    console.log('[ExperimentPage] ====== executeSimulation completed ======');
}

// Handle clear pipeline
function handleClearPipeline() {
    selectedTools = [];
    toolOptions = {};
    selectedProtein = null;
    updateToolCards();
    updatePipelineActions();
    
    // Clear protein input
    if (proteinSequenceInput) {
        proteinSequenceInput.value = '';
    }
    sequenceQuery = '';
}

// Render tool list
function renderToolList() {
    if (!toolList) return;

    let filteredTools = availableTools;

    // Filter by search query
    if (toolSearchQuery) {
        filteredTools = availableTools.filter(tool =>
            tool.name.toLowerCase().includes(toolSearchQuery) ||
            tool.description.toLowerCase().includes(toolSearchQuery) ||
            tool.category.toLowerCase().includes(toolSearchQuery)
        );
    }

    if (filteredTools.length === 0) {
        toolList.innerHTML = '<div class="empty-state"><p>검색 결과가 없습니다.</p></div>';
        return;
    }

    toolList.innerHTML = filteredTools.map(tool => {
        return `
            <div class="tool-item" data-tool-id="${tool.id}" data-tool-name="${tool.name}">
                <div class="tool-header">
                    <p>${escapeHtml(tool.name)}</p>
                    <i class="fas fa-book" data-tool-id="${tool.id}"></i>
                </div>
                <p class="tool-description">${escapeHtml(tool.description)}</p>
                <span class="tool-category">${escapeHtml(tool.category)}</span>
            </div>
        `;
    }).join('');

    // Re-attach handlers
    attachToolItemHandlers();
}

// Render tools grid
function renderToolsGrid() {
    if (!toolsGrid) return;

    toolsGrid.innerHTML = availableTools.map(tool => {
        const isSelected = selectedTools.includes(tool.id);
        const iconClass = tool.icon || "fas fa-cog";
        return `
            <div class="tool-card ${isSelected ? 'selected' : ''}" data-tool-id="${tool.id}">
                ${isSelected ? '<div class="tool-check-icon"><i class="fas fa-check-circle"></i></div>' : ''}
                <div class="flex flex-col items-center text-center">
                    <div class="tool-icon">
                        <i class="${iconClass}"></i>
                    </div>
                    <p class="tool-name">${escapeHtml(tool.name)}</p>
                    <p class="tool-desc">${escapeHtml(tool.description)}</p>
                </div>
                <div class="tool-status">${isSelected ? '선택됨' : '대기'}</div>
            </div>
        `;
    }).join('');

    // Re-attach handlers
    attachToolCardHandlers();
}

// Render experiment table
function renderExperimentTable(experiments) {
    if (!experimentTableBody) return;

    if (experiments.length === 0) {
        experimentTableBody.innerHTML = `
            <tr>
                <td colspan="4" class="empty-state-cell">
                    <div class="empty-state">
                        <p class="empty-message">상단의 시뮬레이션 실험을 진행하시면 진행상태를 확인할 수 있습니다</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    experimentTableBody.innerHTML = experiments.map(experiment => {
        // 도구 정보 처리 - API에서 도구 이름 배열로 반환됨
        const tools = experiment.tools || [];
        const toolsHtml = tools.map(tool => {
            const toolName = typeof tool === 'string' ? tool : (tool.name || tool.tool_name || tool);
            return `<span class="tool-tag">${escapeHtml(toolName)}</span>`;
        }).join('');

        // 상태 처리 - API에서 status_display를 제공하거나 상태 코드를 변환
        const statusCode = experiment.status || 'R';
        const rawStatusDisplay = experiment.status_display || 
                            (statusCode === 'C' ? '완료' :
                            statusCode === 'P' ? '진행중' :
                            statusCode === 'R' ? '준비' :
                            statusCode === 'F' ? '진행' : //실패를 변경
                            statusCode === 'E' ? '활성' :
                            statusCode === 'D' ? '비활성' : statusCode);
        const statusDisplay =
            rawStatusDisplay === 'Failed' || rawStatusDisplay === '실패'
                ? '진행'
                : rawStatusDisplay;
        
                    
        
        // 생성일 처리
        const createdAgo = experiment.created_at ? 
            formatTimeAgo(new Date(experiment.created_at)) : 
            (experiment.created || '알 수 없음');

        // 진행률 처리 - API에서 직접 제공
        const progress = experiment.progress !== undefined ? experiment.progress : 
                        (statusCode === 'C' ? 100 : 
                        statusCode === 'P' ? 65 : 
                        statusCode === 'R' ? 25 : 0);

        // 파이프라인 이름 처리
        const pipelineName = experiment.pipeline || experiment.pipeline_name || experiment.name || 'Unnamed Pipeline';

        // 상태 클래스 결정
        // const statusClass = normalizedStatusDisplay === '완료' ? 'status-완료 status-completed' :
        //                    statusDisplay === '진행중' ? 'status-진행중 status-progress' :
        //                    statusDisplay === '준비' ? 'status-준비 status-ready' :
        //                    statusDisplay === '진행' ? 'status-진행 status-failed' : //실패를 변경
        //                    'status-준비 status-ready';
        
        // const statusDotClass = normalizedStatusDisplay === '완료' ? 'status-dot-완료 status-dot-completed' :
        //                       statusDisplay === '진행중' ? 'status-dot-진행중 status-dot-progress' :
        //                       statusDisplay === '준비' ? 'status-dot-준비 status-dot-ready' :
        //                       statusDisplay === '진행' ? 'status-dot-진행 status-dot-failed' : //실패를 변경
        //                       'status-dot-준비 status-dot-ready';
        const statusClass =
                            statusDisplay === '완료'   ? 'status-completed' :
                            statusDisplay === '진행'   ? 'status-progress' :
                            statusDisplay === '진행중' ? 'status-progress' :
                            statusDisplay === '준비'   ? 'status-ready' :
                            'status-ready';

        const statusDotClass =
                            statusDisplay === '완료'   ? 'status-dot-completed' :
                            statusDisplay === '진행'   ? 'status-dot-progress' :
                            statusDisplay === '진행중' ? 'status-dot-progress' :
                            statusDisplay === '준비'   ? 'status-dot-ready' :
                            'status-dot-ready';

        return `
            <tr data-experiment-id="${experiment.id}" data-experiment-progress="${progress}" class="status-table-row">
                <td class="status-td-pipeline">
                    <p class="text-sm text-gray-900">${escapeHtml(pipelineName)}</p>
                </td>
                <td class="status-td-tools">
                    <div class="tool-tags">
                        ${toolsHtml}
                    </div>
                </td>
                <td class="status-td-status">
                    <span class="status-badge ${statusClass}">
                        <span class="status-dot ${statusDotClass}"></span>
                        ${statusDisplay}
                    </span>
                </td>
                <td class="status-td-created text-gray-600 text-sm whitespace-nowrap">${escapeHtml(createdAgo)}</td>
            </tr>
        `;
    }).join('');

    // Re-attach handlers
    attachExperimentTableHandlers();
}

// Attach tool item handlers
function attachToolItemHandlers() {
    const toolItems = toolList?.querySelectorAll('.tool-item');
    toolItems?.forEach(item => {
        item.addEventListener('click', (e) => {
            // Don't trigger if clicking on book icon
            if (!e.target.closest('.fa-book')) {
                const toolId = parseInt(item.getAttribute('data-tool-id'));
                // React: Clicking tool item opens guide modal
                showToolGuide(toolId);
            }
        });
    });

    const bookIcons = toolList?.querySelectorAll('.fa-book');
    bookIcons?.forEach(icon => {
        icon.addEventListener('click', (e) => {
            e.stopPropagation();
            const toolId = parseInt(icon.getAttribute('data-tool-id'));
            showToolGuide(toolId);
        });
    });
}

// Attach tool card handlers
function attachToolCardHandlers() {
    if (!toolsGrid) return;
    
    const toolCards = toolsGrid.querySelectorAll('.tool-card');
    toolCards.forEach(card => {
        // Remove existing listeners to prevent duplicates
        const newCard = card.cloneNode(true);
        card.parentNode.replaceChild(newCard, card);
        
        // Add click event listener
        newCard.addEventListener('click', (e) => {
            e.stopPropagation();
            const toolId = parseInt(newCard.getAttribute('data-tool-id'));
            if (!isNaN(toolId)) {
                toggleToolSelection(toolId);
            }
        });
        
        // Add cursor pointer style
        newCard.style.cursor = 'pointer';
    });
}

// Attach experiment table handlers
function attachExperimentTableHandlers() {
    const rows = experimentTableBody?.querySelectorAll('tr[data-experiment-id]');
    rows?.forEach(row => {
        row.addEventListener('click', () => {
            const experimentId = row.getAttribute('data-experiment-id');
            // Try to get experiment data from experiments array first (like React)
            const experiment = experiments.find(exp => exp.id == experimentId);
            if (experiment) {
                // Use existing data if available (like React's setSelectedExperiment)
                // Ensure experiment has all required fields for sidebar
                const experimentData = {
                    ...experiment,
                    pipeline: experiment.pipeline || experiment.pipeline_name || 'Unnamed Pipeline',
                    tools: experiment.tools || [],
                    status: experiment.status || 'ready',
                    progress: experiment.progress !== undefined ? experiment.progress : 
                             (experiment.status === 'completed' || experiment.status === '완료' ? 100 :
                              experiment.status === 'in_progress' || experiment.status === '진행중' ? 65 : 25),
                    created: experiment.created || formatTimeAgo(new Date(experiment.created_at || new Date()))
                };
                renderExperimentResult(experimentData);
                if (experimentResultSidebar) {
                    experimentResultSidebar.style.display = 'flex';
                    document.body.style.overflow = 'hidden';
                }
            } else {
                // Fallback: Load from API
                openExperimentResultSidebar(experimentId);
            }
        });
    });
}

// Open experiment result sidebar
async function openExperimentResultSidebar(experimentId) {
    if (!experimentResultSidebar) return;

    try {
        // Load experiment detail from API
        const response = await fetch(`/api/experiments/${experimentId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const experiment = await response.json();
            renderExperimentResult(experiment);
            experimentResultSidebar.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        } else {
            console.error('Failed to load experiment detail');
            if (window.notyf) {
                window.notyf.error('실험 정보를 불러오는데 실패했습니다.');
            }
        }
    } catch (error) {
        console.error('Error loading experiment detail:', error);
        if (window.notyf) {
            window.notyf.error('실험 정보를 불러오는 중 오류가 발생했습니다.');
        }
    }
}

// Close experiment result sidebar
function closeExperimentResultSidebar() {
    if (!experimentResultSidebar) return;
    experimentResultSidebar.style.display = 'none';
    document.body.style.overflow = '';
}

// Render experiment result
function renderExperimentResult(experiment) {
    // Pipeline name - React uses 'pipeline' field
    if (experimentResultPipelineName) {
        experimentResultPipelineName.textContent = experiment.pipeline || experiment.pipeline_name || 'Unnamed Pipeline';
    }

    // Tools list
    if (experimentResultToolsList) {
        const tools = experiment.tools || [];
        if (tools.length === 0) {
            experimentResultToolsList.innerHTML = '<p class="result-empty-text">도구 정보가 없습니다</p>';
        } else {
            experimentResultToolsList.innerHTML = tools.map(tool => {
                const toolName = typeof tool === 'string' ? tool : (tool.name || tool);
                return `<span class="result-tool-tag">${escapeHtml(toolName)}</span>`;
            }).join('');
        }
    }

    // Status - Convert status code to Korean
    if (experimentResultStatus) {
        const status = experiment.status || experiment.status_display || 'R';
        
        // Convert status code to Korean
        let statusDisplay = '';
        if (typeof status === 'string') {
            // Check if already in Korean
            if (status === '완료' || status === '진행중' || status === '준비' || status === '진행' || status === '활성' || status === '비활성') {
                statusDisplay = status;
            }
            // Check English status strings
            else if (status === 'completed' || status === 'C') {
                statusDisplay = '완료';
            } else if (status === 'in_progress' || status === 'P') {
                statusDisplay = '진행중';
            } else if (status === 'ready' || status === 'R') {
                statusDisplay = '준비';
            } else if (status === 'failed' || status === 'F') {
                statusDisplay = '진행';
            } else if (status === 'enabled' || status === 'E') {
                statusDisplay = '활성';
            } else if (status === 'disabled' || status === 'D') {
                statusDisplay = '비활성';
            } else {
                // Unknown status, use as-is
                statusDisplay = status;
            }
        } else {
            statusDisplay = '알 수 없음';
        }
        
        experimentResultStatus.textContent = statusDisplay;
    }

    // Progress - calculate from status if not provided
    // React uses progress directly from selectedExperiment.progress
    let progress = experiment.progress;
    if (progress === undefined || progress === null) {
        const status = experiment.status || experiment.status_display || 'R';
        // Convert status code to determine progress
        if (status === 'completed' || status === '완료' || status === 'C') {
            progress = 100;
        } else if (status === 'in_progress' || status === '진행중' || status === 'P') {
            progress = 65; // Default progress for in_progress (matching React mock data)
        } else if (status === 'ready' || status === '준비' || status === 'R') {
            progress = 25; // Default progress for ready (matching React mock data)
        } else if (status === 'failed' || status === '진행' || status === 'F') {
            progress = 0; // Failed experiments have 0% progress
        } else {
            progress = 0; // Default for unknown status
        }
    }
    
    if (experimentResultProgressFill) {
        experimentResultProgressFill.style.width = `${progress}%`;
    }
    if (experimentResultProgressText) {
        experimentResultProgressText.textContent = `${progress}%`;
    }

    // Result files
    renderExperimentResultFiles(experiment);
}

// Render experiment result files
async function renderExperimentResultFiles(experiment) {
    if (!experimentResultFilesList) return;

    // Try to load result files from API
    try {
        const response = await fetch(`/api/experiments/${experiment.id}/files/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
        });

        if (response.ok) {
            const data = await response.json();
            const resultFiles = data.results || data || [];
            if (resultFiles.length > 0) {
                renderResultFilesList(resultFiles, experiment.id);
                return;
            }
        }
    } catch (error) {
        console.error('Error loading result files:', error);
    }

    // Fallback: Use mock files based on status (React uses Korean status strings)
    const status = experiment.status || experiment.status_display || 'R';
    
    // Convert status code to Korean
    let statusKorean = '';
    if (typeof status === 'string') {
        // Check if already in Korean
        if (status === '완료' || status === '진행중' || status === '준비' || status === '진행') {
            statusKorean = status;
        }
        // Check English status strings and codes
        else if (status === 'completed' || status === 'C') {
            statusKorean = '완료';
        } else if (status === 'in_progress' || status === 'P') {
            statusKorean = '진행중';
        } else if (status === 'ready' || status === 'R') {
            statusKorean = '준비';
        } else if (status === 'failed' || status === 'F') {
            statusKorean = '진행';
        } else {
            statusKorean = '준비'; // Default
        }
    } else {
        statusKorean = '준비'; // Default
    }
    
    const mockFiles = generateMockResultFiles(statusKorean);
    renderResultFilesList(mockFiles, experiment.id);
}

// Generate mock result files based on status
// React uses Korean status strings: "완료", "진행중", etc.
function generateMockResultFiles(status) {
    // Convert status code/English to Korean for comparison
    let statusKorean = '';
    if (typeof status === 'string') {
        // Check if already in Korean
        if (status === '완료' || status === '진행중' || status === '준비' || status === '진행') {
            statusKorean = status;
        }
        // Check English status strings and codes
        else if (status === 'completed' || status === 'C') {
            statusKorean = '완료';
        } else if (status === 'in_progress' || status === 'P') {
            statusKorean = '진행중';
        } else if (status === 'ready' || status === 'R') {
            statusKorean = '준비';
        } else if (status === 'failed' || status === 'F') {
            statusKorean = '진행';
        } else {
            statusKorean = '준비'; // Default
        }
    } else {
        statusKorean = '준비'; // Default
    }
    
    if (statusKorean === '완료') {
        return [
            { id: 1, name: '구조 분석 결과', type: 'PDB', size: '2.3 MB', date: '2시간 전', url: '/api/experiments/files/1/' },
            { id: 2, name: '서열 데이터', type: 'FASTA', size: '156 KB', date: '2시간 전', url: '/api/experiments/files/2/' },
            { id: 3, name: '분석 리포트', type: 'PDF', size: '1.1 MB', date: '1시간 전', url: '/api/experiments/files/3/' },
        ];
    } else if (statusKorean === '진행중') {
        return [
            { id: 1, name: '중간 결과 1', type: 'TXT', size: '89 KB', date: '30분 전', url: '/api/experiments/files/1/' },
            { id: 2, name: '로그 파일', type: 'LOG', size: '234 KB', date: '15분 전', url: '/api/experiments/files/2/' },
        ];
    } else if (statusKorean === '진행') {
        return [
            { id: 1, name: '에러 로그', type: 'LOG', size: '45 KB', date: '1시간 전', url: '/api/experiments/files/1/' },
        ];
    } else {
        // 준비 상태 또는 기타
        return [
            { id: 1, name: '입력 데이터', type: 'CSV', size: '512 KB', date: '1일 전', url: '/api/experiments/files/1/' },
        ];
    }
}

//formatTime 함수 추가
function formatResultDate(value) {
    if (!value) return '신규';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '신규';
    return d.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

// Render result files list
function renderResultFilesList(files, experimentId) {
    if (!experimentResultFilesList) return;

    if (files.length === 0) {
        experimentResultFilesList.innerHTML = '<p class="result-empty-text">결과 파일이 없습니다</p>';
        return;
    }

    experimentResultFilesList.innerHTML = files.map(file => {
        const fileName = file.name || file.filename || 'Unknown';
        const fileType = file.type || file.file_type || 'FILE';
        const fileTypeRaw = fileType.toUpperCase();
        const isPdb = fileTypeRaw === 'PDB';
        const fileDateRaw = file.date || file.created_at || '신규';
        const fileDate = formatResultDate(fileDateRaw);
        // 백엔드 프록시 URL 사용 (CORS 문제 해결)
        const fileId = file.id || file.result_sid || file.file_id;
        const fileUrl = fileId ? `/api/experiments/results/${fileId}/file/` : (file.file_path || file.url || file.file_url || '');


        return `
            <div class="result-file-item" data-file-id="${fileId}">
                <div class="result-file-header">
                    <p class="result-file-name">${escapeHtml(fileName)}</p>
                    <div class="result-file-actions">
                        ${isPdb ? `
                            <button class="result-file-actions-btn"
                                data-file-url="${fileUrl}"
                                data-file-name="${escapeHtml(fileName)}"
                                title="상세보기">
                                <i class="fa-solid fa-arrow-up-right-from-square"></i>
                            </button>
                        ` : ''}
                        <button class="result-file-download-btn"
                            data-file-url="${fileUrl}"
                            data-file-name="${escapeHtml(fileName)}"
                            title="다운로드">
                            <i class="fas fa-download"></i>
                        </button>
                    </div>
                </div>
                <div class="result-file-meta">
                    <span class="result-file-type">${escapeHtml(fileType)}</span>
                    <span class="result-file-date">${escapeHtml(fileDate)}</span>
                </div>
            </div>
        `;
    }).join('');

    // 이후 download 버튼 핸들러는 기존 handleResultFileDownload를 사용
    attachResultFileDownloadHandlers();
    attachResultFileDetailHandlers();
}

// Attach result file download handlers
function attachResultFileDownloadHandlers() {
    const downloadBtns = experimentResultFilesList?.querySelectorAll('.result-file-download-btn');
    downloadBtns?.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const fileUrl = btn.getAttribute('data-file-url');
            const fileName = btn.getAttribute('data-file-name');
            await handleResultFileDownload(fileUrl, fileName);
        });
    });
}

// Attach result file detail view handlers (PDB preview)
function attachResultFileDetailHandlers() {
    const detailBtns = experimentResultFilesList?.querySelectorAll('.result-file-actions-btn');
    console.log('[Experiment] Found detail buttons:', detailBtns?.length || 0);
    
    if (!detailBtns || detailBtns.length === 0) {
        console.warn('[Experiment] No detail buttons found');
        return;
    }
    
    detailBtns.forEach(btn => {
        // Remove existing listeners to avoid duplicates
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);
        
        newBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            console.log('[Experiment] Detail button clicked');
            
            // Get file URL and name from data attributes
            const fileUrl = newBtn.getAttribute('data-file-url');
            const fileName = newBtn.getAttribute('data-file-name') || 'PDB 파일';
            
            if (!fileUrl) {
                console.error('[Experiment] File URL not found');
                if (window.notyf) {
                    window.notyf.error('파일 URL을 찾을 수 없습니다.');
                }
                return;
            }
            
            // Open molstar modal
            if (window.MolstarModal && typeof window.MolstarModal.open === 'function') {
                window.MolstarModal.open(fileUrl, fileName);
            } else {
                console.error('[Experiment] MolstarModal is not available');
                if (window.notyf) {
                    window.notyf.error('3D 뷰어를 열 수 없습니다. 페이지를 새로고침해주세요.');
                }
            }
        });
    });
}

// Open experiment result modal with retry logic
function openExperimentResultModalWithRetry(maxAttempts = 20) {
    console.log('[Experiment] Attempting to open modal, attempts left:', maxAttempts);
    console.log('[Experiment] ExperimentResultModal available:', !!window.ExperimentResultModal);
    
    if (window.ExperimentResultModal && typeof window.ExperimentResultModal.open === 'function') {
        console.log('[Experiment] Opening modal...');
        try {
            window.ExperimentResultModal.open();
            console.log('[Experiment] Modal open called successfully');
        } catch (error) {
            console.error('[Experiment] Error opening modal:', error);
            if (window.notyf) {
                window.notyf.error('모달을 여는 중 오류가 발생했습니다.');
            }
        }
        return;
    }
    
    // Retry if modal is not ready yet
    if (maxAttempts > 0) {
        setTimeout(() => {
            openExperimentResultModalWithRetry(maxAttempts - 1);
        }, 100);
    } else {
        console.error('[Experiment] ExperimentResultModal is not available after waiting');
        console.error('[Experiment] window.ExperimentResultModal:', window.ExperimentResultModal);
        if (window.notyf) {
            window.notyf.error('실험 결과 모달을 열 수 없습니다. 페이지를 새로고침해주세요.');
        }
    }
}

// Open file in new tab for quick preview
function handleResultFileView(fileUrl) {
    if (!fileUrl) {
        window.notyf?.error('보기 URL이 없습니다.');
        return;
    }
    window.open(fileUrl, '_blank', 'noopener,noreferrer');
}

// Handle result file download - open the file_path directly
async function handleResultFileDownload(fileUrl, fileName) {
    if (!fileUrl) {
        if (window.notyf) {
            window.notyf.error('다운로드 URL이 제공되지 않았습니다.');
        }
        return;
    }

    try {
        const link = document.createElement('a');
        link.href = fileUrl;              // 실제 file_path (S3 등)
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        if (fileName) {
            link.download = fileName;     // 확장자 포함 파일명 지정 가능
        }
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        if (window.notyf) {
            window.notyf.success('다운로드가 완료되었습니다.');
        }
    } catch (error) {
        console.error('Error starting download:', error);
        if (window.notyf) {
            window.notyf.error('파일 다운로드를 시작하지 못했습니다.');
        }
    }
}

// 원본코드
// async function handleResultFileDownload(fileUrl, fileName) {
//     if (!fileUrl) {
//         if (window.notyf) {
//             window.notyf.error('다운로드 URL이 없습니다.');
//         }
//         return;
//     }

//     try {
//         const response = await fetch(fileUrl, {
//             method: 'GET',
//             headers: {
//                 'X-CSRFToken': getCsrfToken(),
//             },
//         });

//         if (response.ok) {
//             // Get blob from response
//             const blob = await response.blob();
            
//             // Create download link
//             const url = window.URL.createObjectURL(blob);
//             const link = document.createElement('a');
//             link.href = url;
            
//             // Get filename from Content-Disposition header or use provided name
//             const contentDisposition = response.headers.get('Content-Disposition');
//             let downloadFileName = fileName;
//             if (contentDisposition) {
//                 const fileNameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
//                 if (fileNameMatch && fileNameMatch[1]) {
//                     downloadFileName = fileNameMatch[1].replace(/['"]/g, '');
//                 }
//             }
            
//             link.download = downloadFileName;
//             document.body.appendChild(link);
//             link.click();
//             document.body.removeChild(link);
//             window.URL.revokeObjectURL(url);

//             if (window.notyf) {
//                 window.notyf.success('다운로드를 시작합니다.');
//             }
//         } else {
//             console.error('Failed to download file');
//             if (window.notyf) {
//                 window.notyf.error('파일 다운로드에 실패했습니다.');
//             }
//         }
//     } catch (error) {
//         console.error('Error downloading file:', error);
//         if (window.notyf) {
//             window.notyf.error('파일 다운로드 중 오류가 발생했습니다.');
//         }
//     }
// }



// Show tool guide
function showToolGuide(toolId) {
    const tool = availableTools.find(t => t.id === toolId);
    if (!tool) {
        // Try to find by name if ID doesn't match
        const toolName = toolId;
        const toolByName = availableTools.find(t => t.name === toolName);
        if (toolByName) {
            openToolGuideModal(toolByName);
            return;
        }
        return;
    }

    openToolGuideModal(tool);
}

// Open tool guide modal (extracted for reuse)
function openToolGuideModal(tool) {
    if (!tool) {
        console.error('Tool data not provided');
        return;
    }
    
    // Check if ToolGuideModal is available
    if (window.ToolGuideModal && typeof window.ToolGuideModal.open === 'function') {
        window.ToolGuideModal.open(tool);
        return;
    }
    
    // If not available, try to wait for it to load
    const modal = document.getElementById('toolGuideModal');
    if (!modal) {
        console.error('ToolGuideModal element not found');
        if (window.notyf) {
            window.notyf.error('도구 가이드 모달을 찾을 수 없습니다.');
        }
        return;
    }
    
    // Wait for ToolGuideModal to be available (check multiple times)
    let attempts = 0;
    const maxAttempts = 50; // Increased attempts for slower connections
    let checkInterval = null;
    let eventListenerAdded = false;
    
    // First, try to listen for the ready event
    if (!eventListenerAdded && typeof document !== 'undefined') {
        eventListenerAdded = true;
        const readyHandler = () => {
            if (checkInterval) {
                clearInterval(checkInterval);
            }
            if (window.ToolGuideModal && typeof window.ToolGuideModal.open === 'function') {
                // Ensure modal is initialized before opening
                if (window.ToolGuideModal.init) {
                    window.ToolGuideModal.init();
                }
                window.ToolGuideModal.open(tool);
                document.removeEventListener('toolGuideModalReady', readyHandler);
                return;
            }
        };
        document.addEventListener('toolGuideModalReady', readyHandler, { once: true });
    }
    
    // Also use interval as fallback
    checkInterval = setInterval(() => {
        attempts++;
        if (window.ToolGuideModal && typeof window.ToolGuideModal.open === 'function') {
            clearInterval(checkInterval);
            // Ensure modal is initialized before opening
            if (window.ToolGuideModal.init) {
                window.ToolGuideModal.init();
            }
            window.ToolGuideModal.open(tool);
        } else if (attempts >= maxAttempts) {
            clearInterval(checkInterval);
            console.error('ToolGuideModal not available after waiting. Make sure tool_guide_modal.js is loaded.');
            // Fallback: try to manually open modal if element exists
            if (modal) {
                console.warn('Attempting to manually open modal...');
                // Manually render and show modal as fallback
                manualOpenToolGuideModal(tool, modal);
            } else {
                if (window.notyf) {
                    window.notyf.error('도구 가이드를 불러올 수 없습니다.');
                }
            }
        }
    }, 50); // Check every 50ms (faster checking) // Increase interval to 100ms for better reliability
}

// Fallback function to manually open modal
function manualOpenToolGuideModal(tool, modalElement) {
    if (!modalElement || !tool) return;
    
    // Update title
    const modalTitle = document.getElementById('toolGuideModalTitle');
    const modalSubtitle = document.getElementById('toolGuideModalSubtitle');
    const overviewEl = document.getElementById('toolGuideOverview');
    const usageList = document.getElementById('toolGuideUsageList');
    const tipsEl = document.getElementById('toolGuideTips');
    
    if (modalTitle) modalTitle.textContent = `${tool.name} 사용 가이드`;
    if (modalSubtitle) modalSubtitle.textContent = tool.category || '';
    if (overviewEl) overviewEl.textContent = tool.guide?.overview || tool.description || '';
    if (tipsEl) tipsEl.textContent = tool.guide?.tips || '';
    
    // Render usage steps
    if (usageList && tool.guide?.usage) {
        usageList.innerHTML = tool.guide.usage.map((step, index) => {
            const stepText = step.replace(/^\d+\.\s*/, '');
            return `
                <div class="guide-step">
                    <div class="guide-step-number">${index + 1}</div>
                    <p class="guide-step-text">${escapeHtml(stepText)}</p>
                </div>
            `;
        }).join('');
    }
    
    // Show modal
    modalElement.classList.add('active');
    modalElement.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    
    // Attach close handlers
    const closeBtn = modalElement.querySelector('.modal-close-btn');
    const footerCloseBtn = modalElement.querySelector('[data-action="close"]');
    
    const closeModal = () => {
        modalElement.classList.remove('active');
        modalElement.style.display = 'none';
        document.body.style.overflow = '';
    };
    
    if (closeBtn) {
        closeBtn.onclick = closeModal;
    }
    if (footerCloseBtn) {
        footerCloseBtn.onclick = closeModal;
    }
    
    // Close on overlay click
    modalElement.onclick = (e) => {
        if (e.target === modalElement) {
            closeModal();
        }
    };
}

// Format time ago (matching React format: "2 days ago", "1 day ago", "12 hours ago")
function formatTimeAgo(date) {
    if (!date) return '알 수 없음';
    
    const now = new Date();
    const diff = now - new Date(date);
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    // Match React format more closely
    if (days > 0) {
        if (days === 1) return '1일 전';
        return `${days}일 전`;
    }
    if (hours > 0) {
        if (hours === 1) return '1시간 전';
        return `${hours}시간 전`;
    }
    if (minutes > 0) {
        if (minutes === 1) return '1분 전';
        return `${minutes}분 전`;
    }
    return '방금 전';
}

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

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initExperiment);
} else {
    initExperiment();
}

// Update protein sequence input field (for use by modals)
function updateProteinSequenceInput(sequence) {
    if (proteinSequenceInput) {
        proteinSequenceInput.value = sequence || '';
    }
}

// Setter methods for updating state from external modules
function setSequenceQuery(value) {
    sequenceQuery = value;
}

function setSelectedProtein(value) {
    selectedProtein = value;
}

function setToolOptions(value) {
    toolOptions = value;
}

function setSelectedTools(value) {
    selectedTools = Array.isArray(value) ? [...value] : [];
    selectedTools = getSelectedToolsInOrder().map(t => t.id);
    updateToolCards();
    updatePipelineActions();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ExperimentPage = {
        initExperiment,
        loadAvailableTools,
        loadExperiments,
        toggleToolSelection,
        handleRunSimulation,
        executeSimulation,
        handleClearPipeline,
        handleSearch,
        handleClearSearch,
        handleCopySequence,
        handleProteinDetailClick,
        handleSaveToNote,
        handlePageChange,
        updatePipelineSection,
        renderPipelineVisualization,
        renderPipelineOptions,
        getSelectedToolsInOrder,
        openExperimentResultSidebar,
        closeExperimentResultSidebar,
        updateProteinSequenceInput, // Add method for modals to update input field
        // Setter methods for updating state
        setSequenceQuery,
        setSelectedProtein,
        setToolOptions,
        setSelectedTools,
        // Use getters to always return current values
        get selectedTools() { return selectedTools; },
        get availableTools() { return availableTools; },
        get sequenceQuery() { return sequenceQuery; },
        get toolOptions() { return toolOptions; },
        get selectedProtein() { return selectedProtein; },
    };
}
