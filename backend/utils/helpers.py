from services.llm_service import generate_response


def generate_search_query(user_input: str):
    prompt = f"""give me the array of the [modified text whith includ the keywords/domains for arxiv search,no of papers if not in the input by default return 5] for the following research idea. Return only [string,int] array without any explanation or text.
{user_input}"""
    return generate_response(prompt)