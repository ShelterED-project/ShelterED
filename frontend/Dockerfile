# Етап 1: збірка React + Vite + PWA у папку dist
FROM node:22-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
# API за тим самим доменом через Nginx (/api → backend). Без цього збірка не знає адреси API.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

# Етап 2: роздача зібраної статики через Nginx
FROM nginx:alpine

RUN rm -rf /etc/nginx/conf.d/default.conf /usr/share/nginx/html/*

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY ssl/ /etc/nginx/ssl/
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
