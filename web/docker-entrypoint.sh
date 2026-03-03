#!/bin/sh
# Write runtime environment variables into the JS file that index.html loads
# before the Vite bundle.  This lets a single pre-built image work against any
# API URL without needing a re-build.
set -e

cat > /usr/share/nginx/html/env-config.js <<EOF
window.__ENV__ = {
  VITE_API_URL: "${VITE_API_URL:-}"
};
EOF

exec nginx -g "daemon off;"
