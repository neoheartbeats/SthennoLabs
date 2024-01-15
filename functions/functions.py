# functions.py --- LLM functions

import json
import requests

# Messages are categorized as three types usually:
# System message, user message and assistant messages.


type Message = dict[str, str]
type MessageList = list[Message] | list


def make_message(role: str, content: str) -> Message:
    return {"role": role, "content": content}


def make_message_system(content: str) -> Message:
    return make_message(role="system", content=content)


def make_message_user(content: str) -> Message:
    return make_message(role="user", content=content)


def make_message_assistant(content: str) -> Message:
    return make_message(role="assistant", content=content)


# Any request to LLM should be done by a message list.


def config_llm(
    temperature: float = 0.0,
    max_tokens: int = 800,
) -> dict:
    return {
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def make_request_headers() -> dict:
    return {
        "accept": "application/json",
        "Content-Type": "application/json",
    }


def make_request_data(message_list: MessageList) -> dict:
    return {
        "model": "string",
        "messages": message_list,
        "max_tokens": config_llm()["max_tokens"],
        "temperature": config_llm()["temperature"],
    }


def post_request(source: str, headers: dict, data: dict) -> dict:
    return requests.post(source, headers=headers, data=json.dumps(data)).json()


def get_response_completion(message_list: MessageList) -> str:
    response: dict = post_request(
        source="http://localhost:8000/v1/chat/completions",
        headers=make_request_headers(),
        data=make_request_data(message_list=message_list),
    )
    return response["choices"][0]["message"]["content"]


# It is easy to implement the buffer memory technique from LangChain.


def get_completion_from_buffer(message_list: MessageList, buffer_k: int = 4) -> str:
    return get_response_completion(message_list=message_list[-buffer_k:])


def test_client() -> None:
    message_list: MessageList = []
    for _ in range(6):
        message_list.append(make_message_user(content="你好"))

        # Note it is important to put the user message at the end of the message list.
        output_content = get_completion_from_buffer(message_list=message_list)
        message_list.append(make_message_assistant(content=output_content))
        print(f"message_list: {message_list}")


if __name__ == "__main__":
    test_client()
