# 모달 컴포넌트 사용 가이드

## 폴더 구조

```text
django_app/
├── templates/
│   └── components/
│       └── modals/
│           ├── bookmark_modal.html
│           ├── calendar_add_modal.html
│           ├── experiment_result_modal.html
│           ├── feedback_modal.html
│           ├── google_calendar_modal.html
│           ├── graph_create_modal.html
│           ├── graph_summary_modal.html
│           ├── paper_graph_modal.html
│           ├── protein_detail_modal.html
│           ├── reference_selection_modal.html
│           ├── save_to_note_modal.html
│           ├── schedule_add_modal.html
│           ├── schedule_detail_modal.html
│           ├── sequence_input_modal.html
│           ├── settings_modal.html
│           ├── share_modal.html
│           ├── simulation_confirm_modal.html
│           ├── table_modal.html
│           ├── tool_guide_modal.html
│           └── tool_options_modal.html
└── static/
    ├── css/
    │   └── components/
    │       └── modals/
    │           ├── modal.css                      # 공통 모달 스타일
    │           ├── bookmark_modal.css
    │           ├── calendar_add_modal.css
    │           ├── experiment_result_modal.css
    │           ├── feedback_modal.css
    │           ├── google_calendar_modal.css
    │           ├── graph_create_modal.css
    │           ├── graph_summary_modal.css
    │           ├── paper_graph_modal.css
    │           ├── protein_detail_modal.css
    │           ├── reference_selection_modal.css
    │           ├── save_to_note_modal.css
    │           ├── schedule_add_modal.css
    │           ├── schedule_detail_modal.css
    │           ├── sequence_input_modal.css
    │           ├── settings_modal.css
    │           ├── share_modal.css
    │           ├── simulation_confirm_modal.css
    │           ├── table_modal.css
    │           ├── tool_guide_modal.css
    │           └── tool_options_modal.css
    └── js/
        └── components/
            └── modals/
                ├── modal.js                       # 공통 모달 유틸리티
                ├── bookmark_modal.js
                ├── calendar_add_modal.js
                ├── experiment_result_modal.js
                ├── feedback_modal.js
                ├── google_calendar_modal.js
                ├── graph_create_modal.js
                ├── graph_summary_modal.js
                ├── paper_graph_modal.js
                ├── protein_detail_modal.js
                ├── reference_selection_modal.js
                ├── save_to_note_modal.js
                ├── schedule_add_modal.js
                ├── schedule_detail_modal.js
                ├── sequence_input_modal.js
                ├── settings_modal.js
                ├── share_modal.js
                ├── simulation_confirm_modal.js
                ├── table_modal.js
                ├── tool_guide_modal.js
                └── tool_options_modal.js
```

## 사용 방법

### 1. 템플릿에 모달 포함

```django
{% extends 'base.html' %}
{% load static %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/components/modals/save_to_note_modal.css' %}">
{% endblock %}

{% block content %}
<!-- 페이지 내용 -->
<button onclick="window.SaveToNoteModal.open()">노트에 저장</button>

<!-- 모달 포함 -->
{% include 'components/modals/save_to_note_modal.html' %}
{% endblock %}

{% block extra_js %}
<script src="{% static 'js/components/modals/save_to_note_modal.js' %}"></script>
{% endblock %}
```

### 2. JavaScript에서 모달 열기/닫기

```javascript
// 모달 열기
window.SaveToNoteModal.open();

// 데이터와 함께 열기
window.PaperGraphModal.open({
    nodes: [...],
    edges: [...]
});

// 모달 닫기
window.SaveToNoteModal.close();
```

### 3. 이벤트 리스너

