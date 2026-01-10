/**
 * PubMed Abstract Modal
 * PubMed 논문의 초록을 조회하여 표시하는 모달
 */

const NCPI_API_KEY = '538f83a9cbff5a4db22a4a550be9b267a909';

// 모달 요소
let pubmedAbstractModal = null;
let pubmedAbstractModalCloseBtn = null;
let pubmedAbstractContainer = null;
let pubmedAbstractLoading = null;
let pubmedAbstractContent = null;
let pubmedAbstractText = null;
let pubmedAbstractError = null;
let pubmedAbstractErrorMessage = null;
let pubmedAbstractLink = null;
let pubmedAbstractModalPmid = null;
let pubmedAbstractModalTitleText = null;
let pubmedPaperInfo = null;
let pubmedAbstractModalInitialized = false;

// 초기화
function initPubmedAbstractModal() {
    if (pubmedAbstractModalInitialized) {
        return;
    }

    pubmedAbstractModal = document.getElementById('pubmedAbstractModal');
    if (!pubmedAbstractModal) {
        console.warn('[PubMed Abstract Modal] Modal element not found');
        return;
    }

    pubmedAbstractModalCloseBtn = pubmedAbstractModal.querySelector('.modal-close-btn');
    pubmedAbstractContainer = document.getElementById('pubmedAbstractContainer');
    pubmedAbstractLoading = document.getElementById('pubmedAbstractLoading');
    pubmedAbstractContent = document.getElementById('pubmedAbstractContent');
    pubmedAbstractText = document.getElementById('pubmedAbstractText');
    pubmedAbstractError = document.getElementById('pubmedAbstractError');
    pubmedAbstractErrorMessage = document.getElementById('pubmedAbstractErrorMessage');
    pubmedAbstractLink = document.getElementById('pubmedAbstractLink');
    pubmedAbstractModalPmid = document.getElementById('pubmedAbstractModalPmid');
    pubmedAbstractModalTitleText = document.getElementById('pubmedAbstractModalTitleText');
    pubmedPaperInfo = document.getElementById('pubmedPaperInfo');

    // 닫기 버튼 이벤트
    if (pubmedAbstractModalCloseBtn) {
        pubmedAbstractModalCloseBtn.addEventListener('click', closePubmedAbstractModal);
    }

    // 모달 배경 클릭 시 닫기
    pubmedAbstractModal.addEventListener('click', (e) => {
        if (e.target === pubmedAbstractModal) {
            closePubmedAbstractModal();
        }
    });

    // ESC 키로 닫기
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && pubmedAbstractModal && pubmedAbstractModal.classList.contains('active')) {
            closePubmedAbstractModal();
        }
    });

    // Footer 버튼 이벤트
    const footerCloseBtn = pubmedAbstractModal.querySelector('.modal-footer button[data-action="close"]');
    if (footerCloseBtn) {
        footerCloseBtn.addEventListener('click', closePubmedAbstractModal);
    }

    pubmedAbstractModalInitialized = true;
    console.log('[PubMed Abstract Modal] Initialized');
}

