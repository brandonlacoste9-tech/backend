# Python client for MoneyMaker-API

Thin sync client: register, login, summarise.

## Install

**Preferred** – from the backend repo root, install in editable mode:

```bash
cd /path/to/backend
pip install -e "sdk/python[dev]"
```

Then use `from myai_client import MyAIClient, MyAIClientError`. Use `pip install -e sdk/python` if you don't need the dev extras (pytest, requests-mock).

**Without installing** – set `PYTHONPATH` to the repo root and import `from sdk.python import MyAIClient, MyAIClientError`.

## Usage

```python
from myai_client import MyAIClient, MyAIClientError

client = MyAIClient(base_url="http://localhost:8000")

# Register or login
client.register("alice@example.com", "SuperSecret123")
# or: client.login("alice@example.com", "SuperSecret123")

# Summarise (polls until done, returns the summary string)
try:
    summary = client.summarise("Paste your long article or text here...")
    print(summary)
except MyAIClientError as e:
    print("Error:", e)

client.close()
```

Or as a context manager:

```python
with MyAIClient(base_url="http://localhost:8000") as client:
    client.login("alice@example.com", "password")
    print(client.summarise("Your text..."))
```

## Options

- `summarise(text, max_length=80, poll_interval=1.0, timeout=120.0)` – `max_length` is a hint; polling runs every `poll_interval` seconds until `timeout`.