```javascript
// 저장 이벤트 리스너
document.addEventListener('saveToNote:save', (e) => {
    const { option, noteId, noteName } = e.detail;
    // 저장 로직 처리
});

// 모달 열림/닫힘 이벤트
document.addEventListener('modal:open', (e) => {
    const { modalId } = e.detail;
    console.log(`Modal ${modalId} opened`);
});

document.addEventListener('modal:close', (e) => {
    const { modalId } = e.detail;
    console.log(`Modal ${modalId} closed`);
});
```

## 공통 모달 API

```javascript
// 공통 모달 유틸리티 함수
openModal(modalId, options = {});
closeModal(modalId);

// 전역 객체로 접근
window.Modal = {
    open: openModal,
    close: closeModal
};
```

## 모달 목록

### 1. Bookmark Modal
**설명**: 참고 문헌을 북마크 폴더에 저장하는 모달  
**사용 위치**: `chat/chat.html`  
**Modal ID**: `bookmarkModal`

```javascript
window.BookmarkModal.open();
window.BookmarkModal.close();
```

**이벤트**:
- `bookmark:saved`: 북마크 저장 완료 시 발생

---

### 2. Calendar Add Modal
**설명**: 새로운 캘린더를 추가하는 모달  
**사용 위치**: `schedule/schedule.html`  
**Modal ID**: `calendarAddModal`

```javascript
window.CalendarAddModal.open();
window.CalendarAddModal.close();
```

---

### 3. Experiment Result Modal
**설명**: 실험 결과를 선택하는 모달  
**사용 위치**: `chat/chat.html`  
**Modal ID**: `experimentResultModal`

```javascript
window.ExperimentResultModal.open();
window.ExperimentResultModal.close();
```

---

### 4. Feedback Modal
**설명**: 사용자 피드백을 제출하는 모달  
**사용 위치**: (현재 미사용, 향후 사용 예정)  
**Modal ID**: `feedbackModal`

```javascript
window.FeedbackModal.open();
window.FeedbackModal.close();
```

**이벤트**:
- `feedback:submitted`: 피드백 제출 완료 시 발생

---

### 5. Google Calendar Modal
**설명**: Google Calendar 연동을 관리하는 모달  
**사용 위치**: `schedule/schedule.html`  
**Modal ID**: `googleCalendarModal`

```javascript
window.GoogleCalendarModal.open();
window.GoogleCalendarModal.close();
```

---

### 6. Graph Create Modal
**설명**: 새로운 그래프를 생성하는 모달  
**사용 위치**: `note/note_editor.html`  
**Modal ID**: `graphCreateModal`

```javascript
window.GraphCreateModal.open();
window.GraphCreateModal.close();
```

---

### 7. Graph Summary Modal
**설명**: 그래프 요약 정보를 표시하는 모달  
**사용 위치**: `chat/chat.html`  
**Modal ID**: `graphSummaryModal`

```javascript
window.GraphSummaryModal.open(data);
window.GraphSummaryModal.close();
```

---

### 8. Paper Graph Modal
**설명**: 논문 그래프를 시각화하는 모달  
**사용 위치**: `chat/chat.html`  
**Modal ID**: `paperGraphModal`

```javascript
window.PaperGraphModal.open({
    nodes: [...],
    edges: [...]
});
window.PaperGraphModal.close();
```

---

### 9. Protein Detail Modal
**설명**: 단백질 상세 정보를 표시하는 모달  
**사용 위치**: `experiments/experiment.html`  
**Modal ID**: `proteinDetailModal`

```javascript
window.ProteinDetailModal.open(protein);
window.ProteinDetailModal.close();
```

**파라미터**:
- `protein`: 단백질 정보 객체

---

### 10. Reference Selection Modal
**설명**: 참고 문헌을 선택하는 모달  
**사용 위치**: `chat/chat.html`  
**Modal ID**: `referenceSelectionModal`

```javascript
window.ReferenceSelectionModal.open();
window.ReferenceSelectionModal.close();
```

---

### 11. Save to Note Modal
**설명**: 콘텐츠를 노트에 저장하는 모달  
**사용 위치**: `chat/chat.html`, `experiments/experiment.html`  
**Modal ID**: `saveToNoteModal`

