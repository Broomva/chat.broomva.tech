import os
from typing import Dict, Optional

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch
# from chainlit import user_session
from langchain.chains import RetrievalQAWithSourcesChain
from langchain.chat_models import ChatOpenAI
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.prompts.chat import (AIMessagePromptTemplate,
                                    ChatPromptTemplate,
                                    HumanMessagePromptTemplate)
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
    print(default_app_user)
    return default_app_user


# @cl.set_chat_profiles
# async def chat_profile(current_user: cl.AppUser):
#     if "admin_user" not in current_user.tags:
#         # Default to 3.5 when not admin
#         return [
#             cl.ChatProfile(
#                 name="GPT-3.5",
#                 markdown_description="The underlying LLM model is **GPT-3.5**.",
#                 icon="https://picsum.photos/200",
#             )
#         ]

#     return [
#         cl.ChatProfile(
#             name="GPT-3.5",
#             markdown_description="The underlying LLM model is **GPT-3.5**.",
#             icon="https://picsum.photos/200",
#         ),
#         cl.ChatProfile(
#             name="GPT-4",
#             markdown_description="The underlying LLM model is **GPT-4**.",
#             icon="https://picsum.photos/250",
#         ),
#     ]


@cl.on_settings_update
async def setup_agent(settings):
    print("on_settings_update", settings)

@cl.on_chat_start
async def init():
    
    settings = await cl.ChatSettings(
        [
            Select(
                id="model",
                label="OpenAI - Model",
                values=["gpt-3.5-turbo", "gpt-3.5-turbo-1106", "gpt-4", "gpt-4-1106-preview"],
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
                initial=3,
                min=1,
                max=20,
                step=1,
            ),
        ]
    ).send()
    
    
    # print(settings)
    # app_user = cl.user_session.get("user")
    # chat_profile = cl.user_session.get("chat_profile")
    # await cl.Message(
    #     content=f"🪼 Starting chat with {app_user.username} using the {chat_profile} chat profile"
    # ).send()

    chain = RetrievalQAWithSourcesChain.from_chain_type(
        ChatOpenAI(temperature=settings['temperature'], streaming=settings['streaming'], model=settings['model']),
        chain_type="stuff",
        retriever=vector_store.as_retriever(search_kwargs={"k": int(settings['k'])}),
    )

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