from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.exceptions import AppException
from app.core.response import success_response
from app.schemas.common import APIResponse
from app.schemas.subtitles import SubtitleUploadResult
from app.services.subtitles_service import SubtitleUploadService

router = APIRouter(prefix="/subtitles", tags=["subtitles"])


def get_subtitle_upload_service() -> SubtitleUploadService:
    return SubtitleUploadService()


@router.post("/upload", response_model=APIResponse[SubtitleUploadResult])
def upload_subtitles(
    file: Annotated[UploadFile, File(description="Subtitle file or zip archive")],
    target_path: Annotated[str, Form(description="Remote STRM target directory")],
    service: Annotated[SubtitleUploadService, Depends(get_subtitle_upload_service)],
    overwrite: Annotated[bool, Form(description="Whether to overwrite existing files")] = False,
) -> APIResponse[SubtitleUploadResult]:
    normalized_target_path = target_path.strip()
    if not normalized_target_path:
        raise AppException(status_code=400, message="invalid target path")

    result = service.upload_subtitles(
        file=file,
        target_path=normalized_target_path,
        overwrite=overwrite,
    )
    return success_response(data=result, message="subtitle uploaded successfully")
