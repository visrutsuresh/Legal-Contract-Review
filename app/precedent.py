import weaviate
from fastembed import TextEmbedding
from weaviate.classes.config import DataType, Property
from weaviate.classes.query import MetadataQuery

COLLECTION = "Precedent"
RELEVANCE_FLOOR = 60  # below this, a hit is off-topic noise, not precedent

_model = None  # loaded on first use so a plain import stays instant


def embed(text: str) -> list[float]:
    # turn text into 384,numbers that encode what it is about
    global _model
    if _model is None:
        _model = TextEmbedding()  # bge-small-en-v1.5; the first ever call downloads this
    return list(_model.embed([text]))[0].tolist()


def ensure_collection() -> None:
    # create the Precedent drawer if this Weaviate has never seen it
    client = weaviate.connect_to_local(port=8081, grpc_port=50052)
    try:
        if not client.collections.exists(COLLECTION):
            client.collections.create(
                COLLECTION,
                properties=[
                    Property(name="title", data_type=DataType.TEXT),
                    Property(name="content", data_type=DataType.TEXT),
                    Property(name="source", data_type=DataType.TEXT),
                ],
            )
    finally:
        client.close()


def search(query: str, k: int = 5) -> list[dict]:
    client = weaviate.connect_to_local(port=8081, grpc_port=50052)
    try:
        col = client.collections.get(COLLECTION)
        vec = embed(query)
        results = col.query.near_vector(near_vector=vec, limit=k, return_metadata=MetadataQuery(distance=True))
        out = []
        for o in results.objects:
            d = dict(o.properties)
            dist = o.metadata.distance or 0.0
            d["score"] = round((1 - dist / 2) * 100, 1)  # cosine distance to 0..100 relevance
            out.append(d)
        return [h for h in out if h["score"] >= RELEVANCE_FLOOR]
    finally:
        client.close()


def index_reviewed(title: str, content: str) -> None:
    # file one finished review into the cabinet so future reviews can find it
    client = weaviate.connect_to_local(port=8081, grpc_port=50052)
    try:
        col = client.collections.get(COLLECTION)
        col.data.insert(
            properties={"title": title, "content": content, "source": "review"},
            vector=embed(title + ". " + content),
        )
    finally:
        client.close()
