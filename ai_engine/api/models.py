from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class ResumeRequest(BaseModel):
    retrievedChunks: str = Field(..., description="The context chunks retrieved from the student's old resume.")
    jobDescription: str = Field(..., description="The target job description.")
    disableCache: bool = Field(False, description="Whether to bypass the generation cache.")
    refreshCache: bool = Field(False, description="Whether to force a fresh generation.")
    student_id: Optional[str] = Field(None, description="Student ID to use their master template")
    master_template: Optional[Dict[str, Any]] = Field(None, description="Master template config from student's master resume")

class ResumeSubScores(BaseModel):
    keywordMatch: int
    experienceDepth: int
    impactOutcome: int
    strategicAlignment: int
    atsReadability: int

class ResumeResponse(BaseModel):
    success: bool
    resumeText: str
    pdfPath: Optional[str] = None
    containerPath: Optional[str] = None
    hostPath: Optional[str] = None
    fullName: str
    roleFamily: str
    score: int
    subScores: Optional[ResumeSubScores] = None
    reason: Optional[str] = None
    createdAt: str
    targetCompany: Optional[str] = None
    cacheHit: bool = False
