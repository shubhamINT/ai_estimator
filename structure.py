from pydantic import BaseModel
from typing import List
from enum import Enum


# Define structure for the problem statement
class Problem_satement(BaseModel):
    details: str


# Estimate structure
# Define structure for a single feature
class BreakdownItem(BaseModel):
    task: str
    optimistic: int
    most_likely: int
    pessimistic: int

class FeatureType(str, Enum):
    frontend = "Frontend"
    backend = "Backend"

class Feature(BaseModel):
    name: str
    # breakdown: List[str] = []
    breakdown: List[BreakdownItem] = []
    type: FeatureType
    optimistic: int
    most_likely: int
    pessimistic: int
    
    

# Define structure for the whole response
class EstimationResponse(BaseModel):
    features: List[Feature]



# ranke structure
class Rank(BaseModel):
    Result: str
    reason: str
    rank: int

# ranking structure
class RankingResponse(BaseModel):
    ranks: List[Rank]


# Project type
class ProjectType(BaseModel):
    project_summary: str
    technologies_used: str

# Metadata extraction structue
class Metadatastructure(BaseModel):
    title : str
    backend_technologies : str
    frontend_technologies : str
    summary : str


# Summary calculation structure
class Summary_calculation(BaseModel):
    total_optimistic: int
    total_most_likely: int
    total_pessimistic: int
    qa_percentage: int
    uat_percentage: int
    devops_percentage: int
    critical_percentage: int


# Feature list structure
class FeatureList_Structure(BaseModel):
    features: List[str]