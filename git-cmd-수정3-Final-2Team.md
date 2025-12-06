# git command
- CMD 창에서 이용
- 내가 작업하는 branch는 항상 확인
- 기본 플로우 :  로컬 작업 후 풀 리퀘스트 -> 리뷰 -> 머지
- 깃-레포지토리-주소 : https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN18-FINAL-2TEAM.git

### 1. 최초 프로젝트 다운로드
- 프로젝트 폴더 생성할 디렉토리로 이동 후 아래 커맨드 실행
```bash
git clone {깃-레포지토리-주소}
```

### 2. 터미널에서 내 레포지토리로 이동 
cd {폴더명}

### 3. 브랜치 확인 (main)
```bash
git branch 
```

### 4. 원격 브랜치까지 전체 확인 (다른 사람이 올린 브랜치)
```bash
git fetch -p
git branch -a
```

#### 5. **내 로컬을 항상 최신으로 유지**
- **(매우 중요!!)** 로컬에서 브랜치를 생성하면, 내 로컬에 있는 **develop** 코드를 기준으로 생성(복제) 되므로 항상 원격에서 PULL 하고 최신을 유지합니다.
```bash
git pull origin develop
```

### 6. 브랜치 규칙 
- **main, develop** : 모든 소스가 모이는 곳, 직접 수정하지 않는다, 삭제 불가
- **staging, production** : 배포 테스트 및 배포 소스 모이는 곳, 직접 수정하지 않는다, 삭제 불가
- **feature/설명** : 기능별로 브랜치 생성 (ex: feature/크롤링-버튼-추가)
- **fix/** : 이미 머지 된 소스 중에 수정해야 할 때 (ex: fix/클래스명-수정, fix/리스트-버그-수정)
- 머지 완료 된 브랜치는 삭제 한다.
- 그 외 브랜치는 관리가 어려워 위의 3가지 **Prefix**를 꼭 이용할 것
- **feature와** **fix** 브랜치는 **develop**에 모으고, 통합 테스트 후에 **main**으로 버지한다
- 중간 배포용 브랜치 **staging** 사용
- 최종 배포용 브랜치 **production** 사용

### 7. 내가 작업할 브랜치 만들고 그 브랜치로 체크아웃 하기
- **현재 브랜치는 develop 브랜치인지 확인**
- **git checkout -b {브랜치명}**
```bash
git checkout -b feature/무슨-기능-만들까
```

### 8. 내 현재 브랜치 항상 확인
```bash
git branch
```

### 9. 코드 작업 시작
- 내 브랜치에서 작업
- 참고 : 보통은 작업하기 전에 이슈 목록에서 작업할 기능/이슈 작성 후 시작
	- https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN18-FINAL-2TEAM/issues

| Label              | 설명                                        |
| ------------------ | ----------------------------------------- |
| `bug`              | 예기치 않은 문제 또는 의도하지 않은 동작을 나타냅니다.           |
| `documentation`    | 설명서 개선 또는 추가가 필요함을 나타냅니다.                 |
| `duplicate`        | 유사한 이슈, 끌어오기 요청 또는 토론을 나타냅니다.             |
| `enhancement`      | 새 기능 요청을 나타냅니다.                           |
| `good first issue` | 최초 기여자에게 적절한 이슈를 나타냅니다.                   |
| `help wanted`      | 유지 관리자가 이슈 또는 끌어오기 요청에 대한 지원을 원함을 나타냅니다.  |
| `invalid`          | 이슈, 끌어오기 요청 또는 토론이 더 이상 관련이 없음을 나타냅니다.    |
| `question`         | 이슈, 끌어오기 요청 또는 토론에 더 많은 정보가 필요함을 나타냅니다.   |
| `wontfix`          | 이슈, 끌어오기 요청 또는 토론에 대한 작업이 계속되지 않음을 나타냅니다. |

### 10. 코드 commit 
- IDE UI 활용
- **[Changes]** / [**Staged Changes]** 구분
- 코드 변경사항 확인
- 커밋 메세지 작성
- **커밋 메시지 룰**
    - 제목과 본문을 한 줄 띄워 분리하기
    - 제목은 영문 기준 50자 이내로
    - 제목 첫 글자를 대문자로
    - 제목 끝에 . (마침표) 금지
    - 제목은 명령문으로
    - 본문은 영문 기준 72자 마다 줄 바꾸기
    - 본문은 어떻게 보다 무엇을, 왜에 맞춰 작성하기
- **커밋 유형**
    - **feat** : 새로운 기능의 추가
    - **fix** : 버그 수정
    - **docs** : 문서 수정
    - **style** : 스타일 관련 기능 (코드 포맷팅, 세미콜론 누락, 코드 자체의 변경이 없는 경우)
    - **refactor**: 코드 리팩토링
    - **test**: 테스트 코드, 리팩토링 테스트 코드 추가
    - **chore**: 빌드 업무 수정, 패키지 매니저 수정 (ex: .gitignore 수정 등)
> 커밋 메세지 예시
	**feat: 글쓰기 버튼 추가**

### 11. git push 
- push 하는 브랜치 항상 확인! 
- ⭐⭐⭐⭐⭐ **main에 push 하지 않는다** ⭐⭐⭐⭐⭐
```bash
git push origin feature/내가-만든-브랜치
```

### 12. Pull Request
- 웹으로 이동 : https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN18-FINAL-2TEAM/pulls
- [Pull Request] 탭으로 이동
- Pull Request 생성
- 우측 [Review] 탭에서, 리뷰 후 main 머지 승인 (관리자 또는 코드 오너)

### 13. 머지 승인 후 로컬 업데이트 ⭐⭐⭐⭐⭐
- develop 코드가 리모트에서 업데이트 되었으므로 -> 로컬 develop 브랜치 pull
- **내 로컬 feature/fix 브랜치 삭제**
- 새로운 브랜치 시작
```bash
### develop 코드 업데이트 확인하기
git checkout develop
git pull origin develop
git branch -D feature/무슨-기능-만들까
# 현재 브랜치 확인
git branch 
```

## 주의 ⭐⭐⭐⭐⭐
- **PR 하고 develop 머지 완료된 내 브랜치는 절대 다시 이용하지 마세요! 로컬에서 삭제할것!**
- **PR 하고 develop 머지 완료된 내 브랜치는 절대 다시 이용하지 마세요! 로컬에서 삭제할것!**
- **PR 하고 develop 머지 완료된 내 브랜치는 절대 다시 이용하지 마세요! 로컬에서 삭제할것!**
- **PR 하고 develop 머지 완료된 내 브랜치는 절대 다시 이용하지 마세요! 로컬에서 삭제할것!**
- **PR 하고 develop 머지 완료된 내 브랜치는 절대 다시 이용하지 마세요! 로컬에서 삭제할것!**

## 머지 전에 코드 테스트

> 다른 사람이 PR 올린 코드를 -> 내 로컬에서 테스트

- `feature/A가-만든-브랜치`
- PR 요청이 올라오면 이상이 없는지 코드 또는 실행 리뷰
- 해당 브랜치를 내 로컬에서 확인하는 방법

1. 현재 내 브랜치 상태 확인 (수정 중이던 코드 있으면 커밋하거나, stash 할 것)  
```bash
git branch
```
    
2. remote에서 받아오기  
```bash
git fetch -p
```
    
3. 해당 브랜치 정보가 받아와졌는지 확인 (빨간색)  
```bash
git branch -a
```
- `remotes/origin/feature/A가-만든-브랜치`

4. 해당 브랜치로 체크아웃 
	- 아직 로컬에 없고 리모트에 있으므로 checkout 옵션 -t 이용
```bash
git checkout -t origin/feature/A가-만든-브랜치
```
    
5. 내 로컬에 브랜치와 코드가 받아졌는지 확인 
```bash
git branch
```
    
6. PR Description 지시 사항 대로 코드 테스트
	- requirements.txt 실행 할 거 있으면 실행

## 참고
- 깃 명령어 치트 시트 : https://education.github.com/git-cheat-sheet-education.pdf



