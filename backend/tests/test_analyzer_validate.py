from app.analyzer.validate import CRITERIA, validate_result


def _imp(**kw):
    item = {"image": 1, "area": "mão esquerda", "problem": "dedos iguais", "fix": "use o Move", "gain": "mais natural",
            "confidence": "alta", "criterion": "anatomia"}
    item.update(kw)
    return item


def _raw(**kw):
    raw = {
        "criteria": {slug: {"score": 6, "why": "ok"} for slug in CRITERIA},
        "strengths": [{"text": "dobras do tecido seguem a gravidade", "image": 1, "area": "capa"}],
        "improvements": [_imp()],
        "reference_comparison": [{"reference": 1, "text": "mechas em 3 níveis"}],
        "top_actions": ["a", "b", "c"],
    }
    raw.update(kw)
    return raw


def _validate(raw, **kw):
    args = {"n_images": 2, "n_references": 3, "has_wireframe": True, "market": "print"}
    args.update(kw)
    return validate_result(raw, **args)


def test_criteria_are_the_nine_of_the_spec_in_order():
    assert list(CRITERIA) == ["anatomia", "silhueta", "detalhe", "pose", "materiais", "render", "apresentacao",
                              "topologia", "imprimibilidade"]


def test_improvement_without_location_or_fix_or_with_wrong_image_is_dropped():
    raw = _raw(improvements=[_imp(area=""), _imp(fix=""), _imp(image=3), _imp(problem="ok")])

    assert [i["problem"] for i in _validate(raw)["improvements"]] == ["ok"]


def test_low_confidence_goes_to_check_list():
    result = _validate(_raw(improvements=[_imp(confidence="baixa", problem="talvez"), _imp()]))

    assert [i["problem"] for i in result["to_check"]] == ["talvez"]
    assert [i["problem"] for i in result["improvements"]] == ["dedos iguais"]


def test_at_most_five_improvements_worst_criterion_first():
    criteria = {slug: {"score": 7, "why": ""} for slug in CRITERIA}
    criteria["pose"] = {"score": 3, "why": ""}
    imps = [_imp(problem=f"p{i}", criterion="detalhe") for i in range(6)] + [_imp(problem="pose ruim", criterion="pose")]

    result = _validate(_raw(criteria=criteria, improvements=imps))

    assert len(result["improvements"]) == 5
    assert result["improvements"][0]["problem"] == "pose ruim"


def test_strength_without_area_dropped_and_max_five():
    strengths = [{"text": "sem lugar", "image": 1, "area": ""}] + [
        {"text": f"forte {i}", "image": 1, "area": "rosto"} for i in range(7)
    ]

    result = _validate(_raw(strengths=strengths))

    assert len(result["strengths"]) == 5
    assert all(s["area"] for s in result["strengths"])


def test_flattery_or_exaggeration_is_flagged_not_hidden():
    result = _validate(_raw(
        strengths=[{"text": "Escultura INCRÍVEL", "image": 1, "area": "rosto"},
                   {"text": "pele com poros visíveis", "image": 1, "area": "rosto"}],
        improvements=[_imp(problem="the hands are perfect but")],
    ))

    assert [s["flagged"] for s in result["strengths"]] == [True, False]
    assert result["improvements"][0]["flagged"] is True


def test_criteria_that_do_not_apply_or_are_out_of_range_become_null():
    criteria = {slug: {"score": 6, "why": ""} for slug in CRITERIA}
    criteria["detalhe"] = {"score": 11, "why": ""}

    result = _validate(_raw(criteria=criteria), has_wireframe=False, market="digital")

    assert result["criteria"]["topologia"]["score"] is None
    assert result["criteria"]["imprimibilidade"]["score"] is None
    assert result["criteria"]["detalhe"]["score"] is None


def test_missing_criterion_is_filled_as_not_evaluable():
    result = _validate(_raw(criteria={"anatomia": {"score": 5, "why": "x"}}))

    assert result["criteria"]["pose"] == {"score": None, "why": ""}


def test_overall_is_the_mean_of_the_scores_not_the_ai_number():
    criteria = {slug: {"score": None, "why": ""} for slug in CRITERIA}
    criteria["anatomia"] = {"score": 5, "why": ""}
    criteria["pose"] = {"score": 8, "why": ""}

    result = _validate(_raw(criteria=criteria, overall=10))

    assert result["overall"] == 6.5


def test_overall_null_when_nothing_could_be_evaluated():
    criteria = {slug: {"score": None, "why": ""} for slug in CRITERIA}

    assert _validate(_raw(criteria=criteria))["overall"] is None


def test_comparison_citing_a_missing_reference_is_dropped():
    result = _validate(_raw(reference_comparison=[{"reference": 4, "text": "x"}, {"reference": 2, "text": "y"}]))

    assert [c["text"] for c in result["reference_comparison"]] == ["y"]


def test_top_actions_fall_back_to_the_first_fixes_and_cap_at_three():
    empty = _validate(_raw(top_actions=[], improvements=[_imp(fix="f1"), _imp(fix="f2")]))
    many = _validate(_raw(top_actions=["1", "2", "3", "4"]))

    assert empty["top_actions"] == ["f1", "f2"]
    assert many["top_actions"] == ["1", "2", "3"]


def test_garbage_types_do_not_crash():
    result = _validate({"criteria": "x", "strengths": None, "improvements": [1, "a"], "top_actions": "a"})

    assert result["improvements"] == []
    assert result["overall"] is None
