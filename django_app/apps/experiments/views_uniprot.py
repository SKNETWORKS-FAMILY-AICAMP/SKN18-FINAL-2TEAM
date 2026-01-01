import requests
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@extend_schema(
    summary="UniProt 단백질 검색",
    description="UniProt 공개 REST API를 이용하여 단백질을 검색합니다.",
    tags=["UniProt"],
    parameters=[
        OpenApiParameter(
            name="keyword",
            description="검색 키워드 (예: human PH20)",
            required=True,
            type=str,
        ),
        OpenApiParameter(
            name="size",
            description="검색 결과 개수 (default: 10)",
            required=False,
            type=int,
        ),
    ],
    responses={200: dict},
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def uniprot_search_api(request):
    """
    GET /api/uniprot/search?keyword=xxx
    → UniProtKB search (요약 목록)
    """
    keyword = request.query_params.get("keyword")
    size = int(request.query_params.get("size", 10))

    if not keyword:
        return Response({"error": "keyword is required"}, status=400)

    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {
        "query": keyword,
        "format": "json",
        "size": size,
    }

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()

    results = []

    for item in r.json().get("results", []):

        # --- Protein name ---
        pd = item.get("proteinDescription", {})
        rec = pd.get("recommendedName", {})

        protein_name = (
            rec.get("fullName", {}).get("value")
        )

        # --- Gene ---
        gene = None
        genes = item.get("genes", [])

        # 1️⃣ 우선순위 기반 gene 식별
        for g in genes:
            if g.get("geneName"):
                gene = g["geneName"]["value"]
                break

            if g.get("orderedLocusNames"):
                gene = g["orderedLocusNames"][0]["value"]
                break

            if g.get("orfNames"):
                gene = g["orfNames"][0]["value"]
                break

            if g.get("synonyms"):
                gene = g["synonyms"][0]["value"]
                break

        # 2️⃣ UI 표시용 synonym 결합 (geneName이 있을 때만)
        if gene:
            for g in genes:
                if g.get("geneName") and g.get("synonyms"):
                    syns = [s["value"] for s in g["synonyms"]]
                    if syns:
                        gene = f"{gene} ({', '.join(syns)})"
                    break

        # --- Organism ---
        org = item.get("organism", {})
        organism = org.get("scientificName")
        if org.get("commonName"):
            organism = f"{organism} ({org.get('commonName')})"

        # --- EC numbers ---
        ec_numbers = [
            f"EC:{ec['value']}"
            for ec in rec.get("ecNumbers", [])
            if ec.get("value")
        ]

        # --- Protein existence ---
        pe = item.get("proteinExistence")
        protein_existence = (
            pe.get("type") if isinstance(pe, dict) else None
        )

        # --- Keywords ---
        keywords = [
            kw.get("name")
            for kw in item.get("keywords", [])
            if kw.get("name")
        ]

        results.append({
            "accession": item.get("primaryAccession"),          # P38567
            "entry_name": item.get("uniProtkbId"),              # HYALP_HUMAN
            "protein_name": protein_name,                       # Hyaluronidase PH-20
            "gene": gene,                                       # SPAM1 (HYAL3, PH20)
            "organism": organism,                               # Homo sapiens (Human)
            "ec_numbers": ec_numbers,                           # EC:3.2.1.35
            "length": item.get("sequence", {}).get("length"),   # 509
            "protein_existence": protein_existence,             # Evidence at protein level
            "annotation_score": item.get("annotationScore"),    # 5
            "keywords": keywords,                               # Glycosidase, ...
        })

    return Response({
        "keyword": keyword,
        "count": len(results),
        "results": results,
    })


@extend_schema(tags=["Experiments"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def uniprot_detail_api(request, accession):

    url = f"https://rest.uniprot.org/uniprotkb/{accession}"
    params = {"format": "json"}

    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()

    item = r.json()

    # --- Protein description ---
    pd = item.get("proteinDescription", {})
    rec = pd.get("recommendedName", {})

    protein_name = rec.get("fullName", {}).get("value")

    alternative_names = [
        alt.get("fullName", {}).get("value")
        for alt in pd.get("alternativeNames", [])
        if alt.get("fullName", {}).get("value")
    ]

    # --- Gene ---
    gene = None
    genes = item.get("genes", [])

    for g in genes:
        if g.get("geneName"):
            gene = g["geneName"]["value"]
            break

        if g.get("orderedLocusNames"):
            gene = g["orderedLocusNames"][0]["value"]
            break

        if g.get("orfNames"):
            gene = g["orfNames"][0]["value"]
            break

        if g.get("synonyms"):
            gene = g["synonyms"][0]["value"]
            break

    if gene:
        for g in genes:
            if g.get("geneName") and g.get("synonyms"):
                syns = [s["value"] for s in g["synonyms"]]
                if syns:
                    gene = f"{gene} ({', '.join(syns)})"
                break

    # --- EC numbers ---
    ec_numbers = [
        f"EC:{ec['value']}"
        for ec in rec.get("ecNumbers", [])
        if ec.get("value")
    ]

    # --- Organism ---
    org = item.get("organism", {})

    # --- Sequence ---
    seq = item.get("sequence", {})
    audit = item.get("entryAudit", {})

    response = {
        "accession": item.get("primaryAccession"),
        "entry_name": item.get("uniProtkbId"),
        "protein_name": protein_name,
        "alternative_names": alternative_names,
        "gene": gene,
        "ec_numbers": ec_numbers,

        "organism": {
            "scientific": org.get("scientificName"),
            "common": org.get("commonName"),
            "taxonomy_id": org.get("taxonId"),
            "lineage": org.get("lineage"),
        },

        "sequence": {
            "length": seq.get("length"),
            "mass": seq.get("molWeight"),
            "md5": seq.get("md5"),
            "value": seq.get("value"),
            "last_updated": audit.get("lastSequenceUpdateDate"),
            "version": audit.get("sequenceVersion"),
        },

        "annotation_score": item.get("annotationScore"),
        "protein_existence": item.get("proteinExistence"),
        "keywords": [kw.get("name") for kw in item.get("keywords", []) if kw.get("name")],
    }

    return Response(response)
