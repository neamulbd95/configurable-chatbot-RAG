from ragchatbot.db.vector_store import passes_access_filter


def test_public_chunk_visible_to_everyone():
    assert passes_access_filter({"access_tags": []}, caller_roles=None) is True
    assert passes_access_filter({}, caller_roles=None) is True
    assert passes_access_filter({"access_tags": []}, caller_roles=["sales"]) is True


def test_restricted_chunk_denied_without_matching_role():
    metadata = {"access_tags": ["sales"]}
    assert passes_access_filter(metadata, caller_roles=None) is False
    assert passes_access_filter(metadata, caller_roles=["support"]) is False


def test_restricted_chunk_allowed_with_matching_role():
    metadata = {"access_tags": ["sales", "finance"]}
    assert passes_access_filter(metadata, caller_roles=["support", "sales"]) is True
