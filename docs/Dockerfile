# Stage 1: build the static site with Material for MkDocs
FROM squidfunk/mkdocs-material:9 AS builder

WORKDIR /docs

# Copy project-level mkdocs config
COPY mkdocs.yml /docs/mkdocs.yml

# Copy the docs source
COPY docs/ /docs/docs/

RUN mkdocs build --strict --site-dir /docs/site

# Stage 2: serve the static site with nginx
FROM nginx:alpine

COPY --from=builder /docs/site /usr/share/nginx/html

EXPOSE 80
