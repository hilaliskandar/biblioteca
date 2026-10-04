"""Testes do catálogo de programas externos (orientação de submissão na UI)."""

from openalex_review.external_programs import (
    EXTERNAL_PROGRAMS,
    PAGE_BIBLIOMETRICS,
    PAGE_REFERENCE,
    PAGE_SCREENING,
    programs_for_page,
)


def test_all_programs_have_links_and_submission_guidance():
    assert {program.page for program in EXTERNAL_PROGRAMS} == {
        PAGE_SCREENING,
        PAGE_BIBLIOMETRICS,
        PAGE_REFERENCE,
    }
    for program in EXTERNAL_PROGRAMS:
        assert program.name
        assert program.url.startswith("https://")
        assert program.when and program.what and program.where
        if program.secondary_url:
            assert program.secondary_url.startswith("https://")
            assert program.secondary_url_name


def test_programs_for_page_filters_by_page():
    assert tuple(p.name for p in programs_for_page(PAGE_SCREENING)) == ("ASReview",)
    assert tuple(p.name for p in programs_for_page(PAGE_BIBLIOMETRICS)) == ("VOSviewer",)
    assert tuple(p.name for p in programs_for_page(PAGE_REFERENCE)) == ("Zotero",)
    assert programs_for_page("pagina_inexistente") == ()


def test_reference_guidance_references_zotero_export_files():
    program = next(p for p in programs_for_page(PAGE_REFERENCE))
    assert "zotero.org" in program.url
    assert "openalex_deduplicated.ris" in program.what
    assert "openalex_deduplicated.bib" in program.what


def test_asreview_points_to_official_program_site():
    """Guarda contra o domínio errado: asreview.org e um jornal estudantil, nao o programa."""
    program = next(p for p in programs_for_page(PAGE_SCREENING))
    assert program.url == "https://asreview.ai/"


def test_bibliometrics_guidance_names_vosviewer_slots():
    """A orientação deve nomear os slots Map file/Network file para evitar troca."""
    program = next(p for p in programs_for_page(PAGE_BIBLIOMETRICS))
    assert "Map file" in program.what
    assert "Network file" in program.what
    assert "id id intensidade" in program.what
    assert "https://app.vosviewer.com/docs/file-types/map-and-network-file-type/" in program.what


def test_screening_guidance_references_roundtrip_files():
    program = next(p for p in programs_for_page(PAGE_SCREENING))
    # O texto deve orientar o ciclo completo: CSV local para o programa e o
    # CSV rotulado de volta para esta interface.
    assert "openalex_search_results" in program.what
    assert "CSV rotulado" in program.what
