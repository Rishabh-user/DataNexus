from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse


class DataNexusException(Exception):
    def __init__(self, message: str, detail: str | None = None):
        self.message = message
        self.detail = detail
        super().__init__(self.message)


class FileProcessingError(DataNexusException):
    pass


class ExtractionError(DataNexusException):
    pass


class OneDriveError(DataNexusException):
    pass


class RAGError(DataNexusException):
    pass


class PPTGenerationError(DataNexusException):
    pass


class DuplicateFileError(DataNexusException):
    pass


async def datanexus_exception_handler(request: Request, exc: DataNexusException) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


def register_exception_handlers(app):
    app.add_exception_handler(DataNexusException, datanexus_exception_handler)
