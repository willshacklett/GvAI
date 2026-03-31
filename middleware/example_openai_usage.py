from middleware.openai_compat import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a careful assistant."},
        {"role": "user", "content": "Should we proceed with a risky migration?"},
    ],
    provider="openai",
)

print("Mode:", response.gvai.mode)
print("Blocked:", response.gvai.blocked)
print(response.choices[0].message.content)
