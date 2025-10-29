"""RBAC utility functions for BigQuery access control."""
from typing import List, Tuple, Optional
from .auth import UserContext, AuthorizationError, normalize_identifier


def check_dataset_access(user_context: UserContext, dataset_id: str) -> None:
    """Check if user has access to a dataset.
    
    Args:
        user_context: User context with permissions
        dataset_id: Dataset identifier
        
    Raises:
        AuthorizationError: If user lacks access to the dataset
    """
    normalized_dataset = normalize_identifier(dataset_id)
    if not user_context.can_access_dataset(normalized_dataset):
        raise AuthorizationError(f"Access denied to dataset {dataset_id}")


def check_table_access_simple(user_context: UserContext, dataset_id: str, table_id: str) -> None:
    """Check if user has access to a specific table.
    
    Args:
        user_context: User context with permissions
        dataset_id: Dataset identifier
        table_id: Table identifier
        
    Raises:
        AuthorizationError: If user lacks access to the table
    """
    normalized_dataset = normalize_identifier(dataset_id)
    normalized_table = normalize_identifier(table_id)
    if not user_context.can_access_table(normalized_dataset, normalized_table):
        raise AuthorizationError(f"Access denied to table {dataset_id}.{table_id}")


def check_table_references(
    user_context: UserContext,
    table_references: List[Tuple[Optional[str], Optional[str], Optional[str]]]
) -> None:
    """Check if user has access to all tables in a list of references.
    
    Args:
        user_context: User context with permissions
        table_references: List of (project, dataset, table) tuples
        
    Raises:
        AuthorizationError: If user lacks access to any referenced table
    """
    for project_id, dataset_id, table_id in table_references:
        # Skip if we couldn't parse the reference
        if not dataset_id and not table_id:
            continue
        
        # Check access based on what we extracted
        if dataset_id and table_id:
            # Full dataset.table reference
            check_table_access_simple(user_context, dataset_id, table_id)
        elif dataset_id and not table_id:
            # Dataset-only reference
            check_dataset_access(user_context, dataset_id)


def check_permission(user_context: UserContext, permission: str) -> None:
    """Check if user has a specific permission.
    
    Args:
        user_context: User context with permissions
        permission: Permission string (e.g., "query:execute")
        
    Raises:
        AuthorizationError: If user lacks the required permission
    """
    if not user_context.has_permission(permission):
        raise AuthorizationError(f"Missing required permission: {permission}")
