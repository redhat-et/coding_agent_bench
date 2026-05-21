import openai

weather_tool = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a given U.S. city.",
        "parameters": {
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "type": "object",
        },
    },
}

url = "http://gemma4-26b-gemma4-26b.apps.ocp-beta-test.nerc.mghpcc.org/v1"
model = "gemma4-26b"

client = openai.OpenAI(api_key="NONE", base_url=url, timeout=1000000)
response = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": "Use the get_weather tool to get me the weather for Raleigh.",
        }
    ],
    model=model,
    tools=[weather_tool],
)

print("== MESSAGE CONTENT ==")
print(response.choices[0].message.content)
print()

print("== TOOL CALLS ==")
print(response.choices[0].message.tool_calls)
print()
