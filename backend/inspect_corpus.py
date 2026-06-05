import json

with open('db/einstein_manifest.json') as f:
    chunks = json.load(f)

print(f'Total chunks: {len(chunks)}')
print()

sample_indices = [0, 128, 336, 900, 1170]

for i in sample_indices:
    chunk = chunks[i]
    print(f"ID:      {chunk['chunk_id']}")
    print(f"Source:  {chunk['source_title']}")
    print(f"Year:    {chunk['year']}")
    print(f"Words:   {chunk['word_count']}")
    print(f"Preview: {chunk['preview'][:200]}")
    print('-' * 60)