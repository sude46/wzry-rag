# MCP usage

## Local stdio

```bash
MCP_TRANSPORT=stdio uv run python -m mcp_server.server
```

Example Claude Desktop config (`mcp_config.example.json`):

```json
{
  "mcpServers": {
    "wzry-rag": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "EMBED_API_KEY": "your-key",
        "REDIS_URL": "redis://127.0.0.1:6379/0"
      }
    }
  }
}
```

## Remote SSE

```bash
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8001 uv run python -m mcp_server.server
```

Put authentication/rate limiting in front of the SSE server before exposing it publicly.

## Tools

| Tool | Purpose |
|---|---|
| `search_knowledge(query, k=5, type=None)` | Search the knowledge base |
| `get_hero(name)` | Hero profile, skills and recommended builds |
| `get_item(name)` | Item price, stats and passive |

## Response shape

```json
{
  "doc_id": "equip_1127",
  "subject": "名刀·司命",
  "type": "装备",
  "text": "名刀·司命，攻击类装备，总价2060金币。…",
  "source_url": "https://pvp.qq.com/web201605/item.shtml",
  "score": 0.42
}
```

Always keep `doc_id` and `source_url` when passing results to another agent: they are what makes the answer auditable.
