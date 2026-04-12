from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

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
    service: Annotated[SubtitleUploadService, Depends(get_subtitle_upload_service)],
    target_path: Annotated[str | None, Form(description="Remote STRM target directory")] = None,
    media_type: Annotated[str | None, Form(description="Associated media type")] = None,
    library_title: Annotated[str | None, Form(description="Associated library title")] = None,
    library_year: Annotated[str | None, Form(description="Associated library year")] = None,
    overwrite: Annotated[bool, Form(description="Whether to overwrite existing files")] = True,
) -> APIResponse[SubtitleUploadResult]:
    result = service.upload_subtitles(
        file=file,
        target_path=target_path,
        media_type=media_type,
        library_title=library_title,
        library_year=library_year,
        overwrite=overwrite,
    )
    return success_response(data=result)
