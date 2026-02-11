# myai-client (Node / TypeScript)

Tiny, type-safe wrapper for the Summarise-as-a-Service API.

## Install

From the `sdk/node` directory (or link from the monorepo root):

```bash
# For dev usage
npm i -D myai-client

# For production
npm i myai-client
```

To install from the repo in editable/link mode, from the **backend repo root**:

```bash
cd sdk/node
npm install
npm run build
```

Then in your app you can `import { MyAIClient } from './sdk/node/dist/index.js'` or add the package to your workspace.

## Quick start

```ts
import { MyAIClient } from 'myai-client'

const client = new MyAIClient({ baseUrl: 'http://localhost:8000' })

await client.register('alice@example.com', 'Secret123')
await client.login('alice@example.com', 'Secret123')

const summary = await client.summarise(
  'OpenAI will launch a new LLM next month…'
)
console.log(summary)
```

## API

- **`client.register(email, password)`** – Register a user and store the JWT.
- **`client.login(email, password)`** – Log in and store the JWT.
- **`client.summarise(text, maxLength?, pollInterval?, timeout?)`** – Submit text, poll until the job completes, return the summary string. Throws `SDKError` on failure or timeout.

  - `maxLength` – Hint (default 80; backend may ignore it).
  - `pollInterval` – Ms between status polls (default 1000).
  - `timeout` – Max ms to wait (default 120_000).

## Demo (ESM)

With the API and Ollama running (e.g. `docker compose up -d`):

```bash
cd sdk/node
npm run build
node --input-type=module -e "
import { MyAIClient } from './dist/index.js'
const client = new MyAIClient({ baseUrl: 'http://localhost:8000' })
await client.login('alice@example.com', 'SuperSecret123')
const summary = await client.summarise('OpenAI will launch a next-gen LLM that doubles the context window…')
console.log('✅ Summary:', summary)
"
```
