# Model Context Protocol (MCP) Reference

Lexard implements the Model Context Protocol (MCP) for integration with AI assistants and agents.

## Overview

The MCP server provides a JSON-RPC 2.0 interface for:
- Document upload and management
- RAG-powered queries
- Document analysis (summarization, risks, comparison)
- Tool discovery

## Endpoint

```
POST http://localhost:8000/mcp
Content-Type: application/json
```

## JSON-RPC 2.0 Format

All requests follow the JSON-RPC 2.0 specification:

```json
{
  "jsonrpc": "2.0",
  "method": "method_name",
  "params": { },
  "id": 1
}
```

## Available Methods

### tools/list

List all available tools.

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "id": 1
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "tools": [
      {
        "name": "upload_document",
        "description": "Upload a document for analysis",
        "inputSchema": {
          "type": "object",
          "properties": {
            "file_path": {
              "type": "string",
              "description": "Path to the file to upload"
            }
          },
          "required": ["file_path"]
        }
      },
      {
        "name": "query_document",
        "description": "Ask a question about a document",
        "inputSchema": {
          "type": "object",
          "properties": {
            "document_id": {
              "type": "string",
              "description": "Document ID"
            },
            "question": {
              "type": "string",
              "description": "Question to ask"
            }
          },
          "required": ["document_id", "question"]
        }
      },
      {
        "name": "summarize_document",
        "description": "Generate a summary of a document",
        "inputSchema": {
          "type": "object",
          "properties": {
            "document_id": {"type": "string"},
            "style": {
              "type": "string",
              "enum": ["executive", "detailed"]
            }
          },
          "required": ["document_id"]
        }
      },
      {
        "name": "analyze_risks",
        "description": "Identify risks in a contract",
        "inputSchema": {
          "type": "object",
          "properties": {
            "document_id": {"type": "string"}
          },
          "required": ["document_id"]
        }
      },
      {
        "name": "compare_documents",
        "description": "Compare two documents",
        "inputSchema": {
          "type": "object",
          "properties": {
            "doc_a": {"type": "string"},
            "doc_b": {"type": "string"}
          },
          "required": ["doc_a", "doc_b"]
        }
      },
      {
        "name": "list_documents",
        "description": "List all uploaded documents",
        "inputSchema": {
          "type": "object",
          "properties": {}
        }
      }
    ]
  },
  "id": 1
}
```

---

### tools/call

Call a specific tool.

#### upload_document

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "upload_document",
    "arguments": {
      "file_path": "/path/to/contract.pdf"
    }
  },
  "id": 2
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Document uploaded successfully:\nID: 550e8400-e29b-41d4-a716-446655440000\nTitle: contract\nPages: 10\nChunks: 45"
      }
    ]
  },
  "id": 2
}
```

---

#### query_document

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "query_document",
    "arguments": {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "question": "What is the termination notice period?"
    }
  },
  "id": 3
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Answer: The termination notice period is 30 days...\n\nConfidence: high\n\nCitations:\n- Page 5, Score 0.89: Either party may terminate with 30 days notice..."
      }
    ]
  },
  "id": 3
}
```

---

#### summarize_document

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "summarize_document",
    "arguments": {
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "style": "executive"
    }
  },
  "id": 4
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Summary: This is a standard NDA...\n\nKey Points:\n- Confidentiality period: 2 years\n- Termination: 30 days notice\n- Jurisdiction: Delaware\n\nWord Count: 1250"
      }
    ]
  },
  "id": 4
}
```

---

#### analyze_risks

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "analyze_risks",
    "arguments": {
      "document_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  "id": 5
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Risk Analysis:\n\nOverall Risk Level: medium\n\n1. [FINANCIAL - HIGH] Unlimited liability clause\n   Page: 3\n   Description: Unlimited liability clause without cap\n   Recommendation: Consider adding a liability cap\n\n2. [LEGAL - MEDIUM] Broad termination clause\n   Page: 5\n   ..."
      }
    ]
  },
  "id": 5
}
```

---

#### compare_documents

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "compare_documents",
    "arguments": {
      "doc_a": "550e8400-e29b-41d4-a716-446655440000",
      "doc_b": "660e8400-e29b-41d4-a716-446655440001"
    }
  },
  "id": 6
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Document Comparison:\n\nOverall Similarity: 82%\n\nDifferences Found:\n\n1. [MODIFIED] Termination (Similarity: 75%)\n   Doc A: 30 days notice required\n   Doc B: 60 days notice required\n\n2. [ADDED] Confidentiality\n   Doc B: Additional confidentiality requirements..."
      }
    ]
  },
  "id": 6
}
```

---

#### list_documents

**Request:**

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "list_documents",
    "arguments": {}
  },
  "id": 7
}
```

**Response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Uploaded Documents:\n\n1. contract (ID: 550e8400-...)\n   Status: processed\n   Pages: 10\n   Chunks: 45\n   Uploaded: 2025-12-05T10:30:00Z\n\n2. nda (ID: 660e8400-...)\n   ..."
      }
    ]
  },
  "id": 7
}
```

---

## Error Responses

Errors follow JSON-RPC 2.0 error format:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32600,
    "message": "Invalid Request",
    "data": {
      "details": "Missing required field: document_id"
    }
  },
  "id": 1
}
```

### Error Codes

| Code    | Meaning            | Description                        |
|---------|--------------------|------------------------------------|
| -32700  | Parse error        | Invalid JSON                       |
| -32600  | Invalid Request    | Missing required fields            |
| -32601  | Method not found   | Unknown method                     |
| -32602  | Invalid params     | Invalid parameter values           |
| -32603  | Internal error     | Server error                       |

---

## Usage with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "lexard": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "http://localhost:8000/mcp",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ]
    }
  }
}
```

Then in Claude Desktop, you can use:

```
Upload the contract at /path/to/contract.pdf and analyze its risks
```

Claude will automatically call the MCP tools.

---

## Example: Complete Workflow

```bash
# 1. List available tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'

# 2. Upload document
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "upload_document",
      "arguments": {"file_path": "/path/to/contract.pdf"}
    },
    "id": 2
  }'

# 3. Query document (use document_id from step 2)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "query_document",
      "arguments": {
        "document_id": "YOUR_DOCUMENT_ID",
        "question": "What are the payment terms?"
      }
    },
    "id": 3
  }'

# 4. Analyze risks
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "analyze_risks",
      "arguments": {"document_id": "YOUR_DOCUMENT_ID"}
    },
    "id": 4
  }'
```

---

## Next Steps

- [API Reference](api.md) - REST API documentation
- [Quickstart Guide](quickstart.md) - Get started quickly
- [Development Guide](development.md) - Development setup
