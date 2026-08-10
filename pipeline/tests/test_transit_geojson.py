import json
from pathlib import Path

from urbanstack.config import Settings
from urbanstack.metro import MetroConfig
from urbanstack.transit_geojson import _feature_vertices, _keep_servicing_routes

# One square county covering roughly lon -97..-96, lat 32..33.
COUNTIES_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"GEOID": "48001"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-97.0, 32.0],
                        [-96.0, 32.0],
                        [-96.0, 33.0],
                        [-97.0, 33.0],
                        [-97.0, 32.0],
                    ]
                ],
            },
        }
    ],
}

METRO = MetroConfig(
    metro_id="testville",
    metro_name="Testville MSA",
    metro_fips="00000",
    states={"48": {"Test": "001"}},
    center=(32.5, -96.5),
    zoom=9,
    bounds=(32.0, 33.0, -97.0, -96.0),
    transit_agencies={},
)


def _route(agency: str, coords: list[list[float]]) -> dict:
    return {
        "type": "Feature",
        "properties": {"agency": agency, "route_id": f"{agency}-1"},
        "geometry": {"type": "LineString", "coordinates": coords},
    }


def _settings_with_counties(tmp_path: Path) -> Settings:
    web_dir = tmp_path / "web" / "public" / "data" / "testville"
    web_dir.mkdir(parents=True)
    (web_dir / "counties.geojson").write_text(json.dumps(COUNTIES_GEOJSON))
    # web_data_dir resolves as <data_dir>/../../web/public/data/<metro_id>.
    return Settings(data_dir=tmp_path / "pipeline" / "data")


def test_keeps_route_inside_counties(tmp_path: Path) -> None:
    settings = _settings_with_counties(tmp_path)
    inside = _route("Local Transit", [[-96.6, 32.4], [-96.5, 32.5], [-96.4, 32.6]])

    kept = _keep_servicing_routes([inside], settings, METRO)

    assert [f["properties"]["agency"] for f in kept] == ["Local Transit"]


def test_drops_route_with_no_service_in_counties(tmp_path: Path) -> None:
    settings = _settings_with_counties(tmp_path)
    # Inside the metro's clip box only after padding, but never inside the county.
    outside = _route("Neighbour Lines", [[-97.2, 33.4], [-97.15, 33.5], [-97.1, 33.6]])

    kept = _keep_servicing_routes([outside], settings, METRO)

    assert kept == []


def test_keeps_route_that_only_partly_enters(tmp_path: Path) -> None:
    settings = _settings_with_counties(tmp_path)
    # An operator based elsewhere that genuinely reaches into the MSA still services it.
    crossing = _route(
        "Regional Rail",
        [[-97.5, 33.5], [-97.3, 33.2], [-96.8, 32.8], [-96.5, 32.5], [-96.2, 32.2]],
    )

    kept = _keep_servicing_routes([crossing], settings, METRO)

    assert len(kept) == 1


def test_keeps_all_routes_when_boundaries_missing(tmp_path: Path) -> None:
    # Without counties on disk the filter must not silently empty the map.
    settings = Settings(data_dir=tmp_path / "pipeline" / "data")
    routes = [_route("A", [[-96.5, 32.5]]), _route("B", [[0.0, 0.0]])]

    assert _keep_servicing_routes(routes, settings, METRO) == routes


def test_feature_vertices_handles_multilinestring() -> None:
    geom = {
        "type": "MultiLineString",
        "coordinates": [[[-96.6, 32.4], [-96.5, 32.5]], [[-96.4, 32.6]]],
    }

    assert _feature_vertices(geom) == [[-96.6, 32.4], [-96.5, 32.5], [-96.4, 32.6]]


def test_feature_vertices_ignores_unsupported_geometry() -> None:
    assert _feature_vertices({"type": "Point", "coordinates": [-96.5, 32.5]}) == []
