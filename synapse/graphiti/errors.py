"""
Copyright 2024, Zep Software, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""


class GraphitiError(Exception):
    """Base exception class for Graphiti Core."""


class EdgeNotFoundError(GraphitiError):
    """Raised when an edge is not found."""

    def __init__(self, uuid: str):
        self.message = f'edge {uuid} not found'
        super().__init__(self.message)


class EdgesNotFoundError(GraphitiError):
    """Raised when a list of edges is not found."""

    def __init__(self, uuids: list[str]):
        self.message = f'None of the edges for {uuids} were found.'
        super().__init__(self.message)


class GroupsEdgesNotFoundError(GraphitiError):
    """Raised when no edges are found for a list of group ids."""

    def __init__(self, group_ids: list[str]):
        self.message = f'no edges found for group ids {group_ids}'
        super().__init__(self.message)


class GroupsNodesNotFoundError(GraphitiError):
    """Raised when no nodes are found for a list of group ids."""

    def __init__(self, group_ids: list[str]):
        self.message = f'no nodes found for group ids {group_ids}'
        super().__init__(self.message)


class NodeNotFoundError(GraphitiError):
    """Raised when a node is not found."""

    def __init__(self, uuid: str):
        self.message = f'node {uuid} not found'
        super().__init__(self.message)


class SearchRerankerError(GraphitiError):
    """Raised when a node is not found."""

    def __init__(self, text: str):
        self.message = text
        super().__init__(self.message)


class EntityTypeValidationError(GraphitiError):
    """Raised when an entity type uses protected attribute names."""

    def __init__(self, entity_type: str, entity_type_attribute: str):
        self.message = f'{entity_type_attribute} cannot be used as an attribute for {entity_type} as it is a protected attribute name.'
        super().__init__(self.message)


class GroupIdValidationError(GraphitiError):
    """Raised when a group_id contains invalid characters."""

    def __init__(self, group_id: str):
        self.message = f'group_id "{group_id}" must contain only alphanumeric characters, dashes, or underscores'
        super().__init__(self.message)


class NodeLabelValidationError(GraphitiError, ValueError):
    """Raised when a node label contains invalid characters."""

    def __init__(self, node_labels: list[str]):
        label_list = ', '.join(f'"{label}"' for label in node_labels)
        self.message = (
            'node_labels must start with a letter or underscore and contain only '
            f'alphanumeric characters or underscores: {label_list}'
        )
        super().__init__(self.message)


# ============================================
# Synapse-specific exceptions for Layer 3
# ============================================


class GraphitiWriteError(GraphitiError):
    """Raised when a Graphiti write operation fails.

    This is a critical error that indicates data was not persisted
    to the knowledge graph. Unlike silent failures, this exception
    forces the caller to handle the error explicitly.

    Common causes:
    - Database connection lost
    - LLM extraction failed
    - Invalid entity/edge data
    """

    def __init__(self, operation: str, reason: str, entity_name: str | None = None):
        self.operation = operation
        self.reason = reason
        self.entity_name = entity_name
        if entity_name:
            self.message = f"Graphiti write failed during '{operation}' for entity '{entity_name}': {reason}"
        else:
            self.message = f"Graphiti write failed during '{operation}': {reason}"
        super().__init__(self.message)


class GraphitiConnectionError(GraphitiError):
    """Raised when Graphiti connection is unavailable or broken.

    This indicates a systemic issue with the graph database connection,
    not a transient write failure.

    Common causes:
    - Graphiti client not initialized
    - Database server down
    - Network connectivity issues
    - Authentication failure
    """

    def __init__(self, reason: str, database_type: str | None = None):
        self.reason = reason
        self.database_type = database_type
        if database_type:
            self.message = f"Graphiti connection error ({database_type}): {reason}"
        else:
            self.message = f"Graphiti connection error: {reason}"
        super().__init__(self.message)


class GraphitiNotInitializedError(GraphitiError):
    """Raised when Graphiti operations are attempted without initialization.

    This typically occurs when:
    - SYNAPSE_REQUIRE_GRAPHITI=true but Graphiti client is None
    - Database driver failed to initialize
    - Configuration is missing required fields
    """

    def __init__(self, operation: str):
        self.operation = operation
        self.message = (
            f"Graphiti not initialized for operation '{operation}'. "
            "Check database configuration or set SYNAPSE_REQUIRE_GRAPHITI=false "
            "to run in degraded mode."
        )
        super().__init__(self.message)
