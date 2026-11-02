FROM node:22.22.0-bookworm-slim AS build
WORKDIR /workspace/portal
COPY portal/package*.json ./
RUN npm ci
COPY portal ./
COPY services/monitor/frontend/src /workspace/services/monitor/frontend/src
COPY services/monitor/frontend/public /workspace/portal/public
COPY services/generator/frontend/src /workspace/services/generator/frontend/src
RUN npm run test:api && npm run build
FROM nginx:1.28-alpine
COPY portal/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/portal/dist /usr/share/nginx/html
RUN chown -R nginx:nginx /var/cache/nginx /var/run /usr/share/nginx/html \
    && touch /var/run/nginx.pid && chown nginx:nginx /var/run/nginx.pid
USER nginx

