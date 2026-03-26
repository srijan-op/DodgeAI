# Build from repository root: docker build -f frontend/Dockerfile .
# Same-origin API: nginx proxies /api → backend (VITE_API_BASE empty at build time)

FROM node:20-alpine AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Relative /api URLs in the browser (nginx reverse proxy)
ENV VITE_API_BASE=

RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
