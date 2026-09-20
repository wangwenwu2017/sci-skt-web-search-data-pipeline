"""Small, explicit contracts for discovery and packaging."""

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")]


def http_url(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username:
        raise ValueError("Expected HTTP(S) URL without embedded credentials")
    return value


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRequest(Contract):
    request_id: Identifier = Field(max_length=64)
    mode: Literal["bench", "domain"]
    request: Text
    entrypoints: list[str] = Field(default_factory=list)
    max_candidates: int = Field(default=10, ge=1, le=100)

    @field_validator("entrypoints")
    @classmethod
    def urls(cls, values):
        return [http_url(value) for value in values]


class Source(Contract):
    url: str
    kind: Literal["paper", "code", "data", "benchmark", "web"] = "web"
    version: str | None = None
    read_status: Literal["read", "search_only", "unavailable"] = "search_only"

    _url = field_validator("url")(http_url)


class Candidate(Contract):
    candidate_id: Identifier
    title: Text
    relevance: Text
    scope: Text
    sources: list[Source] = Field(min_length=1)
    relationships: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class Discovery(Contract):
    status: Literal["completed", "no_results", "failed"]
    candidates: list[Candidate] = Field(default_factory=list)
    report: Text

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "completed") != bool(self.candidates):
            raise ValueError("Only completed discovery has nonempty candidates")
        ids = [row.candidate_id for row in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate_id must be unique within a request")
        return self


class PackageItem(Contract):
    item_id: Identifier
    request: SourceRequest
    candidate: Candidate
    originals: list[Candidate]


def exact_key(candidate: Candidate) -> tuple:
    return (
        candidate.scope.strip(),
        tuple(sorted({(s.url.strip(), s.version or "") for s in candidate.sources})),
    )


def expand(request: SourceRequest, discovery: Discovery) -> list[PackageItem]:
    if len(discovery.candidates) > request.max_candidates:
        raise ValueError("Discovery exceeded max_candidates")
    grouped = {}
    for index, candidate in enumerate(discovery.candidates):
        key = exact_key(candidate)
        if key in grouped:
            grouped[key].originals.append(candidate)
        else:
            grouped[key] = PackageItem(
                item_id=f"{request.request_id}-c{index:03d}",
                request=request,
                candidate=candidate,
                originals=[candidate],
            )
    return list(grouped.values())
