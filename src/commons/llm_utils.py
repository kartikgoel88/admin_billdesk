from langchain_openai import ChatOpenAI
class LLMUtils:

    @staticmethod
    def call_llm(client,model,system_prompt,user_prompt,temperature):
        #print(system_prompt)
        #print(user_prompt)
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

    @staticmethod
    def call_local_llm(model,system_prompt,user_prompt,temperature):
        llm = ChatOpenAI(
            base_url="http://localhost:12434/engines/llama.cpp/v1",
            api_key="test-key",
            model=model,
            temperature=temperature,
            max_tokens=5000
        )
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        #print("messages->",messages)
        ai_msg = llm.invoke(messages)
        #print("ai_msg->",ai_msg)
        return ai_msg.content

