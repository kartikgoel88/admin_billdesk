import sys

from groq import Groq

from commons.llm_utils import LLMUtils
from commons.FileUtils import FileUtils

class Extractor:

    path = sys.argv[1] #"D:/pycharm/admin_billdesk/resources/commute"
    system_prompt_file_path = sys.argv[2]

    receipts = FileUtils.process_folder(path)
    print(receipts)

    client = Groq()

    system_prompt = FileUtils.load_text_file(system_prompt_file_path)
    print(system_prompt)
    user_prompt = f"""{receipts}"""
    model = "llama-3.3-70b-versatile"

    output = LLMUtils.call_llm(client,model,system_prompt,user_prompt,0)
    print(output)
    FileUtils.write_json_to_file(output, "rides.json")