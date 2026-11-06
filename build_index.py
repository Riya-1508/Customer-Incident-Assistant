import json
import faiss  # library for fast vector search
from sentence_transformers import SentenceTransformer

# Load all tickets from the JSON file
with open("tickets.json", encoding="utf-8") as f:
    tickets = json.load(f)

# Extract just the symptoms text from each ticket
texts = [t["symptoms"] for t in tickets]

# Load a small pre-trained model that converts text into a list of 384 numbers (a vector)
model = SentenceTransformer("all-MiniLM-L6-v2")

# Convert every symptom text into a vector; normalize=True makes similarity scores range 0-1
vectors = model.encode(texts, normalize_embeddings=True)

# Print the shape: (number of tickets, 384) — just a sanity check
print(vectors.shape)

# Create a FAISS index using Inner Product (IP) similarity
# 384 must match the vector size produced by the model above
index = faiss.IndexFlatIP(384)

# Add all ticket vectors into the index so we can search them
index.add(vectors)

def search(query, component=None, top_n=3):
    query_vec = model.encode([query], normalize_embeddings=True)
    scores, ids = index.search(query_vec, 10)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        s = float(score)
        if component and tickets[idx]["component"] == component:
            s += 0.05
        results.append((s, idx))

    results.sort(key=lambda x: x[0], reverse=True)
    return results[:top_n]


if __name__ == "__main__":
    print("\n--- no component filter ---")
    for score, idx in search("PDF shows as binary"):
        t = tickets[idx]
        print(f"  {t['case_number']}  score={round(score, 4)}  [{t['component']}]  {t['short_description']}")

    print("\n--- component='CA-DMS' ---")
    for score, idx in search("PDF shows as binary", component="CA-DMS"):
        t = tickets[idx]
        print(f"  {t['case_number']}  score={round(score, 4)}  [{t['component']}]  {t['short_description']}")