```javascript
window.SaveToNoteModal.open(data);
window.SaveToNoteModal.close();
```

**파라미터**:
- `data`: 저장할 데이터 객체 (선택사항)

**이벤트**:
- `saveToNote:save`: 노트 저장 완료 시 발생
  ```javascript
  {
    option: 'existing' | 'new',
    noteId: number,
    noteName: string
  }
  ```

---

### 12. Schedule Add Modal
**설명**: 새로운 일정을 추가하는 모달  
**사용 위치**: `schedule/schedule.html`  
**Modal ID**: `scheduleAddModal`

```javascript
window.ScheduleAddModal.open(date);
window.ScheduleAddModal.close();
```

**파라미터**:
- `date`: 초기 날짜 (선택사항)

**이벤트**:
- `schedule:created`: 일정 생성 완료 시 발생

---

### 13. Schedule Detail Modal
**설명**: 일정 상세 정보를 표시하는 모달  
**사용 위치**: `schedule/schedule.html`  
**Modal ID**: `scheduleDetailModal`

```javascript
window.ScheduleDetailModal.open(scheduleId);
window.ScheduleDetailModal.close();
```

**파라미터**:
- `scheduleId`: 일정 ID

**이벤트**:
- `schedule:updated`: 일정 업데이트 완료 시 발생
- `schedule:deleted`: 일정 삭제 완료 시 발생

---

### 14. Sequence Input Modal
**설명**: 단백질 서열을 입력하는 모달  
**사용 위치**: `experiments/experiment.html`  
**Modal ID**: `sequenceInputModal`

```javascript
window.SequenceInputModal.open(initialSequence);
window.SequenceInputModal.close();
```

**파라미터**:
- `initialSequence`: 초기 서열 문자열 (선택사항)

**이벤트**:
- `sequence:submitted`: 서열 제출 완료 시 발생

---

### 15. Settings Modal
**설명**: 사용자 설정을 변경하는 모달  
**사용 위치**: (현재 미사용, 향후 사용 예정)  
**Modal ID**: `settingsModal`

```javascript
window.SettingsModal.open();
window.SettingsModal.close();
```

**이벤트**:
- `settings:saved`: 설정 저장 완료 시 발생
  ```javascript
  {
    notifications: boolean,
    // 기타 설정 항목들
  }
  ```

---

### 16. Share Modal
**설명**: 노트나 콘텐츠를 공유하는 모달  
**사용 위치**: `note/note_detail.html`, `note/note_editor.html`  
**Modal ID**: `shareModal`

```javascript
window.ShareModal.open(noteId, orgs, sharedUsers, title);
window.ShareModal.close();
```

**파라미터**:
- `noteId`: 노트 ID
- `orgs`: 조직 목록
- `sharedUsers`: 공유된 사용자 목록
- `title`: 노트 제목

**이벤트**:
- `share:updated`: 공유 설정 업데이트 완료 시 발생

---

### 17. Simulation Confirm Modal
**설명**: 시뮬레이션 실행을 확인하는 모달  
**사용 위치**: `experiments/experiment.html`  
**Modal ID**: `simulationConfirmModal`

```javascript
window.SimulationConfirmModal.open(tools, sequence);
window.SimulationConfirmModal.close();
```

**파라미터**:
- `tools`: 선택된 도구 목록
- `sequence`: 단백질 서열

**이벤트**:
- `simulation:confirmed`: 시뮬레이션 확인 완료 시 발생

---

### 18. Table Modal
**설명**: 표를 추가하는 모달  
**사용 위치**: `chat/chat.html`  
**Modal ID**: `tableModal`

```javascript
window.TableModal.open();
window.TableModal.close();
```

**이벤트**:
- `table:created`: 표 생성 완료 시 발생

---

