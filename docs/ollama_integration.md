# Ollama Agent Integration

This document provides comprehensive documentation for integrating and using Ollama agents within the Kingdom AI system.

## Overview

The Ollama integration enables Kingdom AI to leverage local LLM models through the Ollama API, allowing for powerful AI capabilities while maintaining data privacy and control. This integration includes:

- Local LLM model support via Ollama
- Agent management (create, delete, list agents)
- Tool integration for extending agent capabilities
- Event-based architecture for seamless integration

## Prerequisites

1. **Ollama Server**
   - Install Ollama from [ollama.ai](https://ollama.ai/)
   - Start the Ollama server (usually runs on http://localhost:11434)
   - Install desired models (e.g., `ollama pull llama3`)

2. **Python Dependencies**
   - Python 3.10+
   - Dependencies listed in `requirements.txt`

## Configuration

Configure the Ollama integration in your Kingdom AI configuration:

```yaml
# config/kingdom_ai.yaml

ai:
  ollama:
    base_url: "http://localhost:11434"  # Ollama server URL
    default_model: "llama3"             # Default model to use
    timeout: 120                        # Request timeout in seconds
    max_tokens: 4096                    # Maximum tokens to generate
    temperature: 0.7                    # Sampling temperature (0-2)
    top_p: 0.9                         # Nucleus sampling parameter
    max_retries: 3                      # Max retries for API calls
    retry_delay: 1.0                    # Delay between retries in seconds
```

## Usage

### Initializing ThothAI with Ollama Support

```python
from kingdom_ai.core.event_bus import EventBus
from kingdom_ai.ai.thoth_ai import ThothAI

# Create event bus
event_bus = EventBus()

# Initialize ThothAI with Ollama config
thoth_ai = ThothAI(
    event_bus=event_bus,
    config={
        'ollama': {
            'base_url': 'http://localhost:11434',
            'default_model': 'llama3'
        }
    }
)

await thoth_ai.initialize()
```

### Managing Agents

#### Create an Agent

```python
# Create a new agent
agent = await thoth_ai.create_agent(
    name="my_agent",
    instructions="You are a helpful assistant.",
    model="llama3"  # Optional, uses default if not specified
)
```

#### List Available Agents

```python
# Get agent by name
agent = thoth_ai.get_agent("my_agent")

# List all agents
agents = thoth_ai.ollama_agents
print(f"Available agents: {list(agents.keys())}")
```

#### Delete an Agent

```python
success = await thoth_ai.delete_agent("my_agent")
```

### Running Agents

#### Basic Usage

```python
# Run an agent with a prompt
result = await thoth_ai.run_agent(
    agent_name="my_agent",
    input_text="Tell me about quantum computing"
)

if result and result.success:
    print(result.final_output)
```

#### With Tools

```python
from kingdom_ai.ai.ollama_agent import Tool

# Define a custom tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {str(e)}"

# Create an agent with tools
agent = await thoth_ai.create_agent(
    name="calculator",
    instructions="You are a helpful calculator assistant. Use the calculator tool for math problems.",
    tools=[Tool(calculate)]
)

# Run the agent with a math problem
result = await thoth_ai.run_agent(
    agent_name="calculator",
    input_text="What is 123 * 456?"
)

print(result.final_output)
```

## Event System

The integration uses Kingdom AI's event bus for communication. Key events include:

- `ai.agent_created`: When a new agent is created
- `ai.agent_deleted`: When an agent is deleted
- `ai.agent_started`: When an agent starts processing
- `ai.agent_completed`: When an agent finishes processing
- `ai.agents.listed`: When listing available agents
- `ai.error`: When an error occurs

Example of subscribing to events:

```python
async def on_agent_created(event_id: str, data: Dict[str, Any]):
    print(f"Agent created: {data['agent_name']}")

event_bus.subscribe('ai.agent_created', on_agent_created)
```

## Best Practices

1. **Model Selection**: Choose models appropriate for your hardware capabilities
2. **Error Handling**: Always check the `success` flag and handle errors
3. **Resource Management**: Delete unused agents to free resources
4. **Tool Design**: Keep tool implementations simple and focused
5. **Monitoring**: Use the event system to monitor agent activity

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure Ollama server is running
   - Verify the base URL in the configuration

2. **Model Not Found**
   - Check if the model is installed (`ollama list`)
   - Install the model if needed (`ollama pull <model>`)

3. **Performance Issues**
   - Reduce `max_tokens` for faster responses
   - Use smaller models on limited hardware

## License

This integration is part of the Kingdom AI system and is subject to the same licensing terms.

---

For additional support, please refer to the [Kingdom AI documentation](https://docs.kingdomai.com) or contact support.
