import json
from pathlib import Path

def save_messages(path,messages):
    file_path=Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path,"w",encoding="utf-8") as file:
        json.dump(messages,file,ensure_ascii=False,indent=4)

def load_messages(path):
    file_path=Path(path)
    if not file_path.exists():
        return []
    with open(file_path,"r",encoding="utf-8-sig") as file:
        messages=json.load(file)
    return messages

