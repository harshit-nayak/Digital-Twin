from app.scientists import list_scientists, load_scientist


def test_load_five_scientists():
    assert set(list_scientists()) == {"curie", "einstein", "feynman", "newton", "tesla"}
    assert load_scientist("einstein").display_name == "Albert Einstein"

