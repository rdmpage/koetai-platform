"""VoID (Vocabulary of Interlinked Datasets) statistics for a dataset.

Computes a VoID description live from a dataset's own SPARQL endpoint, the same
family of statistics kgsteward's `special.py` emits: overall counts plus class
and property partitions. Queries are scoped to the dataset's graphs via
`triplestore.dataset_scope`, so a VoID never leaks another tenant's data.

Two products from one computation:
  compute(ds)  -> VoidStats   (structured, for the HTML view)
  to_turtle(...) -> str       (DCAT/VoID Turtle, content-negotiated)

The partition queries are the light form (group by class, group by property)
rather than kgsteward's subject×object class cross-product: that heavier query
is quadratic in the class count and too slow to serve on demand. The light form
is the widely used VoID profile and answers "what's in here" for callers.
"""
from dataclasses import dataclass, field

from services import triplestore

# Cap partitions so a pathological dataset can't produce a multi-megabyte VoID
# or an unreadable HTML table. Datasets past this are extremely rare; when hit,
# the VoID is flagged truncated and shows the top classes/properties by size.
PARTITION_LIMIT = 1000

VOID = "http://rdfs.org/ns/void#"


@dataclass
class Partition:
    uri: str
    count: int


@dataclass
class VoidStats:
    triples: int = -1
    distinct_subjects: int = -1
    distinct_objects: int = -1
    properties: int = -1
    classes: int = -1
    class_partitions: list = field(default_factory=list)     # [Partition]
    property_partitions: list = field(default_factory=list)  # [Partition]
    class_truncated: bool = False
    property_truncated: bool = False
    error: str = ""

    @property
    def ok(self):
        return not self.error and self.triples >= 0


# ── SPARQL ───────────────────────────────────────────────────────────────────

_Q_SCALARS = """
SELECT (COUNT(*) AS ?triples)
       (COUNT(DISTINCT ?s) AS ?subjects)
       (COUNT(DISTINCT ?o) AS ?objects)
       (COUNT(DISTINCT ?p) AS ?properties)
WHERE { ?s ?p ?o }
"""

_Q_CLASSES = "SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?s a ?c }"

_Q_CLASS_PARTITION = """
SELECT ?class (COUNT(?s) AS ?count)
WHERE { ?s a ?class }
GROUP BY ?class
ORDER BY DESC(?count)
LIMIT %d
""" % (PARTITION_LIMIT + 1)

_Q_PROPERTY_PARTITION = """
SELECT ?property (COUNT(*) AS ?count)
WHERE { ?s ?property ?o }
GROUP BY ?property
ORDER BY DESC(?count)
LIMIT %d
""" % (PARTITION_LIMIT + 1)


def _scalar(bindings, name, default=-1):
    if not bindings:
        return default
    v = bindings[0].get(name)
    if not v:
        return default
    try:
        return int(v["value"])
    except (ValueError, KeyError, TypeError):
        return default


def _partitions(bindings, uri_var, count_var):
    out = []
    for b in bindings:
        u = b.get(uri_var)
        c = b.get(count_var)
        if not u or not c:
            continue
        try:
            out.append(Partition(uri=u["value"], count=int(c["value"])))
        except (ValueError, KeyError, TypeError):
            continue
    return out


def compute(ds) -> VoidStats:
    """Run the VoID queries against the dataset's scoped endpoint."""
    if ds["platform"] == "comunica":
        return VoidStats(error="Federation datasets have no local store to profile.")

    store = triplestore.get(ds)
    scope = triplestore.dataset_scope(ds)

    def q(query):
        ok, res = store.sparql_query(query, graphs=scope)
        if not ok:
            return None, (res or {}).get("error", "query failed")
        return res.get("results", {}).get("bindings", []), None

    stats = VoidStats()

    b, err = q(_Q_SCALARS)
    if err:
        stats.error = err
        return stats
    stats.triples = _scalar(b, "triples")
    stats.distinct_subjects = _scalar(b, "subjects")
    stats.distinct_objects = _scalar(b, "objects")
    stats.properties = _scalar(b, "properties")

    b, err = q(_Q_CLASSES)
    if not err:
        stats.classes = _scalar(b, "n")

    b, err = q(_Q_CLASS_PARTITION)
    if not err:
        parts = _partitions(b, "class", "count")
        if len(parts) > PARTITION_LIMIT:
            stats.class_truncated = True
            parts = parts[:PARTITION_LIMIT]
        stats.class_partitions = parts

    b, err = q(_Q_PROPERTY_PARTITION)
    if not err:
        parts = _partitions(b, "property", "count")
        if len(parts) > PARTITION_LIMIT:
            stats.property_truncated = True
            parts = parts[:PARTITION_LIMIT]
        stats.property_partitions = parts

    return stats


# ── Turtle ───────────────────────────────────────────────────────────────────

_TTL_PREFIXES = """\
@prefix void:  <http://rdfs.org/ns/void#> .
@prefix dcat:  <http://www.w3.org/ns/dcat#> .
@prefix dct:   <http://purl.org/dc/terms/> .
@prefix xsd:   <http://www.w3.org/2001/XMLSchema#> .
@prefix fdp:   <http://rdf.biosemantics.org/ontologies/fdp-o#> .
"""


def to_turtle(stats: VoidStats, void_uri, dataset_uri, sparql_endpoint,
              title, issued, modified) -> str:
    """Serialise a VoidStats as a void:Dataset in Turtle."""
    lines = [_TTL_PREFIXES, ""]
    lines.append(f"<{void_uri}> a void:Dataset ;")
    lines.append(f'    dct:title "{_esc(title)} — VoID statistics"@en ;')
    lines.append(f"    dct:isPartOf <{dataset_uri}> ;")
    lines.append(f"    void:sparqlEndpoint <{sparql_endpoint}> ;")
    if stats.triples >= 0:
        lines.append(f'    void:triples "{stats.triples}"^^xsd:integer ;')
    if stats.distinct_subjects >= 0:
        lines.append(f'    void:distinctSubjects "{stats.distinct_subjects}"^^xsd:integer ;')
    if stats.distinct_objects >= 0:
        lines.append(f'    void:distinctObjects "{stats.distinct_objects}"^^xsd:integer ;')
    if stats.properties >= 0:
        lines.append(f'    void:properties "{stats.properties}"^^xsd:integer ;')
    if stats.classes >= 0:
        lines.append(f'    void:classes "{stats.classes}"^^xsd:integer ;')

    for p in stats.class_partitions:
        lines.append("    void:classPartition [")
        lines.append(f"        void:class <{p.uri}> ;")
        lines.append(f'        void:entities "{p.count}"^^xsd:integer ] ;')
    for p in stats.property_partitions:
        lines.append("    void:propertyPartition [")
        lines.append(f"        void:property <{p.uri}> ;")
        lines.append(f'        void:triples "{p.count}"^^xsd:integer ] ;')

    lines.append(f"    fdp:metadataIdentifier <{void_uri}> ;")
    lines.append(f'    fdp:metadataIssued "{issued}"^^xsd:dateTime ;')
    lines.append(f'    fdp:metadataModified "{modified}"^^xsd:dateTime .')
    return "\n".join(lines) + "\n"


def _esc(s):
    return (s or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