// 모달 열기
function openPubmedAbstractModal(pmid, title = null) {
    console.log('[PubMed Abstract Modal] openPubmedAbstractModal called with PMID:', pmid, 'Title:', title);
    console.log('[PubMed Abstract Modal] pubmedAbstractModal:', pubmedAbstractModal);
    
    // 모달이 아직 초기화되지 않았으면 초기화 시도
    if (!pubmedAbstractModalInitialized || !pubmedAbstractModal) {
        console.log('[PubMed Abstract Modal] Initializing modal...');
        initPubmedAbstractModal();
        pubmedAbstractModal = document.getElementById('pubmedAbstractModal');
        if (!pubmedAbstractModal) {
            console.error('[PubMed Abstract Modal] Modal element not found after initialization. Please check if modal HTML is loaded.');
            return;
        }
    }

    if (!pmid) {
        console.warn('[PubMed Abstract Modal] Invalid PMID');
        return;
    }

    // PMID 설정
    if (pubmedAbstractModalPmid) {
        pubmedAbstractModalPmid.textContent = pmid;
    }

    // 논문 정보 섹션 표시/숨김
    if (pubmedPaperInfo) {
        if (title) {
            if (pubmedAbstractModalTitleText) {
                pubmedAbstractModalTitleText.textContent = title;
            }
            pubmedPaperInfo.style.display = 'block';
        } else {
            pubmedPaperInfo.style.display = 'none';
        }
    }

    // 초기 상태로 리셋
    if (pubmedAbstractLoading) pubmedAbstractLoading.style.display = 'flex';
    if (pubmedAbstractContent) pubmedAbstractContent.style.display = 'none';
    if (pubmedAbstractError) pubmedAbstractError.style.display = 'none';
    if (pubmedAbstractLink) {
        pubmedAbstractLink.style.display = 'none';
        pubmedAbstractLink.href = `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
    }

    // 모달 표시 - active 클래스 추가
    pubmedAbstractModal.classList.add('active');
    document.body.style.overflow = 'hidden';
    
    console.log('[PubMed Abstract Modal] Modal should be visible now');

    // 초록 조회
    fetchPubmedAbstract(pmid);
}

// 모달 닫기
function closePubmedAbstractModal() {
    if (!pubmedAbstractModal) return;

    // active 클래스 제거
    pubmedAbstractModal.classList.remove('active');
    document.body.style.overflow = '';

    // 내용 초기화
    if (pubmedAbstractText) pubmedAbstractText.textContent = '';
    if (pubmedAbstractErrorMessage) pubmedAbstractErrorMessage.textContent = '';
    if (pubmedAbstractModalTitleText) pubmedAbstractModalTitleText.textContent = '';
    if (pubmedAbstractModalPmid) pubmedAbstractModalPmid.textContent = '-';
    if (pubmedPaperInfo) pubmedPaperInfo.style.display = 'none';
}

// PubMed 초록 조회
async function fetchPubmedAbstract(pmid) {
    if (!pmid) {
        showPubmedAbstractError('PMID가 제공되지 않았습니다.');
        return;
    }

    try {
        // PubMed E-utilities API 호출
        const baseUrl = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi';
        const params = new URLSearchParams({
            db: 'pubmed',
            id: pmid,
            retmode: 'text',
            rettype: 'abstract',
            api_key: NCPI_API_KEY
        });

        const url = `${baseUrl}?${params.toString()}`;
        
        console.log('[PubMed Abstract Modal] Fetching abstract for PMID:', pmid);

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'text/plain'
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const abstractText = await response.text();
        
        // 텍스트 파싱 및 정제
        const cleanedAbstract = parseAbstractText(abstractText);
        
        if (!cleanedAbstract || cleanedAbstract.trim().length === 0) {
            showPubmedAbstractError('초록 정보를 찾을 수 없습니다.');
            return;
        }

        // 성공적으로 로드된 경우
        showPubmedAbstractContent(cleanedAbstract);

    } catch (error) {
        console.error('[PubMed Abstract Modal] Error fetching abstract:', error);
        showPubmedAbstractError(`초록을 불러오는 중 오류가 발생했습니다: ${error.message}`);
    }
}

// 초록 텍스트 파싱
function parseAbstractText(text) {
    if (!text) return '';

    // "AB  -" 또는 "AB-" 형식으로 시작하는 초록 섹션 추출
    const abstractMatch = text.match(/(?:AB\s*-\s*|ABSTRACT[:\s]+)(.*?)(?=\n\s*[A-Z]{2}\s*-|\n\n|$)/is);
    
    if (abstractMatch && abstractMatch[1]) {
        let abstract = abstractMatch[1].trim();
        
        // 여러 줄의 공백 정리
        abstract = abstract.replace(/\n\s+/g, ' ');
        abstract = abstract.replace(/\s+/g, ' ');
        
        return abstract;
    }

    // 매칭되지 않으면 전체 텍스트에서 의미있는 부분만 추출 시도
    // 일반적으로 초록은 특정 패턴을 따름
    const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    
    // "AB", "ABSTRACT" 등이 포함된 라인부터 시작
    let abstractStartIndex = -1;
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].match(/^(AB|ABSTRACT)[\s-:]/i)) {
            abstractStartIndex = i;
            break;
        }
    }
    
    if (abstractStartIndex >= 0) {
        const abstractLines = lines.slice(abstractStartIndex + 1);
        // 다음 주요 섹션(예: "FAU", "AD", "SO" 등)까지 추출
        const nextSectionIndex = abstractLines.findIndex(line => /^[A-Z]{2}\s*-/.test(line));
        const extractedLines = nextSectionIndex >= 0 
            ? abstractLines.slice(0, nextSectionIndex)
            : abstractLines;
        
        return extractedLines.join(' ').trim();
    }

    // 마지막으로 전체 텍스트 반환 (파싱 실패 시)
    return text.trim();
}

// 초록 내용 표시
function showPubmedAbstractContent(abstractText) {
    if (pubmedAbstractLoading) pubmedAbstractLoading.style.display = 'none';
    if (pubmedAbstractError) pubmedAbstractError.style.display = 'none';
    
    if (pubmedAbstractContent && pubmedAbstractText) {
        pubmedAbstractText.textContent = abstractText;
        pubmedAbstractContent.style.display = 'block';
    }
    
    if (pubmedAbstractLink) {
        pubmedAbstractLink.style.display = 'inline-flex';
    }
}

// 오류 표시
function showPubmedAbstractError(errorMessage) {
    if (pubmedAbstractLoading) pubmedAbstractLoading.style.display = 'none';
    if (pubmedAbstractContent) pubmedAbstractContent.style.display = 'none';
    
    if (pubmedAbstractError && pubmedAbstractErrorMessage) {
        pubmedAbstractErrorMessage.textContent = errorMessage;
        pubmedAbstractError.style.display = 'flex';
    }
}

// 전역 함수로 export
window.openPubmedAbstractModal = openPubmedAbstractModal;
window.closePubmedAbstractModal = closePubmedAbstractModal;

// DOM 로드 시 초기화
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPubmedAbstractModal);
} else {
    initPubmedAbstractModal();
}

