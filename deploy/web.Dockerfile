FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM node:22-bookworm-slim AS h5-build
WORKDIR /app
COPY frontend-h5/package.json frontend-h5/package-lock.json ./
RUN npm ci
COPY frontend-h5/ ./
RUN npm run build:h5 -- --outDir dist

FROM nginx:1.28-alpine AS frontend
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/dist/ /usr/share/nginx/html/

FROM nginx:1.28-alpine AS h5
COPY --from=h5-build /app/dist/ /usr/share/nginx/html/
