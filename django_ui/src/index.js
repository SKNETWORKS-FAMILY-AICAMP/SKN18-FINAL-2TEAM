// ============================================
// CSS Imports
// ============================================
import './style.css';
import '@fortawesome/fontawesome-free/css/all.css';
import 'air-datepicker/air-datepicker.css';
import 'notyf/notyf.min.css';
import 'tippy.js/dist/tippy.css';
// CKEditor5 CSS
import 'ckeditor5/ckeditor5.css';
// Tagify CSS
import '@yaireo/tagify/dist/tagify.css';
// fullcalendar v6는 CSS를 자동으로 주입하므로 별도 import 불필요

// ============================================
// JavaScript Library Imports
// ============================================
// fullcalendar v6 - CSS는 자동 주입됨
import { Calendar } from 'fullcalendar';

// sigma - 그래프 라이브러리
import Sigma from 'sigma';

// ckeditor5 - 에디터 (빌드된 버전 사용)
// 주의: ckeditor5 패키지는 소스 코드이므로, 빌드된 버전이 필요할 수 있습니다
// 만약 에러가 나면 @ckeditor/ckeditor5-build-classic 사용 고려
import * as CKEditor from 'ckeditor5';

// air-datepicker - 날짜 선택기
import AirDatepicker from 'air-datepicker';
import localeKo from 'air-datepicker/locale/ko';

// notyf - 알림 라이브러리
import { Notyf } from 'notyf';

// tippy.js - 툴팁
import tippy from 'tippy.js';

// mermaid - 다이어그램
import mermaid from 'mermaid';

// micromodal - 모달
import MicroModal from 'micromodal';

// markdown-it - 마크다운 파서
import MarkdownIt from 'markdown-it';

// graphology - 그래프 라이브러리
import { Graph as GraphologyGraph } from 'graphology';
import { forceAtlas2, circular } from 'graphology-layout';

// clsx - className 유틸리티
import clsx from 'clsx';

// tagify - 태그 입력
import Tagify from '@yaireo/tagify';

// highcharts - 차트 라이브러리
import Highcharts from 'highcharts';

// ============================================
// 전역에서 사용할 수 있도록 window 객체에 할당
// ============================================
window.Calendar = Calendar;
window.Sigma = Sigma;
window.CKEditor = CKEditor;
window.AirDatepicker = AirDatepicker;
window.AirDatepickerLocaleKo = localeKo;
window.Notyf = Notyf;

// 전역 Notyf 인스턴스 생성 (재사용을 위해)
// 이미 초기화되어 있으면 재생성하지 않음
if (typeof window.notyf === 'undefined') {
  window.notyf = new Notyf({
    duration: 3500,
    position: {
      x: 'center',
      y: 'bottom',
    },
    types: [
      {
        type: 'success',
        background: '#10b981',
        icon: {
          className: 'notyf__icon--success',
          tagName: 'i',
        },
      },
      {
        type: 'error',
        background: '#ef4444',
        icon: {
          className: 'notyf__icon--error',
          tagName: 'i',
        },
      },
      {
        type: 'info',
        background: '#3b82f6',
        icon: {
          className: 'notyf__icon--info',
          tagName: 'i',
        },
      },
    ],
  });
  console.log('Notyf initialized successfully');
} else {
  console.log('Notyf already initialized');
}

window.tippy = tippy;
window.mermaid = mermaid;
window.MicroModal = MicroModal;
window.MarkdownIt = MarkdownIt;
window.GraphologyGraph = GraphologyGraph;
window.forceAtlas2 = forceAtlas2;
window.GraphologyLayout = { circular, forceAtlas2 };
window.clsx = clsx;
window.Tagify = Tagify;
window.Highcharts = Highcharts;

// ============================================
// 초기화 코드
// ============================================
document.addEventListener('DOMContentLoaded', () => {
  // Mermaid 초기화는 django_app/static/js/utils/mermaid.js에서 처리
  // (더 세밀한 설정과 자동 렌더링을 위해)

  // MicroModal 초기화
  MicroModal.init();

  // 전역 이벤트 리스너 등록 (필요시)
  console.log('HelixOps UI libraries loaded');
});
