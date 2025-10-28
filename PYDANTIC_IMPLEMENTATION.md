# Pydantic Integration for Auth RBAC

## Overview

The authentication and RBAC system now uses **Pydantic v2** for all data models, providing:
- Automatic validation
- Type safety
- Better IDE support
- Serialization/deserialization
- Clear error messages

## Changes Made

### 1. Auth Module (`src/mcp_bigquery/core/auth.py`)

Converted from dataclasses to Pydantic BaseModel:

#### New Pydantic Models

**UserProfile**
```python
class UserProfile(BaseModel):
    user_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

**UserRole**
```python
class UserRole(BaseModel):
    user_id: str
    role_id: str
    role_name: str
    assigned_at: Optional[datetime] = None
```

**RolePermission**
```python
class RolePermission(BaseModel):
    role_id: str
    permission: str
    description: Optional[str] = None
```

**DatasetAccess**
```python
class DatasetAccess(BaseModel):
    role_id: str
    dataset_id: str
    table_id: Optional[str] = None
    access_level: Optional[str] = "read"
    
    @field_validator('dataset_id')
    @classmethod
    def validate_dataset_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("dataset_id cannot be empty")
        return v.strip()
```

**UserContext** (Main Model)
```python
class UserContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    user_id: str
    email: Optional[str] = None
    roles: List[str] = Field(default_factory=list)
    permissions: Set[str] = Field(default_factory=set)
    allowed_datasets: Set[str] = Field(default_factory=set)
    allowed_tables: Dict[str, Set[str]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    token_expires_at: Optional[datetime] = None
    
    @field_validator('user_id')
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("user_id cannot be empty")
        return v.strip()
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v and '@' not in v:
            raise ValueError("Invalid email format")
        return v
```

#### Key Features

- **Validation**: Automatic validation on instantiation
- **Field defaults**: Using `Field(default_factory=...)` instead of `field(default_factory=...)`
- **Custom validators**: `@field_validator` decorators for business logic
- **Type safety**: Pydantic ensures type correctness
- **Graceful fallback**: `_hydrate_user_context` handles validation errors gracefully

### 2. ServerConfig (`src/mcp_bigquery/config/settings.py`)

Converted to Pydantic `BaseSettings`:

```python
class ServerConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    project_id: str = Field(..., description="Google Cloud project ID")
    location: str = Field(default="US", description="BigQuery location")
    key_file: Optional[str] = Field(default=None, description="Path to service account key file")
    supabase_url: Optional[str] = Field(default=None, description="Supabase project URL")
    supabase_key: Optional[str] = Field(default=None, description="Supabase anonymous key")
    supabase_service_key: Optional[str] = Field(default=None, description="Supabase service role key")
    supabase_jwt_secret: Optional[str] = Field(default=None, description="JWT secret for token validation")

    @field_validator('project_id')
    @classmethod
    def validate_project_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Project ID is required and cannot be empty")
        return v.strip()

    @field_validator('key_file')
    @classmethod
    def validate_key_file(cls, v: Optional[str]) -> Optional[str]:
        if v and not os.path.isfile(v):
            raise ValueError(f"Key file '{v}' not found or inaccessible")
        return v

    @model_validator(mode='after')
    def validate_key_file_format(self) -> 'ServerConfig':
        if self.key_file:
            try:
                with open(self.key_file, "r") as f:
                    key_data = json.load(f)
                if (
                    key_data.get("type") != "service_account"
                    or "project_id" not in key_data
                ):
                    raise ValueError("Invalid service account key file format")
            except json.JSONDecodeError:
                raise ValueError("Service account key file is not valid JSON")
        return self
```

#### Key Features

- **BaseSettings**: Automatic environment variable loading
- **Case insensitive**: Environment variables work regardless of case
- **Automatic validation**: No need for separate `validate()` method
- **Simplified `from_env()`**: Just returns `cls()` - BaseSettings handles the rest
- **Field descriptions**: Self-documenting configuration

### 3. Dependencies (`pyproject.toml`)

Added Pydantic dependencies:
```toml
dependencies = [
    # ... existing dependencies ...
    "pyjwt>=2.8.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
]
```

### 4. Tests

Added comprehensive tests for Pydantic models:

**`tests/core/test_auth_models.py`** (42 tests)
- UserProfile validation
- UserRole validation
- RolePermission validation
- DatasetAccess validation (including error cases)
- UserContext validation (including error cases)
- Model interaction tests
- JSON serialization/deserialization

**`tests/config/test_settings.py`** (20 tests)
- ServerConfig validation
- Key file validation
- Environment variable loading
- Case insensitivity
- Error handling

## Benefits

### 1. Automatic Validation

Before (manual validation):
```python
if not user_id or not user_id.strip():
    raise ValueError("user_id cannot be empty")
```

After (automatic):
```python
context = UserContext(user_id="")  # Raises ValidationError
```

### 2. Type Safety

```python
# Pydantic ensures types are correct
context = UserContext(user_id="123", roles=["admin"])  # OK
context = UserContext(user_id=123)  # ValidationError - user_id must be str
```

### 3. Better IDE Support

IDEs can now provide:
- Autocomplete for model fields
- Type hints
- Documentation from field descriptions

### 4. Easy Serialization

```python
# To dict
data = context.model_dump()

# To JSON
json_str = context.model_dump_json()

# From dict
context = UserContext(**data)
```

### 5. Environment Variable Loading

```python
# Before: Manual environment loading
config = ServerConfig(
    project_id=os.getenv("PROJECT_ID"),
    location=os.getenv("LOCATION", "US"),
    # ... etc
)

# After: Automatic with BaseSettings
config = ServerConfig.from_env()  # or just ServerConfig()
```

## Migration Notes

### Breaking Changes

1. **UserContext** is now a Pydantic model instead of dataclass
   - Use `model_dump()` instead of `asdict()`
   - Use `model_dump_json()` instead of custom JSON serialization
   - Validation happens at instantiation, not later

2. **ServerConfig** validates immediately
   - Errors now raised as `ValidationError` instead of `ValueError`
   - No need to call `validate()` separately

### Backward Compatibility

- **Legacy `validate()` method** still exists on ServerConfig for backward compatibility
- **from_env()** still works as before
- All existing tests pass without modification

## Testing

All tests pass successfully:
```bash
uv run pytest tests/ -v
# 71 tests passed
```

Coverage:
- `auth.py`: 84% coverage
- `settings.py`: 100% coverage

## Documentation

Updated documentation:
- `docs/AUTH.md` - Added Pydantic models section
- `docs/AUTH.md` - Added validation error handling section
- `IMPLEMENTATION_SUMMARY.md` - Original implementation details
- `PYDANTIC_IMPLEMENTATION.md` - This document

## Example Usage

### Creating and Validating UserContext

```python
from mcp_bigquery.core.auth import UserContext
from pydantic import ValidationError

# Valid context
context = UserContext(
    user_id="user-123",
    email="test@example.com",
    roles=["analyst"],
    permissions={"query:execute"}
)

# Invalid context - raises ValidationError
try:
    context = UserContext(user_id="")
except ValidationError as e:
    print(e.errors())
```

### Using ServerConfig with Pydantic

```python
from mcp_bigquery.config.settings import ServerConfig
from pydantic import ValidationError

# Load from environment
config = ServerConfig.from_env()

# Validation errors are clear
try:
    config = ServerConfig(project_id="")
except ValidationError as e:
    print(e.errors())
    # [{'type': 'value_error', 'msg': 'Project ID is required and cannot be empty', ...}]
```

### Working with RBAC Models

```python
from mcp_bigquery.core.auth import UserRole, RolePermission, DatasetAccess

# Create models with validation
role = UserRole(
    user_id="user-123",
    role_id="role-1",
    role_name="analyst"
)

permission = RolePermission(
    role_id="role-1",
    permission="query:execute"
)

access = DatasetAccess(
    role_id="role-1",
    dataset_id="analytics",
    table_id="events"
)

# Serialize to dict
role_dict = role.model_dump()

# Serialize to JSON
role_json = role.model_dump_json()
```

## Next Steps

Potential future enhancements:
1. Add more custom validators for email format (use `EmailStr`)
2. Add validators for URL formats (use `HttpUrl`)
3. Add schema generation for API documentation
4. Use Pydantic models for API request/response validation
5. Add computed fields for derived properties
