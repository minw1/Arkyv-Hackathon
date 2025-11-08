from langchain.agents.middleware import dynamic_prompt, ModelRequest
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
load_dotenv()


embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
vector_store = Chroma(
    collection_name="example_collection",
    embedding_function=embeddings,
    persist_directory="./chroma_langchain_db",  # Where to save data locally, remove if not necessary
)
model = init_chat_model("gpt-4.1")


@dynamic_prompt
def prompt_with_context(request: ModelRequest) -> str:
    """Inject context into state messages."""

    last_query = request.state["messages"][-1].text
    retrieved_docs = vector_store.similarity_search(last_query, k=5)

    docs_content = "\n--NEXT DOCUMENT--\n".join(doc.page_content for doc in retrieved_docs)

    system_message = (
        "You are an expert in Swedish architectural law."
        "The user's input is a requirement that may or may not be related to the law paragraphs in the documents below."
        "Determine whether each of the law paragraph documents relates to the users input."
        "Return a list of the relevant document codes."
        "For example, if an input requirment is related to three documents, you should output something like: ['8:41','8:42','7:41']"
        "If an input does not relate to any of the three documents, output: []"
        f"\n\n{docs_content}"
    )

    return system_message


agent = create_agent(model, tools=[], middleware=[prompt_with_context])
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Planera för goda för goda förhållanden avseende dagsljus och solljus, i bostaden och på uteplatsen."}]}
)
#"Installationer och hissar för bostäder är utformade för en rimlig ljudnivå"
print(result['messages'][-1].content)