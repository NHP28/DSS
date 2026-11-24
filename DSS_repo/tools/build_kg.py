"""Build the Đà Nẵng knowledge graph in Neo4j from data/danang. Safe to re-run (MERGE only).

    docker compose up -d --wait neo4j
    python tools/build_kg.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from kg_schema import build_rows, load_frames  # noqa: E402

CONSTRAINTS = [("User", "id"), ("POI", "id"), ("Category", "key"), ("District", "name"), ("TimeSlot", "key")]
NODES = {
    "users": "MERGE (n:User {id: row.id})",
    "pois": "MERGE (n:POI {id: row.id}) SET n.name = row.name, n.category = row.category, n.lat = row.lat, n.lon = row.lon, "
            "n.rating = row.rating, n.price_avg = row.price_avg, n.popularity = row.popularity",
    "categories": "MERGE (n:Category {key: row.key}) SET n.label = row.label",
    "districts": "MERGE (n:District {name: row.name})",
    "timeslots": "MERGE (n:TimeSlot {key: row.key}) SET n.label = row.label",
}
EDGES = {
    "visited": "MATCH (a:User {id: row.source}), (b:POI {id: row.target}) MERGE (a)-[r:VISITED]->(b) "
               "SET r.count = row.count, r.first_ts = row.first_ts, r.last_ts = row.last_ts, r.top_hour = row.top_hour",
    "friend_of": "MATCH (a:User {id: row.source}), (b:User {id: row.target}) MERGE (a)-[:FRIEND_OF]->(b)",
    "in_category": "MATCH (a:POI {id: row.source}), (b:Category {key: row.target}) MERGE (a)-[:IN_CATEGORY]->(b)",
    "located_in": "MATCH (a:POI {id: row.source}), (b:District {name: row.target}) MERGE (a)-[:LOCATED_IN]->(b)",
    "near": "MATCH (a:POI {id: row.source}), (b:POI {id: row.target}) MERGE (a)-[r:NEAR]->(b) SET r.km = row.km",
    "busy_at": "MATCH (a:POI {id: row.source}), (b:TimeSlot {key: row.target}) MERGE (a)-[r:BUSY_AT]->(b) SET r.count = row.count, r.share = row.share",
    "active_at": "MATCH (a:User {id: row.source}), (b:TimeSlot {key: row.target}) MERGE (a)-[r:ACTIVE_AT]->(b) SET r.count = row.count",
}


def env_file_value(name):
    """Fall back to apps/api/.env so one file configures both the API and this script."""
    path = ROOT / "apps" / "api" / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip()
    return None


def setting(name, default):
    return os.getenv(name) or env_file_value(name) or default


def main():
    from neo4j import GraphDatabase

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    rows = build_rows(*load_frames(ROOT / "data" / "danang"))
    driver = GraphDatabase.driver(setting("NEO4J_URI", "bolt://127.0.0.1:7687"),
                                  auth=(setting("NEO4J_USER", "neo4j"), setting("NEO4J_PASSWORD", "neo4j_local_password")))
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            for label, key in CONSTRAINTS:
                session.run(f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{key} IS UNIQUE")
            for name, statement in {**NODES, **EDGES}.items():
                batch = rows[name]
                for start in range(0, len(batch), 1000):
                    session.run(f"UNWIND $rows AS row {statement}", rows=batch[start:start + 1000]).consume()
                print(f"  {name:<12} {len(batch):>7,}")
            nodes = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
            edges = session.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
        print(f"Đồ thị tri thức: {nodes:,} nút, {edges:,} cạnh.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
