from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.response import success_response
from app.schemas.common import APIResponse
from app.schemas.subtitles import SubtitleUploadRequest, SubtitleUploadResult
from app.services.subtitles_service import SubtitleUploadService

router = APIRouter(prefix="/subtitles", tags=["subtitles"])


def get_subtitle_upload_service() -> SubtitleUploadService:
    return SubtitleUploadService()


@router.post("/upload", response_model=APIResponse[SubtitleUploadResult])
def upload_subtitles(
    file: Annotated[UploadFile, File(description="Subtitle file or zip archive")],
    service: Annotated[SubtitleUploadService, Depends(get_subtitle_upload_service)],
    request: Annotated[SubtitleUploadRequest, Depends(SubtitleUploadRequest.as_form)],
) -> APIResponse[SubtitleUploadResult]:
    result = service.upload_subtitles(
        file=file,
        target_path=request.target_path,
        media_type=request.media_type,
        tmdb_id=request.tmdb_id,
        imdb_id=request.imdb_id,
        library_title=request.library_title,
        library_year=request.library_year,
        overwrite=request.overwrite,
    )
    return success_response(data=result)
