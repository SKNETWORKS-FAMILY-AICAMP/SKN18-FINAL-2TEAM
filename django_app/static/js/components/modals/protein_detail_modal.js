// Protein Detail Modal JavaScript

const modalId = 'proteinDetailModal';
let currentProtein = null;

// DOM elements
const modal = document.getElementById(modalId);
const modalTitle = document.getElementById('proteinDetailModalTitle');
const modalSubtitle = document.getElementById('proteinDetailModalSubtitle');
const uniProtLink = document.getElementById('proteinUniProtLink');
const downloadFastaBtn = document.getElementById('proteinDownloadFastaBtn');
const copySequenceBtn = document.getElementById('proteinCopySequenceBtn');

// Initialize modal
function initProteinDetailModal() {
    if (!modal) return;

    // Close button
    const closeBtn = modal.querySelector('.modal-close-btn');
    closeBtn?.addEventListener('click', () => closeModal());

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeModal();
        }
    });

    // Download FASTA button
    downloadFastaBtn?.addEventListener('click', handleDownloadFasta);

    // Copy sequence button
    copySequenceBtn?.addEventListener('click', handleCopySequence);

    // Close on footer close button
    const footerCloseBtn = modal.querySelector('[data-action="close"]');
    footerCloseBtn?.addEventListener('click', () => closeModal());
}

