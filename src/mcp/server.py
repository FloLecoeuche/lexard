"""MCP JSON-RPC 2.0 server implementation.

Provides a FastAPI router that handles JSON-RPC requests at POST /mcp.
"""

import logging
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.mcp.errors import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JSONRPCError,
    make_error,
)
from src.mcp.methods import MCP_METHODS
from src.mcp.schemas import (
    AnalyzeDocumentParams,
    AskQuestionParams,
    CompareParams,
    JSONRPCErrorDetail,
    JSONRPCRequest,
    JSONRPCResponse,
    ListDocumentsParams,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])

# Parameter schema mapping for validation
PARAM_SCHEMAS = {
    "list_documents": ListDocumentsParams,
    "analyze_document": AnalyzeDocumentParams,
    "ask_question": AskQuestionParams,
    "compare": CompareParams,
}


def make_response(
    result: Any = None,
    error: Optional[JSONRPCError] = None,
    request_id: Optional[Union[str, int]] = None,
) -> Dict[str, Any]:
    """Create a JSON-RPC 2.0 response.

    Args:
        result: Success result (mutually exclusive with error)
        error: Error object (mutually exclusive with result)
        request_id: Request ID to echo back

    Returns:
        JSON-RPC 2.0 response dictionary
    """
    response: Dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}

    if error is not None:
        response["error"] = error.to_dict()
    else:
        response["result"] = result

    return response


def make_error_response(
    error: JSONRPCError,
    request_id: Optional[Union[str, int]] = None,
) -> Dict[str, Any]:
    """Create a JSON-RPC 2.0 error response.

    Args:
        error: Error object
        request_id: Request ID to echo back (null for parse errors)

    Returns:
        JSON-RPC 2.0 error response dictionary
    """
    return make_response(error=error, request_id=request_id)


@router.post(
    "/mcp",
    response_class=JSONResponse,
    summary="MCP JSON-RPC endpoint",
    description="Model Context Protocol endpoint accepting JSON-RPC 2.0 requests. "
    "Available methods: list_documents, analyze_document, ask_question, compare.",
    responses={
        200: {
            "description": "JSON-RPC 2.0 response (success or error)",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Success response",
                            "value": {
                                "jsonrpc": "2.0",
                                "result": {"documents": []},
                                "id": 1,
                            },
                        },
                        "error": {
                            "summary": "Error response",
                            "value": {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32601,
                                    "message": "Method not found",
                                },
                                "id": 1,
                            },
                        },
                    }
                }
            },
        }
    },
)
async def mcp_endpoint(request: Request) -> JSONResponse:
    """Handle MCP JSON-RPC requests.

    Parses incoming JSON-RPC 2.0 requests, validates parameters,
    dispatches to the appropriate method, and returns the result.
    """
    request_id: Optional[Union[str, int]] = None

    # Parse JSON body
    try:
        body = await request.json()
    except Exception as e:
        logger.warning(f"JSON parse error: {e}")
        return JSONResponse(
            content=make_error_response(
                make_error(PARSE_ERROR, str(e)), request_id=None
            )
        )

    # Validate JSON-RPC structure
    try:
        rpc_request = JSONRPCRequest(**body)
        request_id = rpc_request.id
    except ValidationError as e:
        logger.warning(f"Invalid JSON-RPC request: {e}")
        # Try to extract ID from raw body for error response
        if isinstance(body, dict):
            request_id = body.get("id")
        return JSONResponse(
            content=make_error_response(
                make_error(INVALID_REQUEST, str(e)), request_id=request_id
            )
        )

    # Check if method exists
    method_name = rpc_request.method
    if method_name not in MCP_METHODS:
        logger.warning(f"Method not found: {method_name}")
        return JSONResponse(
            content=make_error_response(
                make_error(METHOD_NOT_FOUND, f"Unknown method: {method_name}"),
                request_id=request_id,
            )
        )

    # Validate parameters
    params = rpc_request.params or {}
    param_schema = PARAM_SCHEMAS.get(method_name)

    if param_schema:
        try:
            validated_params = param_schema(**params)
        except ValidationError as e:
            logger.warning(f"Invalid params for {method_name}: {e}")
            return JSONResponse(
                content=make_error_response(
                    make_error(INVALID_PARAMS, str(e)), request_id=request_id
                )
            )
    else:
        validated_params = None

    # Execute method
    method_func = MCP_METHODS[method_name]

    try:
        if validated_params is not None:
            result = await method_func(validated_params)
        else:
            result = await method_func()

        # Convert result to dict if it's a Pydantic model
        # Use mode="json" to ensure datetime serialization
        if hasattr(result, "model_dump"):
            result_dict = result.model_dump(mode="json")
        else:
            result_dict = result

        logger.info(f"MCP method {method_name} completed successfully")
        return JSONResponse(content=make_response(result=result_dict, request_id=request_id))

    except ValueError as e:
        # ValueError with error dict from methods
        error_data = e.args[0] if e.args else str(e)
        if isinstance(error_data, dict) and "code" in error_data:
            return JSONResponse(
                content=make_error_response(
                    JSONRPCError(
                        code=error_data["code"],
                        message=error_data["message"],
                        data=error_data.get("data"),
                    ),
                    request_id=request_id,
                )
            )
        return JSONResponse(
            content=make_error_response(
                make_error(INTERNAL_ERROR, str(e)), request_id=request_id
            )
        )

    except Exception as e:
        logger.exception(f"Internal error in {method_name}: {e}")
        return JSONResponse(
            content=make_error_response(
                make_error(INTERNAL_ERROR, str(e)), request_id=request_id
            )
        )
