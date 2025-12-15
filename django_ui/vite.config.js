// vite.config.js
import { defineConfig } from "vite";
import { resolve } from "path";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/static/",
  plugins: [tailwindcss()],
  server: {
    // 개발 서버 설정
    port: 5173,
    strictPort: true,
    cors: true, // Django에서 접근 가능하도록
  },
  build: {
    // 빌드 결과를 바로 Django static 폴더로 보냄
    outDir: "../django_app/static",
    assetsDir: "assets",
    manifest: true,
    emptyOutDir: false, // 다른 static 파일들 지우지 않게

    rollupOptions: {
      input: {
        // 엔트리 이름을 main으로 고정
        main: resolve(__dirname, "src/index.js"),
      },
      output: {
        // npm 라이브러리 빌드 결과물은 js-lib/에 출력
        entryFileNames: "js-lib/[name].js",
        chunkFileNames: "js-lib/[name].js",
        assetFileNames: (assetInfo) => {
          // CSS 파일은 css/style.css로 출력
          if (assetInfo.name && assetInfo.name.endsWith('.css')) {
            return 'css/style.css';
          }
          // 기타 에셋은 assets/에 출력
          return "assets/[name].[ext]";
        },
      },
    },
  },
});
