from app.memory.store import MemoryStore


def test_memory_save_and_retrieve(tmp_path):
    store = MemoryStore(str(tmp_path / "memory.db"))
    store.save("s1", "topic", "Student likes relativity and clocks", 0.8)

    results = store.retrieve("clocks relativity", "s1")

    assert len(results) == 1
    assert results[0].kind == "topic"

