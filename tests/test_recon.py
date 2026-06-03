import pytest

from akirs.db.models import Advertiser
from akirs.recon.base import ReconCoordinator, ReconFindingData, ReconSource
from akirs.recon.registry import build_default_coordinator


class _FakeSource(ReconSource):
    name = "fake"

    def __init__(self, findings, **kw):
        super().__init__(**kw)
        self._findings = findings

    async def _enrich_impl(self, advertiser, session):
        return self._findings


class _ErrorSource(ReconSource):
    name = "error"

    async def _enrich_impl(self, advertiser, session):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_coordinator_merges_findings_from_all_sources(session):
    adv = Advertiser(id=1, fb_url="x", name="X")
    coord = ReconCoordinator(
        sources=[
            _FakeSource([ReconFindingData("a", "k", "v1")]),
            _FakeSource([ReconFindingData("b", "k", "v2"), ReconFindingData("b", "k", "v3")]),
        ]
    )
    findings = await coord.enrich(adv, session)
    assert {f.value for f in findings} == {"v1", "v2", "v3"}


@pytest.mark.asyncio
async def test_source_error_does_not_kill_other_sources(session):
    adv = Advertiser(id=1, fb_url="x", name="X")
    coord = ReconCoordinator(
        sources=[
            _ErrorSource(),
            _FakeSource([ReconFindingData("ok", "k", "v")]),
        ]
    )
    findings = await coord.enrich(adv, session)
    assert [f.value for f in findings] == ["v"]


@pytest.mark.asyncio
async def test_disabled_source_returns_empty(session):
    adv = Advertiser(id=1, fb_url="x", name="X")
    src = _FakeSource([ReconFindingData("a", "k", "v")], enabled=False)
    out = await src.enrich(adv, session)
    assert out == []


def test_default_coordinator_registers_all_five_sources():
    coord = build_default_coordinator()
    names = [s.name for s in coord.sources]
    assert set(names) == {"search", "social", "enrichment", "registry", "warehouse"}
