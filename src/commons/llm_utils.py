class LLMUtils:

    @staticmethod
    def call_llm(client,model,system_prompt,user_prompt,temperature):
        print(system_prompt)
        print(user_prompt)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
        )

        output = resp.choices[0].message.content
        return output

