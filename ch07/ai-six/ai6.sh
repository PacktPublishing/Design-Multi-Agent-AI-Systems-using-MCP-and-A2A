#!/bin/bash

# Change dir to the py directory of AI-6
cd "$(dirname "${BASH_SOURCE[0]}")/py"

# Activate venv if not active already
if [[ -z "$VIRTUAL_ENV" || "$VIRTUAL_ENV" != *"ai-six/py/venv" ]]; then
  source venv/bin/activate
fi

echo "virtualenv: ${VIRTUAL_ENV}"


# Create memory directories if they don't exist
mkdir -p memory/cli memory/slack memory/chainlit

if [[ "$1" == "update" ]]; then
  pip install -r py/requirements.txt
elif [[ "$1" == "cli" ]]; then
  shift  # Drops the first argument ("cli")
  python -m frontend.cli.ai6 "$@"
elif [[ "$1" == "slack" ]]; then
  python -m frontend.slack.app
elif [[ "$1" == "chainlit" ]]; then
  python -m frontend.chainlit.app
elif [[ "$1" == "list-conversations" ]]; then
  # List all conversations in memory
  echo "CLI conversations:"
  ls -1 memory/cli/conversations/ 2>/dev/null | sed 's/\.json$//' || echo "  No conversations found"
  echo
  echo "Slack conversations:"
  ls -1 memory/slack/conversations/ 2>/dev/null | sed 's/\.json$//' || echo "  No conversations found"
  echo
  echo "Chainlit conversations:"
  ls -1 memory/chainlit/conversations/ 2>/dev/null | sed 's/\.json$//' || echo "  No conversations found"
else
  echo 'Usage: ai6.sh <cli | slack | chainlit | list-conversations> [--debug]'
  echo
  echo 'CLI options:'
  echo '  ai6.sh cli                     Start a new conversation'
  echo '  ai6.sh cli -c <conversation>   Continue a specific conversation'
  echo '  ai6.sh cli -l                  List available CLI conversations'
  echo
  echo 'Other commands:'
  echo '  ai6.sh list-conversations      List all conversations across all frontends'
fi
