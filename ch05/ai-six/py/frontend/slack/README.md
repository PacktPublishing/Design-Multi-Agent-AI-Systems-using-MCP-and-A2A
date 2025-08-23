# AI-6 Slack UI

Integrate the AI-6 bot with Slack to provide a seamless messaging experience.

## Using Slack programmatically

Slack provides an RPC-style API that allows programmatic interaction. It facilitates sending messages, managing channels, and more. The API includes two main groups:

- [Web API](https://docs.slack.dev/apis/web-api/): Interact with and modify Slack workspaces.
- [Event API](https://docs.slack.dev/apis/events-api/): Build apps and bots that respond to Slack activities.

Using the API directly can be complex due to the need to handle HTTP requests, JSON payloads, authentication, retries, rate limiting, and pagination.

To simplify, use the [Bolt library](https://tools.slack.dev/bolt-python/).

Here's what you need to do:

- Generate the [AI-6 Slack app](https://api.slack.com/apps) and configure necessary tokens.
  - [app token](https://api.slack.com/apps/A08J2K4SF44/general) with connections:write scope
  - [bot token](https://api.slack.com/apps/A08J2K4SF44/oauth?) with the needed permissions
- Enable [socket mode](https://app.slack.com/app-settings/T08GRUKRA5Q/A08J2K4SF44/socket-mode) for real-time interaction.
- Subscribe to [message events](https://api.slack.com/apps/event-subscriptions).
- Install the app into your Slack workspace.

## Python Setup

Use a Python virtual environment and ensure all required packages are installed:

```shell
cd /Users/gigi/git/ai-six/py
source venv/bin/activate
pip install -r requirements.txt
```

# Reference

For more detailed documentation, visit:
- [Slack Dev](https://docs.slack.dev/)
- [Slack API Apps](https://api.slack.com/apps)
- [Bolt for Python](https://tools.slack.dev/bolt-python/getting-started)
