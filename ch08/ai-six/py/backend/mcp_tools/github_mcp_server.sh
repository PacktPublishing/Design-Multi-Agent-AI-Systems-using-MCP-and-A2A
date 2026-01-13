#!/bin/bash

# GitHub MCP Server - implements MCP protocol for GitHub CLI tools (newline-stripped JSON responses)

# Helper: output compact JSON from heredoc
emit_json() {
    tr -d '\n' | tr -s ' '
    echo
}

# Read JSON-RPC messages from stdin and respond
while read -r line; do
    method=$(echo "$line" | jq -r '.method' 2>/dev/null)
    id=$(echo "$line" | jq -r '.id' 2>/dev/null)
    params=$(echo "$line" | jq -r '.params' 2>/dev/null)
    
    case "$method" in
        "initialize")
            cat <<EOF | emit_json
{
  "jsonrpc": "2.0",
  "id": $id,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {},
      "resources": {}
    },
    "serverInfo": {
      "name": "GitHub CLI Tools",
      "version": "1.0.0"
    }
  }
}
EOF
            ;;
        "notifications/initialized")
            # Notification - no response needed
            ;;
        "tools/list")
            cat <<EOF | emit_json
{
  "jsonrpc": "2.0",
  "id": $id,
  "result": {
    "tools": [
      {
        "name": "gh",
        "description": "Execute GitHub CLI commands",
        "inputSchema": {
          "type": "object",
          "properties": {
            "args": {
              "type": "string",
              "description": "GitHub CLI command arguments"
            }
          },
          "required": ["args"]
        }
      }
    ]
  }
}
EOF
            ;;
        "tools/call")
            tool_name=$(echo "$params" | jq -r '.name' 2>/dev/null)
            args=$(echo "$params" | jq -r '.arguments.args' 2>/dev/null)

            if [ "$tool_name" = "gh" ]; then
                result=$(gh $args 2>&1)
                exit_code=$?
                escaped=$(echo "$result" | jq -Rs .)

                cat <<EOF | emit_json
{
  "jsonrpc": "2.0",
  "id": $id,
  "result": {
    "content": [
      {
        "type": "text",
        "text": $escaped
      }
    ]
  }
}
EOF
            else
                cat <<EOF | emit_json
{
  "jsonrpc": "2.0",
  "id": $id,
  "error": {
    "code": -32602,
    "message": "Unknown tool: $tool_name"
  }
}
EOF
            fi
            ;;
        *)
            if [ "$id" != "null" ]; then
                cat <<EOF | emit_json
{
  "jsonrpc": "2.0",
  "id": $id,
  "error": {
    "code": -32601,
    "message": "Method not found: $method"
  }
}
EOF
            fi
            ;;
    esac
done