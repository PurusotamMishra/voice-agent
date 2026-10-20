from langgraph.checkpoint.memory import InMemorySaver

from tests.fakes import FakeCatalog, FakeLLM, FakeNormalizer, make_listing
from voice_agent.catalog.ranker import DEFAULT_WEIGHTS
from voice_agent.domain.enums import AliasKind, BodyType, City, FollowUpField, Fuel, Intent
from voice_agent.domain.models import Filters
from voice_agent.domain.ports import ProviderError, SearchResult
from voice_agent.graph.build import Deps, build_graph
from voice_agent.graph.runner import TurnRunner
from voice_agent.response import templates
from voice_agent.response.validator import EntityVocab
from voice_agent.understanding.schema import ExtractedSlots, Reference, TurnIntent

LISTINGS = [
    make_listing(
        listing_id="A",
        fuel=Fuel.CNG,
        body_type=BodyType.PICKUP,
        city=City.MUMBAI,
        price_inr=450_000,
    ),
    make_listing(
        listing_id="B",
        fuel=Fuel.DIESEL,
        body_type=BodyType.PICKUP,
        city=City.MUMBAI,
        price_inr=480_000,
        payload_kg=1_300,
    ),
    make_listing(
        listing_id="C",
        fuel=Fuel.DIESEL,
        body_type=BodyType.PICKUP,
        city=City.MUMBAI,
        price_inr=520_000,
    ),
]


def runner(llm: FakeLLM) -> TurnRunner:
    deps = Deps(
        llm=llm,
        normalizer=FakeNormalizer({(AliasKind.CITY, "mumbai"): ("mumbai", 1.0)}),
        catalog=FakeCatalog(LISTINGS),
        vocab=EntityVocab(frozenset({"Tata"}), frozenset({"Ace Gold"})),
        neighbors={},
        weights=DEFAULT_WEIGHTS,
        alias_map={k: {} for k in AliasKind},
    )
    return TurnRunner(build_graph(deps, InMemorySaver()), turn_log_path=None)


async def test_search_correction_followup_across_turns() -> None:
    down = ProviderError("fake", "composer offline")  # forces template, keeps test deterministic
    llm = FakeLLM(
        [
            TurnIntent(
                intent=Intent.SEARCH,
                slots=ExtractedSlots(
                    fuel=Fuel.CNG, body_type=BodyType.PICKUP, city_mention="Mumbai"
                ),
            ),
            down,
            TurnIntent(intent=Intent.CORRECT, slots=ExtractedSlots(fuel=Fuel.DIESEL)),
            down,
            TurnIntent(
                intent=Intent.FOLLOW_UP,
                reference=Reference(ordinal=1),
                follow_up_field=FollowUpField.PAYLOAD,
            ),
        ]
    )
    r = runner(llm)
    t1 = await r.run("s1", "CNG pickup in Mumbai under 5 lakh")
    assert t1.filters == {
        "budget_max": 500_000,
        "body_type": "pickup",
        "fuel": "cng",
        "city": "mumbai",
    }
    assert [x.listing.listing_id for x in t1.results] == ["A"] and "template" in t1.fallback_used

    t2 = await r.run("s1", "no, not CNG, diesel")
    assert t2.slot_diff == {"fuel": ["cng", "diesel"]}
    assert [x.listing.listing_id for x in t2.results] == ["B"]  # C is over budget

    t3 = await r.run("s1", "what's its payload")
    assert t3.route == "follow_up" and t3.followup_rank == 1
    assert "1,300 kg" in t3.response_text


async def test_zero_results_offers_relaxation() -> None:
    llm = FakeLLM(
        [
            TurnIntent(
                intent=Intent.SEARCH,
                slots=ExtractedSlots(fuel=Fuel.ELECTRIC, city_mention="Mumbai"),
            )
        ]
    )
    t = await runner(llm).run("s2", "electric in Mumbai")
    assert t.results == [] and t.relaxation is not None and t.relaxation.slot == "fuel"
    assert "couldn't find" in t.response_text


