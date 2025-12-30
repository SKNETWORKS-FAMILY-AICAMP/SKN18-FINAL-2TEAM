
## 폴더 구성
```text
django_app/static/
├── js/                        # HTML 템플릿용 JavaScript
│   ├── components/           # 컴포넌트별 JS
│   │   ├── header.js
│   │   ├── sidebar.js
│   │   └── subsidebar.js
│   ├── pages/               # 페이지별 JS
│   │   ├── dashboard.js
│   │   ├── chat.js
│   │   └── ...
│   └── utils/               # 유틸리티 함수들
│       ├── markdown_message.js
│       └── ...
└── js-lib/                   # npm 라이브러리 빌드 결과물 (Vite)
    ├── main.js              # Vite 빌드 결과물
    ├── chunk-*.js           # Vite 청크 파일들
    └── ...
```

## 주의 (package.json)
- package.json에 라이브러리 추가할 때는 꼭 내용 공유!!!

## 개발 모드 실행
- **Docker 실행 (PostgreSQL 실행)**
```bash
# windows
docker-compose -f infra/docker-compose.yml up -d
# mac
docker compose -f infra/docker-compose.yml up -d
```

- **터미널 1: Vite 개발 서버 실행**
```bash
# 터미널 1: Vite 개발 서버 실행
cd django_ui

# 노트 버전 확인 (node 22+)
node --version

# 설치 한번
npm install
npm run build
```

- **터미널 2: Django 서버 실행**
```bash
python django_app/manage.py makemigrations
python django_app/manage.py migrate

# 관리자 계정 생성 (로그인할 계정 생성)
python django_app/manage.py createsuperuser

# 실행
python django_app/manage.py runserver
```

- **접속**
```url
http://127.0.0.1:8000/
```

- **더미 데이터**
  - **dummy_data.sql** 파일 참고
  - 데이터 미리 insert 후 테스트

## Swagger API 문서

### 접속 URL
- **Swagger UI**: `http://127.0.0.1:8000/api/docs/`
- **ReDoc**: `http://127.0.0.1:8000/api/redoc/`
- **OpenAPI Schema (JSON)**: `http://127.0.0.1:8000/api/schema/`

### 인증 설정

Swagger UI에서 API를 테스트하려면 인증이 필요합니다.

#### 방법 1: 브라우저 세션 쿠키 자동 사용 (권장)
1. 먼저 로그인 페이지에서 로그인
   ```
   http://127.0.0.1:8000/accounts/login/
   ```
2. 로그인 후 Swagger UI 접속
   ```
   http://127.0.0.1:8000/api/docs/
   ```
3. 브라우저가 세션 쿠키를 자동으로 전달하므로 별도 설정 불필요

#### 방법 2: 세션 쿠키 수동 입력
1. 브라우저 개발자 도구 열기 (F12)
2. **Application/Storage** 탭 → **Cookies** → `http://127.0.0.1:8000` 선택
3. `sessionid` 값 복사
4. Swagger UI 우측 상단의 **"Authorize"** 버튼 클릭
5. `sessionid` 필드에 붙여넣기
6. `csrftoken`도 동일하게 복사해 입력 (있는 경우)
7. **"Authorize"** 클릭

### API 엔드포인트

현재 Swagger에 등록된 API:
- `GET /api/notes/` - 노트 목록 조회
- `GET /api/experiments/` - 실험 목록 조회
- `POST /api/experiments/` - 실험 생성

### 주의사항

- **개발 환경**: API 경로(`/api/`)는 CSRF 보호가 우회되도록 설정되어 있습니다
- **프로덕션 환경**: 보안을 위해 CSRF 보호를 다시 활성화해야 합니다
- Swagger UI에서 테스트할 때는 로그인된 상태여야 합니다


