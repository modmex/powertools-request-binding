# powertools-request-binding

Middleware for AWS Lambda Powertools Event Handler that validates and injects route arguments using Modmex models instead of Pydantic.

## Why

Powertools request validation currently requires Pydantic. This package provides a lightweight alternative for request binding in REST API and HTTP API handlers when your project uses Modmex.

## Installation

```bash
poetry add powertools-request-binding modmex
```

## Usage

```python
from typing import Annotated

from modmex import BaseModel
from aws_lambda_powertools.event_handler import APIGatewayRestResolver

from powertools_request_binding import Body, Query, RequestBindingMiddleware


class CreateTodoRequest(BaseModel):
	title: str
	completed: bool


app = APIGatewayRestResolver()
app.use(middlewares=[RequestBindingMiddleware()])


@app.post("/todos/<todo_id>")
def create_todo(
	todo_id: int,
	payload: Annotated[CreateTodoRequest, Body()],
	source: Annotated[str | None, Query()] = None,
):
	return {
		"todo_id": todo_id,
		"title": payload.title,
		"completed": payload.completed,
		"source": source,
	}
```

## Supported Input Sources

- Path parameters
- Query parameters
- Headers
- JSON body

## Notes

- This package focuses on request argument binding only.
- Powertools `Depends(...)` support remains native and should be used directly from Powertools when needed.
