import getpass
import os
import matplotlib.pyplot as plt
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
import pickle
from dotenv import load_dotenv

load_dotenv()
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")


vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_langchain_db",  # Where to save data locally, remove if not necessary
)


with open("chunks.pkl","rb") as file:
    chunks = pickle.load(file)
    chunks = chunks[59:] # skip the table of contents



    docs = [Document(page_content=chunk) for chunk in chunks]
    vector_store.add_documents(documents=docs, ids=[f"id{x}" for x in range(len(docs))])
    print(f"Added {len(docs)} documents to chroma database")
