import requests
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@extend_schema(
    summary="UniProt 단백질 검색",
    description="UniProt 공개 REST API를 이용하여 단백질을 검색합니다.",
    tags=["Experiments"],
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
        # --- Sequence ---
        seq = item.get("sequence", {})

        results.append({
            "accession": item.get("primaryAccession"),          # P38567
            "entry_name": item.get("uniProtkbId"),              # HYALP_HUMAN
            "protein_name": protein_name,                       # Hyaluronidase PH-20
            "gene": gene,                                       # SPAM1 (HYAL3, PH20)
            "organism": organism,                               # Homo sapiens (Human)
            # "ec_numbers": ec_numbers,                           # EC:3.2.1.35
            "length": item.get("sequence", {}).get("length"),   # 509
            "protein_existence": protein_existence,             # Evidence at protein level
            "annotation_score": item.get("annotationScore"),    # 5
            "keywords": keywords,                               # Glycosidase, ...
            'sequence': seq.get("value")}
        )

    return Response({
        "keyword": keyword,
        "count": len(results),
        "results": results,
    })


@extend_schema(
    summary="UniProt 단백질 상세 정보 조회",
    description="UniProt 공개 REST API를 이용하여 특정 단백질의 상세 정보를 조회합니다.",
    tags=["Experiments"],
    parameters=[
        OpenApiParameter(
            name="accession",
            description="UniProt accession 번호 (예: P38567)",
            required=True,
            type=str,
            location=OpenApiParameter.PATH,
        ),
    ],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'accession': {'type': 'string'},
                'entry_name': {'type': 'string'},
                'protein_recommended_name': {'type': 'string'},
                'gene': {'type': 'string'},
                'taxonomy_id': {'type': 'integer'},
                'organism': {'type': 'string'},
                'lineage': {'type': 'string'},
                'length': {'type': 'integer'},
                'evidence_level': {'type': 'string'},
                'annotation_score': {'type': 'number'},
                'description': {'type': 'string'},
                'keywords': {'type': 'array', 'items': {'type': 'string'}},
                'sequence': {
                    'type': 'object',
                    'properties': {
                        'length': {'type': 'integer'},
                        'mass': {'type': 'number'},
                        'md5': {'type': 'string'},
                        'value': {'type': 'string'},
                        'last_updated': {'type': 'string'},
                    }
                },
            }
        }
    },
)
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

    # --- Organism ---
    org = item.get("organism", {})
    organism_display = org.get("scientificName", "")
    if org.get("commonName"):
        organism_display = f"{organism_display} ({org.get('commonName')})"
    
    lineage = org.get("lineage", [])
    lineage_display = ", ".join(lineage) if lineage else None

    # --- Sequence ---
    seq = item.get("sequence", {})
    audit = item.get("entryAudit", {})

    # --- Description (from FUNCTION comment) ---
    description = None
    comments = item.get("comments", [])
    for comment in comments:
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts", [])
            if texts and texts[0].get("value"):
                description = texts[0]["value"]
                break

    # --- Protein existence (format: "1: Evidence at protein level" -> "Evidence at protein level") ---
    protein_existence = item.get("proteinExistence")
    if isinstance(protein_existence, str) and ":" in protein_existence:
        protein_existence = protein_existence.split(":", 1)[1].strip()

    # --- Keywords ---
    keywords = [kw.get("name") for kw in item.get("keywords", []) if kw.get("name")]

    # 템플릿에 필요한 필드만 추출
    response = {
        # 기본 정보
        "accession": item.get("primaryAccession"),
        "entry_name": item.get("uniProtkbId"),
        
        # Names & Taxonomy
        "protein_recommended_name": protein_name,
        "gene": gene,
        "taxonomy_id": org.get("taxonId"),
        "organism": organism_display,
        "lineage": lineage_display,
        
        # 추가 정보
        "length": seq.get("length"),
        "evidence_level": protein_existence,
        "annotation_score": item.get("annotationScore"),
        "description": description,
        "keywords": keywords,
        
        # Sequence 정보
        "sequence": {
            "length": seq.get("length"),
            "mass": seq.get("molWeight"),
            "md5": seq.get("md5"),
            "value": seq.get("value"),
            "last_updated": audit.get("lastSequenceUpdateDate"),
        },
    }

    return Response(response)
