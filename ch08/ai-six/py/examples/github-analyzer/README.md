# GitHub User Analyzer Agent

This example demonstrates how to create a specialized AI agent that analyzes GitHub user activity and generates
comprehensive reports. The agent uses the GitHub CLI (`gh`) tool to gather information about users, repositories, and
contributions.

## What This Agent Does

The GitHub Analyzer Agent is designed to:

- Analyze any GitHub user's profile and activity
- Generate detailed reports on repositories, contributions, and coding patterns
- Provide insights into a user's technologies, languages, and project involvement
- Answer follow-up questions about the analyzed user

## Setup

**Install GitHub CLI**: Make sure you have `gh` CLI installed**

On Mac:

```bash   
  brew install gh
```

On other platforms, follow the [GitHub CLI installation guide](https://github.com/cli/cli#installation).

**Authenticate with GitHub**: You need to authenticate the `gh` CLI with your GitHub account. Run the following command
and follow the prompts:

```bash   
  gh auth login
```

## Running the Agent

**Run the Agent**: Use `uv run` to execute the analyzer:
```bash
uv run github_analyzer.py <github_username>
```

## Example Session

Here's a short session analyzing the user `the-gigi`:

```bash
$ uv run github_analyzer.py the-gigi

🔍 Starting GitHub analysis for user: the-gigi
==============================================

Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': "api graphql -f query='query ($login: String!) { user(login: $login) { login name bio company location websiteUrl createdAt twitterUsername avatarUrl followers { totalCount } following { totalCount } pinnedItems(first: 6, types: REPOSITORY) { nodes { ... on Repository { nameWithOwner stargazerCount description primaryLanguage { name } } } } repositories(first: 100, ownerAffiliations: OWNER, orderBy: {field: UPDATED_AT, direction: DESC}, privacy: PUBLIC) { totalCount nodes { name nameWithOwner isArchived isFork stargazerCount forkCount updatedAt pushedAt createdAt diskUsage primaryLanguage { name } languages(first: 20, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name } } } licenseInfo { key spdxId name } } } repositoriesContributedTo(first: 100, includeUserRepositories: false, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY], orderBy: {field: STARGAZERS, direction: DESC}) { totalCount nodes { nameWithOwner stargazerCount primaryLanguage { name } isArchived } } starredRepositories(first: 20, orderBy: {field: STARRED_AT, direction: DESC}) { totalCount nodes { nameWithOwner stargazerCount primaryLanguage { name } description } } contributionsCollection { contributionCalendar { totalContributions } totalCommitContributions totalIssueContributions totalPullRequestContributions totalPullRequestReviewContributions restrictedContributionsCount } } }' -F login='the-gigi'"}
Tool gh completed successfully
Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': 'api users/the-gigi/events/public?per_page=300'}
Tool gh completed successfully
Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': 'api users/the-gigi'}
Tool gh completed successfully
Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': 'api users/the-gigi/repos?per_page=100&type=owner&sort=updated'}
Tool gh completed successfully
Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': 'api users/the-gigi/starred?per_page=100'}
Tool gh completed successfully
Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': 'api users/the-gigi/orgs'}
Tool gh completed successfully
Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': 'api users/the-gigi/followers?per_page=1'}
Tool gh completed successfully
Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': 'api users/the-gigi/following?per_page=1'}
Tool gh completed successfully
Invoking tool gh on server /Users/gigi/git/ai-six/py/backend/mcp_tools/github_mcp_server.sh with args: {'args': 'api users/the-gigi/events/public?per_page=300'}
Tool gh completed successfully

User Profile Summary
- Username: the-gigi (Gigi Sayfan)
- Joined: 2012-02-05 (13+ years on GitHub)
- Public repos/gists: 109 repos, 45 gists
- Followers/Following: 109 / 0
- Public orgs: none visible
- Profile details: no bio/location listed; email visible (the.gigi@gmail.com)
- Recent profile activity: active and steadily committing across multiple projects

Repository Analysis
- Most active recently (last 2–3 weeks):
  - Sayfan-AI/ai-six (org repo; Agentic AI focused on ubiquitous tool use)
    - Frequent push activity with agent module refactors, MCP (Model Context Protocol) integration and discovery, GitHub CLI tool in bash, Slack frontend/channel management cleanup, AWS and kubectl tools, CI via GitHub Actions, and multiple version tags (v0.10.0, v0.11.0).
    - Clear push cadence with iterative improvements and tooling additions.
  - PacktPublishing/Design-Multi-Agent-AI-Systems-using-MCP-and-A2A (contributor)
    - Copied "ai-six" (v0.8.0) into chapter 4 and "k8s-ai" into chapter 3; opened an issue to add self as contributor; member event recorded.
  - the-gigi/dotfiles
    - Shell and workflow enhancements (e.g., tagging alias/functions), robustness improvements.
  - the-gigi/quote-service
    - Modernization, dependency bumps, released v1.0.0.
  - the-gigi/gigi-zone
    - Gemini OpenAI compatibility fixes.
  - the-gigi/k8s-ai
    - README fixes and improvements.
- Notable/popular owned repos (by stars)
  - delinkcious (Go) — 71★, 66 forks (A Delicious-like link manager)
  - conman (Python) — 38★, 9 forks (distributed config via etcd)
```

## Configuration

The agent uses a [basic agent configuration](config.yaml) file that includes only the GitHub CLI MCP tool and a detailed
system prompt for
analyzing GitHub users. The configuration file is structured as follows:

```yaml
default_model_id: gpt-5
tools_dirs:
  - ${HOME}/git/ai-six/py/backend/tools
mcp_tools_dirs:
  - ${HOME}/git/ai-six/py/backend/mcp_tools
memory_dir: ${HOME}/git/ai-six/memory/github-analyzer
checkpoint_interval: 3
provider_config:
  openai:
    api_key: ${OPENAI_API_KEY}
enabled_tools:
  - gh
system_prompt: |
  You are a GitHub expert analyst. Your task is to analyze the GitHub user '{username}' 
  and provide a comprehensive report on their activity, contributions, and profile.

  For this analysis, you should:
  1. Get the user's profile information
  2. List their repositories (both owned and contributed to)
  3. Analyze their recent activity and contributions  
  4. Look at their most popular/starred repositories
  5. Check their following/followers if public
  6. Summarize their coding languages and technologies used

  Use the gh CLI tool to gather all necessary information. Structure your final report clearly with:
  - User Profile Summary
  - Repository Analysis  
  - Activity & Contributions
  - Technologies & Languages
  - Key Insights and Observations

  Be thorough but concise in your analysis.
```

## How It Works

1. **Agent Initialization**: Creates an AI agent with a specialized system prompt for GitHub analysis
2. **GitHub CLI Integration**: Uses the `gh` MCP tool to execute GitHub CLI commands
3. **Structured Analysis**: Follows a systematic approach to gather user information
4. **Interactive Session**: Allows follow-up questions for deeper analysis
5. **Memory Persistence**: Maintains conversation history for context

## Customization

You can modify the agent's behavior by:

- Editing the system prompt in `config.yaml`
- Changing the analysis focus areas
- Adding additional tools to the configuration
- Modifying the output format and structure

This example demonstrates how to create domain-specific AI agent with AI-6 that leverage command-line tools for
specialized analysis tasks.
