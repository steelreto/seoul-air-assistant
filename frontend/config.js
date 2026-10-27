// 백엔드 API 주소. 비워 두면 '데모 모드'(예시 데이터, 서버 없이 동작)로 열린다.
// 로컬 개발: "http://127.0.0.1:8000"
// Vercel 배포: 이 파일은 build.sh 가 환경변수 API_BASE_URL 로 덮어쓴다.
window.APP_CONFIG = {
  API_BASE_URL: "http://127.0.0.1:8000"
};
