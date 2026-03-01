FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
# Cache the npm registry download cache across builds; only re-runs when
# package.json / package-lock.json change.
RUN --mount=type=cache,target=/root/.npm \
    npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
