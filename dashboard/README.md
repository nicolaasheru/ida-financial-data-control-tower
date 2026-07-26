# IDA Financial Data Control Tower dashboard

This Vinext/React dashboard is the analyst-facing layer of an independent
financial-data assurance prototype. It reads synchronized pipeline artifacts
from `public/data/` and connects to the local FastAPI review service when
available.

## Local operation

From the repository root, run:

```bash
bash scripts/run-full-stack.sh
```

The review API defaults to `http://localhost:8000`. Override it for another
environment at build time:

```bash
NEXT_PUBLIC_REVIEW_API_URL=https://example-api.invalid npm run build
```

## Validation

```bash
npm run lint
npm test
```

The product-contract tests verify real project metadata, core rendered
interface content, stable record keys in the published analyst queue, and the
dataset-coverage fields used by the operational status indicator.

## Hosting structure

The Worker, Vinext, Vite, and `.openai/hosting.json` files are retained because
they are part of the current dashboard build and hosting path. Optional
ChatGPT-authentication, D1/Drizzle, and example-database scaffold code has been
removed because the product does not use it.
