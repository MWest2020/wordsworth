"""person-aggregate-dedupe (step 3 of 4, split from
`detect-dutch-particle-names`, #285)."""
from __future__ import annotations

from wordsworth import person_spans
from wordsworth.keys import InMemoryKeyProvider
from wordsworth.mapping_store import InMemoryMappingStore
from wordsworth.openanonymiser_driver import Entity
from wordsworth.pseudonymizer import ReversibleAnonymizer


def _person(text: str, start: int = 0) -> Entity:
    return Entity("PERSON", text, start, start + len(text))


# --- 1. Helper --------------------------------------------------------------


def test_bare_first_name_is_absorbed_into_the_full_name():
    bare = _person("Janine")
    full = _person("Janine van Dijk", start=20)
    assert person_spans.drop_absorbed([bare, full]) == [full]


def test_two_people_with_the_same_first_name_keep_two_rows():
    bare = _person("Janine")
    dijk = _person("Janine van Dijk", start=20)
    groot = _person("Janine de Groot", start=50)
    assert person_spans.drop_absorbed([bare, dijk, groot]) == [dijk, groot]


def test_equal_values_keep_one_row_per_occurrence():
    first = _person("Janine van Dijk", start=0)
    second = _person("Janine van Dijk", start=50)
    assert person_spans.drop_absorbed([first, second]) == [first, second]


def test_jan_is_not_absorbed_into_janine_van_dijk():
    jan = _person("Jan")
    full = _person("Janine van Dijk", start=20)
    assert person_spans.drop_absorbed([jan, full]) == [jan, full]


def test_non_person_label_is_untouched():
    bare = _person("Janine")
    full = _person("Janine van Dijk", start=20)
    location = Entity("LOCATION", "Janine", 80, 86)
    assert person_spans.drop_absorbed([bare, full, location]) == [full, location]


def test_case_and_diacritic_variants_are_not_absorbed():
    lower = _person("janine")
    accented = Entity("PERSON", "Jànine", 30, 36)
    full = _person("Janine van Dijk", start=50)
    assert (person_spans.drop_absorbed([lower, accented, full])
            == [lower, accented, full])


# --- 2. Wiring ---------------------------------------------------------------


def test_reversible_anonymizer_aggregate_counts_a_person_once(monkeypatch):
    text = "Janine van Dijk tekende het besluit. Janine was er zelf bij."

    def stub_detect(body: str) -> list[Entity]:
        full_start = body.index("Janine van Dijk")
        full_end = full_start + len("Janine van Dijk")
        full = Entity("PERSON", "Janine van Dijk", full_start, full_end)
        bare_start = body.index("Janine", full_end)
        bare = Entity("PERSON", "Janine", bare_start, bare_start + len("Janine"))
        return [full, bare]

    # One key provider and mapping store shared by both calls below: the
    # pseudonym token is keyed off the key material, so a fresh provider per
    # call would make the tokens differ even for the same value and defeat
    # the text-equality check that follows.
    keys, store = InMemoryKeyProvider(), InMemoryMappingStore()

    def run() -> object:
        return ReversibleAnonymizer(keys, store, detect=stub_detect).anonymize(text)

    helped = run()
    agg = helped.detections["openanonymiser"]["PERSON"]
    assert agg["count"] == 1

    import wordsworth.pseudonymizer as pseudonymizer_module
    monkeypatch.setattr(pseudonymizer_module.person_spans, "drop_absorbed",
                         lambda entities: entities)
    unhelped = run()
    assert unhelped.text == helped.text  # replacement is unaffected by the helper
    assert unhelped.detections["openanonymiser"]["PERSON"]["count"] == 2
