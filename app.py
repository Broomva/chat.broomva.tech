import os
from typing import Dict, Optional

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch
# from chainlit.playground.config import add_llm_provider
# from chainlit.playground.providers.langchain import LangchainGenericProvider
# from chainlit import user_session
from langchain.chains import RetrievalQAWithSourcesChain
from langchain.chat_models import ChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
# from langchain.llms import HuggingFaceHub
# from langchain.prompts.chat import (AIMessagePromptTemplate,
#                                     ChatPromptTemplate,
#                                     HumanMessagePromptTemplate)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
embeddings = OpenAIEmbeddings()
vector_store = FAISS.load_local("docs.faiss", embeddings)


@cl.oauth_callback
def oauth_callback(
    provider_id: str,
    token: str,
    raw_user_data: Dict[str, str],
    default_app_user: cl.AppUser,
) -> Optional[cl.AppUser]:
    # set AppUser tags as regular_user
    match default_app_user.username:
        case "Broomva":
            default_app_user.tags = ["admin_user"]
            default_app_user.role = "ADMIN"
        case _:
            default_app_user.tags = ["regular_user"]
            default_app_user.role = "USER"
    # print(default_app_user)
    return default_app_user


# @cl.header_auth_callback
# def header_auth_callback(headers) -> Optional[cl.AppUser]:
#     # Verify the signature of a token in the header (ex: jwt token)
#     # or check that the value is matching a row from your database
#     # print(headers)
#     if (
#         headers.get("cookie")
#         == "ajs_user_id=5011e946-0d0d-5bd4-a293-65742db98d3d; ajs_anonymous_id=67d2569d-3f50-48f3-beaf-b756286276d9"
#     ):
#         return cl.AppUser(username="Broomva", role="ADMIN", provider="header")
#     else:
#         return None


@cl.password_auth_callback
def auth_callback(
    username: str = "guest", password: str = "guest"
) -> Optional[cl.AppUser]:
    # Fetch the user matching username from your database
    # and compare the hashed password with the value stored in the database
    import hashlib

    # Create a new sha256 hash object
    hash_object = hashlib.sha256()

    # Hash the password
    hash_object.update(password.encode())

    # Get the hexadecimal representation of the hash
    hashed_password = hash_object.hexdigest()

    if (username, hashed_password) == (
        "broomva",
        "b68cacbadaee450b8a8ce2dd44842f1de03ee9993ad97b5e99dea64ef93960ba",
    ):
        return cl.AppUser(username="Broomva", role="OWNER", provider="credentials", tags = ["admin_user"])
    elif (username, password) == ("guest", "guest"):
        return cl.AppUser(username="Guest", role="USER", provider="credentials")
    else:
        return None


@cl.set_chat_profiles
async def chat_profile(current_user: cl.AppUser):
    if "ADMIN" not in current_user.role:
        # Default to 3.5 when not admin
        return [
            cl.ChatProfile(
                name="Broomva Book Agent",
                markdown_description="The underlying LLM model is **GPT-3.5**.",
            ),
        ]

    return [
        cl.ChatProfile(
            name="Broomva Book Agent Lite",
            markdown_description="The underlying LLM model is **GPT-3.5**.",
        ),
        cl.ChatProfile(
            name="Broomva Book Agent Turbo",
            markdown_description="The underlying LLM model is **GPT-4 Turbo**.",
        ),
    ]


@cl.on_settings_update
async def setup_agent(settings):
    print("on_settings_update", settings)


@cl.on_chat_start
async def init():
    cl.AppUser(username="Broomva", role="ADMIN", provider="header")
    settings = await cl.ChatSettings(
        [
            Select(
                id="model",
                label="OpenAI - Model",
                values=[
                    "gpt-3.5-turbo",
                    "gpt-3.5-turbo-1106",
                    "gpt-4",
                    "gpt-4-1106-preview",
                ],
                initial_index=0,
            ),
            Switch(id="streaming", label="OpenAI - Stream Tokens", initial=True),
            Slider(
                id="temperature",
                label="OpenAI - Temperature",
                initial=1,
                min=0,
                max=2,
                step=0.1,
            ),
            Slider(
                id="k",
                label="RAG - Retrieved Documents",
                initial=5,
                min=1,
                max=20,
                step=1,
            ),
        ]
    ).send()

    chat_profile = cl.user_session.get("chat_profile")

    if chat_profile == "Broomva Book Agent Lite":
        settings["model"] = "gpt-3.5-turbo"
    elif chat_profile == "Broomva Book Agent Turbo":
        settings["model"] = "gpt-4-1106-preview"

    chain = RetrievalQAWithSourcesChain.from_chain_type(
        ChatOpenAI(
            temperature=settings["temperature"],
            streaming=settings["streaming"],
            model=settings["model"],
        ),
        chain_type="stuff",
        retriever=vector_store.as_retriever(search_kwargs={"k": int(settings["k"])}),
    )

    cl.user_session.set("settings", settings)
    cl.user_session.set("chain", chain)


@cl.on_message
async def main(message):
    chain = cl.user_session.get("chain")  # type: RetrievalQAWithSourcesChain

    cb = cl.AsyncLangchainCallbackHandler(
        stream_final_answer=True, answer_prefix_tokens=["FINAL", "ANSWER"]
    )
    cb.answer_reached = True

    res = await chain.acall(message.content, callbacks=[cb])

    if cb.has_streamed_final_answer:
        await cb.final_stream.update()
    else:
        answer = res["answer"]
        await cl.Message(
            content=answer,
        ).send()
