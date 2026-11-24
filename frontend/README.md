# Aether Vision frontend

Svelte 5 + Vite dashboard for the Aether Vision backend.

```bash
npm install
npm run dev     # http://localhost:5173, proxies /api to http://127.0.0.1:5803
npm run build   # outputs dist/, served by the backend at /
npm run check   # type-check
```

Set `AETHER_VISION_BACKEND` to proxy to a different backend (e.g. the robot's
coprocessor) during development.

The configuration form is generated from the backend's JSON schemas
(`/api/schema`), so new pipeline settings appear automatically.
