from typing import Literal

from pydantic import BaseModel, Field


CountryCode = Literal["US", "Canada", "China"]
RewardCurrency = Literal["USD", "CAD", "CNY"]
SourceKind = Literal["official", "publisher"]


class OfficialSourceRecord(BaseModel):
    caseId: str
    url: str
    title: str | None = None
    author: str
    reward: int | None = Field(default=None, ge=0)
    rewardCurrency: RewardCurrency | None = None
    rewardText: str | None = None
    sourceUpdatedDate: str | None = None


class RewardCase(BaseModel):
    id: str
    title: str
    agency: str
    country: CountryCode
    regions: list[str] = Field(default_factory=list)
    caseType: str | None = None
    description: str | None = None
    reward: int | None = Field(default=None, ge=0)
    rewardCurrency: RewardCurrency | None = None
    rewardText: str | None = None
    status: str
    summary: str
    warningMessage: str | None = None
    aliases: list[str] = Field(default_factory=list)
    age: str | None = None
    dateOfBirth: str | None = None
    placeOfBirth: str | None = None
    sex: str | None = None
    race: str | None = None
    nationality: str | None = None
    hair: str | None = None
    eyes: str | None = None
    height: str | None = None
    weight: str | None = None
    locations: str | None = None
    distinguishingFeatures: str | None = None
    fieldOffice: str | None = None
    publishedDate: str
    lastVerified: str
    sourceUpdatedDate: str | None = None
    sourceUrl: str
    sourceTitle: str | None = None
    sourceAuthor: str | None = None
    sourceKind: SourceKind = "official"
    sourceRecords: list[OfficialSourceRecord] = Field(default_factory=list)
    imageUrl: str | None = None
    imageUrls: list[str] = Field(default_factory=list)


class CaseFacetOption(BaseModel):
    value: str
    count: int = Field(ge=0)


class CaseFacets(BaseModel):
    statuses: list[CaseFacetOption] = Field(default_factory=list)
    regions: list[CaseFacetOption] = Field(default_factory=list)
    sources: list[CaseFacetOption] = Field(default_factory=list)


class CaseListResponse(BaseModel):
    items: list[RewardCase]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    pageSize: int = Field(ge=1)
    totalPages: int = Field(ge=0)
    facets: CaseFacets


class CaseMapLocation(BaseModel):
    label: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    precision: Literal["city", "region"]
    locationType: Literal[
        "official_location",
        "title_location",
        "broad_region",
        "manual_location",
    ]
    approximate: bool = False


class CaseMapItem(BaseModel):
    id: str
    title: str
    agency: str
    country: CountryCode
    reward: int | None = Field(default=None, ge=0)
    rewardCurrency: RewardCurrency | None = None
    status: str
    imageUrl: str | None = None
    locations: list[CaseMapLocation] = Field(default_factory=list)


class CaseMapResponse(BaseModel):
    items: list[CaseMapItem]
    total: int = Field(ge=0)
    generatedAt: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
