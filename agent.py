from langchain.agents.middleware import dynamic_prompt  # now unused but ok if you want to remove later
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
import re

load_dotenv()

# --- Setup embeddings + vector store ---
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_langchain_db",
)

# --- Base model + agent (no retrieval in middleware now) ---
model = init_chat_model("gpt-4.1")
agent = create_agent(model, tools=[])

def get_sections(EK_item: str):
    # 1. Retrieve relevant docs for this specific EK_item
    retrieved_docs = vector_store.similarity_search(EK_item, k=5)

    # 2. Build the context to feed into the model
    docs_content = "\n--NEXT DOCUMENT--\n".join(
        doc.page_content for doc in retrieved_docs
    )

    system_message = (
        "You are an expert in Swedish architectural law. "
        "The user's input is a requirement that may or may not be related to the law paragraphs in the documents below. "
        "Determine whether each of the law paragraph documents relates to the user's input. "
        "Return a list of the relevant document codes. "
        "For example, if an input requirement is related to three documents, you should output something like: "
        "[\"8:41\",\"8:42\",\"7:41\"]"
        "or, for example, if one document:"
        "[\"6:22\"]"
        "If an input does not relate to any of the documents, output:"
        "[]"
        "Always output a valid json string, readable with json.loads()"
        "Here are the documents:\n\n"
        f"{docs_content}"
    )

    # 3. Call the agent with system + user
    result = agent.invoke(
        {
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": EK_item},
            ]
        }
    )

    def extract_prefix(s: str) -> str:
        """
        Return the longest prefix of the string in the form digits:digits (e.g. '8:41').
        If no such prefix exists, return 'Unknown'.
        """
        match = re.match(r'^(\d+:\d+)', s.strip())
        return match.group(1) if match else "Unknown"

    # 4. Return both the model message and the raw retrieved docs for inspection
    return result["messages"][-1].content, dict([(extract_prefix(doc.page_content), doc.page_content) for doc in retrieved_docs])


if __name__ == "__main__":
    msgs, docs = get_sections(
        "Planera för goda för goda förhållanden avseende dagsljus och solljus, i bostaden och på uteplatsen."
    )

    print("MODEL OUTPUT:")
    print(msgs)

    print("\nRETRIEVED DOCS:")
    print(docs)