// Open modal
function openProteinDetailModal(protein) {
    if (!modal || !protein) {
        console.error('Modal or protein data not available', { modal, protein });
        return;
    }

    currentProtein = protein;
    
    // Update title
    if (modalTitle) {
        modalTitle.textContent = `${protein.proteinId || ''} · ${protein.proteinName || ''}`;
    }
    if (modalSubtitle) {
        modalSubtitle.textContent = '단백질 상세 정보';
    }

    // Update UniProt link
    if (uniProtLink && protein.proteinId) {
        uniProtLink.href = `https://www.uniprot.org/uniprotkb/${protein.proteinId}/entry`;
    } else if (uniProtLink) {
        uniProtLink.href = '#';
    }

    // Render protein details
    renderProteinDetails(protein);

    // Show modal - use both class and inline style for compatibility
    modal.classList.add('active');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

// Close modal
function closeModal() {
    if (!modal) return;
    
    // Remove active class and hide modal
    modal.classList.remove('active');
    modal.style.display = 'none';
    document.body.style.overflow = '';
    currentProtein = null;
}

// Render protein details
function renderProteinDetails(protein) {
    // Recommended name
    const recommendedNameEl = document.getElementById('proteinRecommendedName');
    if (recommendedNameEl) {
        recommendedNameEl.textContent = protein.recommendedName || protein.description || '';
    }

    // Cleaved chains
    const cleavedChainsContainer = document.getElementById('proteinCleavedChainsContainer');
    const cleavedChainsList = document.getElementById('proteinCleavedChainsList');
    if (protein.cleavedChains && protein.cleavedChains.length > 0) {
        cleavedChainsContainer.style.display = 'block';
        const labelEl = document.getElementById('proteinCleavedChainsLabel');
        if (labelEl) {
            labelEl.textContent = `Cleaved into the following ${protein.cleavedChains.length} chains:`;
        }
        if (cleavedChainsList) {
            cleavedChainsList.innerHTML = protein.cleavedChains.map((chain, index) => 
                `<p class="info-value">${index + 1}. ${escapeHtml(chain)}</p>`
            ).join('');
        }
    } else {
        cleavedChainsContainer.style.display = 'none';
    }

    // Gene
    const geneEl = document.getElementById('proteinGene');
    if (geneEl) {
        geneEl.textContent = protein.gene || '';
    }

    // Taxonomic ID
    const taxonomicIdEl = document.getElementById('proteinTaxonomicId');
    if (taxonomicIdEl) {
        taxonomicIdEl.textContent = protein.taxonomicId || '';
    }

    // Organism
    const organismEl = document.getElementById('proteinOrganism');
    if (organismEl) {
        organismEl.textContent = protein.organism || '';
    }

    // Taxonomic lineage
    const taxonomicLineageEl = document.getElementById('proteinTaxonomicLineage');
    if (taxonomicLineageEl) {
        taxonomicLineageEl.textContent = protein.taxonomicLineage || '';
    }

    // Additional info
    const lengthEl = document.getElementById('proteinLength');
    if (lengthEl) {
        lengthEl.textContent = `${protein.length || 0} amino acids`;
    }

    const evidenceLevelEl = document.getElementById('proteinEvidenceLevel');
    if (evidenceLevelEl) {
        evidenceLevelEl.textContent = protein.evidenceLevel || '';
    }

    const annotationScoreEl = document.getElementById('proteinAnnotationScore');
    if (annotationScoreEl) {
        annotationScoreEl.textContent = `${protein.annotationScore || 0}/5`;
    }

    const descriptionEl = document.getElementById('proteinDescription');
    if (descriptionEl) {
        descriptionEl.textContent = protein.description || '';
    }

    // Tags
    const tagsContainer = document.getElementById('proteinTagsContainer');
    const tagsList = document.getElementById('proteinTagsList');
    if (protein.tags && protein.tags.length > 0) {
        tagsContainer.style.display = 'block';
        if (tagsList) {
            tagsList.innerHTML = protein.tags.map(tag => 
                `<span class="protein-tag">${escapeHtml(tag)}</span>`
            ).join('');
        }
    } else {
        tagsContainer.style.display = 'none';
    }

    // Sequence info
    const sequenceLengthEl = document.getElementById('sequenceLength');
    if (sequenceLengthEl) {
        sequenceLengthEl.textContent = protein.length || 0;
    }

    const sequenceLastUpdatedEl = document.getElementById('sequenceLastUpdated');
    if (sequenceLastUpdatedEl) {
        sequenceLastUpdatedEl.textContent = protein.lastUpdated || '';
    }

    const sequenceMassEl = document.getElementById('sequenceMass');
    if (sequenceMassEl) {
        sequenceMassEl.textContent = protein.mass || '';
    }

    const sequenceMd5El = document.getElementById('sequenceMd5');
    if (sequenceMd5El) {
        sequenceMd5El.textContent = protein.md5Checksum || '';
    }

    // Format and render sequence
    if (protein.sequence) {
        renderFormattedSequence(protein.sequence);
    }
}

// Format sequence with numbers (50 chars per line, 10 chars per group)
function formatSequenceWithNumbers(sequence) {
    const lines = [];
    for (let i = 0; i < sequence.length; i += 50) {
        const lineSequence = sequence.slice(i, i + 50);
        const groups = [];
        for (let j = 0; j < lineSequence.length; j += 10) {
            groups.push(lineSequence.slice(j, j + 10));
        }
        lines.push({
            position: i + 1,
            groups: groups,
        });
    }
    return lines;
}

// Render formatted sequence
function renderFormattedSequence(sequence) {
    const sequenceDisplay = document.getElementById('sequenceDisplay');
    if (!sequenceDisplay) return;

    const formattedLines = formatSequenceWithNumbers(sequence);
    
    sequenceDisplay.innerHTML = formattedLines.map(line => `
        <div class="sequence-line">
            <span class="sequence-position">${line.position}</span>
            <div class="sequence-groups">
                ${line.groups.map(group => `<span class="sequence-group">${escapeHtml(group)}</span>`).join('')}
            </div>
        </div>
    `).join('');
}

// Handle download FASTA - React format: >${protein.proteinId}|${protein.proteinName} ${protein.description}
function handleDownloadFasta() {
    if (!currentProtein || !currentProtein.sequence) {
        if (window.notyf) {
            window.notyf.error('다운로드할 서열이 없습니다.');
        }
        return;
    }

    // Create FASTA format content (React format)
    const proteinId = currentProtein.proteinId || '';
    const proteinName = currentProtein.proteinName || '';
    const description = currentProtein.description || '';
    const fastaContent = `>${proteinId}|${proteinName} ${description}\n${currentProtein.sequence}`;
    
    // Create blob and download
    const blob = new Blob([fastaContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${proteinId}_${proteinName}.fasta`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

// Handle copy sequence - React uses fallback method only
function handleCopySequence() {
    if (!currentProtein || !currentProtein.sequence) {
        if (window.notyf) {
            window.notyf.error('복사할 서열이 없습니다.');
        }
        return;
    }

    // React uses fallback method only (document.execCommand)
    fallbackCopySequence(currentProtein.sequence);
}

// Fallback copy method - React implementation
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
            window.notyf.success('서열이 복사 되었습니다');
        }
    } catch (err) {
        console.error('Failed to copy:', err);
        if (window.notyf) {
            window.notyf.error('서열 복사에 실패했습니다');
        }
    }
    
    document.body.removeChild(textArea);
}

// Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProteinDetailModal);
} else {
    initProteinDetailModal();
}

// Export for use in other modules
if (typeof window !== 'undefined') {
    window.ProteinDetailModal = {
        open: openProteinDetailModal,
        close: closeModal,
        init: initProteinDetailModal,
    };
}