async def test_zero_result_search_clears_stale_results_for_references() -> None:
    down = ProviderError("fake", "composer offline")
    llm = FakeLLM(
        [
            TurnIntent(
                intent=Intent.SEARCH,
                slots=ExtractedSlots(
                    fuel=Fuel.CNG, body_type=BodyType.PICKUP, city_mention="Mumbai"
                ),
            ),
            down,
            TurnIntent(intent=Intent.SEARCH, slots=ExtractedSlots(fuel=Fuel.ELECTRIC)),
            TurnIntent(
                intent=Intent.FOLLOW_UP,
                reference=Reference(ordinal=1),
                follow_up_field=FollowUpField.PRICE,
            ),
        ]
    )
    r = runner(llm)
    assert [x.listing.listing_id for x in (await r.run("s3", "CNG pickup in Mumbai")).results] == [
        "A"
    ]
    assert (await r.run("s3", "make it electric")).results == []
    t3 = await r.run("s3", "tell me about the first one")
    assert t3.route == "which_one" and t3.followup_listing_id is None


class _FlakyCatalog(FakeCatalog):
    """Raises on the first search only (simulates a DB outage)."""

    def __init__(self) -> None:
        super().__init__(LISTINGS)
        self.failed = False

    async def search(self, filters: Filters, limit: int = 500) -> SearchResult:
        if not self.failed:
            self.failed = True
            raise RuntimeError("db down")
        return await super().search(filters, limit)


async def test_component_exception_returns_error_turn_and_session_survives() -> None:
    down = ProviderError("fake", "composer offline")
    intent = TurnIntent(
        intent=Intent.SEARCH,
        slots=ExtractedSlots(fuel=Fuel.CNG, body_type=BodyType.PICKUP, city_mention="Mumbai"),
    )
    deps = Deps(
        llm=FakeLLM([intent, intent, down]),
        normalizer=FakeNormalizer({(AliasKind.CITY, "mumbai"): ("mumbai", 1.0)}),
        catalog=_FlakyCatalog(),
        vocab=EntityVocab(frozenset(), frozenset()),
        neighbors={},
        weights=DEFAULT_WEIGHTS,
        alias_map={k: {} for k in AliasKind},
    )
    r = TurnRunner(build_graph(deps, InMemorySaver()), turn_log_path=None)
    t1 = await r.run("s4", "CNG pickup in Mumbai")
    assert t1.route == "error" and t1.fallback_used == ["error"]
    assert t1.response_text == templates.simple("error").text()
    assert "total" in t1.timings_ms
    t2 = await r.run("s4", "CNG pickup in Mumbai")
    assert t2.route == "search" and [x.listing.listing_id for x in t2.results] == ["A"]


async def test_compose_llm_is_used_for_composition_when_given() -> None:
    extract = FakeLLM(
        [
            TurnIntent(
                intent=Intent.SEARCH,
                slots=ExtractedSlots(
                    fuel=Fuel.CNG, body_type=BodyType.PICKUP, city_mention="Mumbai"
                ),
            )
        ]
    )
    composer = FakeLLM([ProviderError("fake", "composer offline")])
    deps = Deps(
        llm=extract,
        normalizer=FakeNormalizer({(AliasKind.CITY, "mumbai"): ("mumbai", 1.0)}),
        catalog=FakeCatalog(LISTINGS),
        vocab=EntityVocab(frozenset({"Tata"}), frozenset({"Ace Gold"})),
        neighbors={},
        weights=DEFAULT_WEIGHTS,
        alias_map={k: {} for k in AliasKind},
        compose_llm=composer,
    )
    r = TurnRunner(build_graph(deps, InMemorySaver()), turn_log_path=None)
    t = await r.run("s9", "CNG pickup in Mumbai")
    assert t.results and "template" in t.fallback_used  # the composer FakeLLM was the one called
    assert len(composer.calls) == 1  # FakeLLM records each structured() call
    assert len(extract.calls) == 1  # the extractor LLM was not asked to compose
