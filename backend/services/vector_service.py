import chromadb
import uuid

client = chromadb.PersistentClient(path="data/chroma")


def get_collection(name):
    return client.get_or_create_collection(name=name)


def add_text_chunks(collection_name, chunks):
    collection = get_collection(collection_name)

    for chunk in chunks:
        collection.add(
            documents=[chunk],
            ids=[str(uuid.uuid4())]
        )


def add_documents(collection_name, docs):
    collection = get_collection(collection_name)

    for doc in docs:
        # Chroma metadata supports scalar values (str/int/float/bool).
        # Convert complex values and remove empty lists/dicts.
        metadata = {}
        for key, value in doc.items():
            if value is None:
                continue

            if isinstance(value, list):
                if not value:
                    continue
                metadata[key] = ", ".join(str(v) for v in value)
                continue

            if isinstance(value, dict):
                if not value:
                    continue
                metadata[key] = str(value)
                continue

            metadata[key] = value

        collection.add(
            documents=[doc.get("summary", "")],
            metadatas=[metadata],
            ids=[str(uuid.uuid4())]
        )


def query_collection(collection_name, query, n_results=5):
    collection = get_collection(collection_name)

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results.get("documents", [[]])[0]
    except:
        return []


def get_all_documents(collection_name):
    collection = get_collection(collection_name)
    return collection.get()
