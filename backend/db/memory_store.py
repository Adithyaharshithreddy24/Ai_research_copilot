import uuid
users = {}
chats = {}

def create_user(name: str):
    user_id = str(uuid.uuid4())
    users[user_id] = {"name": name}
    return user_id

def create_chat(user_id: str, title: str):
    chat_id = str(uuid.uuid4())
    chats[chat_id] = {
        "user_id": user_id,
        "title": title,
        "messages": []
    }
    return chat_id

def add_message(chat_id: str, role: str, content: str):
    if chat_id in chats:
        chats[chat_id]["messages"].append({
            "role": role,
            "content": content
        })

def clear_chat(chat_id: str):
    if chat_id in chats:
        chats[chat_id]["messages"] = []