### 19. Tool Guide Modal
**설명**: 도구 사용 가이드를 표시하는 모달  
**사용 위치**: `experiments/experiment.html`  
**Modal ID**: `toolGuideModal`

```javascript
window.ToolGuideModal.open(tool);
window.ToolGuideModal.close();
```

**파라미터**:
- `tool`: 도구 정보 객체

---

### 20. Tool Options Modal
**설명**: 도구 옵션을 설정하는 모달  
**사용 위치**: `experiments/experiment.html`  
**Modal ID**: `toolOptionsModal`

```javascript
window.ToolOptionsModal.open(tool);
window.ToolOptionsModal.close();
```

**파라미터**:
- `tool`: 도구 정보 객체

**이벤트**:
- `tool:options:updated`: 도구 옵션 업데이트 완료 시 발생

---

## 모달 사용 현황

### Chat 페이지 (`chat/chat.html`)
- Bookmark Modal
- Reference Selection Modal
- Graph Summary Modal
- Paper Graph Modal
- Save to Note Modal
- Table Modal
- Experiment Result Modal

### Schedule 페이지 (`schedule/schedule.html`)
- Schedule Detail Modal
- Schedule Add Modal
- Google Calendar Modal
- Share Modal
- Calendar Add Modal

### Note Detail 페이지 (`note/note_detail.html`)
- Share Modal

### Note Editor 페이지 (`note/note_editor.html`)
- Share Modal
- Graph Create Modal

### Experiment 페이지 (`experiments/experiment.html`)
- Protein Detail Modal
- Sequence Input Modal
- Tool Guide Modal
- Simulation Confirm Modal
- Tool Options Modal
- Save to Note Modal

### 미사용 모달 (향후 사용 예정)
- Feedback Modal
- Settings Modal

---

## 모달 개발 가이드

### 새 모달 추가하기

1. **HTML 템플릿 생성**
   ```html
   {% load static %}
   <div class="modal-overlay" id="myModal" role="dialog" aria-labelledby="myModalTitle" aria-modal="true">
       <div class="modal-container modal-medium">
           <div class="modal-header">
               <h2 class="modal-title" id="myModalTitle">모달 제목</h2>
               <button class="modal-close-btn" aria-label="닫기">
                   <i class="fa-solid fa-times"></i>
               </button>
           </div>
           <div class="modal-body">
               <!-- 모달 내용 -->
           </div>
       </div>
   </div>
   ```

2. **CSS 파일 생성**
   - `django_app/static/css/components/modals/my_modal.css`
   - 공통 스타일은 `common.css`와 `modal.css` 참조

3. **JavaScript 파일 생성**
   ```javascript
   const modalId = 'myModal';
   
   function openMyModal(data = null) {
       openModal(modalId, data);
       // 모달별 초기화 로직
   }
   
   function closeMyModal() {
       closeModal(modalId);
   }
   
   // 전역 객체로 노출
   window.MyModal = {
       open: openMyModal,
       close: closeMyModal
   };
   ```

4. **템플릿에 포함**
   ```django
   {% include 'components/modals/my_modal.html' %}
   ```

5. **CSS/JS 로드**
   ```django
   {% block extra_css %}
   <link rel="stylesheet" href="{% static 'css/components/modals/my_modal.css' %}">
   {% endblock %}
   
   {% block extra_js %}
   <script src="{% static 'js/components/modals/my_modal.js' %}"></script>
   {% endblock %}
   ```

---

## 주의사항

1. **모달 ID는 고유해야 합니다**
2. **공통 모달 스타일은 `common.css`와 `modal.css`를 참조하세요**
3. **접근성을 위해 `role="dialog"`와 `aria-modal="true"`를 포함하세요**
4. **ESC 키로 닫기 기능은 공통 모달 유틸리티에서 자동 처리됩니다**
5. **모달 열림/닫힘 시 body 스크롤은 자동으로 제어됩니다**
