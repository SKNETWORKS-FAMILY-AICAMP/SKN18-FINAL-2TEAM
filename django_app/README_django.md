
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


