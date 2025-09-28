import anthropic
from backend.object_model import Tool, Parameter

class Claude(Tool):
    def __init__(self):
        desc = """Send inference requests to Anthropic Claude LLM. Useful for getting a second opinion or 
                  different perspective from another AI model.
        """
        super().__init__(
            name='claude',
            description=desc,
            parameters=[
                Parameter(
                    name='prompt',
                    type='string',
                    description='The prompt or question to send to Claude'),
                Parameter(
                    name='model',
                    type='string',
                    description="""See https://docs.anthropic.com/en/docs/about-claude/models/overview. 
                                   Default is claude-sonnet-4-20250514
                    """),
                Parameter(
                    name='max_tokens',
                    type='integer',
                    description='Maximum number of tokens to generate. Defaults to 1000'),
                Parameter(
                    name='temperature',
                    type='number',
                    description='Temperature for sampling (0.0-1.0). Defaults to 0.7')
            ],
            required={'prompt'}
        )
        self.client = None
    
    def configure(self, config: dict) -> None:
        """Configure the Claude tool with API key."""
        if 'api_key' in config:
            self.client = anthropic.Anthropic(api_key=config['api_key'])
    
    def run(self, **kwargs) -> str:
        if self.client is None:
            return "Error: Claude API key not configured. Set 'api_key' in tool_config for claude tool"
        
        prompt = kwargs['prompt']
        model = kwargs.get('model', 'claude-sonnet-4-20250514')
        max_tokens = kwargs.get('max_tokens', 1000)
        temperature = kwargs.get('temperature', 0.7)

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error calling Claude API: {str(e)}"
