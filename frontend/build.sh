#!/bin/sh
# Vercel 빌드 스크립트: 정적 파일을 dist/ 로 복사하고,
# Vercel 환경변수 API_BASE_URL 로 config.js 를 새로 만든다.
# (바닐라 JS는 브라우저에서 환경변수를 직접 읽을 수 없어서, 빌드 시점에 파일로 구워 넣는 방식)
set -e
rm -rf dist
mkdir -p dist
cp index.html style.css app.js demo-data.js dist/
printf 'window.APP_CONFIG = { API_BASE_URL: "%s" };\n' "${API_BASE_URL:-}" > dist/config.js
echo "config.js 생성: API_BASE_URL=${API_BASE_URL:-(비어 있음, 데모 모드)}"
