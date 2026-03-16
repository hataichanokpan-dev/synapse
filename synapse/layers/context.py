"""
UserContext - Per-user isolation for memory managers

Each user gets their own:
- Database files (SQLite)
- Manager instances
- Working memory

Usage:
    # Create context for a user
    context = UserContext.create("alice")

    # Access managers
    semantic = context.semantic  # Lazy-loaded SemanticManager
    episodic = context.episodic  # Lazy-loaded EpisodicManager

    # Get user's database path
    db_path = context.db_base_path  # ~/.synapse/users/alice/
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.layers.semantic import SemanticManager
    from synapse.layers.episodic import EpisodicManager
    from synapse.layers.procedural import ProceduralManager
    from synapse.layers.working import WorkingManager
    from synapse.layers.user_model import UserModelManager


@dataclass
class UserContext:
    """
    Holds all manager instances for a specific user.

    Each user gets their own:
    - Database files (SQLite)
    - Manager instances
    - Working memory
    """

    user_id: str
    db_base_path: Path

    # Lazy-loaded managers
    _semantic: Optional["SemanticManager"] = field(default=None, repr=False)
    _episodic: Optional["EpisodicManager"] = field(default=None, repr=False)
    _procedural: Optional["ProceduralManager"] = field(default=None, repr=False)
    _working: Optional["WorkingManager"] = field(default=None, repr=False)
    _user_model: Optional["UserModelManager"] = field(default=None, repr=False)

    @classmethod
    def create(cls, user_id: str, base_path: Optional[Path] = None) -> "UserContext":
        """
        Create a new UserContext with proper paths.

        Args:
            user_id: User identifier
            base_path: Base path for user data (default: ~/.synapse)

        Returns:
            UserContext instance
        """
        if base_path is None:
            base_path = Path.home() / ".synapse"

        user_path = base_path / "users" / user_id
        user_path.mkdir(parents=True, exist_ok=True)

        return cls(user_id=user_id, db_base_path=user_path)

    @property
    def semantic(self) -> "SemanticManager":
        """Get SemanticManager for this user (lazy-loaded)."""
        if self._semantic is None:
            from synapse.layers.semantic import SemanticManager
            self._semantic = SemanticManager()
        return self._semantic

    @property
    def episodic(self) -> "EpisodicManager":
        """Get EpisodicManager for this user (lazy-loaded)."""
        if self._episodic is None:
            from synapse.layers.episodic import EpisodicManager
            self._episodic = EpisodicManager(db_path=self.db_base_path / "episodic.db")
        return self._episodic

    @property
    def procedural(self) -> "ProceduralManager":
        """Get ProceduralManager for this user (lazy-loaded)."""
        if self._procedural is None:
            from synapse.layers.procedural import ProceduralManager
            self._procedural = ProceduralManager(db_path=self.db_base_path / "procedural.db")
        return self._procedural

    @property
    def working(self) -> "WorkingManager":
        """Get WorkingManager for this user (lazy-loaded)."""
        if self._working is None:
            from synapse.layers.working import WorkingManager
            self._working = WorkingManager()
        return self._working

    @property
    def user_model(self) -> "UserModelManager":
        """Get UserModelManager for this user (lazy-loaded)."""
        if self._user_model is None:
            from synapse.layers.user_model import UserModelManager
            self._user_model = UserModelManager(db_path=self.db_base_path / "user_model.db")
        return self._user_model

    def clear(self) -> None:
        """Clear all cached manager instances."""
        self._semantic = None
        self._episodic = None
        self._procedural = None
        self._working = None
        self._user_model = None
