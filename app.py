import os

import chainlit as cl
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

@cl.on_chat_start
async def init():
    vector_store = FAISS.load_local("docs.faiss", embeddings)

    chain = RetrievalQAWithSourcesChain.from_chain_type(
        ChatOpenAI(temperature=0, streaming=True, model="gpt-4-1106-preview"),
        chain_type="stuff",
        retriever=vector_store.as_retriever(search_kwargs={"k": 7}),
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
