/**
 * Runtime environment variable access.
 *
 * Vite bakes `import.meta.env.*` values into the JS bundle at build time, so a
 * single pre-built image cannot serve different API URLs.  To fix this, the
 * Docker entrypoint writes the real container environment into
 * `/env-config.js` which sets `window.__ENV__` before the bundle executes.
 *
 * Precedence: window.__ENV__ (runtime injection) → import.meta.env (build-time)
 */

declare global {
  interface Window {
    __ENV__?: Record<string, string | undefined>;
  }
}

/** Read an environment variable, preferring the runtime-injected value. */
export function getEnv(key: string): string | undefined {
  return window.__ENV__?.[key] || (import.meta.env[key] as string | undefined) || undefined;
}
