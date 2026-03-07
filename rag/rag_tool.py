from rag.search import search_docs

def get_rag_context(query):

    docs = search_docs(query)

    context = "\n\n".join(docs)

    return context