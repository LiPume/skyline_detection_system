#!/bin/bash
# Skyline 系统 Claude Code 专属启动器 (仅当前会话有效)

export ANTHROPIC_BASE_URL="https://code.newcli.com/claude"
export ANTHROPIC_AUTH_TOKEN="sk-ant-oat01-pHo6Dc7Enh4SOqZicVYDjasKZChSgxgiFdG2rGN62C2gfj8PDxEN5OGmW6VFK2vv3Hqi9f86YfgclqpLMjtvWmWCGDPs7AA"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

echo "🟢 API 密钥已局部注入！正在唤醒 Claude Code..."
npx claude
