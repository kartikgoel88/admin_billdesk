import json
import sys

from groq import Groq

from commons.utils import Utils

## Run command : python bill_extractor_tesseract.py D:/pycharm/admin_billdesk/resources/commute D:\pycharm\admin_billdesk\src\prompt\system_prompt_cab.txt
## export api key via PS :$env:GROQ_API_KEY="API_KEY"
class Extractor:
    path = sys.argv[1] #"D:/pycharm/admin_billdesk/resources/commute"
    text = Utils.process_folder(path)

    print(text)

    client = Groq()
    file_path = sys.argv[2]

    try:
        with open(file_path, 'r') as file:
            system_prompt = file.read()
        print("system_prompt loaded successfully:")
        print(system_prompt)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    user_prompt = f"""{text}"""

    resp = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0
    )

    output = resp.choices[0].message.content
    print(output)
    data = json.loads(output)

    with open("rides.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


    print("data written to output.json")