from retrieval.hybrid import expand_query


def test_expand_query_is_case_insensitive():
    assert "冷静之靴" in expand_query("cd鞋是啥")
    assert "冷静之靴" in expand_query("CD鞋是啥")


def test_expand_query_keeps_official_name_for_bm25():
    expanded = expand_query("名刀·司命的属性是什么")
    assert "名刀·司命" in expanded


def test_expand_query_handles_plain_slang():
    expanded = expand_query("帽子是哪个装备")
    assert "博学者之怒" in expanded
